"""CI-only browser regression with offline TradeLab responses."""
from pathlib import Path
from urllib.parse import urlsplit

from playwright.sync_api import expect, sync_playwright


UI = Path(__file__).resolve().parents[1] / "ui"
ORIGIN = "http://tradelab.test"
LOG_URL = ORIGIN + "/api/llm_log?n=30"


def check_log_refresh():
    cycle = {
        "ts": 1795454141.4,
        "trigger": "new shocks",
        "candidates": [{"symbol": "KLAC", "name": "KLA", "move_pct": 13, "volume_ratio": 0.5}],
    }
    comparison = {
        "equity_thb": 5050, "equity_usd": 151.5, "control_equity_thb": 4950,
        "control_equity_usd": 148.5, "capital_thb": 5000, "capital_usd": 150,
        "positions": [], "decisions": [], "events": [], "n_events": 0, "n_up": 0,
        "scan_every_s": 10, "last_scan_age_s": 4,
        "model": "deepseek/deepseek-v4.1-flash-1017", "calls_today": 4, "max_calls_day": 300,
        "rules": {"shock": "move >= 5.0% vs previous close, day volume >= 0.5x 50-day average", "trade": ""},
        "evaluation": {"closed_pairs": 0, "needed": 30, "verdict": "too early (0/30 closed pairs): no conclusion allowed"},
    }
    account_row = {
        "name": "Event trader (rule)", "tab": "events", "start_thb": 5000, "start_usd": 150,
        "equity_thb": 5050, "equity_usd": 151.5, "control_thb": 4950, "control_usd": 148.5,
        "positions": 0, "return_pct": 1, "status": "running",
    }

    def offline(route):
        url = urlsplit(route.request.url)
        if url.hostname != "tradelab.test":
            return route.abort()
        if url.path == "/api/llm_log":
            return route.fulfill(json={"cycles": [cycle], "closed": []})
        if url.path == "/api/event_log":
            return route.fulfill(json={"rows": []})
        if url.path == "/api/account":
            return route.fulfill(json={"stats": {"equity": 100000}, "positions": []})
        if url.path == "/api/alerts":
            return route.fulfill(json={"alerts": [], "log": []})
        if url.path in {"/api/llm_trader", "/api/events"}:
            return route.fulfill(json=comparison)
        if url.path == "/api/accounts":
            return route.fulfill(json={"rows": [account_row], "thb_per_usd": 40, "buzz_events": 6})
        file = UI / (url.path.lstrip("/") or "index.html")
        return route.fulfill(path=file) if file.is_file() else route.fulfill(status=404)

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(channel="chrome")
        page = browser.new_page(viewport={"width": 390, "height": 844})
        page.route("**/*", offline)
        page.add_init_script("""(() => {
          if (location.hostname !== 'tradelab.test') return;
          localStorage.setItem('lang', 'th');
          window.englishLogFrame = false;
          function watchFrame() {
            const header = document.querySelector('#lg-cycles th');
            if (header?.textContent === 'Stock') window.englishLogFrame = true;
            requestAnimationFrame(watchFrame);
          }
          requestAnimationFrame(watchFrame);
        })()""")
        page.goto(ORIGIN + "/#logs")
        header = page.locator("#lg-cycles th").first
        expect(header).to_have_text("หุ้น")
        details = page.locator("#lg-cycles details").first
        summary = details.locator("summary")
        summary.click()
        summary.focus()
        wrap = page.locator("#lg-cycles .tbl-wrap").first
        scroll = wrap.evaluate("(element) => { element.scrollLeft = 100; return element.scrollLeft; }")
        original = details.element_handle()
        assert original is not None and scroll > 0

        with page.expect_response(LOG_URL, timeout=10000):
            pass
        page.wait_for_timeout(150)
        assert original.evaluate("(element) => element.isConnected && element.open")
        expect(summary).to_be_focused()

        cycle["outcomes"] = [{"symbol": "KLAC", "horizon_s": 3600, "abnormal": 0.012}]
        expect(page.get_by_text("+1h vs SPY +1.20%", exact=True)).to_be_visible(timeout=10000)
        expect(details).to_have_attribute("open", "")
        expect(summary).to_be_focused()
        assert wrap.evaluate("(element) => element.scrollLeft") == scroll
        assert not page.evaluate("window.englishLogFrame")

        page.locator("#lg-evt").click()
        expect(page.locator("#lg-cycles")).to_have_text("ยังไม่มีเหตุการณ์")
        page.locator("#lg-llm").click()
        expect(header).to_have_text("หุ้น")
        page.locator("#lang-btn").click()
        expect(header).to_have_text("Stock")

        page.locator("#lang-btn").click()
        for route, section in (("events", "ev"), ("llm", "llm")):
            page.locator(f'.tabs a[data-view="{route}"]').click()
            figures = page.locator(f"#{section}-figs")
            expect(figures.locator(".figure b").nth(0)).to_have_text("5,050.00 THB")
            expect(figures.locator(".figure b").nth(1)).to_have_text("4,950.00 THB")
            expect(figures).to_contain_text("151.50 USD")
            expect(figures).to_contain_text("148.50 USD")
            expect(figures).to_contain_text("มีคู่ปิด 0/30 คู่ ยังสรุปไม่ได้")
        expect(page.locator("#llm-sub")).to_contain_text("เรียกโมเดลวันนี้ 4/300 ครั้ง")

        page.locator('.tabs a[data-view="overview"]').click()
        overview = page.locator("#ov-table")
        expect(overview.get_by_role("columnheader", name="บัญชีสุ่มเทียบ")).to_be_visible()
        for index, thb, usd in ((2, "5,050.00 THB", "151.50 USD"), (3, "4,950.00 THB", "148.50 USD")):
            cell = overview.locator("tbody td").nth(index)
            expect(cell).to_contain_text(thb)
            expect(cell).to_contain_text(usd)
        browser.close()


if __name__ == "__main__":
    check_log_refresh()
