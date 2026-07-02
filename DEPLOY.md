# Deployment Guide for FastHTMX Admin

## Overview

FastHTMX Admin includes deployment tools to make it easier to validate configurations, test database connections, and discover tables before deploying to production.

**Location:** `deploy_tools.py`

---

## Quick Start

### 1. Test Database Connection
Verify that PostgreSQL is reachable with your configured credentials:

```bash
python deploy_tools.py test-connection
```

**Output example:**
```
======================================================================
  Testing Database Connection
======================================================================

Attempting to connect to PostgreSQL...
  Host: postgres.local
  Port: 5432
  Database: vanclan
  User: user1

✓ Connected successfully in 0.15s

  Database Version: PostgreSQL 14.5 on x86_64-pc-linux-gnu, compiled by ...
```

**Exit codes:**
- `0` = Connection successful, ready to deploy
- `1` = Connection failed, fix credentials or network before deploying

---

### 2. Discover Database Tables
Scan your PostgreSQL instance and list all available tables:

```bash
# List all tables
python deploy_tools.py discover-tables

# Filter tables by name pattern (regex)
python deploy_tools.py discover-tables --filter i07_

# Sort by size or column count
python deploy_tools.py discover-tables --sort size
python deploy_tools.py discover-tables --sort cols
```

**Output example:**
```
======================================================================
  Discovering Tables in PostgreSQL
======================================================================

Found 2 tables in public schema:

Table Name                               Columns    Size           
---------------------------------------- ---------- ---------------
i07_concession_hours                     3          8192 bytes     
i07_gsm_wsl_lookup                       7          16 kB          

Total: 2 table(s)

Tip: Use --filter <pattern> to narrow results (e.g., --filter 'i07_')
     Use --sort size|cols to sort by size or column count
```

**Exit codes:**
- `0` = Tables found and displayed
- `1` = Error (DB connection failed or no tables found)

---

### 3. Validate Configuration
Check your `config.toml` for syntax errors and logical issues:

```bash
python deploy_tools.py validate-config
```

**Validation checks:**
- ✓ TOML syntax is valid
- ✓ Required sections exist: `[database]`, `[app]`, `[table_permissions]`
- ✓ All referenced tables exist in database
- ✓ All `editable_columns` exist in their respective tables
- ✓ All scripts defined in `[scripts]` are accessible on disk
- ✓ `fastapi_users` table exists with correct schema
- ✓ User table has all required columns: `user`, `view`, `edit`, `add`, `delete`, `admin`, `run_scripts`, `export_data`, `import_data`
- ✓ Audit trail table configuration is valid (will be created on app startup if configured)
- ✓ Log file paths and patterns are valid (if configured)

**Output example:**
```
======================================================================
  Validating Configuration (config.toml)
======================================================================

Loading config from: /home/jattie/fasthtmx-admin/config.toml
✓ TOML syntax is valid
✓ Section [database] exists
✓ Section [app] exists
✓ Section [table_permissions] exists
✓ Database connection successful

Checking 2 configured tables...
✓ Table 'i07_concession_hours' exists
✓   ✓ Column 'bu_code' is editable
✓ Table 'i07_gsm_wsl_lookup' exists

Checking 1 defined scripts...
✓ Script 'samplescript_1' found: ../samplescripts/run.sh

Checking user management table...
✓ User table 'fastapi_users' exists
✓   ✓ All required user columns present

======================================================================

✓ VALIDATION PASSED: Config is valid and ready to deploy
```

**Exit codes:**
- `0` = Config is valid, safe to deploy
- `1` = Config has **errors** (must fix before deploying)
- `2` = Config is valid but has **warnings** (review before deploying)

---

### 4. Generate Configuration from Database
Auto-create a `[table_permissions]` section by scanning your database tables:

```bash
# Print to stdout (review first)
python deploy_tools.py generate-config

# Save to file
python deploy_tools.py generate-config --output config.new.toml
```

**Use cases:**
- Starting a new `config.toml` from scratch
- Adding newly discovered tables to existing config
- Generating a template to review and edit manually

**Output example:**
```
======================================================================
  Generating Configuration from Database Tables
======================================================================

Found 2 tables. Generating config...

[table_permissions]

[table_permissions.i07_concession_hours]
allow_add = false  # Review and enable if needed
allow_delete = false  # Review and enable if needed
editable_columns = []  # Add column names to allow editing

[table_permissions.i07_gsm_wsl_lookup]
allow_add = false  # Review and enable if needed
allow_delete = false  # Review and enable if needed
editable_columns = []  # Add column names to allow editing

# Generated for 2 table(s)
# Use --output <file> to save to a file
```

Then review and merge into your actual `config.toml`.

**Exit codes:**
- `0` = Config generated successfully
- `1` = Error (DB connection failed or no tables found)

---

## Typical Deployment Workflow

### Before First Deployment

