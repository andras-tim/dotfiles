#!/usr/bin/env python3
"""Run shell commands in parallel with live status and scrollable output.

NOTE on maintenance:
  - README.md must document every key feature and flag.
  - Behavioral contracts (expectations) belong in tests, not in prose.
  - When changing any user-visible behavior or adding a flag: update README AND add/update a test.
"""

import asyncio
import logging
import os
import signal
import sys
import time
from contextlib import nullcontext
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import PurePath
from typing import Any, Callable, ContextManager

logging.getLogger("asyncio").setLevel(logging.CRITICAL)

import click
from rich.console import Console, Group
from rich.control import Control, ControlType
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

console = Console()
err_console = Console(stderr=True)


# ── Data models ────────────────────────────────────────────────────────────────


class JobState(Enum):
    WAITING = "waiting"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"


@dataclass
class LogLine:
    job: "Job"
    fd: int
    text: str


@dataclass
class Job:
    cmd: str
    label: str
    state: JobState = JobState.WAITING
    rc: int | None = None
    started_at: float | None = None
    lines: list[LogLine] = field(default_factory=list)


# ── Live status display ─────────────────────────────────────────────────────────


class StatusDisplay:
    def __init__(self, jobs: list[Job]) -> None:
        self._jobs = jobs

    def __rich__(self) -> Panel:
        by: dict[JobState, list[Job]] = {s: [] for s in JobState}
        for job in self._jobs:
            by[job.state].append(job)

        r = len(by[JobState.RUNNING])
        w = len(by[JobState.WAITING])
        d = len(by[JobState.DONE])
        f = len(by[JobState.FAILED])
        total = len(self._jobs)
        completed = d + f

        bar_width = 24
        filled = round(bar_width * completed / total) if total else 0
        bar = Text()
        bar.append("█" * filled, style="green" if not f else "yellow")
        bar.append("░" * (bar_width - filled), style="dim")

        summary = Text.assemble(
            bar,
            ("  ", ""),
            (str(completed), "dim"),
            (f"/{total}  ", "dim"),
            (f"{r} ", "yellow"),
            ("executing  ", "yellow dim"),
            (f"{w} ", "dim"),
            ("waiting  ", "dim"),
            (f"{d} ", "green"),
            ("done  ", "green dim"),
            (f"{f} ", "red"),
            ("failed", "red dim"),
        )

        height = console.height or 40
        max_rows = max(height // 4 - 1, 1)
        visible = by[JobState.RUNNING][:max_rows]

        now = time.perf_counter()
        table = Table(box=None, padding=(0, 1), show_header=False, expand=True)
        table.add_column(justify="left")
        table.add_column(justify="right", style="dim")

        for job in visible:
            elapsed = _fmt_dur(now - job.started_at) if job.started_at else ""
            table.add_row(job.label, elapsed)

        return Panel(table, title=summary, border_style="dim", padding=(0, 1))


# ── Abort ──────────────────────────────────────────────────────────────────────


class _Aborted(Exception):
    def __init__(self, sig: int) -> None:
        self.sig = sig


# ── Formatting and buffering helpers ───────────────────────────────────────────


class MessageFormatter:
    """Builds Rich Text lines, optionally prefixed with a strftime timestamp."""

    def __init__(self, ts_format: str | None) -> None:
        self._ts_format = ts_format

    def _ts_prefix(self) -> list[tuple[str, str]]:
        if not self._ts_format:
            return []
        return [(datetime.now().strftime(self._ts_format) + " ", "dim")]

    def msg(self, *parts) -> Text:
        return Text.assemble(*self._ts_prefix(), *parts)


class OutputBuffer:
    """Per-job output buffer.

    buffer_secs == 0 → pass-through; > 0 → batch and flush on a timer
    that starts after `stagger_delay` seconds.
    """

    def __init__(self, print_fn, buffer_secs: int | float, stagger_delay: int | float) -> None:
        self._print_fn = print_fn
        self._buffer_secs = buffer_secs
        self._stagger_delay = stagger_delay
        self._buf: list[Text] = []
        self._flush_task: asyncio.Task | None = None

    def add(self, text: Text) -> None:
        if self._buffer_secs == 0:
            self._print_fn(text)
        else:
            self._buf.append(text)

    def flush(self) -> None:
        if not self._buf:
            return
        lines = self._buf[:]
        del self._buf[:]
        if len(lines) == 1:
            self._print_fn(lines[0])
        else:
            self._print_fn(Group(*lines))

    def start(self) -> None:
        if self._buffer_secs > 0:
            self._flush_task = asyncio.create_task(self._loop())

    def stop(self) -> None:
        if self._flush_task:
            self._flush_task.cancel()
        self.flush()

    async def _loop(self) -> None:
        await asyncio.sleep(self._stagger_delay)
        while True:
            self.flush()
            await asyncio.sleep(self._buffer_secs)


# ── Job runner ─────────────────────────────────────────────────────────────────


class JobRunner:
    """Runs a single Job: spawn → drain → finalize, with consistent status events."""

    def __init__(
        self,
        job: Job,
        sem: asyncio.Semaphore,
        formatter: MessageFormatter,
        print_fn,
        *,
        timeout: int | float | None,
        buffer_secs: int | float,
        stagger_delay: int | float,
        normalize_cr: bool,
    ) -> None:
        self.job = job
        self._sem = sem
        self._formatter = formatter
        self._print = print_fn
        self._timeout = timeout
        self._normalize_cr = normalize_cr
        self._out = OutputBuffer(print_fn, buffer_secs, stagger_delay)

    async def run(self) -> None:
        try:
            async with self._sem:
                self.job.state = JobState.RUNNING
                self.job.started_at = time.perf_counter()
                self._emit_started()

                proc = await self._spawn()
                self._out.start()
                assert proc.stdout and proc.stderr
                try:
                    await asyncio.wait_for(
                        asyncio.gather(
                            _drain_stream(proc.stdout, 1, self._on_line, normalize_cr=self._normalize_cr),
                            _drain_stream(proc.stderr, 2, self._on_line, normalize_cr=self._normalize_cr),
                        ),
                        timeout=self._timeout,
                    )
                    await proc.wait()
                    self.job.rc = proc.returncode
                    self.job.state = JobState.DONE if proc.returncode == 0 else JobState.FAILED
                    self._out.flush()
                    if self.job.state == JobState.DONE:
                        self._emit_done()
                    else:
                        self._emit_failed()
                except asyncio.TimeoutError:
                    await self._terminate(proc)
                    self.job.rc = -1
                    self.job.state = JobState.FAILED
                    self._out.flush()
                    self._emit_timeout()
                except asyncio.CancelledError:
                    await self._terminate(proc)
                    self._out.flush()
                    self.job.rc = -1
                    self.job.state = JobState.FAILED
                    self._emit_aborted()
                except Exception:
                    await self._terminate(proc)
                    raise
                finally:
                    self._out.stop()
        except asyncio.CancelledError:
            self.job.state = JobState.FAILED
            self._emit_cancelled()

    async def _spawn(self) -> asyncio.subprocess.Process:
        return await asyncio.create_subprocess_shell(
            self.job.cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            start_new_session=True,
        )

    @staticmethod
    async def _terminate(proc: asyncio.subprocess.Process) -> None:
        """SIGTERM the process group; SIGKILL whatever survives after 3 s."""
        try:
            pgid = os.getpgid(proc.pid)
            os.killpg(pgid, signal.SIGTERM)
            try:
                await asyncio.wait_for(proc.wait(), timeout=3)
                return
            except asyncio.TimeoutError:
                os.killpg(pgid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        await proc.wait()

    def _on_line(self, raw: bytes, fd: int) -> None:
        line = LogLine(job=self.job, fd=fd, text=raw.decode(errors="replace").rstrip())
        self.job.lines.append(line)
        self._out.add(self._formatter.msg(
            Text(f"{self.job.label} ", style="dim cyan"),
            Text(line.text, style="dim" if fd == 1 else "yellow"),
        ))

    def _runtime(self) -> str:
        assert self.job.started_at is not None
        return _fmt_dur(time.perf_counter() - self.job.started_at, ms=True)

    def _label_part(self) -> Text:
        return Text(f"{self.job.label} ", style="cyan")

    def _runtime_part(self) -> Text:
        return Text(f" - runtime: {self._runtime()}", style="dim")

    def _emit_started(self) -> None:
        self._print(self._formatter.msg(self._label_part(), Text("▶ started", style="dim")))

    def _emit_done(self) -> None:
        self._print(self._formatter.msg(
            self._label_part(),
            Text("✓ done", style="green"),
            self._runtime_part(),
        ))

    def _emit_failed(self) -> None:
        self._print(self._formatter.msg(
            self._label_part(),
            Text(f"✗ FAILED  rc={self.job.rc}", style="bold red"),
            self._runtime_part(),
        ))

    def _emit_timeout(self) -> None:
        self._print(self._formatter.msg(
            self._label_part(),
            Text(f"✗ TIMEOUT  ({self._timeout}s)", style="bold red"),
            self._runtime_part(),
        ))

    def _emit_aborted(self) -> None:
        self._print(self._formatter.msg(
            self._label_part(),
            Text("✗ aborted", style="bold red"),
            self._runtime_part(),
        ))

    def _emit_cancelled(self) -> None:
        self._print(self._formatter.msg(self._label_part(), Text("✗ cancelled", style="yellow")))


# ── Live display teardown ──────────────────────────────────────────────────────


def _erase_live_residue() -> None:
    """Erase the top border that Rich's transient Live leaves behind on early stop.

    Rich moves the cursor up height-1 lines when tearing down a transient Live
    region, leaving the panel's top border on screen. We erase that final line.
    """
    console.control(Control(
        (ControlType.CURSOR_UP, 1),
        (ControlType.ERASE_IN_LINE, 2),
        (ControlType.CURSOR_MOVE_TO_COLUMN, 0),
    ))


# ── Abort coordinator ─────────────────────────────────────────────────────────


class AbortController:
    """Coordinates abort across job tasks: signals, fail-fast, single-fire guard.

    Knows nothing about Rich — `abort_hook` is whatever the caller passes
    (e.g. a Live teardown function) to clean up its own output state.
    """

    def __init__(
        self,
        formatter: MessageFormatter,
        tasks: list[asyncio.Task],
        *,
        abort_hook=None,
    ) -> None:
        self._formatter = formatter
        self._tasks = tasks
        self._abort_hook = abort_hook
        self._aborting = False
        self._caught_signal: int | None = None
        self._loop: asyncio.AbstractEventLoop | None = None

    @property
    def caught_signal(self) -> int | None:
        return self._caught_signal

    def install(self, loop: asyncio.AbstractEventLoop) -> None:
        self._loop = loop
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, self._on_signal, sig)

    def remove(self) -> None:
        if self._loop is None:
            return
        for sig in (signal.SIGINT, signal.SIGTERM):
            self._loop.remove_signal_handler(sig)

    def wire_fail_fast(self, jobs: list[Job]) -> None:
        for job, task in zip(jobs, self._tasks):
            task.add_done_callback(lambda _t, j=job: self._check_fail(j))

    def _on_signal(self, sig: int) -> None:
        self._abort(
            Text(f"⚠ Signal received: {signal.Signals(sig).name}", style="bold red"),
            sig=sig,
        )

    def _check_fail(self, job: Job) -> None:
        if not self._aborting and job.state == JobState.FAILED:
            self._abort(Text(f"⚠ Aborting on first failure: {job.label}", style="bold red"))

    def _abort(self, message: Text, sig: int | None = None) -> None:
        if self._aborting:
            return
        self._aborting = True
        if sig is not None:
            self._caught_signal = sig
        if self._abort_hook:
            self._abort_hook()
        console.print(self._formatter.msg(message))
        for t in self._tasks:
            t.cancel()


# ── Output mode selection ──────────────────────────────────────────────────────


@dataclass
class OutputMode:
    """How `Executor.run_all` should render job output."""
    print_fn: Callable[..., None]
    context: ContextManager[Any]
    abort_hook: Callable[[], None] | None = None


def _select_output_mode(jobs: list[Job], *, quiet: bool, no_status: bool) -> OutputMode:
    """Pick a rendering mode: silent / scrolling-only / Live status panel."""
    if quiet:
        return OutputMode(print_fn=lambda *_: None, context=nullcontext())
    if no_status:
        return OutputMode(print_fn=console.print, context=nullcontext())

    live = Live(
        StatusDisplay(jobs),
        refresh_per_second=10,
        console=console,
        screen=False,
        transient=True,
    )

    def _stop_live_cleanly() -> None:
        live.stop()
        _erase_live_residue()

    return OutputMode(print_fn=live.console.print, context=live, abort_hook=_stop_live_cleanly)


# ── Executor ───────────────────────────────────────────────────────────────────


class Executor:

    @classmethod
    async def run_all(
        cls,
        jobs: list[Job],
        *,
        no_status: bool,
        quiet: bool,
        timeout: int | float | None,
        pool: int,
        buffer_secs: int | float,
        stagger: bool = False,
        normalize_cr: bool = False,
        timestamps: str | None = None,
        fail_fast: bool = False,
    ) -> list[Job]:
        if not jobs:
            return jobs

        formatter = MessageFormatter(timestamps)
        sem = asyncio.Semaphore(pool)
        mode = _select_output_mode(jobs, quiet=quiet, no_status=no_status)

        def _stagger_delay(i: int) -> int | float:
            return (i % pool) * buffer_secs / pool if stagger else buffer_secs

        with mode.context:
            runners = [
                JobRunner(
                    j, sem, formatter, mode.print_fn,
                    timeout=timeout,
                    buffer_secs=buffer_secs,
                    stagger_delay=_stagger_delay(i),
                    normalize_cr=normalize_cr,
                )
                for i, j in enumerate(jobs)
            ]
            tasks = [asyncio.create_task(r.run()) for r in runners]

            abort_ctl = AbortController(formatter, tasks, abort_hook=mode.abort_hook)
            if fail_fast:
                abort_ctl.wire_fail_fast(jobs)
            abort_ctl.install(asyncio.get_running_loop())
            try:
                await asyncio.gather(*tasks, return_exceptions=True)
            finally:
                abort_ctl.remove()

        if abort_ctl.caught_signal is not None:
            raise _Aborted(abort_ctl.caught_signal)
        return jobs


# ── Reporter ───────────────────────────────────────────────────────────────────


class Reporter:
    @classmethod
    def summary(cls, jobs: list[Job]) -> None:
        failed = [j for j in jobs if j.state == JobState.FAILED]
        if not failed:
            return
        console.print()
        console.rule("[bold red]Failed jobs — full output[/bold red]", style="red")
        for job in failed:
            label = "TIMEOUT" if job.rc == -1 else f"rc={job.rc}"
            console.print(f"\n[bold red]✗ {job.label}[/bold red]  {label}")
            for line in job.lines:
                console.print(Text(f"  {line.text}", style="red" if line.fd == 2 else ""))


# ── Helpers ────────────────────────────────────────────────────────────────────


def _item_label(item: str) -> str:
    """For path-like items: parent/name. Otherwise: item truncated."""
    p = PurePath(item.strip())
    if len(p.parts) > 1:
        return f"{p.parent.name}/{p.name}"
    return str(p)[:60]


def _cmd_label(cmd: str) -> str:
    cmd = cmd.strip()
    return cmd if len(cmd) <= 60 else cmd[:57] + "…"


async def _drain_stream(stream: asyncio.StreamReader, fd: int, on_line, *, normalize_cr: bool) -> None:
    """Read `stream` line-by-line, calling `on_line(raw_bytes, fd)` per line.

    If normalize_cr: replace \\r\\n→\\n then \\r→\\n before splitting,
    so progress-style output (spinners, percentages) becomes one line per update.
    """
    if normalize_cr:
        remainder = b""
        while True:
            chunk = await stream.read(65536)
            if not chunk:
                break
            data = (remainder + chunk).replace(b"\r\n", b"\n").replace(b"\r", b"\n")
            *lines, remainder = data.split(b"\n")
            for raw_line in lines:
                on_line(raw_line, fd)
        if remainder:
            on_line(remainder, fd)
    else:
        async for raw in stream:
            on_line(raw, fd)


def _fmt_dur(seconds: float, ms: bool = False) -> str:
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = seconds % 60
    if ms:
        return f"{h}:{m:02d}:{s:06.3f}"
    return f"{h}:{m:02d}:{int(s):02d}"


def _read_stdin(null_terminated: bool) -> list[str]:
    data = sys.stdin.buffer.read()
    if null_terminated:
        return [s.decode() for s in data.split(b"\0") if s.strip()]
    return [line.decode() for line in data.splitlines() if line.strip()]


def _split_label(elem: str, sep: str) -> tuple[str, str]:
    """Split 'label{sep}rest' → (label, rest); returns ('', elem) when sep is absent."""
    if sep in elem:
        label, rest = elem.split(sep, 1)
        return label.strip(), rest.strip()
    return "", elem


def _resolve_items(template: str, items: tuple[str, ...], null_sep: bool) -> list[str]:
    """Pick the input source: positional args (when --cmd is set) or stdin.

    Exits with an error if positional items are passed without --cmd, or if
    no template is set and stdin is a TTY (no commands available).
    """
    if template:
        return list(items) if items else _read_stdin(null_sep)
    if items:
        err_console.print("[bold red]Error:[/bold red] positional items require --cmd")
        sys.exit(1)
    if sys.stdin.isatty():
        err_console.print("[bold red]Error:[/bold red] no commands: pass --cmd ITEMS or pipe commands via stdin")
        sys.exit(1)
    return _read_stdin(null_sep)


def _build_jobs(src: list[str], template: str, label_sep: str | None) -> list[Job]:
    """Construct Jobs from raw input items in one of three modes.

    - label_sep set    → split each item on sep: left=label, right→template
    - template != '{}' → each item plugged into template; label = path-style item
    - default          → each item is the full command; label = truncated command
    """
    if label_sep:
        jobs = []
        for elem in src:
            label, rest = _split_label(elem, label_sep)
            jobs.append(Job(cmd=template.replace("{}", rest), label=label or _item_label(rest)))
        return jobs
    if template != "{}":
        return [Job(cmd=template.replace("{}", i), label=_item_label(i)) for i in src]
    return [Job(cmd=c, label=_cmd_label(c)) for c in src]


# ── CLI ────────────────────────────────────────────────────────────────────────


@click.command(context_settings=dict(max_content_width=120))
@click.option("--cmd", "template", default="{}", metavar="TEMPLATE", help="Shell template; {} is replaced by each item. Items from args or stdin.")
@click.option("-0", "--null", "null_sep", is_flag=True, help="Stdin items are null-terminated.")
@click.option("-j", "--jobs", "pool", default=5, show_default=True, metavar="N", help="Parallel job limit.")
@click.option("--timeout", default=None, type=click.FLOAT, help="Per-job timeout in seconds. No timeout by default.")
@click.option("--no-status", "-S", "no_status", is_flag=True, help="Plain scrolling output without live status bar.")
@click.option("-q", "--quiet", is_flag=True, help="Suppress all output; print only on failure.")
@click.option(
    "-L", "--label-sep", "label_sep", default=None, metavar="SEP", help="Split each item on SEP (first occurrence): left part becomes label, right part becomes command/item."
)
@click.option("-e", "--error-summary", "error_summary", is_flag=True, help="Print full output of failed jobs after all jobs finish.")
@click.option(
    "-b",
    "--buffer",
    "buffer_secs",
    default=-1,
    show_default=True,
    metavar="SECS",
    type=click.FLOAT,
    help="Output buffering per job. 0 = immediate; -1 = hold until job ends; N = flush every N seconds (combine with -B for best visual distribution).",
)
@click.option(
    "-B",
    "--stagger",
    "stagger",
    is_flag=True,
    help="Stagger jobs' first flush across the -b interval for visual distribution.",
)
@click.option("--normalize-cr", "-r", "normalize_cr", is_flag=True, help="Normalize CR: replace \\r\\n→\\n then \\r→\\n. Useful for tools that use \\r for progress output.")
@click.option(
    "--timestamps",
    "-t",
    "timestamps",
    is_flag=False,
    flag_value="%Y-%m-%d %H:%M:%S",
    default=None,
    metavar="FORMAT",
    help="Prefix every log line with a timestamp. Use bare -t for default 'YYYY-mm-dd HH:MM:SS', or pass a strftime format.",
)
@click.option("--fail-fast", "-x", "fail_fast", is_flag=True, help="Abort all remaining jobs on first failure.")
@click.argument("items", nargs=-1, metavar="ITEM...")
def main(
    template: str,
    null_sep: bool,
    pool: int,
    timeout: int | float | None,
    no_status: bool,
    quiet: bool,
    label_sep: str | None,
    error_summary: bool,
    buffer_secs: int | float,
    stagger: bool,
    normalize_cr: bool,
    timestamps: str | None,
    fail_fast: bool,
    items: tuple[str, ...],
) -> None:
    """Run shell commands in parallel.

    \b
    Template mode — --cmd replaces {} with each ITEM:
      tia-parallel --cmd "./deploy.sh {}" prod staging dev
      find . -name '*.sh' | tia-parallel --cmd "{} arg"

    \b
    Stdin mode — each line is a complete command:
      echo -e "cmd1\\ncmd2" | tia-parallel
      printf "cmd1\\0cmd2\\0" | tia-parallel -0

    \b
    Label separator (-L) — split each item into label and command/item:
      echo -e "prod|./deploy.sh prod\\nstg|./deploy.sh stg" | tia-parallel -L "|"
      tia-parallel --cmd "./deploy.sh {}" -L "|" "prod|production" "stg|staging"
    """
    src = _resolve_items(template, items, null_sep)
    jobs = _build_jobs(src, template, label_sep)

    if not jobs:
        console.print("[yellow]Nothing to run.[/yellow]")
        return

    if not sys.stdout.isatty():
        no_status = True

    t0 = time.perf_counter()
    try:
        jobs = asyncio.run(Executor.run_all(jobs, no_status=no_status, quiet=quiet, timeout=timeout, pool=pool, buffer_secs=buffer_secs, stagger=stagger, normalize_cr=normalize_cr, timestamps=timestamps, fail_fast=fail_fast))
    except _Aborted as exc:
        sys.exit(128 + exc.sig)
    except (KeyboardInterrupt, asyncio.CancelledError):
        sys.exit(128 + signal.SIGINT)
    elapsed = time.perf_counter() - t0
    console.print(f"[dim]Done in {_fmt_dur(elapsed)}[/dim]")
    if error_summary:
        Reporter.summary(jobs)
    sys.exit(1 if any(j.state == JobState.FAILED for j in jobs) else 0)


if __name__ == "__main__":
    main()


# ── Tests (pytest tia-parallel) ────────────────────────────────────────────────


class TestHelpers:
    def test_fmt_dur(self):
        assert _fmt_dur(5.0) == "0:00:05"
        assert _fmt_dur(90.0) == "0:01:30"
        assert _fmt_dur(3661.0) == "1:01:01"
        assert _fmt_dur(5.0, ms=True) == "0:00:05.000"
        assert _fmt_dur(90.123, ms=True) == "0:01:30.123"

    def test_item_label(self):
        assert _item_label("foo") == "foo"
        assert _item_label("/a/b/c") == "b/c"

    def test_cmd_label_truncates(self):
        label = _cmd_label("x" * 80)
        assert len(label) == 58 and label.endswith("…")

    def test_split_label(self):
        assert _split_label("prod|cmd", "|") == ("prod", "cmd")
        assert _split_label("cmd", "|") == ("", "cmd")
        assert _split_label(" a | b|c ", "|") == ("a", "b|c")


class TestExecutor:
    @classmethod
    def setup_class(cls):
        import importlib

        importlib.import_module("asyncio")  # already imported; confirms env is sane
        cls.run = staticmethod(lambda jobs, **kw: asyncio.run(Executor.run_all(jobs, no_status=True, quiet=True, timeout=kw.pop("timeout", 10), pool=4, buffer_secs=0, **kw)))

    def test_success(self):
        (job,) = self.run([Job(cmd="true", label="ok")])
        assert job.state == JobState.DONE and job.rc == 0

    def test_failure(self):
        (job,) = self.run([Job(cmd="false", label="fail")])
        assert job.state == JobState.FAILED and job.rc == 1

    def test_output_captured(self):
        (job,) = self.run([Job(cmd="echo hello", label="out")])
        assert any("hello" in ln.text for ln in job.lines)

    def test_timeout(self):
        (job,) = self.run([Job(cmd="sleep 10", label="slow")], timeout=0.2)
        assert job.state == JobState.FAILED and job.rc == -1

    def test_no_timeout(self):
        (job,) = self.run([Job(cmd="true", label="ok")], timeout=None)
        assert job.state == JobState.DONE and job.rc == 0


class TestAbort:
    def _run_with_signal_after(self, jobs, delay=0.15, sig=signal.SIGINT, **kw):
        import threading

        kw.setdefault("timeout", 10)
        kw.setdefault("pool", 4)

        def _send():
            time.sleep(delay)
            os.kill(os.getpid(), sig)

        t = threading.Thread(target=_send, daemon=True)
        t.start()
        try:
            asyncio.run(Executor.run_all(jobs, no_status=True, quiet=True, buffer_secs=0, **kw))
            return None
        except _Aborted as e:
            return e
        finally:
            t.join(timeout=2)

    def test_abort_sigint(self):
        jobs = [Job(cmd="sleep 10", label="slow")]
        exc = self._run_with_signal_after(jobs)
        assert isinstance(exc, _Aborted) and exc.sig == signal.SIGINT
        assert jobs[0].state == JobState.FAILED

    def test_abort_sigterm(self):
        jobs = [Job(cmd="sleep 10", label="slow")]
        exc = self._run_with_signal_after(jobs, sig=signal.SIGTERM)
        assert isinstance(exc, _Aborted) and exc.sig == signal.SIGTERM
        assert jobs[0].state == JobState.FAILED

    def test_abort_waiting_job_cancelled(self):
        """pool=1: second job waits on semaphore; on abort it is cancelled, first is aborted."""
        jobs = [Job(cmd="sleep 10", label="slow"), Job(cmd="true", label="waiter")]
        exc = self._run_with_signal_after(jobs, pool=1)
        assert isinstance(exc, _Aborted)
        assert all(j.state == JobState.FAILED for j in jobs)


class TestFailFast:
    def _run(self, jobs, **kw):
        kw.setdefault("timeout", 10)
        kw.setdefault("pool", 4)
        return asyncio.run(Executor.run_all(jobs, no_status=True, quiet=True, buffer_secs=0, **kw))

    def test_no_fail_fast_runs_all_after_failure(self):
        jobs = [Job(cmd="false", label="fail"), Job(cmd="true", label="ok")]
        self._run(jobs)
        assert jobs[0].state == JobState.FAILED
        assert jobs[1].state == JobState.DONE

    def test_fail_fast_cancels_pending(self):
        """With pool=1 and fail_fast=True, the job after a failure must be cancelled."""
        jobs = [Job(cmd="false", label="fail"), Job(cmd="true", label="never")]
        self._run(jobs, pool=1, fail_fast=True)
        assert jobs[0].state == JobState.FAILED and jobs[0].rc == 1
        assert jobs[1].state == JobState.FAILED  # cancelled, never ran


class TestCli:
    """End-to-end CLI tests via click's CliRunner."""

    def _invoke(self, *args):
        from click.testing import CliRunner
        return CliRunner(mix_stderr=False).invoke(main, list(args), catch_exceptions=False)

    def test_default_exit_code_success(self):
        r = self._invoke("--cmd", "true", "x")
        assert r.exit_code == 0

    def test_default_exit_code_failure(self):
        r = self._invoke("--cmd", "false", "x")
        assert r.exit_code == 1

    def test_timestamps_default_format(self):
        """Bare -t (at end of args) uses the default 'YYYY-mm-dd HH:MM:SS' format."""
        r = self._invoke("--cmd", "echo X", "x", "-t")
        assert r.exit_code == 0
        # Default format includes a 4-digit year and seconds — match e.g. "2026-05-04 21:00:00"
        import re
        assert re.search(r"\b\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\b", r.output)

    def test_timestamps_custom_format(self):
        """--timestamps=FORMAT applies the given strftime format."""
        r = self._invoke("--timestamps=MARK", "--cmd", "echo X", "x")
        assert r.exit_code == 0
        assert "MARK" in r.output

    def test_timestamps_off_by_default(self):
        r = self._invoke("--cmd", "echo X", "x")
        assert r.exit_code == 0
        import re
        assert not re.search(r"\b\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\b", r.output)

    def test_fail_fast_flag_exit_code(self):
        """--fail-fast still exits with 1 (not signal-style 130)."""
        r = self._invoke("-x", "-j1", "--cmd", "{}", "false", "true")
        assert r.exit_code == 1
