# Configuration

## Configuration-file path resolution

The path passed with `--config` locates `settings.yml`. Once that file has been
selected, every relative companion-file path declared inside it is interpreted
relative to the directory containing that exact settings file. It is **not**
interpreted relative to the shell or scheduler working directory.

For example:

```text
D:/Apps/vhg_api/config/
├── settings.yml
├── sources.csv
└── .env
```

with:

```yaml
sources_file: sources.csv
```

and:

```bash
vhg-api download --config D:/Apps/vhg_api/config/settings.yml \
  --env-file D:/Apps/vhg_api/config/.env
```

always resolves the catalogue as:

```text
D:/Apps/vhg_api/config/sources.csv
```

This remains true when the command is launched from another directory. An
absolute `sources_file` value is used unchanged.

The CLI may override this setting with `--sources PATH`. A relative `--sources` value is also resolved from the directory containing the active `settings.yml`; an absolute override is used unchanged. The override does not modify `settings.yml`.

`--env-file` is independent: its value is an externally supplied CLI path and
is therefore used exactly as supplied (absolute paths are recommended for
scheduled production runs). Resolving `sources_file` relative to `settings.yml`
does not alter environment-file path handling.


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

### TLS certificate verification

TLS behavior is controlled explicitly in `settings.yml`:

```yaml
tls:
  verify: true
  ca_bundle: ${VHG_CA_BUNDLE:-}
```

The combinations are:

| `tls.verify` | CA bundle | Behavior |
| --- | --- | --- |
| `true` | empty | Normal secure verification using Requests' default trusted CA store. |
| `true` | configured | Secure verification using the specified PEM CA certificate/bundle. |
| `false` | any value | Certificate verification is explicitly disabled. |

`verify: true` is the default and recommended setting. On an institutional
network where an HTTPS proxy presents certificates signed by an internal CA, IT
can provide a PEM CA certificate or bundle through `.env`:

```dotenv
VHG_CA_BUNDLE=C:/certs/institution-ca.pem
```

A relative CA-bundle path is resolved relative to the active `settings.yml`. If
a configured bundle does not exist, configuration loading fails early.

If the controlled network requires operation before a suitable CA bundle is
available, verification can be disabled deliberately with `tls.verify: false`.
This is an explicit security choice: it prevents HTTPS server-certificate
authentication and should not be used when normal verification or an
institutional CA bundle is available. Importantly, leaving `VHG_CA_BUNDLE` empty
does **not** disable verification.


## Incremental settings

```yaml
incremental:
  initial_start: "2026-01-01T00:00:00Z"
  overlap_minutes: 1440
```

`initial_start` is the lower bound for a source with no existing archive.
`overlap_minutes` controls how far the next incremental request moves backwards
from the latest stored datetime before merging and deduplicating the result.

## Download chunking

Long TDS intervals are split into bounded API requests before the returned rows
are concatenated:

```yaml
download:
  chunk_hours: 24
```

`chunk_hours` must be an integer greater than zero. The default is `24` hours.
This setting applies equally to first synchronizations, routine incremental
updates, and explicit historical refreshes. It does not change the requested
overall interval; it only limits the duration of each individual `get_values`
request sent to TDS.

Chunk boundaries are inclusive because the TDS API uses inclusive time bounds.
Adjacent chunks therefore share one boundary timestamp. `vhg_api` sorts the
combined rows and removes duplicate `datetime_utc` values with a keep-last
policy, so the later chunk wins at that intentional overlap and no boundary
observation is lost.

A 24-hour default is deliberately conservative for dense one-minute series and
for long first synchronizations. If a particular deployment still receives TDS
server errors on dense sources, a smaller value such as `12` or `6` hours can be
used without changing the source catalogue or CLI commands.
