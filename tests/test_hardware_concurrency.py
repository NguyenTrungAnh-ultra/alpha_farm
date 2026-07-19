import pytest
from unittest.mock import patch, MagicMock
from concurrent.futures import Future
from strategy_workflows.RunMCTS import run_mcts_pipeline

@pytest.mark.hardware
@patch('strategy_workflows.HMMValidation.precompute_hmm_synthetic_data')
@patch('strategy_workflows.RunMCTS.concurrent.futures.ProcessPoolExecutor')
def test_multiprocessing_pipeline(mock_executor_class, mock_precompute):
    """
    Test quá trình chia việc cho ProcessPoolExecutor.
    Đảm bảo ProcessPoolExecutor được khởi tạo và nhận đúng số lượng tasks.
    """
    # Trả về dummy synthetic data để hàm ko bị vướng
    mock_precompute.return_value = {
        '10m': {'normal': [], 'stressed': []},
        '60m': {'normal': [], 'stressed': []},
    }
    
    # Mock behavior of the Executor instance
    mock_executor_instance = MagicMock()
    mock_executor_class.return_value.__enter__.return_value = mock_executor_instance
    
    # Return REAL Future objects from submit so as_completed doesn't hang!
    f10m = Future()
    f10m.set_result(('10m', 10, 5, [{'strategy_name': 'Mock_10m'}]))
    
    f60m = Future()
    f60m.set_result(('60m', 10, 5, [{'strategy_name': 'Mock_60m'}]))
    
    mock_executor_instance.submit.side_effect = [f10m, f60m]
    
    # Ghi đè biến TIMEFRAMES trong module RunMCTS chỉ lấy 2 cái để test nhanh
    with patch('strategy_workflows.RunMCTS.TIMEFRAMES', ['10m', '60m']):
        # Chạy pipeline
        run_mcts_pipeline(iterations=10, retrain_hmm=False)
        
        # Kiểm tra HMM precompute được gọi
        mock_precompute.assert_called_once()
        
        # Kiểm tra Executor đã submit đúng 2 lần (cho 10m và 60m)
        assert mock_executor_instance.submit.call_count == 2
        
        # Kiểm tra tham số truyền vào hàm submit
        calls = mock_executor_instance.submit.call_args_list
        # calls[0] -> (process_timeframe, '10m', 10, ...)
        tfs_called = [call[0][1] for call in calls]
        assert '10m' in tfs_called
        assert '60m' in tfs_called
