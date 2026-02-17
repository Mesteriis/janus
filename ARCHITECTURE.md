# Архитектура и Flow диаграммы

## 1. Общая архитектура системы

```
┌─────────────────────────────────────────────────────────────────┐
│                          User / Browser                         │
└────────────────┬────────────────────────────────────────────────┘
                 │ HTTPS
                 ↓
┌─────────────────────────────────────────────────────────────────┐
│                     Cloudflare Tunnel                            │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │ Catch-all rule: *.example.com → http://caddy:80         │   │
│  │ Exceptions: ssh.example.com → ssh://host:22              │   │
│  └──────────────────────────────────────────────────────────┘   │
└────────────────┬────────────────────────────────────────────────┘
                 │
                 ↓
┌─────────────────────────────────────────────────────────────────┐
│                         Caddy (Reverse Proxy)                    │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │ Routes: domains → upstreams                               │   │
│  │ TLS: Auto ACME (Let's Encrypt / Cloudflare DNS)          │   │
│  │ Plugins: rate-limit, cache, geoip, security               │   │
│  └──────────────────────────────────────────────────────────┘   │
└────┬────────────────────────────────────┬────────────────────────┘
     │                                    │
     │ Routes traffic to                  │ Managed by
     ↓                                    ↓
┌─────────────────┐              ┌──────────────────────────────┐
│   Upstream      │              │   Dashboard (FastAPI)        │
│   Services      │              │   Port: 8090                 │
│                 │              │                              │
│ • App1:8001     │              │ • API: routes, CF, auth      │
│ • App2:8002     │              │ • Frontend: Vue 3            │
│ • DB:5432       │              │ • Storage: JSON files        │
│ • etc.          │              │ • Docker control             │
└─────────────────┘              └───────┬──────────────────────┘
                                         │
                                         │ Manages config
                                         ↓
                          ┌──────────────────────────────┐
                          │   Configuration Files         │
                          │                              │
                          │ • routes.json (source)       │
                          │ • config.json5 (generated)   │
                          │ • hostnames.json (CF)        │
                          └──────────────────────────────┘
```

---

## 2. Компонентная архитектура Dashboard

```
┌─────────────────────────────────────────────────────────────────┐
│                        FastAPI Application                       │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │                      Middlewares                          │   │
│  │  • CorrelationIdMiddleware (tracing)                      │   │
│  │  • AuthMiddleware (authentication)                        │   │
│  │  • ExceptionHandler (error handling)                      │   │
│  └──────────────────┬───────────────────────────────────────┘   │
│                     │                                            │
│  ┌──────────────────▼───────────────────────────────────────┐   │
│  │                      Routers (API Layer)                  │   │
│  │  • /api/auth       - Authentication                       │   │
│  │  • /api/routes     - CRUD for routes                      │   │
│  │  • /api/raw/*      - Raw JSON/config editing              │   │
│  │  • /api/cf/*       - Cloudflare operations                │   │
│  │  • /api/l4routes   - Layer 4 routes                       │   │
│  │  • /api/plugins    - Plugin config                        │   │
│  │  • /api/cf/docker/* - Tunnel management                   │   │
│  └──────────────────┬───────────────────────────────────────┘   │
│                     │                                            │
│  ┌──────────────────▼───────────────────────────────────────┐   │
│  │                    Services (Business Logic)              │   │
│  │  • routes_service    - Route management                   │   │
│  │  • cloudflare_service - CF API integration                │   │
│  │  • tunnel_service    - Docker tunnel control              │   │
│  │  • provisioning      - Config generation & validation     │   │
│  │  • raw_service       - Raw config editing                 │   │
│  │  • plugins_service   - Plugin management                  │   │
│  │  • l4_service        - L4 routes                          │   │
│  └──────────────────┬───────────────────────────────────────┘   │
│                     │                                            │
│  ┌──────────────────▼───────────────────────────────────────┐   │
│  │                  Storage & External APIs                  │   │
│  │  • storage.py       - JSON file operations                │   │
│  │  • caddy.py         - Caddy config generation             │   │
│  │  • docker_ctl.py    - Docker SDK                          │   │
│  │  • cloudflare/*     - Cloudflare SDK wrapper              │   │
│  └───────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│                      External Dependencies                       │
│  • Docker API       - Container management                       │
│  • Cloudflare API   - Tunnel configuration                       │
│  • Caddy binary     - Config validation                          │
│  • File system      - Persistent storage                         │
└─────────────────────────────────────────────────────────────────┘
```

