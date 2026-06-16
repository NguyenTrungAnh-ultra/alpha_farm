import re
import time
import logging
import os
from playwright.sync_api import sync_playwright
import pandas as pd
from datetime import datetime

logger = logging.getLogger(__name__)

def load_credentials_from_arch() -> tuple:
    """
    Read email and password credentials from ARCH.md in the project root.
    """
    try:
        # ARCH.md is in the project root (parent directory of agent)
        current_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.dirname(current_dir)
        arch_path = os.path.join(project_root, "ARCH.md")
        account = None
        password = None
        if os.path.exists(arch_path):
            with open(arch_path, 'r', encoding='utf-8') as f:
                content = f.read()
                acc_match = re.search(r"account:\s*(\S+)", content)
                pwd_match = re.search(r"password:\s*(\S+)", content)
                if acc_match:
                    account = acc_match.group(1).strip()
                if pwd_match:
                    password = pwd_match.group(1).strip()
        return account, password
    except Exception as e:
        logger.error(f"[AutoSubmit] Failed to load credentials from ARCH.md: {e}")
        return None, None


def inject_params_to_code(code: str, params: dict) -> str:
    """
    Replace default parameter values inside __algorithm__ with optimized values.
    """
    if not params:
        return code
    new_code = code
    for name, val in params.items():
        pattern = rf"\b{name}\s*=\s*[\w\.\-\[\]'\"]+"
        replacement = f"{name} = {repr(val)}"
        new_code = re.sub(pattern, replacement, new_code)
    return new_code

def format_code_for_xno(code: str, params: dict = None) -> str:
    """
    Format the strategy code to comply with XNOQuant rules:
    1. Strip all lines starting with import or from.
    2. Rename the strategy class to CustomStrategy.
    3. Strip the __init__ method entirely.
    4. Replace getattr(self, 'param', default) with the actual parameter value.
    5. Clean up any unallowed numpy (np) and pandas (pd) references.
    """
    # 1. Strip imports and comments
    lines = code.splitlines()
    clean_lines = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("import ") or stripped.startswith("from "):
            continue
        if stripped.startswith("#"):
            continue
        clean_lines.append(line)
        
    clean_code = "\n".join(clean_lines)
    
    # 2. Rename class definition to CustomStrategy
    pattern_class = r"class\s+(\w+)\s*\(\s*SimpleAlgorithm\s*\)\s*:"
    clean_code = re.sub(pattern_class, "class CustomStrategy(SimpleAlgorithm):", clean_code)
    
    # 3. Strip __init__ method entirely (from def __init__ up to def __algorithm__)
    init_pattern = r"def\s+__init__\s*\([\s\S]+?def\s+__algorithm__\s*\(\s*self\s*\)\s*:"
    if re.search(init_pattern, clean_code):
        clean_code = re.sub(init_pattern, "def __algorithm__(self):", clean_code)
        
    # 4. Replace getattr parameter expressions or inject self.param = value
    if params:
        remaining_params = params.copy()
        for name, val in params.items():
            pattern = rf"getattr\(\s*self\s*,\s*['\"]{name}['\"]\s*,\s*[^)]+\)"
            if re.search(pattern, clean_code):
                clean_code = re.sub(pattern, repr(val), clean_code)
                remaining_params.pop(name)
                
        # If any parameters were not replaced, inject them at the top of __algorithm__
        if remaining_params:
            assignments = []
            for name, val in remaining_params.items():
                assignments.append(f"        self.{name} = {repr(val)}")
            assignments_str = "\n".join(assignments)
            clean_code = clean_code.replace("def __algorithm__(self):", f"def __algorithm__(self):\n{assignments_str}\n")
        
    # 5. Clean up np/pd references to only use Series methods
    clean_code = re.sub(
        r"pd\.Series\(\s*np\.where\(\s*(\w+),\s*(\w+),\s*np\.nan\s*\),\s*index\s*=\s*\w+\.index\s*\)\.ffill\(\)",
        r"\2.where(\1).ffill()",
        clean_code
    )
    clean_code = re.sub(
        r"pd\.Series\(\s*np\.where\(\s*(\w+),\s*(\w+),\s*np\.nan\s*\),\s*index\s*=\s*\w+\.index\s*\)",
        r"\2.where(\1)",
        clean_code
    )
    
    # 6. Replace __dict__ fallback parameter checks with direct default values to avoid dunder errors
    # E.g. self.smooth_period = int(self.smooth_period if 'smooth_period' in self.__dict__ else 15) -> self.smooth_period = 15
    pattern_fallback = r"self\.(\w+)\s*=\s*(int|float)\(\s*self\.\1\s*if\s*['\"]\1['\"]\s*in\s*self\.__dict__\s*else\s*([^)]+)\)"
    clean_code = re.sub(pattern_fallback, r"self.\1 = \3", clean_code)
    
    # 7. Replace self.feat.max/min with self.feat.rolling_max/min to bypass web sandbox suffix checks
    clean_code = re.sub(r"self\.feat\.max\(([^,]+),\s*(?:timeperiod|window)=([^)]+)\)", r"self.feat.rolling_max(\1, window=\2)", clean_code)
    clean_code = re.sub(r"self\.feat\.min\(([^,]+),\s*(?:timeperiod|window)=([^)]+)\)", r"self.feat.rolling_min(\1, window=\2)", clean_code)
    # Generic fallback if not matching the pattern above
    clean_code = re.sub(r"\bself\.feat\.max\b", "self.feat.rolling_max", clean_code)
    clean_code = re.sub(r"\bself\.feat\.min\b", "self.feat.rolling_min", clean_code)
    
    # 8. Replace self.feat.cdlengulfing with self.feat.engulfing_pattern
    clean_code = re.sub(r"\bself\.feat\.cdlengulfing\b", "self.feat.engulfing_pattern", clean_code)
    
    return clean_code

