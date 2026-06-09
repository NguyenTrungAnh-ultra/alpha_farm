"""
Prompt Templates for Strategy Generation (XNO Engine)
======================================================
Prompts that produce XNOQuant-compatible strategies using SimpleAlgorithm.

Design principles:
    - Self-contained: each prompt includes ALL context needed
    - Structured output: always request JSON/code in specific format
    - Domain-aware: VN30F1M futures specifics baked in
    - Timeframe-adaptive: different guidance per timeframe
    - Diversity-enforcing: explicit list of existing strategies
"""

# ─── Available talib indicators (curated for futures) ────────────────
TALIB_INDICATORS = """
## Available talib Indicators (gọi qua self.feat.xxx())

**Trend**: sma, ema, dema, tema, wma, kama, t3, trima, midpoint, midprice, sar, linearreg, linearreg_slope
**Momentum**: rsi, stoch, stochf, stochrsi, macd, mom, roc, rocp, willr, cci, cmo, mfi, ultosc, trix, adx, adxr, aroon, aroonosc, dx, minus_di, plus_di, apo, ppo, bop
**Volatility**: atr, natr, trange, bbands (upper/middle/lower)
**Volume**: ad, adosc, obv
**Pattern**: CDL functions (cdl_engulfing, cdl_hammer, cdl_doji, v.v.)
**Math**: max, min, stddev, var, linearreg_angle
"""

# ─── Timeframe-specific guidance ────────────────────────────────────
TIMEFRAME_HINTS = {
    "1m": """
**Khung 1 phút** — Scalping cực nhanh:
- Indicator periods: rất ngắn (3-15 bars)
- Trades: nhiều (10-30+/ngày), target nhỏ (0.5-2 points)
- Phù hợp: Momentum bursts, order flow, micro mean-reversion
- Stop loss: rất chặt (1-3 points)
- Chú ý: noise cao, cần filter mạnh (volume, volatility)
""",
    "3m": """
**Khung 3 phút** — Scalping/Intraday nhanh:
- Indicator periods: ngắn-trung (5-20 bars)
- Trades: trung bình (5-15/ngày)
- Phù hợp: Momentum, short-term trend, breakout phiên
- Stop loss: 2-5 points
""",
    "5m": """
**Khung 5 phút** — Intraday chuẩn:
- Indicator periods: trung bình (10-30 bars)
- Trades: 3-8/ngày
- Phù hợp: Trend-following, mean-reversion, breakout consolidation
- Stop loss: 3-8 points
- Đây là khung phổ biến nhất, nhiều chiến lược kinh điển hoạt động tốt
""",
    "10m": """
**Khung 10 phút** — Intraday balanced:
- Indicator periods: trung bình-dài (10-40 bars)
- Trades: 2-5/ngày
- Phù hợp: Trend confirmation, multi-indicator systems
- Stop loss: 5-10 points
""",
    "15m": """
**Khung 15 phút** — Swing intraday:
- Indicator periods: dài hơn (14-50 bars)
- Trades: 1-3/ngày
- Phù hợp: Trend-following chất lượng cao, divergence, pattern recognition
- Stop loss: 8-15 points
- Tín hiệu ít nhưng chất lượng cao hơn
""",
    "30m": """
**Khung 30 phút** — Position intraday:
- Indicator periods: dài (20-60 bars)
- Trades: 0-2/ngày (có thể có ngày không trade)
- Phù hợp: Major trend, range breakout, session-based strategies
- Stop loss: 10-20 points
- Cẩn trọng: ít bars/ngày nên indicator cần đủ lookback
""",
    "1H": """
**Khung 1 giờ** — Position/Swing lớn:
- Indicator periods: dài (10-30 bars ≈ 2-6 ngày)
- Trades: 0-1/ngày (rất ít, có tuần không trade)
- Phù hợp: Major trend following, regime detection
- Stop loss: 15-30 points
- Cần indicator periods phù hợp (1 ngày chỉ có ~5 bars)
""",
}

# ─── Strategy families for diversity ────────────────────────────────
STRATEGY_FAMILIES = [
    "trend-following",      # EMA crossover, ADX filter, SAR, DEMA
    "momentum",             # RSI, MACD, Stochastic, TRIX, ROC
    "mean-reversion",       # Bollinger Bands, RSI extremes, CCI
    "breakout",             # Donchian, Keltner, range breakout, volatility breakout
    "volatility",           # ATR-based, Bollinger squeeze, volatility regime
    "multi-indicator",      # Combining 2-3 uncorrelated indicators
    "pattern-based",        # Candlestick patterns + confirmation
    "channel",              # Linear regression channel, price channel
    "oscillator-divergence",# RSI/MACD divergence, hidden divergence
    "session-based",        # Opening range breakout, session momentum
]

