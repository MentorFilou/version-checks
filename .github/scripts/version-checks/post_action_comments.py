#!/usr/bin/env python3
"""Post or update PR comments summarising GitHub Action version check findings.

Reads the JSON files written by scan_actions.py and verify_sha.py. Each of the
three problem types maps to exactly one PR comment keyed by a hidden HTML marker,
so repeated CI runs update in-place rather than spamming new comments.

Comment behaviour:
  - Issues found  → create or update the comment with a table of occurrences
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


conflicts = load_json(os.path.join(TMP, "action-conflicts.json"))
not_sha_pinned = load_json(os.path.join(TMP, "action-not-sha-pinned.json"))
outdated = load_json(os.path.join(TMP, "action-outdated.json"))
mismatches = load_json(os.path.join(TMP, "action-sha-mismatch.json"))


# ---------------------------------------------------------------------------
# action-conflict
# ---------------------------------------------------------------------------
MARKER_CONFLICT = "<!--action-conflict-->"
try:
    if conflicts:
        rows = [
            "| Action | File | Line | Pinned ref | Comment |",
            "|--------|------|------|------------|---------|",
        ]
        for c in conflicts:
            for u in c["usages"]:
                rows.append(
                    f'| `{c["action"]}` | `{u["file"]}` | {u["line"]}'
                    f' | `{u["ref"][:12]}...` | `{u["comment"]}` |'
                )
        body = "\n".join([
            MARKER_CONFLICT,
            "## ❌ Action Version Conflict",
            "",
            "The same GitHub Action is pinned to different SHAs across workflow files.",
            "",
        ] + rows)
        gh_comment.upsert_comment(REPO, PR, MARKER_CONFLICT, body)
        print(f"Posted/updated: action-conflict ({len(conflicts)} action(s))")
    else:
        gh_comment.resolve_comment(REPO, PR, MARKER_CONFLICT, "> ✅ No action version conflicts — resolved.")
        print("No action-conflict issues.")
except Exception as e:
    print(f"WARNING: Could not post action-conflict comment: {e}")


# ---------------------------------------------------------------------------
# action-not-sha-pinned
# ---------------------------------------------------------------------------
MARKER_NOT_PINNED = "<!--action-not-sha-pinned-->"
try:
    if not_sha_pinned:
        rows = [
            "| Action | File | Line | Ref used |",
            "|--------|------|------|----------|",
        ]
        for e in not_sha_pinned:
            rows.append(
                f'| `{e["action"]}` | `{e["file"]}` | {e["line"]} | `{e["ref"]}` |'
            )
        body = "\n".join([
            MARKER_NOT_PINNED,
            "## ❌ Actions Not Pinned to a SHA",
            "",
            "All external actions must be pinned to a full commit SHA for supply-chain security.",
            "Replace the version tag with the corresponding 40-character SHA and add a version comment.",
            "",
        ] + rows)
        gh_comment.upsert_comment(REPO, PR, MARKER_NOT_PINNED, body)
        print(f"Posted/updated: action-not-sha-pinned ({len(not_sha_pinned)} action(s))")
    else:
        gh_comment.resolve_comment(REPO, PR, MARKER_NOT_PINNED, "> ✅ All actions are pinned to a SHA — resolved.")
        print("No unpinned actions.")
except Exception as e:
    print(f"WARNING: Could not post action-not-sha-pinned comment: {e}")


# ---------------------------------------------------------------------------
# action-sha-mismatch
# ---------------------------------------------------------------------------
MARKER_SHA = "<!--action-sha-mismatch-->"
try:
    if mismatches:
        rows = [
            "| Action | File | Line | Pinned SHA | Comment | Resolves to |",
            "|--------|------|------|------------|---------|-------------|",
        ]
        for m in mismatches:
            rows.append(
                f'| `{m["action"]}` | `{m["file"]}` | {m["line"]}'
                f' | `{m["pinned_sha"][:12]}...` | `{m["comment"]}`'
                f' | `{m["resolved_sha"][:12]}...` |'
            )
        body = "\n".join([
            MARKER_SHA,
            "## ❌ SHA / Version Comment Mismatch",
            "",
            "The pinned SHA does not resolve to the tag in the inline comment.",
            "",
        ] + rows)
        gh_comment.upsert_comment(REPO, PR, MARKER_SHA, body)
        print(f"Posted/updated: action-sha-mismatch ({len(mismatches)} mismatch(es))")
    else:
        gh_comment.resolve_comment(REPO, PR, MARKER_SHA, "> ✅ All SHAs match their version comments — resolved.")
        print("No SHA mismatch issues.")
except Exception as e:
    print(f"WARNING: Could not post action-sha-mismatch comment: {e}")


# ---------------------------------------------------------------------------
# action-outdated
# ---------------------------------------------------------------------------
MARKER_OUTDATED = "<!--action-outdated-->"
try:
    if outdated:
        rows = [
            "| Action | Pinned | Latest | Locations |",
            "|--------|--------|--------|-----------|",
        ]
        for o in outdated:
            locations = ", ".join(f'`{u["file"]}:{u["line"]}`' for u in o["usages"])
            rows.append(
                f'| `{o["action"]}` | `{o["current"]}` | `{o["latest"]}` | {locations} |'
            )
        body = "\n".join([
            MARKER_OUTDATED,
            "## ⚠️ Outdated GitHub Actions",
            "",
            "Newer releases are available. These do not block merging.",
            "",
        ] + rows)
        gh_comment.upsert_comment(REPO, PR, MARKER_OUTDATED, body)
        print(f"Posted/updated: action-outdated ({len(outdated)} action(s))")
    else:
        gh_comment.resolve_comment(REPO, PR, MARKER_OUTDATED, "> ✅ All GitHub Actions are up to date — resolved.")
        print("No outdated action issues.")
except Exception as e:
    print(f"WARNING: Could not post action-outdated comment: {e}")
