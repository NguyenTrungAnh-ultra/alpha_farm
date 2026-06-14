# Parameter Analysis for Successfully Submitted Alphas

Total strategies: 99

## Summary Statistics

- **Minimum parameters:** 0
- **Maximum parameters:** 9
- **Average parameters:** 5.43

## Frequency Distribution

| Number of Parameters | Count of Strategies |
|---|---|
| 0 | 1 |
| 3 | 5 |
| 4 | 15 |
| 5 | 31 |
| 6 | 29 |
| 7 | 11 |
| 8 | 6 |
| 9 | 1 |


## Strategies by Parameter Count

### 0 Parameters (1 strategies)

- **WQ_Alpha5_10m.py**: None

### 3 Parameters (5 strategies)

- **Donchian_SAR_Breakout_Confluence_30m.py**: donchian_period, sar_acceleration, sar_maximum
- **Micro_TrueRange_Volume_Burst_Breakout_1m.py**: param_b, param_a, param_c
- **T3_True_Range_Asymmetric_Reversion_5m.py**: dx_min, deviation_mult, t3_period
- **Triple_Moving_Average_ADX_Regime_Position_30m.py**: adx_min, tema_period, exit_period
- **Volatility_Asymmetric_Donchian_Breakout_10m.py**: exit_period, breakout_period, expansion_factor

### 4 Parameters (15 strategies)

- **APO_SAR_Confluence_Trend_15m.py**: max_acc, slow_apo, acc, fast_apo
- **APO_Zero_Cross_ADX_Filter_15m.py**: apo_fast, atr_mult, apo_slow, adx_threshold
- **DX_T3_Trend_Strength_10m.py**: strength_threshold, t3_period, dx_period, exit_threshold
- **Kama_Trend_Breakout_ADXR_Envelope_15m.py**: kama_period, adxr_threshold, exit_period, channel_period
- **Kama_Trend_Plus_DI_Breakout_5m.py**: kama_period, adx_min, exit_mult, exit_period
- **Micro_Aroon_Oscillator_Alpha_Scalper_1m.py**: expansion_mult, aroon_trigger, exit_period, aroon_period
- **Micro_Chande_Absolute_Range_Scalper_1m.py**: vol_factor, exit_period, cmo_period, cmo_trigger
- **Micro_MACD_Slope_Volatility_Enforcer_1m.py**: slope_trigger, slope_period, exit_period, expansion_factor
- **Micro_Momentum_Volume_Burst_1m.py**: vol_threshold, exit_period, wma_period, willr_period
- **Micro_TRIX_Asymmetric_Scalper_1m.py**: exit_period, trix_period, noise_floor, trix_trigger
- **Midpoint_SAR_LinearSlope_Trail_5m.py**: midpoint_period, slope_period, sar_maximum, sar_acceleration
- **NATR_LinearSlope_Trend_Activator_30m.py**: vol_enter_threshold, period_natr, period_slope, vol_exit_threshold
- **Session_Chande_Volatility_Breakout_30m.py**: cmo_threshold, range_period, cmo_period, exit_period
- **Session_Williams_R_Volatility_Squeeze_15m.py**: trima_period, exit_period, squeeze_factor, willr_period
- **WilliamsR_NATR_Midprice_Breakout_5m.py**: band_multiplier, atr_period, willr_period, min_natr

### 5 Parameters (31 strategies)

