#!/usr/bin/env python3
"""
Kirator Prompt Intelligence - Comprehensive Test Battery v1.0
Tests all frontend features, API endpoints, and pipeline functionality.
Run from inside kirator_extracted/ with your server + Ollama running.
"""

import sys
import os
import json
import time
import threading
import requests
from bs4 import BeautifulSoup

BASE_URL = "http://127.0.0.1:5000"
PIPELINE_TIMEOUT = 300
POLL_INTERVAL = 1.5
TEST_PROMPT = "Explain how neural networks learn through backpropagation"

results = {"pass": 0, "fail": 0, "skip": 0, "tests": []}

def log_test(category, name, passed, detail=""):
    status = "PASS" if passed else "FAIL"
    results[status.lower()] += 1
    results["tests"].append({"cat": category, "name": name, "pass": passed, "detail": detail})
    icon = "+" if passed else "X"
    line = f"  [{icon}] {category} > {name}"
    if detail:
        line += f"  --  {detail}"
    print(line)

def section(title):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")

def test_html_structure():
    section("SUITE 1: HTML Structure & Feature Presence")

    html_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "src", "gui", "templates", "index.html")
    if not os.path.exists(html_path):
        html_path = "src/gui/templates/index.html"
    if not os.path.exists(html_path):
        print(f"  [!] Cannot find index.html at {html_path}")
        print(f"  [!] Run this script from the kirator_extracted/ directory")
        results["skip"] += 50
        return

    with open(html_path, "r", encoding="utf-8") as f:
        html = f.read()
    soup = BeautifulSoup(html, "html.parser")

    title = soup.find("title")
    log_test("HTML", "Correct title",
             title and "Kirator Prompt Intelligence" in title.text,
             f"Got: '{title.text if title else 'NO TITLE'}'")

    logo = soup.find("img", {"class": "logo-img"})
    log_test("HTML", "Logo image exists", logo is not None)

    model_sel = soup.find("select", {"id": "targetModel"})
    log_test("HTML", "Model selector dropdown", model_sel is not None)
    if model_sel:
        options = [o.get("value") for o in model_sel.find_all("option")]
        expected = ["chatgpt", "claude", "gemini", "grok", "local"]
        log_test("HTML", "Model selector has 5 options",
                 len(options) == 5 and all(o in options for o in expected),
                 f"Options: {options}")

    log_test("HTML", "Copy button exists", soup.find("button", {"id": "copyBtn"}) is not None)
    log_test("HTML", "Download .txt button", soup.find("button", {"id": "downloadTxtBtn"}) is not None)
    log_test("HTML", "Download .md button", soup.find("button", {"id": "downloadMdBtn"}) is not None)
    log_test("HTML", "Clear button exists", soup.find("button", {"id": "clearBtn"}) is not None)

    char_count = soup.find("span", {"id": "charCount"})
    log_test("HTML", "Character count display", char_count is not None)

    shortcut = soup.find("div", {"class": "shortcut-hint"})
    log_test("HTML", "Ctrl+Enter shortcut hint",
             shortcut is not None and "Ctrl" in shortcut.text and "Enter" in shortcut.text)

    chips = soup.find_all("span", {"class": "chip"})
    log_test("HTML", "Example prompt chips",
             len(chips) >= 6, f"Found {len(chips)} chips")
    if chips:
        all_have_data = all(c.get("data-prompt") for c in chips)
        log_test("HTML", "All chips have data-prompt", all_have_data)

    log_test("HTML", "Before/After toggle", soup.find("div", {"id": "beforeAfterToggle"}) is not None)

    tooltip = soup.find("div", {"id": "scoreTooltip"})
    log_test("HTML", "Score tooltip",
             tooltip is not None and "PEEM" in tooltip.text)

    log_test("HTML", "Weaknesses card", soup.find("div", {"id": "weaknessesCard"}) is not None)
    log_test("HTML", "Weaknesses list", soup.find("ul", {"id": "weaknessesList"}) is not None)

    log_test("HTML", "History sidebar", soup.find("div", {"id": "historySidebar"}) is not None)
    log_test("HTML", "History toggle button", soup.find("button", {"id": "historyToggleBtn"}) is not None)
    log_test("HTML", "History close button", soup.find("button", {"id": "historyCloseBtn"}) is not None)
    log_test("HTML", "History overlay", soup.find("div", {"id": "historyOverlay"}) is not None)
    log_test("HTML", "History clear button", soup.find("button", {"id": "historyClearBtn"}) is not None)

    log_test("CSS", "Button pulse animation",
             "btnPulse" in html and "@keyframes btnPulse" in html)
    log_test("CSS", "Toggle switch styles",
             ".toggle-switch" in html and ".toggle-switch.active" in html)
    log_test("CSS", "Score tooltip styles",
             ".score-tooltip" in html and ".score-wrap:hover .score-tooltip" in html)
    log_test("CSS", "History sidebar styles",
             ".history-sidebar" in html and ".history-sidebar.open" in html)

    stages_found = [soup.find("div", {"id": f"si{i}"}) for i in range(1, 10)]
    log_test("HTML", "All 9 stage items", all(s is not None for s in stages_found))

    metric_ids = ["mClarity", "mLing", "mFair", "mComp", "mSpec", "mAmbig", "mConst", "mModel"]
    metrics_found = [soup.find("span", {"id": mid}) for mid in metric_ids]
    log_test("HTML", "All 8 PEEM metric displays", all(m is not None for m in metrics_found))

    footer = soup.find("div", {"class": "footer"})
    log_test("HTML", "Footer says 'Kirator Prompt Intelligence'",
             footer and "Kirator Prompt Intelligence" in footer.text)

    js_funcs = ["copyOutput", "downloadTxt", "downloadMd", "toggleBeforeAfter",
                "clearAll", "openHistory", "closeHistory", "renderHistory",
                "loadHistoryItem", "addToHistory", "clearHistory",
                "updateCharCount", "escapeHtml"]
    for func in js_funcs:
        log_test("JS", f"Function: {func}()", func + "(" in html)

    log_test("JS", "Copy button listener",
             'getElementById("copyBtn")' in html and "copyOutput" in html)
    log_test("JS", "Download .txt listener",
             'getElementById("downloadTxtBtn")' in html and "downloadTxt" in html)
    log_test("JS", "Download .md listener",
             'getElementById("downloadMdBtn")' in html and "downloadMd" in html)
    log_test("JS", "Before/after listener",
             'getElementById("beforeAfterToggle")' in html and "toggleBeforeAfter" in html)
    log_test("JS", "Clear button listener",
             'getElementById("clearBtn")' in html and "clearAll" in html)
    log_test("JS", "Char count on input",
             ("'input'" in html or '"input"' in html) and "updateCharCount" in html)
    log_test("JS", "Chip click handlers",
             ".chip" in html and 'getAttribute("data-prompt")' in html)
    log_test("JS", "target_model sent in API request",
             'target_model' in html and '"targetModel"' in html)
    log_test("JS", "localStorage persistence",
             "localStorage" in html and "kirator_history" in html)


