"""
Recallspection – Dual-core exact memory for AI agents.
"""

__version__ = "18.0.0"

from .swstm import (
    ExactMemory,
    HybridEngine,
    SWSTMEngine,
    SWSTMCore,
)

__all__ = [
    "ExactMemory",
    "HybridEngine",
    "SWSTMEngine",
    "SWSTMCore",
]

