import pytest
from unittest.mock import patch, MagicMock
from concurrent.futures import Future
import sys

@pytest.mark.hardware
def test_multiprocessing_pipeline():
    """
    Test quá trình chia việc cho ProcessPoolExecutor.
    Đảm bảo ProcessPoolExecutor được khởi tạo và nhận đúng số lượng tasks.
    """
    mock_hmm = MagicMock()
    mock_precompute = MagicMock()
    mock_precompute.return_value = {
        '10m': {'normal': [], 'stressed': []},
        '60m': {'normal': [], 'stressed': []},
    }
    mock_hmm.precompute_hmm_synthetic_data = mock_precompute

    with patch.dict('sys.modules', {
        'hmmlearn': MagicMock(),
        'hmmlearn.hmm': MagicMock(),
        'strategy_workflows.HMMValidation': mock_hmm
    }):
        from strategy_workflows.RunMCTS import run_mcts_pipeline

        import pandas as pd
        tiny = pd.DataFrame({'Open': [1.0], 'High': [1.0], 'Low': [1.0], 'Close': [1.0], 'Volume': [1.0]},
                            index=pd.date_range('2024-01-01', periods=1))

        mock_executor_instance = MagicMock()

        f10m = Future()
        f10m.set_result(('10m', 10, 5, [{'strategy_name': 'Mock_10m'}]))

        f60m = Future()
        f60m.set_result(('60m', 10, 5, [{'strategy_name': 'Mock_60m'}]))

        mock_executor_instance.submit.side_effect = [f10m, f60m]

        with patch('strategy_workflows.RunMCTS.concurrent.futures.ProcessPoolExecutor') as mock_executor_class:
            mock_executor_class.return_value.__enter__.return_value = mock_executor_instance
            with patch('strategy_workflows.RunMCTS.TIMEFRAMES', ['10m', '60m']), patch('strategy_workflows.RunMCTS.load_data', return_value=tiny):
                run_mcts_pipeline(iterations=10, retrain_hmm=False)

                mock_precompute.assert_called_once()
                assert mock_executor_instance.submit.call_count == 2

                calls = mock_executor_instance.submit.call_args_list
                tfs_called = [call[0][1] for call in calls]
                assert '10m' in tfs_called
                assert '60m' in tfs_called
