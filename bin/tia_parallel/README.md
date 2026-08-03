# tia-parallel

Run shell commands in parallel with live status and scrollable output.

## Usage

Work comes from one of three places. In every mode `-j N` caps concurrency and
`-Bb N` buffers each job's output, staggering the first flush across `N` seconds
so parallel progress lines don't interleave (`-B` = stagger, `-b N` = buffer).

- **stdin, one command per line** — each line runs as-is (no `--cmd`):
  ```sh
  ls *.sh | tia-parallel -j 4
  ```
- **`--cmd` template + items** — `{}` is replaced by each item, taken from
  positional args or stdin:
  ```sh
  tia-parallel -j 5 --cmd './deploy.sh {}' prod staging dev
  ```
- **`-L SEP` label/item split** — split each stdin line on the first `SEP`; the
  left part becomes the status-bar label, the right fills `{}`. Made for
  `label<TAB>arg` feeds:
  ```sh
  printf 'web\thost1\napi\thost2\n' | tia-parallel -L $'\t' --cmd 'ssh {} uptime'
  ```

### Example: parallel yt-dlp downloads

Each item is one video/URL; `-j 5 -Bb 5` runs five downloads at once with tidy,
staggered progress. `--newline` makes yt-dlp print progress on its own line so
the status bar can render it (no need for `-r`/`--normalize-cr`).

A whole playlist into one fixed folder — enumerate URLs, pipe them in:

```sh
yt-dlp --flat-playlist --print "%(url)s" "https://www.youtube.com/playlist?list=PLUD5ui3fFY-PabZDn2NPhQkF6H22Iays7" \
  | tia-parallel -j 5 -Bb 5 \
    --cmd 'yt-dlp -f "bestvideo[height<=1280][width<=1280]+bestaudio/best[height<=1280][width<=1280]" -S "res:720,+tbr" --cookies-from-browser chrome --merge-output-format mkv --remux-video mkv --js-runtimes node --newline --progress-delta 2 --windows-filenames --concurrent-fragments 2 -o "/mnt/server-tia/download/media/FUN/IceBlueBird/SteamPunk Gameplay/%(upload_date>%Y-%m-%d)s %(title)s [%(id)s].%(ext)s" {}'
```

A handful of specific videos as positional items (label is auto-derived):

```sh
tia-parallel -j 5 -Bb 5 \
  --cmd 'yt-dlp -f "bestvideo[height<=1280][width<=1280]+bestaudio/best[height<=1280][width<=1280]" -S "res:720,+tbr" --cookies-from-browser chrome --merge-output-format mkv --remux-video mkv --js-runtimes node --newline --progress-delta 2 --windows-filenames --concurrent-fragments 2 -o "/mnt/server-tia/download/media/FUN/IceBlueBird/Subnautica 2/%(upload_date>%Y-%m-%d)s %(title)s [%(id)s].%(ext)s" {}' \
  "https://www.youtube.com/watch?v=dKJkVkkQYb0" \
  "https://www.youtube.com/watch?v=H55p3e4HDzU" \
  "https://www.youtube.com/watch?v=WuJd0o674sQ"
```

Feed `title<TAB>url` pairs so each playlist's title becomes the job label, and
let yt-dlp bucket files into per-playlist folders. The four backslashes in the
`--replace-in-metadata` regex are required: the `--cmd` body is re-parsed by one
shell (`sh -c`), which collapses `\\\\` → `\\` (a literal backslash in the
character class) and `\"` → `"`, yielding `[|/\\:*?"<>#]`:

```sh
yt-dlp --flat-playlist --print "%(title)s"$'\t'"%(url)s" "https://www.youtube.com/@PerkyParrot/playlists" \
  | tia-parallel -L $'\t' -j 5 -Bb 5 \
    --cmd 'yt-dlp -f "bestvideo[height<=1280][width<=1280]+bestaudio/best[height<=1280][width<=1280]" -S "res:720,+tbr" --cookies-from-browser chrome --merge-output-format mkv --remux-video mkv --js-runtimes node --newline --progress-delta 2 --windows-filenames --replace-in-metadata "playlist_title" "[|/\\\\:*?\"<>#]" "_" --concurrent-fragments 2 -o "/mnt/server-tia/download/media/FUN/PerkyParrot/%(playlist_title)s/%(upload_date>%Y-%m-%d)s %(title)s [%(id)s].%(ext)s" {}'
```

When the destination folder is a literal (first two examples) you don't need
`%(playlist_title)s` or `--replace-in-metadata`; when bucketing by playlist
title (third) you do.

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
