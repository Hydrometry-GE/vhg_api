# Command-line reference and operational use

`vhg_api` provides two command-line commands:

```text
vhg-api validate-config
vhg-api download
```

The same interface is available without installing the package:

```text
python scripts/run_download.py validate-config
python scripts/run_download.py download
```

This document is the complete command-line reference. For configuration file contents, see [`configuration.md`](configuration.md).

---

## 1. Quick reference

### General command

| Command / option | Purpose |
|---|---|
| `vhg-api --help` | Show top-level help and available commands. |
| `vhg-api --version` | Print the installed `vhg_api` version. |
| `vhg-api validate-config` | Validate settings, environment variables, and the source catalogue. |
| `vhg-api download` | Download and update the configured raw archives. |

### `validate-config` options

| Option | Value | Default | Purpose |
|---|---|---|---|
| `--config` | path | `config/settings.yml` | Path to `settings.yml`. |
| `--env-file` | path | `config/.env` | Path to the `.env` file containing credentials and deployment-specific environment variables. |
| `--sources` | path | `sources_file` from settings | Override the source catalogue. Relative paths are resolved from the selected `settings.yml` directory. |
| `--include-disabled` | flag | off | Also display disabled source rows when validating the configuration. |

### `download` options

| Option | Value | Default | Purpose |
|---|---|---|---|
| `--config` | path | `config/settings.yml` | Path to `settings.yml`. |
| `--env-file` | path | `config/.env` | Path to the `.env` file. |
| `--sources` | path | `sources_file` from settings | Override the source catalogue. Relative paths are resolved from the selected `settings.yml` directory. |
| `--start` | UTC datetime | not set | Explicit lower time bound. Supplying it activates historical-refresh mode and bypasses incremental archive-state calculation. |
| `--end` | UTC datetime | current UTC minute | Explicit upper time bound for a historical refresh. Valid only together with `--start`. |
| `--station` | station code | all | Process only one station code, for example `VX`. |
| `--variable` | variable code | all | Process only one variable, for example `H`, `Q`, `T`, or `P`. |
| `--destination` | exact destination | all | Process only source rows whose configured `destination` exactly matches the supplied value. |
| `--no-incremental` | flag | off | Ignore existing archive timestamps when calculating the lower bound. Without `--start`, use `incremental.initial_start` directly. |
| `--dry-run` | flag | off | Show which sources would be processed without downloading or writing data. |
| `--stop-on-error` | flag | off | Stop after the first failed source instead of continuing with the remaining sources. |
| `--verbose` | flag | off | Enable debug-level logging. |

**Catalogue vs. filters:** `--sources` chooses which source catalogue to load. `--station`, `--variable`, and `--destination` then filter rows inside that selected catalogue. They never replace the source definitions themselves.

---

## 2. Command syntax

Installed package:

```bash
vhg-api [--version] {validate-config,download} ...
```

Repository-local runner:

```bash
python scripts/run_download.py [--version] {validate-config,download} ...
```

For command-specific help:

```bash
vhg-api validate-config --help
vhg-api download --help
```

---

## 3. `validate-config`

### Synopsis

```bash
vhg-api validate-config [--config PATH] [--env-file PATH] [--sources PATH] [--include-disabled]
```

### Purpose

`validate-config` loads the deployment configuration without downloading data. It reports the resolved settings and source-catalogue paths and lists the configured sources.

A normal check is:

```bash
vhg-api validate-config
```

For production or scheduled deployments, explicit absolute paths are recommended:

```bash
vhg-api validate-config \
  --config /opt/vhg_api/config/settings.yml \
  --env-file /opt/vhg_api/config/.env
```

On Windows:

```powershell
vhg-api validate-config --config "D:\Apps\vhg_api\config\settings.yml" --env-file "D:\Apps\vhg_api\config\.env"
```

### `--config PATH`

Selects the `settings.yml` file.

Example:

```bash
vhg-api validate-config --config D:/Apps/vhg_api/config/settings.yml
```

Relative file paths declared *inside* `settings.yml` are resolved relative to the directory containing the selected settings file. Therefore, if:

```text
D:/Apps/vhg_api/config/settings.yml
D:/Apps/vhg_api/config/sources.csv
```

and `settings.yml` contains:

```yaml
sources_file: sources.csv
```

then `sources.csv` is resolved as:

```text
D:/Apps/vhg_api/config/sources.csv
```

This remains true regardless of the process working directory.

### `--env-file PATH`

