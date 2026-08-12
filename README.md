# vhg_api

`vhg_api` is a configuration-driven Python client and operational downloader for
the Tetraèdre TDS JSON API. Version 1.0.0 provides a stable raw-data schema, safe
incremental archive updates, generic destination routing, an installable command,
and a repository-local runner suitable for manual use or scheduled execution.

## Main capabilities

- short YAML deployment configuration and semicolon-separated source catalogue;
- secrets and machine-specific paths supplied through `.env` or process environment variables;
- SHA256 challenge authentication and access checks;
- retries, timeouts, optional proxy handling, and optional institutional CA-bundle support;
- generic relative, POSIX, Windows-drive, and UNC destination routing;
- yearly semicolon-separated raw CSV archives;
- overlap-based incremental updates and explicit historical refreshes;
- atomic archive rewrites with newly downloaded duplicate timestamps taking precedence;
- source filters, dry run, logging, summaries, and meaningful exit codes;
- operation both with and without installing the package;
- automated pytest suite and manual diagnostic scripts.

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

The repository-local wrapper changes to the repository root before invoking the
CLI, so its default `config/settings.yml` and `config/.env` paths work even when
the script is launched from Spyder or from another working directory.

## Installed command

```bash
python -m pip install -e .
vhg-api validate-config
vhg-api download --dry-run
vhg-api download
```

When the installed `vhg-api` command is used, the default CLI paths
`config/settings.yml` and `config/.env` are relative to the current working
directory. For scheduled deployments, explicit absolute `--config` and
`--env-file` paths are therefore recommended.

## Command-line reference

General help and version:

```bash
vhg-api --help
vhg-api --version
vhg-api validate-config --help
vhg-api download --help
```

The CLI has two subcommands:

- `validate-config`: load and validate settings, environment variables, and the source catalogue;
- `download`: perform a dry run, normal incremental synchronization, or explicit historical refresh.

### `validate-config`

```bash
vhg-api validate-config [OPTIONS]
```

Options:

| Option | Meaning |
|---|---|
| `--config PATH` | Path to `settings.yml`. Default: `config/settings.yml`. |
| `--env-file PATH` | Path to the `.env` file. Default: `config/.env`. |
| `--sources PATH` | Override the catalogue from `sources_file`; relative paths resolve beside the active `settings.yml`. |
| `--include-disabled` | Also display disabled rows from the source catalogue. |

Example:

```bash
vhg-api validate-config \
  --config D:/Apps/vhg_api/config/settings.yml \
  --env-file D:/Apps/vhg_api/config/.env
```

`validate-config` prints the resolved settings path, the resolved `sources.csv`
path, and the configured measurement sources. A relative `sources_file` declared
inside `settings.yml` is resolved relative to the directory containing that
specific `settings.yml`, not relative to the shell working directory.

### `download`

```bash
vhg-api download [OPTIONS]
```

Common configuration options:

| Option | Meaning |
|---|---|
| `--config PATH` | Path to `settings.yml`. Default: `config/settings.yml`. |
| `--env-file PATH` | Path to the `.env` file. Default: `config/.env`. |
| `--sources PATH` | Override the catalogue from `sources_file`; relative paths resolve beside the active `settings.yml`. |

Time and synchronization options:

| Option | Meaning |
|---|---|
| `--start DATETIME` | Explicit lower UTC bound. Supplying it activates historical-refresh mode and bypasses incremental archive-state calculation. |
| `--end DATETIME` | Explicit upper UTC bound. Requires `--start`; if omitted while `--start` is present, the current UTC minute is used. |
| `--no-incremental` | Ignore existing archive timestamps. Without `--start`, use `incremental.initial_start` directly. |

Source-selection options:

| Option | Meaning |
|---|---|
| `--station CODE` | Select one station code; matching is case-insensitive. |
| `--variable CODE` | Select one variable; matching is case-insensitive. |
| `--destination PATH` | Select one exact configured destination after path normalization. |

