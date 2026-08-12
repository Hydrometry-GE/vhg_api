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

If the proxy is reachable but the log contains
`CERTIFICATE_VERIFY_FAILED` / `unable to get local issuer certificate`, the
proxy is probably presenting a certificate signed by an institutional CA that
Python does not trust by default. The preferred solution is to ask IT for the
trusted CA certificate/bundle in PEM format, keep `tls.verify: true`, and set
`VHG_CA_BUNDLE` in `.env`. Leave the bundle empty on networks where the normal
public certificate chain works.

If operation on a controlled network explicitly requires bypassing certificate
verification, set `tls.verify: false` in `settings.yml`. This is intentionally a
visible setting rather than an automatic fallback: it disables HTTPS
server-certificate authentication. Restore `tls.verify: true` when normal trust
or an institutional CA bundle is available.

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


## A long first download returns only part of the expected data

Check `download.chunk_hours` in `settings.yml`. `vhg_api` should split every
long effective interval into bounded TDS requests (24 hours by default) and
concatenate them before writing the archive. A successful multi-month first
synchronization should therefore contain the full requested period rather than
only one day's worth of observations.

Run a focused source with verbose logging to inspect the individual chunks:

```bash
vhg-api download --station NAA --variable H --verbose
```

If the source has no existing archive, the first chunk starts at
`incremental.initial_start`. If an archive already exists, normal incremental
mode starts from the latest archived timestamp minus `overlap_minutes`. Use an
explicit `--start` for a deliberate historical replay.

## HTTP 500 on a dense or one-minute source

A TDS HTTP 500 can be caused by a request that is too large for the server. Long
requests are automatically chunked, but a particularly dense source may still
benefit from smaller chunks. Reduce, for example:

```yaml
download:
  chunk_hours: 12
```

or, if necessary, `6`, then rerun the same source or historical interval. This
changes only the internal API request size; it does not alter archive format,
source selection, or the requested overall time range.
