# Branches

One long-lived branch, `main`, and short-lived ones for the work itself.

| Branch | What it is |
|---|---|
| `main` | What runs: Render deploys it, the nightly and hourly workflows run from it (scheduled workflows always use the default branch). Always green. |
| `data` | Not code: the published export that the site reads. The workflow rewrites it. Never delete or edit it by hand. |
| `feat/*`, `fix/*`, `docs/*`, `chore/*` | One piece of work, branched from `main`, deleted after the merge. |

## Day to day

1. `git switch main && git pull`, then `git switch -c feat/what-it-does`.
2. Open the PR **against `main`** (`gh pr create`). CI runs; merge it with **squash**.
3. After the merge `ci.yml` runs on `main`, its `deploy` job asks Render to deploy, and the branch is
   deleted (GitHub does it: Settings > General > "Automatically delete head branches").

One PR is one deploy. A fix that cannot wait is the same flow: a short branch, a PR, a squash.

## History

For a few days there was a second branch, `develop`, with release PRs into `main`. It was dropped: the
site is small, there is one author, and every release (a squash in practice) made the two branches
diverge and need a manual merge. A single trunk is faster and has nothing to keep in step.
