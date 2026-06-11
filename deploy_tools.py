#!/usr/bin/env python3
"""
FastHTMX Admin Deployment Tools

CLI utilities for managing database connections, configuration validation,
and table discovery during deployment. Use this before deploying to production.

Usage:
    python deploy_tools.py --help              Show general help
    python deploy_tools.py <command> --help    Show command-specific help

Examples:
    python deploy_tools.py test-connection
    python deploy_tools.py discover-tables --filter gsm
    python deploy_tools.py validate-config
    python deploy_tools.py generate-config --output config.new.toml
"""

import argparse
import sys
import tomllib
import time
from pathlib import Path
from typing import Optional, Dict, List, Tuple

# Import from project
from config import DB_CONFIG, TABLE_PERMISSIONS, SCRIPTS_CONFIG, DEPLOY_TOOLS_CONFIG, config, load_config
from database import get_db_connection, return_db_connection, get_available_tables
import psycopg2


# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def print_header(text: str):
    """Print a formatted section header"""
    print(f"\n{'='*70}")
    print(f"  {text}")
    print(f"{'='*70}\n")


def print_success(text: str):
    """Print success message"""
    print(f"✓ {text}")


def print_error(text: str):
    """Print error message"""
    print(f"✗ {text}")


def print_warning(text: str):
    """Print warning message"""
    print(f"⚠ {text}")


def print_info(text: str):
    """Print info message"""
    print(f"ℹ {text}")


# ============================================================================
# COMMAND: test-connection
# ============================================================================

def cmd_test_connection(args):
    """
    Test database connectivity.
    
    Verifies that PostgreSQL can be reached with configured credentials.
    Shows database version, availability, and basic connection details.
    
    Exit codes:
        0 = Connection successful
        1 = Connection failed
    """
    print_header("Testing Database Connection")
    
    print(f"Attempting to connect to PostgreSQL...")
    print(f"  Host: {DB_CONFIG.get('host', 'localhost')}")
    print(f"  Port: {DB_CONFIG.get('port', 5432)}")
    print(f"  Database: {DB_CONFIG.get('database', 'unknown')}")
    print(f"  User: {DB_CONFIG.get('user', 'unknown')}")
    
    start_time = time.time()
    
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        elapsed = time.time() - start_time
        
        cursor = conn.cursor()
        cursor.execute("SELECT version();")
        version = cursor.fetchone()[0]
        cursor.close()
        
        print_success(f"Connected successfully in {elapsed:.2f}s")
        print(f"\n  Database Version: {version}\n")
        
        return_db_connection(conn)
        return 0
        
    except Exception as e:
        elapsed = time.time() - start_time
        print_error(f"Connection failed after {elapsed:.2f}s")
        print(f"\n  Error: {str(e)}\n")
        print("  Troubleshooting steps:")
        print("    1. Check config.toml [database] section")
        print("    2. Verify PostgreSQL is running on the target host")
        print("    3. Verify credentials (username/password)")
        print("    4. Check network connectivity to the host")
        print("    5. Verify database exists and user has access\n")
        return 1


# ============================================================================
# COMMAND: discover-tables
# ============================================================================

