import numpy as np
import scipy.stats as stats

# From SMA10 SAR Simulate stage:
# avg_return = 0.0021042498816947752
# volatility = 0.4718469291480022
# daily_std = volatility / np.sqrt(252) = 0.02972356396956272
# XNO VaR = -0.04678834740337065
# XNO CVaR = -0.07029623040746483

mean = 0.0021042498816947752
volatility = 0.4718469291480022
std = volatility / np.sqrt(252)

# 1. Parametric VaR with standard normal z-score
z_95 = stats.norm.ppf(0.95) # ~1.64485
var_param = mean - z_95 * std
print(f"Parametric VaR: {var_param:.8f} (XNO: -0.04678835)")

# 2. Parametric CVaR
pdf_z = stats.norm.pdf(z_95)
cvar_param = mean - (pdf_z / 0.05) * std
print(f"Parametric CVaR: {cvar_param:.8f} (XNO: -0.07029623)")

# 3. What if z-score is exactly 1.65?
var_165 = mean - 1.65 * std
print(f"Parametric VaR (z=1.65): {var_165:.8f}")

# 4. What if z-score is exactly 1.645?
var_1645 = mean - 1.645 * std
print(f"Parametric VaR (z=1.645): {var_1645:.8f}")
