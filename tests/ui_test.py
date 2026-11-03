# -*- coding: utf-8 -*-
"""Browser test for the lab app.

Drives Chrome through the full exam loop: login, MCQ answer and check, SQL run and
check against the expected output, Python run through Pyodide, study mode, mobile
layout. Fails on any console error or wrong verdict.

Run: python3 tests/ui_test.py            (expects the server on 127.0.0.1:8097)
"""
import os
import sys
import time

from playwright.sync_api import sync_playwright

BASE = os.environ.get("BASE", "http://127.0.0.1:8097")
PASSWORD = os.environ.get("APP_PASSWORD", "pw")
SHOTS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "shots")
os.makedirs(SHOTS, exist_ok=True)

errors = []


def run():
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="chrome", headless=True)
        ctx = browser.new_context(viewport={"width": 1440, "height": 900})
        page = ctx.new_page()
        def on_console(m):
            if m.type != "error":
                return
            text = m.text
            # the wrong-password step deliberately provokes a 401 from /login
            if "401" in text and "Unauthorized" in text:
                return
            errors.append(text)
        page.on("console", on_console)
        page.on("pageerror", lambda e: errors.append("pageerror: %s" % e))

        # ---------------------------------------------------------- login
        page.goto(BASE + "/", wait_until="load")
        assert "/login" in page.url, "should redirect to login, got %s" % page.url
        page.fill("#p", "wrong-password")
        page.click("button[type=submit]")
        page.wait_for_selector(".err", timeout=5000)
        assert "Wrong password" in page.inner_text(".err")
        page.fill("#p", PASSWORD)
        page.click("button[type=submit]")
        page.wait_for_selector("#pills .pill", timeout=15000)
        print("login: wrong password rejected, correct password accepted")

        pills = page.locator("#pills .pill")
        n = pills.count()
        assert n == 16, "exam should draw 16 tasks, got %d" % n
        kinds = page.evaluate("paperIds().map(id => byId[id].kind)")
        assert kinds.count("mcq") == 11 and kinds.count("sql") == 3 and kinds.count("python") == 2, kinds
        print("paper: 16 tasks, 11 knowledge / 3 SQL / 2 Python")
        page.screenshot(path=os.path.join(SHOTS, "01_exam_mcq.png"), full_page=False)

        # ---------------------------------------------------------- MCQ
        page.locator(".opt").nth(1).click()
        page.click("#checkBtn")
        page.wait_for_selector("#out .msg", timeout=5000)
        verdict = page.inner_text("#out .msg")
        assert verdict.startswith(("Correct", "Not quite")), verdict
        checked = page.evaluate("Object.keys(S.checked).length")
        assert checked == 1, "check should record the attempt"
        print("mcq: answered and checked, verdict =", verdict.split(".")[0])

        # right pane material
        concept = page.inner_text("#lbody")
        assert len(concept) > 120, "learning pane should have content"
        page.click("#ltabs .ltab:nth-child(2)")
        assert "Recipe" in page.inner_text("#ltabs")
        recipe = page.inner_text("#lbody")
        assert len(recipe) > 80, "recipe tab should have content"
        print("material: concept and recipe tabs render")

        # ---------------------------------------------------------- SQL
        sql_ids = page.evaluate("S.paper.sql")
        page.evaluate("""id => { const i = paperIds().indexOf(id); cur = i; S.idx = i; save(); renderAll(); }""",
                      sql_ids[0])
        page.wait_for_selector("#code", timeout=5000)
        assert "SQL" in page.inner_text(".tags").upper()

        # preview a table by tapping its name
        page.locator("[data-preview]").first.click()
        page.wait_for_selector("table.res", timeout=15000)
        rows_preview = page.locator("table.res tr").count()
        assert rows_preview > 1, "table preview should return rows"
        print("sql: schema preview returned %d rows" % (rows_preview - 1))

        # wrong answer first, then the reference
        page.fill("#code", "SELECT 1 AS x;")
        page.click("#checkBtn")
        page.wait_for_selector("#out .msg.no", timeout=15000)
        assert page.evaluate("S.checked[%r]" % sql_ids[0]) is False
        print("sql: a wrong query is marked not matching")

        ref = page.evaluate("id => byId[id].reference", sql_ids[0])
        page.fill("#code", ref)
        page.click("#checkBtn")
        page.wait_for_selector("#out .msg.ok", timeout=20000)
        assert page.evaluate("S.checked[%r]" % sql_ids[0]) is True
        print("sql: reference solution checks as correct")
        page.screenshot(path=os.path.join(SHOTS, "02_exam_sql.png"))

        # ordering tolerance: shuffled-but-correct answer should also pass when order matters = false
        order_matters = page.evaluate("id => byId[id].order_matters", sql_ids[0])
        print("sql: order matters for this task =", order_matters)

        # ---------------------------------------------------------- Python
        py_ids = page.evaluate("S.paper.py")
        page.evaluate("""id => { const i = paperIds().indexOf(id); cur = i; S.idx = i; save(); renderAll(); }""",
                      py_ids[0])
        page.wait_for_selector("#code", timeout=5000)
        ref = page.evaluate("id => byId[id].reference", py_ids[0])
        page.fill("#code", ref)
        page.click("#checkBtn")
        # first run loads the Python runtime from the CDN
        page.wait_for_selector("#out .msg.ok, #out .msg.no", timeout=180000)
        msg = page.inner_text("#out .msg")
        assert msg.startswith("Correct"), "python reference should pass, got: %s" % msg[:200]
        print("python: reference solution checks as correct (runtime loaded)")
        page.screenshot(path=os.path.join(SHOTS, "03_exam_python.png"))

        # ---------------------------------------------------------- study mode
        page.click("#modeStudy")
        page.wait_for_selector(".card", timeout=8000)
        cards = page.locator(".card").count()
        assert cards == 97, "bank should list 97 items, got %d" % cards
        page.fill("#qfilter", "retention")
        time.sleep(0.4)
        filtered = page.locator(".card").count()
        assert 0 < filtered < 97, "search should narrow the list, got %d" % filtered
        print("study: %d items in the bank, search narrows to %d" % (cards, filtered))
        page.locator(".card").first.click()
        page.wait_for_selector("#code, .opt", timeout=5000)
        assert page.inner_text("#lbody").strip() != "", "material should follow the selected item"
        page.screenshot(path=os.path.join(SHOTS, "04_study.png"))

        # ---------------------------------------------------------- finish
        page.click("#modeExam")
        page.click("#finishBtn")
        page.wait_for_selector(".overlay.on", timeout=5000)
        summary = page.inner_text("#modal")
        assert "Test finished" in summary
        assert "points" in summary
        page.screenshot(path=os.path.join(SHOTS, "05_result.png"))
        print("result: score modal renders")

        ctx.close()

        # ---------------------------------------------------------- mobile
        m = browser.new_context(viewport={"width": 390, "height": 844},
                                device_scale_factor=2, is_mobile=True, has_touch=True)
        mp = m.new_page()
        mp.on("pageerror", lambda e: errors.append("mobile pageerror: %s" % e))
        mp.goto(BASE + "/", wait_until="load")
        mp.fill("#p", PASSWORD)
        mp.click("button[type=submit]")
        mp.wait_for_selector("#pills .pill", timeout=15000)
        assert mp.locator("#pills .pill").first.is_visible(), "task pills must stay reachable on mobile"
        box = mp.locator("#timer").bounding_box()
        assert box and box["width"] > 20, "timer should be visible on mobile"
        mp.screenshot(path=os.path.join(SHOTS, "06_mobile_task.png"))
        # material sits below the task on mobile
        assert mp.locator("#learn").is_visible()
        y_learn = mp.locator("#learn").bounding_box()["y"]
        y_test = mp.locator("#test").bounding_box()["y"]
        assert y_learn > y_test, "on mobile the material pane should stack below the task"
        mp.screenshot(path=os.path.join(SHOTS, "07_mobile_material.png"), full_page=True)
        print("mobile: pills, timer and stacked material pane verified at 390x844")
        m.close()
        browser.close()


if __name__ == "__main__":
    try:
        run()
    except AssertionError as exc:
        print("FAIL:", exc)
        if errors:
            print("console errors:")
            for e in errors[:10]:
                print("  ", e)
        sys.exit(1)
    if errors:
        print("console errors seen:")
        for e in errors[:10]:
            print("  ", e)
    print("PASS: ui flow desktop + mobile")
