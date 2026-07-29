"""Command-line interface for vhg_api."""

from __future__ import annotations

import argparse
import logging

from . import __version__
from .config import ConfigError, load_config
from .errors import VHGAPIError
from .runner import configure_logging, run_download


def _load(args: argparse.Namespace):
    """Load configuration paths supplied by one CLI subcommand."""
    return load_config(args.config, args.env_file)


def _validate_config(args: argparse.Namespace) -> int:
    """Validate configuration and print the resolved source catalogue."""
    try:
        config = _load(args)
    except ConfigError as exc:
        print(f"Configuration error: {exc}")
        return 2

    print(f"Profile: {config.profile}")
    for station in config.stations:
        print(f"Station {station.code} ({station.series_id})")
        for source in station.sources:
            if source.enabled or args.include_disabled:
                suffix = "" if source.enabled else " [disabled]"
                print(
                    f"  {source.measurement_set} / {source.variable} / media {source.media}{suffix}"
                    f" -> {source.destination}"
                )
    print("Configuration OK.")
    return 0


def _download(args: argparse.Namespace) -> int:
    """Execute an operational download and translate outcomes to exit codes."""
    try:
        config = _load(args)
        log_path = configure_logging(config.storage.log_dir, verbose=args.verbose)
        logging.getLogger("vhg_api.cli").info("Log file: %s", log_path)
        summary = run_download(
            config,
            start=args.start,
            end=args.end,
            incremental=not args.no_incremental,
            station=args.station,
            variable=args.variable,
            destination=args.destination,
            dry_run=args.dry_run,
            continue_on_error=not args.stop_on_error,
        )
        return 1 if summary.failed else 0
    except ConfigError as exc:
        print(f"Configuration error: {exc}")
        return 2
    except (VHGAPIError, ValueError, OSError) as exc:
        print(f"Execution error: {exc}")
        return 1


def _common_config_arguments(parser: argparse.ArgumentParser) -> None:
    """Add settings and environment-file options shared by subcommands."""
    parser.add_argument("--config", default="config/settings.yml")
    parser.add_argument("--env-file", default="config/.env")


def build_parser() -> argparse.ArgumentParser:
    """Build the complete ``vhg-api`` argument parser."""
    parser = argparse.ArgumentParser(prog="vhg-api")
    parser.add_argument("--version", action="version", version=__version__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    validate = subparsers.add_parser("validate-config", help="validate settings and sources")
    _common_config_arguments(validate)
    validate.add_argument("--include-disabled", action="store_true")
    validate.set_defaults(func=_validate_config)

    download = subparsers.add_parser("download", help="update configured raw archives")
    _common_config_arguments(download)
    download.add_argument("--start", help="lower UTC bound; defaults to incremental.initial_start")
    download.add_argument("--end", help="upper UTC bound; defaults to current UTC minute")
    download.add_argument("--station", help="select one station code")
    download.add_argument("--variable", help="select one variable")
    download.add_argument("--destination", help="select one exact destination")
    download.add_argument("--no-incremental", action="store_true", help="ignore existing files")
    download.add_argument("--dry-run", action="store_true", help="show selected sources without downloading")
    download.add_argument("--stop-on-error", action="store_true", help="stop after the first failed source")
    download.add_argument("--verbose", action="store_true", help="enable debug logging")
    download.set_defaults(func=_download)
    return parser


def main() -> int:
    """Parse command-line arguments and run the selected subcommand."""
    parser = build_parser()
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
