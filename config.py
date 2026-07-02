"""Configuration management"""
import tomllib
from pathlib import Path

# ============================================================================
# CONFIG CACHING
# ============================================================================

_config_path = Path(__file__).parent / "config.toml"
_cached_config = None

def load_config():
    """Load configuration from TOML file (cached)"""
    global _cached_config
    if _cached_config is None:
        reload_config()
    return _cached_config


def reload_config():
    """Reload configuration from disk (bypasses cache)"""
    global _cached_config
    try:
        with open(_config_path, "rb") as f:
            _cached_config = tomllib.load(f)
        print("✓ Configuration reloaded from disk")
    except Exception as e:
        print(f"ERROR loading config: {e}")
        import traceback
        traceback.print_exc()
        _cached_config = {}
    return _cached_config


# Load config on module import
config = load_config()

# Database config from TOML
DB_CONFIG = config.get("database", {})

# App config from TOML
APP_CONFIG = config.get("app", {})

# User management table name
FASTAPI_USERS_TABLE = APP_CONFIG.get("fastapi_users_table", "fastapi_users")

# Kerberos domain for authentication
KERBEROS_DOMAIN = APP_CONFIG.get("kerberos_domain", "FASTHTMX.LOCAL")

# Scripts config from TOML
SCRIPTS_CONFIG = config.get("scripts", {})

# Deploy tools config from TOML
DEPLOY_TOOLS_CONFIG = config.get("deploy_tools", {})

# Table permissions config from TOML
TABLE_PERMISSIONS = config.get("table_permissions", {})

# Kerberos login config from TOML
KERBEROS_LOGIN_CONFIG = config.get("kerberos_login", {})

# Audit trail config from TOML
AUDIT_TRAIL_CONFIG = config.get("audit_trail", {})


def get_table_display_name(table_name: str) -> str:
    """Get display name for a table, falling back to table_name if not configured"""
    if table_name in TABLE_PERMISSIONS:
        display_name = TABLE_PERMISSIONS[table_name].get("display_name")
        if display_name:
            return display_name
    return table_name


def get_kerberos_login_text() -> dict:
    """Get Kerberos login page customizable text with defaults"""
    return {
        "header_text": KERBEROS_LOGIN_CONFIG.get("header_text", "Kerberos Login"),
        "username_placeholder": KERBEROS_LOGIN_CONFIG.get("username_placeholder", "Username"),
        "password_placeholder": KERBEROS_LOGIN_CONFIG.get("password_placeholder", "Password"),
        "username_required_message": KERBEROS_LOGIN_CONFIG.get("username_required_message", "Please enter your username"),
        "password_required_message": KERBEROS_LOGIN_CONFIG.get("password_required_message", "Please enter your password"),
    }


def get_audit_trail_table_name() -> str:
    """Get audit trail table name from config, default to fastapi_audit_trail"""
    return AUDIT_TRAIL_CONFIG.get("table_name", "fastapi_audit_trail")


def is_script_background(script_name: str) -> bool:
    """Check if a script should run in the background (default: False)"""
    if not isinstance(SCRIPTS_CONFIG, dict):
        return False
    # Check run_in_background subsection
    bg_scripts = SCRIPTS_CONFIG.get("run_in_background", {})
    return bg_scripts.get(script_name, False)


def get_script_timeout(script_name: str) -> int:
    """Get execution timeout in seconds for a script (default: 300 seconds)"""
    if not isinstance(SCRIPTS_CONFIG, dict):
        return 300
    # Check timeout subsection
    timeouts = SCRIPTS_CONFIG.get("timeout", {})
    timeout = timeouts.get(script_name)
    if isinstance(timeout, int) and timeout > 0:
        return timeout
    return 300


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


# User permission helper functions (checked against fastapi_users table)
def get_user_permission_level(user_perms: dict, action: str) -> bool:
    """
    Check if user has permission for an action.
    
    Args:
        user_perms: Dict from database with keys: view, edit, add, delete, admin
        action: One of 'view', 'edit', 'add', 'delete', 'admin'
    
    Returns:
        Boolean permission status
    """
    return user_perms.get(action, False)


def can_user_view(user_perms: dict) -> bool:
    """Check if user has view permission"""
    return get_user_permission_level(user_perms, 'view')


def can_user_edit(user_perms: dict) -> bool:
    """Check if user has edit permission"""
    return get_user_permission_level(user_perms, 'edit')


def can_user_add(user_perms: dict) -> bool:
    """Check if user has add permission"""
    return get_user_permission_level(user_perms, 'add')


def can_user_delete(user_perms: dict) -> bool:
    """Check if user has delete permission"""
    return get_user_permission_level(user_perms, 'delete')


def is_user_admin(user_perms: dict) -> bool:
    """Check if user has admin permission"""
    return get_user_permission_level(user_perms, 'admin')


def can_user_run_scripts(user_perms: dict) -> bool:
    """Check if user has run_scripts permission"""
    return user_perms.get('run_scripts', False)


# Combined permission checkers (user + table level)
def can_user_view_table(user_perms: dict) -> bool:
    """Check if user has view permission globally"""
    return can_user_view(user_perms)


def can_user_edit_table(user_perms: dict, table_name: str) -> bool:
    """Check if user can edit: user must have edit permission AND table must allow edits"""
    user_can_edit = can_user_edit(user_perms)
    table_allows_edit = len(get_table_permissions(table_name)["editable_columns"]) > 0
    return user_can_edit and table_allows_edit


def can_user_add_to_table(user_perms: dict, table_name: str) -> bool:
    """Check if user can add rows: user must have add permission AND table must allow adds"""
    user_can_add = can_user_add(user_perms)
    table_allows_add = can_add_rows(table_name)
    return user_can_add and table_allows_add


def can_user_delete_from_table(user_perms: dict, table_name: str) -> bool:
    """Check if user can delete rows: user must have delete permission AND table must allow deletes"""
    user_can_delete = can_user_delete(user_perms)
    table_allows_delete = can_delete_rows(table_name)
    return user_can_delete and table_allows_delete


def get_script_log_config(script_name: str) -> dict:
    """Get log configuration for a script
    
    Returns dict with:
        - directory: path to log directory (None if not configured)
        - pattern: glob pattern for log files (None if not configured)
        - display: whether to display log in UI (default: True if configured)
        - limit: number of recent logs to display per script (default: 5)
    """
    if not isinstance(SCRIPTS_CONFIG, dict):
        return {"directory": None, "pattern": None, "display": False, "limit": 5}
    
    log_config = SCRIPTS_CONFIG.get("log_config", {})
    if isinstance(log_config, dict) and script_name in log_config:
        cfg = log_config[script_name]
        if isinstance(cfg, dict):
            return {
                "directory": cfg.get("directory"),
                "pattern": cfg.get("pattern"),
                "display": cfg.get("display", True),
                "limit": cfg.get("limit", 5)
            }
    
    return {"directory": None, "pattern": None, "display": False, "limit": 5}




def get_log_display_limit() -> int:
    """Get the maximum number of logs per script to display in viewer (default: 5)"""
    if not isinstance(SCRIPTS_CONFIG, dict):
        return 5
    
    log_display = SCRIPTS_CONFIG.get("log_display", {})
    if isinstance(log_display, dict):
        return log_display.get("limit", 5)
    
    return 5
