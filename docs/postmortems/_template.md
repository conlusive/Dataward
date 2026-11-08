# Postmortem: <one line: what broke>

- **Date:** YYYY-MM-DD
- **Duration / impact:** how long, which data or consumers were affected (or "none")
- **Detected by:** an alert, a failed run, a person looking at a table; how long after it started

## What happened
A short timeline in UTC. Facts, no blame.

## Root cause
The condition that made it possible, not only the line of code. Ask "why" until it is about a
missing check, a wrong assumption or a missing test.

## What went well
What limited the damage (for example: raw data was saved before the failing step).

## What did not
What made it worse or slower to find.

## Fix
Link to the PR. What changed in the code and in the tests.

## Follow-ups
- [ ] action, owner, how we will know it is done
