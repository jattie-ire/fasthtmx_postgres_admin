"""Database operations"""
import psycopg2
from psycopg2.extras import RealDictCursor
import re
from config import DB_CONFIG, config


def get_db_connection():
    """Get PostgreSQL connection"""
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        return conn
    except Exception as e:
        print(f"DB CONNECTION ERROR: {e}")
        import traceback
        traceback.print_exc()
        return None


def filter_tables(tables: list) -> list:
    """Filter tables based on include/exclude patterns from config"""
    include_patterns = config.get("tables", {}).get("include", [])
    exclude_patterns = config.get("tables", {}).get("exclude", [])
    
    if not include_patterns:
        include_patterns = [".*"]  # Include all by default if not specified
    
    filtered = []
    
    for table in tables:
        # Check if table matches any exclude pattern
        excluded = False
        for pattern in exclude_patterns:
            if re.match(pattern, table):
                excluded = True
                break
        
        if excluded:
            continue
        
        # Check if table matches any include pattern
        included = False
        for pattern in include_patterns:
            if re.match(pattern, table):
                included = True
                break
        
        if included:
            filtered.append(table)
    
    return filtered


def get_available_tables():
    """Get list of available tables in public schema (filtered by config)"""
    conn = get_db_connection()
    if not conn:
        return []
    
    try:
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        # Use pg_tables which is more reliable for getting user tables
        cursor.execute(
            "SELECT tablename FROM pg_tables WHERE schemaname = 'public' ORDER BY tablename"
        )
        tables = [row['tablename'] for row in cursor.fetchall()]
        cursor.close()
        
        # Apply filtering from config
        filtered_tables = filter_tables(tables)
        return filtered_tables
    except Exception as e:
        print(f"ERROR fetching tables: {e}")
        import traceback
        traceback.print_exc()
        return []
    finally:
        conn.close()


def get_table_columns(table_name: str):
    """Get columns from specified table"""
    conn = get_db_connection()
    if not conn:
        print(f"ERROR: Could not connect to database for table '{table_name}'")
        return []
    
    try:
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        query = "SELECT column_name FROM information_schema.columns WHERE table_name = %s ORDER BY ordinal_position"
        print(f"DEBUG: Executing query: {query} with table_name='{table_name}'")
        cursor.execute(query, (table_name,))
        columns = [row['column_name'] for row in cursor.fetchall()]
        print(f"Columns found for table '{table_name}': {columns}")
        cursor.close()
        return columns
    except Exception as e:
        print(f"ERROR fetching columns for '{table_name}': {e}")
        import traceback
        traceback.print_exc()
        return []
    finally:
        conn.close()


def get_column_types(table_name: str):
    """Get column names and their data types"""
    conn = get_db_connection()
    if not conn:
        print("ERROR: Could not connect to database")
        return {}
    
    try:
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute(
            "SELECT column_name, data_type FROM information_schema.columns WHERE table_name = %s ORDER BY ordinal_position",
            (table_name,)
        )
        col_types = {row['column_name']: row['data_type'] for row in cursor.fetchall()}
        print(f"Column types for table '{table_name}': {col_types}")
        cursor.close()
        return col_types
    except Exception as e:
        print(f"ERROR fetching column types: {e}")
        import traceback
        traceback.print_exc()
        return {}
    finally:
        conn.close()


def get_table_data(table_name: str):
    """Get data from specified table"""
    conn = get_db_connection()
    if not conn:
        print("ERROR: Could not connect to database")
        return []
    
    try:
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        query = f"SELECT * FROM {table_name}"
        print(f"DEBUG: Executing query: {query}")
        cursor.execute(query)
        data = cursor.fetchall()
        print(f"Rows fetched from '{table_name}': {len(data)}")
        cursor.close()
        return data
    except Exception as e:
        print(f"ERROR fetching data from '{table_name}': {e}")
        import traceback
        traceback.print_exc()
        return []
    finally:
        conn.close()


# ============================================================================
# LOOKUP FUNCTIONS
# ============================================================================

def get_text_columns(table_name: str) -> list:
    """Get all TEXT columns from a table"""
    col_types = get_column_types(table_name)
    text_cols = [col for col, dtype in col_types.items() if dtype == 'text']
    return text_cols


def find_source_table(column_name: str) -> str:
    """
    Find source table for a column by naming convention.
    Examples:
    - gsm_name -> i07_gsm.gsm_name
    - wsl_name -> i07_wsl.wsl_name
    """
    available_tables = get_available_tables()
    
    # Extract base name from column (e.g., "gsm_name" -> "gsm")
    base_name = column_name.rsplit('_', 1)[0]
    
    # Look for matching table
    for table in available_tables:
        # Match i07_gsm, i07_wsl, etc.
        if base_name in table.lower() or table.lower().endswith(base_name):
            # Verify column exists in potential source table
            source_cols = get_table_columns(table)
            if column_name in source_cols:
                return f"{table}.{column_name}"
            # Also try just the base column name
            if base_name in source_cols:
                return f"{table}.{base_name}"
    
    return None


def get_lookup_options(source_table: str, column_name: str) -> list:
    """
    Fetch distinct values from a source table column for dropdown.
    Format: "table.column"
    Returns list of tuples: [(value, value), ...] for simple values
    """
    conn = get_db_connection()
    if not conn:
        return []
    
    try:
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        table, col = source_table.split('.')
        
        # Get distinct values, ordered
        query = f"SELECT DISTINCT {col} FROM {table} ORDER BY {col}"
        print(f"DEBUG: Lookup query: {query}")
        cursor.execute(query)
        results = cursor.fetchall()
        
        # Return list of values
        values = [row[col] for row in results]
        cursor.close()
        return values
    except Exception as e:
        print(f"ERROR fetching lookup options from {source_table}: {e}")
        import traceback
        traceback.print_exc()
        return []
    finally:
        conn.close()


def add_lookup_value(source_table: str, column_name: str, value: str) -> bool:
    """
    Add a new value to a lookup source table.
    Format: source_table = "table.column"
    """
    conn = get_db_connection()
    if not conn:
        return False
    
    try:
        cursor = conn.cursor()
        table, col = source_table.split('.')
        
        # Insert just the one column - others will be NULL or use defaults
        query = f"INSERT INTO {table} ({col}) VALUES (%s)"
        print(f"DEBUG: Inserting lookup value: {query} with {value}")
        cursor.execute(query, (value,))
        conn.commit()
        cursor.close()
        
        print(f"✓ Added {value} to {table}.{col}")
        return True
    except Exception as e:
        print(f"ERROR adding lookup value: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        conn.close()


def generate_lookups_for_table(table_name: str) -> dict:
    """
    Scan table for TEXT columns and return lookup entries.
    Returns: {"column1": "table.column1", "column2": "table.column2", ...}
    """
    try:
        col_types = get_column_types(table_name)
        text_cols = [col for col, col_type in col_types.items() if col_type == 'text']
        
        # Build lookups dict: col -> table.col
        lookups = {col: f"{table_name}.{col}" for col in text_cols}
        return lookups
    except Exception as e:
        print(f"ERROR generating lookups for {table_name}: {e}")
        import traceback
        traceback.print_exc()
        return {}
