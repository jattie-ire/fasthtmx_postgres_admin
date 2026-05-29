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

# Table permissions config from TOML
TABLE_PERMISSIONS = config.get("table_permissions", {})


def get_table_permissions(table_name: str) -> dict:
    """Get permissions for a table. Returns dict with allow_add, allow_delete, editable_columns"""
    if table_name not in TABLE_PERMISSIONS:
        # Unconfigured tables are read-only by default
        return {
            "allow_add": False,
            "allow_delete": False,
            "editable_columns": []
        }
    
    perms = TABLE_PERMISSIONS[table_name]
    return {
        "allow_add": perms.get("allow_add", False),
        "allow_delete": perms.get("allow_delete", False),
        "editable_columns": perms.get("editable_columns", [])
    }


def is_column_editable(table_name: str, column_name: str) -> bool:
    """Check if a specific column is editable"""
    perms = get_table_permissions(table_name)
    return column_name in perms["editable_columns"]


def can_add_rows(table_name: str) -> bool:
    """Check if rows can be added to this table"""
    return get_table_permissions(table_name)["allow_add"]


def can_delete_rows(table_name: str) -> bool:
    """Check if rows can be deleted from this table"""
    return get_table_permissions(table_name)["allow_delete"]

