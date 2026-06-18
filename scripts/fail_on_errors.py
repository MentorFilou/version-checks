#!/usr/bin/env python3
"""Exit with code 1 if any FAIL-level action version check produced findings.

Kept separate from post_action_comments.py so a comment API failure cannot
mask a real version-check failure — the job still fails even if posting the
PR comment threw an exception.
"""

import json
import os
import sys
import tempfile

TMP = tempfile.gettempdir()

FAIL_FILES = [
    os.path.join(TMP, "action-conflicts.json"),
    os.path.join(TMP, "action-not-sha-pinned.json"),
    os.path.join(TMP, "action-sha-mismatch.json"),
]

fail = False
for path in FAIL_FILES:
    if os.path.exists(path):
        with open(path) as f:
            if json.load(f):
                fail = True

if fail:
    print("FAIL: Action version checks failed — see output above.")
    sys.exit(1)
else:
    print("All action version checks passed.")