Selects the `.env` file used for credentials and deployment-specific environment variables.

Example:

```bash
vhg-api validate-config --env-file D:/Apps/vhg_api/config/.env
```

`--env-file` is independent of `--config`: the path supplied on the command line is used as supplied. For scheduled operation, an absolute path is recommended.

### `--sources PATH`

Overrides the source catalogue selected by `sources_file` in `settings.yml`. This is useful for tests, partial deployments, or alternate catalogues without editing the normal settings file.

```bash
vhg-api validate-config --sources sources_test.csv
```

If the supplied path is relative, it is resolved relative to the directory containing the active `settings.yml`. An absolute path is used unchanged. If `--sources` is omitted, `sources_file` from `settings.yml` is used.

### `--include-disabled`

By default, validation output lists only enabled source rows. Use:

```bash
vhg-api validate-config --include-disabled
```

to also display disabled rows. This is useful when checking future or temporarily inactive media configured in `sources.csv`.

---

## 4. `download`

### Synopsis

```bash
vhg-api download \
  [--config PATH] \
  [--env-file PATH] \
  [--sources PATH] \
  [--start UTC_DATETIME] \
  [--end UTC_DATETIME] \
  [--station CODE] \
  [--variable CODE] \
  [--destination PATH] \
  [--no-incremental] \
  [--dry-run] \
  [--stop-on-error] \
  [--verbose]
```

Without filters, `download` processes **all enabled rows** in the configured `sources.csv`.

---

## 5. Selecting the source catalogue and rows

The source catalogue is always required. By default it comes from `sources_file` in `settings.yml`. `--sources` temporarily overrides that choice:

```bash
# Default catalogue declared in settings.yml
vhg-api download

# Alternate catalogue, without editing settings.yml
vhg-api download --sources sources_test.csv
```

The selection order is:

```text
--sources PATH (if supplied)
        ↓ otherwise
sources_file from settings.yml
        ↓
load selected CSV catalogue
        ↓
apply --station / --variable / --destination filters
        ↓
download matching enabled rows
```

Thus `--station VX` does **not** bypass `sources.csv`; it selects the rows for station `VX` from whichever catalogue is active. The same principle applies to `--variable` and `--destination`. API identifiers, measurement sets, media, series IDs, and destinations still come from the selected CSV rows.

### `--sources PATH`

For a relative path, the base directory is the directory containing the active `settings.yml`. For example:

```bash
vhg-api download --config D:/VHG/config/settings.yml --sources sources_test.csv
```

loads:

```text
D:/VHG/config/sources_test.csv
```

An absolute `--sources` path is used unchanged.

---

## 6. Time selection and operating modes

The time-related options determine whether `vhg_api` performs a routine incremental update or an explicit historical refresh.

### 5.1 Normal incremental update

```bash
vhg-api download
```

For each selected source, the runner:

1. inspects the existing archive file;
2. finds the latest archived `datetime_utc`;
3. subtracts `incremental.overlap_minutes`;
4. downloads from that point to the current UTC minute;
5. merges the new rows with the existing yearly file;
6. sorts by `datetime_utc`;
7. removes duplicate timestamps, keeping the **newly downloaded row**.

The overlap allows delayed observations and recent retrospective corrections on the VHG/TDS platform to be picked up automatically.

If no archive exists yet, `incremental.initial_start` from `settings.yml` is used.

### 5.2 `--start UTC_DATETIME`

Supplying `--start` activates **historical-refresh mode**.

Example:

```bash
vhg-api download --start 2026-07-01T00:00:00Z
```

In historical-refresh mode, existing archive timestamps do **not** move the requested start forward. The explicit start is used exactly, and the end defaults to the current UTC minute.

This mode is intended for re-downloading older data after retrospective corrections on the VHG/TDS platform.

### 5.3 `--start` together with `--end`

Use both options to refresh a bounded period:

```bash
vhg-api download \
  --start 2025-05-01T00:00:00Z \
  --end 2025-05-31T23:59:59Z
```

The downloaded rows are merged into the existing archive. If an existing row and a newly downloaded row have the same `datetime_utc`, the newly downloaded row wins.

This makes historical refreshes safe for correcting previously archived values without rebuilding unrelated periods.

### 5.4 `--end UTC_DATETIME`

`--end` cannot be used alone.

This is invalid:

```bash
vhg-api download --end 2026-07-31T23:59:59Z
```

Use `--start` as well:

