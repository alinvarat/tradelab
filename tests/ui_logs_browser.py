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
        browser.close()


if __name__ == "__main__":
    check_log_refresh()
