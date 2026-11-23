"""Capture presentation screenshots by driving the running Streamlit app with Playwright (system Chrome).

The script SUBMITS reports and approves closures, so run it only against a DISPOSABLE copy of the demo DB:
    set PHARMA_DB_PATH=%TEMP%\\pharma_shots\\shots.db && streamlit run app.py --server.port 8600
    set PHARMA_SCREENSHOT_DISPOSABLE=1 && python scripts/capture_screenshots.py http://localhost:8600
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

from playwright.sync_api import Page, sync_playwright

if os.environ.get("PHARMA_SCREENSHOT_DISPOSABLE") != "1":
    sys.exit("Refusing to run: this script writes to the target app's database. Point it at a disposable "
             "instance and set PHARMA_SCREENSHOT_DISPOSABLE=1.")

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8600"
FROM_AGENT = len(sys.argv) > 2 and sys.argv[2] == "agent"
OUT = Path(__file__).resolve().parents[1] / "docs" / "presentation" / "screenshots"
OUT.mkdir(parents=True, exist_ok=True)


def settle(page: Page, ms: int = 1800) -> None:
    page.wait_for_timeout(400)
    try:  # wait until Streamlit finished running the script
        page.wait_for_selector('[data-testid="stStatusWidget"]', state="detached", timeout=60000)
    except Exception:  # noqa: BLE001
        pass
    page.wait_for_timeout(ms)


def shot(page: Page, name: str, height: int | None = None) -> None:
    if height:
        page.set_viewport_size({"width": 1600, "height": height})
        settle(page, 800)
    page.screenshot(path=str(OUT / f"{name}.png"))
    print("saved", name)


def nav(page: Page, label: str) -> None:
    page.locator('[data-testid="stSidebarNav"] a').filter(has_text=label).first.click()
    settle(page)


def pick(page: Page, label: str, option: str) -> None:
    page.locator('[data-testid="stSelectbox"]').filter(has_text=label).first.click()
    page.get_by_role("option", name=option, exact=True).click()
    settle(page, 800)


def main() -> None:
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="chrome", headless=True)
        page = browser.new_page(viewport={"width": 1600, "height": 1000}, device_scale_factor=1)
        page.goto(BASE)
        page.wait_for_selector("text=Total reports", timeout=180000)
        settle(page)
        shot(page, "01_home", 1000)
        if FROM_AGENT:
            return agent_and_audit(page, browser)

        # ---------------- New Report: validation errors, then success
        nav(page, "New Report")
        page.get_by_label("Product name *").fill("Fictivex 20mg")
        page.get_by_label("Batch / Lot number *").fill("LOT-883")
        page.get_by_label("Detailed description *").fill("Short")
        page.get_by_role("button", name="Submit report").click()
        settle(page)
        shot(page, "02_intake_validation_errors", 1250)

        page.get_by_text("Product Quality Complaint", exact=True).first.click()
        settle(page, 800)
        page.get_by_label("Product name *").fill("Nullamycin 250mg")
        page.get_by_label("Batch / Lot number *").fill("lot 55120")
        pick(page, "Reporter type", "Consumer")
        page.get_by_label("Detailed description *").fill(
            "Consumer reported that the bottle seal was broken on arrival and the cap was loose.")
        page.get_by_role("button", name="Submit report").click()
        settle(page)
        shot(page, "03_intake_success", 900)

        # ---------------- Dashboard: filter + select a row + action
        nav(page, "Dashboard")
        shot(page, "04_dashboard", 1000)
        grid = page.locator('[data-testid="stDataFrame"]').first
        box = grid.bounding_box()
        # row index 8 (newly created REF-2026-0009) -> row-marker column
        page.mouse.click(box["x"] + 18, box["y"] + 35 + 17 + 8 * 35)
        settle(page)
        page.get_by_role("button", name="Move to In Review").click()
        settle(page)
        grid = page.locator('[data-testid="stDataFrame"]').first
        box = grid.bounding_box()
        page.mouse.click(box["x"] + 18, box["y"] + 35 + 17 + 8 * 35)
        settle(page)
        shot(page, "05_dashboard_detail_in_review", 1350)
        page.get_by_role("button", name="Request closure (HITL approval)").click()
        settle(page)
        shot(page, "06_dashboard_closure_requested", 1000)

        # ---------------- Triage approvals as reviewer
        nav(page, "Triage Approvals")
        pick(page, "Pseudonymous actor code", "REV-02")
        shot(page, "07_triage_pending", 1300)
        areas = page.get_by_label("Justification (required, min 10 characters)")
        areas.last.fill("Seal defect documented; sample return logged; closure criteria met.")
        areas.last.press("Control+Enter")
        settle(page, 600)
        page.get_by_role("button", name="Approve closure").last.click()
        settle(page)
        shot(page, "08_triage_approved", 1100)

        pick(page, "Pseudonymous actor code", "OP-01")
        agent_and_audit(page, browser)


def agent_and_audit(page, browser) -> None:
        # ---------------- Knowledge agent
        nav(page, "Knowledge Agent")
        box_in = page.locator('[data-testid="stChatInputTextArea"]')
        box_in.fill("any history of difficulty breathing with LOT-88392?")
        box_in.press("Enter")
        settle(page, 3000)
        page.get_by_text("ReAct trace").last.click()
        page.get_by_text("Pipeline inspector").last.click()
        settle(page, 1500)
        shot(page, "09_rag_answer_and_inspector", 2300)

        page.get_by_role("button", name="Reset session").click()
        settle(page)
        for q in ["Was the dyspnea caused by Fictivex?", "chocolate cake recipe ideas",
                  "move REF-2026-0999 to in review", "move REF-2026-0999 to in review",
                  "move REF-2026-0999 to in review"]:
            box_in = page.locator('[data-testid="stChatInputTextArea"]')
            box_in.fill(q)
            box_in.press("Enter")
            settle(page, 1500)
        shot(page, "10_guardrails_refusal_abstain_breaker", 2600)

        # ---------------- Audit trail
        nav(page, "Audit Trail")
        shot(page, "11_audit_trail_and_hook_log", 1500)
        browser.close()


if __name__ == "__main__":
    main()
