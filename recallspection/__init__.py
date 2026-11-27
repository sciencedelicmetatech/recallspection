"""
recallspection — tamper-evident exact memory for autonomous AI agents.

Fix for path mismatch:
- Anchor lives in recallspection/anchor.py (package)
- Mandate / Notary / Client / Store were pushed to repo ROOT (mandate.py, notary.py, ...)
  while __init__.py tried `from recallspection.mandate import ...`
  -> ModuleNotFoundError in clean checkout.

This __init__ works in BOTH layouts:
  A) files inside recallspection/ (correct package layout)
  B) files at repo root (current pushed layout)
It keeps anchor exports + __version__ = "18.0.0" untouched.
"""

import sys as _sys
import pathlib as _pathlib

# Make repo root importable so flat files at root can be found
# when this package is imported from a checkout.
try:
    _ROOT = _pathlib.Path(__file__).resolve().parent.parent
    if str(_ROOT) not in _sys.path:
        _sys.path.insert(0, str(_ROOT))
except Exception:
    pass

# --- Anchor: unchanged, package-relative first ---
try:
    from .anchor import (
        AnchorRecord,
        RemoteAnchorS3,
        anchor_root,
        audit_export,
        compute_merkle_root,
    )
except ImportError:
    # Fallback for flat / installed layouts
    from recallspection.anchor import (
        AnchorRecord,
        RemoteAnchorS3,
        anchor_root,
        audit_export,
        compute_merkle_root,
    )

# --- Mandate / Notary / Client / Store: try package, then root ---
# We need aliases in sys.modules because notary.py itself does
# `from mandate import Mandate` (flat import). If files live inside
# the package, that flat import would fail unless we alias it.
# If files live at root, the package import fails and we load flat.

def _alias(name, mod):
    # mod is e.g. recallspection.mandate -> also expose as top-level `mandate`
    # so flat imports inside notary.py keep working.
    _sys.modules.setdefault(name, mod)
    _sys.modules.setdefault(f"recallspection.{name}", mod)
    return mod

try:
    # Layout A: correct package layout — recallspection/mandate.py etc.
    # ORDER MATTERS: notary.py does `from mandate import Mandate` (flat).
    # Alias mandate + store BEFORE importing notary, or notary fails.
    from .mandate import Mandate as _Mandate
    _alias("mandate", _sys.modules["recallspection.mandate"])
    from .store import ExactStore as _ExactStore, NotaryStore as _NotaryStore
    _alias("store", _sys.modules["recallspection.store"])
    from .notary import MachineNotary as _MachineNotary
    _alias("notary", _sys.modules["recallspection.notary"])
    from .client import NotaryClient as _NotaryClient
    _alias("client", _sys.modules["recallspection.client"])
    Mandate = _Mandate
    MachineNotary = _MachineNotary
    NotaryClient = _NotaryClient
    ExactStore = _ExactStore
    NotaryStore = _NotaryStore
except ImportError:
    # Layout B: current pushed layout — files at repo root
    # notary.py does `from mandate import ...` so root must be on path (done above)
    from mandate import Mandate
    from notary import MachineNotary
    from client import NotaryClient
    from store import ExactStore, NotaryStore
    # Alias so `from recallspection.mandate import ...` also works
    _alias("mandate", _sys.modules["mandate"])
    _alias("store", _sys.modules["store"])
    _alias("notary", _sys.modules["notary"])
    _alias("client", _sys.modules["client"])
    _sys.modules.setdefault("recallspection.mandate", _sys.modules["mandate"])
    _sys.modules.setdefault("recallspection.notary", _sys.modules["notary"])
    _sys.modules.setdefault("recallspection.client", _sys.modules["client"])
    _sys.modules.setdefault("recallspection.store", _sys.modules["store"])

__version__ = "18.0.0"

__all__ = [
    # existing anchor surface, unchanged
    "AnchorRecord",
    "RemoteAnchorS3",
    "anchor_root",
    "audit_export",
    "compute_merkle_root",
    # new mandate / notary surface
    "Mandate",
    "MachineNotary",
    "NotaryClient",
    "ExactStore",
    "NotaryStore",
    "__version__",
]
