# MentorFilou/version-checks

A GitHub Action (and reusable-workflow wrapper) that keeps a repository's pinned versions up to date, consistent, and securely pinned - and reports findings as a single, self-updating PR comment per problem type.

It checks:

1. **GitHub Action pins** in `.github/workflows/*.yml`
   - must be pinned to a full commit SHA (FAIL if not),
   - the SHA must resolve to the version in the trailing `# vX.Y.Z` comment (FAIL on mismatch),
   - the same action must not be pinned to different SHAs across files (FAIL on conflict),
   - warns when a newer release is available.
2. **npm dependencies** (pnpm projects) - warns on outdated packages and **fails** on packages younger than 24 h (pnpm's minimum age).
3. **Runtime versions** - NODE / PNPM declared in `package.json` and workflow files must agree (FAIL on mismatch); warns on outdated versions and mixed Ubuntu runners.

## Usage

You should pin it to a full commit SHA for stricter supply-chain hygiene (e.g. `@<40-char-sha> # vX.Y.Z`).

> Why would I do this? [Read about it on the official GitHub Blog.](https://github.blog/changelog/2025-08-15-github-actions-policy-now-supports-blocking-and-sha-pinning-actions/#enforce-sha-pinning)

There are two ways to embed and use these version-checks.

### A) Composite action (as a step); recommended due to more control

Add it as a step inside your own job (for example on pull requests to main). You control the [runner](https://docs.github.com/en/actions/reference/runners/github-hosted-runners#standard-github-hosted-runners-for--private-repositories), [checkout](https://github.com/actions/checkout) and [permissions](https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax?versionId=free-pro-team%40latest&productId=actions&restPage=tutorials%2Ccreate-an-example-workflow#permissions):

```yaml
name: Version Checks

on:
  pull_request:
    branches: [main]

jobs:
  version-checks:
    runs-on: ubuntu-24.04
    permissions:
      contents: read
      pull-requests: write
    steps:
      - uses: actions/checkout@df4cb1c069e1874edd31b4311f1884172cec0e10 # v6.0.3
      - uses: MentorFilou/version-checks@sha # vX.Y.Z
        with:
          check-npm: "false"   # e.g. not a pnpm project
          check-runtime: "false"
```

Replace the sha and version accordingly. The action's checks then run sequentially in your job. 

### B) Reusable workflow (as a job); zero boilerplate

Reference it at the job level; it does its own checkout and runs the checks as parallel jobs:

```yaml
name: Version Checks

on:
  pull_request:
    branches: [main]

jobs:
  version-checks:
    uses: MentorFilou/version-checks/.github/workflows/version-checks.yml@sha # vX.Y.Z
    permissions:
      contents: read
      pull-requests: write
    with:
      check-npm: false
      check-runtime: false
```

Replace the sha and version accordingly.

### Inputs

All inputs are optional. (Booleans are strings for the action - `"true"`/`"false"` - but real booleans for the reusable workflow. That divergance is GitHub-controlled.)

| Input | Default | Description |
|-------|---------|-------------|
| `check-actions` | `true` | Check GitHub Action SHA pins. |
| `check-npm` | `true` | Check npm dependency versions and age. Requires a pnpm project! |
| `check-runtime` | `true` | Check NODE / PNPM / runner consistency. Requires `package.json`! |
| `node-version-file` | `package.json` | File that `setup-node` reads the Node version from (npm check only). |
| `pnpm-version` | `""` | Explicit pnpm version; if empty reads `packageManager` from `package.json`. |
| `github-token` | `${{ github.token }}` | Token for API calls / PR comments. **Action only.** |
| `setup-pnpm` | `"true"` | Let the action set up pnpm + Node for the npm check. **Action only.** |
| `runner` | `ubuntu-24.04` | Runner to execute on. **Reusable workflow only.** |

### Requirements

- Call it from a `pull_request`-triggered workflow - the bot comments target the PR.
- The job must grant `contents: read` and `pull-requests: write`.
- `GITHUB_TOKEN` (used automatically) is sufficient; no extra secrets needed.

## How it works

The engine is a **composite action** ([action.yml](action.yml)); the reusable
workflow is a thin wrapper around it. The checks are plain Python scripts that
use only the standard library plus the `pnpm` CLI (for the npm check) and run
against your checked-out repository. See [scripts/README.md](scripts/README.md)
for details.

## License

This project is licensed under the [MIT License specified in the LICENSE file](LICENSE).