- **Chande_Volatility_Index_Structural_Regime_30m.py**: cmo_period, tema_period, exit_period, cmo_threshold, expansion_mult
- **DEMA_Structural_Breakout_CCI_Filter_5m.py**: adx_min, cci_bound, dema_period, cci_period, channel_period
- **DI_Cross_ADX_NATR_Trend_30m.py**: di_period, natr_min, adx_period, adx_threshold, natr_period
- **Dual_Channel_ADX_Breakout_15m.py**: bb_period, kc_mult, bb_std, adx_period, adx_threshold
- **Harami_ATR_Trend_Confirmation_15m.py**: exit_atr_mult, sma_atr_period, atr_period, ema_period, atr_min_mult
- **Hull_Linear_Acceleration_Trend_5m.py**: slope_trigger, exit_period, slope_period, noise_threshold, wma_period
- **Kama_Linear_Angle_Regime_Position_30m.py**: kama_period, exit_period, angle_threshold, exit_mult, angle_period
- **LinearSlope_BBWidth_Momentum_Burst_5m.py**: threshold_mult, slope_period, bb_period, exit_lookback, trail_atr_mult
- **Linear_Angle_Plus_DI_Swing_Confirmation_15m.py**: exit_period, di_period, natr_min, angle_threshold, angle_period
- **Linear_Angle_RSI_Volatility_Pivot_15m.py**: exit_period, angle_min, rsi_period, angle_period, natr_threshold
- **MedianROC_Bollinger_Thrust_10m.py**: bb_period, roc_period, std_dev, adx_period, adx_threshold
- **Micro_Donchian_Volume_Burst_Scalper_1m.py**: vol_mult, atr_period, donchian_period, atr_threshold, vol_period
- **Micro_Kama_BOP_Filtered_Scalper_1m.py**: kama_period, exit_period, noise_floor, bop_threshold, slope_threshold
- **Micro_LinearSlope_Volume_Acceleration_Scalper_1m.py**: trailing_mult, lin_slope_period, atr_period, vol_trima_period, atr_sma_period
- **Micro_Linear_Angle_BOP_Volatility_Guard_1m.py**: bop_min, expansion_ratio, exit_period, angle_trigger, angle_period
- **Micro_Linear_Slope_BOP_Alpha_Scalper_1m.py**: slope_trigger, exit_period, slope_period, bop_threshold, noise_threshold
- **Micro_StochRSI_Velocity_Scalper_1m.py**: exit_period, noise_floor, dx_threshold, stoch_period, dx_period
- **Micro_Vol_Expansion_Scalper_1m.py**: exit_period, trend_period, atr_period, angle_threshold, vol_trigger
- **Midprice_Regression_Oscillator_Trend_5m.py**: exit_period, exit_mult, anchor_period, channel_mult, adxr_min
- **Midprice_StochRSI_NATR_Fader_5m.py**: oversold_threshold, entry_mult, overbought_threshold, natr_min, exit_mult
- **OBV_Accumulation_ADX_Trend_System_10m.py**: trail_lookback, trail_mult, obv_ema_period, adx_period, adx_threshold
- **Oscillator_Divergence_Trend_Filter_10m.py**: overbought_bound, trend_period, stoch_period, adx_min, oversold_bound
- **Regression_Deviation_Aroon_Reversion_30m.py**: diff_thresh, L, entry_thresh, stop_mult, A_period
- **Regression_Residual_Chandelier_Reversion_30m.py**: atr_multiplier, resid_mult, reg_period, chandelier_period, adx_threshold
- **Slope_CMO_ADXR_Trend_10m.py**: cmo_period, slope_period, adxr_threshold, cmo_threshold, adxr_period
- **StochRSI_ATR_Trailing_Momentum_15m.py**: trail_window, stoch_k, ema_period, atr_mult, adx_period
- **TEMA_Aroonosc_NATR_Trend_Follower_10m.py**: tema_period, aroon_period, natr_min, aroon_threshold, natr_period
- **TEMA_CCI_Envelope_Reversal_5m.py**: s, f, c, k, a
- **TEMA_DEMA_Cross_Trend_Follower_15m.py**: slow_period, exit_period, atr_mult_exit, adx_threshold, fast_period
- **Triangular_Aroon_Trend_Follower_5m.py**: trima_period, trailing_period, atr_multiplier, aroon_period, atr_period
- **Triple_Exponential_Volatility_Channel_15m.py**: tema_period, exit_period, vol_min, atr_period, channel_mult

### 6 Parameters (29 strategies)

