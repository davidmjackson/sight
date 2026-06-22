"""Test-wide defaults.

The web auth layer (SS-34) fails safe: it refuses to start without a signing
secret unless explicitly in dev mode. Tests run offline in dev mode, so set the
flag before any app module is imported. setdefault means a real CI/env value
still wins if one is provided.
"""

import os

os.environ.setdefault("SPRINTSIGHT_ENV", "dev")