---

## 3. Route Creation Flow (детально)

```
┌─────────────┐
│ User/Client │
└──────┬──────┘
       │
       │ POST /api/routes
       │ {domains, upstreams, ...}
       ↓
┌──────────────────────────────────────────────────────────┐
│ 1. Router (routers/routes.py)                            │
│    • Parse request body                                   │
│    • Normalize headers/domains                            │
│    • Call validation.validate_route_payload()             │
└──────┬───────────────────────────────────────────────────┘
       │
       ↓
┌──────────────────────────────────────────────────────────┐
│ 2. Validation (validation.py)                            │
│    ✓ Domains match regex                                 │
│    ✓ Upstreams have valid scheme/host/port               │
│    ✓ Headers properly formatted                          │
│    ✓ Rate limits valid                                   │
└──────┬───────────────────────────────────────────────────┘
       │
       ↓
┌──────────────────────────────────────────────────────────┐
│ 3. Service (services/routes.py)                          │
│    • Check domain conflicts: _domains_conflict()          │
│    • Generate UUID for route                             │
│    • Add to routes list                                  │
│    • Call storage.save_routes(data)                      │
└──────┬───────────────────────────────────────────────────┘
       │
       ↓
┌──────────────────────────────────────────────────────────┐
│ 4. Storage (storage.py)                                  │
│    • Serialize to JSON                                   │
│    • Write to routes.json                                │
│    ⚠️  TODO: Add atomic writes + file locking            │
└──────┬───────────────────────────────────────────────────┘
       │
       ↓
┌──────────────────────────────────────────────────────────┐
│ 5. Provisioning (services/provisioning.py)               │
│    • Generate Caddy config: write_caddy_config()          │
│    • Validate with caddy binary: subprocess.run()         │
│    • If error → rollback config                          │
│    • If trigger in [create, replace, raw] → continue      │
└──────┬───────────────────────────────────────────────────┘
       │
       ↓ if cf_configured()
┌──────────────────────────────────────────────────────────┐
│ 6. Cloudflare Sync (cloudflare/flow.py)                 │
│    • Extract domains from routes                         │
│    • Detect SSH exceptions (port 22)                     │
│    • Group by zones                                      │
│    • Call cf.provision_all_to_caddy()                    │
│    • Update tunnel config via CF API                     │
└──────┬───────────────────────────────────────────────────┘
       │
       ↓
┌──────────────────────────────────────────────────────────┐
│ 7. Tunnel Management (services/tunnel.py)                │
│    • Check tunnel status                                 │
│    • If not running → start via Docker                   │
│    • docker.containers.run(cloudflared, ...)             │
└──────┬───────────────────────────────────────────────────┘
       │
       │ Success
       ↓
┌──────────────────────────────────────────────────────────┐
│ 8. Response                                              │
│    • Return created route with ID                        │
│    • HTTP 201 Created                                    │
│    {id, domains, upstreams, enabled, ...}                │
└──────────────────────────────────────────────────────────┘
```

---

## 4. Cloudflare Sync Flow (подробно)

