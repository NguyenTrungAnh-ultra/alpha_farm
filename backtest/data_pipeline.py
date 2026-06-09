"""
Data Pipeline for VN30F1M
=========================
Handles loading, cleaning, and session-tagging of TCBS continuous futures data.
"""

import pandas as pd
import numpy as np
from datetime import time
from backtest.constants import (
    MORNING_START, MORNING_END,
    AFTERNOON_START, AFTERNOON_END,
)


def load(filepath: str) -> pd.DataFrame:
    """
    Load raw VN30F1M CSV from TCBS.

    Parameters
    ----------
    filepath : str
        Path to the CSV file (e.g., 'data/VN30F1M_5m.csv').

    Returns
    -------
    pd.DataFrame
        Raw DataFrame with parsed Datetime column (not yet cleaned).
    """
    df = pd.read_csv(
        filepath,
        parse_dates=['Datetime'],
        dtype={
            'Open': 'float64',
            'High': 'float64',
            'Low': 'float64',
            'Close': 'float64',
            'Volume': 'Int64',  # nullable int to handle NaN
        }
    )
    # Drop completely empty rows (e.g., trailing newline)
    df = df.dropna(subset=['Datetime'])
    return df


def clean(df: pd.DataFrame) -> pd.DataFrame:
    """
    Clean raw data by removing padding bars and invalid rows.

    Removes:
    - Rows with Volume == 0 or NaN (padding bars from TCBS)
    - Rows with any NaN in OHLC columns

    Parameters
    ----------
    df : pd.DataFrame
        Raw DataFrame from load().

    Returns
    -------
    pd.DataFrame
        Cleaned DataFrame with only valid trading bars.
    """
    df = df.copy()

    # Drop rows with NaN in essential columns
    df = df.dropna(subset=['Open', 'High', 'Low', 'Close', 'Volume'])

    # Remove padding bars (volume == 0)
    df = df[df['Volume'] > 0].copy()

    # Reset index
    df = df.reset_index(drop=True)

    return df


def tag_sessions(df: pd.DataFrame) -> pd.DataFrame:
    """
    Add session metadata columns to the DataFrame.

    Adds:
    - 'trading_date': The calendar date of each bar
    - 'session': 'morning', 'afternoon', or 'atc'
    - 'bar_time': time component of Datetime
    - 'is_last_bar': True for the last valid bar of each trading day

    Parameters
    ----------
    df : pd.DataFrame
        Cleaned DataFrame from clean().

    Returns
    -------
    pd.DataFrame
        DataFrame with session metadata columns added.
    """
    df = df.copy()

    # Extract date and time
    df['trading_date'] = df['Datetime'].dt.date
    df['bar_time'] = df['Datetime'].dt.time

    # Classify session
    def _classify_session(t: time) -> str:
        if MORNING_START <= t < MORNING_END:
            return 'morning'
        elif AFTERNOON_START <= t <= AFTERNOON_END:
            return 'afternoon'
        elif t >= AFTERNOON_END:
            return 'atc'
        elif MORNING_END <= t < AFTERNOON_START:
            # Bars in the lunch break gap (11:30-13:00)
            # Rare edge cases (e.g., 2025-10-20 had bars at 11:35, 11:40)
            # Treat as morning session extension
            return 'morning'
        else:
            return 'other'

    df['session'] = df['bar_time'].apply(_classify_session)

    # Mark the last bar of each trading day
    # (important for force-close logic in the engine)
    df['is_last_bar'] = False
    last_indices = df.groupby('trading_date').tail(1).index
    df.loc[last_indices, 'is_last_bar'] = True

    return df


def get_daily_groups(df: pd.DataFrame) -> dict:
    """
    Group the DataFrame by trading_date.

    Parameters
    ----------
    df : pd.DataFrame
        Tagged DataFrame from tag_sessions().

    Returns
    -------
    dict[date, pd.DataFrame]
        Dictionary mapping each trading date to its bars.
    """
    return {date: group for date, group in df.groupby('trading_date')}


def prepare(filepath: str) -> pd.DataFrame:
    """
    Convenience function: load → clean → tag_sessions in one call.

    Parameters
    ----------
    filepath : str
        Path to the CSV file.

    Returns
    -------
    pd.DataFrame
        Fully prepared DataFrame ready for backtesting.
    """
    df = load(filepath)
    df = clean(df)
    df = tag_sessions(df)
    return df
