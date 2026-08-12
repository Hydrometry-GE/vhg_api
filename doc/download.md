# Downloading configured data

`download_configured()` resolves enabled rows from `config/sources.csv`, calls
the TDS API, and returns one `DownloadResult` per source.

## Canonical raw schema

Every returned frame and exported CSV uses these columns, in order:

```text
timestamp
datetime_utc
value
station
series_id
variable
measurement_set
media
```

`datetime_utc` is the canonical, human-readable UTC datetime. `timestamp` is
the corresponding Unix epoch value in whole seconds and is regenerated from
`datetime_utc` whenever data are normalized or written. Older raw files without
this column are migrated automatically on their next update.

## Destination routing

With `write_csv=True` and no `output_dir`, every source is written according to
its own `destination` value.

For a relative destination:

```text
01_Rivieres/stations/145_VX/raw_data/H
```

and `DATA_ROOT=D:/Hydrometrie`, the yearly file is:

```text
D:/Hydrometrie/01_Rivieres/stations/145_VX/raw_data/H/2026/145_VX_H_2026_raw.csv
```

For an absolute destination such as:

```text
S:/Technical/VX/BAT_INT
```

the root is bypassed and the yearly file is written directly below that path.
POSIX (`/srv/...`) and UNC (`//server/share/...`) absolute paths are also
recognized.

This routing is archive-agnostic. Different variables from the same station may
be sent to different drives, shares, archives, or temporary folders.

Data crossing a calendar-year boundary are split into separate yearly files.
`DownloadResult.output_files` contains every written path; `output_file` remains
a convenience property when exactly one yearly file was produced.

For tests or ad-hoc extraction, `output_dir` overrides row routing:

```python
results = download_configured(
    config,
    start="2026-01-01T00:00:00Z",
    end="2026-01-02T00:00:00Z",
    output_dir="runtime/downloads",
    write_csv=True,
)
```

## Merge precedence and retrospective corrections

Existing yearly CSVs are merged rather than blindly overwritten. The merge is
ordered deliberately: archived rows are placed first and newly downloaded rows
second. Deduplication then uses `datetime_utc` with a keep-last policy. Therefore,
when both frames contain the same timestamp, the newly downloaded TDS record is
retained.

This rule is part of the archive contract, not merely an implementation detail.
It allows corrected values on TDS to propagate into the local archive while
leaving all other timestamps unchanged. Sorting, deduplication, timestamp
regeneration, and file replacement are performed before an atomic rewrite.

## Incremental overlap versus historical refresh

The default incremental overlap is 1440 minutes (24 h). It automatically picks
up late or corrected values only when their timestamps fall inside that overlap.
A correction older than the overlap is invisible until its period is downloaded
again.

The CLI handles this through explicit bounds:

```bash
vhg-api download --start 2025-01-01T00:00:00Z --end 2025-01-31T23:59:59Z
```

Supplying `--start` disables incremental lower-bound calculation. The exact
requested period is downloaded and passed through the same merge policy, so
historical duplicate timestamps replace their previous archived values. `--end`
is optional but may not be supplied without `--start`.

## Bounded API requests for long periods

`vhg_api` does not send an arbitrarily long requested period as one TDS
`get_values` call. The effective interval for each source is split into chunks
controlled by:

```yaml
download:
  chunk_hours: 24
```

For example, a request from 2026-01-01 00:00 UTC through 2026-01-03 12:00 UTC
with `chunk_hours: 24` is sent as three API calls:

```text
2026-01-01 00:00 -> 2026-01-02 00:00
2026-01-02 00:00 -> 2026-01-03 00:00
2026-01-03 00:00 -> 2026-01-03 12:00
```

The repeated boundary timestamp is intentional. All non-empty chunk frames are
concatenated, sorted by `datetime_utc`, and deduplicated with `keep="last"`.
Only after the full source interval has been assembled is it enriched with the
source metadata and written to the yearly raw archive.

This behavior is especially important for first synchronizations and dense
one-minute measurements, where a single multi-month API request can be
incomplete or can trigger a TDS server error. Chunking is internal: operators
continue to use the same `vhg-api download`, `--start`, and `--end` commands.
