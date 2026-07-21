import re

with open('core_engine/BacktestEngine.py', 'r', encoding='utf-8') as f:
    code = f.read()

# Just put the Vectorized Rollover logic BEFORE total_fees = np.sum(fee_bar)

rollover_logic = '''
        # --- Vectorized Rollover Penalty (Applied after Margin Call checking) ---
        # Tìm các điểm đáo hạn (Thứ Năm lần thứ 3 của tháng)
        dates = pd.Series(df.index.date)
        weekdays = pd.Series(df.index.weekday)
        is_thursday = weekdays == 3
        thursdays_df = pd.DataFrame({'date': dates, 'is_thursday': is_thursday, 'year': df.index.year, 'month': df.index.month})
        thursdays_only = thursdays_df[thursdays_df['is_thursday']]
        
        expiration_dates = []
        for (y, m), group in thursdays_only.groupby(['year', 'month']):
            unique_dates = group['date'].unique()
            if len(unique_dates) >= 3:
                expiration_dates.append(unique_dates[2])
                
        is_expiration_day = dates.isin(expiration_dates)
        is_rollover_bar = np.zeros_like(close, dtype=bool)
        
        if is_expiration_day.any():
            is_exp_np = is_expiration_day.to_numpy()
            date_diff = np.zeros_like(is_exp_np, dtype=bool)
            date_diff[:-1] = dates.iloc[:-1].values != dates.iloc[1:].values
            date_diff[-1] = True 
            is_rollover_bar = is_exp_np & date_diff
            
        rollover_penalty = (ROLLOVER_PENALTY_POINTS * MULTIPLIER) + (2 * self.fee_per_contract)
        fee_bar[is_rollover_bar] += contracts[is_rollover_bar] * rollover_penalty
        
        # Cập nhật lại net_bar_pnl lần cuối và equity
        net_bar_pnl = pnl_bar - fee_bar
        if has_breach:
            equity = self.initial_capital + np.cumsum(net_bar_pnl)
            equity[first_breach_idx:] = equity_mc_threshold
        else:
            equity = self.initial_capital + np.cumsum(net_bar_pnl)
'''

code = code.replace("        total_fees = np.sum(fee_bar)", rollover_logic + "\n        total_fees = float(np.sum(fee_bar))")

with open('core_engine/BacktestEngine.py', 'w', encoding='utf-8') as f:
    f.write(code)

print("Patched again!")