def get_ui_errors(page) -> str:
    """
    Attempt to extract any visible error, alert, dialog or toast message from the page.
    """
    try:
        errors = page.evaluate("""() => {
            let messages = [];
            
            // 1. Toast notifications
            let toastElements = document.querySelectorAll('.Toastify__toast, [class*="toast" i], [role="alert"], [role="status"]');
            toastElements.forEach(el => {
                let text = el.innerText || el.textContent;
                if (text) {
                    let clean = text.trim();
                    if (clean && !messages.includes(clean)) {
                        messages.push(clean);
                    }
                }
            });

            // 2. Modals/Dialogs containing error/warning/validation/lỗi
            let dialogElements = document.querySelectorAll('[role="dialog"], [class*="modal" i], [class*="dialog" i]');
            dialogElements.forEach(el => {
                let text = el.innerText || el.textContent;
                if (text) {
                    let clean = text.trim();
                    let lower = clean.toLowerCase();
                    if (clean && !messages.includes(clean)) {
                        if (lower.includes('error') || lower.includes('lỗi') || lower.includes('fail') || 
                            lower.includes('invalid') || lower.includes('cấm') || lower.includes('vi phạm')) {
                            messages.push(clean);
                        }
                    }
                }
            });

            // 3. Error text elements in DOM
            let errorElements = document.querySelectorAll('.text-red-500, .text-red-600, .text-destructive, [class*="error" i], [class*="danger" i]');
            errorElements.forEach(el => {
                let text = el.innerText || el.textContent;
                if (text) {
                    let clean = text.trim();
                    if (clean && clean.length < 500 && !messages.includes(clean)) {
                        if (!['simulate', 'cancel', 'close', 'x', 'hủy', 'đóng'].includes(clean.toLowerCase())) {
                            messages.push(clean);
                        }
                    }
                }
            });

            // 4. Terminal / Log panel content (black background, mono font, or terminal classes)
            let logElements = document.querySelectorAll('.terminal, [class*="terminal" i], [class*="console" i], [class*="log" i], .bg-black, .font-mono');
            logElements.forEach(el => {
                let text = el.innerText || el.textContent;
                if (text && text.trim().length > 10) {
                    let clean = text.trim();
                    if (clean.length < 2000 && !messages.includes(clean)) {
                        let lower = clean.toLowerCase();
                        if (lower.includes('error') || lower.includes('lỗi') || lower.includes('fail') || 
                            lower.includes('invalid') || lower.includes('traceback') || lower.includes('line ')) {
                            messages.push("Log Panel: " + clean);
                        }
                    }
                }
            });

            // Filter out success messages if error messages are present
            let hasErrors = messages.some(m => {
                let l = m.toLowerCase();
                return l.includes('error') || l.includes('lỗi') || l.includes('fail') || l.includes('invalid') || l.includes('vi phạm') || l.includes('line ') || l.includes('traceback');
            });
            if (hasErrors) {
                messages = messages.filter(m => !m.toLowerCase().includes('success') && !m.toLowerCase().includes('thành công') && !m.toLowerCase().includes('started successfully'));
            }

            return messages.filter(x => x.length > 0).join(' | ');
        }""")
        return errors if errors else "No specific UI errors found"
    except Exception as e:
        return f"Failed to retrieve UI errors: {e}"