```bash
# 1. Test database connectivity
python deploy_tools.py test-connection

# 2. Discover what tables exist
python deploy_tools.py discover-tables

# 3. Generate initial configuration from discovered tables
python deploy_tools.py generate-config --output config.new.toml

# 4. Review and edit config.new.toml:
#    - Enable allow_add/allow_delete where appropriate
#    - Add editable_columns for tables that support editing
#    - Configure script paths
#    - Set dashboard display_description

# 5. Replace config.toml with your reviewed config
cp config.new.toml config.toml

# 6. Validate final config
python deploy_tools.py validate-config

# 7. If validation passes, deploy application
python app.py  # or run in production
```

### Before Each Redeployment

```bash
# Quick check: Is everything still valid?
python deploy_tools.py validate-config

# If exit code is 0, safe to deploy
# If exit code is 2, review warnings
# If exit code is 1, fix errors before deploying
```

### After Schema Changes

```bash
# Tables added/removed? Discover them
python deploy_tools.py discover-tables

# Generate new config section
python deploy_tools.py generate-config --output new_tables.toml

# Merge new_tables.toml into config.toml

# Validate
python deploy_tools.py validate-config
```

---

## Command Reference

### `test-connection`
Test PostgreSQL connectivity with configured credentials.

**Options:** None

**Exit codes:**
- `0` = Success
- `1` = Connection failed

---

### `discover-tables`
Scan PostgreSQL and list all tables in the public schema.

**Options:**
- `--filter PATTERN` — Filter results by table name (regex, case-insensitive)
  - Example: `--filter i07_` matches tables like `i07_concession_hours`, `i07_gsm_wsl_lookup`
  
- `--sort {name|size|cols}` — Sort results (default: `name`)
  - `name` — Alphabetical by table name
  - `size` — Largest tables first
  - `cols` — Most columns first

**Exit codes:**
- `0` = Tables found
- `1` = Error or no tables found

---

### `validate-config`
Validate `config.toml` for syntax and logical errors.

**Options:** None

**Validation checks:**
1. TOML syntax is valid
2. Required sections exist
3. Database connectivity
4. All referenced tables exist in DB
5. All editable_columns exist in their tables
6. All scripts are accessible on disk
7. User management table (fastapi_users) exists and has correct schema

**Exit codes:**
- `0` = Valid, ready to deploy
- `1` = Errors found (fix before deploying)
- `2` = Valid but warnings found (review before deploying)

---

### `generate-config`
Auto-generate `[table_permissions]` section from discovered tables.

**Options:**
- `--output FILE` — Save to file instead of printing to stdout
  - Omit to print to stdout (for preview)
  - Specify to save: `--output config.new.toml`

**Generates:**
- `allow_add = false` (review and enable if needed)
- `allow_delete = false` (review and enable if needed)
- `editable_columns = []` (add column names to enable editing)

**Exit codes:**
- `0` = Config generated
- `1` = Error (DB connection failed)

---

## Help

Get help for any command:

```bash
python deploy_tools.py --help              # General help
python deploy_tools.py test-connection --help
python deploy_tools.py discover-tables --help
python deploy_tools.py validate-config --help
python deploy_tools.py generate-config --help
```

---

## New Features & Configuration

### 1. Audit Trail Setup

**What it does**: Automatically logs all INSERT, UPDATE, DELETE operations on managed tables.

**Configuration (in config.toml)**:
```toml
[audit_trail]
table_name = "fastapi_audit_trail"  # Optional; uses this name for the audit table
```

**Deployment considerations**:
- Audit table is automatically created on app startup if it doesn't exist
- Runs `CREATE TABLE IF NOT EXISTS`, so safe to deploy on existing databases
- Audit trail reference format: `table_name:id=primary_key_value` (e.g., `i07_concession_hours:id=42`)
- No configuration needed; just ensure audit trail section exists in config.toml

**Verification**:
- After app starts, verify audit table: `SELECT * FROM fastapi_audit_trail;`
- Query audited operations: `SELECT * FROM fastapi_audit_trail WHERE action='UPDATE';`

### 2. Custom Table Display Names

**What it does**: Shows friendly names for tables in the Edit Tables dropdown instead of table names.

**Configuration (in config.toml)**:
```toml
[table_permissions.i07_concession_hours]
display_name = "Concession Hours"  # Optional; defaults to table name if omitted
allow_add = true
allow_delete = true
editable_columns = ["concession_hours"]
```

**Deployment notes**:
- Backward compatible; tables without display_name show table name
- Set via `[table_permissions.TABLE_NAME]` sections
- Each table's display name is independent

### 3. Customizable Kerberos Login Text

**What it does**: Allows customization of login page header and input placeholders.

**Configuration (in config.toml)**:
```toml
[kerberos_login]
header_text = "Company Portal Login"
username_placeholder = "Domain Username"
password_placeholder = "Kerberos Password"
```