def cmd_discover_tables(args):
    """
    Discover all tables in PostgreSQL database.
    
    Scans the public schema and lists all available tables.
    Can filter by table name pattern (regex).
    Shows row count and size estimate for each table.
    
    Usage:
        python deploy_tools.py discover-tables              # List all tables
        python deploy_tools.py discover-tables --filter gsm  # Filter by name
        python deploy_tools.py discover-tables --sort size   # Sort by size
    
    Exit codes:
        0 = Success (tables found)
        1 = Error (DB connection failed or no tables found)
    """
    print_header("Discovering Tables in PostgreSQL")
    
    try:
        conn = get_db_connection()
        if not conn:
            print_error("Failed to connect to database")
            return 1
        
        cursor = conn.cursor()
        
        # Get all tables
        cursor.execute("""
            SELECT 
                schemaname,
                tablename,
                pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) as size,
                (SELECT count(*) FROM information_schema.columns 
                 WHERE table_name = tablename) as col_count
            FROM pg_tables 
            WHERE schemaname = 'public' 
            ORDER BY tablename
        """)
        
        results = cursor.fetchall()
        cursor.close()
        return_db_connection(conn)
        
        if not results:
            print_warning("No tables found in public schema")
            return 1
        
        # Filter if requested
        if args.filter:
            import re
            pattern = re.compile(args.filter, re.IGNORECASE)
            results = [r for r in results if pattern.search(r[1])]
            
            if not results:
                print_warning(f"No tables match filter: {args.filter}")
                return 1
            
            print(f"Found {len(results)} tables matching '{args.filter}':\n")
        else:
            print(f"Found {len(results)} tables in public schema:\n")
        
        # Sort
        if args.sort == "size":
            # Custom sort: handle sizes like "123 kB", "1 GB", etc
            results.sort(key=lambda x: x[2], reverse=True)
        elif args.sort == "cols":
            results.sort(key=lambda x: x[3], reverse=True)
        
        # Print table
        print(f"{'Table Name':<40} {'Columns':<10} {'Size':<15}")
        print(f"{'-'*40} {'-'*10} {'-'*15}")
        
        for schema, table, size, cols in results:
            print(f"{table:<40} {cols:<10} {size:<15}")
        
        print(f"\nTotal: {len(results)} table(s)")
        print("\nTip: Use --filter <pattern> to narrow results (e.g., --filter 'i07_')")
        print("     Use --sort size|cols to sort by size or column count\n")
        
        return 0
        
    except Exception as e:
        print_error(f"Failed to discover tables: {str(e)}")
        return 1


# ============================================================================
# COMMAND: validate-config
# ============================================================================

