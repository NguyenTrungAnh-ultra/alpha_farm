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
        Execute the backtest simulation.
        
        1. Runs the strategy algorithm to generate target positions.
        2. Unwraps RestrictedSeries if necessary.
        3. Tracks mark-to-market equity bar-by-bar.
        4. Simulates position reversals (closing old contracts, calculation of fees,
           and opening new contracts based on the first trade's base contract calculation).
        5. Returns structured BacktestResult.

        Parameters
        ----------
        strategy : SimpleAlgorithm
            The strategy instance subclassing SimpleAlgorithm.
        df : pd.DataFrame
            The OHLCV DataFrame (index = Datetime, columns = Open, High, Low, Close, Volume).

        Returns
        -------
        BacktestResult
            The structured results of the backtest.
        """
        # --- 1. Lấy position targets từ strategy ---
        positions = strategy.run_algorithm(df)
        
        # Unwrap RestrictedSeries if returned by strategy to allow engine/metrics to process it normally
        if type(positions).__name__ == 'RestrictedSeries':
            positions = positions._data

        close = df['Close'].values
        n_bars = len(df)
        index = df.index

        # --- 2. Khởi tạo tracking arrays ---
        equity = np.full(n_bars, np.nan)
        equity[0] = self.initial_capital

        trades: List[TradeRecord] = []
        total_fees = 0.0

        # Trạng thái vị thế hiện tại
        current_pos = 0.0          # Position target hiện tại
        current_contracts = 0      # Số HĐ đang giữ
        current_entry_price = 0.0  # Giá vào lệnh
        current_entry_bar = 0      # Bar vào lệnh
        current_equity = self.initial_capital
        unrealized_pnl = 0.0
        first_trade_open_fee = 0.0

        # XNOQuant dùng số HĐ CỐ ĐỊNH: tính 1 lần từ initial capital + giá bar đầu tiên
        # N = round(|pos| * initial_capital / (first_price * MULTIPLIER * margin_rate))
        # Sau đó giữ nguyên N cho tất cả trades
        base_contracts = None      # Sẽ tính khi trade đầu tiên xảy ra
        xno_trade_count = 0        # Đếm position changes (cách XNO đếm)

        # --- 3. Xử lý bar-by-bar ---
        for i in range(n_bars):
            target_pos = positions.iloc[i]
            price = close[i]

            # Phát hiện thay đổi vị thế
            if target_pos != current_pos:
                xno_trade_count += 1

                # --- Đóng vị thế cũ (nếu có) ---
                if current_contracts > 0:
                    direction = 1.0 if current_pos > 0 else -1.0
                    gross_pnl = direction * (price - current_entry_price) * current_contracts * MULTIPLIER
                    close_fee = current_contracts * self.fee_per_contract

                    # Ghi trade
                    trades.append(TradeRecord(
                        entry_bar=current_entry_bar,
                        exit_bar=i,
                        entry_time=index[current_entry_bar],
                        exit_time=index[i],
                        direction=direction,
                        position_size=abs(current_pos),
                        entry_price=current_entry_price,
                        exit_price=price,
                        contracts=current_contracts,
                        gross_pnl=gross_pnl,
                        fee=close_fee,
                        net_pnl=gross_pnl - close_fee,
                    ))

                    current_equity += gross_pnl - close_fee
                    total_fees += close_fee
                    current_contracts = 0
                    unrealized_pnl = 0.0

                # --- Mở vị thế mới (nếu target != 0) ---
                if target_pos != 0.0:
                    # Tính base_contracts 1 lần duy nhất (từ bar đầu tiên có trade)
                    if base_contracts is None:
                        base_contracts = self.calc_contracts(1.0, self.initial_capital, price)
                        first_trade_open_fee = round(abs(target_pos) * base_contracts) * self.fee_per_contract

                    # N = round(|target_pos| * base_contracts)
                    new_contracts = round(abs(target_pos) * base_contracts)
                    if new_contracts > 0:
                        open_fee = new_contracts * self.fee_per_contract
                        current_equity -= open_fee
                        total_fees += open_fee

                        current_contracts = new_contracts
                        current_entry_price = price
                        current_entry_bar = i
                    else:
                        target_pos = 0.0  # Không đủ vốn

                current_pos = target_pos

            # --- Mark-to-market ---
            if current_contracts > 0:
                direction = 1.0 if current_pos > 0 else -1.0
                unrealized_pnl = direction * (price - current_entry_price) * current_contracts * MULTIPLIER
            else:
                unrealized_pnl = 0.0

            equity[i] = current_equity + unrealized_pnl

        # --- 4. Build result ---
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
