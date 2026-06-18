#!/usr/bin/env python3
"""Check npm dependencies against the latest published versions via the npm registry.

Writes two JSON files:
  <tmp>/npm-too-new.json   — installed packages younger than 24 h (FAIL)
  <tmp>/npm-outdated.json  — packages with a newer version available (WARN)
Both are consumed by post_npm_comment.py and fail_on_npm_errors.py.
"""

import json
import os
import re
import subprocess
import tempfile
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from functools import lru_cache

IS_CI = bool(os.environ.get("GITHUB_ACTIONS"))
TMP = tempfile.gettempdir()
MIN_AGE_SECONDS = 86400  # pnpm default: packages must be >= 24 h old


@lru_cache(maxsize=None)
def _fetch_registry(pkg_name):
    """Return the full npm registry document for a package, or {}."""
    encoded = urllib.parse.quote(pkg_name, safe="@/")
    try:
        with urllib.request.urlopen(f"https://registry.npmjs.org/{encoded}", timeout=15) as resp:
            return json.loads(resp.read())
    except Exception:
        return {}


def _latest_version(pkg_name):
    return _fetch_registry(pkg_name).get("dist-tags", {}).get("latest", "")


def _time_map(pkg_name):
    return _fetch_registry(pkg_name).get("time", {})


def _parse_version(s):
    parts = re.findall(r"\d+", s)
    return tuple(int(x) for x in parts) if parts else (0,)


def _age_seconds(iso):
    published = datetime.fromisoformat(iso.replace("Z", "+00:00"))
    return int((datetime.now(timezone.utc) - published).total_seconds())


def _format_age(seconds):
    if seconds < 3600:
        return f"{seconds // 60} minute(s) ago"
    if seconds < 86400:
        return f"{seconds // 3600} hour(s) ago"
    return f"{seconds // 86400} day(s) ago"


def _get_installed():
    """Return {pkg_name: version} for all direct dependencies via pnpm list."""
    result = subprocess.run(
        ["pnpm", "list", "--json", "--depth=0"],
        capture_output=True,
        text=True,
        shell=(os.name == "nt"),
    )
    installed = {}
    for project in json.loads(result.stdout or "[]"):
        for dep_type in ("dependencies", "devDependencies", "optionalDependencies"):
            for name, info in project.get(dep_type, {}).items():
                installed[name] = info["version"]
    return installed


def check_npm_too_new(installed):
    """Return packages whose currently installed version is younger than 24 hours."""
    too_new = []
    print("=== npm install age check (24 h minimum) ===")
    for name in sorted(installed):
        version = installed[name]
        iso = _time_map(name).get(version, "")
        if not iso:
            print(f"INFO: Could not check age of {name}@{version}")
            continue
        age = _age_seconds(iso)
        age_str = _format_age(age)
        if age < MIN_AGE_SECONDS:
            if IS_CI:
                print(f"::error file=package.json::{name}@{version} was published {age_str} — pnpm requires packages >= 24 h old")
            print(f"FAIL: {name}@{version} published {age_str}")
            too_new.append({"package": name, "version": version, "age": age_str})
        else:
            print(f"OK:   {name}@{version} ({age_str})")

    if too_new:
        print(f"\n{len(too_new)} package(s) younger than 24 hours.")
    else:
        print("\nAll installed packages meet the 24 h minimum age.")
    return too_new


def check_npm_outdated(installed):
    """Return packages with a newer version available on npm.

    Queries the registry directly instead of pnpm outdated so that versions
    younger than 24 h (which pnpm silently suppresses) are still surfaced.
    """
    outdated = []
    print("\n=== npm dependency version check ===")
    for name in sorted(installed):
        current = installed[name]
        latest = _latest_version(name)
        if not latest:
            print(f"INFO: Could not fetch latest version for {name}")
            continue
        if _parse_version(latest) <= _parse_version(current):
            print(f"OK:   {name} at {current} (latest: {latest})")
            continue
        iso = _time_map(name).get(latest, "")
        age = _age_seconds(iso) if iso else None
        released = _format_age(age) if age is not None else "unknown"
        too_young = age is not None and age < MIN_AGE_SECONDS
        if IS_CI:
            print(f"::warning file=package.json::{name}: {current} — latest is {latest} (released {released}{'  — too young for pnpm' if too_young else ''})")
        print(f"WARN: {name}: {current} -> {latest} (released {released}{'  — too young for pnpm' if too_young else ''})")
        outdated.append({"package": name, "current": current, "latest": latest, "released": released, "too_young": too_young})

    if outdated:
        print(f"\n{len(outdated)} outdated npm package(s) found.")
    else:
        print("\nAll checked npm dependencies are up to date.")
    return outdated


if __name__ == "__main__":
    installed = _get_installed()
    too_new = check_npm_too_new(installed)
    outdated = check_npm_outdated(installed)

    with open(os.path.join(TMP, "npm-too-new.json"), "w") as f:
        json.dump(too_new, f)
    with open(os.path.join(TMP, "npm-outdated.json"), "w") as f:
        json.dump(outdated, f)
