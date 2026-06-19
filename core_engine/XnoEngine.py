import pandas as pd
import numpy as np
import talib
import logging
import os
import re
from .RestrictedSeries import RestrictedSeries

logger = logging.getLogger("core_engine.XnoEngine")

def _load_feature_whitelist():
    whitelist = set()
    current_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(current_dir)
    possible_paths = [
        os.path.join(project_root, "feature.txt"),
        "f:/Projects/alpha_farm/feature.txt"
    ]
    for path in possible_paths:
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    content = f.read()
                matches = re.findall(r"self\.feat\.([a-zA-Z0-9_]+)\s*\(", content)
                for m in matches:
                    whitelist.add(m.lower())
            except Exception:
                pass
            break
            
    if not whitelist:
        whitelist = {
            "adx", "sma", "macd", "roc", "rsi", "obv", "vwap", "rolling_vwap", "bbands",
            "dema", "ema", "wma", "kama", "tema", "t3", "trima", "stddev", "var", "mom",
            "cmo", "cci", "mfi", "willr", "ultosc", "trix", "adxr", "aroon", "aroonosc",
            "dx", "minus_di", "plus_di", "apo", "ppo", "bop", "atr", "natr", "trange",
            "ad", "adosc", "linearreg", "linearreg_slope", "linearreg_angle", "midpoint",
            "midprice", "sar", "stoch", "stochf", "stochrsi", "max", "min", "rolling_mean",
            "rolling_sum", "rolling_std", "rolling_max", "rolling_min", "rolling_median",
            "rolling_quantile", "rolling_mad", "rolling_argmax", "rolling_argmin", "rolling_rank",
            "rolling_percentile_rank", "rolling_covariance", "rolling_correlation", "rolling_zscore",
            "price_z", "volume_z", "zscore", "returns", "log_returns", "donchian_upper",
            "donchian_lower", "hlc3", "ohlc4", "cmf", "minmax", "piercing_pattern", "engulfing_pattern",
            "harami_pattern", "harami_cross_pattern", "hikkake_pattern", "modified_hikkake_pattern",
            "in_neck_pattern", "on_neck_pattern"
        }
    return whitelist


TALIB_NAME_MAPPING = {
    "piercing_pattern": "CDLPIERCING",
    "engulfing_pattern": "CDLENGULFING",
    "harami_pattern": "CDLHARAMI",
    "harami_cross_pattern": "CDLHARAMICROSS",
    "hikkake_pattern": "CDLHIKKAKE",
    "modified_hikkake_pattern": "CDLHIKKAKE",
    "in_neck_pattern": "CDLINNECK",
    "on_neck_pattern": "CDLONNECK",
    "three_white_soldiers": "CDL3WHITESOLDIERS",
    "three_black_crows": "CDL3BLACKCROWS",
    "two_crows": "CDL2CROWS",
    "three_inside_up_down": "CDL3INSIDE",
    "three_outside_up_down": "CDL3OUTSIDE",
    "three_line_strike": "CDL3LINESTRIKE",
    "three_stars_in_south": "CDL3STARSINSOUTH",
    "identical_three_crows": "CDLIDENTICAL3CROWS",
    "upside_gap_two_crows": "CDLUPSGAPTWOCROWS",
}

