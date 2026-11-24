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
        "candidates": [
            {"symbol": "KLAC", "name": "KLA", "move_pct": 13, "volume_ratio": 0.5},
            {"symbol": "ADI", "name": "Analog Devices", "move_pct": 9, "volume_ratio": 0.5},
        ],
        "decisions": [{"symbol": "KLAC", "action": "hold"}, {"symbol": "NVDA", "action": "hold"}],
        "account": {"positions": [{"symbol": "NVDA"}]},
    }
    comparison = {
        "equity_thb": 5050, "equity_usd": 151.5, "control_equity_thb": 4950,
        "control_equity_usd": 148.5, "capital_thb": 5000, "capital_usd": 150,
        "positions": [], "decisions": [], "events": [], "n_events": 0, "n_up": 0,
        "scan_every_s": 10, "last_scan_age_s": 4,
        "model": "deepseek/deepseek-v4.1-flash-1017", "calls_today": 4, "max_calls_day": 300,
        "protocol": "v4", "universe_size": 217,
        "classes": {"stock": 148, "etf": 34, "commodity": 16, "fx": 8, "crypto": 11}, "next_scan_in_s": 120,
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
        if url.path == "/api/quotes":
            return route.fulfill(json={"watchlist": ["KLAC"], "quotes": [{"symbol": "KLAC", "open": False}]})
        if url.path == "/api/overview":
            return route.fulfill(json={"groups": {}})
        if url.path == "/api/news":
            return route.fulfill(json={"items": []})
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
        for label in ("ไม่เปิดสถานะ", "ถือสถานะต่อ", "โมเดลไม่ได้ตอบ"):
            expect(page.locator("#lg-cycles").get_by_text(label, exact=True)).to_be_visible()
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

        page.locator('.tabs a[data-view="markets"]').click()
        expect(page.locator("#watchlist").get_by_text("ตลาดปิด", exact=True)).to_be_visible()
        expect(page.locator("#overview")).to_have_attribute("data-loaded", "1")
        expect(page.locator("#mk-news")).to_have_attribute("data-loaded", "1")
        with page.expect_response(ORIGIN + "/api/overview"):
            page.locator('[data-refresh="markets"]').click()
        expect(page.locator("#watchlist").get_by_text("ตลาดปิด", exact=True)).to_be_visible()
        browser.close()


def check_page_translations():
    stamp = 1795454141
    account = {
        "stats": {"equity": 100000, "trades": 2}, "positions": [],
        "orders": [{"id": 1, "side": 1, "symbol": "BUY", "type": "limit", "status": "pending"}],
        "trades": [], "allocation": {}, "cash_usd": 100000, "equity_curve": [],
        "settings": {"initial": 100000, "leverage": 1, "fee_rate": 0.0005, "slippage": 0},
    }
    quote = {"symbol": "BUY", "name": "Markets", "price": 10, "bid": 9, "ask": 11,
             "currency": "USD", "open": True, "source": "Test"}
    responses = {
        "/api/account": account,
        "/api/alerts": {"alerts": [], "log": []},
        "/api/auto": {"stats": {"equity": 150}, "equity_thb": 5000, "capital_thb": 5000,
                      "targets": [], "lessons": [], "log": [{"ts": stamp, "text": "Running"}],
                      "months": [], "positions": [], "grid": [], "equity_curve": []},
        "/api/hunter": {"equity_thb": 5000, "capital_thb": 5000, "lev": 20,
                        "positions": [], "months": [], "log": []},
        "/api/quotes": {"watchlist": ["BUY"], "quotes": [quote]},
        "/api/overview": {"groups": {}, "fear_greed": {"value": 25, "label": "Fear",
                          "history": [{"v": 25}], "source": "Test"}},
        "/api/news": {"summary": {"count": 1, "positive": 0, "negative": 0, "avg": 0},
                      "items": [{"title": "Market closed", "summary": "Buy", "link": "https://example.test",
                                 "source": "News", "sentiment": 0, "ts": stamp}]},
        "/api/quote": quote,
        "/api/chart": {"bars": [], "ind": {}, "meta": {"longName": "Markets", "currency": "USD"}, "interval": "1d"},
        "/api/analysis": {"score": 100, "rating": "Strong buy", "signals": [], "as_of": stamp,
                          "levels": {"resistance": [12], "support": [], "pivots": {}, "fib_52w": {}},
                          "performance": {}, "risk": {}, "volatility": {}, "events": []},
        "/api/strategies": {"sma_cross": {"name": "SMA crossover", "params": {"fast": 50, "slow": 200}}},
    }

    def offline(route):
        url = urlsplit(route.request.url)
        if url.hostname != "tradelab.test":
            return route.abort()
        if url.path in responses:
            return route.fulfill(json=responses[url.path])
        if url.path == "/api/backtest":
            body = route.request.post_data_json
            assert body["symbol"] == "BUY" and body["strategy"] == "sma_cross"
            assert body["params"]["fast"] == 51
            return route.fulfill(json={"symbol": "BUY", "strategy": "SMA crossover", "start": stamp, "end": stamp,
                                       "metrics": {"trades": 0}, "bars": 60, "interval": "1d",
                                       "costs": {"fee_pct_per_side": 0.05, "slippage_pct_per_side": 0.02},
                                       "trades": [], "equity": [], "buy_hold": []})
        file = UI / (url.path.lstrip("/") or "index.html")
        return route.fulfill(path=file) if file.is_file() else route.fulfill(status=404)

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(channel="chrome")
        page = browser.new_page()
        page.route("**/*", offline)
        page.goto(ORIGIN + "/#auto")
        lang = page.locator("#lang-btn")
        expect(page.locator("#auto-figs")).to_contain_text("Running")
        lang.click()
        expect(page.locator("#auto-figs")).to_contain_text("กำลังทำงาน")
        expect(page.locator("#auto-log")).to_contain_text("Running")
        expect(page.locator("#hunt-pos")).to_contain_text("ไม่มีสถานะ")
        responses["/api/auto"]["paused"] = True
        expect(page.locator("#auto-pause")).to_have_text("ทำงานต่อ", timeout=10000)
        expect(page.locator("#auto-pause")).to_have_attribute("data-auto", "resume")

        page.locator('[data-view="markets"]').click()
        watch = page.locator("#watch-sym")
        expect(watch).to_have_attribute("placeholder", "เพิ่มสัญลักษณ์ เช่น AMD")
        expect(page.locator("#watchlist").get_by_role("button", name="นำ BUY ออก")).to_be_visible()
        expect(page.locator("#watchlist .sym-name")).to_have_text("Markets")
        expect(page.locator("#fng").get_by_role("img", name="ดัชนี 25 จาก 100")).to_be_visible()
        expect(page.locator("#mk-news").get_by_role("link", name="Market closed")).to_be_visible()
        watch.fill("BUY")
        lang.click()
        expect(watch).to_have_attribute("placeholder", "Add symbol, e.g. AMD")
        expect(watch).to_have_value("BUY")
        expect(page.locator("#watchlist").get_by_role("button", name="Remove BUY")).to_be_visible()
        lang.click()

        page.locator("#watchlist tr[data-sym]").click()
        expect(page.locator("#qhead h1")).to_have_text("BUY")
        expect(page.locator("#rating").get_by_text("ซื้อแรง", exact=True)).to_be_visible()
        expect(page.locator("#ranges")).to_have_attribute("aria-label", "ช่วงเวลา")
        expect(page.locator("#levels")).to_contain_text("แนวต้าน 1")
        expect(page.locator("#place")).to_have_text("ซื้อ BUY")
        page.locator('#order-form select[name="type"]').select_option("limit")
        page.locator('#order-form input[name="price"]').fill("9.5")
        lang.click()
        expect(page.locator("#place")).to_have_text("Buy BUY")
        expect(page.locator('#order-form select[name="type"]')).to_have_value("limit")
        expect(page.locator('#order-form input[name="price"]')).to_have_value("9.5")
        lang.click()

        page.locator('[data-view="portfolio"]').click()
        expect(page.locator("#orders")).to_contain_text("ซื้อ จำกัดราคา")
        expect(page.locator("#orders")).to_contain_text("รอผล")
        page.locator('#reset-form button[type="submit"]').click()
        expect(page.locator('#reset-form button[type="submit"]')).to_have_text("กดอีกครั้งเพื่อล้างข้อมูล")
        lang.click()
        expect(page.locator('#reset-form button[type="submit"]')).to_have_text("Press again to erase")
        lang.click()

        page.locator('[data-view="backtest"]').click()
        expect(page.locator("#bt-strat option")).to_have_text("SMA ตัดกัน")
        page.locator('#bt-form [name="symbol"]').fill("BUY")
        page.locator('#bt-form [data-p="fast"]').fill("51")
        page.locator("#bt-form button").click()
        expect(page.locator("#bt-out h2").first).to_contain_text("BUY, SMA ตัดกัน")
        expect(page.locator("#bt-out")).to_contain_text("กติกาไม่ส่งคำสั่งในช่วงนี้")
        lang.click()
        expect(page.locator("#bt-strat")).to_have_value("sma_cross")
        expect(page.locator('#bt-form [data-p="fast"]')).to_have_value("51")
        expect(page.locator("#bt-out h2").first).to_contain_text("BUY, SMA crossover")
        browser.close()


if __name__ == "__main__":
    check_log_refresh()
    check_page_translations()
