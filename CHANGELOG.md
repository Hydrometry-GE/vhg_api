# Changelog

## Unreleased

- Formalize and test that relative `sources_file` paths are resolved from the directory containing the selected `settings.yml`, including custom `--config` locations.
- Add `--sources PATH` to `download` and `validate-config` as a temporary source-catalogue override, with relative paths resolved beside the active `settings.yml`.
- Document that `--env-file` remains an independent CLI path and is not affected by settings-relative path resolution.
- Show resolved settings and sources paths in `validate-config` output.

- Add explicit historical-refresh semantics: supplying `--start` bypasses incremental archive-state calculation, while optional `--end` bounds the refresh.
- Reject `--end` without `--start` to avoid an ambiguous download range.
- Document and test that newly downloaded rows replace archived rows at duplicate `datetime_utc` values.
- Expand operational, download, troubleshooting, CLI, and function documentation for retrospective synchronization.

- Remove the unused SQLite/state-database configuration and placeholder module.
- Remove local user-specific destination paths from the example source catalogue.
- Make the repository-local runner resolve default configuration paths from the project root.
- Expand module, class, method, and helper-function documentation.
- Remove generated build and cache artifacts from the repository candidate.

## 1.0.0 - 2026-07-29

- Add the production `vhg-api download` command for manual and scheduled runs.
- Add a repository-local `scripts/run_download.py` entry point requiring no package installation.
- Add configurable `incremental.initial_start`.
- Add dry-run and station, variable, and destination filters.
- Continue source-by-source after failures by default while returning a non-zero exit code.
- Add daily console/file logging and final run summaries.
- Formalize the installable package and console entry point.
- Expand installation, operations, cron, data-format, and troubleshooting documentation.
- Retain the canonical `timestamp` and `datetime_utc` raw columns introduced in 0.8.1.

## 0.8.1 - 2026-07-29

- Added `timestamp` as the first canonical raw-data column.
- Store Unix epoch time as integer seconds derived from `datetime_utc`.
- Kept `datetime_utc` as the authoritative time field for sorting, merging, and deduplication.
- Added automatic migration support for existing raw CSV files without a `timestamp` column.
- Updated tests and documentation for the revised schema.

## 0.8.0 - 2026-07-29

- Renamed `configs/` to `config/` and `docs/` to `doc/`.
- Updated all scripts, CLI defaults, examples, tests, and documentation paths.
- Renamed `archive_id` to `series_id` throughout the configuration model, raw schema, filenames, and documentation.
- Added a corrected `06_test_destination_routing.py` using the same bootstrap and configuration loading as test 05.
- Kept test 05 as a safe runtime download test while test 06 exercises configured relative and absolute destinations.
- Removed generated caches and downloaded test files from the release archive.

## 0.7.0 - 2026-07-29

- Allowed each `sources.csv` destination to be either relative or absolute.
- Added OS-independent recognition of POSIX, Windows-drive, and UNC paths.
- Made `DATA_ROOT` optional and limited it to anchoring relative destinations.
- Kept absolute destinations independent from `DATA_ROOT`, enabling direct
  routing to different drives, network shares, and technical-data locations.
- Continued to reject `..` traversal in relative destinations.
- Added tests for `/...`, `D:/...`, `S:/...`, UNC paths, optional roots, and
  absolute-path output routing.

## 0.6.0 - 2026-07-29

- Replaced named archive routing with a generic row-level `destination` column.
- Added one machine-specific `DATA_ROOT` storage root.
- Made destinations portable relative paths resolved below `DATA_ROOT`.
- Added protection against absolute paths and `..` path traversal.
- Allowed hydrological, rainfall, technical, and test variables to use
  independent destinations without Python changes.
- Retained yearly splitting, incremental overlap, merge, sorting, and newest-row
  timestamp deduplication.
- Updated examples, manual tests, automated tests, and documentation.

## 0.5.0 - 2026-07-29

- Added separate river and rainfall archive routing (superseded by 0.6.0).

## 0.4.0 - 2026-07-29

- Added canonical self-describing raw columns: `datetime_utc`, `value`,
  `station`, `series_id`, `variable`, `measurement_set`, and `media`.
- Added `update_raw_archive()` with chronological merge and newest-value
  timestamp deduplication.
- Added atomic CSV replacement to avoid partially written raw files.
- Added `incremental_start()` and optional incremental configured downloads.
- Changed the default incremental overlap to 1440 minutes (24 hours).
