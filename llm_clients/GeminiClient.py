"""
Gemini Client — Self-contained, model-selectable
=================================================
Sends requests directly to Gemini StreamGenerate endpoint with model headers.
No dependency on gemini or gemini_webapi packages.

Based on reverse-engineering both packages:
- Old `gemini` package: sync requests, session/nonce management, response parsing
- `gemini_webapi` package: model headers, cookie rotation, endpoint format

Features:
    - Model selection (Pro, Flash, Thinking)
    - Sync requests (stable in notebooks)
    - Auto cookie refresh via RotateCookies endpoint
    - Retry with exponential backoff
    - Rate limiting
    - JSON extraction from responses
    - Robust response parsing

Usage:
    from agent import GeminiChat

    chat = GeminiChat(cookies={...}, model="pro")
    text = chat.send("Đề xuất trading strategy")
    data = chat.send_json("Return JSON with strategy details")
"""

import os
import re
import json
import time
import random
import string
import threading
import urllib.parse
from typing import Optional, Any, Union

import requests


# ─── Model Definitions ──────────────────────────────────────────────
# Format: x-goog-ext-525001261-jspb header value
# [1,null,null,null,"<model_id>",null,null,0,[4],null,null,<capacity>]
#
# capacity=1: Free, capacity=2: Advanced/Pro, capacity=4: Plus

MODEL_HEADER_KEY = "x-goog-ext-525001261-jspb"

MODELS = {
    # ── Free tier ──
    "flash": {
        "id": "fbb127bbb056c959",
        "capacity": 1,
        "name": "gemini-3-flash",
    },
    "pro": {
        "id": "9d8ca3786ebdfbea",
        "capacity": 1,
        "name": "gemini-3-pro",
    },
    "thinking": {
        "id": "5bf011840784117a",
        "capacity": 1,
        "name": "gemini-3-flash-thinking",
    },
    # ── Advanced tier (capacity=2) ──
    "advanced-pro": {
        "id": "e6fa609c3fa255c0",
        "capacity": 2,
        "name": "gemini-3-pro-advanced",
    },
    "advanced-flash": {
        "id": "56fdd199312815e2",
        "capacity": 2,
        "name": "gemini-3-flash-advanced",
    },
    "advanced-thinking": {
        "id": "e051ce1aa80aa576",
        "capacity": 2,
        "name": "gemini-3-flash-thinking-advanced",
    },
    # ── Plus tier (capacity=4) ──
    "plus-pro": {
        "id": "e6fa609c3fa255c0",
        "capacity": 4,
        "name": "gemini-3-pro-plus",
    },
    "plus-flash": {
        "id": "56fdd199312815e2",
        "capacity": 4,
        "name": "gemini-3-flash-plus",
    },
}

# Aliases
MODELS["default"] = MODELS["flash"]


def _build_model_header(model_id: str, capacity: int) -> dict:
    """Build the HTTP headers for model selection."""
    return {
        MODEL_HEADER_KEY: (
            f'[1,null,null,null,"{model_id}",null,null,0,[4],null,null,{capacity}]'
        ),
        "x-goog-ext-73010989-jspb": "[0]",
        "x-goog-ext-73010990-jspb": "[0]",
    }


def _get_model_headers(model_key: str) -> dict:
    """Get model headers by short name."""
    model = MODELS.get(model_key)
    if model is None:
        available = ", ".join(MODELS.keys())
        raise ValueError(f"Unknown model: '{model_key}'. Available: {available}")
    return _build_model_header(model["id"], model["capacity"])


# ─── JSON Extraction ────────────────────────────────────────────────
def extract_json(text: str) -> Optional[Union[dict, list]]:
    """
    Extract JSON from LLM response text.
    Handles: ```json ... ```, raw JSON, or JSON embedded in markdown.
    """
    if not text:
        return None

    # Strategy 1: ```json ... ``` block
    pattern = r'```(?:json)?\s*\n?([\s\S]*?)\n?```'
    matches = re.findall(pattern, text)
    for match in matches:
        try:
            return json.loads(match.strip())
        except json.JSONDecodeError:
            continue

    # Strategy 2: Raw JSON object/array
    for start_char, end_char in [('{', '}'), ('[', ']')]:
        start = text.find(start_char)
        if start == -1:
            continue
        depth = 0
        for i in range(start, len(text)):
            if text[i] == start_char:
                depth += 1
            elif text[i] == end_char:
                depth -= 1
                if depth == 0:
                    try:
                        return json.loads(text[start:i + 1])
                    except json.JSONDecodeError:
                        break
    return None


