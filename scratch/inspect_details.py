import sys
import os
import json
import logging
import time
from playwright.sync_api import sync_playwright

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from agent.auto_submit import load_credentials_from_arch

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

STRATEGY_ID = "c0RX7j3DAz"

def inspect_details():
    captured_responses = []

    def handle_response(response):
        url = response.url
        try:
            if "xnoquant.io" in url and "json" in response.headers.get("content-type", ""):
                try:
                    data = response.json()
                    captured_responses.append({
                        "url": url,
                        "data": data
                    })
                    logger.info(f"Captured: {url}")
                except:
                    pass
        except:
            pass

    with sync_playwright() as p:
        logger.info("Connecting to Chrome CDP...")
        browser = None
        try:
            browser = p.chromium.connect_over_cdp("http://localhost:9222")
            context = browser.contexts[0]
        except Exception as e:
            logger.warning(f"CDP failed: {e}. Launching new headless browser...")
            browser = p.chromium.launch(headless=True)
            context = browser.new_context()

        page = context.new_page()
        page.on("response", handle_response)

        account, password = load_credentials_from_arch()
        if not account or not password:
            logger.error("No credentials in ARCH.md")
            return

        logger.info("Navigating to build page first (to ensure login)...")
        page.goto("https://alpha.xnoquant.io/build")
        page.wait_for_timeout(3000)

        if "dang-nhap" in page.url or page.locator("input[type='password']").count() > 0:
            logger.info("Logging in...")
            page.fill("input[type='text']", account)
            page.fill("input[type='password']", password)
            page.click("button:has-text('Login')")
            page.wait_for_timeout(3000)

        details_url = f"https://alpha.xnoquant.io/list?strategyId={STRATEGY_ID}&stage=train"
        logger.info(f"Navigating to Details: {details_url}")
        page.goto(details_url)
        page.wait_for_timeout(5000)

        # Let's take a screenshot
        screenshot_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scratch", "details_screenshot.png")
        page.screenshot(path=screenshot_path)
        logger.info(f"Screenshot saved to {screenshot_path}")

        # Dump HTML
        html_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scratch", "details.html")
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(page.content())
        logger.info(f"HTML DOM dumped to {html_path}")

        # Try to find all button/tab texts on the page to see if we need to click something to view trades
        buttons = page.evaluate("() => Array.from(document.querySelectorAll('button, a, div[role=\"tab\"]')).map(el => el.textContent.trim())")
        logger.info(f"Found buttons/tabs: {buttons}")

        # Let's see if we can click a tab that says "Trades" or "Giao dịch"
        # In Vietnamese, it might be "Giao dịch" or "Lịch sử giao dịch" or "Trades".
        for text in ["Trades", "Giao dịch", "Transactions", "Lịch sử"]:
            tab_locator = page.locator(f"div[role='tab']:has-text('{text}'), button:has-text('{text}'), a:has-text('{text}')")
            if tab_locator.count() > 0:
                logger.info(f"Found tab containing '{text}', clicking it...")
                tab_locator.first.click()
                page.wait_for_timeout(3000)
                # Take another screenshot
                page.screenshot(path=screenshot_path.replace(".png", f"_{text}.png"))
                break

        # Save all captured responses to a JSON file
        output_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scratch", "details_captured_responses.json")
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(captured_responses, f, indent=2, ensure_ascii=False)
        logger.info(f"Saved details captured responses to {output_path}")

        page.close()
        browser.close()

if __name__ == "__main__":
    inspect_details()
