# Troubleshooting

## Configuration error before any download

Run:

```bash
vhg-api validate-config --config config/settings.yml --env-file config/.env
```

Typical causes are a missing environment variable, an invalid `sources.csv`
column, a duplicate mapping, or a relative destination without `DATA_ROOT`.

## No configured sources match

Check the spelling and case of `--station`, `--variable`, or `--destination`.
The destination filter is an exact normalized path match.

## Permission error

The runtime account needs write access to:

- every selected destination;
- `VHG_LOG_DIR`;
- parent directories needed for new yearly folders.

## Proxy or connectivity failure

Set `proxy.enabled: true` only when a proxy is required and define at least one
of `HTTP_PROXY` or `HTTPS_PROXY`. Use the numbered connection test scripts to
separate configuration, ping, authentication, and access-right problems.

## One source fails but others continue

This is the default production behaviour. The command returns exit code `1` and
records the complete exception in the daily log. Use `--stop-on-error` when an
immediate stop is preferable during diagnostics.

## First run downloads too much or too little history

Adjust `incremental.initial_start` in `config/settings.yml` for the first normal
run. To deliberately synchronize a historical period, supply `--start` and
optionally `--end`; this activates historical-refresh mode and ignores archive
state for the lower bound. Once files exist, normal incremental runs use their latest stored
datetime and the configured overlap.

## A retrospective correction is not appearing

A normal run only re-downloads the configured overlap. If the corrected timestamp
is older, explicitly refresh the affected interval and preferably filter the
source:

```bash
vhg-api download --station VX --variable H \
  --start 2025-05-01T00:00:00Z --end 2025-05-31T23:59:59Z
```

The downloaded record replaces the archived record with the same `datetime_utc`.
Check the daily log to confirm the selected source, interval, row count, and
written file.

## `--end` is rejected

`--end` must be paired with `--start`. An upper bound alone is ambiguous because
there is no explicit historical lower bound. Use both options for a bounded
refresh, or omit both for a normal incremental run.
