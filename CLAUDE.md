# dotfiles — Claude instructions

## Purpose

Personal dotfiles managed by [dotbot](https://github.com/anishathalye/dotbot).

## Installing / updating

```bash
./install          # applies default.conf.yaml (home configs + scripts)
```

Dotbot creates symlinks and runs any shell hooks listed in the yaml.

## Terminal+tmux wrapper pattern

For X11 terminals, prefer a `bin/<term>-tmux` wrapper that hands `tmux new-session -A -s main` to `-e`. The `-A` flag makes tmux attach if `main` exists, else create. Use `exec` since the shell is just a launcher.

## Code style preferences

- **Look for native config first.** Before proposing a wrapper script, check whether the tool has a CLI flag, X resource, env var, or config file that does the job. The user pushes back on wrappers when a native option exists (e.g., `tmux new-session -A` replaced a hand-rolled `has_session` helper).
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