class FeatureEngine:
    """
    Mock self.feat.*
    Includes all TA-Lib indicators and custom rolling/statistical indicators.
    Automatically unwraps RestrictedSeries, computes using pandas/numpy/talib, 
    and wraps the result back to RestrictedSeries.
    """
    def __init__(self):
        # Tự động bọc tất cả các hàm để chuẩn hóa tham số (window/timeperiod)
        import inspect
        for name in dir(self):
            if not name.startswith('_') and name not in ['_unwrap', '_wrap']:
                attr = getattr(self, name)
                # Dùng __func__ nếu là bound method để lấy hàm gốc
                func_obj = getattr(attr, '__func__', attr)
                if inspect.isfunction(func_obj):
                    # Bọc hàm gốc rồi bind lại thành method
                    wrapped = self._wrap_normalize_params(func_obj)
                    import types
                    setattr(self, name, types.MethodType(wrapped, self))

    def _wrap_normalize_params(self, func):
        import inspect
        try:
            sig = inspect.signature(func)
        except ValueError:
            return func
            
        def wrapper(*args, **kwargs):
            # 1. Chuẩn hóa tên tham số window / timeperiod
            if 'window' in sig.parameters and 'window' not in kwargs:
                for alt in ['timeperiod', 'period']:
                    if alt in kwargs:
                        kwargs['window'] = kwargs.pop(alt)
                        break
            if 'timeperiod' in sig.parameters and 'timeperiod' not in kwargs:
                for alt in ['window', 'period']:
                    if alt in kwargs:
                        kwargs['timeperiod'] = kwargs.pop(alt)
                        break
                        
            # 2. Loại bỏ các tham số lạ (không có trong signature) để tránh lỗi crash do AI tự bịa tham số
            has_var_keyword = any(p.kind == inspect.Parameter.VAR_KEYWORD for p in sig.parameters.values())
            if not has_var_keyword:
                filtered_kwargs = {}
                for k, v in kwargs.items():
                    if k in sig.parameters:
                        filtered_kwargs[k] = v
                kwargs = filtered_kwargs
                
            return func(*args, **kwargs)
        return wrapper

    def _unwrap(self, val):
        if isinstance(val, RestrictedSeries):
            return val._data
        return val

    def _wrap(self, val):
        if isinstance(val, pd.Series):
            return RestrictedSeries(val)
        return val

    # --- Basic custom rolling functions ---
    def rolling_mean(self, series, window=20):
        logger.debug(f"FeatureEngine.rolling_mean called with window={window}")
        s = self._unwrap(series)
        return self._wrap(s.rolling(window).mean())

    def rolling_max(self, series, window=20):
        logger.debug(f"FeatureEngine.rolling_max called with window={window}")
        s = self._unwrap(series)
        return self._wrap(s.rolling(window).max())

    def rolling_min(self, series, window=20):
        logger.debug(f"FeatureEngine.rolling_min called with window={window}")
        s = self._unwrap(series)
        return self._wrap(s.rolling(window).min())

    def rolling_std(self, series, window=20):
        logger.debug(f"FeatureEngine.rolling_std called with window={window}")
        s = self._unwrap(series)
        return self._wrap(s.rolling(window).std())

    def rolling_sum(self, series, window=20):
        logger.debug(f"FeatureEngine.rolling_sum called with window={window}")
        s = self._unwrap(series)
        return self._wrap(s.rolling(window).sum())

    def rolling_prod(self, series, window=20):
        logger.debug(f"FeatureEngine.rolling_prod called with window={window}")
        s = self._unwrap(series)
        # Using rolling apply with np.prod
        return self._wrap(s.rolling(window).apply(np.prod, raw=True))

    def rolling_rank(self, series, window=20):
        logger.debug(f"FeatureEngine.rolling_rank called with window={window}")
        s = self._unwrap(series)
        from numpy.lib.stride_tricks import sliding_window_view
        vals = s.values
        n = len(vals)
        out = np.empty(n)
        out[:] = np.nan
        if n >= window:
            windows = sliding_window_view(vals, window)
            last_elements = windows[:, -1][:, np.newaxis]
            nan_mask = np.isnan(windows)
            valid_counts = np.sum(~nan_mask, axis=1)
            filled_windows = np.where(nan_mask, np.inf, windows)
            ranks = np.sum(filled_windows <= last_elements, axis=1) / np.maximum(valid_counts, 1)
            ranks = np.where(np.isnan(windows[:, -1]), np.nan, ranks)
            out[window - 1:] = ranks
        return self._wrap(pd.Series(out, index=s.index))

    def rolling_percentile_rank(self, series, window=20, method='average'):
        logger.debug(f"FeatureEngine.rolling_percentile_rank called with window={window}")
        if method == 'average':
            return self.rolling_rank(series, window)
        s = self._unwrap(series)
        r = s.rolling(window).apply(lambda x: pd.Series(x).rank(pct=True, method=method).iloc[-1], raw=True)
        return self._wrap(r)

    def rolling_median(self, series, window=20):
        logger.debug(f"FeatureEngine.rolling_median called with window={window}")
        s = self._unwrap(series)
        return self._wrap(s.rolling(window).median())

    def rolling_quantile(self, series, window=20, q=0.5):
        logger.debug(f"FeatureEngine.rolling_quantile called with window={window}, q={q}")
        s = self._unwrap(series)
        return self._wrap(s.rolling(window).quantile(q))

    def rolling_correlation(self, series1, series2, window=20):
        logger.debug(f"FeatureEngine.rolling_correlation called with window={window}")
        s1 = self._unwrap(series1)
        s2 = self._unwrap(series2)
        return self._wrap(s1.rolling(window).corr(s2))

    def rolling_covariance(self, series1, series2, window=20):
        logger.debug(f"FeatureEngine.rolling_covariance called with window={window}")
        s1 = self._unwrap(series1)
        s2 = self._unwrap(series2)
        return self._wrap(s1.rolling(window).cov(s2))

    def rolling_zscore(self, series, window=20):
        logger.debug(f"FeatureEngine.rolling_zscore called with window={window}")
        s = self._unwrap(series)
        mean = s.rolling(window).mean()
        std = s.rolling(window).std()
        return self._wrap((s - mean) / std)

    def rolling_mad(self, series, window=20):
        logger.debug(f"FeatureEngine.rolling_mad called with window={window}")
        s = self._unwrap(series)
        def mad(x):
            med = np.median(x)
            return np.median(np.abs(x - med))
        return self._wrap(s.rolling(window).apply(mad, raw=True))

    def rolling_argmax(self, series, window=20):
        logger.debug(f"FeatureEngine.rolling_argmax called with window={window}")
        s = self._unwrap(series)
        # Returns bars since the most recent maximum: 0 = current row
        r = s.rolling(window).apply(lambda x: len(x) - 1 - np.argmax(x), raw=True)
        return self._wrap(r)

    def rolling_argmin(self, series, window=20):
        logger.debug(f"FeatureEngine.rolling_argmin called with window={window}")
        s = self._unwrap(series)
        r = s.rolling(window).apply(lambda x: len(x) - 1 - np.argmin(x), raw=True)
        return self._wrap(r)

    # --- Custom statistical & custom price indicators ---
    def zscore(self, series, timeperiod=30):
        logger.debug(f"FeatureEngine.zscore called with timeperiod={timeperiod}")
        return self.rolling_zscore(series, window=timeperiod)

    def price_z(self, close, timeperiod=30):
        logger.debug(f"FeatureEngine.price_z called with timeperiod={timeperiod}")
        return self.zscore(close, timeperiod=timeperiod)

    def volume_z(self, volume, timeperiod=30):
        logger.debug(f"FeatureEngine.volume_z called with timeperiod={timeperiod}")
        return self.zscore(volume, timeperiod=timeperiod)

    def returns(self, series, periods=1):
        logger.debug(f"FeatureEngine.returns called with periods={periods}")
        s = self._unwrap(series)
        return self._wrap(s.pct_change(periods))

    def log_returns(self, series, periods=1):
        logger.debug(f"FeatureEngine.log_returns called with periods={periods}")
        s = self._unwrap(series)
        return self._wrap(np.log(s / s.shift(periods)))

    def donchian_upper(self, high, timeperiod=30):
        logger.debug(f"FeatureEngine.donchian_upper called with timeperiod={timeperiod}")
        return self.rolling_max(high, window=timeperiod)

    def donchian_lower(self, low, timeperiod=30):
        logger.debug(f"FeatureEngine.donchian_lower called with timeperiod={timeperiod}")
        return self.rolling_min(low, window=timeperiod)

    def hlc3(self, high, low, close):
        logger.debug("FeatureEngine.hlc3 called")
        h = self._unwrap(high)
        l = self._unwrap(low)
        c = self._unwrap(close)
        return self._wrap((h + l + c) / 3.0)

    def ohlc4(self, open_, high, low, close):
        logger.debug("FeatureEngine.ohlc4 called")
        o = self._unwrap(open_)
        h = self._unwrap(high)
        l = self._unwrap(low)
        c = self._unwrap(close)
        return self._wrap((o + h + l + c) / 4.0)

    # --- Volume Weighted functions ---
    def vwap(self, high, low, close, volume):
        logger.debug("FeatureEngine.vwap called")
        h = self._unwrap(high)
        l = self._unwrap(low)
        c = self._unwrap(close)
        v = self._unwrap(volume)
        typical = (h + l + c) / 3.0
        return self._wrap((typical * v).cumsum() / v.cumsum())

    def rolling_vwap(self, high, low, close, volume, window=20):
        logger.debug(f"FeatureEngine.rolling_vwap called with window={window}")
        h = self._unwrap(high)
        l = self._unwrap(low)
        c = self._unwrap(close)
        v = self._unwrap(volume)
        typical = (h + l + c) / 3.0
        num = (typical * v).rolling(window).sum()
        den = v.rolling(window).sum()
        return self._wrap(num / den)

    def cmf(self, high, low, close, volume, timeperiod=20):
        logger.debug(f"FeatureEngine.cmf called with timeperiod={timeperiod}")
        h = self._unwrap(high)
        l = self._unwrap(low)
        c = self._unwrap(close)
        v = self._unwrap(volume)
        ad = ((c - l) - (h - c)) / (h - l).replace(0, np.nan) * v
        ad = ad.fillna(0.0)
        return self._wrap(ad.rolling(timeperiod).sum() / v.rolling(timeperiod).sum())

    # --- Fallback/Aliases for TA-Lib compatibility ---
    def stddev(self, series, period=14, timeperiod=None):
        p = timeperiod if timeperiod is not None else period
        return self.rolling_std(series, window=p)

    def minmax(self, series, timeperiod=30):
        return self.rolling_min(series, window=timeperiod), self.rolling_max(series, window=timeperiod)

    def __getattr__(self, name):
        if name.startswith('_'):
            raise AttributeError(f"'FeatureEngine' object has no attribute '{name}'")
            
        # Clean the name to lower for comparison
        lower_name = name.lower()
        if "_whitelist" not in self.__dict__:
            self._whitelist = _load_feature_whitelist()
            
        if lower_name not in self._whitelist:
            logger.error(f"XNO Sandbox Error: self.feat has no method '{name}' (not in feature.txt whitelist)")
            raise AttributeError(f"strategy verification failed: 'self.feat' has no method '{name}'.")

        # Resolve to standard TA-Lib name if it is a mapped pattern
        talib_name = TALIB_NAME_MAPPING.get(lower_name, name)

        # Dynamically load standard TA-Lib functions
        func = getattr(talib, talib_name, None) or getattr(talib, talib_name.upper(), None)
        if func is None:
            logger.error(f"talib has no function '{talib_name}' or '{talib_name.upper()}'")
            raise AttributeError(f"talib has no function '{talib_name}' or '{talib_name.upper()}'")


        def wrapper(*args, **kwargs):
            logger.debug(f"FeatureEngine.{name} called")
            converted = []
            index = None
            for arg in args:
                if isinstance(arg, RestrictedSeries):
                    if index is None:
                        index = arg._data.index
                    converted.append(arg._data.values.astype(np.float64))
                elif isinstance(arg, pd.Series):
                    if index is None:
                        index = arg.index
                    converted.append(arg.values.astype(np.float64))
                else:
                    converted.append(arg)

            # Chuẩn hóa tên tham số của TA-Lib (bỏ gạch dưới, đổi period -> timeperiod, map stoch/macd)
            normalized_kwargs = {}
            for k, v in kwargs.items():
                k_norm = k.replace('_', '').lower()
                if k_norm == 'period':
                    k_norm = 'timeperiod'
                
                # Ánh xạ riêng cho stoch và macd
                if talib_name.lower() in ['stoch', 'stochf'] and k_norm == 'timeperiod':
                    k_norm = 'fastk_period'
                if talib_name.lower() in ['macd', 'macdext', 'ppo', 'apo'] and k_norm == 'timeperiod':
                    k_norm = 'fastperiod'
                
                normalized_kwargs[k_norm] = v

            try:
                result = func(*converted, **normalized_kwargs)
            except TypeError as e:
                # Lỗi tham số (unexpected keyword argument hoặc sai số lượng positional argument)
                # Thử tự động thích ứng đối số
                logger.warning(f"TA-Lib call failed: {e}. Retrying argument adaptation...")
                try:
                    # 1. Thử rút gọn chỉ lấy 1 đối số cuối cùng (thường là close)
                    try:
                        result = func(converted[-1], **normalized_kwargs)
                    except:
                        # 2. Thử lấy 2 đối số cuối cùng (thường là close, volume cho OBV)
                        if len(converted) >= 2:
                            try:
                                result = func(converted[-2], converted[-1], **normalized_kwargs)
                            except:
                                pass
                        # 3. Thử chạy positional thuần túy không có kwargs
                        result = func(*converted)
                except Exception as e2:
                    logger.error(f"Adaptation failed. Original error: {e}")
                    raise e

            if isinstance(result, np.ndarray):
                s = pd.Series(result, index=index) if index is not None else pd.Series(result)
                return RestrictedSeries(s)
            elif isinstance(result, tuple):
                return tuple(
                    RestrictedSeries(pd.Series(r, index=index) if index is not None else pd.Series(r))
                    if isinstance(r, np.ndarray) else r
                    for r in result
                )
            return result

        return wrapper