# ─── Text Cleaning ──────────────────────────────────────────────────
def _clean_text(text: str) -> str:
    """
    Clean LLM response text by removing non-text content.
    Strips: googleusercontent image links, standalone URLs, 
    markdown image syntax, excessive blank lines.
    """
    if not text:
        return text

    lines = text.split('\n')
    cleaned = []

    for line in lines:
        stripped = line.strip()

        # Skip lines that are just URLs (image links from Gemini)
        if re.match(r'^https?://\S+$', stripped):
            continue

        # Skip googleusercontent links (images generated by Gemini)
        if 'googleusercontent.com' in stripped:
            # Remove just the URL part, keep surrounding text
            line = re.sub(
                r'https?://googleusercontent\.com/\S+',
                '', line
            ).strip()
            if not line:
                continue

        # Remove markdown image syntax ![alt](url)
        line = re.sub(r'!\[[^\]]*\]\([^)]+\)', '', line)

        # Remove inline image references like [image: ...]
        line = re.sub(r'\[image[:\s][^\]]*\]', '', line, flags=re.IGNORECASE)

        cleaned.append(line)

    # Join and collapse multiple blank lines into max 2
    result = '\n'.join(cleaned)
    result = re.sub(r'\n{3,}', '\n\n', result)

    return result.strip()


# ─── Response Parser ────────────────────────────────────────────────
def _parse_response(raw_text: str) -> str:
    """
    Parse Gemini StreamGenerate response to extract the actual text.
    
    Known response structure (confirmed via debug_dump):
        inner[1]  = ['c_xxxx', 'r_xxxx']                    ← conversation metadata
        inner[4]  = [['rc_xxxx', ['actual text'], ...]]      ← response content
        inner[14] = True when streaming is complete           ← completion flag
        inner[4][0][1] = ['actual response text']             ← THE text we want
        inner[4][0][8] = [2] when response is finalized       ← finalization flag
    
    The Pro model may include "thinking" text at other paths — we ONLY
    extract from inner[4][0][1] to avoid picking up reasoning traces.
    """
    lines = raw_text.split("\n")
    
    # Collect response text from each frame, take the last complete one
    last_text = ""
    final_text = ""  # text from frame where inner[14]=True
    
    for line in lines:
        line = line.strip()
        if not line or line.isdigit():
            continue

        try:
            outer = json.loads(line)
        except json.JSONDecodeError:
            continue

        if not isinstance(outer, list) or len(outer) < 1:
            continue

        for item in outer:
            if not isinstance(item, list) or len(item) < 3:
                continue

            inner_str = item[2]
            if not isinstance(inner_str, str):
                continue

            try:
                inner = json.loads(inner_str)
            except json.JSONDecodeError:
                continue

            if not isinstance(inner, list) or len(inner) < 5:
                continue
            
            # ── Check for error responses ──
            text_at_path = _get_text_at_path(inner)
            if text_at_path and "googleapis.com" in text_at_path:
                # This is an error, not actual content
                continue
            if text_at_path and "BardError" in text_at_path:
                continue
            
            if text_at_path and len(text_at_path) > 0:
                last_text = text_at_path
                
                # Check if this is the final (complete) frame
                try:
                    is_final = (len(inner) > 14 and inner[14] is True)
                except (IndexError, TypeError):
                    is_final = False
                
                if is_final:
                    final_text = text_at_path

    # Prefer final frame text, fall back to last seen text
    result = final_text or last_text
    
    if not result:
        # Last resort: find longest meaningful string
        result = _find_longest_string_in_response(raw_text)
    
    return result


def _get_text_at_path(inner: list) -> str:
    """Extract text from the known path: inner[4][0][1][0]."""
    try:
        candidates = inner[4]
        if not isinstance(candidates, list) or len(candidates) == 0:
            return ""
        
        first_candidate = candidates[0]
        if not isinstance(first_candidate, list) or len(first_candidate) < 2:
            return ""
        
        text_parts = first_candidate[1]
        if isinstance(text_parts, list) and len(text_parts) > 0:
            # Join all text parts (sometimes split across multiple elements)
            parts = [p for p in text_parts if isinstance(p, str)]
            return "\n".join(parts)
        elif isinstance(text_parts, str):
            return text_parts
        
        return ""
    except (IndexError, TypeError, KeyError):
        return ""


