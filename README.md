# FastAPI HTMX Kerberos Application

A basic FastAPI + HTMX application with Kerberos authentication and PostgreSQL integration.

## Features

- **Kerberos Authentication**: Login using kinit with username/password validation
- **Dynamic Sidebar**: Navigation with edit menu for database tables
- **PostgreSQL Integration**: Connect to and view/edit PostgreSQL tables
- **HTMX**: Dynamic page updates without full page reloads
- **Shell Script Execution**: Run predefined shell scripts from the dashboard with live output

## Setup

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Ensure PostgreSQL is Accessible

The application expects:
- Host: `postgres.local`
- Database: `v*****`
- Table: `tes`
- Username: `v*****`
- Password: `*****`

Make sure your PostgreSQL server is running and accessible at these credentials.

### 3. Run the Application

```bash
python app.py
```

The application will start at `http://localhost:8000`

## Usage

### Login

1. Visit `http://localhost:8000`
2. Enter Kerberos username and password
3. The app validates credentials using `kinit`
4. On successful auth, you'll be redirected to the dashboard

### Demo Credentials

- Username: `j*****`
- Password: `*****`

These are Kerberos principals that were created during setup.

### Dashboard Navigation

- **Dashboard**: Home page
- **Edit Tables → View TES Table**: Browse and edit PostgreSQL records
- **Run Scripts**: Execute predefined shell scripts and view results
- **Logout**: Clear session and return to login

## Architecture

- **app.py**: FastAPI application with routes and Kerberos auth logic
- **templates/base.html**: Base template with sidebar and styling
- **templates/login.html**: Login form
- **templates/dashboard.html**: Dashboard with sidebar
- **templates/table.html**: Table data display
- **templates/script_results.html**: Shell script execution results page
- **config.toml**: Configuration for database, lookups, and scripts

## Kerberos Integration

The app uses `kinit` via subprocess to validate credentials:

```python
def kerberos_auth(username: str, password: str) -> bool:
    # Runs: kinit username@FASTHTMX.LOCAL
    # Returns: True if successful, False if failed
```

## Shell Script Execution

### Configuration

Define scripts in `config.toml` under the `[scripts]` section:

```toml
[scripts]
samplescript_1 = "../samplescripts/run.sh"
my_backup_script = "../scripts/backup.sh"
cleanup = "/opt/admin/cleanup.sh"
```

### Usage

1. Navigate to the dashboard
2. Select a script from the **Run Scripts** dropdown menu
3. Click **Execute Script**
4. Wait for the results page to load
5. View:
   - Script name and status
   - Return code (0 = success)
   - Execution time in seconds
   - Full stdout output
   - stderr if any errors occurred

### Features

- **Timeout Protection**: Scripts that exceed 5 minutes will timeout automatically
- **UI Lock**: All navigation is disabled while a script runs to prevent result loss
- **Live Results**: Full output displayed on a dedicated results page
- **Return Code Tracking**: Exit code shown for script status validation

## Notes

- Sessions are stored in memory (use Redis for production)
- Database connection errors are logged but won't crash the app
- HTMX is used for dynamic content loading via `/table` endpoint