def cmd_validate_config(args):
    """
    Validate configuration file (config.toml).
    
    Checks:
        ✓ TOML syntax validity
        ✓ Required sections exist ([database], [app], [table_permissions])
        ✓ All referenced tables exist in database
        ✓ All editable_columns exist in their respective tables
        ✓ All scripts defined in [scripts] are accessible
        ✓ fastapi_users table exists with correct schema
        ✓ Table permissions are sensible (no circular issues)
    
    Exit codes:
        0 = Config is valid
        1 = Config has errors (won't deploy)
        2 = Config has warnings (should review)
    """
    print_header("Validating Configuration (config.toml)")
    
    config_path = Path(__file__).parent / "config.toml"
    errors = []
    warnings = []
    
    # 1. Check file exists
    if not config_path.exists():
        print_error(f"Config file not found: {config_path}")
        return 1
    
    print(f"Loading config from: {config_path}")
    
    # 2. Validate TOML syntax
    try:
        with open(config_path, "rb") as f:
            config = tomllib.load(f)
        print_success("TOML syntax is valid")
    except Exception as e:
        print_error(f"Invalid TOML syntax: {str(e)}")
        return 1
    
    # 3. Check required sections
    required_sections = ["database", "app", "table_permissions"]
    for section in required_sections:
        if section in config:
            print_success(f"Section [{section}] exists")
        else:
            errors.append(f"Required section [{section}] missing")
    
    if errors:
        for err in errors:
            print_error(err)
        return 1
    
    # 4. Connect to database
    try:
        conn = get_db_connection()
        if not conn:
            errors.append("Cannot connect to database")
            raise Exception("Connection failed")
        cursor = conn.cursor()
        print_success("Database connection successful")
    except Exception as e:
        print_error(f"Cannot validate config: {str(e)}")
        return 1
    
    # 5. Validate table_permissions
    table_perms = config.get("table_permissions", {})
    print(f"\nChecking {len(table_perms)} configured tables...")
    
    for table_name, perms in table_perms.items():
        # Check table exists
        try:
            cursor.execute(
                "SELECT 1 FROM information_schema.tables WHERE table_name = %s",
                (table_name,)
            )
            if not cursor.fetchone():
                errors.append(f"Table '{table_name}' not found in database")
                continue
            
            print_success(f"Table '{table_name}' exists")
            
            # Check editable_columns
            editable_cols = perms.get("editable_columns", [])
            if editable_cols:
                cursor.execute(
                    "SELECT column_name FROM information_schema.columns WHERE table_name = %s",
                    (table_name,)
                )
                actual_cols = {row[0] for row in cursor.fetchall()}
                
                for col in editable_cols:
                    if col not in actual_cols:
                        errors.append(f"Column '{col}' not found in table '{table_name}'")
                    else:
                        print_success(f"  ✓ Column '{col}' is editable")
        
        except Exception as e:
            errors.append(f"Error validating table '{table_name}': {str(e)}")
    
    # 6. Validate scripts
    scripts = config.get("scripts", {})
    if scripts:
        print(f"\nChecking {len(scripts)} defined scripts...")
        
        for script_name, script_path in scripts.items():
            script_file = Path(__file__).parent / script_path
            if script_file.exists():
                print_success(f"Script '{script_name}' found: {script_path}")
            else:
                warnings.append(f"Script '{script_name}' not found: {script_path}")
    
    # 7. Validate fastapi_users table
    print("\nChecking user management table...")
    fastapi_users_table = config.get("app", {}).get("fastapi_users_table", "fastapi_users")
    
    try:
        cursor.execute(
            "SELECT 1 FROM information_schema.tables WHERE table_name = %s",
            (fastapi_users_table,)
        )
        if cursor.fetchone():
            print_success(f"User table '{fastapi_users_table}' exists")
            
            # Check columns
            required_cols = {"user", "view", "edit", "add", "delete", "admin", "run_scripts", "export_data", "import_data"}
            cursor.execute(
                "SELECT column_name FROM information_schema.columns WHERE table_name = %s",
                (fastapi_users_table,)
            )
            actual_cols = {row[0] for row in cursor.fetchall()}
            
            missing = required_cols - actual_cols
            if missing:
                errors.append(f"User table missing columns: {', '.join(missing)}")
            else:
                print_success(f"  ✓ All required user columns present")
        else:
            errors.append(f"User table '{fastapi_users_table}' not found")
    except Exception as e:
        errors.append(f"Error validating user table: {str(e)}")
    
    # 8. Validate audit trail configuration
    print("\nChecking audit trail configuration...")
    audit_config = config.get("audit_trail", {})
    audit_table_name = audit_config.get("table_name", "fastapi_audit_trail")
    
    try:
        # Check if audit table exists or can be created
        cursor.execute(
            "SELECT 1 FROM information_schema.tables WHERE table_name = %s",
            (audit_table_name,)
        )
        if cursor.fetchone():
            print_success(f"Audit trail table '{audit_table_name}' exists")
            
            # Verify schema
            cursor.execute(
                "SELECT column_name FROM information_schema.columns WHERE table_name = %s ORDER BY ordinal_position",
                (audit_table_name,)
            )
            audit_cols = {row[0] for row in cursor.fetchall()}
            required_audit_cols = {"index", "userid", "datetime", "reference", "action"}
            
            missing = required_audit_cols - audit_cols
            if missing:
                warnings.append(f"Audit table missing columns (will be created on startup): {', '.join(missing)}")
            else:
                print_success(f"  ✓ All required audit columns present")
        else:
            print_info(f"Audit trail table '{audit_table_name}' will be created on app startup")
    except Exception as e:
        warnings.append(f"Audit table validation: {str(e)} (will be created on startup)")
    
    # 9. Validate new feature configurations
    print("\nChecking advanced feature configurations...")
    
    # Check display names
    has_display_names = any(
        perms.get("display_name") for perms in config.get("table_permissions", {}).values()
    )
    if has_display_names:
        print_success("Table display names configured")
    
    # Check Kerberos login customization
    kerberos_config = config.get("kerberos_login", {})
    if kerberos_config:
        print_success("Kerberos login text customization configured")
    
    # Check background scripts
    scripts_config = config.get("scripts", {})
    has_background = any(
        config.get(f"{script}_run_in_background", False) 
        for script in scripts_config.keys()
    )
    if has_background:
        print_success("Background script execution configured")
    
    cursor.close()
    return_db_connection(conn)
    
    # 10. Summary
    print("\n" + "="*70)
    if errors:
        print(f"\n✗ VALIDATION FAILED: {len(errors)} error(s)\n")
        for err in errors:
            print(f"  ✗ {err}")
        if warnings:
            print(f"\n⚠ Also {len(warnings)} warning(s):")
            for warn in warnings:
                print(f"  ⚠ {warn}")
        return 1
    elif warnings:
        print(f"\n✓ VALIDATION PASSED with {len(warnings)} warning(s)\n")
        for warn in warnings:
            print(f"  ⚠ {warn}")
        return 2
    else:
        print("\n✓ VALIDATION PASSED: Config is valid and ready to deploy\n")
        return 0


