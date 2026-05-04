#!/usr/bin/env python3
"""Run shell commands in parallel with live status and scrollable output."""

import asyncio
import logging
import os
import signal
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import PurePath

logging.getLogger("asyncio").setLevel(logging.CRITICAL)

import click
from rich.console import Console
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


# ── Executor ───────────────────────────────────────────────────────────────────


class Executor:
    @classmethod
    async def _killpg(cls, proc: asyncio.subprocess.Process) -> None:
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

    @classmethod
    async def _run(
        cls,
        job: Job,
        print_fn,
        sem: asyncio.Semaphore,
        timeout: int | float,
        buffer_secs: int | float,
        normalize_cr: bool = False,
        timestamps: bool = False,
    ) -> None:
        def _ts_prefix() -> list[tuple[str, str]]:
            if not timestamps:
                return []
            return [(datetime.now().strftime("%H:%M:%S "), "dim")]

        def _msg(*parts) -> Text:
            return Text.assemble(*_ts_prefix(), *parts)

        async with sem:
            job.state = JobState.RUNNING
            job.started_at = time.perf_counter()
            print_fn(_msg(Text(f"{job.label} ", style="cyan"), Text("▶ started", style="dim")))

            proc = await asyncio.create_subprocess_shell(
                job.cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                start_new_session=True,
            )

            buf: list[Text] = []

            def _flush() -> None:
                lines = buf[:]
                del buf[:]
                for t in lines:
                    print_fn(t)

            def _emit(raw: bytes, fd: int) -> None:
                line = LogLine(job=job, fd=fd, text=raw.decode(errors="replace").rstrip())
                job.lines.append(line)
                t = _msg(Text(f"{job.label} ", style="dim cyan"), Text(line.text, style="dim" if fd == 1 else "yellow"))
                if buffer_secs == 0:
                    print_fn(t)
                else:
                    buf.append(t)

            async def drain(stream: asyncio.StreamReader, fd: int) -> None:
                if normalize_cr:
                    remainder = b""
                    while True:
                        chunk = await stream.read(65536)
                        if not chunk:
                            break
                        data = (remainder + chunk).replace(b"\r\n", b"\n").replace(b"\r", b"\n")
                        *lines, remainder = data.split(b"\n")
                        for raw_line in lines:
                            _emit(raw_line, fd)
                    if remainder:
                        _emit(remainder, fd)
                else:
                    async for raw in stream:
                        _emit(raw, fd)

            async def _flush_loop() -> None:
                while True:
                    await asyncio.sleep(buffer_secs)
                    _flush()

            flush_task = asyncio.create_task(_flush_loop()) if buffer_secs > 0 else None

            assert proc.stdout and proc.stderr
            try:
                await asyncio.wait_for(
                    asyncio.gather(drain(proc.stdout, 1), drain(proc.stderr, 2)),
                    timeout=timeout,
                )
                await proc.wait()
                job.rc = proc.returncode
                job.state = JobState.DONE if proc.returncode == 0 else JobState.FAILED
                dur = _fmt_dur(time.perf_counter() - job.started_at, ms=True)
                _flush()
                if job.state == JobState.DONE:
                    print_fn(_msg(
                        Text(f"{job.label} ", style="cyan"),
                        Text("✓ done", style="green"),
                        Text(f" - runtime: {dur}", style="dim"),
                    ))
                else:
                    print_fn(_msg(
                        Text(f"{job.label} ", style="cyan"),
                        Text(f"✗ FAILED  rc={job.rc}", style="bold red"),
                        Text(f" - runtime: {dur}", style="dim"),
                    ))
            except asyncio.TimeoutError:
                await cls._killpg(proc)
                job.rc = -1
                job.state = JobState.FAILED
                dur = _fmt_dur(time.perf_counter() - job.started_at, ms=True)
                _flush()
                print_fn(_msg(
                    Text(f"{job.label} ", style="cyan"),
                    Text(f"✗ TIMEOUT  ({timeout}s)", style="bold red"),
                    Text(f" - runtime: {dur}", style="dim"),
                ))
            except (asyncio.CancelledError, Exception):
                await cls._killpg(proc)
                raise
            finally:
                if flush_task:
                    flush_task.cancel()
                _flush()

    @classmethod
    async def run_all(
        cls,
        jobs: list[Job],
        *,
        no_status: bool,
        quiet: bool,
        timeout: int | float,
        pool: int,
        buffer_secs: int | float,
        normalize_cr: bool = False,
        timestamps: bool = False,
    ) -> list[Job]:
        if not jobs:
            return jobs

        sem = asyncio.Semaphore(pool)

        async def _gather(print_fn) -> None:
            tasks = [asyncio.create_task(cls._run(j, print_fn, sem, timeout, buffer_secs, normalize_cr, timestamps)) for j in jobs]
            try:
                await asyncio.gather(*tasks, return_exceptions=True)
            except (KeyboardInterrupt, asyncio.CancelledError):
                for t in tasks:
                    t.cancel()
                await asyncio.gather(*tasks, return_exceptions=True)

        if quiet:
            await _gather(lambda *a, **kw: None)
        elif no_status:
            await _gather(console.print)
        else:
            status = StatusDisplay(jobs)
            with Live(status, refresh_per_second=10, console=console, screen=False, transient=True) as live:
                await _gather(live.console.print)

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