def test_api_endpoints():
    section("SUITE 2: API Endpoints")

    try:
        r = requests.get(BASE_URL + "/", timeout=10)
        log_test("API", "GET / (index page)",
                 r.status_code == 200, f"Status: {r.status_code}")
    except Exception as e:
        log_test("API", "GET / (index page)", False, str(e))
        print("\n  [!] Server not reachable at", BASE_URL)
        print("  [!] Start the server first, then re-run this test.")
        return False

    if r.status_code == 200:
        log_test("API", "Page has 'Kirator' branding", "Kirator" in r.text)
        log_test("API", "Page has Generate button", "Generate Optimized Prompt" in r.text)
        log_test("API", "Page has model selector", "targetModel" in r.text)

    r = requests.post(BASE_URL + "/api/run", json={}, timeout=10)
    log_test("API", "POST /api/run empty -> 400",
             r.status_code == 400, f"Status: {r.status_code}")

    r = requests.get(BASE_URL + "/api/status", timeout=10)
    log_test("API", "GET /api/status idle",
             r.status_code == 200 and r.json().get("status") == "idle")

    r = requests.get(BASE_URL + "/api/history", timeout=10)
    log_test("API", "GET /api/history",
             r.status_code == 200 and r.json().get("status") == "ok")
    log_test("API", "History initially empty",
             r.json().get("count", -1) == 0, f"Count: {r.json().get('count')}")

    r = requests.delete(BASE_URL + "/api/history", timeout=10)
    log_test("API", "DELETE /api/history clear",
             r.status_code == 200 and r.json().get("status") == "ok")

    r = requests.post(BASE_URL + "/api/run",
                      json={"request": TEST_PROMPT, "target_model": "chatgpt"},
                      timeout=10)
    log_test("API", "POST /api/run valid -> 200",
             r.status_code == 200, f"Status: {r.status_code}")
    if r.status_code == 200:
        log_test("API", "Response has 'status: started'",
                 r.json().get("status") == "started")

    r2 = requests.post(BASE_URL + "/api/run",
                       json={"request": TEST_PROMPT, "target_model": "chatgpt"},
                       timeout=10)
    log_test("API", "Duplicate request -> 409 or 429",
             r2.status_code in [409, 429], f"Status: {r2.status_code}")

    return True


