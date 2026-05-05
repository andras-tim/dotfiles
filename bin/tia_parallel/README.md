# tia-parallel

Run shell commands in parallel with live status and scrollable output.

## Architecture

- Log output scrolls naturally in the terminal (printed above the live status bar).
- A status bar at the bottom (Rich Live) shows only currently-running jobs.
- Job start and completion events are printed into the scrollable log area.

## Key behaviors

- **Exit codes**: standard Unix `128 + signal` on abort (SIGINT → 130, SIGTERM → 143). `1` if any job failed, else `0`.
- **Abort flow** (SIGINT/SIGTERM):
  1. Live status bar is stopped.
  2. `⚠ Signal received: SIG…` is printed.
  3. Waiting jobs (queued on the semaphore) print `✗ cancelled`.
  4. Running jobs are killed via `SIGTERM` → `SIGKILL` (3s grace) on the process group, and print `✗ aborted - runtime: H:MM:SS.mmm`.
  5. Process exits with `128 + signal`.
- **Signal handling** uses asyncio's `loop.add_signal_handler` (not Python's default `signal.signal`) — this prevents `KeyboardInterrupt` traceback and gives clean ordering of the abort messages.
- **Status bar fragment workaround**: Rich's transient `Live` cleanup is off-by-one (moves cursor up `height - 1` instead of `height`), leaving the top border. After `live.stop()` we erase one extra line via `rich.control.Control` (`CURSOR_UP`, `ERASE_IN_LINE`, `CURSOR_MOVE_TO_COLUMN`). If Rich ever fixes this, the workaround will overcorrect by one line.
- **Job state on abort**: WAITING jobs (still on the semaphore) get the outer `CancelledError` → `cancelled`. RUNNING jobs (process active) get the inner `CancelledError` → `aborted` with runtime.
- **`--fail-fast`** (`-x`): on first job failure, cancel waiting jobs and abort running ones (same flow as a SIGINT, but exits with `1`, not `130`). Prints `⚠ Aborting on first failure: <label>`.
- **`--normalize-cr`** (`-r`): converts `\r\n` → `\n` then remaining `\r` → `\n` for tools that use `\r` for progress lines.
- **`--timestamps`** (`-t`): prefixes every line (including ABORT) with a timestamp. Bare `-t` (or `-t` placed where nothing trailing can be parsed as its value) uses default format `YYYY-mm-dd HH:MM:SS`. Pass a custom strftime format with `-t %H:%M:%S` (space-separated) or `--timestamps=%H:%M:%S` (long form with `=`). Click's short-option parser does NOT accept `-t=FORMAT`.
- **Duration format**: `H:MM:SS` for status bar elapsed, `H:MM:SS.mmm` for completion messages.
- **`--timeout SECS`**: per-job timeout in seconds. No timeout by default — jobs run until they finish or are aborted.

## Maintenance

- **README.md**: must document every key feature and flag.
- **Tests**: behavioral contracts (expectations) belong in tests, not in prose. When changing user-visible behavior or adding a flag, update the README **and** add/update a test.

## QA

```
make -C ~/dotfiles/bin/tia_parallel qa
```
