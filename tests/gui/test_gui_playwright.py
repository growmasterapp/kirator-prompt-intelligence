"""
Playwright GUI tests — exercises real browser interactions against the live Flask UI.

Install once:
  pip install -r requirements-dev.txt
  playwright install chromium

Run:
  pytest tests/gui -m gui -v
  python scripts/run_overnight_battery.py --gui
"""

from __future__ import annotations

import re
import time

import pytest

pytest.importorskip("playwright")

from playwright.sync_api import expect, sync_playwright

pytestmark = [pytest.mark.gui, pytest.mark.overnight]


@pytest.fixture(scope="module")
def browser_page(live_server):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1400, "height": 900})
        page = context.new_page()
        page.goto(live_server["base_url"], wait_until="domcontentloaded")
        yield page, live_server
        context.close()
        browser.close()


def test_brand_and_logo_visible(browser_page):
    page, _ = browser_page
    page.reload(wait_until="domcontentloaded")
    expect(page.locator(".brand-name")).to_contain_text(re.compile("Kirator", re.I))
    logo = page.locator(".brand-mark img")
    expect(logo).to_be_visible()
    box = logo.bounding_box()
    assert box is not None
    assert box["height"] >= 60, f"Logo too small: {box}"


def test_health_and_idle_status(browser_page):
    page, _ = browser_page
    page.reload(wait_until="domcontentloaded")
    expect(page.locator("#statusBadge")).to_contain_text(re.compile("IDLE", re.I))
    health = page.locator("#healthText")
    expect(health).to_be_visible()
    # Ready / Busy / Checking / Offline are all valid early states
    text = health.inner_text().strip().lower()
    assert text in ("ready", "busy", "checking", "offline", "issue")


def test_target_model_selection_updates_hint(browser_page):
    page, _ = browser_page
    page.reload(wait_until="domcontentloaded")
    page.locator('.target-option[data-model="claude"]').click()
    expect(page.locator('.target-option[data-model="claude"]')).to_have_class(re.compile("active"))
    hint = page.locator("#targetHint").inner_text().lower()
    assert "xml" in hint or "claude" in hint or "section" in hint


def test_example_chip_fills_textarea(browser_page):
    page, _ = browser_page
    page.reload(wait_until="domcontentloaded")
    page.locator('.chip[data-category="code_generation"]').click()
    value = page.locator("#requestInput").input_value()
    assert len(value) > 20
    chars = int(page.locator("#charCount").inner_text())
    assert chars == len(value)
    expect(page.locator("#runBtn")).to_be_enabled()


def test_clear_resets_request(browser_page):
    page, _ = browser_page
    page.reload(wait_until="domcontentloaded")
    page.locator("#requestInput").fill("temporary test text")
    page.locator("#clearBtn").click()
    assert page.locator("#requestInput").input_value() == ""
    expect(page.locator("#runBtn")).to_be_disabled()


def test_history_open_and_close(browser_page):
    page, _ = browser_page
    page.reload(wait_until="domcontentloaded")
    page.locator("#historyToggleBtn").click()
    expect(page.locator("#historySidebar")).to_have_class(re.compile("open"))
    page.locator("#historyCloseBtn").click()
    expect(page.locator("#historySidebar")).not_to_have_class(re.compile(r"\bopen\b"))


def test_history_esc_closes(browser_page):
    page, _ = browser_page
    page.reload(wait_until="domcontentloaded")
    page.locator("#historyToggleBtn").click()
    expect(page.locator("#historySidebar")).to_have_class(re.compile("open"))
    page.keyboard.press("Escape")
    time.sleep(0.3)
    expect(page.locator("#historySidebar")).not_to_have_class(re.compile(r"\bopen\b"))


def test_advanced_panel_toggles(browser_page):
    page, _ = browser_page
    page.reload(wait_until="domcontentloaded")
    panel = page.locator("#advancedPanel")
    # open
    page.locator("#advancedPanel > summary").click()
    assert panel.evaluate("el => el.open") is True
    expect(page.locator("#logWindow")).to_be_visible()
    expect(page.locator("#si1")).to_be_visible()
    # close
    page.locator("#advancedPanel > summary").click()
    assert panel.evaluate("el => el.open") is False


def test_output_actions_disabled_until_result(browser_page):
    page, _ = browser_page
    page.reload(wait_until="domcontentloaded")
    expect(page.locator("#copyBtn")).to_be_disabled()
    expect(page.locator("#downloadTxtBtn")).to_be_disabled()
    expect(page.locator("#useAsInputBtn")).to_be_disabled()


def test_improve_disabled_when_empty(browser_page):
    page, _ = browser_page
    page.reload(wait_until="domcontentloaded")
    page.locator("#requestInput").fill("")
    expect(page.locator("#runBtn")).to_be_disabled()


@pytest.mark.e2e
def test_e2e_improve_prompt_flow(browser_page):
    """Full GUI run through the pipeline — requires Ollama. Skipped if offline."""
    page, server = browser_page
    if not server.get("ollama"):
        pytest.skip("Ollama required for E2E GUI pipeline run")

    page.reload(wait_until="domcontentloaded")
    page.locator('.target-option[data-model="generic"]').click()
    page.locator("#requestInput").fill("reverse a string in python")
    expect(page.locator("#runBtn")).to_be_enabled()
    page.locator("#runBtn").click()

    # Cancel button appears while running
    expect(page.locator("#cancelBtn")).to_be_visible(timeout=10000)
    expect(page.locator("#statusBadge")).to_contain_text(re.compile("RUNNING", re.I), timeout=10000)

    # Wait for completion (pipeline can take several minutes)
    expect(page.locator("#statusBadge")).to_contain_text(
        re.compile("COMPLETE|ERROR|CANCELLED", re.I),
        timeout=600_000,
    )

    status = page.locator("#statusBadge").inner_text().upper()
    if "COMPLETE" in status:
        score_text = page.locator("#scoreDisplay").inner_text().strip()
        assert score_text.isdigit(), f"Expected numeric score, got {score_text}"
        assert int(score_text) > 0
        expect(page.locator("#copyBtn")).to_be_enabled()
        out = page.locator("#outputPre").inner_text()
        assert len(out) > 40
        assert "will appear here" not in out.lower()
    else:
        pytest.fail(f"E2E pipeline ended with status {status}")
