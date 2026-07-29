# Configuration

`vhg_api` separates API/runtime settings from the operational source catalogue.

## settings.yml

Environment placeholders support `${NAME}` and `${NAME:-default}`.

```yaml
storage:
  root: ${DATA_ROOT:-}
  filename: "{series_id}_{variable}_{year}_raw.csv"
  log_dir: ${VHG_LOG_DIR}
```

`storage.root` is an optional default base folder. It is used only for relative
row destinations. It may be left empty when all destinations are absolute. The
filename template supports `series_id`, `station`, `variable`, and `year`.

## sources.csv

The semicolon-separated catalogue has one row per API source:

```text
enabled;station;series_id;measurement_set;variable;media;destination
```

`destination` is deliberately the last column and acts as the complete
row-specific routing rule up to the series folder. It may be relative or
absolute:

```csv
enabled;station;series_id;measurement_set;variable;media;destination
true;VX;145_VX;VX_;H;6;01_Rivieres/stations/145_VX/raw_data/H
true;AR;AR;AR_;P;1;D:/RainArchive/stations/AR/raw_data/P
true;VX;145_VX;VX_;BAT_INT;100;S:/Technical/VX/BAT_INT
true;XX;999_XX;XX_;H;6;//server/share/hydrometry/XX/H
```

Resolution rules:

- relative destination: `storage.root / destination`;
- absolute POSIX path beginning with `/`: used directly;
- Windows drive path such as `D:/` or `S:/`: used directly;
- UNC path such as `//server/share/...`: used directly.

The downloader then adds the UTC year and generated filename. Backslashes are
normalized to forward slashes. Relative paths containing `..` are rejected. If
a relative destination is selected while `storage.root` is empty, the download
fails with an explicit configuration error.

Row order is preserved. A duplicate is defined by
`station + measurement_set + variable` and is rejected explicitly.

## Proxy behaviour

Proxy use is controlled explicitly in `settings.yml`. When disabled, proxy
values are ignored. When enabled, at least one proxy address must be defined.


## Incremental settings

```yaml
incremental:
  initial_start: "2026-01-01T00:00:00Z"
  overlap_minutes: 1440
```

`initial_start` is the lower bound for a source with no existing archive.
`overlap_minutes` controls how far the next incremental request moves backwards
from the latest stored datetime before merging and deduplicating the result.
