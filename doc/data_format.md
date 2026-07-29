# Raw data format

Each configured source is stored in semicolon-separated yearly CSV files.

Canonical columns:

```text
timestamp;datetime_utc;value;station;series_id;variable;measurement_set;media
```

- `timestamp`: Unix epoch seconds, derived from `datetime_utc`;
- `datetime_utc`: authoritative timezone-aware UTC datetime;
- `value`: value returned by the API;
- `station`: operational station code;
- `series_id`: stable identifier used in filenames and stored records;
- `variable`: configured variable code;
- `measurement_set`: API measurement-set identifier;
- `media`: API media identifier.

`datetime_utc` is authoritative for sorting, merging, deduplication, and overlap
calculation. `timestamp` is retained as a convenient numeric representation of
the same instant. Files created before v0.8.1 without `timestamp` are migrated
automatically on their next update.

The default filename is:

```text
{series_id}_{variable}_{year}_raw.csv
```

Files are placed below the row-level `destination`, in a subfolder named after
the UTC calendar year.
