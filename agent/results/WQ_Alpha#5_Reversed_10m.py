class CustomStrategy(SimpleAlgorithm):
    def abs(self, x):
        return self.op.where(x > 0, x, -x)
        
    def sign(self, x):
        return self.op.where(x > 0, 1.0, self.op.where(x < 0, -1.0, 0.0))
        
    def log(self, x):
        return np.log(self.op.where(x > 1e-8, x, 1e-8))
        
    def scale(self, x, a=1.0):
        return (x / (self.feat.rolling_sum(self.abs(x), 20) + 1e-8)) * a
        
    def min_(self, x, y):
        return self.op.where(x < y, x, y)
        
    def max_(self, x, y):
        return self.op.where(x > y, x, y)
        
    def signedpower(self, x, p):
        return self.sign(x) * (self.abs(x) ** p)
        
    def SignedPower(self, x, p):
        return self.sign(x) * (self.abs(x) ** p)
        
    def indneutralize(self, x, g):
        return x
        
    def decay_linear(self, x, d):
        d_val = int(round(float(d)))
        if d_val <= 1:
            return x
        total_weight = d_val * (d_val + 1) / 2
        sum_val = x * d_val
        for i in range(1, d_val):
            sum_val = sum_val + self.op.shift(x, i) * (d_val - i)
        return sum_val / total_weight
        
    def where(self, cond, true_val, false_val):
        return self.op.where(cond, true_val, false_val)
        
    def rank(self, x):
        return self.feat.rolling_rank(x, 20)
        
    def ts_rank(self, x, d):
        return self.feat.rolling_rank(x, int(d))
        
    def delay(self, x, d):
        return self.op.shift(x, int(d))
        
    def delta(self, x, d):
        return self.op.diff(x, int(d))
        
    def correlation(self, x, y, d):
        return self.feat.rolling_correlation(x, y, int(d))
        
    def covariance(self, x, y, d):
        return self.feat.rolling_covariance(x, y, int(d))
        
    def ts_min(self, x, d):
        return self.feat.rolling_min(x, int(d))
        
    def ts_max(self, x, d):
        return self.feat.rolling_max(x, int(d))
        
    def ts_argmax(self, x, d):
        return self.feat.rolling_argmax(x, int(d))
        
    def ts_argmin(self, x, d):
        return self.feat.rolling_argmin(x, int(d))
        
    def sum_(self, x, d):
        return self.feat.rolling_sum(x, int(d))
        
    def product(self, x, d):
        return self.feat.rolling_prod(x, int(d))
        
    def stddev(self, x, d):
        return self.feat.rolling_std(x, int(d))

    def __algorithm__(self):
        close = self.data.pv_close
        high = self.data.pv_high
        low = self.data.pv_low
        open_ = self.data.pv_open
        volume = self.data.pv_volume
        
        # Returns
        returns = self.feat.returns(close, 1)
        
        # Cap proxy
        cap = close * 1e6
        
        # VWAP proxy
        vwap = self.feat.rolling_mean(close, 20)
        
        # ADV variables
        adv5 = self.feat.rolling_mean(volume, 5)
        adv10 = self.feat.rolling_mean(volume, 10)
        adv15 = self.feat.rolling_mean(volume, 15)
        adv20 = self.feat.rolling_mean(volume, 20)
        adv30 = self.feat.rolling_mean(volume, 30)
        adv40 = self.feat.rolling_mean(volume, 40)
        adv50 = self.feat.rolling_mean(volume, 50)
        adv60 = self.feat.rolling_mean(volume, 60)
        adv81 = self.feat.rolling_mean(volume, 81)
        adv120 = self.feat.rolling_mean(volume, 120)
        adv150 = self.feat.rolling_mean(volume, 150)
        adv180 = self.feat.rolling_mean(volume, 180)
        
        alpha_val = self.rank(open_ - (self.sum_(vwap, 10) / 10)) * (-1 * self.abs(self.rank(close - vwap)))
            
        # Normalize to position targets in [-1, 1] using rolling min-max
        window = 120
        r_min = self.feat.rolling_min(alpha_val, window)
        r_max = self.feat.rolling_max(alpha_val, window)
        scaled = (alpha_val - r_min) / (r_max - r_min + 1e-8)
        scaled = (scaled - 0.5) * 2.0
        
        # Reversal multiplier
        scaled = scaled * -1.0
        
        # Discretize and scale position
        raw_pos = self.op.where(scaled > 0.5, 1.0, self.op.where(scaled < -0.5, -1.0, 0.0))
        positions = raw_pos * 0.5
        
        positions = self.op.clip(positions, -1.0, 1.0)
        self._positions = self.op.fillna(positions, 0.0)
