"""History, kept in a single sqlite3 file next to the app.

One row per analysis. The page text is stored too, so the evidence highlighting
still works when an old analysis is reopened days later.
"""

import datetime
import json
import os
import sqlite3
import uuid

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_DB = os.path.join(ROOT, "deadline_radar.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS analyses (
    id          TEXT PRIMARY KEY,
    created_at  TEXT NOT NULL,
    title       TEXT,
    mode        TEXT,
    source_text TEXT,
    source_hash TEXT,
    result_json TEXT
);
"""


class Store(object):
    def __init__(self, path=DEFAULT_DB):
        self.path = path
        if path != ":memory:":
            self.conn = sqlite3.connect(path, check_same_thread=False)
        else:
            self.conn = sqlite3.connect(":memory:", check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA)
        self.conn.commit()

    def save(self, source, result, analysis_id=None):
        analysis_id = analysis_id or uuid.uuid4().hex[:12]
        title = ((result.get("brief") or {}).get("title") or "").strip() or "Untitled page"
        if len(title) > 80:
            title = title[:80]
        self.conn.execute(
            "INSERT OR REPLACE INTO analyses (id, created_at, title, mode, source_text,"
            " source_hash, result_json) VALUES (?,?,?,?,?,?,?)",
            (analysis_id, result.get("created_at") or datetime.datetime.now().isoformat(timespec="seconds"),
             title, result.get("mode"), source,
             (result.get("source") or {}).get("sha256"), json.dumps(result)))
        self.conn.commit()
        return analysis_id

    def get(self, analysis_id):
        row = self.conn.execute("SELECT * FROM analyses WHERE id = ?", (analysis_id,)).fetchone()
        if row is None:
            return None
        return {
            "id": row["id"], "created_at": row["created_at"], "title": row["title"],
            "mode": row["mode"], "source": row["source_text"],
            "result": json.loads(row["result_json"]),
        }

    def history(self, limit=25):
        rows = self.conn.execute(
            "SELECT id, created_at, title, mode, source_hash, result_json FROM analyses"
            " ORDER BY created_at DESC, rowid DESC LIMIT ?", (limit,)).fetchall()
        out = []
        for row in rows:
            result = json.loads(row["result_json"])
            counts = result.get("counts") or {}
            out.append({
                "id": row["id"], "created_at": row["created_at"], "title": row["title"],
                "mode": row["mode"], "counts": counts,
                "verdicts": sum(counts.get(k, 0) for k in ("accepted", "corrected")),
                "rejected": counts.get("rejected", 0),
                "missing": counts.get("missing", 0),
                "events": len(result.get("events") or []),
            })
        return out

    def count(self):
        return self.conn.execute("SELECT COUNT(*) AS n FROM analyses").fetchone()["n"]

    def clear(self):
        self.conn.execute("DELETE FROM analyses")
        self.conn.commit()

    def close(self):
        self.conn.close()
