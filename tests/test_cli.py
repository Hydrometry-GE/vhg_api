"""Tests for command-mode selection and argument validation."""

from argparse import Namespace

import vhg_api.cli as cli
from vhg_api.cli import _use_incremental_mode, build_parser


def _download_args(*extra: str) -> Namespace:
    """Parse arguments for the ``download`` subcommand."""
    return build_parser().parse_args(["download", *extra])


def test_download_is_incremental_by_default() -> None:
    """A normal operational run must resume from archive state."""
    assert _use_incremental_mode(_download_args()) is True


def test_explicit_start_activates_historical_refresh() -> None:
    """An explicit lower bound must never be advanced by archive state."""
    args = _download_args(
        "--start", "2025-01-01T00:00:00Z",
        "--end", "2025-01-31T23:59:59Z",
    )
    assert _use_incremental_mode(args) is False


def test_explicit_start_without_end_is_historical_refresh() -> None:
    """A refresh may run from an explicit start through the current minute."""
    args = _download_args("--start", "2025-01-01T00:00:00Z")
    assert _use_incremental_mode(args) is False


def test_no_incremental_disables_archive_state_without_explicit_start() -> None:
    """The recovery switch uses configured initial_start without archive state."""
    assert _use_incremental_mode(_download_args("--no-incremental")) is False


def test_end_without_start_is_rejected(capsys) -> None:
    """An upper bound alone is ambiguous and must not start a download."""
    exit_code = cli._download(_download_args("--end", "2025-01-31T00:00:00Z"))

    assert exit_code == 2
    assert "--end requires --start" in capsys.readouterr().out
