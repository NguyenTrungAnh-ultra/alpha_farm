"""
XNOQuant Engine — Core Backtest Engine
========================================
Vectorized backtest engine mô phỏng chính xác cơ chế XNOQuant.

Quy trình:
1. Strategy tạo chuỗi position targets (vectorized)
2. Engine phát hiện thay đổi vị thế
3. Tính số HĐ, phí, PnL bar-by-bar
4. Tạo equity curve mark-to-market
"""

import pandas as pd
import numpy as np
from dataclasses import dataclass, field
from typing import List, Optional

from backtest.constants import (
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
    """Bản ghi một giao dịch hoàn chỉnh."""
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
    """Kết quả backtest hoàn chỉnh."""
    equity_curve: pd.Series        # Equity tại mỗi bar (mark-to-market)
    positions: pd.Series           # Vị thế target tại mỗi bar
    trades: List[TradeRecord]      # Danh sách giao dịch
    initial_capital: float
    final_equity: float
    total_fees: float
    total_trades: int


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
        Tính số hợp đồng theo công thức XNOQuant.

        N = round(|position| × equity / (price × MULTIPLIER × margin_rate))
        """
        if price <= 0 or equity <= 0:
            return 0
        margin_per_contract = price * MULTIPLIER * self.margin_rate
        n = abs(position) * equity / margin_per_contract
        return round(n)

    def run(self, strategy, df: pd.DataFrame) -> BacktestResult:
        """
        Chạy backtest.

        Parameters
        ----------
        strategy : SimpleAlgorithm
            Instance của strategy (subclass SimpleAlgorithm).
        df : pd.DataFrame
            DataFrame OHLCV (index = Datetime, columns = Open, High, Low, Close, Volume).

        Returns
        -------
        BacktestResult
        """
        # --- 1. Lấy position targets từ strategy ---
        positions = strategy.run_algorithm(df)

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
        )


def load_data(timeframe: str = '10m', start: str = BACKTEST_START, end: str = BACKTEST_END) -> pd.DataFrame:
    """
    Tải dữ liệu OHLCV từ file CSV.

    Parameters
    ----------
    timeframe : str
        Khung thời gian ('1m', '3m', '5m', '10m', '15m', '30m', '60m').
    start : str
        Ngày bắt đầu (YYYY-MM-DD).
    end : str
        Ngày kết thúc (YYYY-MM-DD).

    Returns
    -------
    pd.DataFrame
        DataFrame OHLCV với index là Datetime.
    """
    # Map 60m -> 1H for filename
    tf_file = '1H' if timeframe == '60m' else timeframe
    filename = DATA_FILENAME_TEMPLATE.format(timeframe=tf_file)
    filepath = f'{DATA_DIR}/{filename}'

    df = pd.read_csv(filepath, index_col='Datetime', parse_dates=True)

    # Lọc theo khoảng thời gian
    df = df[start:end]

    return df
