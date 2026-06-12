# Combat Log & Experience (Experience Log)

This is the "brain" storing crucial lessons learned from designing algorithms for the VN30F1M futures and the rules of the XNOQuant system. The AI Model MUST CAREFULLY READ and STRICTLY FOLLOW the lessons below when generating ideas to avoid repeating past mistakes.

## 1. VN30F1M Futures & Data Characteristics
- **Volume = 0 Bars**: The dataset contains many candlesticks with `Volume = 0` or a price range of `High - Low = 0`. ABSOLUTELY AVOID formulas that directly divide by `Volume` or `(High - Low)` as this will cause division-by-zero errors (NaN/Inf) and crash the backtesting system. If you must use them, explicitly suggest adding a small constant (e.g., `Volume + 1e-8`).
- **Noise in short-term timeframes**: The 1m and 3m timeframes are highly noisy. Mean-reversion strategies on the 1m timeframe often have all their profits eaten away by trading fees and slippage due to excessive fakeouts. Prioritize **Filtered Breakouts** or **Lagged Trend-following** on short timeframes.
- **Trend Regimes**: VN futures often experience prolonged narrow sideways (ranging) periods followed by massive breakouts. You must always include a market regime filter (e.g., using ADX, ATR, or Bollinger Bands Squeeze) to prevent the account from being "chopped up" during sideways markets.

## 2. XNOQuant Rules (AST Rules)
- **Optimizer often fails if logic is too strict**: When designing parameters, provide "wide" and easily triggerable ranges. If the Entry conditions are too strict (e.g., RSI < 10 WHILE MACD crosses up AND Price touches the lower Band), the strategy will not open any trades (0 trades). The Optimizer will throw the error `No trials are completed yet`.
- **Formula Structure**: Always define logic clearly, separating:
  - Auxiliary Indicators
  - Long Conditions (Entry Long)
  - Short Conditions (Entry Short)
  - Stop Loss / Take Profit / Exit Logic - Exit conditions must always be processed before Entry conditions.
- **No Virtual Stop Loss**: The model is a static vector array, meaning it does NOT support placing Limit orders or automated Stop Loss orders that trigger exactly at a price level. Trades are only exited at the *close of the candlestick* when the signal is met. Therefore, exit logic should rely on volatility indicators (like ATR trailing, Donchian channels) rather than hard SL price values.

## 3. Pitfalls to Avoid
- Avoid pairing too many lagging indicators together (e.g., EMA + MACD + TRIX) because they are highly correlated (multicollinearity) and will make the signal far too late compared to the market.
- Maximize Vectorized Calculations: Avoid designing complex recursive formulas (e.g., calculating the current value based on the previous trade's value) because the AST environment prohibits row-by-row `for/while` loops. Everything must be calculable as an Array/Series.
