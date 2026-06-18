#!/usr/bin/env python3
"""Post or update PR comments summarising runtime version check findings.

Reads the JSON files written by scan_runtime_versions.py. Each problem type
maps to exactly one PR comment keyed by a hidden HTML marker, so repeated CI
runs update in-place rather than spamming new comments.

Comment behaviour:
  - Issues found   → create or update the comment with a summary table
  - Issues cleared → update the existing comment to a ✅ resolved line
  - Never an issue → no comment is ever created (resolve_comment no-ops)
"""

import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(__file__))
import gh_comment

REPO = os.environ["REPO"]
PR = os.environ["PR_NUMBER"]
TMP = tempfile.gettempdir()


def load_json(path):
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f)
    return []


conflicts = load_json(os.path.join(TMP, "runtime-version-conflicts.json"))
warnings = load_json(os.path.join(TMP, "runtime-version-warnings.json"))

version_warnings = [w for w in warnings if w.get("type", "").endswith("-outdated")]
runner_warnings = [w for w in warnings if w.get("type") == "runner-inconsistency"]


# ---------------------------------------------------------------------------
# runtime-version-conflict  (FAIL-level: version mismatch across files)
# ---------------------------------------------------------------------------
MARKER_CONFLICT = "<!--runtime-version-conflict-->"
try:
    if conflicts:
        rows = [
            "| Runtime | Version | Location |",
            "|---------|---------|----------|",
        ]
        for c in conflicts:
            for e in c["entries"]:
                rows.append(f'| `{c["runtime"].upper()}` | `{e["version"]}` | `{e["label"]}` |')
        body = "\n".join([
            MARKER_CONFLICT,
            "## ❌ Runtime Version Conflict",
            "",
            "The same runtime is declared at different versions across config files. "
            "All declarations must agree before this PR can merge.",
            "",
        ] + rows)
        gh_comment.upsert_comment(REPO, PR, MARKER_CONFLICT, body)
        print(f"Posted/updated: runtime-version-conflict ({len(conflicts)} conflict(s))")
    else:
        gh_comment.resolve_comment(
            REPO, PR, MARKER_CONFLICT,
            "> ✅ NODE and PNPM versions are consistent across all files — resolved.",
        )
        print("No runtime version conflicts.")
except Exception as e:
    print(f"WARNING: Could not post runtime-version-conflict comment: {e}")


# ---------------------------------------------------------------------------
# runtime-version-outdated  (WARN-level: newer version available)
# ---------------------------------------------------------------------------
MARKER_OUTDATED = "<!--runtime-version-outdated-->"
try:
    if version_warnings:
        rows = [
            "| Runtime | Current | Latest |",
            "|---------|---------|--------|",
        ]
        for w in version_warnings:
            runtime = w["type"].replace("-outdated", "").upper()
            rows.append(f'| `{runtime}` | `{w["current"]}` | `{w["latest"]}` |')
        body = "\n".join([
            MARKER_OUTDATED,
            "## ⚠️ Outdated Runtime Versions",
            "",
            "Newer patch releases are available. These do not block merging.",
            "",
        ] + rows)
        gh_comment.upsert_comment(REPO, PR, MARKER_OUTDATED, body)
        print(f"Posted/updated: runtime-version-outdated ({len(version_warnings)} runtime(s))")
    else:
        gh_comment.resolve_comment(
            REPO, PR, MARKER_OUTDATED,
            "> ✅ NODE and PNPM are on the latest versions — resolved.",
        )
        print("No outdated runtime versions.")
except Exception as e:
    print(f"WARNING: Could not post runtime-version-outdated comment: {e}")


# ---------------------------------------------------------------------------
# runtime-runner-inconsistency  (WARN-level: mixed ubuntu runner versions)
# ---------------------------------------------------------------------------
MARKER_RUNNER = "<!--runtime-runner-inconsistency-->"
try:
    if runner_warnings:
        w = runner_warnings[0]
        rows = [
            "| Runner | File | Line |",
            "|--------|------|------|",
        ]
        for e in w["entries"]:
            rows.append(f'| `{e["runner"]}` | `{e["ann_file"]}` | {e["ann_line"]} |')
        body = "\n".join([
            MARKER_RUNNER,
            "## ⚠️ Inconsistent Runner Versions",
            "",
            f"Workflow files use multiple Ubuntu runner versions: "
            f"{', '.join(f'`{v}`' for v in w['found'])}. "
            "Mixing `ubuntu-latest` with a pinned version can cause hard-to-reproduce "
            "failures when the `latest` label advances. These do not block merging.",
            "",
        ] + rows)
        gh_comment.upsert_comment(REPO, PR, MARKER_RUNNER, body)
        print(f"Posted/updated: runtime-runner-inconsistency")
    else:
        gh_comment.resolve_comment(
            REPO, PR, MARKER_RUNNER,
            "> ✅ All workflow runners use a consistent Ubuntu version — resolved.",
        )
        print("No runner version inconsistency.")
except Exception as e:
    print(f"WARNING: Could not post runtime-runner-inconsistency comment: {e}")
