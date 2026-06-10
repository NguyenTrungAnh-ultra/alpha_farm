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

def fetch_charts():
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
                
                const fetchSeries = async (name, extra = "") => {{
                    const url = `https://api.xnoquant.io/xalpha-api/v1/strategies/{STRATEGY_ID}/charts?series=${{name}}${{extra}}`;
                    const res = await fetch(url, {{
                        headers: {{ 'Authorization': 'Bearer ' + token }}
                    }});
                    return await res.json();
                }};
                
                // Try with stage=simulate
                const pnls_sim = await fetchSeries('pnls', '&stage=simulate');
                const returns_sim = await fetchSeries('returns', '&stage=simulate');
                
                // Try without stage
                const pnls_no_stage = await fetchSeries('pnls');
                
                return {{ 
                    "pnls_sim": pnls_sim, 
                    "returns_sim": returns_sim,
                    "pnls_no_stage": pnls_no_stage
                }};
            }} catch (e) {{
                return {{ "error": e.message }};
            }}
        }}
        """
        
        result = page.evaluate(fetch_js)
        
        print("Sub-keys in result:")
        print(list(result.keys()) if isinstance(result, dict) else type(result))
        
        for k, v in result.items():
            if isinstance(v, dict):
                print(f"{k} success: {v.get('success')}, status: {v.get('status_code')}, data is None: {v.get('data') is None}")
                
        output_path = "scratch/charts_sma10.json"
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
        print(f"Saved charts to {output_path}")

        page.close()
        browser.close()

if __name__ == "__main__":
    fetch_charts()