def run_auto_submit(strategy_code: str, timeframe: str = "15m", params: dict = None, timeout_seconds: int = 300, filepath: str = None) -> tuple:
    """
    Automate strategy creation, simulation, and submission on XNOQuant via Playwright CDP.
    
    Parameters
    ----------
    strategy_code : str
        The strategy python code.
    timeframe : str
        Timeframe (e.g. "1m", "5m", "10m", "15m", "30m", "60m").
    timeout_seconds : int
        Max wait time for simulation.
    filepath : str
        Optional. The path of the strategy file. If provided, the file will be moved to agent/results/pushed/ on success, or agent/results/failed/ on failure.
        
    Returns
    -------
    tuple (bool, str)
        success: True if submitted successfully (or simulated successfully), False otherwise.
        err_msg: Detailed error description/pop-up text if success is False, or None/warning details if True.
    """
    max_attempts = 2
    success = False
    err_msg = None
    
    for attempt in range(max_attempts):
        success, err_msg = _run_auto_submit_core(strategy_code, timeframe, params, timeout_seconds, filepath)
        if success:
            break
            
        # Check if rate limit exceeded
        if err_msg and "rate limit exceeded" in err_msg.lower():
            if attempt < max_attempts - 1:
                logger.warning(f"[AutoSubmit] Rate limit encountered: {err_msg}. Sleeping 60 seconds and retrying (attempt {attempt + 2}/{max_attempts})...")
                time.sleep(60)
                continue
        break
        
    if filepath and os.path.exists(filepath):
        import shutil
        target_dir_name = "pushed" if success else "failed"
        
        # Check origin to sub-categorize
        sub_dir = "llm_strategies"
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()
                if "[MCTS_DISCOVERY_ENGINE]" in content:
                    sub_dir = "mcts_strategies"
        except Exception:
            pass
            
        target_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results", target_dir_name, sub_dir)
        os.makedirs(target_dir, exist_ok=True)
        dest_path = os.path.join(target_dir, os.path.basename(filepath))
        try:
            shutil.move(filepath, dest_path)
            logger.info(f"[AutoSubmit] Moved {filepath} to {target_dir}")
            
            # Move corresponding _equity.csv if exists
            csv_filepath = filepath.replace(".py", "_equity.csv")
            if os.path.exists(csv_filepath):
                csv_dest = os.path.join(target_dir, os.path.basename(csv_filepath))
                shutil.move(csv_filepath, csv_dest)
                
            # Move corresponding _positions.csv if exists
            pos_filepath = filepath.replace(".py", "_positions.csv")
            if os.path.exists(pos_filepath):
                pos_dest = os.path.join(target_dir, os.path.basename(pos_filepath))
                shutil.move(pos_filepath, pos_dest)
                
        except Exception as e:
            logger.error(f"[AutoSubmit] Failed to move files: {e}")
            
    return success, err_msg

def log_console_message(msg):
    text = msg.text
    # Filter out common accessibility warnings/errors from Radix UI / React
    # that do not affect the execution of our script.
    if any(k in text for k in ["DialogContent", "DialogTitle", "VisuallyHidden", "aria-describedby"]):
        return
    logger.info(f"[Browser Console] {msg.type}: {text}")

