import sys
import os
import json
import logging
from playwright.sync_api import sync_playwright

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from agent.auto_submit import load_credentials_from_arch

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def fetch_sma10_stages():
    with sync_playwright() as p:
        logger.info("Connecting to Chrome...")
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()
        page = context.new_page()

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

        # Navigate to details to activate context
        details_url = "https://alpha.xnoquant.io/list?strategyId=v6qikQeZN1&stage=train"
        logger.info(f"Navigating to details: {details_url}")
        page.goto(details_url)
        page.wait_for_timeout(4000)

        # Fetch stages
        logger.info("Executing fetch in page context...")
        fetch_js = """
        async () => {
            try {
                const authData = JSON.parse(localStorage.getItem('auth-storage'));
                const token = authData.state.accessToken;
                if (!token) return { "error": "No access token in auth-storage" };
                
                const results = {};
                for (const stage of ['train', 'simulate']) {
                    const url = `https://api.xnoquant.io/xalpha-api/v1/strategies/v6qikQeZN1/stages/${stage}/summary-aggregate`;
                    const response = await fetch(url, {
                        headers: {
                            'Authorization': 'Bearer ' + token
                        }
                    });
                    results[stage] = await response.json();
                }
                
                // Also fetch main strategy info to see train_ratio
                const info_url = 'https://api.xnoquant.io/xalpha-api/v1/strategies/v6qikQeZN1';
                const info_resp = await fetch(info_url, {
                    headers: { 'Authorization': 'Bearer ' + token }
                });
                results['info'] = await info_resp.json();
                
                return results;
            } catch (e) {
                return { "error": e.message };
            }
        }
        """
        result = page.evaluate(fetch_js)
        
        output_path = "scratch/web_sma10_stages.json"
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
        logger.info(f"Saved stages to {output_path}")
        print(json.dumps(result, indent=2, ensure_ascii=False))

        page.close()
        browser.close()

if __name__ == "__main__":
    fetch_sma10_stages()
