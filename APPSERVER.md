# Application Servers: Uvicorn vs Gunicorn

A comprehensive guide to understanding application servers, why they exist, and how to choose between Uvicorn and Gunicorn for your FastHTMX Admin deployment.

---

## Table of Contents

1. [The Names](#the-names)
2. [What They Actually Do](#what-they-actually-do)
3. [Technical Comparison](#technical-comparison)
4. [Why Use Them Together](#why-use-them-together)
5. [Performance Scenarios](#performance-scenarios)
6. [When to Use What](#when-to-use-what)
7. [Your FastHTMX Admin Setup](#your-fasthtmx-admin-setup)

---

## The Names

### Gunicorn = "Green Unicorn"

Named as a playful reference to the Python community's love of whimsical naming:
- **"Green"** likely refers to greenlets (lightweight pseudo-threads in Python)
- **"Unicorn"** = just cool and mythical
- It's a joke name that stuck and became the industry standard for WSGI servers

### Uvicorn

Likely inspired by Gunicorn:
- **"U"** = ASGI (or just stands out visually)
- Follows the Python naming convention of playful server names
- Less clear origin, but clearly inspired by Gunicorn's naming style

### Cultural Context

The Python community values whimsical naming:
```
Django (the musical genius)
Twisted (async networking)
Tornado (high-speed server)
Flask (lightweight framework)
Celery (distributed task queue)
Gunicorn (Green Unicorn)
Uvicorn (ASGI Unicorn)
```

The actual names don't describe what they do—you just have to learn them. It's part of Python culture.

---

## What They Actually Do

### Gunicorn (WSGI Server)

**WSGI** = Web Server Gateway Interface (synchronous protocol)

```
Client Request
    ↓
HAProxy/Nginx (reverse proxy)
    ↓
Gunicorn (pre-fork model, process manager)
    ├── Worker Process 1 (handles requests sync)
    ├── Worker Process 2 (handles requests sync)
    ├── Worker Process 3 (handles requests sync)
    └── Worker Process 4 (handles requests sync)
```

**How it works:**
- Spawns multiple **separate processes** (workers)
- Each worker is a completely independent Python interpreter
- Each worker handles one request at a time (synchronously)
- If Worker 1 is processing a request (5 second database query), it's blocked—can't handle other requests
- But Worker 2, 3, 4 can handle requests simultaneously on other CPU cores
- Uses OS-level process isolation (safer, more stable, but more memory)

**Example timeline:**
```
Request 1 arrives → Goes to Worker 1 (takes 5 seconds: database query)
Request 2 arrives immediately → Goes to Worker 2 (starts right away)
Request 3 arrives → Goes to Worker 3
Request 4 arrives → Goes to Worker 4
Request 5 arrives → Waits in queue (all 4 workers busy)

Time 5s: Worker 1 finishes Request 1, picks up Request 5 from queue
```

**Memory usage:**
- Each process: ~50-100 MB (all Python libraries loaded per worker)
- 4 workers: ~400 MB overhead just for interpreter copies

---

### Uvicorn (ASGI Server)

**ASGI** = Asynchronous Server Gateway Interface (async protocol)

```
Client Request
    ↓
HAProxy/Nginx (reverse proxy)
    ↓
Uvicorn (single process, event loop)
    └── Event Loop (like Node.js event loop)
        ├── Request 1 (paused at database query)
        ├── Request 2 (processing)
        ├── Request 3 (paused at API call)
        ├── Request 4 (sending response)
        └── Request 5 (starting to process)
```

**How it works:**
- Single process with **event loop** (similar to JavaScript/Node.js)
- Handles multiple requests **concurrently** using async/await
- When a request hits I/O (database query, network call), uvicorn **pauses** it and switches to another request
- Not truly parallel (single-threaded), but **concurrent** (interleaved)
- Much lower overhead than separate processes
- Requires Python async/await support (Python 3.5+)

**Example timeline:**
```
Request 1 arrives → Starts processing
  → Hits "await database.query()" → Paused and switched to Request 2

Request 2 arrives → Starts processing
  → Hits "await external_api.call()" → Paused and switched to Request 3

Request 3 arrives → Starts processing
  → Completes all work → Sends response

Request 4 arrives → Starts processing

Request 1's database query finishes → Resumes Request 1
  → Continues processing → Completes → Sends response

Request 2's API call finishes → Resumes Request 2
```

**Memory usage:**
- Single process: ~20-30 MB
- Event loop handles thousands of concurrent requests efficiently

---

## Technical Comparison

| Aspect | Gunicorn | Uvicorn |
|--------|----------|---------|
| **Protocol** | WSGI (synchronous) | ASGI (asynchronous) |
| **Model** | Multi-process (pre-fork) | Single-process event loop |
| **Concurrency Type** | Parallel (true multi-tasking) | Concurrent (interleaved) |
| **Memory per worker** | ~50-100 MB per process | ~20-30 MB total |
| **Startup time** | Slower (spawns processes) | Faster (single process) |
| **Python versions** | Python 2/3, any code | Python 3 async/await only |
| **Typical frameworks** | Flask, Django, older frameworks | FastAPI, Starlette, modern frameworks |
| **Database I/O** | Blocks entire worker thread | Non-blocking async await |
| **Debugging** | Easier (process-based) | Harder (async debugging) |
| **CPU cores used** | Multiple (one per worker) | Single core (need multiple instances) |
| **Crash handling** | One crash = one worker down | One crash = entire app down |
| **Code required** | Regular sync code | Async/await code |

---

## Why Use Them Together?

The most common production setup for FastAPI:

```bash
gunicorn -w 4 -k uvicorn.workers.UvicornWorker -b 127.0.0.1:8000 app:app
```

This command creates:

```
Gunicorn (Process Manager)
    ├── Worker 1: Uvicorn (event loop)
    ├── Worker 2: Uvicorn (event loop)
    ├── Worker 3: Uvicorn (event loop)
    └── Worker 4: Uvicorn (event loop)

Result: 4 independent Python processes, each with async event loop
```

**Why this combination is brilliant:**

1. **Gunicorn** manages 4 separate processes (true parallelism across CPU cores)
2. **Each Uvicorn** uses async internally (high concurrency within each process)
3. **Result**: 4 × event loops = better CPU utilization + async concurrency + crash isolation

### The Best of Both Worlds

```
Gunicorn benefits:
  ✓ Uses multiple CPU cores (parallelism)
  ✓ Process isolation (one crash doesn't kill everything)
  ✓ Mature, battle-tested process manager
  
Uvicorn benefits:
  ✓ Async/await (handles I/O efficiently)
  ✓ Low memory per worker
  ✓ High concurrency within each process
```

---

## Performance Scenarios

### Scenario: 100 Concurrent Requests, Each Takes 5 Seconds

All requests are I/O-bound (database query):

#### Pure Gunicorn (4 sync workers)

```
Time 0s:   100 requests arrive
           Worker 1: Handling Request 1 (5 second database query) ⏳
           Worker 2: Handling Request 2 (5 second database query) ⏳
           Worker 3: Handling Request 3 (5 second database query) ⏳
           Worker 4: Handling Request 4 (5 second database query) ⏳
           Queue: Requests 5-100 waiting (96 requests in queue) 🚫

Time 5s:   First 4 complete ✓
           Workers pick up Requests 5-8 from queue
           Queue: Requests 9-100 still waiting (92 requests in queue)
           
           Total time for all 100: 100/4 workers × 5s = 125 seconds ❌
```

**Result:** ~125 seconds (very slow, queue backs up)

---

#### Pure Uvicorn (1 async process)

```
Time 0s:   100 requests arrive
           Event loop handles all concurrently via async/await
           
           Request 1: Hits database query → Paused ⏸️
           Request 2: Hits database query → Paused ⏸️
           Request 3: Hits database query → Paused ⏸️
           ...
           Request 100: Hits database query → Paused ⏸️
           
           All 100 database queries run IN PARALLEL at database server

Time 5s+:  Database responses come back
           Requests resume and complete
           
           Total time for all 100: ~5-7 seconds (heavily overlapped) ✓
```

**Result:** ~5-7 seconds (very fast, async concurrency!)

**BUT:** Only uses 1 CPU core—wastes 75% of CPU if running on 4-core machine

---

#### Gunicorn + 4 Uvicorn Workers (Best of Both)

```
Time 0s:   100 requests arrive, distributed to 4 workers
           
           Worker 1 event loop: Handles 25 requests async
             Request 1: database query → Paused
             Request 5: database query → Paused
             Request 9: database query → Paused
             ...
           
           Worker 2 event loop: Handles 25 requests async
           Worker 3 event loop: Handles 25 requests async
           Worker 4 event loop: Handles 25 requests async

Time 5s+:  Database responses come back
           All 100 complete
           
           Total time: ~5-7 seconds (like pure Uvicorn)
           BUT using all 4 CPU cores ✓
```

**Result:** ~5-7 seconds (as fast as pure Uvicorn) + 4 CPU cores active + process isolation

---

### Summary

| Setup | Time to Complete 100 Requests | CPU Cores Used | Memory | Crash Resilience |
|-------|------|--------|--------|------------------|
| Gunicorn 4 sync workers | ~125 seconds | 4 cores | 400 MB | Good |
| Uvicorn 1 async process | ~6 seconds | 1 core | 30 MB | Poor |
| **Gunicorn 4 + Uvicorn workers** | **~6 seconds** | **4 cores** | **120 MB** | **Good** |

---

## When to Use What

### Use Pure Gunicorn with Sync Workers

**When:**
- Running old frameworks (Flask, Django 2.x with no async)
- Code is not async-ready
- Simplicity more important than max concurrency
- I/O-bound latency is acceptable

**Example:**
```python
# Old Flask app (no async support)
@app.route('/data')
def get_data():
    result = database.query()  # Blocks entire worker
    return result

# Deploy with:
# gunicorn -w 4 app:app
```

---

### Use Pure Uvicorn

**When:**
- Development/testing only
- Single-machine deployment with low traffic
- Quick prototyping
- You want minimum memory usage
- Running on resource-constrained environment (edge device)

**Example:**
```bash
# Development
uvicorn app:app --host 127.0.0.1 --port 8000 --reload

# Very light production (single machine, low QPS)
uvicorn app:app --host 127.0.0.1 --port 8000 --workers 1
```

**Gotcha:** Single process = if it crashes, app is down. No process isolation.

---

### Use Gunicorn + Uvicorn Workers (RECOMMENDED FOR PRODUCTION)

**When:**
- Production FastAPI deployment
- Multi-core server
- Need both performance and reliability
- Want to leverage async AND CPU parallelism
- This is the industry standard for FastAPI

**Example:**
```bash
# Production (recommended)
gunicorn \
    -w 4 \
    -k uvicorn.workers.UvicornWorker \
    -b 127.0.0.1:8000 \
    app:app
```

**Why this is best:**
- ✅ Uses all CPU cores
- ✅ Async event loop efficiency
- ✅ Process isolation (one crash doesn't kill all)
- ✅ Low memory per worker
- ✅ Industry standard
- ✅ Integrates perfectly with HAProxy for load balancing

---

## Your FastHTMX Admin Setup

Your production configuration:

```bash
gunicorn -w 4 -k uvicorn.workers.UvicornWorker -b 127.0.0.1:8000 app:app
```

### What Happens Under the Hood

1. **Gunicorn starts** as the process manager
2. **Spawns 4 worker processes**, each running Uvicorn
3. **Each Uvicorn** loads your FastAPI app (app:app)
4. **Each Uvicorn** runs an event loop in its own process
5. **Gunicorn** listens on 127.0.0.1:8000 and distributes requests across 4 workers

### Request Flow

```
User Request → HAProxy (port 443)
    ↓
HAProxy redirects to → 127.0.0.1:8000 (Gunicorn)
    ↓
Gunicorn round-robin → Worker 1/2/3/4
    ↓
Uvicorn in selected worker → Handles with async event loop
    ↓
FastAPI processes request (async database calls non-blocking)
    ↓
Response sent back through HAProxy to user
```

### Benefits for Your Setup

- **Scales across CPU cores**: 4 cores = 4 workers = true parallelism
- **Handles I/O efficiently**: Async waits in database queries don't block
- **High concurrency**: Handles thousands of concurrent users
- **Automatic failover**: If one worker crashes, 3 keep running (HAProxy sees it)
- **Fast startup**: Shared Uvicorn event loop code, quick initialization
- **Low memory**: 120-150 MB total for 4 workers + Gunicorn

---

## Memory Usage Comparison

Running 100 concurrent requests to your FastHTMX Admin:

```
Pure Gunicorn (4 sync workers):
  Master process: 10 MB
  Worker 1: 80 MB (full Python, Django libs)
  Worker 2: 80 MB
  Worker 3: 80 MB
  Worker 4: 80 MB
  ────────────
  Total: ~410 MB

Pure Uvicorn (1 async worker):
  Process: 30 MB (FastAPI, async libs)
  ────────────
  Total: ~30 MB
  BUT: Only handles 1 CPU core (wasteful on multi-core)

Gunicorn + 4 Uvicorn workers:
  Master process: 10 MB
  Worker 1: 40 MB (FastAPI, async libs)
  Worker 2: 40 MB
  Worker 3: 40 MB
  Worker 4: 40 MB
  ────────────
  Total: ~170 MB
  PLUS: Uses all 4 CPU cores + async efficiency ✓
```

---

## Process vs Thread vs Async

### Process (Gunicorn default)

```
Process 1 (separate Python interpreter)
  ├── Runs Request 1
  ├── Runs Request 2
  └── Runs Request 3

Process 2 (separate Python interpreter)
  ├── Runs Request 4
  ├── Runs Request 5
  └── Runs Request 6

Parallelism: YES (OS runs them simultaneously on different cores)
Memory: HIGH (each interpreter loads all libs)
Crash impact: Only affects that process
GIL impact: NONE (each process has its own GIL)
```

### Thread (not used in production Python web)

```
Single Python Process
  ├── Thread 1: Runs Request 1
  ├── Thread 2: Runs Request 2 (blocked by GIL)
  └── Thread 3: Runs Request 3 (blocked by GIL)

Parallelism: NO (Python's GIL prevents true parallelism)
Memory: MEDIUM (single interpreter, shared libs)
Crash impact: Entire app crashes
GIL impact: HUGE (threads block each other)
```

**Note:** Python's GIL (Global Interpreter Lock) prevents threads from running Python bytecode in parallel. This is why web servers use processes or async, not threads.

---

### Async (Uvicorn default)

```
Single Python Process with Event Loop
  ├── Request 1: awaiting database
  ├── Request 2: processing
  ├── Request 3: awaiting API call
  └── Request 4: sending response

Concurrency: YES (event loop switches between requests)
Parallelism: NO (single thread, but I/O doesn't block others)
Memory: LOW (single interpreter, low overhead)
Crash impact: Entire app crashes
GIL impact: No problem (no threads competing)
```

**Key difference:** Async provides concurrency (many things happening) but not parallelism (truly simultaneous). For I/O-bound workloads, this is fine. For CPU-bound workloads, you need processes.

---

## Debugging Tips

### How to see if your setup is working

```bash
# Check processes running
ps aux | grep gunicorn
# Should show:
#   gunicorn master process
#   gunicorn worker 1
#   gunicorn worker 2
#   gunicorn worker 3
#   gunicorn worker 4

# Check connections to each port
lsof -i :8000
# Should show 4 Uvicorn processes on port 8000

# Monitor with htop
htop -p $(pgrep -f gunicorn | tr '\n' ',')
# See CPU and memory for each worker
```

### Performance monitoring

```bash
# Real-time stats
curl http://localhost:8404/stats

# Should show:
# - 4 servers (app1, app2, app3, app4)
# - Each RUNNING (green)
# - Request rates per server
# - Queue length
```

---

## Common Issues

### "ModuleNotFoundError" when using Gunicorn

```
Error: ModuleNotFoundError: No module named 'uvicorn'
```

**Solution:** Install uvicorn in your environment
```bash
pip install uvicorn
# OR if using conda:
conda install uvicorn
```

---

### "Address already in use" error

```
OSError: [Errno 98] Address already in use: ('127.0.0.1', 8000)
```

**Solution:** Kill existing process
```bash
# Find what's using port 8000
lsof -i :8000

# Kill it
kill -9 <PID>

# OR just change the port
gunicorn -b 127.0.0.1:8001 app:app
```

---

### High memory usage with Gunicorn

```
Each worker using 200+ MB instead of 50-100 MB
```

**Causes:**
- Too many libraries loaded
- Memory leaks in code
- Too many workers for available RAM

**Solutions:**
```bash
# Use fewer workers
gunicorn -w 2 -k uvicorn.workers.UvicornWorker app:app

# Use Uvicorn directly with fewer processes
gunicorn -w 1 -k uvicorn.workers.UvicornWorker app:app

# Limit memory per worker (Linux)
ulimit -m 100000  # 100 MB per process
```

---

## Systemd Service File

For automatic startup:

```ini
# /etc/systemd/system/fastapi-admin.service

[Unit]
Description=FastHTMX Admin with Gunicorn + Uvicorn
After=network.target

[Service]
Type=notify
User=fastapi
WorkingDirectory=/home/fastapi/hcf_admin
Environment="PATH=/home/fastapi/hcf_admin/venv/bin"
ExecStart=/home/fastapi/hcf_admin/venv/bin/gunicorn \
    -w 4 \
    -k uvicorn.workers.UvicornWorker \
    -b 127.0.0.1:8000 \
    app:app
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Enable:
```bash
sudo systemctl daemon-reload
sudo systemctl enable fastapi-admin
sudo systemctl start fastapi-admin
```

---

## Summary

| Aspect | Gunicorn | Uvicorn | Gunicorn + Uvicorn |
|--------|----------|---------|-------------------|
| **Throughput** | Good | Excellent | Excellent |
| **CPU cores** | Multiple ✓ | Single ❌ | Multiple ✓ |
| **Memory** | High | Low | Medium |
| **Async support** | No | Yes | Yes ✓ |
| **Crash resilience** | Good | Poor | Good ✓ |
| **Production ready** | Yes | Yes | Best ✓ |
| **Recommended for** | Old sync code | Dev/testing | FastAPI production |

**Recommendation for FastHTMX Admin:** Use Gunicorn + 4 Uvicorn workers. This is the industry standard for production FastAPI deployments and provides the best balance of performance, reliability, and resource efficiency.

---

## References

- [Gunicorn Documentation](https://gunicorn.org/)
- [Uvicorn Documentation](https://www.uvicorn.org/)
- [FastAPI Deployment Guide](https://fastapi.tiangolo.com/deployment/)
- [WSGI vs ASGI](https://www.fullstackpython.com/wsgi-servers.html)
- [Python GIL Explained](https://realpython.com/python-gil/)
