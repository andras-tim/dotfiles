# dotfiles — Claude instructions

## Purpose

Personal dotfiles managed by [dotbot](https://github.com/anishathalye/dotbot).

## Installing / updating

```bash
./install          # applies default.conf.yaml (home configs + scripts)
```

Dotbot creates symlinks and runs any shell hooks listed in the yaml.

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
