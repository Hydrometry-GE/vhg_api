"""Minimal example of loading vhg_api configuration."""

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from vhg_api.config import load_config  # noqa: E402

config = load_config(ROOT / "config/settings.yml", ROOT / "config/.env")
print(config.profile)
print(config.active_sources)