# ── CLI ────────────────────────────────────────────────────────────────────────


@click.command(context_settings=dict(help_option_names=["-h", "--help"]))
@click.option("--cmd", "template", default="{}", metavar="TEMPLATE", help="Shell template; {} is replaced by each item. Items from args or stdin.")
@click.option("-0", "null_sep", is_flag=True, help="Stdin items are null-terminated.")
@click.option("-j", "--jobs", "pool", default=5, show_default=True, metavar="N", help="Parallel job limit.")
@click.option("--timeout", default=120, show_default=True, type=click.FLOAT, help="Per-job timeout in seconds.")
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
    help="Output buffering per job. 0 = immediate; -1 = hold until job ends; N = flush every N seconds.",
)
@click.option("--normalize-cr", "-r", "normalize_cr", is_flag=True, help="Normalize CR: replace \\r\\n→\\n then \\r→\\n. Useful for tools that use \\r for progress output.")
@click.option("--timestamps", "-t", "timestamps", is_flag=True, help="Prefix every log line with HH:MM:SS.")
@click.argument("items", nargs=-1, metavar="ITEM...")
def main(
    template: str,
    null_sep: bool,
    pool: int,
    timeout: int | float,
    no_status: bool,
    quiet: bool,
    label_sep: str | None,
    error_summary: bool,
    buffer_secs: int | float,
    normalize_cr: bool,
    timestamps: bool,
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
    if template:
        src = list(items) if items else _read_stdin(null_sep)
    else:
        if items:
            err_console.print("[bold red]Error:[/bold red] positional items require --cmd")
            sys.exit(1)
        if sys.stdin.isatty():
            err_console.print("[bold red]Error:[/bold red] no commands: pass --cmd ITEMS or pipe commands via stdin")
            sys.exit(1)
        src = _read_stdin(null_sep)

    if label_sep:

        def make_job(elem: str) -> Job:
            label, rest = _split_label(elem, label_sep)
            return Job(cmd=template.replace("{}", rest), label=label or _item_label(rest))

        jobs = [make_job(e) for e in src]
    elif template != "{}":
        jobs = [Job(cmd=template.replace("{}", i), label=_item_label(i)) for i in src]
    else:
        jobs = [Job(cmd=c, label=_cmd_label(c)) for c in src]

    if not jobs:
        console.print("[yellow]Nothing to run.[/yellow]")
        return

    if not sys.stdout.isatty():
        no_status = True

    t0 = time.perf_counter()
    try:
        jobs = asyncio.run(Executor.run_all(jobs, no_status=no_status, quiet=quiet, timeout=timeout, pool=pool, buffer_secs=buffer_secs, normalize_cr=normalize_cr, timestamps=timestamps))
    except (KeyboardInterrupt, asyncio.CancelledError):
        console.print(StatusDisplay(jobs))
        sys.exit(130)
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
