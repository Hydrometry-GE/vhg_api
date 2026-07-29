# Operational runner

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

## Useful commands

Preview the selected sources without contacting the API or writing files:

```bash
vhg-api download --dry-run
```

Limit a run:

```bash
vhg-api download --station VX
vhg-api download --station VX --variable H
vhg-api download --destination 01_Rivieres/stations/145_VX/raw_data/H
```

Run an explicit interval:

```bash
vhg-api download \
  --start 2026-07-01T00:00:00Z \
  --end 2026-07-31T00:00:00Z
```

Ignore existing files and use the supplied/configured lower bound directly:

```bash
vhg-api download --no-incremental --start 2026-01-01T00:00:00Z
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
