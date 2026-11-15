import sys
import os

# =====================================================================
# PUBLIC ANCHOR: Update this hash every time you release a new version.
# Post this hash on your README, Twitter, or Zenodo paper.
# =====================================================================
V18_ANCHOR = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855" 
VERSION = "v18"

def bootstrap():
    # 1. Check for bypass (only for local development)
    if os.environ.get("RECALLSPECTION_SKIP_SELF_CHECK") == "1":
        print("[Recallspection] ⚠️ WARNING: Self-check bypassed via ENV variable.")
        return

    # 2. Load the self-ledger module
    try:
        from recallspection.self_ledger import verify_self
    except ImportError:
        sys.exit("[Recallspection FATAL] Could not import self_ledger. Is the directory structure correct?")

    # 3. Verify THIS file against the ledger and the public anchor
    verify_self(__file__, V18_ANCHOR)

# Run the check before importing the heavy logic
bootstrap()

# =====================================================================
# BELOW THIS LINE IS THE ACTUAL RECALLSPECTION LOGIC
# =====================================================================
print("[Recallspection] Loading core engines...")
try:
    from recallspection.exactmemory_recallspection.core import ExactMemory
    from recallspection.swstm import SWSTMEngine
except ImportError as e:
    sys.exit(f"[Recallspection FATAL] Could not load core modules: {e}")

def main():
    print("[Recallspection] System is online and verified.")
    # Your actual startup logic here
    # store = ExactMemory(...)

if __name__ == "__main__":
    main()