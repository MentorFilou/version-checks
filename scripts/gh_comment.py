#!/usr/bin/env python3
"""Shared helpers for reading and upserting GitHub PR comments via the REST API.

Each comment type is identified by a hidden HTML marker on the first line of
the body so that repeated CI runs update the same comment in-place instead of
posting duplicates. resolve_comment() is intentionally a no-op when no comment
exists yet — a PR that was always clean should have zero bot comments.
"""

import json
import os
import urllib.request


def cell(value):
    """Escape a value for safe inclusion in a Markdown table cell.

    GitHub treats `|` as a column separator even inside backticks, so any
    dynamic value containing one (e.g. `inputs.runner || 'ubuntu-24.04'` or a
    `^20 || >=22` version range) splits into bogus columns and mangles the row.
    Escaping it as `\\|` makes it render literally. Newlines are also flattened
    since they would otherwise terminate the row.
    """
    return str(value).replace("|", "\\|").replace("\n", " ")


def _headers():
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "Content-Type": "application/json",
    }
    token = os.environ.get("GH_TOKEN", "")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def find_comment(repo, pr_number, marker):
    """Scan paginated PR comments and return the id of the one containing marker, or None."""
    page = 1
    while True:
        url = (
            f"https://api.github.com/repos/{repo}/issues/{pr_number}"
            f"/comments?per_page=100&page={page}"
        )
        req = urllib.request.Request(url, headers=_headers())
        with urllib.request.urlopen(req) as resp:
            comments = json.loads(resp.read())
        if not comments:
            return None
        for c in comments:
            if marker in c["body"]:
                return c["id"]
        if len(comments) < 100:
            return None  # reached last page without a match
        page += 1


def upsert_comment(repo, pr_number, marker, body):
    """Create or PATCH the single PR comment identified by marker."""
    payload = json.dumps({"body": body}).encode()
    comment_id = find_comment(repo, pr_number, marker)
    if comment_id:
        url = f"https://api.github.com/repos/{repo}/issues/comments/{comment_id}"
        req = urllib.request.Request(url, data=payload, headers=_headers(), method="PATCH")
    else:
        url = f"https://api.github.com/repos/{repo}/issues/{pr_number}/comments"
        req = urllib.request.Request(url, data=payload, headers=_headers(), method="POST")
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read())


def resolve_comment(repo, pr_number, marker, msg):
    """Replace an existing marker comment with a resolved message.

    No-ops when no comment with that marker exists so a clean-from-the-start
    PR never gets any bot comments at all.
    """
    comment_id = find_comment(repo, pr_number, marker)
    if not comment_id:
        return
    payload = json.dumps({"body": f"{marker}\n{msg}"}).encode()
    url = f"https://api.github.com/repos/{repo}/issues/comments/{comment_id}"
    req = urllib.request.Request(url, data=payload, headers=_headers(), method="PATCH")
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read())
