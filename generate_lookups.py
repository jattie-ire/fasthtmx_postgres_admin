#!/usr/bin/env python3
"""
Generate lookup entries for a table by scanning for TEXT columns.
Usage: python generate_lookups.py [table_name]
  python generate_lookups.py i07_gsm_wsl_lookup  # Generate for specific table
  python generate_lookups.py                     # Generate for all tables
"""

import sys
import tomllib
from pathlib import Path
from database import get_db_connection, get_table_columns, get_column_types, get_available_tables

def get_text_columns(table_name):
    """Get all TEXT columns from a table"""
    col_types = get_column_types(table_name)
    return [col for col, col_type in col_types.items() if col_type == 'text']

def generate_lookups_for_table(table_name):
    """Generate lookup entries for a table and update config.toml"""
    # Get TEXT columns
    text_cols = get_text_columns(table_name)
    if not text_cols:
        print(f"  No TEXT columns found in {table_name}")
        return False
    
    # Read current config
    config_path = Path(__file__).parent / "config.toml"
    with open(config_path, 'rb') as f:
        config = tomllib.load(f)
    
    # Ensure [lookups] section exists
    if 'lookups' not in config:
        config['lookups'] = {}
    
    # Check if table already has entries
    if table_name in config['lookups']:
        existing = config['lookups'][table_name]
        print(f"  {table_name} already has lookups: {existing}")
        new_cols = [col for col in text_cols if col not in existing]
        if not new_cols:
            print(f"  All TEXT columns already in config")
            return False
        print(f"  Adding new columns: {new_cols}")
        config['lookups'][table_name].extend(new_cols)
    else:
        print(f"  Creating lookup entries for {table_name}: {text_cols}")
        config['lookups'][table_name] = text_cols
    
    # Write back to config.toml - manually format to preserve readability
    with open(config_path, 'w') as f:
        # Write sections in order
        for section in ['database', 'tables', 'dashboard', 'lookups']:
            if section in config:
                f.write(f"[{section}]\n")
                section_data = config[section]
                
                if section == 'lookups':
                    # Format lookups as table = ["col1", "col2", ...]
                    for table, cols in sorted(section_data.items()):
                        cols_str = ', '.join(f'"{col}"' for col in cols)
                        f.write(f"{table} = [{cols_str}]\n")
                else:
                    # Write other sections as-is
                    for key, value in section_data.items():
                        if isinstance(value, list):
                            if all(isinstance(v, str) for v in value):
                                # String array
                                items = ', '.join(f'"{v}"' for v in value)
                                f.write(f'{key} = [{items}]\n')
                            else:
                                f.write(f'{key} = {value}\n')
                        elif isinstance(value, str):
                            f.write(f'{key} = "{value}"\n')
                        else:
                            f.write(f'{key} = {value}\n')
                f.write('\n')
    
    print(f"✓ Updated config.toml")
    return True

def main():
    if len(sys.argv) > 1:
        # Specific table
        table_name = sys.argv[1]
        print(f"\nGenerating lookups for {table_name}...")
        try:
            generate_lookups_for_table(table_name)
        except Exception as e:
            print(f"✗ Error: {e}")
            import traceback
            traceback.print_exc()
    else:
        # All tables matching include pattern
        from config import config
        tables = get_available_tables()
        print(f"\nScanning {len(tables)} tables for TEXT columns...")
        for table in tables:
            print(f"\n{table}:")
            try:
                generate_lookups_for_table(table)
            except Exception as e:
                print(f"  ✗ Error: {e}")

if __name__ == "__main__":
    main()
