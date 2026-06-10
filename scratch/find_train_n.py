import numpy as np

val = -0.005679999999999762
target_sharpe = -0.5796550670490436

for N in range(700, 1300):
    for ddof in [0, 1]:
        returns = np.zeros(N)
        returns[3] = val
        mean = np.mean(returns)
        std = np.std(returns, ddof=ddof)
        sharpe = (mean / std) * np.sqrt(252)
        if abs(sharpe - target_sharpe) < 1e-5:
            print(f"Match found: N={N}, ddof={ddof}, Sharpe={sharpe:.16f}")
