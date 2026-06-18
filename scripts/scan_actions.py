#!/usr/bin/env python3
"""Scan all .github/workflows/*.yml files for GitHub Action pins.

Writes two JSON files consumed by post_action_comments.py:
  <tmp>/action-conflicts.json  — actions pinned to different SHAs across files (FAIL)
  <tmp>/action-outdated.json   — actions with a newer release available (WARN)
"""

import json
import os
import re
import tempfile
import urllib.error
import urllib.request

IS_CI = bool(os.environ.get("GITHUB_ACTIONS"))
TMP = tempfile.gettempdir()


def parse_version(s):
    """Extract a comparable tuple from version strings like 'v6.0.2' or 'v.0.10.0'."""
    parts = re.findall(r"\d+", s)
    return tuple(int(x) for x in parts) if parts else (0,)


def parse_workflow_uses():
    """Return {action: [{ref, comment, file, line}]} parsed from all workflow files.

    Uses re.match (anchored to line start) so that 'uses:' occurrences inside
    run: blocks — e.g. in string literals or variable names — are never matched.
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
                # Local composite actions (./path) have no GitHub releases to check
                if "@" not in uses_val or uses_val.startswith("./"):
                    continue
                action, ref = uses_val.split("@", 1)
                action_map.setdefault(action, []).append(
                    {"ref": ref, "comment": comment, "file": fname, "line": lineno}
                )
    return action_map


def check_conflicts(action_map):
    """Return actions that are pinned to more than one distinct SHA across files."""
    conflicts = []
    print("=== Version conflict check ===")
    for action in sorted(action_map):
        refs = {u["ref"] for u in action_map[action]}
        if len(refs) > 1:
            for u in action_map[action]:
                if IS_CI:
                    print(
                        f"::error file=.github/workflows/{u['file']},line={u['line']}::"
                        f"{action} is pinned to {u['ref'][:12]}... ({u['comment']}) "
                        f"but other workflow files use a different pin"
                    )
            print(f"FAIL: '{action}' has conflicting pins: {', '.join(sorted(refs))}")
            conflicts.append({"action": action, "usages": action_map[action]})
    if not conflicts:
        print("No version conflicts found.")
    return conflicts


def check_outdated(action_map, token):
    """Return actions where the latest GitHub release is newer than the pinned comment."""
    outdated = []
    print("\n=== Latest release check ===")
    headers = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    for action in sorted(action_map):
        usages = action_map[action]
        comment = usages[0]["comment"]
        current_ver = parse_version(comment)
        if not current_ver:
            print(f"INFO: No parseable version in comment for {action}: '{comment}'")
            continue
        latest_tag = _fetch_latest(action, headers)
        if latest_tag is None:
            continue
        latest_ver = parse_version(latest_tag)
        if latest_ver > current_ver:
            if IS_CI:
                for u in usages:
                    print(
                        f"::warning file=.github/workflows/{u['file']},line={u['line']}::"
                        f"{action} uses {comment} but latest release is {latest_tag}"
                    )
            print(f"WARN: '{action}' — pinned: {comment}, latest: {latest_tag}")
            outdated.append({
                "action": action,
                "current": comment,
                "latest": latest_tag,
                "usages": [{"file": u["file"], "line": u["line"]} for u in usages],
            })
        else:
            print(f"OK:   '{action}' at {comment} (latest: {latest_tag})")
    return outdated


def _fetch_latest(action, headers):
    """Return the latest release tag for an action repo, falling back to tags list.

    Some repos (e.g. webfactory/ssh-agent) publish tags but no GitHub Releases,
    so a 404 on /releases/latest is a normal case, not an error.
    """
    url = f"https://api.github.com/repos/{action}/releases/latest"
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read())["tag_name"]
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return _fetch_latest_tag(action, headers)
        print(f"INFO: Could not fetch releases for {action}: HTTP {e.code}")
    except Exception as e:
        print(f"INFO: Could not check {action}: {e}")
    return None


def _fetch_latest_tag(action, headers):
    try:
        req = urllib.request.Request(
            f"https://api.github.com/repos/{action}/tags", headers=headers
        )
        with urllib.request.urlopen(req) as resp:
            tags = json.loads(resp.read())
            return tags[0]["name"] if tags else None
    except Exception as e:
        print(f"INFO: Could not fetch tags for {action}: {e}")
    return None


if __name__ == "__main__":
    token = os.environ.get("GH_TOKEN", "")
    action_map = parse_workflow_uses()
    conflicts = check_conflicts(action_map)
    outdated = check_outdated(action_map, token)

    with open(os.path.join(TMP, "action-conflicts.json"), "w") as f:
        json.dump(conflicts, f)
    with open(os.path.join(TMP, "action-outdated.json"), "w") as f:
        json.dump(outdated, f)
