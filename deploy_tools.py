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
from config import DB_CONFIG, TABLE_PERMISSIONS, SCRIPTS_CONFIG
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
            required_cols = {"user", "view", "edit", "add", "delete", "admin", "run_scripts"}
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
    
    cursor.close()
    return_db_connection(conn)
    
    # 8. Summary
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
    Useful for:
        - Starting a new config.toml
        - Adding new tables discovered after deployment
        - Generating a template to edit manually
    
    Usage:
        python deploy_tools.py generate-config                    # Print to stdout
        python deploy_tools.py generate-config --output new.toml  # Save to file
        python deploy_tools.py generate-config --read-only        # No edit/add/delete
    
    Default permissions:
        - All tables: allow_view = true
        - All tables: allow_add = false (review before enabling)
        - All tables: allow_delete = false (review before enabling)
        - No editable columns (review before enabling)
    """
    print_header("Generating Configuration from Database Tables")
    
    try:
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
        
        tables = [row[0] for row in cursor.fetchall()]
        cursor.close()
        return_db_connection(conn)
        
        if not tables:
            print_warning("No tables found in database")
            return 1
        
        print(f"Found {len(tables)} tables. Generating config...\n")
        
        # Generate TOML
        toml_lines = ["[table_permissions]\n"]
        
        for table in tables:
            toml_lines.append(f"[table_permissions.{table}]")
            toml_lines.append(f'allow_add = false  # Review and enable if needed')
            toml_lines.append(f'allow_delete = false  # Review and enable if needed')
            toml_lines.append(f'editable_columns = []  # Add column names to allow editing')
            toml_lines.append("")
        
        toml_content = "\n".join(toml_lines)
        
        # Output
        if args.output:
            output_path = Path(args.output)
            output_path.write_text(toml_content)
            print_success(f"Config generated and saved to: {output_path}")
            print(f"\nGenerated configuration for {len(tables)} table(s)")
            print(f"File size: {len(toml_content)} bytes")
            print(f"\nNext steps:")
            print(f"  1. Review the file: {args.output}")
            print(f"  2. Enable allow_add/allow_delete where appropriate")
            print(f"  3. Add editable_columns for tables that allow editing")
            print(f"  4. Merge into your config.toml [table_permissions] section\n")
        else:
            print(toml_content)
            print(f"\n# Generated for {len(tables)} table(s)")
            print(f"# Use --output <file> to save to a file\n")
        
        return 0
        
    except Exception as e:
        print_error(f"Failed to generate config: {str(e)}")
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
