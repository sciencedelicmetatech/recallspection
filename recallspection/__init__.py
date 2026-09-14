"""
Recallspection – Dual-core exact memory for AI agents.
"""

__version__ = "18.0.0"

from .exact import ExactMemory, TamperDetectedError
from .swstm import SWSTMEngine, SWSTMCore, HybridEngine

__all__ = [
    "ExactMemory",
    "TamperDetectedError",
    "SWSTMEngine",
    "SWSTMCore",
    "HybridEngine",
]
