#!/usr/bin/env python3
"""Check NODE, PNPM and runner versions across all config files.

Sources checked:
  NODE   : package.json (engines.node), workflow setup-node steps
  PNPM   : package.json (packageManager), workflow pnpm/action-setup steps (explicit version: only)
  Runner : all workflow runs-on values — warn when Ubuntu runner versions are mixed

Version mismatches between files are hard failures; outdated versions and runner
inconsistency are warnings (non-blocking).

Writes:
  <tmp>/runtime-version-conflicts.json  — version mismatches across files (FAIL)
  <tmp>/runtime-version-warnings.json   — outdated versions or runner inconsistency (WARN)
"""

import glob
import json
import os
import re
import tempfile
import urllib.request

IS_CI = bool(os.environ.get("GITHUB_ACTIONS"))
TMP = tempfile.gettempdir()


def parse_version(s):
    parts = re.findall(r"\d+", s)
    return tuple(int(x) for x in parts) if parts else (0,)


def fetch_latest_node_in_major(major):
    url = "https://nodejs.org/dist/index.json"
    with urllib.request.urlopen(url, timeout=15) as r:
        releases = json.loads(r.read())
    for rel in releases:
        v = rel["version"].lstrip("v")
        if re.match(rf"^{re.escape(major)}\.\d+\.\d+$", v):
            return v
    return None


def fetch_latest_pnpm():
    url = "https://registry.npmjs.org/pnpm/latest"
    with urllib.request.urlopen(url, timeout=15) as r:
        return json.loads(r.read())["version"]


# ---------------------------------------------------------------------------
# Extraction helpers
# ---------------------------------------------------------------------------

def extract_package_json():
    """Return {runtime: {version, label, ann_file}} from package.json."""
    with open("package.json") as f:
        pkg = json.load(f)
    result = {}
    node_ver = (pkg.get("engines") or {}).get("node", "").strip()
    if node_ver:
        result["node"] = {"version": node_ver, "label": "package.json (engines.node)", "ann_file": "package.json"}
    m = re.match(r"pnpm@([\d.]+)", pkg.get("packageManager", ""))
    if m:
        result["pnpm"] = {"version": m.group(1), "label": "package.json (packageManager)", "ann_file": "package.json"}
    return result


def extract_workflows():
    """Return (version_entries, runner_entries) from all .github/workflows/*.yml files.

    version_entries: [{runtime, version, label, ann_file, ann_line}]
    runner_entries:  [{runner, ann_file, ann_line}]
    """
    version_entries = []
    runner_entries = []

    for path in sorted(
        glob.glob(".github/workflows/*.yml") + glob.glob(".github/workflows/*.yaml")
    ):
        fname = path.replace("\\", "/").split("/")[-1]
        ann_file = f".github/workflows/{fname}"
        with open(path) as f:
            lines = f.readlines()

        i = 0
        while i < len(lines):
            line = lines[i]

            # runs-on
            m = re.match(r"[ \t]+runs-on:\s+(.+)", line)
            if m:
                runner = m.group(1).strip().strip("\"'")
                runner_entries.append({"runner": runner, "ann_file": ann_file, "ann_line": i + 1})

            # setup-node -> look ahead for node-version:
            elif re.search(r"uses:\s+actions/setup-node@", line):
                j = i + 1
                while j < len(lines):
                    s = lines[j].rstrip()
                    if re.match(r"[ \t]+-[ \t]+(name|uses|if|run|env|with|id):", s):
                        break
                    m = re.match(r'[ \t]+node-version:\s+"?([\d.]+)"?', s)
                    if m:
                        version_entries.append({
                            "runtime": "node",
                            "version": m.group(1),
                            "label": f"{fname}:{j+1} (setup-node node-version)",
                            "ann_file": ann_file,
                            "ann_line": j + 1,
                        })
                        break
                    j += 1

            # pnpm/action-setup -> look ahead for explicit version:
            elif re.search(r"uses:\s+pnpm/action-setup@", line):
                j = i + 1
                while j < len(lines):
                    s = lines[j].rstrip()
                    if re.match(r"[ \t]+-[ \t]+(name|uses|if|run|env|with|id):", s):
                        break
                    m = re.match(r'[ \t]+version:\s+"?([\d.]+)"?', s)
                    if m:
                        version_entries.append({
                            "runtime": "pnpm",
                            "version": m.group(1),
                            "label": f"{fname}:{j+1} (pnpm/action-setup version)",
                            "ann_file": ann_file,
                            "ann_line": j + 1,
                        })
                        break
                    j += 1

            i += 1

    return version_entries, runner_entries


