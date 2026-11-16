# Branches

Two long-lived branches, plus short-lived ones for the work itself.

| Branch | What it is | Who writes to it |
|---|---|---|
| `main` | What runs: Render deploys it, the nightly and hourly workflows run from it (scheduled workflows always use the default branch). | Only a **release** PR from `develop`. |
| `develop` | Where finished work lands first; always green. | Pull requests from short-lived branches. |
| `data` | Not code: the published export that the site reads. The workflow rewrites it. Never delete or edit it by hand. | `publish-data` only. |
| `feat/*`, `fix/*`, `docs/*`, `chore/*` | One piece of work, branched from `develop`. | One author, deleted after the merge. |

## Day to day

1. `git switch develop && git pull`, then `git switch -c feat/what-it-does`.
2. Open the PR **against `develop`** (`gh pr create --base develop`). CI runs; merge it with **squash**.
3. Delete the branch after the merge (GitHub can do it: Settings > General > "Automatically delete head branches").

## Release (develop to main)

1. Open a PR from `develop` into `main` (`gh pr create --base main --head develop`).
2. Merge it with **"Create a merge commit"**, never squash: a squash gives `main` a commit that
   `develop` does not have, and the next release then conflicts on the same lines again.
3. After the merge `ci.yml` runs on `main`, the `deploy` job asks Render to deploy, and `main` is back
   in `develop` with `git switch develop && git merge main` only if `main` got a hotfix.

A fix that cannot wait (the site is broken) may branch from `main` and go to `main` directly; merge `main`
into `develop` right after, so the two do not drift.

## Why

PRs that are open at the same time used to conflict in `CHANGELOG.md` and in the stylesheet, and every
merge to a single `main` deployed at once. With `develop` several changes can be tried together and
deployed in one go, and `main` always holds something that was green as a whole.
