# Branches

One long-lived branch, `main`, and `data` (not code: the published export the site reads; the workflow
rewrites it, never delete or edit it by hand).

## Day to day: commit to `main`

1. `git switch main && git pull`, change, run the checks (`make lint`, `make test`).
2. `git commit` and `git push` straight to `main`. No pull request, no waiting for a merge.
3. `ci.yml` runs on the push (lint, types, tests, the dashboard image); its `deploy` job asks Render to
   deploy **only if those pass**. The site is updated about 10-15 minutes later (the image is rebuilt).

A pull request is for a change worth a second look first, or for anyone but the owner: `main` is
protected (the checks `checks` and `docker` must pass before a merge), and the owner may push past that;
a PR is merged with **squash**.

## A broken push

CI is red and nothing is deployed, so the site keeps the last good version (set Render's auto-deploy to
"After CI checks pass" so that its own deploy on a push waits as well). Fix forward with another commit,
or `git revert <commit>` and push.

## History

For a few days there was a second branch, `develop`, with release PRs into `main`; it was dropped: the
site is small, there is one author, and every release (a squash in practice) made the two diverge.
Before that every change was a PR; with one author it was a click per change and no review.
