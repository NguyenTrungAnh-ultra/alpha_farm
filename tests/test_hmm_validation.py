import os
import pytest
pytest.importorskip('hmmlearn')
import numpy as np
import pandas as pd
import strategy_workflows.HMMValidation as hmm_module
from strategy_workflows.HMMValidation import (
    fit_hmm_model,
    stress_transition_matrix,
    generate_synthetic_ohlcv,
    precompute_hmm_synthetic_data
)
from utilities.AppConfig import HMM_COMPONENTS

@pytest.mark.core
def test_fit_hmm_model(dummy_ohlcv_data):
    """Đảm bảo GaussianHMM fit thành công trên dữ liệu ảo và xác định được bad_state."""
    hmm, df_clean, bad_state = fit_hmm_model(dummy_ohlcv_data, n_components=HMM_COMPONENTS, random_state=42)
    
    # Kiểm tra model hội tụ
    assert hmm.monitor_.converged, "HMM Model không hội tụ"
    
    # Kiểm tra df_clean có cột State
    assert 'State' in df_clean.columns
    
    # Kiểm tra bad_state có nằm trong range [0, HMM_COMPONENTS-1]
    assert 0 <= bad_state < HMM_COMPONENTS

@pytest.mark.core
def test_stress_transition_matrix():
    """Kiểm tra logic stress matrix: tăng xác suất bad_state lên stress_factor lần."""
    # Ma trận giả lập 3 states
    trans_matrix = np.array([
        [0.7, 0.2, 0.1],
        [0.3, 0.5, 0.2],
        [0.1, 0.1, 0.8]
    ])
    bad_state = 1
    stress_factor = 1.5
    
    stressed_trans = stress_transition_matrix(trans_matrix, bad_state, stress_factor)
    
    # State 0 -> bad_state = 0.2 * 1.5 = 0.3
    assert np.isclose(stressed_trans[0, 1], 0.3)
    
    # Check normalization: sum of each row should still be 1.0
    for i in range(3):
        assert np.isclose(np.sum(stressed_trans[i]), 1.0)
        
    # Check cap at 0.90
    trans_matrix_extreme = np.array([
        [0.1, 0.8, 0.1],
        [0.1, 0.8, 0.1],
        [0.1, 0.8, 0.1]
    ])
    stressed_extreme = stress_transition_matrix(trans_matrix_extreme, bad_state, stress_factor=2.0)
    assert np.isclose(stressed_extreme[0, 1], 0.90)

@pytest.mark.core
def test_generate_synthetic_ohlcv(dummy_ohlcv_data):
    """Kiểm tra module block bootstrapping sinh nến ảo có đúng định dạng không."""
    hmm, df_clean, _ = fit_hmm_model(dummy_ohlcv_data, n_components=2)
    
    n_bars = 200
    block_size = 20
    
    sim_df = generate_synthetic_ohlcv(
        df_clean=df_clean,
        trans_matrix=hmm.transmat_,
        n_bars=n_bars,
        block_size=block_size,
        initial_price=1000.0,
        random_seed=42
    )
    
    assert len(sim_df) == n_bars
    assert all(col in sim_df.columns for col in ['Open', 'High', 'Low', 'Close', 'Volume'])
    assert sim_df['Close'].iloc[0] > 0
    # Đảm bảo index là Datetime
    assert isinstance(sim_df.index, pd.DatetimeIndex)

@pytest.mark.hardware
def test_precompute_hmm_synthetic_data_caching(dummy_ohlcv_data, temp_hmm_cache, monkeypatch):
    """Test cơ chế ghi/đọc cache từ Disk, giảm tải CPU khi dữ liệu đã có sẵn."""
    monkeypatch.setattr('strategy_workflows.HMMValidation.MC_CACHE_DIR', temp_hmm_cache)
    fit_calls = []
    real_fit = hmm_module.fit_hmm_model
    monkeypatch.setattr(hmm_module, 'fit_hmm_model', lambda *a, **k: fit_calls.append(1) or real_fit(*a, **k))

    # 1. Chạy lần đầu tiên: Chưa có file cache -> Bắt buộc phải train và sinh file
    data = {'10m': dummy_ohlcv_data, '15m': dummy_ohlcv_data.iloc[:800]}
    result_first_run = precompute_hmm_synthetic_data(data, force_retrain=False, n_paths=2)

    assert '10m' in result_first_run
    assert '15m' in result_first_run
    assert len(fit_calls) == 2

    # Đảm bảo mỗi (timeframe, dữ liệu) có một file .pkl riêng trên Disk
    cache_dir = os.path.join(temp_hmm_cache, hmm_module.KEYED_CACHE_SUBDIR)
    assert len(os.listdir(cache_dir)) == 2

    # 2. Chạy lần thứ 2: Đã có file cache -> Phải load thẳng từ Disk, không fit lại
    result_second_run = precompute_hmm_synthetic_data(data, force_retrain=False, n_paths=2)
    assert len(fit_calls) == 2
    assert '10m' in result_second_run

    # 3. Chạy ép retrain: --retrain-hmm -> fit lại cho cả 2 timeframe
    precompute_hmm_synthetic_data(data, force_retrain=True, n_paths=2)
    assert len(fit_calls) == 4