class OperatorEngine:
    """
    Mock self.op.*
    Includes all 30 custom operators supported by XNOQuant.
    """
    def _unwrap(self, val):
        if isinstance(val, RestrictedSeries):
            return val._data
        return val

    def _wrap(self, val):
        if isinstance(val, pd.Series):
            return RestrictedSeries(val)
        return val

    # 1. crossed
    def crossed(self, series1, series2) -> RestrictedSeries:
        logger.debug("OperatorEngine.crossed called")
        s1 = self._unwrap(series1)
        s2 = self._unwrap(series2)
        c = ((s1.shift(1) < s2.shift(1)) & (s1 > s2)) | ((s1.shift(1) > s2.shift(1)) & (s1 < s2))
        return self._wrap(c)

    # 2. crossed_above
    def crossed_above(self, series1, series2) -> RestrictedSeries:
        logger.debug("OperatorEngine.crossed_above called")
        s1 = self._unwrap(series1)
        s2 = self._unwrap(series2)
        c = (s1.shift(1) <= s2.shift(1)) & (s1 > s2)
        return self._wrap(c)

    # 3. crossed_below
    def crossed_below(self, series1, series2) -> RestrictedSeries:
        logger.debug("OperatorEngine.crossed_below called")
        s1 = self._unwrap(series1)
        s2 = self._unwrap(series2)
        c = (s1.shift(1) >= s2.shift(1)) & (s1 < s2)
        return self._wrap(c)

    # 4. current
    def current(self, series) -> RestrictedSeries:
        logger.debug("OperatorEngine.current called")
        return series

    # 5. previous
    def previous(self, series, periods=1) -> RestrictedSeries:
        logger.debug(f"OperatorEngine.previous called with periods={periods}")
        s = self._unwrap(series)
        return self._wrap(s.shift(periods))

    # 6. shift
    def shift(self, series, periods=1) -> RestrictedSeries:
        logger.debug(f"OperatorEngine.shift called with periods={periods}")
        if periods <= 0:
            raise ValueError("XNO Operator Error: shift period must be > 0 for causal safety.")
        s = self._unwrap(series)
        return self._wrap(s.shift(periods))

    # 7. diff
    def diff(self, series, periods=1) -> RestrictedSeries:
        logger.debug(f"OperatorEngine.diff called with periods={periods}")
        if periods <= 0:
            raise ValueError("XNO Operator Error: diff period must be > 0 for causal safety.")
        s = self._unwrap(series)
        return self._wrap(s.diff(periods))

    # 8. pct_change
    def pct_change(self, series, periods=1) -> RestrictedSeries:
        logger.debug(f"OperatorEngine.pct_change called with periods={periods}")
        if periods <= 0:
            raise ValueError("XNO Operator Error: pct_change period must be > 0.")
        s = self._unwrap(series)
        return self._wrap(s.pct_change(periods))

    # 9. rising
    def rising(self, series, periods=1) -> RestrictedSeries:
        logger.debug(f"OperatorEngine.rising called with periods={periods}")
        s = self._unwrap(series)
        return self._wrap(s > s.shift(periods))

    # 10. falling
    def falling(self, series, periods=1) -> RestrictedSeries:
        logger.debug(f"OperatorEngine.falling called with periods={periods}")
        s = self._unwrap(series)
        return self._wrap(s < s.shift(periods))

    # 11. fillna
    def fillna(self, series, value=None, method=None) -> RestrictedSeries:
        logger.debug(f"OperatorEngine.fillna called (value={value}, method={method})")
        s = self._unwrap(series)
        if method == 'ffill':
            return self._wrap(s.ffill())
        elif method == 'bfill':
            raise ValueError("XNO Operator Error: Backfill (bfill) is rejected for causal safety.")
        return self._wrap(s.fillna(value))

    # 12. ffill
    def ffill(self, series) -> RestrictedSeries:
        logger.debug("OperatorEngine.ffill called")
        s = self._unwrap(series)
        return self._wrap(s.ffill())

    # 13. abs
    def abs(self, series) -> RestrictedSeries:
        logger.debug("OperatorEngine.abs called")
        s = self._unwrap(series)
        return self._wrap(abs(s))

    # 14. clip
    def clip(self, series, lower=None, upper=None) -> RestrictedSeries:
        logger.debug(f"OperatorEngine.clip called (lower={lower}, upper={upper})")
        s = self._unwrap(series)
        return self._wrap(s.clip(lower, upper))

    # 15. isna
    def isna(self, series) -> RestrictedSeries:
        logger.debug("OperatorEngine.isna called")
        s = self._unwrap(series)
        return self._wrap(s.isna())

    # 16. notna
    def notna(self, series) -> RestrictedSeries:
        logger.debug("OperatorEngine.notna called")
        s = self._unwrap(series)
        return self._wrap(s.notna())

    # 17. isfinite
    def isfinite(self, series) -> RestrictedSeries:
        logger.debug("OperatorEngine.isfinite called")
        s = self._unwrap(series)
        # Rejects inf, -inf, and NaN
        finite = ~s.isna() & ~s.isin([np.inf, -np.inf])
        return self._wrap(finite)

    # 18. zero_ifna
    def zero_ifna(self, series) -> RestrictedSeries:
        logger.debug("OperatorEngine.zero_ifna called")
        s = self._unwrap(series)
        return self._wrap(s.fillna(0.0))

    # 19. sign
    def sign(self, series) -> RestrictedSeries:
        logger.debug("OperatorEngine.sign called")
        s = self._unwrap(series)
        return self._wrap(np.sign(s))

    # 20. replace
    def replace(self, series, to_replace, value) -> RestrictedSeries:
        logger.debug(f"OperatorEngine.replace called (to_replace={to_replace}, value={value})")
        s = self._unwrap(series)
        return self._wrap(s.replace(to_replace, value))

    # 21. between
    def between(self, series, lower, upper) -> RestrictedSeries:
        logger.debug(f"OperatorEngine.between called (lower={lower}, upper={upper})")
        s = self._unwrap(series)
        low = self._unwrap(lower)
        up = self._unwrap(upper)
        return self._wrap((s >= low) & (s <= up))

    # 22. where
    def where(self, condition, x, y) -> RestrictedSeries:
        logger.debug("OperatorEngine.where called")
        cond = self._unwrap(condition)
        val_x = self._unwrap(x)
        val_y = self._unwrap(y)
        res = pd.Series(np.where(cond, val_x, val_y), index=cond.index)
        return self._wrap(res)

    # 23. value_when
    def value_when(self, condition, values, occurrence=0) -> RestrictedSeries:
        logger.debug(f"OperatorEngine.value_when called (occurrence={occurrence})")
        cond = self._unwrap(condition)
        vals = self._unwrap(values)
        
        valid_vals = vals.where(cond)
        if occurrence == 0:
            return self._wrap(valid_vals.ffill())
        else:
            # Shift the non-null values causally
            # Dropna returns only the rows that met the condition, shift it, 
            # and reindex it back to original indexes, then ffill
            shifted = valid_vals.dropna().shift(occurrence).reindex(vals.index).ffill()
            return self._wrap(shifted)

    # 24. bars_since
    def bars_since(self, condition) -> RestrictedSeries:
        logger.debug("OperatorEngine.bars_since called")
        cond = self._unwrap(condition).fillna(False).astype(bool)
        
        # Causal running count reset by the latest True row
        cumsum = cond.cumsum()
        cumcount = cond.groupby(cumsum).cumcount()
        
        # If the condition has never been True, return NaN
        has_occurred = cumsum > 0
        res = cumcount.where(has_occurred, np.nan)
        return self._wrap(res)

    # 25. hold_for
    def hold_for(self, condition, periods) -> RestrictedSeries:
        logger.debug(f"OperatorEngine.hold_for called with periods={periods}")
        bars = self._unwrap(self.bars_since(condition))
        return self._wrap(bars < periods)

    # 26. crossed_above_value
    def crossed_above_value(self, series, value: float) -> RestrictedSeries:
        logger.debug(f"OperatorEngine.crossed_above_value called with value={value}")
        s = self._unwrap(series)
        c = (s.shift(1) <= value) & (s > value)
        return self._wrap(c)

    # 27. crossed_below_value
    def crossed_below_value(self, series, value: float) -> RestrictedSeries:
        logger.debug(f"OperatorEngine.crossed_below_value called with value={value}")
        s = self._unwrap(series)
        c = (s.shift(1) >= value) & (s < value)
        return self._wrap(c)

    # 28. and_
    def and_(self, *conditions) -> RestrictedSeries:
        logger.debug(f"OperatorEngine.and_ called with {len(conditions)} conditions")
        res = self._unwrap(conditions[0])
        for c in conditions[1:]:
            res = res & self._unwrap(c)
        return self._wrap(res)

    # 29. or_
    def or_(self, *conditions) -> RestrictedSeries:
        logger.debug(f"OperatorEngine.or_ called with {len(conditions)} conditions")
        res = self._unwrap(conditions[0])
        for c in conditions[1:]:
            res = res | self._unwrap(c)
        return self._wrap(res)

    # 30. not_
    def not_(self, series) -> RestrictedSeries:
        logger.debug("OperatorEngine.not_ called")
        s = self._unwrap(series)
        return self._wrap(~s)