```
┌────────────────┐
│ routes.json    │
└────────┬───────┘
         │
         ↓
┌─────────────────────────────────────────────────────────┐
│ sync_cloudflare_from_routes()                           │
│                                                          │
│ Step 1: Collect all domains                             │
│   for route in routes:                                  │
│     domains.add(route.domains)                          │
│   → Result: {app.example.com, api.example.com, ...}     │
└────────┬────────────────────────────────────────────────┘
         │
         ↓
┌─────────────────────────────────────────────────────────┐
│ Step 2: Extract SSH exceptions                          │
│   for route in routes:                                  │
│     if upstream.port == 22:                             │
│       exceptions[domain] = CNAME/A record               │
│   → Result: {ssh.example.com: "1.2.3.4"}                │
└────────┬────────────────────────────────────────────────┘
         │
         ↓
┌─────────────────────────────────────────────────────────┐
│ Step 3: Initialize Cloudflare client                    │
│   cf = CloudFlare(state_file)                           │
│   if token:                                             │
│     cf.set_token(token, persist=True)                   │
│   if not cf.ready:                                      │
│     return skipped                                      │
└────────┬────────────────────────────────────────────────┘
         │
         ↓
┌─────────────────────────────────────────────────────────┐
│ Step 4: Resolve zones for each domain                   │
│   for domain in domains:                                │
│     zone_info = cf.resolve_zone_for_hostname(domain)    │
│     zones[zone].add(domain)                             │
│   → Result: {                                           │
│       "example.com": {                                  │
│         domains: [app.example.com, api.example.com],    │
│         exceptions: [{ssh.example.com: "1.2.3.4"}]      │
│       }                                                 │
│     }                                                   │
└────────┬────────────────────────────────────────────────┘
         │
         ↓
┌─────────────────────────────────────────────────────────┐
│ Step 5: Provision each zone                             │
│   for zone, info in zones.items():                      │
│     cf.provision_all_to_caddy(                          │
│       zone=zone,                                        │
│       caddy_url="http://caddy:80",                      │
│       dns_exceptions=info.exceptions                    │
│     )                                                   │
│                                                         │
│   This does:                                            │
│   • Get tunnel ID for zone                              │
│   • Build config with:                                  │
│     - Catch-all: * → http://caddy:80                    │
│     - Exceptions: ssh.example.com → direct              │
│   • Update tunnel via CF API                            │
│   • Create DNS records if needed                        │
└────────┬────────────────────────────────────────────────┘
         │
         ↓
┌─────────────────────────────────────────────────────────┐
│ Result                                                  │
│ {                                                       │
│   status: "ok",                                         │
│   zones: [...],                                         │
│   domains: 15                                           │
│ }                                                       │
└─────────────────────────────────────────────────────────┘
```

---

## 5. Authentication Flow

### Current (⚠️ INSECURE):

```
┌──────────┐
│  User    │
└────┬─────┘
     │
     │ POST /api/auth/login
     │ {password: "secret123"}
     ↓
┌─────────────────────────────────────────────────┐
│ auth_login()                                    │
│   plaintext_password = payload.password         │
│   stored_password = read_from_file()            │
│   if plaintext_password == stored_password:  ⚠️  │
│     set_cookie("janus_auth", plaintext_password)│ ⚠️
└────┬────────────────────────────────────────────┘
     │
     │ Cookie: janus_auth=secret123  ⚠️
     ↓
┌─────────────────────────────────────────────────┐
│ Subsequent requests                             │
│   AuthMiddleware                                │
│     cookie_value = request.cookies["janus_auth"]│
│     if cookie_value == stored_password:      ⚠️  │
│       allow()                                   │
└─────────────────────────────────────────────────┘

Problems:
⚠️  Password stored in plaintext
⚠️  Cookie contains password in plaintext
⚠️  No session management
⚠️  No rate limiting
```

### Recommended (✅ SECURE):

```
┌──────────┐
│  User    │
└────┬─────┘
     │
     │ POST /api/auth/login
     │ {password: "secret123"}
     ↓
┌─────────────────────────────────────────────────┐
│ auth_login()                                    │
│   plaintext = payload.password                  │
│   stored_hash = read_bcrypt_hash_from_file()    │
│   if bcrypt.verify(plaintext, stored_hash): ✅   │
│     jwt_token = create_jwt({sub: "admin"})      │
│     set_cookie("janus_auth", jwt_token) ✅       │
└────┬────────────────────────────────────────────┘
     │
     │ Cookie: janus_auth=eyJhbG... (JWT) ✅
     ↓
┌─────────────────────────────────────────────────┐
│ Subsequent requests                             │
│   AuthMiddleware                                │
│     jwt_token = request.cookies["janus_auth"]   │
│     payload = jwt.verify(jwt_token)         ✅   │
│     if payload and not expired:                 │
│       request.state.user = payload.sub          │
│       allow()                                   │
└─────────────────────────────────────────────────┘

Benefits:
✅ Password never transmitted after login
✅ Token has expiration
✅ Token can be revoked
✅ Stateless authentication
✅ Can add claims (roles, permissions)
```