# ---------------------------------------------------------------------------
# Checks
# ---------------------------------------------------------------------------

def check_versions(all_versions):
    conflicts = []
    warnings = []

    for runtime in ("node", "pnpm"):
        entries = all_versions[runtime]
        if not entries:
            print(f"INFO: No {runtime.upper()} version declarations found — skipping.")
            continue

        print(f"\n=== {runtime.upper()} version consistency ===")
        for e in entries:
            print(f"  {e['label']}: {e['version']}")

        unique = set(e["version"] for e in entries)
        if len(unique) > 1:
            if IS_CI:
                for e in entries:
                    loc = f"file={e['ann_file']}"
                    if e.get("ann_line"):
                        loc += f",line={e['ann_line']}"
                    print(
                        f"::error {loc}::{runtime.upper()} {e['version']} — "
                        f"inconsistent across files: {', '.join(sorted(unique))}"
                    )
            print(f"FAIL: {runtime.upper()} has conflicting versions: {', '.join(sorted(unique))}")
            conflicts.append({"runtime": runtime, "found": sorted(unique), "entries": entries})
        else:
            print(f"OK: {runtime.upper()} is consistently {entries[0]['version']} across {len(entries)} declaration(s).")

        canonical = entries[0]["version"]
        major = canonical.split(".")[0]
        try:
            latest = fetch_latest_node_in_major(major) if runtime == "node" else fetch_latest_pnpm()
            if latest and parse_version(latest) > parse_version(canonical):
                if IS_CI:
                    print(
                        f"::warning file=package.json::"
                        f"{runtime.upper()} {canonical} — latest {major}.x is {latest}"
                    )
                print(f"WARN: {runtime.upper()} latest is {latest}, currently using {canonical}")
                warnings.append({"type": f"{runtime}-outdated", "current": canonical, "latest": latest})
            elif latest:
                print(f"OK: {runtime.upper()} {canonical} is up to date (latest {major}.x: {latest})")
        except Exception as e:
            print(f"INFO: Could not check latest {runtime.upper()}: {e}")

    return conflicts, warnings


def check_runners(runner_entries):
    print("\n=== Runner version consistency ===")
    ubuntu = [e for e in runner_entries if "ubuntu" in e["runner"].lower()]
    unique = set(e["runner"] for e in ubuntu)

    if len(unique) > 1:
        if IS_CI:
            for e in ubuntu:
                print(
                    f"::warning file={e['ann_file']},line={e['ann_line']}::"
                    f"Runner '{e['runner']}' — multiple Ubuntu versions in use: "
                    f"{', '.join(sorted(unique))}"
                )
        print(f"WARN: Multiple Ubuntu runner versions: {', '.join(sorted(unique))}")
        return {"type": "runner-inconsistency", "found": sorted(unique), "entries": ubuntu}
    elif ubuntu:
        print(f"OK: All Ubuntu runners consistently use '{ubuntu[0]['runner']}'.")
    else:
        print("INFO: No Ubuntu runners detected.")
    return None


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    pkg = extract_package_json()
    workflow_versions, runner_entries = extract_workflows()

    all_versions = {"node": [], "pnpm": []}
    for runtime, entry in pkg.items():
        all_versions[runtime].append(entry)
    for e in workflow_versions:
        all_versions[e["runtime"]].append(e)

    conflicts, warnings = check_versions(all_versions)

    runner_issue = check_runners(runner_entries)
    if runner_issue:
        warnings.append(runner_issue)

    with open(os.path.join(TMP, "runtime-version-conflicts.json"), "w") as f:
        json.dump(conflicts, f)
    with open(os.path.join(TMP, "runtime-version-warnings.json"), "w") as f:
        json.dump(warnings, f)
