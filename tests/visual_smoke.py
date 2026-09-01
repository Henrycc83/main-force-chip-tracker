from pathlib import Path
import re
import json
from urllib.parse import urljoin

from playwright.sync_api import sync_playwright


ROOT_URL = "http://127.0.0.1:8765/"
ARTIFACTS = Path("artifacts/qa")
PAYLOAD = json.loads(Path("docs/data/dashboard.json").read_text(encoding="utf-8"))


def check_page(browser, *, width: int, height: int, name: str) -> None:
    page = browser.new_page(viewport={"width": width, "height": height})
    console_errors: list[str] = []
    page.on("console", lambda message: console_errors.append(message.text) if message.type == "error" else None)
    page.goto(ROOT_URL)
    page.wait_for_load_state("networkidle")

    rendered_date = page.locator("#data-date").inner_text()
    assert re.search(r"2026\D+0?9\D+0?1", rendered_date), rendered_date
    expected_latest = 10 if width <= 700 else 30
    assert page.locator("#latest-table tbody tr").count() == expected_latest
    if width <= 700:
        page.locator("#latest-toggle").click()
        assert page.locator("#latest-table tbody tr").count() == 30
        page.locator("#latest-toggle").click()
        assert page.locator("#latest-table tbody tr").count() == 10
    visible_text = page.locator("body").inner_text()
    assert "分母" not in visible_text
    assert "已確認" not in visible_text
    assert "部分或代理" not in visible_text
    assert page.locator(".section-nav a").count() == 4

    compact_limit = 6 if width <= 700 else 10
    memory_total = min(20, len(PAYLOAD["rolling_20d"]))
    monthly_total = min(20, sum(
        row.get("security_type") == "ordinary_stock"
        for row in PAYLOAD["monthly"]["summary_rows"]
    ))
    assert page.locator("#memory-table tbody tr").count() == min(compact_limit, memory_total)
    assert page.locator("#monthly-table tbody tr").count() == min(compact_limit, monthly_total)
    if memory_total > compact_limit:
        page.locator("#memory-toggle").click()
        assert page.locator("#memory-table tbody tr").count() == memory_total
        page.locator("#memory-toggle").click()
    if monthly_total > compact_limit:
        page.locator("#monthly-toggle").click()
        assert page.locator("#monthly-table tbody tr").count() == monthly_total
        page.locator("#monthly-toggle").click()
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

print("Visual smoke checks passed: hierarchy, compact/expanded latest and history tables, hidden audit labels and report links.")
