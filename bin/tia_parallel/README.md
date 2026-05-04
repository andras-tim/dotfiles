# tia-parallel

Run shell commands in parallel with live status and scrollable output.

## Architecture

- Log output scrolls naturally in the terminal (printed above the live status bar).
- A status bar at the bottom (Rich Live) shows only currently-running jobs.
- Job start and completion events are printed into the scrollable log area.

## QA

```
make -C ~/dotfiles/bin/tia_parallel qa
```