---

## 6. Data Flow (Route → Caddy → CF)

```
┌──────────────────────────────────────────────────────────────┐
│                      routes.json (Source of Truth)           │
│ {                                                            │
│   "routes": [                                                │
│     {                                                        │
│       "id": "uuid",                                          │
│       "domains": ["app.example.com"],                        │
│       "upstreams": [{"scheme": "http", "host": "app", ...}], │
│       "enabled": true                                        │
│     }                                                        │
│   ]                                                          │
│ }                                                            │
└────┬─────────────────────────────────────────────────────────┘
     │
     │ caddy.render_caddy_config()
     ↓
┌──────────────────────────────────────────────────────────────┐
│                    config.json5 (Generated)                  │
│ {                                                            │
│   "apps": {                                                  │
│     "http": {                                                │
│       "servers": {                                           │
│         "srv0": {                                            │
│           "routes": [                                        │
│             {                                                │
│               "match": [{"host": ["app.example.com"]}],      │
│               "handle": [{                                   │
│                 "handler": "reverse_proxy",                  │
│                 "upstreams": [{"dial": "app:8080"}]          │
│               }]                                             │
│             }                                                │
│           ]                                                  │
│         }                                                    │
│       }                                                      │
│     },                                                       │
│     "tls": { /* auto ACME */ }                               │
│   }                                                          │
│ }                                                            │
└────┬─────────────────────────────────────────────────────────┘
     │
     │ subprocess: caddy validate
     ↓
┌──────────────────────────────────────────────────────────────┐
│                    Caddy Validation                          │
│   caddy validate --config config.json5 --adapter json5       │
│   ✓ Syntax OK                                                │
│   ✓ No conflicts                                             │
└────┬─────────────────────────────────────────────────────────┘
     │
     │ If valid → reload Caddy (watches file)
     │
     ↓
┌──────────────────────────────────────────────────────────────┐
│               Caddy Reverse Proxy (Running)                  │
│   Listens on :80, :443                                       │
│   Routes traffic per config.json5                            │
│   Auto TLS via ACME                                          │
└──────────────────────────────────────────────────────────────┘
```

Parallel flow для Cloudflare:

```
routes.json
     │
     │ sync_cloudflare_from_routes()
     ↓
┌──────────────────────────────────────────────────────────────┐
│              Cloudflare Tunnel Config (API)                  │
│ {                                                            │
│   "ingress": [                                               │
│     {                                                        │
│       "hostname": "ssh.example.com",                         │
│       "service": "ssh://host:22"                             │
│     },                                                       │
│     {                                                        │
│       "service": "http://caddy:80"  ← Catch-all              │
│     }                                                        │
│   ]                                                          │
│ }                                                            │
└────┬─────────────────────────────────────────────────────────┘
     │
     │ cf.update_tunnel_config()
     ↓
┌──────────────────────────────────────────────────────────────┐
│         Cloudflared Container (Running)                      │
│   Pulls config from Cloudflare                               │
│   Routes traffic:                                            │
│     • Most traffic → Caddy                                   │
│     • SSH → direct to host                                   │
└──────────────────────────────────────────────────────────────┘
```

---

## 7. Error Handling & Rollback Flow

