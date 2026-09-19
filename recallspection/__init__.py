"""
Recallspection – Dual-core exact memory for AI agents.
"""

__version__ = "18.0.0"

__all__ = [
    "ExactMemory",
    "HybridEngine",
    "SWSTMEngine",
    "SWSTMCore",
]

def __getattr__(name):
    if name in __all__:
        from . import swstm
        return getattr(swstm, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
