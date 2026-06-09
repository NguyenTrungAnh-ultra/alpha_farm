"""
XNOQuant Engine — Strategy Base Class + FeatureEngine
=====================================================
Mô phỏng chính xác API SimpleAlgorithm + self.feat.* của XNOQuant.
FeatureEngine wraps TA-Lib: bất kỳ hàm talib nào cũng gọi được qua self.feat.xxx().
"""

import pandas as pd
import numpy as np
import talib


class FeatureEngine:
    """
    Mô phỏng đối tượng self.feat trên nền tảng XNOQuant.
    
    Bất kỳ hàm talib nào đều gọi được qua self.feat.xxx():
        self.feat.sma(close, timeperiod=10)
        self.feat.rsi(close, timeperiod=14)
        self.feat.bbands(close, timeperiod=20, nbdevup=2, nbdevdn=2)
        self.feat.trix(close, timeperiod=9)
        self.feat.aroonosc(high, low, timeperiod=25)
    
    Tự động convert pd.Series → numpy, trả về pd.Series với index gốc.
    """

    def __getattr__(self, name):
        # Try exact match first, then uppercase (talib uses UPPER)
        func = getattr(talib, name, None) or getattr(talib, name.upper(), None)
        if func is None:
            raise AttributeError(f"talib has no function '{name}' or '{name.upper()}'")

        def wrapper(*args, **kwargs):
            # Convert pd.Series args to numpy float64, capture index
            converted = []
            index = None
            for arg in args:
                if isinstance(arg, pd.Series):
                    if index is None:
                        index = arg.index
                    converted.append(arg.values.astype(np.float64))
                else:
                    converted.append(arg)

            result = func(*converted, **kwargs)

            # Wrap result back to pd.Series
            if isinstance(result, np.ndarray):
                return pd.Series(result, index=index) if index is not None else pd.Series(result)
            elif isinstance(result, tuple):
                return tuple(
                    pd.Series(r, index=index) if isinstance(r, np.ndarray) and index is not None else r
                    for r in result
                )
            return result

        return wrapper


class DataProxy:
    """
    Mô phỏng đối tượng self.data trên XNOQuant.
    Cung cấp pv_open, pv_high, pv_low, pv_close, pv_volume.
    """

    def __init__(self, df: pd.DataFrame):
        self._df = df
        self.pv_open = df['Open']
        self.pv_high = df['High']
        self.pv_low = df['Low']
        self.pv_close = df['Close']
        # pv_volume trên XNOQuant là empty array, nhưng mình vẫn cung cấp
        self.pv_volume = df['Volume'] if 'Volume' in df.columns else pd.Series(
            dtype=float, index=df.index
        )

    @property
    def index(self):
        return self._df.index


class SimpleAlgorithm:
    """
    Base class mô phỏng SimpleAlgorithm của XNOQuant.

    Cách sử dụng:
        class CustomStrategy(SimpleAlgorithm):
            def __init__(self, sma_period=10):
                super().__init__()
                self.sma_period = sma_period

            def __algorithm__(self):
                close = self.data.pv_close
                sma = self.feat.sma(close, timeperiod=self.sma_period)
                long_zone = close > sma
                short_zone = close < sma
                flat_zone = ~long_zone & ~short_zone
                self.set_positions(flat_zone, position=0.0)
                self.set_positions(long_zone, position=1.0)
                self.set_positions(short_zone, position=-1.0)
    """

    def __init__(self):
        self.data: DataProxy = None
        self.feat: FeatureEngine = None
        self._positions: pd.Series = None
        self.params: dict = {}  # Subclass nên override

    def _initialize(self, df: pd.DataFrame):
        """Engine gọi hàm này trước khi chạy __algorithm__."""
        self.data = DataProxy(df)
        self.feat = FeatureEngine()
        self._positions = pd.Series(0.0, index=df.index)

    def set_positions(self, mask, position: float):
        """
        Đặt vị thế mục tiêu cho tất cả bar thỏa điều kiện mask.

        Parameters
        ----------
        mask : pd.Series[bool] hoặc np.ndarray[bool]
            Điều kiện True/False cho mỗi bar.
        position : float
            Vị thế mục tiêu. 1.0 = full long, -1.0 = full short, 0.0 = flat.
            Giá trị fractional (0.5, -0.5, v.v.) được hỗ trợ.
        """
        self._positions[mask] = position

    def __algorithm__(self):
        """Override trong subclass để định nghĩa logic chiến lược."""
        raise NotImplementedError("Subclass phải implement __algorithm__()")

    def run_algorithm(self, df: pd.DataFrame) -> pd.Series:
        """
        Chạy thuật toán và trả về chuỗi vị thế.

        Parameters
        ----------
        df : pd.DataFrame
            DataFrame OHLCV với index là Datetime.

        Returns
        -------
        pd.Series
            Chuỗi vị thế mục tiêu cho mỗi bar.
        """
        self._initialize(df)
        self.__algorithm__()
        return self._positions.copy()
