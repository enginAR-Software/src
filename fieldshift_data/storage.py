"""One SQLite snapshot per run; original text columns remain text."""

import json
import sqlite3


def quoted(name):
    return '"' + name.replace('"', '""') + '"'


def save_database(path, tables, manifest):
    with sqlite3.connect(path) as db:
        db.execute("CREATE TABLE run_metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
        db.execute("INSERT INTO run_metadata VALUES (?, ?)", ("manifest", json.dumps(manifest, ensure_ascii=False)))
        for name, (headers, rows) in tables.items():
            types = []
            for column in headers:
                values = [row.get(column) for row in rows if row.get(column) is not None]
                if values and all(isinstance(v, bool) for v in values):
                    types.append("INTEGER")
                elif values and all(isinstance(v, (int, float)) for v in values):
                    types.append("REAL")
                else:
                    types.append("TEXT")
            definitions = ", ".join(f"{quoted(c)} {t}" for c, t in zip(headers, types))
            db.execute(f"CREATE TABLE {quoted(name)} ({definitions})")
            slots = ", ".join("?" for _ in headers)
            db.executemany(f"INSERT INTO {quoted(name)} VALUES ({slots})",
                           ([row.get(c) for c in headers] for row in rows))
        db.execute("PRAGMA user_version=1")
