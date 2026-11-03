# -*- coding: utf-8 -*-
"""Assembles app/index.html: content + database + SQL engine inlined into one file.

Run: python3 build/build_app.py   (after build/gen_db.py and build/verify.py)
Out: app/index.html and app/index.html.gz
"""
import base64
import gzip
import inspect
import json
import os
import sqlite3
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "content"))

from bank_mcq import MCQ_BANK          # noqa: E402
from bank_sql import SQL_TASKS         # noqa: E402
from bank_py import PY_TASKS           # noqa: E402
from topics import TOPICS              # noqa: E402
from library import LIBRARY            # noqa: E402

DB = os.path.join(ROOT, "data", "mock.db")
SCHEMA = [
    ["users", "user_id, signup_date, city, country, channel, is_unlimited"],
    ["bookings", "booking_id, user_id, service_type, booking_ts, gmv, promo_code, status"],
    ["campaign_sends", "send_id, campaign_id, user_id, variant, sent_ts, opened, clicked, "
                       "redeemed, booked_7d"],
    ["user_events", "user_id, event_date, event_type"],
    ["campaign_costs", "campaign_id, region, total_cost_idr, sent_at"],
]
EXAM = {"mcq": 11, "sql": 3, "py": 2}
MINUTES = 110


def sql_expected():
    con = sqlite3.connect(DB)
    out = {}
    for t in SQL_TASKS:
        cur = con.execute(t["reference"])
        out[t["id"]] = {
            "cols": [c[0] for c in cur.description],
            "rows": [list(r) for r in cur.fetchall()],
        }
    con.close()
    return out


def py_expected():
    out = {}
    for t in PY_TASKS:
        ns = {}
        exec(compile(t["fixture_py"], "<fixture>", "exec"), ns)  # noqa: S102
        ns[t["entry"]] = t["reference_fn"]
        out[t["id"]] = json.loads(json.dumps(eval(t["call"], ns)))  # noqa: S307
    return out


def build_tasks():
    exp_sql, exp_py = sql_expected(), py_expected()
    tasks = []

    for q in MCQ_BANK:
        tasks.append(dict(
            id=q["id"], kind="mcq", pool="mcq", points=4,
            title=q["q"][:95] + ("…" if len(q["q"]) > 95 else ""),
            tags="Knowledge  ·  %s  ·  4 points" % TOPICS[q["topic"]]["name"],
            prompt=q["q"], options=q["options"], answer=q["answer"],
            why=q["why"], note=q.get("note", ""), topic=q["topic"],
            learning=TOPICS[q["topic"]],
            hints=[q["why"].split(". ")[0] + "."],
        ))

    for t in SQL_TASKS:
        tasks.append(dict(
            id=t["id"], kind="sql", pool="sql", points=20,
            title=t["title"], tags=t["tags"], prompt=t["prompt"],
            contract=t["contract"], reference=t["reference"],
            starter=t["starter"], order_matters=t["order_matters"],
            learning=t["learning"], hints=t["hints"], schema=SCHEMA,
            expected=exp_sql[t["id"]],
        ))

    for t in PY_TASKS:
        tasks.append(dict(
            id=t["id"], kind="python", pool="py", points=20,
            title=t["title"], tags=t["tags"], prompt=t["prompt"],
            entry=t["entry"], fixture_py=t["fixture_py"], call=t["call"],
            # Rename to the public entry point the task asks for, and prepend the
            # imports the body relies on, so the pasted reference runs as-is.
            reference=("import datetime as dt\nimport math\n\n"
                       + inspect.getsource(t["reference_fn"])
                       .replace("def %s(" % t["reference_fn"].__name__,
                                "def %s(" % t["entry"], 1).rstrip()),
            starter=t["starter"], learning=t["learning"], hints=t["hints"],
            expected=exp_py[t["id"]],
        ))
    return tasks


def main():
    tasks = build_tasks()
    tpl = open(os.path.join(HERE, "template.html"), encoding="utf-8").read()
    sqljs = open(os.path.join(HERE, "sql-wasm.js"), encoding="utf-8").read()
    wasm_b64 = base64.b64encode(open(os.path.join(HERE, "sql-wasm.wasm"), "rb").read()).decode()
    db_b64 = base64.b64encode(open(DB, "rb").read()).decode()

    html = (tpl
            .replace("{{TASKS_JSON}}", json.dumps(tasks, ensure_ascii=False))
            .replace("{{LIBRARY_JSON}}", json.dumps(LIBRARY, ensure_ascii=False))
            .replace("{{EXAM_JSON}}", json.dumps(EXAM))
            .replace("{{MINUTES}}", str(MINUTES))
            .replace("{{DB_B64}}", db_b64)
            .replace("{{WASM_B64}}", wasm_b64)
            .replace("{{SQLJS_JS}}", sqljs))

    outdir = os.path.join(ROOT, "app")
    os.makedirs(outdir, exist_ok=True)  # the Docker build stage has no app/ yet
    out = os.path.join(outdir, "index.html")
    with open(out, "w", encoding="utf-8") as f:
        f.write(html)
    with gzip.open(out + ".gz", "wb", compresslevel=9) as f:
        f.write(html.encode("utf-8"))

    raw = os.path.getsize(out)
    gz = os.path.getsize(out + ".gz")
    print("wrote %s" % out)
    print("  raw %.2f MB, gzipped %.2f MB" % (raw / 1048576.0, gz / 1048576.0))
    counts = {}
    for t in tasks:
        counts[t["pool"]] = counts.get(t["pool"], 0) + 1
    print("  tasks: %s, exam draws %s, ratio %.1fx"
          % (counts, EXAM, sum(counts.values()) / sum(EXAM.values())))


if __name__ == "__main__":
    main()
