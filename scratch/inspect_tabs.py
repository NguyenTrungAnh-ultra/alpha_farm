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

def inspect_tabs():
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

        details_url = f"https://alpha.xnoquant.io/list?strategyId={STRATEGY_ID}&stage=train"
        logger.info(f"Navigating to Details: {details_url}")
        page.goto(details_url)
        page.wait_for_timeout(5000)

        # 1. Click Performance Tab
        logger.info("Clicking Performance tab...")
        page.click("div.cursor-pointer:has-text('Performance')")
        page.wait_for_timeout(4000)
        perf_screenshot = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scratch", "details_performance.png")
        page.screenshot(path=perf_screenshot)
        logger.info(f"Saved Performance screenshot to {perf_screenshot}")

        # 2. Click Analysis Tab
        logger.info("Clicking Analysis tab...")
        page.click("div.cursor-pointer:has-text('Analysis')")
        page.wait_for_timeout(4000)
        analysis_screenshot = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scratch", "details_analysis.png")
        page.screenshot(path=analysis_screenshot)
        logger.info(f"Saved Analysis screenshot to {analysis_screenshot}")

        # Save captured responses
        output_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scratch", "tabs_captured_responses.json")
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(captured_responses, f, indent=2, ensure_ascii=False)
        logger.info(f"Saved tabs captured responses to {output_path}")

        page.close()
        browser.close()

if __name__ == "__main__":
    inspect_tabs()