- **APO_T3_Zero_Cross_Trend_5m.py**: slow_period, atr_multiplier, atr_period, trailing_lookback, t3_period, fast_period
- **Absolute_Directional_MFI_Reversal_10m.py**: mfi_period, exit_period, trend_period, mfi_overbought, di_period, mfi_oversold
- **Aroon_Structural_Chande_Volatility_Regime_10m.py**: cmo_period, aroon_period, exit_period, cmo_trigger, aroon_min, expansion_mult
- **Aroon_TRIX_ATR_Trail_5m.py**: atr_multiplier, trix_period, aroon_period, atr_period, ema_period, trail_period
- **BOP_Linear_Angle_Swing_Follower_15m.py**: exit_period, smooth_period, bop_threshold, angle_threshold, exit_mult, angle_period
- **Chande_Momentum_WMA_Channel_System_10m.py**: cmo_period, vol_floor, exit_period, cmo_trigger, exit_mult, wma_period
- **EfficiencyRatio_T3_OBV_Trend_15m.py**: er_period, er_threshold, er_exit_threshold, atr_period, atr_mult, t3_period
- **Intraday_Pattern_Volatility_Channel_5m.py**: cci_long_bound, cci_short_bound, lr_period, natr_threshold, cci_period, natr_period
- **Kama_Trend_CMO_Pullback_10m.py**: kama_period, cmo_short_pullback, cmo_period, exit_period, cmo_long_pullback, adx_threshold
- **Keltner_WMA_Momentum_Regime_30m.py**: roc_threshold, exit_period, roc_period, exit_mult, channel_mult, wma_period
- **Linear_Slope_CCI_Regime_Position_30m.py**: exit_period, slope_period, slope_threshold, cci_bound, expansion_factor, cci_period
- **Linear_Slope_Momentum_Reversal_10m.py**: cmo_period, cmo_long_trigger, slope_period, slope_threshold, cmo_short_trigger, dc_period
- **Linear_Slope_Plus_DI_Regime_Position_30m.py**: exit_period, slope_period, slope_threshold, di_period, exit_mult, expansion_factor
- **Linear_Slope_Ultimate_Oscillator_Confirmation_5m.py**: slope_trigger, exit_period, ultosc_offset, slope_period, natr_min, exit_mult
- **MACD_Histogram_Slope_Position_Follower_30m.py**: volatility_min, exit_period, slope_period, slow_macd, slope_threshold, fast_macd
- **Mean_Reversion_Triple_Standard_Deviation_30m.py**: rsi_lower, aroon_period, rsi_upper, rsi_period, bb_period, bb_mult
- **Micro_Ultimate_Keltner_Scalper_1m.py**: keltner_mult, vol_mult, atr_period, ema_period, ult_overbought, ult_oversold
- **Midpoint_Cross_ADX_Trail_30m.py**: slow_period, exit_atr_mult, atr_period, adx_period, adx_threshold, fast_period
- **Midprice_Ultimate_Oscillator_Reversion_30m.py**: ult_oversold, ult_overbought, stop_mult, midprice_period, deviation_mult, natr_period
- **Parabolic_SAR_MFI_Structural_Breakout_5m.py**: mfi_period, exit_period, sar_max, sar_acc, exit_mult, mfi_offset
- **ROCP_ADXR_Trend_Strength_15m.py**: rocp_period, ema_period, adxr_exit_threshold, adxr_strength_min, rocp_threshold, adxr_period
- **Star_Reversal_ADX_Trail_10m.py**: trailing_period, trailing_mult, atr_period, ema_period, adx_period, adx_threshold
- **Stoch_Momentum_WMA_Trend_Enforcer_10m.py**: overbought_bound, exit_period, oversold_bound, stoch_period, exit_mult, wma_period
- **TRIMA_CMO_NATR_Breakout_5m.py**: trima_period, cmo_period, cmo_entry_threshold, cmo_exit_threshold, natr_period, mult
- **Triple_Exponential_CCI_Volatility_Regime_10m.py**: tema_period, exit_period, natr_min, cci_bound, exit_mult, cci_period
- **Triple_Exponential_Moving_Average_CCI_Swing_15m.py**: tema_period, exit_period, cci_bound, exit_mult, expansion_mult, cci_period
- **Ultimate_Oscillator_BB_Squeeze_Reversion_5m.py**: overbought_bound, squeeze_threshold, exit_period, bb_period, oversold_bound, bb_mult
- **Volatility_Squeeze_Kama_Trend_15m.py**: kama_period, sar_max, bb_period, kc_mult, sar_acc, bb_mult
- **WMA_ATR_Angle_Breakout_15m.py**: ATR_length, trail_mult, WMA_length, angle_threshold, angle_period, channel_mult

