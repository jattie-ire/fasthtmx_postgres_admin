"""Configuration management"""
import tomllib
from pathlib import Path

# Load configuration from TOML file
config_path = Path(__file__).parent / "config.toml"
with open(config_path, "rb") as f:
    config = tomllib.load(f)

# Database config from TOML
DB_CONFIG = config.get("database", {})

# Scripts config from TOML
SCRIPTS_CONFIG = config.get("scripts", {})
