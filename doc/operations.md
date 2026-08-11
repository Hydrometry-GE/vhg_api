# Operational runner and command-line reference

The `vhg-api` command is the operational interface for manual execution and
scheduled synchronization. The repository-local wrapper
`scripts/run_download.py` forwards the same arguments to the same CLI code, so
both execution modes have identical options and download behavior.

## 1. Two ways to run the same CLI

Installed package:

```bash
vhg-api COMMAND [OPTIONS]
```

Repository mode:

```bash
python scripts/run_download.py COMMAND [OPTIONS]
```

The repository wrapper changes its working directory to the repository root
before invoking the CLI. Therefore its default paths `config/settings.yml` and
`config/.env` are stable even when launched from Spyder or another directory.

The installed `vhg-api` command does not change the working directory. Its
default `--config config/settings.yml` and `--env-file config/.env` values are
therefore interpreted from the process working directory. Production schedulers
should use explicit absolute paths.

Recommended scheduled form:

```bash
vhg-api download \
  --config /opt/vhg_api/config/settings.yml \
  --env-file /opt/vhg_api/config/.env
```

## 2. General help and version

```bash
vhg-api --help
vhg-api --version
vhg-api validate-config --help
vhg-api download --help
```

`vhg-api` requires one subcommand: either `validate-config` or `download`.
Running `vhg-api` without a subcommand returns argparse exit code `2`.

## 3. `validate-config`

Syntax:

```bash
vhg-api validate-config [OPTIONS]
```

Purpose: load the selected `settings.yml`, load the selected `.env`, resolve the
source catalogue, validate the configuration, and print the configured sources.
It does not download measurements.

### Options

#### `--config PATH`

Path to `settings.yml`.

Default:

```text
config/settings.yml
```

Example:

```bash
vhg-api validate-config --config D:/Apps/vhg_api/config/settings.yml
```

Once the settings file is selected, relative companion-file paths declared
inside it are resolved from **that settings file's directory**. For example:

```yaml
sources_file: sources.csv
```

inside:

```text
D:/Apps/vhg_api/config/settings.yml
```

resolves to:

```text
D:/Apps/vhg_api/config/sources.csv
```

An absolute `sources_file` is used unchanged.

#### `--env-file PATH`

Path to the `.env` file.

Default:

```text
config/.env
```

This path is independent of `settings.yml` and is interpreted exactly as
supplied to the CLI. For scheduled execution, use an absolute path.

Example:

```bash
vhg-api validate-config \
  --config D:/Apps/vhg_api/config/settings.yml \
  --env-file D:/Apps/vhg_api/config/.env
```

#### `--include-disabled`

By default, the validation output lists enabled source rows. Add this flag to
also display disabled rows:

```bash
vhg-api validate-config --include-disabled
```

Disabled rows remain disabled; the flag only changes validation output.

### Validation output

A successful validation prints at least:

- the profile name;
- the resolved settings file;
- the resolved sources file;
- configured stations and source mappings;
- `Configuration OK.`

Configuration failures return exit code `2`.

## 4. `download`

Syntax:

```bash
vhg-api download [OPTIONS]
```

Without time overrides, `download` performs the normal incremental archive
update for every enabled source matching the optional filters.

## 5. Configuration options shared by `download`

### `--config PATH`

Select a non-default `settings.yml`:

```bash
vhg-api download --config D:/Apps/vhg_api/config/settings.yml
```

The `sources_file` inside this selected file follows the settings-relative path
rule described above.

### `--env-file PATH`

Select a non-default `.env`:

```bash
vhg-api download --env-file D:/Apps/vhg_api/config/.env
```

`--env-file` is independent from settings-relative path resolution.

There is currently **no `--sources` option**. The source catalogue is selected
through `sources_file` inside `settings.yml`.

## 6. Normal incremental mode

Command:

```bash
vhg-api download
```

For each selected source, the runner:

1. uses `incremental.initial_start` as the baseline lower bound;
2. checks the existing raw yearly archive;
3. if existing data are present, advances the source-specific lower bound to
   the latest archived `datetime_utc` minus `incremental.overlap_minutes`;
4. downloads through the current UTC minute;
5. merges existing and downloaded rows;
6. sorts by `datetime_utc` and removes duplicate timestamps, retaining the newly
   downloaded row;
7. rewrites yearly files atomically.

The overlap is intentionally re-downloaded so delayed transmissions and recent
retrospective corrections can replace archived values.

When no archive exists, the first normal incremental run begins at
`incremental.initial_start`.

## 7. Historical refresh options

### `--start DATETIME`

Supplying `--start` activates historical-refresh mode:

```bash
vhg-api download --start 2026-07-01T00:00:00Z
```

The explicit lower bound is used exactly. Existing archive state does not move
it forward. If `--end` is omitted, the upper bound is the current UTC minute.

Naive datetime values accepted by the underlying parser are interpreted as UTC,
but explicit UTC values ending in `Z` are recommended operationally.

### `--end DATETIME`

Define an explicit upper bound:

```bash
vhg-api download \
  --start 2026-07-01T00:00:00Z \
  --end 2026-07-31T23:59:59Z
```

`--end` requires `--start`. Using `--end` alone is rejected with command exit
code `2`.

### Why historical refresh exists

A correction made retrospectively on TDS can only be discovered by an ordinary
incremental run when the corrected timestamp lies inside the configured overlap.
For older changes, explicitly re-download the affected interval. During the
merge, the newly downloaded value replaces the older local row sharing the same
`datetime_utc`.