# ─── SimpleAlgorithm interface reference ────────────────────────────
STRATEGY_INTERFACE = """
## SimpleAlgorithm Interface (XNOQuant compatible)

```python
import talib
import numpy as np
import pandas as pd
from backtest.strategy import SimpleAlgorithm

class StrategyNameHere(SimpleAlgorithm):
    def __init__(self, rsi_period=14, ema_period=20):
        super().__init__()
        self.rsi_period = rsi_period
        self.ema_period = ema_period
        self.params = dict(rsi_period=rsi_period, ema_period=ema_period)

    def __algorithm__(self):
        # 1. Lấy dữ liệu giá
        close = self.data.pv_close
        high = self.data.pv_high
        low = self.data.pv_low

        # 2. Tính indicators (vectorized, qua self.feat)
        rsi = self.feat.rsi(close, timeperiod=self.rsi_period)
        ema = self.feat.ema(close, timeperiod=self.ema_period)

        # 3. Tạo điều kiện entry/exit
        long_setup = (close > ema) & (rsi < 30)
        short_setup = (close < ema) & (rsi > 70)
        exit_long = rsi > 50
        exit_short = rsi < 50
        exit_setup = exit_long | exit_short

        # 4. Set positions (EXIT trước, ENTRY sau để override)
        self.set_positions(exit_setup, position=0)
        self.set_positions(long_setup, position=1)
        self.set_positions(short_setup, position=-1)
```

## Important Rules:
1. MUST `import talib`, `import numpy as np`, `import pandas as pd`
2. MUST inherit from `SimpleAlgorithm` (KHÔNG phải BaseStrategy)
3. MUST implement `__algorithm__()` method
4. Indicators gọi qua `self.feat.xxx()` — ví dụ: `self.feat.rsi(close, timeperiod=14)`
5. Dữ liệu giá qua `self.data.pv_close`, `self.data.pv_high`, `self.data.pv_low`, `self.data.pv_open`
6. Entry/Exit dùng `self.set_positions(mask, position=...)` — 1=long, -1=short, 0=flat
7. EXIT conditions PHẢI set TRƯỚC entry conditions (entry sẽ override exit khi cùng lúc)
8. `self.params` dict MUST contain ALL constructor parameters
9. TUYỆT ĐỐI KHÔNG dùng tên class 'MyStrategy' hay 'StrategyNameHere'
10. TUYỆT ĐỐI KHÔNG dùng param1/param2 — phải dùng tên parameter có ý nghĩa
"""

# ─── Complete example strategy ──────────────────────────────────────
EXAMPLE_STRATEGY = """
## Complete Working Example — EMA Crossover + ADX Filter

```python
import talib
import numpy as np
import pandas as pd
from backtest.strategy import SimpleAlgorithm

class EmaCrossADX(SimpleAlgorithm):
    def __init__(self, ema_fast=10, ema_slow=30, adx_period=14, adx_threshold=25.0):
        super().__init__()
        self.ema_fast = ema_fast
        self.ema_slow = ema_slow
        self.adx_period = adx_period
        self.adx_threshold = adx_threshold
        self.params = dict(ema_fast=ema_fast, ema_slow=ema_slow,
                           adx_period=adx_period, adx_threshold=adx_threshold)

    def __algorithm__(self):
        close = self.data.pv_close
        high = self.data.pv_high
        low = self.data.pv_low

        # Tính indicators
        ef = self.feat.ema(close, timeperiod=self.ema_fast)
        es = self.feat.ema(close, timeperiod=self.ema_slow)
        adx = self.feat.adx(high, low, close, timeperiod=self.adx_period)

        # Điều kiện
        trend_strong = adx > self.adx_threshold
        long_setup = trend_strong & (ef > es)
        short_setup = trend_strong & (ef < es)
        exit_setup = adx <= self.adx_threshold

        # Set positions (exit trước, entry sau)
        self.set_positions(exit_setup, position=0)
        self.set_positions(long_setup, position=1)
        self.set_positions(short_setup, position=-1)
```
"""


# ═══════════════════════════════════════════════════════════════════════
# Prompt Builders
# ═══════════════════════════════════════════════════════════════════════

