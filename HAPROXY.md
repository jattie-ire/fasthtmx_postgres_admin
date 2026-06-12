# HAProxy Configuration Guide

HAProxy is a high-performance, battle-tested reverse proxy ideal for distributing traffic across multiple backend instances of the FastHTMX Admin application.

## Overview

**Why HAProxy?**
- Simple, elegant configuration syntax
- Superior load balancing algorithms (round-robin, least connections, consistent hashing)
- Excellent for high-traffic, high-availability deployments
- Minimal resource overhead
- Real-time statistics and monitoring
- Transparent failover between backend servers

**Architecture**
```
┌─────────────────┐
│   Client (80)   │
└────────┬────────┘
         │
    ┌────▼────────────┐
    │     HAProxy      │ (listens on :80 & :443)
    │  Load Balancer   │
    └────┬────┬───┬───┘
         │    │   │
    ┌────▼─┐┌──▼──┐┌──▼──┐┌──▼──┐
    │:8000 ││:8001││:8002││:8003│  FastAPI instances
    └──────┘└─────┘└─────┘└─────┘  (Gunicorn workers)
```

---

## 1. Global Section - Foundation Settings

```
global
    maxconn 4096
    ulimit-n 1000000
    daemon
    log stdout local0
```

**What it does:**
- `maxconn 4096`: Maximum number of simultaneous connections HAProxy can handle globally
- `ulimit-n 1000000`: Tells Linux to allow HAProxy to open 1 million file descriptors (each connection = 1 file descriptor)
- `daemon`: Runs HAProxy in background (detaches from terminal)
- `log stdout local0`: Send logs to standard output using syslog facility "local0"

**Why it matters for your setup:**
Your FastHTMX Admin has 4 backend instances. Each client connection creates 2 file descriptors (one from client→HAProxy, one from HAProxy→backend). With `maxconn 4096`, you can handle roughly 2,000 simultaneous users. For higher traffic, increase both numbers.

**Example calculation:**
```
If you expect 10,000 concurrent users:
- Each user needs 2 file descriptors (client side + backend side)
- Set maxconn to 20,000
- Set ulimit-n to at least 25,000 (with buffer)
```

---

## 2. Defaults Section - Common Rules for All Frontends/Backends

```
defaults
    mode http
    timeout connect 5000ms
    timeout client 60000ms
    timeout server 60000ms
    log global
    option httplog
    option forwardfor
```

### Line-by-line breakdown:

**`mode http`** - Process traffic as HTTP (not TCP raw sockets)
- Means HAProxy understands HTTP headers and can make smart routing decisions
- Alternative: `mode tcp` for non-HTTP protocols

**`timeout connect 5000ms`** - Wait max 5 seconds to connect to backend server
- If backend server doesn't respond in 5 seconds, connection fails
- For slow/distant servers, increase this
```
Connection attempt timeline:
Client → HAProxy → Backend Server
         └─5000ms─┘
```

**`timeout client 60000ms`** - Keep client connection open for 60 seconds of inactivity
- If client sends no data for 60 seconds, HAProxy closes the connection
- Prevents zombie connections from hanging clients

**`timeout server 60000ms`** - Keep backend connection open for 60 seconds of inactivity
- Matches client timeout to prevent mismatches
- If backend is slow, increase both timeouts

**`log global`** - Use the logging settings from the `global` section
- Ensures all traffic is logged consistently

**`option httplog`** - Log in HTTP format (includes method, URL, status code)
- Example log: `GET /api/tables HTTP/1.1 200 1234 "Mozilla..."`

