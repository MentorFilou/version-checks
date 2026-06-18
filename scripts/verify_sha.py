#!/usr/bin/env python3
"""Verify that each pinned SHA in workflow files resolves to the commented version tag.

Uses GET /repos/{owner}/{repo}/commits/{ref} which resolves both lightweight and
annotated tags to their underlying commit SHA — the value workflow files should pin.

Writes:
  <tmp>/action-sha-mismatch.json    — SHA does not match version comment (FAIL)
  <tmp>/action-not-sha-pinned.json  — action is not pinned to a SHA at all (FAIL)
Both are consumed by post_action_comments.py.
"""

import json
import os
import re
import tempfile
import urllib.error
import urllib.request

IS_CI = bool(os.environ.get("GITHUB_ACTIONS"))
TMP = tempfile.gettempdir()
SHA_RE = re.compile(r"^[0-9a-f]{40}$")


def check_sha_pinning(action_map):
    """Return entries where the ref is not a full 40-char hex SHA."""
    not_pinned = []
    print("=== SHA pinning enforcement ===")
    for action in sorted(action_map):
        for usage in action_map[action]:
            if not SHA_RE.match(usage["ref"]):
                if IS_CI:
                    print(
                        f"::error file=.github/workflows/{usage['file']},line={usage['line']}::"
                        f"{action} is not pinned to a SHA — ref is '{usage['ref']}'"
                    )
                print(f"FAIL: '{action}' uses ref '{usage['ref']}' — must be a full commit SHA")
                not_pinned.append({
                    "action": action,
                    "file": usage["file"],
                    "line": usage["line"],
                    "ref": usage["ref"],
                })
    if not not_pinned:
        print("All actions are SHA-pinned.")
    return not_pinned


def parse_unique_pins():
    """Return {action: [{action, ref, comment, file, line}]} with one entry per unique (action, ref).

    Deduplicating by (action, ref) avoids redundant API calls when the same pin
    appears in multiple workflow files.
    """
    action_map = {}
    for fname in sorted(os.listdir(".github/workflows")):
        if not fname.endswith(".yml") and not fname.endswith(".yaml"):
            continue
        with open(f".github/workflows/{fname}") as f:
            for lineno, line in enumerate(f, 1):
                m = re.match(r"\s+uses:\s+([^\s#]+)(?:\s+#\s*(.*))?", line)
                if not m:
                    continue
                uses_val = m.group(1).strip()
                comment = (m.group(2) or "").strip()
                if "@" not in uses_val or uses_val.startswith("./"):
                    continue
                action, ref = uses_val.split("@", 1)
                key = (action, ref)
                existing = {(u["action"], u["ref"]) for u in action_map.get(action, [])}
                if key not in existing:
                    action_map.setdefault(action, []).append(
                        {"action": action, "ref": ref, "comment": comment, "file": fname, "line": lineno}
                    )
    return action_map


def verify_sha(action_map, token):
    """Check each pinned SHA against the commit the version comment tag resolves to."""
    mismatches = []
    headers = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    print("=== SHA vs version comment verification ===")
    for action in sorted(action_map):
        for usage in action_map[action]:
            pinned_sha = usage["ref"]
            comment = usage["comment"]
            if not re.search(r"\d", comment):
                print(f"INFO: No version tag in comment for {action}: '{comment}' — skipping")
                continue
            resolved_sha = _resolve_ref(action, comment, headers)
            if resolved_sha is None:
                continue
            if resolved_sha != pinned_sha:
                if IS_CI:
                    print(
                        f"::error file=.github/workflows/{usage['file']},line={usage['line']}::"
                        f"{action} is pinned to {pinned_sha[:12]}... but "
                        f"'{comment}' resolves to {resolved_sha[:12]}..."
                    )
                print(
                    f"FAIL: '{action}' — pinned SHA {pinned_sha[:12]}... "
                    f"does not match '{comment}' ({resolved_sha[:12]}...)"
                )
                mismatches.append({
                    "action": action,
                    "file": usage["file"],
                    "line": usage["line"],
                    "pinned_sha": pinned_sha,
                    "comment": comment,
                    "resolved_sha": resolved_sha,
                })
            else:
                print(f"OK:   '{action}' — {pinned_sha[:12]}... matches '{comment}'")
    return mismatches


def _resolve_ref(action, ref, headers):
    """Return the commit SHA that ref resolves to, or None if the ref cannot be found."""
    url = f"https://api.github.com/repos/{action}/commits/{ref}"
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read())["sha"]
    except urllib.error.HTTPError as e:
        print(f"INFO: Could not resolve '{ref}' for {action}: HTTP {e.code} — skipping")
    except Exception as e:
        print(f"INFO: Could not resolve '{ref}' for {action}: {e} — skipping")
    return None


if __name__ == "__main__":
    token = os.environ.get("GH_TOKEN", "")
    action_map = parse_unique_pins()
    not_pinned = check_sha_pinning(action_map)
    # Only verify SHA vs comment for entries that are already SHA-pinned
    sha_pinned_map = {
        action: [u for u in usages if SHA_RE.match(u["ref"])]
        for action, usages in action_map.items()
    }
    sha_pinned_map = {k: v for k, v in sha_pinned_map.items() if v}
    mismatches = verify_sha(sha_pinned_map, token)

    with open(os.path.join(TMP, "action-not-sha-pinned.json"), "w") as f:
        json.dump(not_pinned, f)
    with open(os.path.join(TMP, "action-sha-mismatch.json"), "w") as f:
        json.dump(mismatches, f)