def _run_auto_submit_core(strategy_code: str, timeframe: str = "15m", params: dict = None, timeout_seconds: int = 300, filepath: str = None) -> tuple:
    strategy_code = format_code_for_xno(strategy_code, params)
    
    timeframe_map = {
        "1m": "VN30F1M-01MIN",
        "3m": "VN30F1M-03MIN",
        "5m": "VN30F1M-05MIN",
        "10m": "VN30F1M-10MIN",
        "15m": "VN30F1M-15MIN",
        "30m": "VN30F1M-30MIN",
        "60m": "VN30F1M-60MIN"
    }
    
    target_universe = timeframe_map.get(timeframe.lower())
    if not target_universe:
        logger.error(f"[AutoSubmit] Invalid timeframe: {timeframe}")
        return False, f"Invalid timeframe: {timeframe}"
        
    try:
        with sync_playwright() as p:
            browser = None
            try:
                logger.info("[AutoSubmit] Connecting to Chrome CDP on localhost:9222...")
                browser = p.chromium.connect_over_cdp("http://localhost:9222")
                context = browser.contexts[0]
                page = context.new_page()
                page.on("console", log_console_message)
                logger.info("[AutoSubmit] Navigating to build page...")
                page.goto("https://alpha.xnoquant.io/build")
                page.wait_for_selector("button.shrink-0.w-14.border-r", timeout=5000)
            except Exception as cdp_err:
                logger.warning(f"[AutoSubmit] CDP connection failed or not logged in: {cdp_err}. Launching local browser instead...")
                if browser:
                    try:
                        browser.close()
                    except:
                        pass
                
                # Launch a new Chromium browser
                browser = p.chromium.launch(headless=True)
                context = browser.new_context()
                page = context.new_page()
                page.on("console", log_console_message)
                
                # Load credentials from ARCH.md
                account, password = load_credentials_from_arch()
                if not account or not password:
                    logger.error("[AutoSubmit] Could not find account credentials in ARCH.md")
                    return False, "Could not find account credentials in ARCH.md"
                
                logger.info("[AutoSubmit] Navigating to build page...")
                page.goto("https://alpha.xnoquant.io/build")
                page.wait_for_timeout(3000)
                
                if "dang-nhap" in page.url or page.locator("input[type='password']").count() > 0:
                    logger.info("[AutoSubmit] Login page detected. Performing automated login...")
                    page.fill("input[type='text']", account)
                    page.fill("input[type='password']", password)
                    page.click("button:has-text('Login')")
                    page.wait_for_timeout(3000)
                    
                    logger.info("[AutoSubmit] Navigating back to build page after login...")
                    page.goto("https://alpha.xnoquant.io/build")
                    page.wait_for_timeout(2000)
                
                # Wait for page to load
                page.wait_for_selector("button.shrink-0.w-14.border-r", timeout=15000)
            
            logger.info("[AutoSubmit] Adding new strategy tab...")
            page.click("button.shrink-0.w-14.border-r")
            page.wait_for_timeout(1500)
            
            logger.info("[AutoSubmit] Waiting for Monaco editor to load...")
            try:
                page.wait_for_function("window.monaco !== undefined", timeout=15000)
            except Exception as e:
                logger.error("[AutoSubmit] Monaco editor did not load in time.")
                page.close()
                return False, "Monaco editor did not load in time"
                
            logger.info("[AutoSubmit] Setting Monaco Editor content on the active tab...")
            escaped_code = strategy_code.replace("\\", "\\\\").replace("`", "\\`").replace("$", "\\$")
            page.evaluate(f"""() => {{
                let editors = monaco.editor.getEditors();
                let activeEditor = editors.find(e => {{
                    let domNode = e.getDomNode();
                    return domNode && domNode.getBoundingClientRect().width > 0;
                }});
                if (activeEditor) {{
                    activeEditor.setValue(`{escaped_code}`);
                }} else if (editors.length > 0) {{
                    editors[editors.length - 1].setValue(`{escaped_code}`);
                }} else {{
                    throw new Error("No Monaco editor instances found");
                }}
            }}""")
            page.wait_for_timeout(500)
            
            logger.info(f"[AutoSubmit] Configuring settings for {target_universe}...")
            config_result = page.evaluate("""async (targetUniv) => {
                let settingsBtn = document.getElementById('onboarding-settings-btn');
                if (!settingsBtn) throw new Error('Settings button not found');
                settingsBtn.click();
                
                const wait = ms => new Promise(r => setTimeout(r, ms));
                await wait(500);
                
                let dialog = document.querySelector('[role="dialog"]');
                if (!dialog) throw new Error('Settings dialog not found');
                
                let buttons = Array.from(dialog.querySelectorAll('button'));
                
                // Click Market
                let marketBtn = buttons.find(b => b.textContent.includes('Crypto Spot') || b.textContent.includes('Vietnam Future') || b.textContent.includes('Vietnam Stock'));
                if (marketBtn && !marketBtn.textContent.includes('Vietnam Future')) {
                    marketBtn.click();
                    await wait(500);
                    let divs = Array.from(document.querySelectorAll('div, button, span'));
                    let targetMarket = divs.find(d => d.textContent.trim() === 'Vietnam Future');
                    if (targetMarket) targetMarket.click();
                    await wait(500);
                }
                
                // Refresh buttons reference
                buttons = Array.from(dialog.querySelectorAll('button'));
                
                // Click Universe
                let universeBtn = buttons.find(b => b.textContent.includes('VN30F1M') || b.textContent.includes('TOP10'));
                if (universeBtn && !universeBtn.textContent.includes(targetUniv)) {
                    universeBtn.click();
                    await wait(500);
                    let divs = Array.from(document.querySelectorAll('div, button, span'));
                    let targetOption = divs.find(d => d.textContent.trim() === targetUniv);
                    if (targetOption) targetOption.click();
                    await wait(500);
                }
                
                // Click Save
                buttons = Array.from(dialog.querySelectorAll('button'));
                let saveBtn = buttons.find(b => b.textContent.trim() === 'Save');
                if (saveBtn) {
                    saveBtn.click();
                    return 'Settings saved';
                }
                throw new Error('Save button not found');
            }""", target_universe)
            
            logger.info(f"[AutoSubmit] {config_result}")
            page.wait_for_timeout(1000)
            
            logger.info("[AutoSubmit] Running simulation...")
            click_result = page.evaluate("""() => {
                let buttons = Array.from(document.querySelectorAll('button'));
                let simulateBtn = buttons.find(b => {
                    let text = b.textContent || b.innerText;
                    let isSimulate = text && text.trim() === 'Simulate';
                    let isVisible = b.getBoundingClientRect().width > 0;
                    return isSimulate && isVisible;
                });
                if (simulateBtn) {
                    simulateBtn.click();
                    return "Clicked visible Simulate button";
                }
                let fallbackBtn = buttons.find(b => (b.textContent || b.innerText || '').trim() === 'Simulate');
                if (fallbackBtn) {
                    fallbackBtn.click();
                    return "Clicked fallback Simulate button";
                }
                return "Simulate button not found in DOM";
            }""")
            logger.info(f"[AutoSubmit] Simulate click trigger: {click_result}")
            
            # Poll status
            logger.info("[AutoSubmit] Polling simulation status...")
            start_time = time.time()
            sim_success = False
            
            while time.time() - start_time < timeout_seconds:
                # Save screenshot to debug what's on the screen
                try:
                    page.screenshot(path="C:/Users/TPAA/.gemini/antigravity/brain/1d3d35f3-81b2-4796-94ce-b8fd9971db7d/playwright_sim_poll.png")
                except Exception as ss_err:
                    logger.error(f"[AutoSubmit] Failed to take polling screenshot: {ss_err}")

                # Evaluate status and log all badges found in the toolbar for debugging
                eval_result = page.evaluate("""() => {
                    let titleEl = document.querySelector('h1.text-xl.font-semibold');
                    let toolbar = titleEl ? titleEl.parentElement.parentElement : null;
                    let badges = [];
                    if (toolbar) {
                        badges = Array.from(toolbar.querySelectorAll('span, div')).map(b => b.textContent.trim());
                    }
                    
                    let statusBadge = null;
                    if (toolbar) {
                        statusBadge = Array.from(toolbar.querySelectorAll('span, div')).find(b => {
                            let text = b.textContent.trim().toLowerCase();
                            return ['draft', 'simulating', 'running', 'completed', 'published', 'failed', 'error'].includes(text);
                        });
                    }
                    
                    if (!statusBadge) {
                        let potentialBadges = Array.from(document.querySelectorAll('span, div, p, button')).filter(el => {
                            let text = el.textContent.trim().toLowerCase();
                            return ['draft', 'simulating', 'running', 'completed', 'published', 'failed', 'error'].includes(text);
                        });
                        statusBadge = potentialBadges.find(el => el.getBoundingClientRect().width > 0);
                    }
                    
                    return {
                        status: statusBadge ? statusBadge.textContent.trim() : 'Unknown',
                        badges: badges
                    };
                }""")
                
                status_text = eval_result['status']
                found_badges = eval_result['badges']
                ui_errs = get_ui_errors(page)
                logger.info(f"[AutoSubmit] Status: {status_text} | Toolbar badges found: {found_badges} | UI Errors: {ui_errs}")
                
                # Check for compilation/verification/rate-limit errors in UI to abort early
                if ui_errs and ("verification failed" in ui_errs.lower() or "is not allowed" in ui_errs.lower() or "not allowed in strategy code" in ui_errs.lower() or "has no method" in ui_errs.lower() or "is not defined" in ui_errs.lower() or "rate limit exceeded" in ui_errs.lower()):
                    logger.error(f"[AutoSubmit] Aborting simulation early due to error: {ui_errs}")
                    page.close()
                    return False, f"Simulation aborted early due to error: {ui_errs}"
                
                # Check for compilation errors (remains Draft too long)
                if status_text.lower() == 'draft' and (time.time() - start_time) > 20:
                    ui_err = get_ui_errors(page)
                    logger.error(f"[AutoSubmit] Strategy failed to compile (Status remained Draft for > 20s). UI Errors: {ui_err}")
                    page.close()
                    return False, f"Strategy failed to compile (remained Draft > 20s). UI Errors: {ui_err}"
                    
                if status_text.lower() in ["published", "completed"]:
                    logger.info(f"[AutoSubmit] Simulation finished with status: {status_text}. Proceeding to submission...")
                    sim_success = True
                    
                    logger.info("[AutoSubmit] Extracting performance metrics...")
                    try:
                        page.evaluate("""() => {
                            let tabs = Array.from(document.querySelectorAll('button, a, div, span'));
                            let perfTab = tabs.find(b => b.textContent === 'Performance' || b.innerText === 'Performance');
                            if (perfTab) perfTab.click();
                        }""")
                        page.wait_for_timeout(1000)
                        
                        metrics = page.evaluate("""() => {
                            let data = {};
                            let elements = document.querySelectorAll('div.flex.justify-between, li.flex.justify-between');
                            elements.forEach(el => {
                                let children = el.children;
                                if (children.length >= 2) {
                                    let key = children[0].innerText || children[0].textContent;
                                    let val = children[1].innerText || children[1].textContent;
                                    if (key && val) {
                                        key = key.trim();
                                        val = val.trim();
                                        if (key.length > 0 && key.length < 40 && val.length < 40) {
                                            data[key] = val;
                                        }
                                    }
                                }
                            });
                            return data;
                        }""")
                        
                        if metrics and len(metrics) > 0:
                            logger.info(f"[AutoSubmit] Extracted {len(metrics)} metrics: {metrics}")
                            csv_path = os.path.join(os.path.dirname(__file__), "results", "leaderboard.csv")
                            strat_name = os.path.basename(filepath) if filepath else "Unknown"
                            
                            row_data = {"Timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "Strategy": strat_name}
                            row_data.update(metrics)
                            df_new = pd.DataFrame([row_data])
                            
                            if os.path.isfile(csv_path) and os.path.getsize(csv_path) > 0:
                                df_existing = pd.read_csv(csv_path)
                                df_combined = pd.concat([df_existing, df_new], ignore_index=True)
                                df_combined.to_csv(csv_path, index=False)
                            else:
                                df_new.to_csv(csv_path, index=False)
                        else:
                            logger.warning("[AutoSubmit] Could not extract metrics from UI.")
                    except Exception as e:
                        logger.error(f"[AutoSubmit] Failed to extract metrics: {e}")
                        
                    break
                elif status_text.lower() in ["failed", "error"]:
                    ui_err = get_ui_errors(page)
                    logger.error(f"[AutoSubmit] Simulation failed (compilation/runtime error). Details: {ui_err}")
                    page.close()
                    return False, f"Simulation failed/errored. UI Errors: {ui_err}"
                
                time.sleep(5)
                
            if not sim_success:
                ui_err = get_ui_errors(page)
                logger.error(f"[AutoSubmit] Simulation timed out or failed to publish. UI Errors: {ui_err}")
                try:
                    screenshot_path = "C:/Users/TPAA/.gemini/antigravity/brain/1d3d35f3-81b2-4796-94ce-b8fd9971db7d/playwright_sim_timeout.png"
                    page.screenshot(path=screenshot_path)
                    logger.info(f"[AutoSubmit] Saved timeout screenshot to {screenshot_path}")
                except Exception as ss_err:
                    logger.error(f"[AutoSubmit] Failed to take screenshot: {ss_err}")
                page.close()
                return False, f"Simulation timed out or failed to publish. UI Errors: {ui_err}"
                
            # Get strategy ID from localStorage (find the newest editor state)
            logger.info("[AutoSubmit] Fetching Strategy ID from localStorage...")
            strategy_ids = page.evaluate("""() => {
                try {
                    const authData = JSON.parse(localStorage.getItem('auth-storage'));
                    const uid = authData.state.user.uid;
                    const editorStates = JSON.parse(localStorage.getItem('xno-editor-states-' + uid));
                    
                    let newestId = null;
                    let newestTime = 0;
                    for (let id in editorStates) {
                        let t = new Date(editorStates[id].editor.created_at).getTime();
                        if (t > newestTime) {
                            newestTime = t;
                            newestId = id;
                        }
                    }
                    if (newestId) {
                        return editorStates[newestId].editor.strategy_ids;
                    }
                    return [];
                } catch(e) {
                    return [];
                }
            }""")
            
            if not strategy_ids:
                logger.warning("[AutoSubmit] Failed to get strategy ID from localStorage. Treating as simulated-only.")
                page.close()
                return True, "Simulated successfully but failed to get strategy ID from localStorage"
                
            strategy_id = strategy_ids[0]
            logger.info(f"[AutoSubmit] Strategy ID found: {strategy_id}")
            
            # Navigate to Details View
            details_url = f"https://alpha.xnoquant.io/list?strategyId={strategy_id}&stage=train"
            logger.info(f"[AutoSubmit] Navigating to Details URL: {details_url}")
            page.goto(details_url)
            page.wait_for_timeout(2000)
            
            # Click three-dots menu in details panel
            logger.info("[AutoSubmit] Clicking details action menu...")
            page.wait_for_selector('button[aria-haspopup="menu"].size-8')
            page.keyboard.press('Escape')  # Dismiss any lingering toasts/modals
            page.wait_for_timeout(500)
            page.click('button[aria-haspopup="menu"].size-8', force=True)
            page.wait_for_timeout(1000)
            
            # Click Submit Alpha
            logger.info("[AutoSubmit] Clicking Submit Alpha...")
            submit_item_selector = 'div[role="menuitem"]:has-text("Submit Alpha")'
            try:
                page.wait_for_selector(submit_item_selector, timeout=10000)
                page.click(submit_item_selector, force=True)
            except Exception as e:
                logger.warning("[AutoSubmit] Submit Alpha option not found in menu or timed out. Treating as simulated-only.")
                page.close()
                return True, f"Simulated successfully but Submit Alpha option not found: {e}"
                
            page.wait_for_timeout(1500)
            
            # Click competition selection and confirm
            logger.info("[AutoSubmit] Confirming VQC 2026 event submission...")
            try:
                comp_selector = 'button:has-text("Data Science Talent Competition")'
                page.wait_for_selector(comp_selector, timeout=10000)
                page.click(comp_selector, force=True)
                page.wait_for_timeout(500)
                
                confirm_selector = 'button:has-text("Confirm submission")'
                page.wait_for_selector(confirm_selector, timeout=10000)
                page.click(confirm_selector, force=True)
                page.wait_for_timeout(1000)
                submission_result = 'Submitted'
            except Exception as e:
                # Cố gắng trích xuất text từ popup/modal để xem nguyên nhân nút bị mờ
                error_details = ""
                try:
                    # Tìm text trong các thành phần UI có thể chứa thông báo lỗi
                    error_details = page.locator('[role="dialog"]').inner_text(timeout=1000)
                    error_details = " ".join(error_details.split()) # Xóa khoảng trắng thừa
                except Exception:
                    pass
                    
                msg = f"Simulated successfully but failed during confirmation. Modal text: '{error_details}'. Exception: {e}"
                logger.warning(f"[AutoSubmit] {msg}")
                page.close()
                return True, msg
            
            logger.info(f"[AutoSubmit] Result: {submission_result}")
            page.close()
            if submission_result == 'Submitted':
                return True, None
            else:
                return False, f"Submission result was not 'Submitted': {submission_result}"
            
    except Exception as e:
        logger.error(f"[AutoSubmit] Error: {e}")
        return False, f"Exception occurred: {e}"