def _find_longest_string_in_response(raw_text: str) -> str:
    """Last resort: find the longest text-like string in raw response."""
    all_strings = re.findall(r'"((?:[^"\\]|\\.){30,})"', raw_text)
    best = ""
    for s in all_strings:
        try:
            decoded = s.encode().decode('unicode_escape')
        except Exception:
            decoded = s.replace('\\n', '\n').replace('\\"', '"')
        
        # Skip non-text content
        if (decoded.startswith(("http", "data:", "//", "type.googleapis", "Aw", "[", "{")) or
            'googleapis.com' in decoded or
            'BardError' in decoded):
            continue
        
        # Skip if no spaces (likely not natural text)
        if ' ' not in decoded and len(decoded) < 100:
            continue
            
        if len(decoded) > len(best):
            best = decoded
    
    return best


# ─── Main Client ────────────────────────────────────────────────────

BASE_URL = "https://gemini.google.com"
GENERATE_URL = f"{BASE_URL}/_/BardChatUi/data/assistant.lamda.BardFrontendService/StreamGenerate"
ROTATE_URL = "https://accounts.google.com/RotateCookies"

DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Content-Type": "application/x-www-form-urlencoded;charset=utf-8",
    "Origin": BASE_URL,
    "Referer": f"{BASE_URL}/",
    "X-Same-Domain": "1",
    "Accept": "*/*",
    "Accept-Language": "en-US,en;q=0.9",
    "DNT": "1",
    "Connection": "keep-alive",
    "Sec-Fetch-Dest": "empty",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Site": "same-origin",
}