Example focused correction refresh:

```bash
vhg-api download \
  --station VX \
  --variable H \
  --start 2025-05-01T00:00:00Z \
  --end 2025-05-31T23:59:59Z
```

Historical intervals may cross calendar-year boundaries; rows are split into the
appropriate yearly files before merging.

## 8. `--no-incremental`

```bash
vhg-api download --no-incremental
```

This disables use of existing archive timestamps when calculating the lower
bound. If no explicit `--start` is supplied, the run begins directly from
`incremental.initial_start`.

Typical uses include:

- deliberate replay from the configured initial date;
- recovery or diagnostic runs where existing archive state should not advance
  the request start.

`--no-incremental` is unnecessary when `--start` is already present, because an
explicit start automatically activates non-incremental historical-refresh mode.

## 9. Source-selection filters

All filters apply both to normal incremental runs and historical refreshes.

### `--station CODE`

Select one station code; matching is case-insensitive:

```bash
vhg-api download --station VX
```

### `--variable CODE`

Select one variable; matching is case-insensitive:

```bash
vhg-api download --variable H
```

Combine station and variable to target a specific configured series when that
pair is unique:

```bash
vhg-api download --station VX --variable H
```

### `--destination PATH`

Select one exact configured destination after path normalization:

```bash
vhg-api download \
  --destination 01_Rivieres/stations/145_VX/raw_data/H
```

This is an exact destination filter, not a prefix or substring search.

## 10. Execution-control options

### `--dry-run`

```bash
vhg-api download --dry-run
```

The runner resolves configuration, computes the common requested period, applies
filters, and reports selected sources. It does **not** create a TDS client, does
not contact the API, and does not write raw data files.

Logging is still configured, so a log file may be created in the configured log
directory.

Useful examples:

```bash
vhg-api download --dry-run --station VX
vhg-api download --dry-run --station VX --variable H
```

### `--stop-on-error`

Default behavior is fault-tolerant: if one source fails, the failure is logged
and the runner attempts the remaining selected sources.

Use:

```bash
vhg-api download --stop-on-error
```

to stop after the first failed source.

### `--verbose`

```bash
vhg-api download --verbose
```

Enable debug-level logging on both the console and the daily log file. Normal
runs use INFO-level logging.

## 11. Command-mode summary

| Command | Incremental archive state used? | Effective lower bound | Typical use |
|---|---:|---|---|
| `vhg-api download` | Yes | latest archive time minus overlap, or `initial_start` on first run | Scheduled synchronization |
| `vhg-api download --start START` | No | `START` exactly | Refresh from a historical date through now |
| `vhg-api download --start START --end END` | No | `START` exactly | Bounded historical refresh |
| `vhg-api download --no-incremental` | No | `incremental.initial_start` | Deliberate broad replay/recovery |
| `vhg-api download --dry-run` | Selection only | calculated but not downloaded | Preview configuration and filters |

## 12. Option interactions and precedence

Important rules:

- `--start` automatically disables incremental archive-state calculation;
- `--end` requires `--start`;
- `--no-incremental` without `--start` uses `incremental.initial_start`;
- `--station`, `--variable`, and `--destination` narrow the enabled source set;
- `--dry-run` suppresses API contact and raw-data writes;
- `--stop-on-error` changes source-failure handling only;
- `--verbose` changes logging level only;
- CLI `--config` and `--env-file` override their built-in default locations;
- `sources_file` is not a CLI option and is resolved from the selected
  `settings.yml`.

## 13. Logs

The command writes to the console and to one daily UTF-8 log file:

```text
<VHG_LOG_DIR>/vhg_api_YYYYMMDD.log
```

The log records, among other details:

- selected source count;
- requested start/end bounds;
- whether incremental and dry-run modes are active;
- per-source measurement set and media;
- rows downloaded and files written;
- source failures with traceback;
- final success/failure counts and duration.

## 14. Exit codes

| Exit code | Meaning |
|---:|---|
| `0` | Command completed successfully; for `download`, every selected source succeeded. |
| `1` | At least one source failed, or another execution/runtime error occurred. |
| `2` | Invalid configuration or invalid command usage such as `--end` without `--start`. |

The default continue-on-error behavior is useful for scheduling: healthy sources
are still updated, while the non-zero final exit code remains visible to IT
monitoring.

## 15. Cron example

Installed package with explicit absolute configuration paths:

```cron
15 * * * * /opt/vhg_api/.venv/bin/vhg-api download --config /opt/vhg_api/config/settings.yml --env-file /opt/vhg_api/config/.env
```

Repository mode:

```cron
15 * * * * /opt/vhg_api/.venv/bin/python /opt/vhg_api/scripts/run_download.py download --config /opt/vhg_api/config/settings.yml --env-file /opt/vhg_api/config/.env
```

The application already writes its own daily log file. Shell redirection is
optional. IT should additionally monitor the process exit code and protect the
`.env` file with appropriate filesystem permissions.

## 16. Persistent state and safe reruns

`vhg_api` does not create or maintain a SQLite database. The raw CSV archive is
the synchronization state: the latest `datetime_utc` found in an existing yearly
file determines the next incremental request range.

Yearly archives are rewritten atomically through a temporary file. Repeated runs
are safe because existing and downloaded rows are merged, sorted, and
deduplicated by `datetime_utc`, with newly downloaded rows taking precedence.
