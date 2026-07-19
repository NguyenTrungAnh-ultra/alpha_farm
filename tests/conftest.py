import os
import shutil
import pytest
import numpy as np
import pandas as pd
from utilities.AppConfig import PROJECT_ROOT

@pytest.fixture
def dummy_ohlcv_data():
    """Sinh dữ liệu giả lập OHLCV (1000 nến) để test các Engine mà không cần file CSV nặng."""
    np.random.seed(42)
    n_bars = 1000
    
    # Sinh dữ liệu ngẫu nhiên có Trend nhẹ
    returns = np.random.normal(0.0001, 0.005, n_bars)
    prices = 1000.0 * np.exp(np.cumsum(returns))
    
    dates = pd.date_range(start="2024-01-01", periods=n_bars, freq="15min")
    
    df = pd.DataFrame({
        'Open': prices * np.random.uniform(0.999, 1.001, n_bars),
        'High': prices * np.random.uniform(1.0, 1.005, n_bars),
        'Low': prices * np.random.uniform(0.995, 1.0, n_bars),
        'Close': prices,
        'Volume': np.random.uniform(1000, 10000, n_bars)
    }, index=dates)
    
    df.index.name = "Datetime"
    return df

@pytest.fixture
def temp_hmm_cache():
    """Tạo thư mục giả để lưu cache của HMM, sau khi test xong sẽ tự động dọn dẹp."""
    test_cache_dir = os.path.join(PROJECT_ROOT, "results", "test_hmm_cache")
    os.makedirs(test_cache_dir, exist_ok=True)
    
    # Yield đường dẫn cho test function
    yield test_cache_dir
    
    # Teardown
    if os.path.exists(test_cache_dir):
        shutil.rmtree(test_cache_dir)
