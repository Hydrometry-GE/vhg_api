# Installation and execution

`vhg_api` can be used either directly from a checked-out repository or as an
installed Python package. Both modes execute the same command-line code.

## Requirements

- Python 3.10 or newer;
- network access to the configured TDS server;
- write access to all configured destinations and to the log directory.

A virtual environment is strongly recommended for scheduled deployments.

## Repository mode — no package installation

Create a virtual environment and install only the dependencies:

```bash
python -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -r requirements.txt
```

On Windows, replace `.venv/bin/python` with `.venv\Scripts\python.exe`.

Commands are then run through the repository wrapper:

```bash
.venv/bin/python scripts/run_download.py validate-config \
  --config config/settings.yml --env-file config/.env

.venv/bin/python scripts/run_download.py download \
  --config config/settings.yml --env-file config/.env
```

## Installed package mode

Install the project in editable mode during deployment or development:

```bash
python -m pip install -e .
```

This creates the console command:

```bash
vhg-api --version
vhg-api validate-config --config config/settings.yml --env-file config/.env
vhg-api download --config config/settings.yml --env-file config/.env
```

A regular, non-editable installation is also supported:

```bash
python -m pip install .
```

## Secrets

Copy `config/.env.example` to `config/.env` and adapt it locally. Never commit
`config/.env`. Real process environment variables override non-empty values in
the file, which allows an IT deployment system to inject secrets directly.
