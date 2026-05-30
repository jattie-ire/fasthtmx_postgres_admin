# HCF Admin - FastAPI PostgreSQL Management Interface

A FastAPI + HTMX application with Kerberos authentication for secure database and configuration management.

## Why HCF Admin?

Managing PostgreSQL databases in enterprise environments is complex. You need **secure authentication**, **granular permissions**, **audit trails**, and the ability to let teams access data without exposing database credentials or SQL knowledge. Most solutions either require expensive enterprise tools, extensive custom development, or expose your database to risky third-party platforms.

**HCF Admin solves this problem** with a lightweight, self-hosted web application that:

- **Integrates with your Kerberos infrastructure** → Authentication happens through your existing corporate directory (no new user databases)
- **Provides instant database administration** → Browse, edit, and manage PostgreSQL tables without writing SQL
- **Maintains performance at scale** → Connection pooling, caching, and pagination keep the app responsive even with millions of rows
- **Gives granular control** → Admins can restrict exactly which tables, columns, and operations each user can perform
- **Runs scripts safely** → Execute maintenance scripts with full output capture and timeout protection
- **Hot-reloads configuration** → Change permissions and settings without restarting the application
- **Ships with deployment tools** → CLI utilities validate your setup, discover tables, and auto-generate configuration

### Who Should Use This?

- **System Administrators** who need to manage PostgreSQL databases for business users
- **DevOps Teams** looking for a self-hosted alternative to commercial database tools
- **Enterprises** with Kerberos/Active Directory infrastructure and strong security requirements
- **Organizations** wanting to democratize database access while maintaining control and audit trails

### What You Get

✅ Web UI for database browsing and editing  
✅ Permission-based access control (6-level user flags + column-level restrictions)  
✅ Integrated shell script execution with live output  
✅ Configuration management with live editor and hot-reload  
✅ Dark/light theme support for comfortable use  
✅ Deployment tools (connectivity checker, table discovery, config validator, auto-config generator)  
✅ Complete documentation with Kerberos setup guides and deployment examples  
✅ Production-ready with connection pooling, pagination, and caching  

## Features

- **Kerberos Authentication**: Secure login using kinit with username/password validation
- **Dynamic Dashboard**: Real-time database table viewing and editing with HTMX
- **Pagination**: Efficient table browsing with configurable page sizes (25-500 rows)
- **Connection Pooling**: Optimized PostgreSQL performance with ThreadedConnectionPool
- **Configuration Management**: TOML-based configuration with live editing and hot-reload
- **Dark/Light Theme**: CSS variable-based theming with automatic theme switching
- **Shell Script Execution**: Run predefined scripts with full output capture and status tracking
- **User & Permission Management**: Granular access control (view, edit, add, delete, admin, run_scripts)
- **Deployment Tools**: CLI utility for database connectivity, table discovery, and config validation

## Quick Start

### Prerequisites

- Python 3.10+
- PostgreSQL 12+
- Kerberos client libraries (kinit)

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Configuration

Create or verify `config.toml` with your PostgreSQL database credentials and settings. **Note:** Use your actual database name and user—the values below are just examples:

```toml
[database]
host = "postgres.local"          # Your PostgreSQL server
port = 5432                       # PostgreSQL port
database = "your_database_name"   # Any database name
user = "your_database_user"       # Any database user
password = "your_password"        # Database user password

[table_permissions]
[table_permissions.your_table]
allow_add = true
allow_delete = true
editable_columns = ["col1", "col2"]

[scripts]
my_script = "../scripts/run.sh"
```

### 3. Start the Application

```bash
python app.py
```

The application will be available at `http://localhost:8000`

## Kerberos Setup for Development & Testing

### Overview

This application uses Kerberos (MIT Kerberos or Heimdal) for secure authentication. For development and testing, you can set up a local Kerberos realm.

### Installation

#### Ubuntu/Debian

```bash
# Install MIT Kerberos server and client libraries
sudo apt-get install krb5-admin-server krb5-kdc krb5-user libkrb5-dev
```

#### macOS

```bash
# Using Homebrew
brew install krb5
```

#### Other Systems

