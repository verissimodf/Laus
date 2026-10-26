"""Explicit callable permissions; Markdown never grants executable authority."""
import json
import sqlite3
import time


class SkillRuntime:
    def __init__(self, db_path):
        self.conn = sqlite3.connect(db_path)
        self.conn.execute("""CREATE TABLE IF NOT EXISTS episodes (
            id INTEGER PRIMARY KEY, timestamp REAL NOT NULL, skill TEXT NOT NULL,
            status TEXT NOT NULL, context_json TEXT NOT NULL, result_json TEXT NOT NULL)""")
        self.conn.commit()
        self.handlers = {}

    def register(self, name, handler, permissions):
        if name in self.handlers:
            raise ValueError("Duplicate skill")
        self.handlers[name] = (handler, frozenset(permissions))

    def invoke(self, name, arguments, granted=()):
        handler, required = self.handlers[name]
        encoded = json.dumps(arguments, allow_nan=False, sort_keys=True)
        if not required.issubset(frozenset(granted)):
            self._record(name, "DENIED", encoded, {"reason": "MISSING_PERMISSION"})
            raise PermissionError("Skill permissions were not granted")
        try:
            result = handler(**arguments)
            self._record(name, "COMPLETED", encoded, result)
            return result
        except Exception as exc:
            self._record(name, "FAILED", encoded, {"error_type": type(exc).__name__})
            raise

    def _record(self, name, status, context, result):
        encoded = json.dumps(result, allow_nan=False, sort_keys=True)
        with self.conn:
            self.conn.execute("INSERT INTO episodes(timestamp,skill,status,context_json,result_json) VALUES (?,?,?,?,?)",
                              (time.time(), name, status, context, encoded))

    def recent(self, name, limit=20):
        if not isinstance(limit, int) or not 1 <= limit <= 100:
            raise ValueError("limit must be between 1 and 100")
        return self.conn.execute("SELECT timestamp,status,context_json,result_json FROM episodes WHERE skill=? ORDER BY id DESC LIMIT ?",
                                 (name, limit)).fetchall()
