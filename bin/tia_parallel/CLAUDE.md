# tia_parallel — Claude instructions

## Dev notes

- `live.console.print()` is the key: it erases the live display, prints the line into
  the terminal scroll buffer, then redraws — do not replace with `console.print()`.
- `StatusDisplay.__rich__()` is called every refresh; keep it cheap.

## Agentic notes

- Do not restore a log panel; log lines must reach the terminal scroll buffer so the
  user can scroll back. That is why `live.console.print()` is used, not `console.print()`.
- All output modes (live, no-status, quiet) share `_run()` via a `print_fn` callback.
  Quiet passes a no-op, but `Reporter.summary()` still runs independently at the end.
- Status bar shows only RUNNING jobs; the scrollable log is the record for the rest.
- `-b` buffering is per-job to prevent interleaving across parallel executions.
  The end-of-job status message is always printed after the final flush.
