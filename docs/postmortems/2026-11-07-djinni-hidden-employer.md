# Postmortem: the first full parse failed on Djinni vacancies with a hidden employer

- **Date:** 2026-11-07
- **Duration / impact:** the daily run was red until the fix was merged. No data lost (bronze was
  already saved), no silver or gold built for that day. Nobody consumed the data yet.
- **Detected by:** a person: the first manual run of `pipeline-daily` with the new parse step was
  red. There was no alert at the time.

## What happened
- The first manual run of the daily workflow with the parse step scraped and saved bronze, then
  parsed 6,885 vacancies in about 87 seconds.
- The `Parse into silver` step then failed: 5 of 5,692 Djinni pages could not be parsed.
- The log showed that on those pages the JSON-LD field `hiringOrganization` is not an object with a
  name but the bare string `"confidential"`. The parser expected an object and raised.

## Root cause
- The parser assumed a shape of the data that was true for every page in the samples we had. An
  employer who hides the name is a normal case on the site, and it was not in the fixtures.
- Any unreadable page failed the whole run, so five odd pages out of 5,692 decided the result for
  all the others. Nothing distinguished "the site changed its markup" from "a few unusual pages".
- Deduplication compares vacancies of the same company. All hidden employers share the name
  "confidential", so, once parsed, they would have been merged into one group.

## What went well
- The workflow saves bronze before the parse step, so the failure lost no scraped data and the
  re-parse needed no network.
- The log named the page type and the field, so the cause was found from the run output alone.

## What did not
- Found by someone opening the run, not by an alert.
- The behaviour of the parser on unusual pages was not tested.

## Fix
PR #13: a string employer is accepted as the company name; hidden employers are never compared in
deduplication; a run fails only when more than 5% of a day's pages are unreadable; a recent day
with unreadable pages is parsed again after a parser fix.

## Follow-ups
- [x] A fixture and a test for a hidden employer (PR #13).
- [x] A check that separates "a few odd pages" from "the markup changed": `parse_failures` in
      `jobmarket dq` (warn 1%, error 5%), stored in `ops_dq_results`.
- [ ] A failed run is reported without anyone opening Actions: the Telegram message names the failed
      step and the check that said why. Implemented; it works once `TELEGRAM_BOT_TOKEN` and
      `TELEGRAM_CHAT_ID` are set as GitHub secrets (see docs/observability.md).
- [ ] Keep a real unreadable page when one appears, as a fixture, so each new page type becomes a test.