Execution options:

| Option | Meaning |
|---|---|
| `--dry-run` | Resolve and report selected sources without contacting TDS or writing data files. |
| `--stop-on-error` | Stop after the first source failure instead of continuing with remaining sources. |
| `--verbose` | Enable debug-level console and file logging. |

Examples:

```bash
# Normal incremental synchronization
vhg-api download

# Preview selection without API calls or writes
vhg-api download --dry-run

# Incremental update for one series selection
vhg-api download --station VX --variable H

# Historical refresh from a date through now
vhg-api download --station VX --variable H \
  --start 2026-01-01T00:00:00Z

# Bounded historical refresh
vhg-api download --station VX --variable H \
  --start 2026-01-01T00:00:00Z \
  --end 2026-01-31T23:59:59Z

# Deliberately replay from incremental.initial_start
vhg-api download --no-incremental
```

A normal `download` is incremental. Supplying `--start` activates historical
refresh mode: the requested lower bound is used exactly instead of being moved
forward from existing archive state. During the merge, newly downloaded rows
replace older rows with the same `datetime_utc`, allowing retrospective TDS
corrections to propagate into the raw archive.

Long requested intervals are automatically split into bounded TDS requests. The
default is 24 hours per request, configured in `settings.yml`:

```yaml
download:
  chunk_hours: 24
```

This is transparent to the CLI: first synchronizations and historical refreshes
can span months or years without requiring the operator to split the dates
manually. Adjacent chunks intentionally share their boundary timestamp; the
combined result is sorted and deduplicated with the newest chunk winning at the
shared boundary.

`--end` cannot be used alone. It must be paired with `--start`.

By default, the source catalogue is selected through `sources_file` in
`settings.yml`. `--sources PATH` can temporarily override that catalogue without
editing the settings file. Relative `--sources` paths use the same base directory:
the directory containing the active `settings.yml`. After the catalogue is loaded,
`--station`, `--variable`, and `--destination` filter rows within it.

For the full operational behavior, option interactions, exit codes, and cron
examples, see [Operational runner and command-line reference](doc/operations.md).

### Institutional proxy certificates

TLS verification is enabled by default (`tls.verify: true`) and requires no extra
configuration on networks where the normal public certificate chain is trusted.
If an institutional HTTPS proxy uses an internal CA, set the optional
`VHG_CA_BUNDLE` path in `config/.env` to the PEM certificate/bundle supplied by
IT. If certificate verification must deliberately be bypassed in a controlled
environment, set `tls.verify: false` explicitly in `settings.yml`. An empty CA
bundle never disables verification by itself. See `doc/configuration.md` and
`doc/troubleshooting.md`.

## Configuration

- `config/settings.yml`: API, proxy/TLS, storage, logging, incremental settings, and `sources_file`;
- `config/sources.csv`: enabled sources and their destinations;
- `config/.env`: local secrets and deployment paths; never commit this file.

Example incremental configuration:

```yaml
incremental:
  initial_start: "2026-01-01T00:00:00Z"
  overlap_minutes: 1440
```

Path-resolution rule for companion files declared inside `settings.yml`:

- relative paths are resolved from the directory containing the selected settings file;
- absolute paths are used unchanged.

For example, when this command is used:

```bash
vhg-api download --config D:/Apps/vhg_api/config/settings.yml \
  --env-file D:/Apps/vhg_api/config/.env
```

and `settings.yml` contains:

```yaml
sources_file: sources.csv
```

then the catalogue resolves to:

```text
D:/Apps/vhg_api/config/sources.csv
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
- [Operational runner and command-line reference](doc/operations.md)
- [Raw data format](doc/data_format.md)
- [Download and storage internals](doc/download.md)
- [Client reference](doc/client.md)
- [Troubleshooting](doc/troubleshooting.md)
- [Changelog](CHANGELOG.md)

## Tests

```bash
python -m pytest
```

## Version

Current release: **1.0.0**.
