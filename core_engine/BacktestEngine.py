"""
BacktestEngine
==============
Vectorized and bar-by-bar backtesting engine that simulates the exact behavior of XNOQuant.

Workflow:
1. The strategy generates position target series (vectorized)
2. The engine detects position changes and records trade transitions
3. Contracts, fees, and gross/net PnL are calculated bar-by-bar
4. Mark-to-market valuations are computed at each bar to build the equity curve.
"""

import pandas as pd
import numpy as np
from dataclasses import dataclass, field
from typing import List, Optional

from utilities.AppConfig import (
    MULTIPLIER,
    FEE_PER_CONTRACT_PER_SIDE,
    MARGIN_RATE,
    INITIAL_CAPITAL,
    BACKTEST_START,
    BACKTEST_END,
    DATA_DIR,
    DATA_FILENAME_TEMPLATE,
)


@dataclass
class TradeRecord:
    """
    Represents a record of a single completed trade.
    
    Attributes
    ----------
    entry_bar : int
        Bar index when entering the trade.
    exit_bar : int
        Bar index when exiting the trade.
    entry_time : object
        Timestamp of entry.
    exit_time : object
        Timestamp of exit.
    direction : float
        Direction of the trade: +1.0 for long, -1.0 for short.
    position_size : float
        Size of position (e.g. 0.2, 0.5, etc.).
    entry_price : float
        Entry price (close price at entry bar).
    exit_price : float
        Exit price (close price at exit bar).
    contracts : int
        Number of contracts traded.
    gross_pnl : float
        Gross profit/loss before fees.
    fee : float
        Total commission fees (for closing side, and opening side if reversal).
    net_pnl : float
        Net profit/loss after fees.
    """
    entry_bar: int                 # Index bar vào lệnh
    exit_bar: int                  # Index bar ra lệnh
    entry_time: object             # Datetime vào
    exit_time: object              # Datetime ra
    direction: float               # +1.0 long, -1.0 short
    position_size: float           # Giá trị position (0.5, 1.0, v.v.)
    entry_price: float             # Giá vào (Close tại bar vào)
    exit_price: float              # Giá ra (Close tại bar ra)
    contracts: int                 # Số hợp đồng
    gross_pnl: float               # PnL trước phí
    fee: float                     # Tổng phí (cả 2 chiều nếu reversal)
    net_pnl: float                 # PnL sau phí


@dataclass
class BacktestResult:
    """
    Represents the accumulated results of a backtest simulation.
    
    Attributes
    ----------
    equity_curve : pd.Series
        The portfolio equity value (mark-to-market) at each bar.
    positions : pd.Series
        The target position size at each bar.
    trades : list[TradeRecord]
        List of all recorded completed trade transactions.
    initial_capital : float
        The initial starting capital.
    final_equity : float
        The final portfolio equity value.
    total_fees : float
        Total fees incurred during the backtest.
    total_trades : int
        Total number of position change events.
    first_trade_open_fee : float, default 0.0
        The opening fee of the first trade (used for base adjustments).
    """
    equity_curve: pd.Series        # Equity tại mỗi bar (mark-to-market)
    positions: pd.Series           # Vị thế target tại mỗi bar
    trades: List[TradeRecord]      # Danh sách giao dịch
    initial_capital: float
    final_equity: float
    total_fees: float
    total_trades: int
    first_trade_open_fee: float = 0.0


