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

def fetch_web_trades():
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

        # Navigate to the strategy page to ensure context is fully active
        details_url = f"https://alpha.xnoquant.io/list?strategyId={STRATEGY_ID}&stage=simulate"
        logger.info(f"Navigating to details: {details_url}")
        page.goto(details_url)
        page.wait_for_timeout(4000)

        # Now evaluate fetch from the page context!
        logger.info("Executing fetch in page context...")
        
        fetch_js = f"""
        async () => {{
            try {{
                const authData = JSON.parse(localStorage.getItem('auth-storage'));
                const token = authData.state.accessToken;
                if (!token) return {{ "error": "No access token in auth-storage" }};
                
                const url = 'https://api.xnoquant.io/xalpha-api/v1/strategies/{STRATEGY_ID}/stages/simulate/summary-table?limit=10000';
                const response = await fetch(url, {{
                    headers: {{
                        'Authorization': 'Bearer ' + token
                    }}
                }});
                return await response.json();
            }} catch (e) {{
                return {{ "error": e.message }};
            }}
        }}
        """
        
        result = page.evaluate(fetch_js)
        
        if result and "data" in result and result["data"] is not None:
            trades = result["data"]
            print(f"\nSuccessfully fetched {len(trades)} trades from web API.")
            
            output_path = "scratch/web_trades_sma10.json"
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(result, f, indent=2, ensure_ascii=False)
            print(f"Saved trades to {output_path}")
            
            # Print first 5 trades
            print("\nFirst 5 trades from Web:")
            for i, t in enumerate(trades[:5]):
                print(f"Trade {i+1}: {t}")
                
            # Print last 5 trades
            print("\nLast 5 trades from Web:")
            for i, t in enumerate(trades[-5:]):
                print(f"Trade {len(trades)-4+i}: {t}")
        else:
            print("Failed to fetch trades or error:")
            print(json.dumps(result, indent=2, ensure_ascii=False))

        page.close()
        browser.close()

if __name__ == "__main__":
    fetch_web_trades()
