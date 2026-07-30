# Operational runner


> **Path safety:** `sources_file: sources.csv` is resolved beside the selected
> `settings.yml`, even when `--config` is absolute and the scheduler starts in a
> different working directory. `--env-file` remains an independent CLI path;
> use an absolute value in production schedules.

The `download` command is the production entry point for both manual execution
and cron. It updates all enabled rows in `config/sources.csv` unless filters are
provided.

## Standard incremental run

Installed package:

```bash
vhg-api download --config config/settings.yml --env-file config/.env
```

Repository mode:

```bash
python scripts/run_download.py download \
  --config config/settings.yml --env-file config/.env
```

Incremental mode is enabled by default. For each source, the runner looks at the
existing file for the end year, restarts from the latest archived datetime minus
`incremental.overlap_minutes`, downloads the overlap again, and safely merges by
`datetime_utc`.

When no archive exists, the lower bound is `incremental.initial_start`. The end
bound defaults to the current UTC minute and is fixed once for the complete run,
so all selected sources use the same period.

## Historical refreshes

Values may be corrected retrospectively in TDS. An ordinary incremental run can
only discover corrections that fall inside its configured overlap. To synchronize
an older interval, provide an explicit `--start`:

```bash
vhg-api download \
  --start 2026-07-01T00:00:00Z \
  --end 2026-07-31T23:59:59Z
```

The presence of `--start` automatically activates **historical-refresh mode**.
In this mode, the downloader:

1. ignores the latest timestamp already present in the archive when calculating
   the lower bound;
2. requests the explicit interval from TDS;
3. merges the downloaded rows into the existing yearly files;
4. retains the newly downloaded row when `datetime_utc` is duplicated.

This means a corrected TDS value replaces the older local value without deleting
or rebuilding the rest of the archive. The `--end` option is optional and
defaults to the current UTC minute, but it cannot be used without `--start`.

A focused refresh is recommended when only one series was corrected:

```bash
vhg-api download \
  --station VX \
  --variable H \
  --start 2025-05-01T00:00:00Z \
  --end 2025-05-31T23:59:59Z
```

The same command can cross year boundaries. Downloaded rows are split into the
appropriate yearly archive files before merging.

## Command modes

| Command | Lower-bound behaviour | Typical use |
|---|---|---|
| `vhg-api download` | Latest archive datetime minus overlap | Scheduled operational update |
| `vhg-api download --start ...` | Uses the explicit start exactly | Refresh from a date through now |
| `vhg-api download --start ... --end ...` | Uses both explicit bounds exactly | Refresh a bounded historical interval |
| `vhg-api download --no-incremental` | Uses configured `incremental.initial_start` | Recovery or deliberate broad replay |

`--no-incremental` is not required when `--start` is supplied; an explicit start
already disables archive-state calculation.

## Filters and dry runs

Preview selected sources without contacting the API or writing files:

```bash
vhg-api download --dry-run
```

Limit either an incremental run or a historical refresh:

```bash
vhg-api download --station VX
vhg-api download --station VX --variable H
vhg-api download --destination 01_Rivieres/stations/145_VX/raw_data/H
```

Stop immediately instead of continuing with healthy sources after a failure:

```bash
vhg-api download --stop-on-error
```

## Logs and exit codes

The command writes to the console and to one daily UTF-8 log file:

```text
<VHG_LOG_DIR>/vhg_api_YYYYMMDD.log
```

Exit codes:

- `0`: every selected source succeeded;
- `1`: at least one source failed, or an execution error occurred;
- `2`: invalid configuration.

By default a failed source is logged and the runner continues with the remaining
sources. The final log entry reports succeeded sources, failed sources, rows,
files, and total duration. This behaviour is suitable for cron: healthy series
are still updated, while the non-zero exit status remains visible to monitoring.

## Cron example

Use absolute paths and the Python executable from the deployment virtual
environment:

```cron
15 * * * * cd /opt/vhg_api && /opt/vhg_api/.venv/bin/vhg-api download --config /opt/vhg_api/config/settings.yml --env-file /opt/vhg_api/config/.env
```

Repository mode is equally valid:

```cron
15 * * * * cd /opt/vhg_api && /opt/vhg_api/.venv/bin/python /opt/vhg_api/scripts/run_download.py download --config /opt/vhg_api/config/settings.yml --env-file /opt/vhg_api/config/.env
```

The application already writes its own log file; shell redirection is optional.
The IT deployment should additionally monitor the process exit code and protect
the `.env` file with appropriate filesystem permissions.

## Persistent state

`vhg_api` does not create or maintain a SQLite database. For each source, the
latest `datetime_utc` found in the existing yearly CSV determines the next
incremental range. Daily log files provide operational history. This avoids a
second state store that could diverge from the raw archive.

## Safe interruption and reruns

Yearly archives are rewritten atomically through a temporary file. A later rerun
is safe because existing and downloaded rows are merged, sorted, and deduplicated
by `datetime_utc`, with newly downloaded rows taking precedence inside the
overlap.