def build_idea_prompt(
    timeframe: str,
    existing_strategies: list[dict],
    round_num: int,
    total_rounds: int,
    tried_names: list[str] = None,
) -> str:
    """
    Build prompt for generating a strategy idea (JSON).
    """
    
    # Format existing strategies list
    if existing_strategies:
        existing_list = "\n".join([
            f"  - [{s['timeframe']}] {s['name']} ({s['family']}): {s.get('description', '')[:80]}"
            for s in existing_strategies
        ])
        existing_section = f"""
## ĐÃ CÓ {len(existing_strategies)} CHIẾN LƯỢC ACCEPTED — KHÔNG ĐƯỢC TRÙNG:
{existing_list}

→ Hãy tạo chiến lược KHÁC BIỆT hoàn toàn: khác indicators, khác logic, khác family.
"""
    else:
        existing_section = "\n## Đây là chiến lược ĐẦU TIÊN — hãy chọn approach mạnh và đa dạng.\n"
    
    # Add ALL tried strategy names
    if tried_names:
        tried_list = ", ".join(sorted(tried_names))
        tried_section = f"""
## TÊN CHIẾN LƯỢC ĐÃ THỬ (KHÔNG ĐƯỢC DÙNG LẠI):
{tried_list}

→ TUYỆT ĐỐI không dùng lại bất kỳ tên nào ở trên. Phải dùng tên MỚI HOÀN TOÀN và indicators/logic KHÁC.
"""
    else:
        tried_section = ""

    # Pick suggested family
    used_families = [s.get('family', '') for s in existing_strategies]
    unused_families = [f for f in STRATEGY_FAMILIES if f not in used_families]
    if unused_families:
        suggested = f"Gợi ý family chưa dùng: **{', '.join(unused_families[:3])}**"
    else:
        suggested = "Tất cả families đã dùng. Hãy tạo BIẾN THỂ sáng tạo khác biệt."

    tf_hint = TIMEFRAME_HINTS.get(timeframe, "")

    return f"""Bạn là một **Quant Researcher** chuyên nghiệp đang thiết kế chiến lược giao dịch cho **hợp đồng tương lai VN30F1M** (phái sinh chỉ số VN30 trên sàn Việt Nam).

## Nhiệm vụ
Thiết kế 1 chiến lược giao dịch intraday cho khung **{timeframe}**.
Đây là vòng {round_num}/{total_rounds}.

{tf_hint}

## Yêu cầu chất lượng
- Chiến lược phải có **logic entry/exit RÕ RÀNG**, không mơ hồ
- Phải dùng **ít nhất 2 indicators** (1 chính + 1 filter/confirmation)
- Phải có **exit logic riêng** (không chỉ đảo tín hiệu)
- Parameters phải có **khoảng tìm kiếm hợp lý** cho optimization
- Phải **KHÁC BIỆT** hoàn toàn với các chiến lược đã có

{existing_section}

{tried_section}

{suggested}

{TALIB_INDICATORS}

## Output Format — PHẢI trả về JSON CHÍNH XÁC như sau:

```json
{{
    "name": "TênChiếnLược",
    "timeframe": "{timeframe}",
    "family": "trend-following|momentum|mean-reversion|breakout|volatility|multi-indicator|pattern-based|channel|oscillator-divergence|session-based",
    "description": "Mô tả ngắn gọn logic chiến lược",
    "indicators": ["RSI", "EMA", "ATR"],
    "entry_long": "Điều kiện cụ thể để vào lệnh LONG",
    "entry_short": "Điều kiện cụ thể để vào lệnh SHORT",
    "exit_logic": "Điều kiện thoát lệnh (áp dụng cho cả long và short)",
    "param_space": {{
        "param_name": {{"type": "int|float", "low": 5, "high": 30, "step": 1}},
        "another_param": {{"type": "float", "low": 0.5, "high": 3.0, "step": 0.1}}
    }}
}}
```

QUAN TRỌNG: Chỉ trả về JSON, không thêm text ngoài block."""


def build_code_prompt(strategy_idea: dict) -> str:
    """Build prompt for generating strategy Python code."""
    idea_json = str(strategy_idea)
    tf = strategy_idea.get("timeframe", "5m")
    
    return f"""Bạn là một **Quant Developer** chuyên viết code Python cho hệ thống backtesting.

## Nhiệm vụ
Viết code Python cho chiến lược sau, tuân thủ CHÍNH XÁC interface SimpleAlgorithm.

## Chiến lược cần implement:
```json
{idea_json}
```

{STRATEGY_INTERFACE}

{EXAMPLE_STRATEGY}

## QUY TẮC BẮT BUỘC (VI PHẠM = THẤT BẠI):
1. Class PHẢI tên CHÍNH XÁC: `{strategy_idea.get('name', 'Strategy')}` — KHÔNG ĐƯỢC dùng MyStrategy, StrategyNameHere, hay bất kỳ tên khác
2. PHẢI kế thừa `SimpleAlgorithm` (KHÔNG phải BaseStrategy)
3. Constructor PHẢI có `self.params = dict(...)` chứa TẤT CẢ parameters VỚI TÊN CÓ Ý NGHĨA
4. Implement `__algorithm__()` — dùng `self.data.pv_close`, `self.feat.xxx()`, `self.set_positions()`
5. EXIT conditions set TRƯỚC, ENTRY conditions set SAU
6. KHÔNG dùng print(), KHÔNG dùng global state
7. Dữ liệu đầu vào có columns: Open, High, Low, Close, Volume (index = Datetime)

## Output: CHỈ trả về code Python trong block ```python ... ```. Không giải thích."""


def build_fix_prompt(code: str, error: str, strategy_name: str) -> str:
    """Build prompt to fix broken strategy code."""
    return f"""Code chiến lược `{strategy_name}` bị lỗi khi chạy:

## Error:
```
{error[:1000]}
```

## Code hiện tại:
```python
{code}
```

{STRATEGY_INTERFACE}

Hãy sửa code để chạy đúng. CHỈ trả về code Python đã sửa trong block ```python ... ```.
Không giải thích, không thêm text."""