Refer to [MIT Kerberos documentation](https://web.mit.edu/kerberos/www/install.html) for platform-specific instructions.

### Setup Local Kerberos Realm (Development)

#### 1. Configure krb5.conf

Edit `/etc/krb5.conf` (or `~/.krb5/config` for user-level setup) and add your realm:

```ini
[libdefaults]
    default_realm = FASTHTMX.LOCAL
    kdc_timesync = 1
    ccache_type = 4
    forwardable = yes
    proxiable = yes
    
[realms]
    FASTHTMX.LOCAL = {
        kdc = localhost:88
        admin_server = localhost:749
        default_domain = fasthtmx.local
    }

[domain_realm]
    .fasthtmx.local = FASTHTMX.LOCAL
    fasthtmx.local = FASTHTMX.LOCAL
    localhost = FASTHTMX.LOCAL
```

#### 2. Initialize the Kerberos Database (Ubuntu/Debian)

```bash
# Create KDC database directory
sudo mkdir -p /var/lib/krb5kdc
sudo chown krb5:krb5 /var/lib/krb5kdc

# Initialize the database (set a strong master password)
sudo kdb5_util create -s -r FASTHTMX.LOCAL

# Start Kerberos services
sudo systemctl restart krb5-kdc krb5-admin-server
```

#### 3. Create Test Principals

```bash
# Connect to Kerberos admin
kadmin.local

# Create admin principal
addprinc -pw adminpass admin/admin

# Create test user principal
addprinc -pw testpass testuser

# Create another test principal
addprinc -pw devpass devuser

# Exit kadmin
quit
```

#### 4. Test the Setup

```bash
# Test authentication with a principal
kinit testuser
# Enter password: testpass

# Verify the ticket
klist

# Destroy the ticket when done
kdestroy
```

### Docker Setup (Alternative)

For containerized development, use a pre-built Kerberos image:

```dockerfile
FROM ubuntu:22.04

RUN apt-get update && apt-get install -y \
    krb5-admin-server krb5-kdc krb5-user libkrb5-dev \
    postgresql-client python3 python3-pip

# Copy krb5.conf and setup scripts
COPY krb5.conf /etc/krb5.conf
COPY setup-kerberos.sh /setup-kerberos.sh

RUN chmod +x /setup-kerberos.sh

ENTRYPOINT ["/setup-kerberos.sh"]
```

### Configuration for Application

Once Kerberos is set up, the application will:

1. Use `kinit` to validate user credentials at login
2. Check against your configured Kerberos realm (default: `FASTHTMX.LOCAL`)
3. Create user records in the database upon first login
4. Grant full admin permissions to the first user

No additional application configuration needed—it uses the system Kerberos setup automatically.

### Testing Authentication

#### Via Command Line

```bash
# Test with a known principal
kinit testuser

# The application will accept this principal's credentials
# when logging in via the web interface
```

#### Via Application

1. Start the app: `python app.py`
2. Visit `http://localhost:8000`
3. Enter credentials:
   - **Username**: `testuser`
   - **Password**: `testpass`
4. The app will validate via Kerberos and create a user record

### Common Kerberos Commands

```bash
# Initialize a ticket
kinit username

# List current tickets
klist

# Renew an existing ticket
kinit -R

# Destroy tickets
kdestroy

# Test Kerberos connectivity
kvno host/localhost

# Check KDC connectivity (requires admin access)
kadmin.local
```

### Troubleshooting Kerberos

#### "kinit: Cannot contact any KDC for realm FASTHTMX.LOCAL"

- Verify `/etc/krb5.conf` has correct KDC address
- Ensure KDC service is running: `sudo systemctl status krb5-kdc`
- Check firewall allows port 88/UDP (KDC) and 749/TCP (admin)

#### "kinit: Preauthentication failed"

- Verify principal exists: `kadmin.local -c /etc/krb5.conf`
- List principals: `listprincs` in kadmin
- Reset principal password: `cpw <principal>` in kadmin

#### "krb5.conf: No such file or directory"

- Install krb5-user: `sudo apt-get install krb5-user`
- Or set `KRB5CONFIG=/path/to/krb5.conf` environment variable

#### Application Says "Invalid Credentials"

- Run `kinit username` in terminal—if it fails, Kerberos is misconfigured
- Check KDC logs: `sudo tail -f /var/log/krb5kdc.log`
- Verify principal exists in KDC database
- Check system time is synchronized (important for Kerberos)

### Production Kerberos

For production deployments:

1. Use your organization's existing Kerberos infrastructure
2. Create application-specific service principal: `hcfadmin/hostname@REALM`
3. Configure krb5.conf to point to your KDC
4. Update `krb5.conf` realm to match your environment
5. Test thoroughly in staging environment before production rollout


## Usage

### Authentication

1. Visit `http://localhost:8000`
2. Enter your Kerberos username and password
3. The app validates credentials using `kinit`
4. On successful authentication, you'll be redirected to the dashboard

### Dashboard

The dashboard provides access to all application features:

- **Tables**: Browse and edit database tables with configurable pagination
- **Admin Panel** (admin-only): Configure tables, permissions, users, and settings
- **Run Scripts**: Execute predefined shell scripts and view results
- **Help**: View documentation and system information
- **Theme Toggle**: Switch between light and dark modes
- **Logout**: End your session

![HCF Admin Dashboard - Script Execution Results](images/dashboard.png)

### Tables

- **Browsing**: View paginated table data with size selections (25-500 rows)
- **Editing**: Click row values to edit (if permissions allow)
- **Sorting**: Column-based sorting
- **Search/Filter**: Quick row filtering via table search

![Table Editor - View and Edit Data with Pagination](images/table-view.png)

### Admin Panel

Accessible only to users with admin privileges:

- **Users**: Manage user accounts and permissions
- **Configuration**: Edit config.toml directly with validation
- **Table Permissions**: Control which tables are visible and editable per user
- **Scripts**: Manage available scripts
- **Lookups**: Configure reference data

![Admin Panel - Configuration Editor with Live Validation](images/admin-panel.png)

### Running Scripts

1. Navigate to **Run Scripts** from the dashboard
2. Select a script from the dropdown menu
3. Click **Execute Script**
4. Monitor execution status and view results:
   - Script name and execution timestamp
   - Return code (0 = success)
   - Execution duration
   - Full stdout and stderr output
5. Scripts timeout after 5 minutes of execution

## Architecture

### Core Modules

- **app.py**: FastAPI application with all route handlers and endpoint logic
- **auth.py**: Kerberos authentication and session management
- **database.py**: PostgreSQL operations, connection pooling, permissions, and user management
- **config.py**: Configuration loading, caching, and hot-reload functionality
- **templates.py**: Template rendering utilities

### Database Layer

- **Connection Pooling**: `psycopg2.pool.ThreadedConnectionPool` (min: 2, max: 10 connections)
- **Query Optimization**: Parameterized queries with pagination support
- **User Management**: Table-based user storage in `fastapi_users`
- **Permission Model**: Dual-level (user flags + table-level permissions)

### Frontend

- **Base Template**: `templates/base.html` - Navigation, sidebar, theme toggle, session info
- **Dashboard**: `templates/dashboard.html` - Main entry point with navigation
- **Tables**: `templates/table.html` - Paginated table display with editing
- **Scripts**: `templates/script_results.html` - Script execution results
- **Admin**: `templates/admin.html` - Configuration and user management (if admin)
- **Styling**: `static/css/style.css` - Complete CSS variable theming system

### Deployment Tools

- **deploy_tools.py**: CLI utility with 4 commands:
  - `test-connection`: Verify PostgreSQL connectivity
  - `discover-tables`: List all tables with metadata
  - `validate-config`: Check config.toml validity and database schema compatibility
  - `generate-config`: Auto-generate table permission templates
- **DEPLOY.md**: Complete deployment guide with examples and troubleshooting

## Authentication & Security

### Kerberos Integration

The application uses Kerberos via `kinit` for secure authentication:

```python
def kerberos_auth(username: str, password: str) -> bool:
    # Validates against Kerberos realm
    # Returns: True if credentials valid, False otherwise
```

### Sessions

- **Storage**: In-memory cookies with session validation
- **Security**: Kerberos-backed authentication ensures only valid principals can access
- **First User**: The first user to login receives full admin privileges
- **Subsequent Users**: New users default to view-only permissions

### Permissions System

Each user has 6 permission flags:

- `view`: Can view table data
- `edit`: Can edit existing rows
- `add`: Can insert new rows
- `delete`: Can delete rows
- `admin`: Access to admin panel and configuration
- `run_scripts`: Can execute shell scripts

Additionally, table-level permissions in `config.toml` control which columns are editable per table.

## Script Execution

### Configuration

Define executable scripts in `config.toml`:

```toml
[scripts]
backup_job = "../scripts/backup.sh"
data_sync = "../scripts/sync.sh"
cleanup = "/opt/maintenance/cleanup.sh"
```

### Execution

- **Access Control**: Only users with `run_scripts` permission can execute
- **Timeout**: Scripts timeout after 5 minutes of execution
- **UI Lock**: Navigation disabled during execution to preserve results
- **Output Capture**: Full stdout and stderr captured and displayed

### Results Display

The results page shows:

- Script name and execution timestamp
- Exit code (0 = success, non-zero = error)
- Total execution time in seconds
- Complete stdout output in code block
- Any stderr output with error styling
- Ability to return to dashboard after completion

## Deployment

## Deployment Environment

### Running in Production

The application is built with FastAPI and can be deployed in several ways. Here are the recommended approaches for different deployment scenarios.

#### 1. Using Gunicorn + Uvicorn (Recommended)

For production deployments, use Gunicorn as the application server with Uvicorn workers:

```bash
# Install Gunicorn
pip install gunicorn

# Run with Gunicorn
gunicorn -w 4 -k uvicorn.workers.UvicornWorker -b 0.0.0.0:8000 app:app
```

**Parameters explained:**
- `-w 4`: Number of worker processes (adjust based on CPU cores)
- `-k uvicorn.workers.UvicornWorker`: Use Uvicorn worker class
- `-b 0.0.0.0:8000`: Bind to all interfaces on port 8000

#### 2. Using Environment Variables

Instead of hardcoding secrets in `config.toml`, use environment variables:

```bash
# Set environment variables before running
export DATABASE_URL="postgresql://user:pass@postgres.local:5432/mydb"
export SECRET_KEY="your-secret-key-here"
export KERBEROS_REALM="YOUR.REALM"

# Run the application
python app.py
```

Then update `config.py` to read from environment:

```python
import os

DB_CONFIG = {
    "host": os.getenv("DB_HOST", "postgres.local"),
    "port": int(os.getenv("DB_PORT", 5432)),
    "database": os.getenv("DB_NAME", "mydb"),
    "user": os.getenv("DB_USER"),
    "password": os.getenv("DB_PASSWORD"),
}
```

#### 3. Reverse Proxy with Nginx

Set up Nginx as a reverse proxy in front of the application:

```nginx
upstream hcf_admin {
    server localhost:8000;
    server localhost:8001;
    server localhost:8002;
    server localhost:8003;
}

server {
    listen 80;
    server_name admin.example.com;

    # Redirect HTTP to HTTPS
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name admin.example.com;

    ssl_certificate /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;

    # Security headers
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-Frame-Options "SAMEORIGIN" always;

    location / {
        proxy_pass http://hcf_admin;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # WebSocket support
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}
```

#### 4. Systemd Service File

Create a systemd service to manage the application:

```ini
# /etc/systemd/system/hcf-admin.service

[Unit]
Description=HCF Admin Application
After=network.target postgresql.service krb5-kdc.service

[Service]
Type=notify
User=hcf-admin
WorkingDirectory=/opt/hcf-admin
Environment="PATH=/opt/hcf-admin/venv/bin"
EnvironmentFile=/etc/hcf-admin/.env
ExecStart=/opt/hcf-admin/venv/bin/gunicorn \
    -w 4 \
    -k uvicorn.workers.UvicornWorker \
    -b 127.0.0.1:8000 \
    app:app
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Enable and start the service:

```bash
sudo systemctl enable hcf-admin
sudo systemctl start hcf-admin
sudo systemctl status hcf-admin
```

#### 5. Docker Deployment

Create a `Dockerfile` for containerized deployment:

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    krb5-user libkrb5-dev postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python packages
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt gunicorn

# Copy application code
COPY . .

# Copy krb5.conf
COPY krb5.conf /etc/krb5.conf

# Expose port
EXPOSE 8000

# Run with Gunicorn
CMD ["gunicorn", "-w", "4", "-k", "uvicorn.workers.UvicornWorker", "-b", "0.0.0.0:8000", "app:app"]
```

Build and run:

```bash
docker build -t hcf-admin:latest .
docker run -d \
    -p 8000:8000 \
    -e DATABASE_URL="postgresql://user:pass@postgres:5432/mydb" \
    -e KERBEROS_REALM="EXAMPLE.COM" \
    -v /etc/krb5.conf:/etc/krb5.conf \
    hcf-admin:latest
```

#### 6. Docker Compose

For complete stack deployment with database and application:

```yaml
version: '3.8'

services:
  postgres:
    image: postgres:15-alpine
    environment:
      POSTGRES_USER: hcf_user
      POSTGRES_PASSWORD: secure_password
      POSTGRES_DB: hcf_db
    volumes:
      - postgres_data:/var/lib/postgresql/data
    ports:
      - "5432:5432"

  hcf-admin:
    build: .
    ports:
      - "8000:8000"
    environment:
      DB_HOST: postgres
      DB_USER: hcf_user
      DB_PASSWORD: secure_password
      DB_NAME: hcf_db
    depends_on:
      - postgres
    volumes:
      - ./config.toml:/app/config.toml
      - /etc/krb5.conf:/etc/krb5.conf

  nginx:
    image: nginx:alpine
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf
      - ./certs:/etc/nginx/certs
    depends_on:
      - hcf-admin
```

Run with:

```bash
docker-compose up -d
```

### Pre-Deployment Checklist

Use the included deployment tools to validate your setup before going live:

```bash
# Test database connectivity
python deploy_tools.py test-connection

# Discover all available tables
python deploy_tools.py discover-tables

# Validate configuration against database schema
python deploy_tools.py validate-config

# Auto-generate permission templates from database
python deploy_tools.py generate-config --output new_tables.toml
```

For detailed deployment instructions, see [DEPLOY.md](DEPLOY.md).

### Production Setup

1. **Session Store**: Use Redis or similar instead of in-memory sessions
   ```python
   # In app.py, configure Redis session store
   from fastapi_sessions.backends.implementations import SessionBackend
   from redis import Redis
   ```

2. **Secure Cookies**: Configure in `app.py`
   ```python
   session_cookie_secure = True
   session_cookie_httponly = True
   session_cookie_samesite = "lax"
   ```

3. **Environment Variables**: Never hardcode secrets
   ```bash
   export DB_PASSWORD=$(aws secretsmanager get-secret-value --secret-id db-password --query SecretString --output text)
   ```

4. **HTTPS/TLS**: Enable SSL via reverse proxy or uvicorn
   ```bash
   gunicorn --certfile=cert.pem --keyfile=key.pem --ssl-version=TLSv1_2 app:app
   ```

5. **Database Backups**: Automate with cron jobs
   ```bash
   # Daily backup
   0 2 * * * /usr/bin/pg_dump -h localhost -U hcf_user hcf_db | gzip > /backups/hcf_db_$(date +\%Y\%m\%d).sql.gz
   ```

6. **Logging**: Configure application logs
   ```python
   import logging
   logging.basicConfig(filename="/var/log/hcf-admin/app.log", level=logging.INFO)
   ```

7. **Kerberos Configuration**: Point to your organization's KDC
   ```ini
   [libdefaults]
       default_realm = YOUR.ORGANIZATION.COM
   [realms]
       YOUR.ORGANIZATION.COM = {
           kdc = kdc1.example.com
           kdc = kdc2.example.com
       }
   ```

8. **Health Checks**: Monitor application availability
   ```bash
   curl -f http://localhost:8000/health || systemctl restart hcf-admin
   ```

9. **Resource Limits**: Set appropriate limits for the service
   ```ini
   # In systemd service file
   MemoryLimit=2G
   TasksMax=256
   ```

10. **Connection Pool Settings**: Adjust for production workload
    ```python
    # In database.py
    ThreadedConnectionPool(minconn=5, maxconn=20)  # Increase for production
    ```

## Configuration

### config.toml Structure

```toml
[database]
host = "localhost"
port = 5432
database = "mydb"
user = "myuser"
password = "mypassword"

[app]
app_name = "HCF Admin"
version = "1.0.0"

[table_permissions]
[table_permissions.my_table]
allow_add = true
allow_delete = false
editable_columns = ["column1", "column2"]

[scripts]
backup = "../scripts/backup.sh"

[lookups]
[lookups.department]
sql = "SELECT id, name FROM departments ORDER BY name"

[dashboard]
default_table = "my_table"
```

### Hot Reload

Configuration changes made through the admin panel are immediately applied:

1. Click "Save" in the config editor
2. App reloads configuration from disk
3. New settings take effect for subsequent operations
4. No application restart needed

## Troubleshooting

### Database Connection Issues

- Verify PostgreSQL is running and accessible
- Check `config.toml` database credentials
- Ensure network connectivity to database host
- Run `python deploy_tools.py test-connection` for diagnostics

### Permission Denied Errors

- Verify user has required permission flags in `fastapi_users` table
- Check table-level permissions in `config.toml`
- First user should have full permissions by default
- Use admin panel to grant permissions to new users

### Config Validation Errors

- Run `python deploy_tools.py validate-config` to identify issues
- Ensure all referenced tables exist in database
- Verify column names in `editable_columns` match database schema
- Check script paths are correct and files exist

### Theme Not Applying

- Clear browser cache (Ctrl+Shift+Delete)
- Verify CSS files loaded (check browser DevTools Network tab)
- Check browser console for JavaScript errors
- Ensure theme toggle button is working

## Performance Notes

- Pagination is configured for up to 500 rows per page
- Connection pool maintains 2-10 concurrent connections
- Config is cached in-memory after loading
- HTMX minimizes full-page reloads
- Monitor database query performance for large tables

## Support & Documentation

- See [DEPLOY.md](DEPLOY.md) for deployment-specific guidance
- Check [config.toml](config.toml) for configuration examples
- Review application logs for error details
- Use the in-app Help page for feature documentation
