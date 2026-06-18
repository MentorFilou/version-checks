# `scripts/`

These scripts are the engine behind the reusable workflow defined in
`.github/workflows/version-checks.yml`. The workflow checks them out into
`.version-checks/scripts/` in the calling repository and runs them against that
repository's files. See the [root README](../README.md) for consumer usage.

They check some versions for ...

1. updates (resulting in WARNs)
2. using the same across multiple places (resulting in FAILs)
3. being pinned to a SHA in workflow files (resulting in FAILs)
4. correctly commenting those sha's (resulting in FAILs)

... to ensure being updated and consistent.

This is currently scanned in:

- `.github/workflows/*.yml` files for `uses:` (action pins),
- `.github/workflows/*.yml` files for `runs-on:` (runner versions),
- `.github/workflows/*.yml` files for `node-version:` / `pnpm version:` (runtime versions),
- `package.json` for `engines.node`, `packageManager`, `dependencies` and `devDependencies`,

It serves the result as errors (failing the job) or warnings; depending on type of check - both will lead to a helpful bot-comment on the PR thats consistently being updated whenever the job runs again.

Each `scan_*` script writes intermediate JSON to the system temp dir, which the
matching `post_*` / `fail_on_*` scripts read — so they must run in the same job.
The scripts depend only on the Python standard library, plus the `pnpm` CLI for
the npm check.

> This version-checks setup does NOT include Docker checks. Earlier copies in
> other repositories may differ.
