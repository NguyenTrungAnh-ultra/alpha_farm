# strategies/alpha_42.py
from xno_sdk.engine import SimpleAlgorithm

class CustomStrategy(SimpleAlgorithm):
    """
    Alpha #42: (rank((vwap - close)) / rank((vwap + close)))
    Since vwap depends on volume and pv_volume is empty (all zeros) on XNOQuant,
    we proxy vwap using SMA(close, 20).
    We use rolling_rank over a window of 20 periods as a proxy for cross-sectional rank.
    """
    def __algorithm__(self):
        # Parameters
        sma_period = int(20)
        rank_window = int(20)
        long_thresh = float(1.2)
        short_thresh = float(0.8)

        close = self.data.pv_close

        # Proxy VWAP using SMA
        vwap_proxy = self.feat.sma(close, timeperiod=sma_period)

        # Compute rank of (vwap - close) and (vwap + close)
        rank_minus = self.feat.rolling_rank(vwap_proxy - close, window=rank_window)
        rank_plus = self.feat.rolling_rank(vwap_proxy + close, window=rank_window)

        # Avoid division by zero
        rank_plus = rank_plus.where(rank_plus > 0.001, 0.001)

        alpha = rank_minus / rank_plus

        # Signals
        long_zone = alpha > long_thresh
        short_zone = alpha < short_thresh
        flat_zone = ~long_zone & ~short_zone

        self.set_positions(flat_zone, position=0.0)
        self.set_positions(long_zone, position=1.0)
        self.set_positions(short_zone, position=-1.0)
