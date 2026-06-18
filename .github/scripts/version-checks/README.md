# `./github/scripts/version-checks/`

This folder solely serves `.github/workflows/version-checks.yml` providing different scripts for all the tasks in its jobs.

You can locally run the _important parts_ of this workflow by using `pnpm run check:versions`

That workflow checks some versions for ...

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

> If you know this version-checks/ script setup from another repository, note that the version in [this repository](../../../README.md) does NOT include Docker checks. These were intentionally removed as we're not using any Docker files here.
