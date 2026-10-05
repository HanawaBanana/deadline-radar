"""The HTTP layer: a single stdlib http.server, three JSON endpoints and pages.

Routes
    GET  /                        the app (or a guided-tour step with ?demo=N)
    GET  /analysis/<id>           a saved analysis, reopened from sqlite3
    GET  /ics/<id>                the .ics text as a page (so it can be shown)
    GET  /api/analysis/<id>       the analysis as JSON
    GET  /api/analysis/<id>.ics   the calendar file (attachment)
    GET  /api/analysis/<id>.html  the brief as one standalone HTML file (attachment)
    GET  /api/history             JSON + rendered HTML for the history list
    GET  /api/demo                the guided tour as JSON (a tiny demo driver)
    POST /api/analyse             {"text": ..., "mode": "offline"|"llm"}
    GET  /static/<file>           css and js
    GET  /healthz                 health probe

The analysis itself lives in radar.pipeline; this module only moves bytes.
"""

import json
import mimetypes
import os
import posixpath
import time
import traceback
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from . import demo as demo_mod
from . import export as export_mod
from . import ics as ics_mod
from . import render
from .store import Store

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATIC_DIR = os.path.join(ROOT, "static")
TEMPLATE = os.path.join(ROOT, "templates", "index.html")

MAX_BODY = 400_000


def read_template():
    with open(TEMPLATE, "r", encoding="utf-8") as fh:
        return fh.read()