```bash
vhg-api download \
  --start 2026-07-01T00:00:00Z \
  --end 2026-07-31T23:59:59Z
```

### 5.5 `--no-incremental`

```bash
vhg-api download --no-incremental
```

This tells the runner not to use the latest timestamp already present in the archive when determining the lower bound.

Without `--start`, the lower bound becomes the configured:

```yaml
incremental:
  initial_start: "..."
```

This is mainly useful for recovery, testing, or a deliberate broad replay.

When `--start` is already supplied, historical-refresh mode is already non-incremental, so `--no-incremental` is unnecessary.

### Mode summary

| Invocation | Lower bound | Upper bound | Typical use |
|---|---|---|---|
| `vhg-api download` | Latest archive time minus overlap; or `initial_start` if no archive exists | Current UTC minute | Normal scheduled synchronization |
| `vhg-api download --start START` | Exact `START` | Current UTC minute | Refresh from a historical date through now |
| `vhg-api download --start START --end END` | Exact `START` | Exact `END` | Refresh a bounded historical period |
| `vhg-api download --no-incremental` | `incremental.initial_start` | Current UTC minute | Recovery or deliberate broad replay |

---

## 7. Source filters

Filters can be used in either incremental mode or historical-refresh mode. They reduce the enabled rows selected from `sources.csv`.

### `--station CODE`

Process only one station code:

```bash
vhg-api download --station VX
```

A station can still contain several enabled variables/media, so this may process several source rows.

Example historical refresh for one station:

```bash
vhg-api download \
  --station VX \
  --start 2025-05-01T00:00:00Z \
  --end 2025-05-31T23:59:59Z
```

### `--variable CODE`

Process only one variable:

```bash
vhg-api download --variable Q
```

The filter applies across all enabled stations unless combined with another filter.

Example:

```bash
vhg-api download --station VX --variable H
```

This is the recommended way to refresh a single station/variable combination after a correction:

```bash
vhg-api download \
  --station VX \
  --variable H \
  --start 2025-05-01T00:00:00Z \
  --end 2025-05-31T23:59:59Z
```

### `--destination PATH`

Process only source rows whose configured `destination` exactly matches the supplied value.

Example:

```bash
vhg-api download \
  --destination 01_Rivieres/stations/145_VX/raw_data/H
```

This filter acts on the `destination` value from `sources.csv`; it is not a replacement output directory and does not modify routing.

### Combining filters

Filters are combined. For example:

```bash
vhg-api download --station VX --variable H
```

selects rows matching both `station=VX` and `variable=H`.

---

## 7. Execution-control options

### `--dry-run`

```bash
vhg-api download --dry-run
```

Shows which source rows would be processed without contacting the API and without writing archive files.

Use it when checking filters or deployment configuration:

```bash
vhg-api download --station VX --variable H --dry-run
```

### `--stop-on-error`

The default behavior is resilient: if one source fails, the failure is logged and the runner continues with the remaining selected sources.

To stop immediately after the first source failure:

```bash
vhg-api download --stop-on-error
```

For unattended scheduled operation, the default continue-on-error behavior is generally preferable because healthy sources can still be updated.

### `--verbose`

```bash
vhg-api download --verbose
```

Enables debug-level logging in addition to the normal operational messages. This is primarily useful for diagnosis and troubleshooting.

---

## 8. Configuration-path behavior

### Default CLI paths

Unless overridden:

```text
--config   config/settings.yml
--env-file config/.env
```

For interactive use from the repository root this is convenient:

```bash
vhg-api download
```

For cron, Task Scheduler, services, or any execution where the working directory may be unpredictable, use explicit absolute paths:

```bash
vhg-api download \
  --config /opt/vhg_api/config/settings.yml \
  --env-file /opt/vhg_api/config/.env
```

### `sources_file` inside `settings.yml`

A relative `sources_file` is resolved relative to the directory containing `settings.yml`.

Example:

```yaml
sources_file: sources.csv
```

with:

```text
/opt/vhg_api/config/settings.yml
```

resolves to:

```text
/opt/vhg_api/config/sources.csv
```

An absolute `sources_file` path is used directly.

There is no separate `--sources` CLI option in the current release.

---

## 9. Archive update behavior

Downloaded data are stored in yearly CSV files according to each source row's configured destination.

During an update:

1. existing rows are loaded;
2. newly downloaded rows are appended after them;
3. rows are sorted by `datetime_utc`;
4. duplicate `datetime_utc` values are removed with the newly downloaded row taking precedence;
5. the yearly file is replaced atomically through a temporary file.

