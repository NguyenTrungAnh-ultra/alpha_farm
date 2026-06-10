import sys
import os
import json
import logging
from playwright.sync_api import sync_playwright

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from agent.auto_submit import load_credentials_from_arch

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

STRATEGY_ID = "v6qikQeZN1"

def check_simulate():
    captured_data = None

    def handle_response(response):
        nonlocal captured_data
        url = response.url
        # The Simulate performance is fetched from the main strategy endpoint or /stages/simulate/performance
        if f"strategies/{STRATEGY_ID}" in url and "stages" not in url:
            try:
                captured_data = response.json()
                logger.info("Captured main strategy data!")
            except:
                pass
        elif "stages/simulate/performance" in url:
            try:
                captured_data = response.json()
                logger.info("Captured simulate stage performance data!")
            except:
                pass

    with sync_playwright() as p:
        logger.info("Connecting to Chrome...")
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()
        page = context.new_page()
        page.on("response", handle_response)

        account, password = load_credentials_from_arch()
        if not account or not password:
            logger.error("No credentials in ARCH.md")
            return

        logger.info("Logging in...")
        page.goto("https://alpha.xnoquant.io/build")
        page.wait_for_timeout(3000)
        if "dang-nhap" in page.url or page.locator("input[type='password']").count() > 0:
            page.fill("input[type='text']", account)
            page.fill("input[type='password']", password)
            page.click("button:has-text('Login')")
            page.wait_for_timeout(3000)
            page.goto("https://alpha.xnoquant.io/build")
            page.wait_for_timeout(2000)

        # Wait for page to load
        page.wait_for_selector("button.shrink-0.w-14.border-r", timeout=15000)

        details_url = f"https://alpha.xnoquant.io/list?strategyId={STRATEGY_ID}&stage=simulate"
        logger.info(f"Navigating to details: {details_url}")
        page.goto(details_url)
        page.wait_for_timeout(5000)
        
        # Click the Performance tab to trigger simulate performance request
        logger.info("Clicking Performance tab...")
        page.click("div.cursor-pointer:has-text('Performance')")
        page.wait_for_timeout(3000)

        # Wait up to 10 seconds
        for _ in range(10):
            if captured_data is not None:
                break
            page.wait_for_timeout(1000)

        if captured_data:
            print("\n=== XNOQuant Web backtest results for SMA10 SAR (Simulate Stage) ===")
            print(json.dumps(captured_data["data"], indent=2))
        else:
            logger.error("Timed out waiting for simulate data.")

        page.close()
        browser.close()

if __name__ == "__main__":
    check_simulate()
