#!/usr/bin/env python3
"""Exit with code 1 if any runtime version conflict was detected.

Kept separate from post_runtime_comment.py so a comment API failure cannot
mask a real version-check failure.
"""

import json
import os
import sys
import tempfile

path = os.path.join(tempfile.gettempdir(), "runtime-version-conflicts.json")
if os.path.exists(path):
    with open(path) as f:
        if json.load(f):
            print("FAIL: Runtime version conflicts detected — see output above.")
            sys.exit(1)

print("All runtime version checks passed.")