**`option forwardfor`** - Add `X-Forwarded-For` header to backend requests
- Tells your FastAPI app the real client IP (not HAProxy's IP)
```
Original request from client: 192.168.1.100
HAProxy forwards to backend: 127.0.0.1

Without forwardfor header:
Your app sees IP: 127.0.0.1 (wrong!)

With forwardfor header:
Header added: X-Forwarded-For: 192.168.1.100
Your app reads this header and knows real IP: 192.168.1.100
```

---

## 3. Frontend Section - What Clients Connect To

```
frontend http-in
    bind *:80
    redirect scheme https code 301 if !{ ssl_fc }

frontend https-in
    bind *:443 ssl crt /path/to/cert.pem
    default_backend app_cluster
```

### Line-by-line breakdown:

**`bind *:80`** - Listen on all network interfaces (`*`) on port 80
- `*` = any IP address on this server (0.0.0.0)
- If you only want localhost: `bind 127.0.0.1:80`
- You can bind multiple ports: `bind *:80 *:8080`

**`redirect scheme https code 301 if !{ ssl_fc }`** - Force HTTP→HTTPS
- `redirect scheme https`: Tell client to use HTTPS instead
- `code 301`: Permanent redirect (browsers will cache this)
- `if !{ ssl_fc }`: Only if NOT already using SSL
  - `ssl_fc` = "SSL Front-end Connection"
  - `!{ ssl_fc }` = NOT an SSL connection

**Real example:**
```
Client requests: http://admin.example.com/login
HAProxy sees: !{ ssl_fc } = true (not SSL yet)
HAProxy responds: 301 Permanent Redirect to https://admin.example.com/login
Browser automatically follows redirect
```

**`bind *:443 ssl crt /path/to/cert.pem`** - Listen on port 443 with SSL
- SSL certificate file combines cert + private key
- HAProxy decrypts HTTPS traffic, then forwards as HTTP to backends

---

## 4. Backend Section - Where Traffic Goes

```
backend app_cluster
    balance roundrobin
    option httpchk GET /
    
    server app1 127.0.0.1:8000 maxconn 32 check inter 5000 fall 3 rise 2
    server app2 127.0.0.1:8001 maxconn 32 check inter 5000 fall 3 rise 2
    server app3 127.0.0.1:8002 maxconn 32 check inter 5000 fall 3 rise 2
    server app4 127.0.0.1:8003 maxconn 32 check inter 5000 fall 3 rise 2
```

### Load Balancing

**`balance roundrobin`** - Distribute requests in a cycle
```
Request 1 → app1 (127.0.0.1:8000)
Request 2 → app2 (127.0.0.1:8001)
Request 3 → app3 (127.0.0.1:8002)
Request 4 → app4 (127.0.0.1:8003)
Request 5 → app1 (cycle repeats)
```

### Health Checking

**`option httpchk GET /`** - Health check via HTTP GET
- Every 5 seconds (see `inter` below), HAProxy sends: `GET / HTTP/1.1`
- If response is 200-399 (success), server stays UP
- If connection fails or status 5xx (error), server marked DOWN

### Server Definition

**`server app1 127.0.0.1:8000 maxconn 32 check inter 5000 fall 3 rise 2`** - Define one backend

Breaking it down:
- `server app1`: Name this server "app1" (just for identification in logs)
- `127.0.0.1:8000`: IP and port to forward traffic to
- `maxconn 32`: HAProxy will open at most 32 connections from HAProxy→app1
  - Prevents one backend from being overwhelmed if others fail

- `check`: Enable health checks for this server
- `inter 5000`: Check every 5000 milliseconds (5 seconds)
- `fall 3`: Mark server DOWN after 3 consecutive health check failures
- `rise 2`: Mark server UP after 2 consecutive successful health checks

### Health Check Sequence Example

```
Time 0s:   Health check sent, app1 responds with 200 OK ✓
Time 5s:   Health check sent, app1 responds with 200 OK ✓
Time 10s:  Health check sent, app1 TIMEOUT (no response) ✗ (1 failure)
Time 15s:  Health check sent, app1 TIMEOUT ✗ (2 failures)
Time 20s:  Health check sent, app1 TIMEOUT ✗ (3 failures - MARKED DOWN!)

No new connections go to app1 anymore. Existing connections drain.

Time 25s:  app1 comes back online, health check succeeds ✓ (1 success)
Time 30s:  health check succeeds ✓ (2 successes - MARKED UP!)

New connections resume being sent to app1.
```

---

## 5. Real-World Request Flow Example

Let's trace a request through your FastHTMX Admin setup:

```
User in browser types: https://admin.example.com/dashboard

Step 1: Browser establishes SSL connection to HAProxy
  Browser → HAProxy (port 443, SSL encrypted)
  HAProxy decrypts the request: GET /dashboard

Step 2: HAProxy applies load balancing
  - Request counter: 42 requests so far
  - 42 % 4 = 2 (use server index 2)
  - Next request → app3 (127.0.0.1:8003)

Step 3: HAProxy forwards to backend with headers
  GET /dashboard HTTP/1.1
  Host: admin.example.com
  X-Forwarded-For: 192.168.1.100
  X-Forwarded-Proto: https
  
  (HAProxy adds these headers automatically)

Step 4: FastAPI on app3 receives request
  - Reads X-Forwarded-For to get real user IP
  - Reads X-Forwarded-Proto to know request was HTTPS
  - Processes request, returns HTML

Step 5: HAProxy sends response back to browser
  HTTP/1.1 200 OK
  Content-Type: text/html
  
  [HTML body]

Step 6: Browser renders the page
  User sees: Dashboard loaded!
```

---

## 6. Connection Limits - The maxconn Setting

```
backend app_cluster
    server app1 127.0.0.1:8000 maxconn 32 check
    server app2 127.0.0.1:8001 maxconn 32 check
```

**What `maxconn 32` means:**

```
HAProxy can open AT MOST 32 simultaneous connections to app1

Scenario:
- app1 is slow (processing takes 30 seconds)
- Client 1 connects at 0s: 1/32 connections used
- Client 2 connects at 1s: 2/32
- Client 3 connects at 2s: 3/32
- ...
- Client 32 connects at 31s: 32/32 (FULL!)

- Client 33 tries to connect at 32s:
  - Can't open new connection to app1 (maxconn limit hit)
  - HAProxy tries app2, app3, or app4 instead
  - OR queues the request and waits for app1 connection to free up

- Client 1 finishes at 30s: 31/32 connections (1 slot freed)
- Client 33's request can now connect to app1
```

**Why this matters:**

If one backend is slower than others, `maxconn` ensures:
1. It doesn't get swamped with connections
2. Other backends get a fair share of traffic
3. Queue prevents request loss

---

## 7. Complete Configuration Explained

```
# /etc/haproxy/haproxy.cfg

global
    # Allow 100,000 concurrent connections
    maxconn 100000
    # Linux kernel should open up to 1M file descriptors for HAProxy process
    ulimit-n 1000000
    # Run in background
    daemon
    # Log everything using syslog facility local0
    log stdout local0

defaults
    # Speak HTTP protocol
    mode http
    # Wait 5 seconds to connect to backend
    timeout connect 5000ms
    # Disconnect client if idle for 60 seconds
    timeout client 60000ms
    # Disconnect backend if idle for 60 seconds
    timeout server 60000ms
    # Use logging from global section
    log global
    # Log in HTTP format (method, URL, status)
    option httplog
    # Add X-Forwarded-For header so backend knows real client IP
    option forwardfor

# =============================================================================
# FRONTEND: What clients connect to
# =============================================================================

frontend http-in
    # Listen on port 80 on all network interfaces
    bind *:80
    # If request is NOT encrypted (not ssl_fc = !ssl_fc), redirect to HTTPS
    redirect scheme https code 301 if !{ ssl_fc }

# =============================================================================
# FRONTEND: HTTPS entry point
# =============================================================================

frontend https-in
    # Listen on port 443 with SSL using certificate at /etc/haproxy/cert.pem
    bind *:443 ssl crt /etc/haproxy/cert.pem
    # Send all HTTPS traffic to the "app_cluster" backend
    default_backend app_cluster

# =============================================================================
# MONITORING: Stats dashboard (optional but useful)
# =============================================================================

frontend stats
    # Listen on port 8404 for admin access
    bind *:8404
    # Enable statistics page
    stats enable
    # Access at http://localhost:8404/stats
    stats uri /stats
    # Refresh stats every 30 seconds
    stats refresh 30s

# =============================================================================
# BACKEND: Where traffic is routed
# =============================================================================

backend app_cluster
    # Distribute requests evenly round-robin: req1→app1, req2→app2, req3→app3, etc
    balance roundrobin
    
    # Health check: Send "GET /" to backend every 5 seconds
    # If 3 consecutive checks fail, mark server DOWN
    # If 2 consecutive checks succeed after being DOWN, mark UP
    option httpchk GET /
    
    # Define the 4 FastAPI instances running via Gunicorn
    
    # First instance on port 8000
    # - maxconn 32: HAProxy opens max 32 connections to this server
    # - check: Monitor health via health checks
    # - inter 5000: Health check every 5 seconds
    # - fall 3: Mark DOWN after 3 failures
    # - rise 2: Mark UP after 2 successes
    server app1 127.0.0.1:8000 maxconn 32 check inter 5000 fall 3 rise 2
    
    # Remaining 3 instances on ports 8001, 8002, 8003 (same config)
    server app2 127.0.0.1:8001 maxconn 32 check inter 5000 fall 3 rise 2
    server app3 127.0.0.1:8002 maxconn 32 check inter 5000 fall 3 rise 2
    server app4 127.0.0.1:8003 maxconn 32 check inter 5000 fall 3 rise 2
    
    # Reuse idle HTTP connections (reduces overhead)
    http-reuse safe
```

---

## 8. Running Your Setup Step-by-Step

**Step 1: Start 4 FastAPI instances**
```bash
# Terminal 1
gunicorn -w 4 -k uvicorn.workers.UvicornWorker -b 127.0.0.1:8000 app:app

# This starts Gunicorn listening on 127.0.0.1:8000
# Gunicorn internally manages 4 worker processes
```

**Step 2: Start HAProxy**
```bash
# Terminal 2
sudo haproxy -f /etc/haproxy/haproxy.cfg

# HAProxy now:
# - Listens on :80 (redirects to :443)
# - Listens on :443 (SSL)
# - Checks health of backends every 5 seconds
# - Distributes requests round-robin
```

**Step 3: Make a request**
```bash
# Terminal 3
curl -k https://localhost/dashboard

# This:
# 1. Connects to HAProxy on :443
# 2. HAProxy decrypts SSL
# 3. HAProxy picks next server in round-robin (first request → app1)
# 4. Forwards GET /dashboard to 127.0.0.1:8000
# 5. Receives response and sends back to client
```

**Step 4: Monitor**
```bash
# Open browser
http://localhost:8404/stats

# See:
# - app1, app2, app3, app4 status (UP/DOWN)
# - Request rates
# - Active connections per server
# - Error counts
```

---

## 9. What Happens When a Backend Fails

```
Initial state: All servers UP

Scenario: app3 (127.0.0.1:8002) crashes

Time 5s:   Health check to app3: TIMEOUT ✗
Time 10s:  Health check to app3: TIMEOUT ✗
Time 15s:  Health check to app3: TIMEOUT ✗ (3 failures total)
           
           app3 marked DOWN!
           
           New incoming requests:
           Round-robin continues: req→app1, req→app2, req→app4, req→app1, etc
           (app3 is skipped)
           
           Existing connections to app3:
           HAProxy waits for them to finish naturally
           (doesn't force-close them)

Time 25s:  app3 comes back online, health check succeeds ✓
Time 30s:  Another success ✓ (2 successes total)
           
           app3 marked UP!
           
           New requests now include app3 again:
           req→app1, req→app2, req→app3, req→app4, req→app1, etc
```

This is **automatic failover** – no manual intervention needed!

---

## Installation

### Ubuntu/Debian

```bash
# Install HAProxy
sudo apt-get update
sudo apt-get install haproxy

# Enable and start the service
sudo systemctl enable haproxy
sudo systemctl start haproxy

# Verify installation
haproxy -v
```

### macOS

```bash
# Using Homebrew
brew install haproxy

# Start HAProxy (if configured as a service)
brew services start haproxy
```

---

## Configuration File Locations

- **Debian/Ubuntu**: `/etc/haproxy/haproxy.cfg`
- **macOS (Homebrew)**: `/usr/local/etc/haproxy.cfg`
- **Development**: Create anywhere (then pass with `-f` flag)

---

## SSL/TLS Setup

### Self-Signed Certificate (Development)

```bash
# Create certificate valid for 365 days
openssl req -x509 -newkey rsa:2048 -keyout key.pem -out cert.pem -days 365 -nodes

# HAProxy expects certificate and key in one file
cat cert.pem key.pem > /etc/haproxy/cert.pem
sudo chmod 600 /etc/haproxy/cert.pem
```

### Using Let's Encrypt (Production)

```bash
# Install Certbot
sudo apt-get install certbot

# Obtain certificate (stop HAProxy first)
sudo certbot certonly --standalone -d admin.example.com

# Combine cert and key
sudo cat /etc/letsencrypt/live/admin.example.com/fullchain.pem \
         /etc/letsencrypt/live/admin.example.com/privkey.pem \
         > /etc/haproxy/cert.pem
sudo chmod 600 /etc/haproxy/cert.pem

# Auto-renew with Certbot hook
sudo certbot renew --post-hook "systemctl reload haproxy"
```

---

## Service Management

### Using Systemd

```bash
# Start HAProxy
sudo systemctl start haproxy

# Stop HAProxy
sudo systemctl stop haproxy

# Restart (reload configuration)
sudo systemctl restart haproxy

# View logs
sudo journalctl -u haproxy -f

# Check status
sudo systemctl status haproxy
```

### Manual Start/Stop

```bash
# Start (foreground, useful for testing)
sudo haproxy -f /etc/haproxy/haproxy.cfg

# Start (daemon mode)
sudo haproxy -f /etc/haproxy/haproxy.cfg -D

# Reload configuration (graceful, no connection drops)
sudo haproxy -f /etc/haproxy/haproxy.cfg -D -sf $(pidof haproxy)

# Check configuration syntax
sudo haproxy -f /etc/haproxy/haproxy.cfg -c
```

---

## Monitoring HAProxy

### Stats Dashboard

Access the stats dashboard:
```
http://localhost:8404/stats
```

Shows:
- Frontend/backend status
- Server health (UP/DOWN)
- Connection counts
- Request/response rates
- Session data

### Logs

```bash
# View real-time logs
sudo tail -f /var/log/haproxy.log

# Or use journalctl (if using systemd)
sudo journalctl -u haproxy -f

# Filter for errors only
sudo grep "ERROR\|error" /var/log/haproxy.log
```

---

## Troubleshooting

### HAProxy Won't Start

```bash
# Check syntax errors
sudo haproxy -f /etc/haproxy/haproxy.cfg -c

# Check port already in use
sudo lsof -i :80 -i :443

# Check permissions
sudo ls -l /etc/haproxy/haproxy.cfg
sudo ls -l /etc/haproxy/cert.pem
```

### Backends Marked DOWN

```bash
# Check if backend servers are running
lsof -i :8000 -i :8001 -i :8002 -i :8003

# Test direct connection
curl -v http://127.0.0.1:8000/

# View health check failures in logs
sudo grep "DOWN" /var/log/haproxy.log
```

### High Latency or Connection Timeouts

```
# In HAProxy config, increase timeouts:
defaults
    timeout connect 10000ms      # Connection to backend
    timeout client 120000ms       # Client -> HAProxy
    timeout server 120000ms       # HAProxy -> Backend
    timeout http-request 10s      # Time to receive complete HTTP request
    timeout http-keep-alive 10s   # Keep-alive timeout
```

### Memory Usage Spikes

```
# Reduce max connections or session limits
global
    maxconn 50000  # Reduce from 100000

backend app_cluster
    server app1 127.0.0.1:8000 maxconn 16  # Reduce from 32
```

---

## Load Balancing Algorithms

Change the `balance` directive in the backend:

```
# Round-robin (default, recommended)
balance roundrobin

# Least connections (sends new connections to server with fewest active)
balance leastconn

# Source IP hashing (same client always goes to same server)
balance source

# Random
balance random

# Consistent hash (for persistent caching)
balance uri consistent
```

---

## Systemd Service File

For automatic startup on system boot:

```ini
# /etc/systemd/system/haproxy.service

[Unit]
Description=HAProxy Reverse Proxy
After=network.target

[Service]
Type=notify
ExecStart=/usr/sbin/haproxy -f /etc/haproxy/haproxy.cfg -Ws
ExecReload=/bin/bash -c 'test -f /proc/$(pgrep haproxy)/stat' && kill -USR2 $(pgrep haproxy)
Restart=on-failure
RestartSec=5s

[Install]
WantedBy=multi-user.target
```

Enable and start:
```bash
sudo systemctl daemon-reload
sudo systemctl enable haproxy
sudo systemctl start haproxy
```

---

## Performance Benchmarking

```bash
# Install Apache Bench
sudo apt-get install apache2-utils

# Run benchmark (1000 requests, 10 concurrent)
ab -n 1000 -c 10 http://localhost/

# Run with HTTPS
ab -n 1000 -c 10 https://localhost/
```

---

## Additional Resources

- [Official HAProxy Documentation](http://www.haproxy.org/)
- [HAProxy Configuration Manual](http://cbonte.github.io/haproxy-dconv/)
- [HAProxy Best Practices](https://www.haproxy.com/resources/)