**Deployment notes**:
- All fields are optional; falls back to defaults if not set
- Defaults: "Kerberos Login", "Username", "Password"
- Changes take effect immediately on app reload

### 4. User Deletion (Admin Only)

**What it does**: Allows admins to delete users from the Admin Panel.

**Security**:
- Only users with admin=true can delete users
- Non-admins cannot access DELETE endpoint
- Deletes user from `fastapi_users` table and revokes all permissions

**Deployment notes**:
- No configuration needed
- Automatic protection based on admin flag in user record
- Endpoint: `DELETE /api/admin/users/{username}`

### 5. Background Script Execution

**What it does**: Execute long-running scripts asynchronously with real-time status updates.

**Configuration (in config.toml)**):
```toml
[scripts]
my_script = "/path/to/script.sh"
my_script_run_in_background = true  # Optional; enable async execution
```

**Deployment notes**:
- Scripts without `_run_in_background = true` run synchronously (old behavior)
- Job tracking is in-memory; jobs lost on app restart
- Old jobs (>1 hour) are auto-cleaned up
- Polling interval: 2 seconds (hardcoded, customizable in frontend)

**User experience**:
- Toast notification on script start
- Sidebar shows running script count
- Results page polls for status updates
- Toast on completion

---

## Troubleshooting

### "Connection failed" on test-connection

**Check these in order:**
1. Is PostgreSQL running on the target host?
   ```bash
   ping postgres.local
   ```

2. Are credentials correct in `config.toml` [database] section?
   - Host
   - Port
   - Database name
   - Username
   - Password (if using authentication)

3. Does the database exist?
   ```bash
   # From a PostgreSQL client:
   \l  # List databases
   ```

4. Does the user have access?
   ```bash
   # From a PostgreSQL admin:
   GRANT CONNECT ON DATABASE vanclan TO username;
   ```

### "No tables found" on discover-tables

**Possible causes:**
- Database exists but has no tables (create some first)
- Tables exist but in a different schema (not `public`)
- User lacks SELECT permission on tables

### validate-config shows "Table not found"

**Possible causes:**
1. Table name is misspelled in `config.toml`
2. Table was deleted from database
3. Table exists in a different schema (FastHTMX Admin only sees `public` schema)

**Fix:**
- Update `config.toml` with correct table name, OR
- Create the table in PostgreSQL, OR
- Run `discover-tables` to see what actually exists

### validate-config shows "Column not found"

**Possible cause:**
- Column name in `editable_columns` is misspelled or doesn't exist

**Fix:**
- Run `discover-tables` to find correct column names
- Update `config.toml` with correct column name

### Scripts "not found"

**Possible causes:**
1. Script path in `config.toml` is wrong
2. Script file doesn't exist
3. Script path is relative but incorrect (relative to deploy_tools.py location)

**Fix:**
- Verify script exists: `ls -la ../samplescripts/run.sh`
- Update `config.toml` with correct relative or absolute path

---

## Examples

### Scenario: Setting up new deployment

```bash
# 1. Test connection
$ python deploy_tools.py test-connection
✓ Connected successfully

# 2. Discover tables
$ python deploy_tools.py discover-tables
Found 5 tables in public schema:
  table1
  table2
  table3
  table4
  table5

# 3. Generate config
$ python deploy_tools.py generate-config --output config.new.toml
✓ Config generated and saved to: config.new.toml

# 4. Edit config.new.toml in your editor
# - Enable allow_add for table1
# - Enable allow_delete for table2
# - Add editable_columns for table3

# 5. Validate
$ cp config.new.toml config.toml
$ python deploy_tools.py validate-config
✓ VALIDATION PASSED: Config is valid and ready to deploy

# 6. Deploy
$ python app.py
```

### Scenario: Filter to specific table prefix

```bash
$ python deploy_tools.py discover-tables --filter gsm
Found 3 tables matching 'gsm':
  gsm_config
  gsm_lookup
  gsm_permissions
```

### Scenario: Check before redeployment

```bash
$ python deploy_tools.py validate-config

# Output:
✓ TOML syntax is valid
✓ Section [database] exists
... (all checks pass)
✓ VALIDATION PASSED: Config is valid and ready to deploy

echo "Ready to deploy!"
```

---

## Integration with CI/CD

These tools can be integrated into deployment pipelines:

```bash
#!/bin/bash
# Pre-deploy validation script

set -e  # Exit on any error

echo "Running pre-deployment checks..."

python deploy_tools.py test-connection || { echo "DB connection failed"; exit 1; }
python deploy_tools.py validate-config || { echo "Config validation failed"; exit 1; }

echo "All checks passed! Ready to deploy."
```

---

## Support

For issues or questions:
1. Check the [Troubleshooting](#troubleshooting) section above
2. Review your `config.toml` file
3. Run `python deploy_tools.py <command> --help` for command details
4. Check PostgreSQL logs: `SELECT * FROM pg_stat_activity;`

