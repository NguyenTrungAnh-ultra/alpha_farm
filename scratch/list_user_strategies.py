import sys
import os
import json
import logging
from playwright.sync_api import sync_playwright

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from agent.auto_submit import load_credentials_from_arch

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def list_user_strategies():
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

        # Fetch strategies list
        logger.info("Fetching strategies list...")
        fetch_js = """
        async () => {
            try {
                const authData = JSON.parse(localStorage.getItem('auth-storage'));
                const token = authData.state.accessToken;
                if (!token) return { "error": "No access token in auth-storage" };
                
                const url = 'https://api.xnoquant.io/xalpha-api/v1/strategies?page=1&limit=10&sort=-created_at&status=published&status=submitted&status=completed&status=error';
                const response = await fetch(url, {
                    headers: {
                        'Authorization': 'Bearer ' + token
                    }
                });
                return await response.json();
            } catch (e) {
                return { "error": e.message };
            }
        }
        """
        result = page.evaluate(fetch_js)
        
        output_path = "scratch/user_strategies_list.json"
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
        logger.info(f"Saved strategies list to {output_path}")
        
        if result and "data" in result and result["data"] is not None:
            strategies = result["data"]
            print(f"\nSuccessfully fetched {len(strategies)} strategies.")
            for i, s in enumerate(strategies):
                print(f"Strategy {i+1}: ID={s.get('id')} Name='{s.get('name')}' Universe={s.get('universe')} Status={s.get('status')} CreatedAt={s.get('created_at')}")
        else:
            print("Failed to fetch or error:")
            print(json.dumps(result, indent=2, ensure_ascii=False))

        page.close()
        browser.close()

if __name__ == "__main__":
    list_user_strategies()