def test_pipeline():
    section("SUITE 3: Full Pipeline Execution")

    print("  Waiting for pipeline to complete (this takes 1-3 min)...")

    elapsed = 0
    last_stage = 0
    final_result = None
    error_occurred = False
    error_msg = ""

    start_time = time.time()

    while elapsed < PIPELINE_TIMEOUT:
        try:
            r = requests.get(BASE_URL + "/api/status", timeout=10)
            data = r.json()
            status = data.get("status")

            if status == "complete":
                final_result = data.get("result")
                print(f"  Pipeline completed in {elapsed:.1f}s")
                break
            elif status == "error":
                error_occurred = True
                error_msg = data.get("error", "Unknown")
                print(f"  Pipeline ERROR at {elapsed:.1f}s: {error_msg}")
                final_result = data.get("result")
                break
            elif status == "running":
                cs = data.get("current_stage", "")
                if cs and int(cs) > last_stage:
                    last_stage = int(cs)
                    stage_data = data.get("stages", {}).get(cs, {})
                    name = stage_data.get("name", "?")
                    detail = stage_data.get("detail", "?")
                    print(f"  [{elapsed:>5.1f}s] Stage {cs}: {name} - {detail[:50]}")

            time.sleep(POLL_INTERVAL)
            elapsed = time.time() - start_time

        except requests.exceptions.ConnectionError:
            print(f"  [{elapsed:.1f}s] Connection lost!")
            error_occurred = True
            error_msg = "Server connection lost"
            break
        except Exception as e:
            print(f"  [{elapsed:.1f}s] Poll error: {e}")
            time.sleep(POLL_INTERVAL)
            elapsed = time.time() - start_time

    if elapsed >= PIPELINE_TIMEOUT:
        log_test("Pipeline", "Completed within timeout", False, f"Timed out at {PIPELINE_TIMEOUT}s")
        return

    if error_occurred:
        log_test("Pipeline", "Completed without error", False, error_msg)
        if final_result:
            log_test("Pipeline", "Error result has traceback",
                     "traceback" in final_result or "error" in final_result)
        return

    if not final_result:
        log_test("Pipeline", "Got result data", False, "No result returned")
        return

    required_fields = ["request", "prompt", "score", "report", "rendered",
                       "total_time", "stages", "logs", "weaknesses", "target_model"]
    for field in required_fields:
        present = field in final_result
        val = final_result.get(field, "MISSING")
        if isinstance(val, str) and len(val) > 80:
            val = val[:80] + "..."
        log_test("Pipeline", f"Result has '{field}'",
                 present,
                 f"Type: {type(final_result.get(field)).__name__}, Val: {val}" if present else "MISSING")

    score = final_result.get("score", 0)
    log_test("Pipeline", "Score is integer >= 0",
             isinstance(score, int) and score >= 0, f"Score: {score}/100")
    log_test("Pipeline", "Score is reasonable (>50)",
             score > 50 if isinstance(score, int) else False, f"Score: {score}/100")

    prompt = final_result.get("prompt", "")
    rendered = final_result.get("rendered", "")
    log_test("Pipeline", "Prompt output non-empty",
             len(prompt) > 100, f"Length: {len(prompt)} chars")
    log_test("Pipeline", "Rendered output non-empty",
             len(rendered) > 100, f"Length: {len(rendered)} chars")

    total_time = final_result.get("total_time", 0)
    log_test("Pipeline", f"Total time: {total_time}s",
             total_time > 0 and total_time < 600)

    stages = final_result.get("stages", {})
    log_test("Pipeline", "All 9 stages in result",
             len(stages) == 9, f"Found {len(stages)} stages")
    for i in range(1, 10):
        s_data = stages.get(str(i))
        if s_data:
            log_test("Pipeline", f"S{i} has name+detail+time",
                     all(k in s_data for k in ["name", "detail", "time"]),
                     f"{s_data.get('name')}: {s_data.get('detail', '')[:40]}")

    tm = final_result.get("target_model", "")
    log_test("Pipeline", "Target model in result",
             tm == "chatgpt", f"Got: '{tm}'")

    weaknesses = final_result.get("weaknesses", [])
    log_test("Pipeline", "Weaknesses is a list",
             isinstance(weaknesses, list))
    log_test("Pipeline", "Weaknesses data available",
             len(weaknesses) > 0, f"Count: {len(weaknesses)}")

    report = final_result.get("report", {})
    peem_axes = ["clarity_structure", "linguistic_quality", "fairness_bias",
                 "completeness", "specificity", "ambiguity",
                 "constraint_clarity", "model_compatibility"]
    for axis in peem_axes:
        val = report.get(axis)
        log_test("Pipeline", f"Report axis '{axis}'",
                 val is not None, f"Value: {val}")