### 7 Parameters (11 strategies)

- **Aroon_Oscillator_Volatility_Envelope_15m.py**: width_min, aroon_period, exit_period, bb_period, exit_mult, aroon_threshold, bb_mult
- **Chande_Momentum_Oscillator_DEMA_Swing_15m.py**: cmo_period, exit_period, slope_threshold, cmo_trigger, exit_mult, vol_factor, dema_period
- **Fast_Stochastic_NATR_Trend_Filter_15m.py**: slowk_period, ema_period, oversold_threshold, overbought_threshold, fastk_period, natr_threshold, natr_period
- **Keltner_Adaptive_Trend_Breakout_5m.py**: exit_period, atr_period, ema_period, kc_mult, exit_mult, adx_period, adx_threshold
- **LinearReg_Channel_ADX_Breakout_30m.py**: trailing_period, atr_trail_mult, ADX_period, LR_period, ATR_period, multiplier, adx_threshold
- **Micro_SAR_Volume_Burst_Scalper_1m.py**: param_vol_roc_threshold, param_accel, param_vol_roc_period, param_atr_period, param_max, param_atr_expansion_factor, param_exit_period
- **Micro_T3_ADX_Burst_Scalper_1m.py**: vol_mult, atr_period, mult_entry, adx_period, t3_period, mult_exit, adx_threshold
- **Micro_TRIMA_CMO_Volatility_Scalper_1m.py**: trima_period, atr_multiplier, cmo_period, volume_period, atr_period, volume_surge, cmo_threshold
- **Micro_Williams_Linear_Volume_Scalper_1m.py**: vol_mult, slope_period, willr_oversold, willr_overbought, willr_exit, vol_sma_period, willr_period
- **PPO_CMO_ATR_Trail_5m.py**: atr_multiplier, cmo_period, atr_period, ppo_slow, ppo_fast, cmo_threshold, trail_period
- **TRIX_ADX_Trail_System_10m.py**: trix_period, adx_exit_threshold, atr_mult, atr_period, adx_entry_threshold, exit_lookback, adx_period

### 8 Parameters (6 strategies)

- **Absolute_Price_Oscillator_Volatility_Enforcer_10m.py**: fast_apo, exit_period, sar_max, apo_threshold, sar_acc, natr_min, exit_mult, slow_apo
- **Engulfing_ADX_RSI_Chandelier_5m.py**: atr_period, rsi_period, chandelier_lookback, rsi_oversold, chandelier_mult, adx_period, rsi_overbought, adx_threshold
- **Micro_Acceleration_Burst_Scalper_1m.py**: volume_sma_period, atr_multiplier, fast_slope_period, trail_lookback, atr_period, volume_surge_threshold, breakout_lookback, slow_slope_period
- **PPO_Bandwidth_Expansion_Strategy_30m.py**: signalperiod, contraction_factor, bb_period, bandwidth_lookback, slowperiod, fastperiod, expansion_factor, bb_std
- **ROC_BBWidth_Momentum_System_10m.py**: trima_period, roc_threshold, exit_atr_mult, bb_stddev, atr_period, bb_period, roc_period, bbw_threshold
- **TEMA_BBWidth_WillR_Dynamic_Trail_10m.py**: trailing_period, tema_slow_period, atr_trail_mult, tema_fast_period, bb_period, bb_std, bbw_threshold, willr_period

### 9 Parameters (1 strategies)

- **Micro_DEMA_ADXR_Volume_Scalper_1m.py**: trail_multiplier, ADXR_period, vol_multiplier, ADX_period, chandelier_lookback, DEMA_period, ATR_period, vol_ma_period, ADX_threshold