class XNOBacktestEngine:
    """
    Engine backtest mô phỏng chính xác XNOQuant.

    Parameters
    ----------
    initial_capital : float
        Vốn ban đầu (mặc định 1 tỷ VND).
    margin_rate : float
        Tỷ lệ ký quỹ (mặc định 28.5%).
    fee_per_contract : float
        Phí mỗi hợp đồng mỗi chiều (mặc định 6,000 VND).
    """

    def __init__(
        self,
        initial_capital: float = INITIAL_CAPITAL,
        margin_rate: float = MARGIN_RATE,
        fee_per_contract: float = FEE_PER_CONTRACT_PER_SIDE,
    ):
        self.initial_capital = initial_capital
        self.margin_rate = margin_rate
        self.fee_per_contract = fee_per_contract

    def calc_contracts(self, position: float, equity: float, price: float) -> int:
        """
        Calculate the number of contracts according to the XNOQuant formula.
        
        Formula:
            N = round(|position| * equity / (price * MULTIPLIER * margin_rate))
            
        Parameters
        ----------
        position : float
            Target position size.
        equity : float
            Current portfolio equity.
        price : float
            Underlying index price.
            
        Returns
        -------
        int
            Calculated number of contracts.
        """
        if price <= 0 or equity <= 0:
            return 0
        margin_per_contract = price * MULTIPLIER * self.margin_rate
        n = abs(position) * equity / margin_per_contract
        return round(n)

    def run(self, strategy, df: pd.DataFrame) -> BacktestResult:
        """
        Thực thi mô phỏng Backtest toàn diện (Fully Vectorized).
        
        Quy trình xử lý lõi:
        1. Target Generation: Nhận mảng tín hiệu mục tiêu (Target Positions) từ chiến lược.
        2. Lookahead Bias Prevention: Áp dụng `positions.shift(1)` để dịch tín hiệu. Đảm bảo tín hiệu sinh ra từ nến `i` 
           sẽ chỉ được thực thi tại giá Close của nến `i+1`. Triệt tiêu hoàn toàn Data Leak tương lai.
        3. Netting Fee Engine: Áp dụng chuẩn Netting của thị trường Phái sinh VN30F. Phí giao dịch chỉ được tính 
           dựa trên Delta Contracts (độ lệch hợp đồng) thay vì cơ chế Full Close/Reopen. Tránh lỗi Commission Drag.
        4. Vectorized MTM: Tính toán Mark-To-Market (MTM) PnL và Equity toàn bộ chuỗi thời gian thông qua các 
           phép toán ma trận Numpy, cho tốc độ xử lý siêu tốc O(1) thay vì vòng lặp O(N).
        5. Trade Reconstruction: Quét qua các điểm giao cắt vị thế (`np.where(pos_changed)`) để dựng lại 
           mảng `TradeRecord`, đảm bảo tính tương thích ngược với hệ thống CalculateMetrics cũ.

        Parameters
        ----------
        strategy : SimpleAlgorithm
            Bản thể chiến lược sinh ra từ MCTSEngine hoặc Workflow chuẩn.
        df : pd.DataFrame
            DataFrame OHLCV cần Backtest.

        Returns
        -------
        BacktestResult
            Bao gồm Equity curve, List Trades, Total Fees, Trade Counts và Initial Capital.
        """
        # --- 1. Lấy position targets từ strategy ---
        positions = strategy.run_algorithm(df)
        
        # Unwrap RestrictedSeries if returned by strategy
        if type(positions).__name__ == 'RestrictedSeries':
            positions = positions._data

        # FIX: DATA LEAK (LOOKAHEAD BIAS)
        # Shift target positions by 1 so signal generated at close of bar `i` executes at close of bar `i+1`
        # This completely removes the lookahead bias and represents realistic execution.
        positions = positions.shift(1).fillna(0.0)

        close = df['Close'].values
        n_bars = len(df)
        index = df.index

        target_pos = positions.values
        
        # Find first index where target_pos != 0
        active_indices = np.where(target_pos != 0.0)[0]
        if len(active_indices) == 0:
            # No trades
            equity_curve = pd.Series(self.initial_capital, index=df.index, name='equity')
            return BacktestResult(equity_curve, positions, [], self.initial_capital, self.initial_capital, 0.0, 0, 0.0)
            
        first_idx = active_indices[0]
        first_price = close[first_idx]
        
        # --- 2. Calculate Contract sizing ---
        base_contracts = self.calc_contracts(1.0, self.initial_capital, first_price)
        first_trade_open_fee = round(abs(target_pos[first_idx]) * base_contracts) * self.fee_per_contract
        
        contracts = np.round(np.abs(target_pos) * base_contracts)
        direction = np.sign(target_pos)
        
        prev_contracts = np.roll(contracts, 1)
        prev_contracts[0] = 0.0
        prev_direction = np.roll(direction, 1)
        prev_direction[0] = 0.0
        
        # --- 3. Netting Fee & PnL Calculation ---
        # Calculate PnL (Mark-to-market bar by bar)
        price_diff = np.zeros_like(close)
        price_diff[1:] = close[1:] - close[:-1]
        
        # PnL realized at bar i is generated by holding position from i-1 to i
        pnl_bar = price_diff * prev_contracts * prev_direction * MULTIPLIER
        
        # VN30F Netting Fee: Fee is charged on the delta of contracts traded
        current_signed_contracts = contracts * direction
        prev_signed_contracts = prev_contracts * prev_direction
        delta_contracts = np.abs(current_signed_contracts - prev_signed_contracts)
        
        fee_bar = delta_contracts * self.fee_per_contract
        
        # Cumulative Equity
        net_bar_pnl = pnl_bar - fee_bar
        equity = self.initial_capital + np.cumsum(net_bar_pnl)
        
        total_fees = np.sum(fee_bar)
        
        # Count XNO trades (position changes)
        pos_changed = current_signed_contracts != prev_signed_contracts
        xno_trade_count = np.sum(pos_changed)
        
        # --- 4. Reconstruct TradeRecord list ---
        trades: List[TradeRecord] = []
        trade_indices = np.where(pos_changed)[0]
        
        current_entry_bar = -1
        current_contracts_held = 0.0
        current_dir = 0.0
        current_entry_price = 0.0
        accum_fee = 0.0
        accum_realized = 0.0
        
        for i in trade_indices:
            c = contracts[i]
            d = direction[i]
            p = close[i]
            fee_paid = delta_contracts[i] * self.fee_per_contract
            
            if current_contracts_held > 0:
                if d != current_dir:
                    # REVERSAL OR FLAT: Close entire held position
                    gross = current_dir * (p - current_entry_price) * current_contracts_held * MULTIPLIER
                    close_fee = current_contracts_held * self.fee_per_contract
                    net = gross + accum_realized - accum_fee - close_fee
                    
                    trades.append(TradeRecord(
                        entry_bar=current_entry_bar, exit_bar=i,
                        entry_time=index[current_entry_bar], exit_time=index[i],
                        direction=current_dir, position_size=1.0,
                        entry_price=current_entry_price, exit_price=p,
                        contracts=int(current_contracts_held),
                        gross_pnl=gross + accum_realized, fee=accum_fee + close_fee,
                        net_pnl=net
                    ))
                    
                    if d != 0:
                        # Reverse
                        current_dir = d
                        current_contracts_held = c
                        current_entry_price = p
                        current_entry_bar = i
                        accum_fee = c * self.fee_per_contract # Opening fee
                        accum_realized = 0.0
                    else:
                        current_dir = 0.0
                        current_contracts_held = 0.0
                        accum_fee = 0.0
                        accum_realized = 0.0
                else:
                    # SAME DIRECTION: Scale In / Scale Out
                    if c > current_contracts_held:
                        # Scale IN: VWAP entry price
                        added_c = c - current_contracts_held
                        current_entry_price = (current_entry_price * current_contracts_held + p * added_c) / c
                        current_contracts_held = c
                        accum_fee += fee_paid
                    elif c < current_contracts_held:
                        # Scale OUT: Realize partial PnL
                        removed_c = current_contracts_held - c
                        realized = current_dir * (p - current_entry_price) * removed_c * MULTIPLIER
                        accum_realized += realized
                        accum_fee += fee_paid
                        current_contracts_held = c
            else:
                # Open new position
                if d != 0:
                    current_dir = d
                    current_contracts_held = c
                    current_entry_price = p
                    current_entry_bar = i
                    accum_fee = fee_paid
                    accum_realized = 0.0

        # --- 5. Build result ---
        equity_series = pd.Series(equity, index=index, name='equity')
        final_equity = equity[-1] if n_bars > 0 else self.initial_capital

        return BacktestResult(
            equity_curve=equity_series,
            positions=positions,
            trades=trades,
            initial_capital=self.initial_capital,
            final_equity=final_equity,
            total_fees=total_fees,
            total_trades=xno_trade_count,
            first_trade_open_fee=first_trade_open_fee,
        )


def load_data(timeframe: str = '10m', start: str = BACKTEST_START, end: str = BACKTEST_END) -> pd.DataFrame:
    """
    Load historical OHLCV data from a CSV file.
    
    Resolves 60m to 1H files based on the project's data template, reads the CSV
    from the data directory, parses the 'Datetime' index, and filters the rows
    between the start and end dates.

    Parameters
    ----------
    timeframe : str, default '10m'
        The timeframe representation ('1m', '3m', '5m', '10m', '15m', '30m', '60m').
    start : str, default BACKTEST_START
        Start date filter string (YYYY-MM-DD).
    end : str, default BACKTEST_END
        End date filter string (YYYY-MM-DD).

    Returns
    -------
    pd.DataFrame
        The filtered OHLCV DataFrame with parsed Datetime index.
    """
    # Map 60m -> 1H for filename
    tf_file = '1H' if timeframe == '60m' else timeframe
    filename = DATA_FILENAME_TEMPLATE.format(timeframe=tf_file)
    filepath = f'{DATA_DIR}/{filename}'

    df = pd.read_csv(filepath, index_col='Datetime', parse_dates=True)

    # Lọc theo khoảng thời gian
    df = df[start:end]

    return df