This behavior is intentional. If a value is changed retrospectively on VHG/TDS and that timestamp is downloaded again, the local raw archive is updated to the most recently downloaded value.

`vhg_api` does not maintain a SQLite state database. The raw archive itself supplies incremental state through its latest `datetime_utc` value.

---

## 10. Logging and exit codes

The runner writes operational messages to the console and to the configured log directory.

Typical log filename:

```text
<VHG_LOG_DIR>/vhg_api_YYYYMMDD.log
```

Exit codes are suitable for cron or monitoring:

| Exit code | Meaning |
|---:|---|
| `0` | All selected sources succeeded. |
| `1` | At least one source failed, or an execution error occurred. |
| `2` | Configuration or command-line usage error. |

By default, one source failure does not prevent the remaining sources from being processed. The process still returns a non-zero exit code so that scheduled-job monitoring can detect the problem.

---

## 11. Common command examples

### Validate the normal configuration

```bash
vhg-api validate-config
```

### Validate and display disabled sources

```bash
vhg-api validate-config --include-disabled
```

### Normal operational update of all enabled sources

```bash
vhg-api download
```

### Preview a run

```bash
vhg-api download --dry-run
```

### Update one station

```bash
vhg-api download --station VX
```

### Update one variable across all stations

```bash
vhg-api download --variable Q
```

### Update one station and one variable

```bash
vhg-api download --station VX --variable H
```

### Refresh one historical month for one series

```bash
vhg-api download \
  --station VX \
  --variable H \
  --start 2025-05-01T00:00:00Z \
  --end 2025-05-31T23:59:59Z
```

### Refresh a historical period for every enabled source

```bash
vhg-api download \
  --start 2025-05-01T00:00:00Z \
  --end 2025-05-31T23:59:59Z
```

### Force a replay from `incremental.initial_start`

```bash
vhg-api download --no-incremental
```

### Stop after the first failed source

```bash
vhg-api download --stop-on-error
```

### Enable diagnostic logging

```bash
vhg-api download --verbose
```

### Production run with explicit configuration paths

```bash
vhg-api download \
  --config /opt/vhg_api/config/settings.yml \
  --env-file /opt/vhg_api/config/.env
```

---

## 12. Scheduled execution

For unattended operation, use explicit paths and the Python environment used to install `vhg_api`.

Example cron entry:

```cron
15 * * * * /opt/vhg_api/.venv/bin/vhg-api download --config /opt/vhg_api/config/settings.yml --env-file /opt/vhg_api/config/.env
```

Repository-local execution is also supported:

```cron
15 * * * * /opt/vhg_api/.venv/bin/python /opt/vhg_api/scripts/run_download.py download --config /opt/vhg_api/config/settings.yml --env-file /opt/vhg_api/config/.env
```

The application writes its own log file. IT monitoring should additionally check the process exit code.

## TLS / institutional CA bundle

HTTPS certificate verification is enabled by default with `tls.verify: true`.
With an empty `VHG_CA_BUNDLE`, Requests uses its standard trusted CA store. On an
institutional network whose HTTPS proxy uses an internal CA, keep verification
enabled and set `VHG_CA_BUNDLE` in the selected `.env` to the PEM CA
certificate/bundle supplied by IT.

When explicitly required in a controlled environment, `tls.verify: false` in
`settings.yml` disables certificate verification. This is a configuration
setting, not a command-line option. It applies to all HTTP operations. An empty
`VHG_CA_BUNDLE` alone never disables verification.


## Long intervals and automatic chunking

The CLI accepts the overall interval; it does not require the operator to split
long periods manually. For each selected source, `vhg_api` divides the effective
interval into TDS requests of at most `download.chunk_hours` (24 hours by
default), concatenates the returned rows, and removes the deliberate duplicate
at each inclusive chunk boundary.

```yaml
download:
  chunk_hours: 24
```

This applies to all modes:

```bash
# First/normal synchronization
vhg-api download

# Historical refresh spanning a long period
vhg-api download --station ES --variable P \
  --start 2026-01-01T00:00:00Z --end 2026-08-01T00:00:00Z
```

With `--verbose`, each individual chunk interval is written at debug level in
the log. At normal logging level, a source that needs more than one request is
reported once with the number of chunks and configured maximum chunk duration.
If TDS still returns HTTP 500 for a dense source, reduce `download.chunk_hours`
(e.g. to 12 or 6) and retry the same command.