```
┌──────────────┐
│ Update route │
└──────┬───────┘
       │
       ↓
┌─────────────────────────────────────────────┐
│ 1. Backup current config                    │
│    old_content = read_file(config.json5)    │
└──────┬──────────────────────────────────────┘
       │
       ↓
┌─────────────────────────────────────────────┐
│ 2. Save new routes.json                     │
│    save_routes(new_data)                    │
└──────┬──────────────────────────────────────┘
       │
       ↓
┌─────────────────────────────────────────────┐
│ 3. Generate new config.json5                │
│    write_caddy_config(new_data)             │
└──────┬──────────────────────────────────────┘
       │
       ↓
┌─────────────────────────────────────────────┐
│ 4. Validate with Caddy                      │
│    caddy validate --config config.json5     │
└──────┬──────────────────────────────────────┘
       │
       ├─ Success ──────────────────────┐
       │                                │
       ↓                                │
┌──────────────────────────┐            │
│ 5a. Update Cloudflare    │            │
│     (if configured)      │            │
│     May fail...          │            │
└──────┬───────────────────┘            │
       │                                │
       ↓                                │
       ✓ Complete                       │
                                        │
       Error ←─────────────────────────┘
       │
       ↓
┌─────────────────────────────────────────────┐
│ Rollback                                    │
│   restore_file(config.json5, old_content)   │
│   log_error(correlation_id)                 │
│   return 400 with error details             │
└─────────────────────────────────────────────┘

⚠️  Current problem:
   If Cloudflare API fails, routes.json is NOT rolled back!
   
✅ Solution:
   Separate "save config" and "apply to CF" into different operations
   Add manual sync trigger
```

---

## 8. Concurrency Issues (Current)

```
Request A                      Request B
   │                              │
   ↓                              │
load_routes()                     │
   │                              │
   ├─ data = {...}                │
   │                              ↓
   │                          load_routes()
   │                              │
   ↓                              ├─ data = {...}
modify data                       │
   │                              ↓
   ↓                          modify data
save_routes(data)                 │
   │                              ↓
   ├─ Write to disk           save_routes(data)
   ↓                              │
   ✓ Done                         ├─ Write to disk
                                  ↓
                                  ✓ Done
                                  
⚠️  Result: Request B overwrites Request A!
    Race condition, data loss possible.

✅ Solution: Add file locking
    
Request A                      Request B
   │                              │
   ↓                              │
acquire_lock()                    │
   │                              ↓
   ├─ LOCKED                  acquire_lock()
   │                              │
   ↓                              ├─ WAITING...
load_routes()                     │
modify data                       │
save_routes(data)                 │
   │                              │
   ↓                              │
release_lock()                    │
   │                              ↓
   ✓ Done                     acquire_lock()
                                  │
                                  ├─ LOCKED
                                  ↓
                              load_routes()
                              modify data
                              save_routes(data)
                              release_lock()
                                  ↓
                                  ✓ Done
```

---

## 9. Recommended Architecture (Future)

```
┌─────────────────────────────────────────────────────────────┐
│                        API Gateway                           │
│  • Rate limiting                                             │
│  • Authentication                                            │
│  • CORS                                                      │
└────┬────────────────────────────────────────────────────────┘
     │
     ↓
┌─────────────────────────────────────────────────────────────┐
│                     FastAPI Application                      │
│  • API endpoints (read-only)                                 │
│  • Websocket (real-time updates)                             │
└────┬───────────────────────┬────────────────────────────────┘
     │                       │
     │ Writes                │ Reads
     ↓                       ↓
┌──────────────┐      ┌─────────────────┐
│ Message Queue│      │  Read Cache     │
│ (Redis/RMQ)  │      │  (Redis)        │
└──────┬───────┘      └─────────────────┘
       │
       │ async
       ↓
┌─────────────────────────────────────────────────────────────┐
│                    Background Workers                        │
│  • Config generation                                         │
│  • Cloudflare sync (with retry)                              │
│  • Validation                                                │
└────┬────────────────────────────────────────────────────────┘
     │
     ↓
┌─────────────────────────────────────────────────────────────┐
│                    Persistent Storage                        │
│  • PostgreSQL (config + audit log)                           │
│  • S3 (config backups)                                       │
└─────────────────────────────────────────────────────────────┘

Benefits:
✅ No race conditions (queue)
✅ Async operations don't block API
✅ Retry logic built-in
✅ Scalable (multiple workers)
✅ Audit trail (PostgreSQL)
✅ Backup history (S3)
```

---

## Легенда

```
┌─────┐
│ Box │  - Компонент/процесс
└─────┘

   │
   ↓      - Односторонний поток данных

   ↕      - Двусторонняя коммуникация

   ✅     - Правильная реализация

   ⚠️      - Проблема/риск

   ❌     - Критическая проблема
```
