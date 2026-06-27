#!/usr/bin/env python3
"""Post or update the PR comment summarising outdated npm dependency findings.

Reads /tmp/npm-outdated.json written by scan_npm.py.
"""

import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(__file__))
import gh_comment

REPO = os.environ["REPO"]
PR = os.environ["PR_NUMBER"]
MARKER = "<!--npm-outdated-->"
TMP = tempfile.gettempdir()

outdated = []
npm_path = os.path.join(TMP, "npm-outdated.json")
if os.path.exists(npm_path):
    with open(npm_path) as f:
        outdated = json.load(f)

try:
    if outdated:
        rows = [
            "| Package | Current | Latest | Released |",
            "|---------|---------|--------|----------|",
        ]
        for o in outdated:
            released = o.get("released", "unknown")
            if o.get("too_young"):
                released += " _(too young for pnpm)_"
            rows.append(
                f'| `{gh_comment.cell(o["package"])}` | `{gh_comment.cell(o["current"])}`'
                f' | `{gh_comment.cell(o["latest"])}` | {released} |'
            )
        body = "\n".join([
            MARKER,
            "## ⚠️ Outdated npm Dependencies",
            "",
            "Newer versions are available on npm. These do not block merging.",
            "",
        ] + rows)
        gh_comment.upsert_comment(REPO, PR, MARKER, body)
        print(f"Posted/updated: npm-outdated ({len(outdated)} package(s))")
    else:
        gh_comment.resolve_comment(REPO, PR, MARKER, "> ✅ All npm dependencies are up to date — resolved.")
        print("No outdated npm packages.")
except Exception as e:
    print(f"WARNING: Could not post npm-outdated comment: {e}")
