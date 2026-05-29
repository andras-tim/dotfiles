# dotfiles — Claude instructions

## Purpose

Personal dotfiles managed by [dotbot](https://github.com/anishathalye/dotbot).

## Installing / updating

```bash
./install           # default.conf.yaml — shell, VCS, console-app configs (universal)
./install desktop   # desktop.conf.yaml — X11 (Xdefaults, openbox, xbindkeys, xfce4)
./install termux    # termux.conf.yaml — Termux/Android (tm-x11, termux-x11 prefs)
```

Each profile reads its own yaml. Some configs are platform-conditional — e.g., openbox lives under `desktop` (used both on Linux and on Android via Termux:X11).

Dotbot creates symlinks and runs any shell hooks listed in the yaml.

## Platforms

Repo targets **two environments**: Linux desktop and Termux on Android (with Termux:X11 for GUI). When adding config:

- Universal (shell, git, vim, tmux) → `default.conf.yaml`
- X11 GUI (terminal, WM, xresources) → `desktop.conf.yaml` — works on both Linux X and Termux:X11
- Termux/Android-only (tm-x11 wrapper, termux-x11 prefs) → `termux.conf.yaml`
- One-time Android bootstrap (apk check, pkg install) → `android/setup-termux-x11.sh`

## Termux:X11 entry point — `bin/tm-x11`

`tm-x11` is the X11 session launcher on Android. Pattern:

1. **start1**: `am start` the Termux:X11 activity
2. **start2**: restore prefs from `~/.config/termux-x11.prefs` (`termux-x11-preference < file`)
3. **start3**: run `termux-x11 :0 -xstartup openbox-session "$@"` in foreground
4. **trap EXIT**: dump prefs back to file + `am broadcast ACTION_STOP` to close the Android window

The prefs file is tracked in dotfiles. UI changes during a session are captured on exit.

## Terminal+tmux wrapper pattern

For X11 terminals, prefer a `bin/<term>-tmux` wrapper that hands `tmux new-session -A -s main` to `-e`. The `-A` flag makes tmux attach if `main` exists, else create. Use `exec` since the shell is just a launcher.

Openbox keybindings (`openbox/rc.xml`) and menu (`openbox/menu.xml`) reference these wrappers, not the bare terminal binary.

## Code style preferences

- **Look for native config first.** Before proposing a wrapper script, check whether the tool has a CLI flag, X resource, env var, or config file that does the job. The user pushes back on wrappers when a native option exists (e.g., `tmux new-session -A` replaced a hand-rolled `has_session` helper; `-xstartup` on `termux-x11` replaced an env var hack).
- **Keep scripts minimal.** Use `exec` for single-command launchers (no idle bash process). Prefer one-line conditionals (`[ -f X ] && cmd`) over multi-line `if/fi` when expressing one fact. Use `trap cleanup EXIT` for paired setup/teardown instead of duplicated cleanup paths.
- **Don't reach for helper functions** when a one-liner is clear. If the script is short, leave it short.

## Adding a config file

Drop the file in the repo root (or a subdirectory), then add a `link:` entry in `default.conf.yaml`:

```yaml
- link:
    ~/.config/foo: foo.conf
```

## Adding a script

Drop the file in `bin/`, add a `link:` entry under the Scripts section of `default.conf.yaml`:

```yaml
    ~/bin/my-script: bin/my-script
```

Re-run `./install` to create the symlink.

## Subdirectory scripts (e.g. `bin/tia-parallel/`)

When a script has supporting files (tests, Makefile, conftest), keep them in a named subdirectory:

```
bin/
  tia-parallel/
    tia_parallel.py   ← the script
    Makefile          ← qa targets: make qa
    conftest.py       ← pytest helpers (if needed)
```

The link target in `default.conf.yaml` points to the script file directly:

```yaml
    ~/bin/tia-parallel: bin/tia-parallel/tia_parallel.py
```