def test_history():
    section("SUITE 4: History Endpoints")

    r = requests.get(BASE_URL + "/api/history", timeout=10)
    if r.status_code == 200:
        data = r.json()
        count = data.get("count", 0)
        log_test("History", "Has entry after pipeline", count >= 1, f"Count: {count}")

        if count >= 1:
            history = data.get("history", [])
            entry = history[0]
            log_test("History", "Entry has request field", "request" in entry)
            log_test("History", "Entry has score field", "score" in entry)
            log_test("History", "Entry has model field", "model" in entry)
            log_test("History", "Entry has timestamp", "timestamp" in entry)
            log_test("History", "Model is 'chatgpt'",
                     entry.get("model") == "chatgpt", f"Got: '{entry.get('model')}'")

    r = requests.delete(BASE_URL + "/api/history", timeout=10)
    log_test("History", "DELETE clears history", r.status_code == 200)

    r = requests.get(BASE_URL + "/api/history", timeout=10)
    data = r.json()
    log_test("History", "History is empty after clear",
             data.get("count", -1) == 0, f"Count: {data.get('count')}")


def test_edge_cases():
    section("SUITE 5: API Edge Cases")

    r = requests.get(BASE_URL + "/api/run", timeout=10)
    log_test("Edge", "GET /api/run -> 405",
             r.status_code == 405, f"Status: {r.status_code}")

    r = requests.post(BASE_URL + "/api/run",
                      data="not json",
                      headers={"Content-Type": "text/plain"},
                      timeout=10)
    log_test("Edge", "POST non-JSON -> handled",
             r.status_code in [400, 415], f"Status: {r.status_code}")

    r = requests.post(BASE_URL + "/api/cancel", timeout=10)
    log_test("Edge", "POST /api/cancel -> 200",
             r.status_code == 200)


def main():
    print("=" * 60)
    print("  KIRATOR PROMPT INTELLIGENCE - TEST BATTERY v1.0")
    print("  " + time.strftime("%Y-%m-%d %H:%M:%S"))
    print("=" * 60)

    test_html_structure()

    server_ok = test_api_endpoints()

    if server_ok:
        test_pipeline()
        test_history()
        test_edge_cases()
    else:
        print("\n  [!] Skipping Suites 3-5: Server not reachable")
        results["skip"] += 4

    print(f"\n{'='*60}")
    print(f"  TEST BATTERY COMPLETE")
    print(f"{'='*60}")
    print(f"  PASSED:  {results['pass']}")
    print(f"  FAILED:  {results['fail']}")
    print(f"  SKIPPED: {results['skip']}")
    print(f"  TOTAL:   {results['pass'] + results['fail'] + results['skip']}")
    print(f"{'='*60}")

    if results['fail'] > 0:
        print("\n  FAILURES:")
        for t in results['tests']:
            if not t['pass']:
                print(f"    [X] {t['cat']} > {t['name']}")
                if t['detail']:
                    print(f"        {t['detail']}")

    print()
    return 0 if results['fail'] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())