class DataProxy:
    """Mock self.data.*"""
    def __init__(self, df: pd.DataFrame):
        logger.debug("Initializing DataProxy. Mocking pv_volume to all zeros.")
        self._df = df
        self.pv_open = RestrictedSeries(df['Open'])
        self.pv_high = RestrictedSeries(df['High'])
        self.pv_low = RestrictedSeries(df['Low'])
        self.pv_close = RestrictedSeries(df['Close'])
        
        # Fetch real volume data, filling NaNs with 0.0 for safety
        self.pv_volume = RestrictedSeries(df['Volume'].fillna(0.0))

    @property
    def index(self):
        return self._df.index

class SimpleAlgorithm:
    """
    Mock SimpleAlgorithm for XNOQuant Sandbox.
    """
    def __init__(self, **kwargs):
        logger.debug(f"Initializing SimpleAlgorithm with params: {kwargs}")
        self.data: DataProxy = None
        self.feat: FeatureEngine = None
        self.op: OperatorEngine = None
        self._positions: pd.Series = None
        self.params: dict = kwargs.copy()
        
        # In Sandbox, __init__ shouldn't be overridden except to define kwargs params.
        # We auto-assign kwargs to self.
        for k, v in kwargs.items():
            setattr(self, k, v)

    def _initialize(self, df: pd.DataFrame):
        logger.debug("Setting up strategy environment (DataProxy, FeatureEngine, OperatorEngine)")
        self.data = DataProxy(df)
        self.feat = FeatureEngine()
        self.op = OperatorEngine()
        self._positions = pd.Series(0.0, index=df.index)

    def set_positions(self, mask, position: float):
        logger.debug(f"set_positions called with target position: {position}")
        if isinstance(mask, RestrictedSeries):
            mask = mask._data
        self._positions.loc[mask.fillna(False).astype(bool)] = position

    def __algorithm__(self):
        raise NotImplementedError("Subclass must implement __algorithm__()")

    def _validate_sandbox_constraints(self):
        import inspect
        import ast
        import dis
        import sys
        
        cls = self.__class__
        errors = []
        
        # 1. No __init__ check (in subclass)
        if '__init__' in cls.__dict__:
            errors.append("Forbidden '__init__' constructor: Do not define __init__ inside CustomStrategy. Define params in __algorithm__ instead.")

        # 2. No helper functions check via dict lookup
        allowed_methods = {'__algorithm__', 'run_algorithm', '_initialize', 'set_positions', '_validate_sandbox_constraints'}
        for name, attr in cls.__dict__.items():
            if callable(attr) and not name.startswith('_'):
                if name not in allowed_methods:
                    errors.append(f"Forbidden helper function '{name}': Only '__algorithm__' is allowed inside CustomStrategy class.")

        # 3. AST checks on the source code
        source_code = getattr(cls, '_emulator_source_code', None)
        
        if source_code is None:
            # Try to get the entire module source
            try:
                if cls.__module__ in sys.modules:
                    module = sys.modules[cls.__module__]
                    if not module.__name__.startswith('xno_sdk') and not module.__name__.startswith('backtest') and not module.__name__ == '__main__':
                        source_code = inspect.getsource(module)
            except Exception:
                pass
                
            # Fall back to class source if module source is not available
            if source_code is None:
                try:
                    source_code = inspect.getsource(cls)
                except Exception:
                    pass

        if source_code is not None:
            try:
                tree = ast.parse(source_code)
                
                class XNOSandboxASTValidator(ast.NodeVisitor):
                    def __init__(self):
                        self.in_class = False

                    def visit_ClassDef(self, node):
                        old_in_class = self.in_class
                        self.in_class = True
                        self.generic_visit(node)
                        self.in_class = old_in_class

                    def visit_FunctionDef(self, node):
                        if self.in_class:
                            if node.name not in allowed_methods:
                                errors.append(f"Line {node.lineno}: Forbidden function definition '{node.name}' inside CustomStrategy.")
                        else:
                            errors.append(f"Line {node.lineno}: Forbidden function definition '{node.name}' outside CustomStrategy.")
                        self.generic_visit(node)

                    def visit_Name(self, node):
                        if node.id == 'open':
                            errors.append(f"Line {node.lineno}: use of forbidden name 'open' is not allowed in XNO strategy sandbox.")
                        self.generic_visit(node)

                    def visit_Attribute(self, node):
                        if node.attr == 'open':
                            errors.append(f"Line {node.lineno}: use of attribute name 'open' is not allowed in XNO strategy sandbox.")
                        self.generic_visit(node)

                    def visit_Call(self, node):
                        if isinstance(node.func, ast.Name) and node.func.id == 'getattr':
                            errors.append(f"Line {node.lineno}: call to 'getattr' is not allowed in XNO strategy sandbox.")
                        self.generic_visit(node)
                        
                    def visit_Import(self, node):
                        errors.append(f"Line {node.lineno}: import statement is not allowed in XNO strategy sandbox.")
                        self.generic_visit(node)
                        
                    def visit_ImportFrom(self, node):
                        errors.append(f"Line {node.lineno}: import statement is not allowed in XNO strategy sandbox.")
                        self.generic_visit(node)

                ast_validator = XNOSandboxASTValidator()
                ast_validator.visit(tree)
            except Exception:
                pass

        # 4. Fallback bytecode check for safety (especially if source is not available)
        for name, attr in cls.__dict__.items():
            if callable(attr) and hasattr(attr, '__code__'):
                code_obj = attr.__code__
                
                # Check co_names (global names, attributes, function calls)
                if 'getattr' in code_obj.co_names:
                    errors.append(f"Forbidden call/reference to 'getattr' detected in method '{name}'.")
                if 'open' in code_obj.co_names:
                    errors.append(f"Forbidden name 'open' detected in method '{name}'.")
                    
                # Check co_varnames (local variables)
                if 'open' in code_obj.co_varnames:
                    errors.append(f"Forbidden local variable assignment to 'open' detected in method '{name}'.")
                    
                # Check for import instructions in bytecode
                try:
                    for instr in dis.get_instructions(attr):
                        if 'IMPORT' in instr.opname:
                            errors.append(f"Forbidden import instruction '{instr.opname} {instr.argval}' detected in method '{name}'.")
                except Exception:
                    pass

        if errors:
            raise AttributeError("XNO Sandbox Error:\n" + "\n".join(errors))

    def run_algorithm(self, df: pd.DataFrame) -> pd.Series:
        logger.debug("Running custom algorithm in XNO SDK Mock Environment")
        self._validate_sandbox_constraints()
        self._initialize(df)
        self.__algorithm__()
        logger.debug("Custom algorithm finished successfully")
        return self._positions.copy()
