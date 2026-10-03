#!/usr/bin/env python3
"""Deadline Radar.

    python3 app.py                    read .env, offer both readers in the UI
    python3 app.py --offline          never touch the network (demo and testing)
    python3 app.py --analyse page.txt print the validated brief as JSON
    python3 app.py --plan             print the demo scenario as JSON

Standard library only. Python 3.9+.
"""

import argparse
import json
import os
import sys
import threading
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from radar import demo, extract, ics, web                     # noqa: E402
from radar.pipeline import Pipeline                           # noqa: E402
from radar.store import DEFAULT_DB, Store                     # noqa: E402

DEFAULT_PORT = int(os.environ.get("PORT", "8781"))


def build_parser():
    parser = argparse.ArgumentParser(
        prog="app.py", description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--offline", action="store_true",
                        help="disable the language-model reader; the deterministic reader is used")
    parser.add_argument("--db", default=None, help="sqlite3 file for the history")
    parser.add_argument("--analyse", metavar="FILE",
                        help="analyse a text file and print the brief as JSON")
    parser.add_argument("--source", metavar="FILE", help="page text to use with --demo")
    parser.add_argument("--demo", type=int, metavar="N",
                        help="run a tour step and print the brief as JSON")
    parser.add_argument("--plan", action="store_true", help="print the demo scenario as JSON")
    parser.add_argument("--ics", metavar="FILE", help="also write the calendar to this file")
    parser.add_argument("--quiet", action="store_true", help="no request logging")
    return parser


def read_text(path):
    with open(path, "r", encoding="utf-8") as fh:
        return fh.read()


def _analyse_once(args, pipeline, store):
    inject = None
    if args.analyse:
        text = read_text(args.analyse)
        if args.analyse.endswith("__hallucinated.txt"):
            inject = demo.hallucinate
    else:
        step = demo.step_by_number(args.demo, pipeline)
        if step is None:
            sys.stderr.write("no such tour step: %s\n" % args.demo)
            return 2
        if args.source:
            text = read_text(args.source)
        else:
            result = step["result"]
            if result is None:
                sys.stderr.write("step %s has no brief\n" % args.demo)
                return 2
            text, inject = step["source"], None
    mode = "offline" if args.offline else "llm"
    result, analysis_id = pipeline.run(text, mode=mode, inject=inject)
    out = {
        "id": analysis_id, "mode": mode, "brief": result["brief"],
        "counts": result["counts"], "key_dates": result["key_dates"],
        "rejected": result["rejected"], "events": result["events"],
    }
    print(json.dumps(out, indent=2, ensure_ascii=False))
    if args.ics:
        with open(args.ics, "w", encoding="utf-8", newline="") as fh:
            fh.write(ics.build(result))
        sys.stderr.write("wrote %s\n" % args.ics)
    return 0


def main(argv=None):
    args = build_parser().parse_args(argv)

    if args.plan:
        print(demo.plan_json())
        return 0

    one_shot = bool(args.analyse) or args.demo is not None
    store = Store(args.db) if args.db else Store(":memory:" if one_shot else DEFAULT_DB)
    pipeline = Pipeline(store, offline_default=args.offline)
    if one_shot:
        try:
            return _analyse_once(args, pipeline, store)
        finally:
            store.close()

    if not args.offline and not extract.configured():
        sys.stderr.write("note: no LLM_* settings found, so the language-model reader will be\n"
                         "      unavailable in the UI. Start with --offline to hide it entirely.\n")

    httpd = web.make_server(host=args.host, port=args.port, db=args.db,
                            offline_default=args.offline, pipeline=pipeline, quiet=args.quiet)
    url = "http://%s:%d/" % (args.host, args.port)
    print("Deadline Radar on %s" % url)
    print("  reader default : %s" % ("offline (no network)" if args.offline else "language model"))
    print("  guided tour    : %s?demo=0   (step list: %sapi/demo)" % (url, url))
    print("  history store  : %s" % store.path)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nstopping")
    finally:
        httpd.shutdown()
        httpd.server_close()
        store.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
