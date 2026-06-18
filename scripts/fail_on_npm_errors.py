#!/usr/bin/env python3
"""Exit with code 1 if any installed npm package is younger than 24 hours.

Kept separate from post_npm_comment.py so a comment API failure cannot
mask a real version-check failure.
"""

import json
import os
import sys
import tempfile

path = os.path.join(tempfile.gettempdir(), "npm-too-new.json")
if os.path.exists(path):
    with open(path) as f:
        if json.load(f):
            print("FAIL: npm age check failed — one or more installed packages are younger than 24 hours.")
            sys.exit(1)

print("All npm age checks passed.")