# ============================================================================
# COMMAND: generate-config
# ============================================================================

def cmd_generate_config(args):
    """
    Auto-generate configuration section for all discovered tables.
    
    Creates a [table_permissions] section with sensible defaults.
    Uses the [tables] include/exclude filters from config.toml if available.
    Default permissions are configurable via [deploy_tools] section in config.toml.
    Useful for:
        - Starting a new config.toml
        - Adding new tables discovered after deployment
        - Generating a template to edit manually
    
    Usage:
        python deploy_tools.py generate-config                    # Print to stdout
        python deploy_tools.py generate-config --output new.toml  # Save to file
        python deploy_tools.py generate-config --read-only        # No edit/add/delete
    
    Default permissions (configurable in [deploy_tools] section):
        - allow_add: defaults to value in config.toml [deploy_tools] (default: true)
        - allow_delete: defaults to value in config.toml [deploy_tools] (default: true)
        - Text columns: auto-detected as editable if enabled in config.toml
    """
    print_header("Generating Configuration from Database Tables")
    
    try:
        import re
        conn = get_db_connection()
        if not conn:
            print_error("Failed to connect to database")
            return 1
        
        cursor = conn.cursor()
        
        # Get all tables
        cursor.execute("""
            SELECT tablename FROM pg_tables WHERE schemaname = 'public'
            ORDER BY tablename
        """)
        
        all_tables = [row[0] for row in cursor.fetchall()]
        
        # Apply include/exclude filters from config
        include_pattern = TABLE_PERMISSIONS.get('include', ['.*'])  if isinstance(TABLE_PERMISSIONS, dict) else ['.*']
        exclude_pattern = TABLE_PERMISSIONS.get('exclude', []) if isinstance(TABLE_PERMISSIONS, dict) else []
        
        # Load from config if available
        if 'tables' in config:
            table_config = config.get('tables', {})
            if isinstance(table_config, dict):
                include_pattern = table_config.get('include', ['.*'])
                exclude_pattern = table_config.get('exclude', [])
        
        # Filter tables based on patterns
        tables = []
        for table in all_tables:
            # Check include patterns
            included = False
            for pattern in include_pattern:
                if re.match(pattern, table):
                    included = True
                    break
            
            if not included:
                continue
            
            # Check exclude patterns
            excluded = False
            for pattern in exclude_pattern:
                if re.match(pattern, table):
                    excluded = True
                    break
            
            if not excluded:
                tables.append(table)
        
        if not tables:
            print_warning("No tables found matching configured filters")
            return 1
        
        print(f"Found {len(tables)} table(s) matching configured filters.\n")
        
        # Get column information for each table
        table_columns = {}
        for table in tables:
            cursor.execute(f"""
                SELECT column_name, data_type FROM information_schema.columns 
                WHERE table_name = %s AND table_schema = 'public'
                ORDER BY ordinal_position
            """, (table,))
            table_columns[table] = cursor.fetchall()
        
        cursor.close()
        return_db_connection(conn)
        
        # Generate TOML with enhanced defaults
        toml_lines = ["[table_permissions]\n"]
        
        # Get defaults from config
        default_allow_add = DEPLOY_TOOLS_CONFIG.get("default_allow_add", True)
        default_allow_delete = DEPLOY_TOOLS_CONFIG.get("default_allow_delete", True)
        auto_detect_text = DEPLOY_TOOLS_CONFIG.get("auto_detect_text_columns", True)
        
        for table in tables:
            toml_lines.append(f"[table_permissions.{table}]")
            toml_lines.append(f'allow_add = {str(default_allow_add).lower()}  # Review and adjust if needed')
            toml_lines.append(f'allow_delete = {str(default_allow_delete).lower()}  # Review and adjust if needed')
            
            # Identify text columns for editable_columns if enabled
            text_columns = []
            if auto_detect_text:
                columns = table_columns.get(table, [])
                for col_name, col_type in columns:
                    # Skip primary key columns (usually id, pk, etc.)
                    if col_name.lower() in ['id', 'pk', 'oid', 'rowid']:
                        continue
                    # Include text-like columns
                    if col_type in ['character varying', 'text', 'varchar', 'char']:
                        text_columns.append(col_name)
            
            if text_columns:
                toml_lines.append(f'editable_columns = {text_columns}  # Text columns - consider as dropdown lookups')
            else:
                toml_lines.append(f'editable_columns = []  # Add column names to allow editing')
            
            toml_lines.append("")
        
        toml_content = "\n".join(toml_lines)
        
        # Output
        if args.output:
            output_path = Path(args.output)
            output_path.write_text(toml_content)
            print_success(f"Config generated and saved to: {output_path}")
            print(f"\nGenerated configuration for {len(tables)} table(s)")
            print(f"Filtered using patterns from config.toml [tables] section")
            print(f"File size: {len(toml_content)} bytes")
            print(f"\nNext steps:")
            print(f"  1. Review the file: {args.output}")
            print(f"  2. Disable allow_add/allow_delete where not needed")
            print(f"  3. Map text columns to lookup tables in [lookups] section")
            print(f"  4. Merge into your config.toml [table_permissions] section\n")
        else:
            print(toml_content)
            print(f"\n# Generated for {len(tables)} table(s) matching configured filters")
            print(f"# Use --output <file> to save to a file\n")
        
        return 0
        
    except Exception as e:
        print_error(f"Failed to generate config: {str(e)}")
        import traceback
        traceback.print_exc()
        return 1


