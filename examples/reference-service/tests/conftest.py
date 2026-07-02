# SPDX-License-Identifier: MIT
"""Put the reference-service directory on sys.path so the upload-surface tests can
`import app` standalone (the service is an example, not part of the `cab` package).
The engine itself (`cab`) resolves via the repo's pytest `pythonpath = ["src"]`.
"""

import os
import sys

SERVICE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if SERVICE_DIR not in sys.path:
    sys.path.insert(0, SERVICE_DIR)
