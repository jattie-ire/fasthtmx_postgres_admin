# Upgrade Guide: 1.0 → 1.1

This guide covers upgrading from FastHTMX Admin 1.0 to 1.1.0, including the critical connection pool fix and new log viewer feature.

## Overview

**Version 1.1.0 includes:**
- ✅ **Critical fix**: Connection pool exhaustion bug (prevents "PoolError: connection not found" after 10 requests)
- ✅ **New feature**: Log Viewer (`/logs`) for browsing and analyzing script logs
- ✅ No database schema changes
- ✅ No breaking changes to existing configuration or API

## Pre-Upgrade Checklist

Before upgrading, ensure:
- [ ] Current version is 1.0.x
- [ ] Database is backed up (no schema changes, but good practice)
- [ ] Scripts are healthy (no pending long-running operations)
- [ ] You have deployment tool access: `python deploy_tools.py`

## Upgrade Steps

### 1. Pull/Download 1.1.0

```bash
# If using git
git pull origin main
git checkout v1.1.0

# Or download release manually
```

### 2. Verify Code Changes (Optional but Recommended)

Verify the connection pool fix was applied:

```bash
# Should return 0 results (no conn.close() calls)
grep -r "\.close()" app.py | grep -v "#" | wc -l
# Output: 0 ✓

# Verify new log viewer endpoints exist
grep -r "/logs" app.py
# Output: Should see @app.get("/logs"), @app.get("/api/logs"), etc.
```

### 3. Update Configuration (Optional)

The log viewer is **optional**. To enable it, add to your `config.toml`:

```toml
[scripts.log_config]
# Map script names to their log locations
"Your Script Name" = { directory = "/path/to/logs", pattern = "*.log", display = true }

[scripts.log_display]
# Show the 5 most recent logs per script
limit = 5
```

**If you skip this step**: The app continues to work normally; `/logs` page returns "No log files found"

### 4. Validate Configuration

```bash
python deploy_tools.py validate-config

# Expected output:
# ✓ VALIDATION PASSED: Config is valid and ready to deploy
```

If you see errors about log paths, either:
- Ensure log directories exist, OR
- Remove `[scripts.log_config]` from config.toml to disable log viewer

### 5. Test the Application

```bash
# Start in development (single-threaded)
python app.py

# Or restart your production server
sudo systemctl restart fasthtmlx-admin
# Or with gunicorn
gunicorn -w 4 -b 0.0.0.0:8000 app:app
```

### 6. Verify Connection Pool Fix

Test that connections are being properly returned to the pool:

```bash
# Make multiple rapid requests (more than 10, which was the pool size limit)
for i in {1..20}; do
  curl -s http://localhost:8000/api/tables -H "Authorization: Bearer YOUR_TOKEN" > /dev/null
  echo "Request $i: OK"
done

# All 20 requests should succeed (1.0 would fail after ~10)
```

### 7. Verify Log Viewer (If Enabled)

```bash
# Visit the log viewer page
curl http://localhost:8000/logs

# You should see either:
# - A list of logs organized by script (if configured)
# - "No log files found" message (if not configured)
```

## Breaking Changes

**None.** Version 1.1.0 is fully backward compatible:
- All existing endpoints work identically
- All configuration options from 1.0 still work
- No database schema changes
- No API changes

## Known Issues / Limitations

None currently. Report issues via your usual channels.

## Rollback (If Needed)

If you encounter issues, rollback to 1.0:

```bash
# Git
git checkout v1.0.0

# Restart application
sudo systemctl restart fasthtmlx-admin
```

No database recovery needed (no schema changes were made).

## Performance Impact

**No negative impact:**
- Connection pool fix actually **improves performance** (connections stay available instead of being discarded)
- Log viewer runs on-demand via `/logs` endpoint (no background impact)
- No additional database queries on existing endpoints

## Deployment Scenarios

### Scenario 1: Single Server (Uvicorn)

```bash
# Pull 1.1.0
git pull origin v1.1.0

# Restart
pkill -f "uvicorn app:app"
python app.py  # Runs in foreground
# Or systemd: sudo systemctl restart fasthtmlx-admin
```

### Scenario 2: Clustered (Gunicorn + HAProxy)

```bash
# On each backend server:
git pull origin v1.1.0

# Restart gunicorn gracefully (doesn't drop connections)
sudo systemctl reload fasthtmlx-admin
# Or: kill -HUP <gunicorn_master_pid>
```

HAProxy continues serving requests from other backends during reload.

### Scenario 3: Docker

```bash
# Rebuild image with 1.1.0
docker build -t fasthtmlx-admin:1.1.0 .

# Graceful rolling update
docker service update --image fasthtmlx-admin:1.1.0 fasthtmlx_admin_service

# Or manual: stop old container, start new one
docker stop <old_container>
docker run -d --name fasthtmlx-admin fasthtmlx-admin:1.1.0
```

## Support

If you encounter issues:
1. Check deployment validation: `python deploy_tools.py validate-config`
2. Review application logs for errors
3. Verify network connectivity to PostgreSQL
4. Ensure log directories exist and are readable (if log viewer enabled)

## What's New to Learn

### Log Viewer Features

Users with `run_scripts` permission can now:
1. Visit `/logs` page
2. See logs organized by script name
3. Click any log to open in full-screen viewer
4. See syntax highlighting: timestamps (blue), log levels (red/gold/green/purple), key=value pairs (cyan)

### For Administrators

Configure log discovery in `config.toml`:

```toml
[scripts]
"Backup Job" = "/path/to/backup.sh"

[scripts.log_config]
"Backup Job" = { directory = "/var/log/backups", pattern = "backup_*.log", display = true }

[scripts.log_display]
limit = 5  # Show 5 newest logs per script
```

Logs are discovered automatically at page load; no database changes needed.

---

**Upgrade complete!** Your FastHTMX Admin is now running 1.1.0 with connection pool stability and log viewer functionality.
