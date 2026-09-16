# Demo Script (60-90 seconds)

A natural, technically credible walkthrough for a screen recording.

---

**[Show the project folder / README in an editor]**

"This is a Python and Playwright automation bot that demonstrates a
full lead-generation pipeline — the kind of thing I'd build for a client
who needs data pulled from a web portal and synced into a CRM like
GoHighLevel. It's structured in layers: browser automation, data
extraction, validation, and a CRM API client — each one independently
testable."

**[Run `python main.py` in the terminal, let the browser automation start]**

"I'll run it live. It's launching Chromium and navigating to a public
book catalog site that's built specifically for scraping practice — no
logins, no CAPTCHAs, nothing being bypassed. It's filtering to a category,
and paginating through the results."

**[Point at the scrolling log output — PAGE_LOADED, RECORD_EXTRACTED, RECORD_VALIDATED lines]**

"Every stage logs a clear marker — page loaded, record extracted, record
validated — so you can see exactly what the bot is doing at each step.
It's following each listing into its product page to pull a real unique
ID, description, and category, not just scraping the summary card."

**[Show a screenshot in `screenshots/`, or `docs/demo-screenshot.png` if showing the repo]**

"It also saves a screenshot as proof of a real run, not a mocked one —
there's a committed example of that, plus a full sample JSON output, right
in the repo's `docs/` folder and linked from the README."

**[Point at a CRM_SYNC_RETRY line if one appears]**

"Here you can see it hit a simulated transient failure while syncing to
the CRM, and automatically retried with backoff — that's the reliability
layer, not just a happy-path demo."

**[Let it finish, show the run summary in the terminal]**

"And here's the run summary — records discovered, extracted, rejected,
duplicates skipped, CRM sync successes and failures, total time. This
matches exactly what got written to a JSON file."

**[Open `output/run_*.json` and scroll to one record]**

"This is the structured output — clean, typed data, validation status,
and the CRM sync result all sitting next to each other for each record."

**[Optionally show the Mermaid architecture diagram in the README]**

"The architecture is deliberately modular: the browser layer only produces
raw records, validation only cleans and checks them, and the CRM client
only knows how to push a payload with retries. That separation is what
makes it straightforward to point this at a different site or swap in a
real GoHighLevel account — it's mock mode by default so this demo needs
zero credentials, but the live HTTP path with auth headers and retry
logic is already fully implemented and unit tested."

**[Close]**

"That's the full pipeline — web portal to CRM, with validation,
deduplication, retries, and logging in between."

---

## Notes for recording

- Run with default settings (`python main.py`) — no `.env` needed.
- The run takes roughly 10-15 seconds end to end; if recording live,
  consider trimming the middle of the log scroll in post.
- Have `output/` and `screenshots/` visible in a file explorer/sidebar
  ahead of time so you can cut to them quickly after the run finishes.
- If you want to show the test suite too, add: `python -m pytest -v`
  before or after the main run, and note "35 tests covering the
  validation and CRM logic independent of the live site."
