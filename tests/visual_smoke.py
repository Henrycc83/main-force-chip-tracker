from pathlib import Path
import re
import json
from urllib.parse import urljoin

from playwright.sync_api import sync_playwright


ROOT_URL = "http://127.0.0.1:8765/"
ARTIFACTS = Path("artifacts/qa")
PAYLOAD = json.loads(Path("docs/data/dashboard.json").read_text(encoding="utf-8"))
STATUS_TEXT = {
    "confirmed": "已確認",
    "partial": "部分或代理",
    "no_new_data": "無新交易資料",
    "unavailable": "不可用",
}


def check_page(browser, *, width: int, height: int, name: str) -> None:
    page = browser.new_page(viewport={"width": width, "height": height})
    console_errors: list[str] = []
    page.on("console", lambda message: console_errors.append(message.text) if message.type == "error" else None)
    page.goto(ROOT_URL)
    page.wait_for_load_state("networkidle")

    rendered_date = page.locator("#data-date").inner_text()
    assert re.search(r"2026\D+0?9\D+0?1", rendered_date), rendered_date
    assert page.locator("#latest-table tbody tr").count() == 30
    evidence_rows = page.locator("#latest-table .row-evidence")
    assert evidence_rows.count() == 30
    assert evidence_rows.first.is_visible()
    assert "分母" in evidence_rows.first.inner_text()
    assert page.locator("#overall-status").inner_text().strip() == STATUS_TEXT[PAYLOAD["status"]]
    assert not console_errors, console_errors
    assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")

    for link in page.locator("#report-links a").all():
        href = link.get_attribute("href")
        response = page.request.get(urljoin(page.url, href))
        assert response.ok, f"broken report link: {link.get_attribute('href')} ({response.status})"

    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    page.screenshot(path=str(ARTIFACTS / f"{name}.png"), full_page=True)
    page.close()


with sync_playwright() as playwright:
    browser = playwright.chromium.launch(headless=True)
    check_page(browser, width=1440, height=1000, name="desktop")
    check_page(browser, width=390, height=844, name="mobile")
    browser.close()

print("Visual smoke checks passed: desktop/mobile layout, 30 rows, visible evidence, status, console and report links.")