class Handler(BaseHTTPRequestHandler):
    server_version = "DeadlineRadar/1.0"
    protocol_version = "HTTP/1.1"

    # ---------------- helpers ----------------
    @property
    def store(self):
        return self.server.store

    @property
    def offline_default(self):
        return self.server.offline_default

    def log_message(self, fmt, *args):
        if getattr(self.server, "quiet", False):
            return
        BaseHTTPRequestHandler.log_message(self, fmt, *args)

    def send_html(self, body, status=200):
        data = body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def send_json(self, payload, status=200):
        data = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def send_text(self, text, content_type="text/plain; charset=utf-8", status=200, filename=None):
        data = text.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        if filename:
            self.send_header("Content-Disposition", 'attachment; filename="%s"' % filename)
        self.end_headers()
        self.wfile.write(data)

    def page(self, result=None, source="", analysis_id=None, tour=None, mode=None, extra_note=""):
        mode = mode or ("llm" if (self.offline_default is False) else "offline")
        result_html = ""
        if result is not None:
            result_html = render.result_html(result, source, analysis_id)
        elif source.strip():
            result_html = ('<section class="card"><h2>No brief yet</h2>'
                           '<p class="card-note">Press <b>Analyse</b> to read this page: the '
                           'brief, the evidence trail and the calendar appear here.</p>'
                           '</section>')
        else:
            result_html = ('<section class="card"><h2>No brief yet</h2>'
                           '<p class="card-note">Paste an announcement above, or open one of the '
                           'worked examples, then press <b>Analyse</b>.</p></section>')
        rows = self.store.history(20)
        html = render.page(
            read_template(),
            TITLE=("Deadline Radar - " + (tour["title"] if tour else "validated briefs")),
            SOURCE_TEXT=render.esc(source),
            RESULT=result_html,
            HISTORY=render.history_html(rows, analysis_id),
            HISTORY_COUNT=str(len(rows)),
            MODE=render.esc(mode),
            MISSING_TEXT="page does not state",
            SOURCE_NOTE=render.esc(extra_note) if extra_note else
                        ("offline reader: no network is used" if mode == "offline"
                         else "text is sent to the configured model endpoint, then validated locally"),
            OFFLINE_SELECTED=" selected" if mode == "offline" else "",
            LLM_SELECTED=" selected" if mode == "llm" else "",
            BODY_ATTRS=(' class="tour-mode" data-focus="%s"' % render.esc(tour["focus"])) if tour else "",
            TOUR=render.tour_bar(tour) if tour else "",
        )
        self.send_html(html)

    def _analysis_or_404(self, analysis_id):
        found = self.store.get(analysis_id)
        if not found:
            self.send_html("<h1>404</h1><p>No analysis with id %s.</p>"
                           % render.esc(analysis_id), status=404)
        return found

    # ---------------- routes ----------------
    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = urllib.parse.unquote(parsed.path)
        query = urllib.parse.parse_qs(parsed.query)
        try:
            if path == "/favicon.ico":
                self.send_response(204)
                self.send_header("Content-Length", "0")
                self.end_headers()
                return

            if path == "/healthz":
                return self.send_json({"ok": True, "analyses": self.store.count(),
                                       "offline_default": self.offline_default})

            if path.startswith("/static/"):
                return self.serve_static(path[len("/static/"):])

            if path == "/":
                if "demo" in query:
                    step = demo_mod.step_by_number(int(query["demo"][0]),
                                                   self.server.pipeline)
                    if step is None:
                        return self.send_html("<h1>404</h1><p>No such tour step.</p>", status=404)
                    return self.page(result=step["result"], source=step["source"],
                                     analysis_id=step.get("id"), tour=step["tour"],
                                     mode=step["mode"])
                return self.page(mode="offline" if self.offline_default else "llm")

            if path.startswith("/analysis/"):
                found = self._analysis_or_404(path[len("/analysis/"):])
                if not found:
                    return
                return self.page(result=found["result"], source=found["source"],
                                 analysis_id=found["id"], mode=found["result"].get("mode"))

            if path.startswith("/ics/"):
                found = self._analysis_or_404(path[len("/ics/"):])
                if not found:
                    return
                body = ics_mod.build(found["result"])
                page = ("<!DOCTYPE html><html><head><meta charset='utf-8'>"
                        "<title>%s</title><link rel='stylesheet' href='/static/style.css'></head>"
                        "<body><main class='layout'><section class='col-main'>"
                        "<section class='card'><h2>%s</h2>"
                        "<p class='card-note'>This is the exact file the Download button serves: "
                        "%d bytes, RFC 5545. Only validated dates appear in it.</p>"
                        "<pre class='source'>%s</pre>"
                        "<p><a class='btn btn-primary' href='/api/analysis/%s.ics'>Download .ics</a>"
                        " <a class='btn' href='/analysis/%s'>&larr; back to the brief</a></p>"
                        "</section></section></main></body></html>"
                        % (render.esc(ics_mod.filename(found["result"])),
                           render.esc(ics_mod.filename(found["result"])),
                           len(body.encode("utf-8")), render.esc(body), found["id"], found["id"]))
                return self.send_html(page)

            if path == "/api/history":
                rows = self.store.history(20)
                return self.send_json({"rows": rows, "html": render.history_html(rows)})

            if path == "/api/demo":
                return self.send_json({"steps": demo_mod.plan()})

            if path.startswith("/api/analysis/"):
                tail = path[len("/api/analysis/"):]
                if tail.endswith(".ics"):
                    found = self._analysis_or_404(tail[:-4])
                    if not found:
                        return
                    return self.send_text(ics_mod.build(found["result"]),
                                          content_type="text/calendar; charset=utf-8",
                                          filename=ics_mod.filename(found["result"]))
                if tail.endswith(".html"):
                    found = self._analysis_or_404(tail[:-5])
                    if not found:
                        return
                    name = "deadline-radar-brief-%s.html" % found["id"]
                    return self.send_text(export_mod.brief_html(found),
                                          content_type="text/html; charset=utf-8",
                                          filename=name)
                found = self._analysis_or_404(tail)
                if not found:
                    return
                return self.send_json({"id": found["id"], "result": found["result"],
                                       "source": found["source"],
                                       "ics": ics_mod.build(found["result"])})

            return self.send_html("<h1>404</h1><p>%s</p>" % render.esc(path), status=404)
        except Exception:                                  # noqa: BLE001 - surfaced to the caller
            self.send_html("<h1>500</h1><pre>%s</pre>"
                           % render.esc(traceback.format_exc()), status=500)

    def do_POST(self):
        path = urllib.parse.urlparse(self.path).path
        if path != "/api/analyse":
            return self.send_json({"error": "unknown endpoint"}, status=404)
        try:
            length = int(self.headers.get("Content-Length") or 0)
            if length > MAX_BODY:
                return self.send_json({"error": "body too large"}, status=413)
            payload = json.loads(self.rfile.read(length).decode("utf-8") or "{}")
        except ValueError:
            return self.send_json({"error": "invalid JSON body"}, status=400)

        text = (payload.get("text") or "").strip()
        mode = payload.get("mode") or ("offline" if self.offline_default else "llm")
        if mode not in ("offline", "llm"):
            return self.send_json({"error": "mode must be offline or llm"}, status=400)
        if mode == "llm" and self.offline_default:
            return self.send_json({"error": "this server is running with --offline, so the "
                                            "language-model reader is disabled"}, status=400)
        if not text:
            return self.send_json({"error": "no text to analyse"}, status=400)
        try:
            started = time.time()
            result, analysis_id = self.server.pipeline.run(text, mode=mode)
            elapsed = int((time.time() - started) * 1000)
        except Exception as exc:                            # noqa: BLE001
            return self.send_json({"error": "%s: %s" % (type(exc).__name__, exc)}, status=502)
        return self.send_json({
            "id": analysis_id,
            "html": render.result_html(result, text, analysis_id),
            "counts": result.get("counts"),
            "elapsed_ms": elapsed,
            "mode": mode,
        })

    def serve_static(self, rel):
        rel = posixpath.normpath("/" + rel).lstrip("/")
        full = os.path.join(STATIC_DIR, rel)
        if not os.path.abspath(full).startswith(STATIC_DIR) or not os.path.isfile(full):
            return self.send_html("<h1>404</h1>", status=404)
        ctype = mimetypes.guess_type(full)[0] or "application/octet-stream"
        with open(full, "rb") as fh:
            data = fh.read()
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


def make_server(host="127.0.0.1", port=8781, db=None, offline_default=False,
                pipeline=None, quiet=False):
    from .pipeline import Pipeline
    httpd = ThreadingHTTPServer((host, port), Handler)
    httpd.daemon_threads = True
    # When a pipeline is supplied it already owns a store; using a second one
    # would split the history in two (and break the in-memory case entirely).
    httpd.store = pipeline.store if pipeline is not None else (Store(db) if db else Store())
    httpd.offline_default = offline_default
    httpd.pipeline = pipeline or Pipeline(httpd.store, offline_default=offline_default)
    httpd.quiet = quiet
    return httpd
