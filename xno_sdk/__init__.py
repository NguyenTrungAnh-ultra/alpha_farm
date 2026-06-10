"""
XNOQuant Local SDK Environment
==============================
Mô phỏng 100% môi trường Sandbox của XNOQuant.
Giúp phát hiện sớm các lỗi về logic như sử dụng pandas functions (lỗi 10),
sử dụng vật lý indexing (lỗi 11), và thiếu volume data (lỗi 9).
"""

from .engine import SimpleAlgorithm
from .engine import FeatureEngine
from .engine import OperatorEngine
from .engine import DataProxy
