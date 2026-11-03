# -*- coding: utf-8 -*-
"""Content gate. Runs before the app is built and refuses to ship broken content.

Checks, in order:
  1. bank sizes are at least 5x the exam draw
  2. every MCQ has 4 unique options and a valid answer index
  3. every SQL reference runs against data/mock.db and returns rows
  4. every Python reference runs against its fixture and returns JSON
  5. no em dashes or template placeholders anywhere in content

Run: python3 build/verify.py
"""
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
from ordering import balanced_options  # noqa: E402

DB = os.path.join(ROOT, "data", "mock.db")
DRAW = {"mcq": 11, "sql": 3, "py": 2}
MULTIPLE = 5


def check_mcq():
    problems = []
    ids = set()
    for i, q in enumerate(MCQ_BANK):
        if q["id"] in ids:
            problems.append("duplicate id %s" % q["id"])
        ids.add(q["id"])
        if len(q["options"]) != 4:
            problems.append("%s has %d options" % (q["id"], len(q["options"])))
        if len(set(q["options"])) != 4:
            problems.append("%s has duplicate options" % q["id"])
        if not (0 <= q["answer"] < 4):
            problems.append("%s answer index out of range" % q["id"])
        if q["topic"] not in TOPICS:
            problems.append("%s unknown topic %s" % (q["id"], q["topic"]))
        if not q.get("why"):
            problems.append("%s has no explanation" % q["id"])
    # An answer key concentrated in one position is a guessing strategy, not a
    # test. Check the distribution the candidate actually sees, after the build's
    # deterministic shuffle, not the authored order.
    spread = {i: sum(1 for q in MCQ_BANK if balanced_options(q)[1] == i) for i in range(4)}
    for i, n in spread.items():
        if n < len(MCQ_BANK) * 0.12:
            problems.append("answer position %s used only %d times: %s" % ("ABCD"[i], n, spread))
    return problems


def check_sql():
    problems, expected = [], {}
    if not os.path.exists(DB):
        problems.append("database missing, run build/gen_db.py")
        return problems, expected
    con = sqlite3.connect(DB)
    for t in SQL_TASKS:
        try:
            cur = con.execute(t["reference"])
            cols = [c[0] for c in cur.description]
            rows = [list(r) for r in cur.fetchall()]
        except Exception as exc:  # noqa: BLE001
            problems.append("%s failed: %s" % (t["id"], exc))
            continue
        if not rows:
            problems.append("%s returned no rows" % t["id"])
        expected[t["id"]] = {"cols": cols, "rows": rows}
    con.close()
    return problems, expected


def check_py():
    problems, expected = [], {}
    for t in PY_TASKS:
        ns = {}
        try:
            exec(compile(t["fixture_py"], "<fixture>", "exec"), ns)
            ns[t["entry"]] = t["reference_fn"]
            value = eval(t["call"], ns)  # noqa: S307
            blob = json.loads(json.dumps(value))
        except Exception as exc:  # noqa: BLE001
            problems.append("%s failed: %s" % (t["id"], exc))
            continue
        if blob in ([], None, {}):
            problems.append("%s produced an empty result" % t["id"])
        expected[t["id"]] = blob
    return problems, expected


def _serialisable(tasks):
    """Strip callables so the text check can inspect everything else."""
    out = []
    for t in tasks:
        out.append({k: v for k, v in t.items() if not callable(v)})
    return out


def check_text():
    problems = []
    blob = json.dumps([MCQ_BANK, SQL_TASKS, _serialisable(PY_TASKS), TOPICS],
                      ensure_ascii=False)
    if "\u2014" in blob:
        problems.append("em dash in content")
    for bad in ("[X]", "[company]", "TODO", "insert here"):
        if bad in blob:
            problems.append("placeholder %s in content" % bad)
    return problems


def main():
    problems = []
    problems += check_mcq()
    sql_problems, sql_expected = check_sql()
    problems += sql_problems
    py_problems, py_expected = check_py()
    problems += py_problems
    problems += check_text()

    counts = {"mcq": len(MCQ_BANK), "sql": len(SQL_TASKS), "py": len(PY_TASKS)}
    print("bank sizes")
    for k, n in counts.items():
        need = DRAW[k] * MULTIPLE
        flag = "ok" if n >= need else "TOO SMALL"
        print("  %-4s %3d items, exam draws %2d, need >= %3d  [%s]" % (k, n, DRAW[k], need, flag))
        if n < need:
            problems.append("%s bank is %d, need %d for a 5x ratio" % (k, n, need))

    print("\nexpected outputs")
    for tid, exp in sql_expected.items():
        print("  %-6s %3d rows" % (tid, len(exp["rows"])))
    for tid, exp in py_expected.items():
        print("  %-6s %s" % (tid, json.dumps(exp)[:90]))

    if problems:
        print("\nFAIL")
        for p in problems:
            print("  -", p)
        return 1
    print("\nPASS: %d problems" % len(problems))
    return 0


if __name__ == "__main__":
    sys.exit(main())