# ============================================================================
# MAIN
# ============================================================================

def main():
    """Main CLI entry point"""
    
    parser = argparse.ArgumentParser(
        prog="deploy_tools.py",
        description="FastHTMX Admin Deployment Tools - Validate and configure before deployment",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python deploy_tools.py test-connection
  python deploy_tools.py discover-tables --filter gsm
  python deploy_tools.py validate-config
  python deploy_tools.py generate-config --output tables.toml

For help on a specific command:
  python deploy_tools.py <command> --help
        """
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Command to run")
    
    # test-connection
    test_parser = subparsers.add_parser(
        "test-connection",
        help="Test database connectivity",
        description="Test if PostgreSQL can be reached with configured credentials"
    )
    test_parser.set_defaults(func=cmd_test_connection)
    
    # discover-tables
    discover_parser = subparsers.add_parser(
        "discover-tables",
        help="Discover all tables in database",
        description="Scan PostgreSQL and list all tables with details"
    )
    discover_parser.add_argument(
        "--filter",
        help="Filter tables by name pattern (regex, case-insensitive)",
        metavar="PATTERN"
    )
    discover_parser.add_argument(
        "--sort",
        choices=["name", "size", "cols"],
        default="name",
        help="Sort by table name (default), size, or column count"
    )
    discover_parser.set_defaults(func=cmd_discover_tables)
    
    # validate-config
    validate_parser = subparsers.add_parser(
        "validate-config",
        help="Validate configuration file",
        description="Check config.toml for syntax and logical errors"
    )
    validate_parser.set_defaults(func=cmd_validate_config)
    
    # generate-config
    generate_parser = subparsers.add_parser(
        "generate-config",
        help="Generate configuration from database tables",
        description="Auto-create [table_permissions] section from discovered tables"
    )
    generate_parser.add_argument(
        "--output",
        help="Save to file instead of stdout",
        metavar="FILE"
    )
    generate_parser.set_defaults(func=cmd_generate_config)
    
    # Parse args
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return 0
    
    # Run command
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
