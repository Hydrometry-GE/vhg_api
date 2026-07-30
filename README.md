# vhg_api

`vhg_api` is a configuration-driven Python client and operational downloader for
the Tetraèdre TDS JSON API. Version 1.0.0 provides a stable raw-data schema, safe
incremental archive updates, generic destination routing, an installable command,
and a repository-local runner suitable for manual use or cron.

## Main capabilities

- short YAML deployment configuration and semicolon-separated source catalogue;
- secrets and paths supplied through `.env` or process environment variables;
- SHA256 challenge authentication and access checks;
- retries, timeouts, and optional proxy handling;
- generic relative, POSIX, Windows-drive, and UNC destination routing;
- yearly semicolon-separated raw CSV archives;
- overlap-based incremental updates and explicit historical refreshes;
- atomic archive rewrites with newly downloaded duplicate timestamps taking precedence;
- source filters, dry run, logging, summaries, and meaningful exit codes;
- operation both with and without installing the package;
- automated pytest suite and numbered manual diagnostic scripts.

## Quick start without installing the package

```bash
python -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
cp config/.env.example config/.env
.venv/bin/python scripts/run_download.py validate-config
.venv/bin/python scripts/run_download.py download --dry-run
.venv/bin/python scripts/run_download.py download
```

On Windows, use `.venv\Scripts\python.exe` and copy `.env.example` through
Explorer or PowerShell.

## Installed command

```bash
python -m pip install -e .
vhg-api validate-config
vhg-api download --dry-run
vhg-api download
```

A normal `download` is incremental. To re-download corrected historical data,
provide an explicit UTC start and, optionally, an end:

```bash
vhg-api download --station VX --variable H \
  --start 2026-01-01T00:00:00Z \
  --end 2026-01-31T23:59:59Z
```

Supplying `--start` activates historical-refresh mode: the interval is requested
without advancing the lower bound from existing archive state. During the merge,
newly downloaded rows replace older rows with the same `datetime_utc`.

The default paths are `config/settings.yml` and `config/.env`. Explicit absolute
paths are recommended in scheduled deployments.

## Configuration

- `config/settings.yml`: API, proxy, storage, logging, and incremental settings;
- `config/sources.csv`: enabled sources and their destinations;
- `config/.env`: local secrets and deployment paths; never commit this file.

Example incremental configuration:

```yaml
incremental:
  initial_start: "2026-01-01T00:00:00Z"
  overlap_minutes: 1440
```

The canonical raw schema is:

```text
timestamp;datetime_utc;value;station;series_id;variable;measurement_set;media
```

`datetime_utc` remains authoritative. `timestamp` is the equivalent Unix epoch
value in seconds. The package uses no database: existing raw CSV files provide
the incremental state, while daily log files record execution history.

## Documentation

- [Installation and execution](doc/installation.md)
- [Configuration reference](doc/configuration.md)
- [Operational runner and cron](doc/operations.md)
- [Raw data format](doc/data_format.md)
- [Download and storage internals](doc/download.md)
- [Client reference](doc/client.md)
- [Troubleshooting](doc/troubleshooting.md)
- [Changelog](CHANGELOG.md)

## Tests

```bash
python -m pytest
```

The scripts under `scripts/test/` provide ordered manual diagnostics for an
actual deployment. They intentionally keep credentials out of their output.

## Version

Current release: **1.0.0**.


Relative paths declared in `settings.yml` are resolved from the settings file directory.