class GeminiChat:
    """
    Self-contained Gemini client with model selection.

    Parameters
    ----------
    cookies : dict
        Full Google cookies dictionary from browser.
    model : str
        Model short name: "flash", "pro", "thinking",
        "advanced-pro", "advanced-flash", "advanced-thinking",
        "plus-pro", "plus-flash"
    request_delay : float
        Min seconds between requests (rate limiting).
    max_retries : int
        Max attempts per request.
    timeout : float
        HTTP timeout in seconds.
    auto_rotate : bool
        Auto-rotate cookies to keep session alive.
    rotate_interval : float
        Seconds between cookie rotations (default 600 = 10 min).
    verbose : bool
        Print debug info.
    """

    @staticmethod
    def parse_cookie_string(cookie_str: str) -> dict:
        """
        Parse raw cookie string from browser Network tab.
        Format: 'key1=value1; key2=value2; ...'
        """
        cookies = {}
        for pair in cookie_str.split(';'):
            pair = pair.strip()
            if '=' not in pair:
                continue
            key, _, value = pair.partition('=')
            key = key.strip()
            # Skip tracking cookies (not needed for Gemini API)
            if key.startswith(('_ga', '_gcl')):
                continue
            cookies[key] = value.strip()
        return cookies

    def __init__(
        self,
        cookies,  # str or dict
        model: str = "flash",
        request_delay: float = 3.0,
        max_retries: int = 3,
        timeout: float = 60,
        auto_rotate: bool = True,
        rotate_interval: float = 600,
        verbose: bool = False,
    ):
        # Parse cookies (support raw string from browser or dict)
        if isinstance(cookies, str):
            self.cookies = self.parse_cookie_string(cookies)
        else:
            self.cookies = cookies

        self.model = model
        self.request_delay = request_delay
        self.max_retries = max_retries
        self.timeout = timeout
        self.auto_rotate = auto_rotate
        self.rotate_interval = rotate_interval
        self.verbose = verbose

        self._session = requests.Session()
        self._session.headers.update(DEFAULT_HEADERS)
        self._session.cookies.update(self.cookies)

        self._nonce = None
        self._sid = None
        self._cid = None
        self._rid = None
        self._rcid = None
        self._reqid = int("".join(random.choices(string.digits, k=7)))
        self._last_request_time = 0
        self._request_count = 0
        self._last_rotate_time = time.time()
        self._session_init_time = time.time()
        self._rotate_lock = threading.Lock()
        self._consecutive_errors = 0

        self._init_session()

        # Start background keepalive thread (prevents cookie expiry during long operations)
        self._keepalive_interval = 300  # 5 minutes
        self._keepalive_stop = threading.Event()
        self._keepalive_thread = threading.Thread(
            target=self._keepalive_loop, daemon=True, name="GeminiKeepalive"
        )
        self._keepalive_thread.start()

        if self.verbose:
            model_info = MODELS.get(model, {})
            rotate_str = f"auto-rotate={rotate_interval}s" if auto_rotate else "no-rotate"
            print(f"[GeminiChat] ✅ Ready | model={model} ({model_info.get('name', '?')}) | {rotate_str} | keepalive=5m")

    def _init_session(self):
        """Fetch SNlM0e nonce value required for POST requests."""
        try:
            resp = self._session.get(f"{BASE_URL}/app", timeout=self.timeout)
            resp.raise_for_status()

            nonce_match = re.search(r'"SNlM0e":"(.*?)"', resp.text)
            if nonce_match:
                self._nonce = nonce_match.group(1)
            else:
                raise ValueError("Failed to get SNlM0e nonce. Check cookies.")

            sid_match = re.search(r'"FdrFJe":"([\d-]+)"', resp.text)
            if sid_match:
                self._sid = sid_match.group(1)

            self._session_init_time = time.time()

            if self.verbose:
                print(f"[GeminiChat] Session initialized (nonce={self._nonce[:20]}...)")

        except Exception as e:
            raise ConnectionError(f"Failed to init Gemini session: {e}")

    def _keepalive_loop(self):
        """Background loop: ping Gemini every 5 min to keep cookies alive."""
        while not self._keepalive_stop.wait(self._keepalive_interval):
            try:
                with self._rotate_lock:
                    resp = self._session.get(
                        f"{BASE_URL}/app", timeout=30, allow_redirects=True
                    )
                    if resp.status_code == 200:
                        # Refresh nonce while we're at it
                        nonce_match = re.search(r'"SNlM0e":"(.*?)"', resp.text)
                        if nonce_match:
                            self._nonce = nonce_match.group(1)
                            self._session_init_time = time.time()
                        if self.verbose:
                            print(f"[GeminiChat] heartbeat OK (nonce refreshed)")
                    else:
                        if self.verbose:
                            print(f"[GeminiChat] heartbeat {resp.status_code}")
            except Exception as e:
                if self.verbose:
                    print(f"[GeminiChat] heartbeat error: {str(e)[:60]}")

    def stop_keepalive(self):
        """Stop the background keepalive thread."""
        self._keepalive_stop.set()

    def _build_payload(self, prompt: str) -> dict:
        """Build the POST payload."""
        inner = json.dumps([
            [prompt, 0, None, None, None, None, 0],
            [os.environ.get("GEMINI_LANGUAGE", "en")],
            [self._cid or "", self._rid or "", self._rcid or ""],
            None,
            None,
            None,
            [1],
        ])

        return {
            "at": self._nonce,
            "f.req": json.dumps([None, inner]),
        }

    def _build_params(self) -> dict:
        """Build URL query parameters."""
        params = {
            "hl": os.environ.get("GEMINI_LANGUAGE", "en"),
            "_reqid": self._reqid,
            "rt": "c",
        }
        if self._sid:
            params["f.sid"] = self._sid
        return params

    def _rate_limit(self):
        """Enforce minimum delay between requests."""
        elapsed = time.time() - self._last_request_time
        if elapsed < self.request_delay:
            wait = self.request_delay - elapsed
            if self.verbose:
                print(f"[GeminiChat] ⏳ {wait:.1f}s")
            time.sleep(wait)
        self._last_request_time = time.time()

    def _maybe_rotate(self):
        """
        Auto-rotate cookies if enough time has passed.
        Called before each send() to keep session alive.
        """
        if not self.auto_rotate:
            return

        elapsed = time.time() - self._last_rotate_time
        if elapsed < self.rotate_interval:
            return

        with self._rotate_lock:
            # Double-check after acquiring lock
            if time.time() - self._last_rotate_time < self.rotate_interval:
                return

            try:
                if self.verbose:
                    print(f"[GeminiChat] 🔄 Auto-rotating cookies ({elapsed:.0f}s since last)...")

                resp = self._session.post(
                    ROTATE_URL,
                    headers={
                        "Content-Type": "application/json",
                        "Origin": "https://accounts.google.com",
                    },
                    data='[000,"-0000000000000000000"]',
                    timeout=30,
                )

                if resp.status_code == 200:
                    self._last_rotate_time = time.time()
                    # Re-fetch nonce with fresh cookies
                    self._init_session()
                    if self.verbose:
                        print("[GeminiChat] ✅ Cookies rotated & session refreshed")
                elif resp.status_code == 401:
                    if self.verbose:
                        print("[GeminiChat] ⚠️ Cookie rotation 401 — cookies may have expired")
                    # Still update time to avoid spamming
                    self._last_rotate_time = time.time()
                else:
                    if self.verbose:
                        print(f"[GeminiChat] ⚠️ Cookie rotation returned {resp.status_code}")
                    self._last_rotate_time = time.time()

            except Exception as e:
                if self.verbose:
                    print(f"[GeminiChat] ⚠️ Cookie rotation error: {e}")
                # Still update time to avoid rapid retry
                self._last_rotate_time = time.time()

    def _maybe_refresh_nonce(self):
        """
        Re-fetch nonce if session is old (nonce can expire after ~30 min).
        """
        session_age = time.time() - self._session_init_time
        if session_age > 1800:  # 30 minutes
            if self.verbose:
                print(f"[GeminiChat] 🔄 Nonce refresh (session {session_age:.0f}s old)...")
            try:
                self._init_session()
            except Exception as e:
                if self.verbose:
                    print(f"[GeminiChat] ⚠️ Nonce refresh failed: {e}")

    def _send_request(self, prompt: str) -> str:
        """Send a single request to Gemini and return raw response text."""
        params = self._build_params()
        payload = self._build_payload(prompt)

        # Add model headers
        model_headers = _get_model_headers(self.model)

        resp = self._session.post(
            GENERATE_URL,
            params=params,
            data=payload,
            headers=model_headers,  # Model selection headers
            timeout=self.timeout,
        )
        self._reqid += 100000
        resp.raise_for_status()

        return resp.text

    def _parse_and_extract(self, raw_text: str) -> str:
        """Parse response and extract text content + conversation metadata."""
        
        # ALWAYS extract conversation metadata (keeps same chat)
        self._extract_conversation_metadata(raw_text)
        
        # Method 1: Use our custom parser
        text = _parse_response(raw_text)
        if text and len(text) >= 10:
            return _clean_text(text)

        # Method 2: Try the old gemini package parser as fallback
        try:
            from gemini.src.model.parser.response_parser import ResponseParser
            parser = ResponseParser(cookies=self.cookies)
            parsed = parser.parse(raw_text)
            if parsed and "candidates" in parsed:
                candidates = parsed["candidates"]
                if candidates:
                    candidate_text = candidates[0].get("text", "")
                    if candidate_text and len(candidate_text) >= 10:
                        return _clean_text(candidate_text)
        except Exception:
            pass

        # Method 3: Brute-force find longest text in response
        # (last resort for when parsers fail)
        all_strings = re.findall(r'"((?:[^"\\]|\\.){50,})"', raw_text)
        if all_strings:
            # Decode escaped strings and find the longest meaningful one
            best = ""
            for s in all_strings:
                try:
                    decoded = s.encode().decode('unicode_escape')
                except Exception:
                    decoded = s.replace('\\n', '\n').replace('\\"', '"')

                # Skip URLs, base64, JSON fragments
                if (not decoded.startswith("http") and
                    not decoded.startswith("data:") and
                    not decoded.startswith("[") and
                    not decoded.startswith("{") and
                    len(decoded) > len(best)):
                    best = decoded

            if best:
                return _clean_text(best)

        raise RuntimeError("Failed to extract text from response")

    def _extract_conversation_metadata(self, raw_text: str):
        """
        Extract conversation_id and response_id from raw response.
        
        Known response structure (confirmed via debug_dump):
            inner[1] = ['c_xxxx', 'r_xxxx']     ← cid, rid
            inner[4][0][0] = 'rc_xxxx'           ← rcid
        """
        lines = raw_text.split("\n")
        
        for line in lines:
            line = line.strip()
            if not line or line.isdigit():
                continue
            
            try:
                outer = json.loads(line)
            except json.JSONDecodeError:
                continue
            
            if not isinstance(outer, list):
                continue
            
            for item in outer:
                if not isinstance(item, list) or len(item) < 3:
                    continue
                
                inner_str = item[2]
                if not isinstance(inner_str, str):
                    continue
                
                try:
                    inner = json.loads(inner_str)
                except json.JSONDecodeError:
                    continue
                
                if not isinstance(inner, list) or len(inner) < 2:
                    continue
                
                # ── Extract cid + rid from inner[1] ──
                try:
                    if isinstance(inner[1], list) and len(inner[1]) >= 2:
                        cid = inner[1][0]
                        rid = inner[1][1]
                        if isinstance(cid, str) and cid.startswith("c_"):
                            self._cid = cid
                        if isinstance(rid, str) and rid.startswith("r_"):
                            self._rid = rid
                except (IndexError, TypeError):
                    pass
                
                # ── Extract rcid from inner[4][0][0] ──
                try:
                    if (len(inner) > 4 and isinstance(inner[4], list) and
                        len(inner[4]) > 0 and isinstance(inner[4][0], list) and
                        len(inner[4][0]) > 0):
                        rcid = inner[4][0][0]
                        if isinstance(rcid, str) and rcid.startswith("rc_"):
                            self._rcid = rcid
                except (IndexError, TypeError):
                    pass
                
                # Found both → done
                if self._cid and self._rid:
                    if self.verbose:
                        print(f"[GeminiChat] 💬 Chat: cid=...{self._cid[-8:]}, rid=...{self._rid[-8:]}")
                    return
    
    def debug_dump(self, prompt: str = "test") -> dict:
        """
        Send a request and dump the raw response structure for debugging.
        Use this in notebook to inspect where conversation IDs are.
        
        Returns dict with raw text and parsed structure.
        """
        raw = self._send_request(prompt)
        
        structures = []
        lines = raw.split("\n")
        for line in lines:
            line = line.strip()
            if not line or line.isdigit():
                continue
            try:
                outer = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(outer, list):
                continue
            
            for item in outer:
                if not isinstance(item, list) or len(item) < 3:
                    continue
                inner_str = item[2]
                if not isinstance(inner_str, str):
                    continue
                try:
                    inner = json.loads(inner_str)
                except json.JSONDecodeError:
                    continue
                if not isinstance(inner, list):
                    continue
                
                # Show top-level structure
                summary = []
                for k in range(min(len(inner), 15)):
                    val = inner[k]
                    if val is None:
                        summary.append(f"[{k}] None")
                    elif isinstance(val, str):
                        summary.append(f"[{k}] str({len(val)}): {val[:60]!r}")
                    elif isinstance(val, list):
                        summary.append(f"[{k}] list(len={len(val)}): {str(val)[:120]}")
                    elif isinstance(val, (int, float, bool)):
                        summary.append(f"[{k}] {val}")
                    else:
                        summary.append(f"[{k}] {type(val).__name__}")
                structures.append(summary)
        
        # Also try metadata extraction
        self._extract_conversation_metadata(raw)
        
        return {
            "cid": self._cid,
            "rid": self._rid,
            "rcid": self._rcid,
            "raw_length": len(raw),
            "structures": structures,
        }

    # ── Public API ───────────────────────────────────────────────────

    def send(self, prompt: str) -> str:
        """
        Send prompt and get text response with retry.
        Auto-recovers from BardErrorInfo by re-initializing session.
        """
        last_error = None

        for attempt in range(1, self.max_retries + 1):
            # Auto-rotate cookies & refresh nonce if needed
            self._maybe_rotate()
            self._maybe_refresh_nonce()
            self._rate_limit()
            self._request_count += 1

            try:
                raw = self._send_request(prompt)
                
                # ── Check for BardErrorInfo BEFORE parsing ──
                if "BardErrorInfo" in raw or "BardError" in raw:
                    raise RuntimeError("BardErrorInfo: Gemini session blocked/rate-limited")
                
                text = self._parse_and_extract(raw)

                if self.verbose:
                    print(f"[GeminiChat] ✅ {len(text)} chars (attempt {attempt})")
                
                # Reset consecutive error counter on success
                self._consecutive_errors = 0
                return text

            except Exception as e:
                last_error = e
                self._consecutive_errors = getattr(self, '_consecutive_errors', 0) + 1
                
                if self.verbose:
                    print(f"[GeminiChat] ⚠️ Attempt {attempt}: {type(e).__name__}: {str(e)[:100]}")

                is_session_error = (
                    "BardError" in str(e) or
                    "401" in str(e) or 
                    "nonce" in str(e).lower() or
                    "blocked" in str(e).lower() or
                    "rate" in str(e).lower()
                )
                
                if is_session_error:
                    # Re-init with backoff
                    backoff = min(30 * attempt, 90)
                    if self.verbose:
                        print(f"[GeminiChat] 🔄 Session error. Re-init in {backoff}s...")
                    time.sleep(backoff)
                    
                    try:
                        self._init_session()
                        self.new_conversation()
                        if self.verbose:
                            print(f"[GeminiChat] ✅ Session re-initialized")
                    except Exception as reinit_err:
                        if self.verbose:
                            print(f"[GeminiChat] ❌ Re-init failed: {reinit_err}")
                else:
                    # Normal retry with exponential backoff
                    if attempt < self.max_retries:
                        backoff = min(2 ** attempt, 30)
                        if self.verbose:
                            print(f"[GeminiChat] 🔄 Retry in {backoff}s...")
                        time.sleep(backoff)

        raise ConnectionError(
            f"All {self.max_retries} attempts failed. Last error: {last_error}"
        )

    def send_json(self, prompt: str, retries: int = None) -> Union[dict, list, None]:
        """
        Send prompt and extract JSON from response.
        Returns None if all attempts fail (instead of raising).
        """
        max_attempts = retries or self.max_retries
        last_text = ""

        for attempt in range(1, max_attempts + 1):
            try:
                text = self.send(prompt)
            except ConnectionError as e:
                # All send retries failed (likely BardError)
                if self.verbose:
                    print(f"[GeminiChat] ❌ send() failed: {str(e)[:100]}")
                return None
            
            last_text = text
            result = extract_json(text)

            if result is not None:
                if self.verbose:
                    print(f"[GeminiChat] ✅ JSON extracted ({type(result).__name__})")
                return result

            if self.verbose:
                print(f"[GeminiChat] ⚠️ No JSON found (attempt {attempt})")

            if attempt < max_attempts:
                prompt = (
                    f"{prompt}\n\n"
                    "CRITICAL: Return ONLY valid JSON inside ```json\\n...\\n``` block. "
                    "No other text outside the block."
                )

        if self.verbose:
            print(f"[GeminiChat] ❌ No JSON after {max_attempts} attempts")
        return None

    # ── Utility ──────────────────────────────────────────────────────

    def set_model(self, model: str):
        """Change model. See MODELS dict for options."""
        if model not in MODELS:
            available = ", ".join(MODELS.keys())
            raise ValueError(f"Unknown model: '{model}'. Available: {available}")
        self.model = model
        if self.verbose:
            info = MODELS[model]
            print(f"[GeminiChat] Model → {model} ({info['name']}, capacity={info['capacity']})")

    def new_conversation(self):
        """Start a fresh conversation (reset chat context)."""
        self._cid = None
        self._rid = None
        self._rcid = None
        if self.verbose:
            print("[GeminiChat] 🆕 New conversation")

    def rotate_cookies(self):
        """Manually rotate cookies now."""
        self._last_rotate_time = 0  # Force rotation
        self._maybe_rotate()

    @property
    def stats(self) -> dict:
        next_rotate = max(0, self.rotate_interval - (time.time() - self._last_rotate_time))
        session_age = time.time() - self._session_init_time
        return {
            "requests": self._request_count,
            "model": self.model,
            "model_name": MODELS.get(self.model, {}).get("name", "?"),
            "has_conversation": self._cid is not None,
            "auto_rotate": self.auto_rotate,
            "next_rotate_in": f"{next_rotate:.0f}s",
            "session_age": f"{session_age:.0f}s",
        }

    @staticmethod
    def available_models() -> dict:
        """List all available model short names."""
        return {k: v["name"] for k, v in MODELS.items()}

    def __repr__(self):
        info = MODELS.get(self.model, {})
        return (f"GeminiChat(model={self.model} [{info.get('name', '?')}], "
                f"requests={self._request_count})")
