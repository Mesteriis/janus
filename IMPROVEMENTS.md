# Примеры улучшений кода

## 1. Безопасная аутентификация

### Текущая реализация (❌):

```python
# dashboard/backend/auth.py
def check_password(candidate: str | None) -> bool:
    if not candidate:
        return False
    return candidate == get_password()  # Plaintext comparison!
```

### Улучшенная версия (✅):

```python
# dashboard/backend/auth.py
import bcrypt
from typing import Optional

def hash_password(password: str) -> str:
    """Hash password using bcrypt."""
    salt = bcrypt.gensalt(rounds=12)
    return bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')

def verify_password(password: str, hashed: str) -> bool:
    """Verify password against bcrypt hash."""
    try:
        return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))
    except Exception:
        return False

def set_password(value: str | None) -> None:
    """Set password with hashing."""
    path = settings.AUTH_PASSWORD_FILE
    if value:
        hashed = hash_password(value.strip())
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(hashed, encoding="utf-8")
        _cache["mtime"] = None
        _cache["value"] = hashed
    else:
        # Disable auth
        if path.exists():
            path.unlink()
        _cache["mtime"] = None
        _cache["value"] = ""

def check_password(candidate: str | None) -> bool:
    """Check password against stored hash."""
    if not candidate:
        return False
    stored_hash = get_password()
    if not stored_hash:
        return False
    return verify_password(candidate, stored_hash)
```

### Обновить зависимости:

```toml
# pyproject.toml
dependencies = [
    # ...existing...
    "bcrypt>=4.1.2",
]
```

---

## 2. Session-based аутентификация

### Улучшенная версия с JWT:

```python
# dashboard/backend/auth_jwt.py
from datetime import datetime, timedelta
import jwt
from typing import Optional

SECRET_KEY = settings.JWT_SECRET_KEY  # Add to settings
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Create JWT access token."""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def verify_token(token: str) -> Optional[dict]:
    """Verify and decode JWT token."""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        return None
    except jwt.JWTError:
        return None
```

### Обновленный login endpoint:

```python
# dashboard/backend/routers/auth.py
@router.post("/api/auth/login")
async def auth_login(request: Request):
    payload = await request.json()
    password = payload.get("password")
    
    if not auth_enabled():
        return {"enabled": False, "authorized": True}
    
    if not password or not check_password(password):
        raise HTTPException(status_code=401, detail="Invalid password")
    
    # Create JWT token
    access_token = create_access_token(
        data={"sub": "admin"},
        expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    
    response = JSONResponse({"status": "ok", "access_token": access_token})
    response.set_cookie(
        settings.AUTH_COOKIE_NAME,
        access_token,
        httponly=True,
        samesite="lax",
        max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60
    )
    return response
```

### Обновленный middleware:

```python
# dashboard/backend/core/middleware.py
class AuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if not auth_enabled():
            return await call_next(request)

        path = request.url.path
        if path == "/" or path.startswith("/static") or path.startswith("/api/auth"):
            return await call_next(request)

        token = request.cookies.get(settings.AUTH_COOKIE_NAME) or \
                request.headers.get("Authorization", "").replace("Bearer ", "")
        
        if not token:
            return JSONResponse({"detail": "Unauthorized"}, status_code=401)
        
        # Verify JWT token
        payload = verify_token(token)
        if not payload:
            return JSONResponse({"detail": "Invalid or expired token"}, status_code=401)
        
        request.state.user = payload.get("sub")
        return await call_next(request)
```

---

## 3. Rate Limiting

### Добавить slowapi:

```toml
# pyproject.toml
dependencies = [
    # ...existing...
    "slowapi>=0.1.9",
]
```

### Настроить rate limiter:

```python
# dashboard/backend/main.py
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

def create_app() -> FastAPI:
    configure_logging()
    
    limiter = Limiter(key_func=get_remote_address, default_limits=["100/minute"])
    app = FastAPI(lifespan=lifespan)
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    
    app.add_middleware(AuthMiddleware)
    app.add_middleware(CorrelationIdMiddleware)
    app.include_router(router)
    # ...rest...
```

### Применить к критичным endpoints:

```python
# dashboard/backend/routers/auth.py
from slowapi import Limiter
from slowapi.util import get_remote_address
from fastapi import Request

limiter = Limiter(key_func=get_remote_address)

@router.post("/api/auth/login")
@limiter.limit("5/minute")  # Maximum 5 login attempts per minute
async def auth_login(request: Request):
    # ...existing code...
```

---

## 4. Atomic File Writes

### Текущая реализация (❌):

```python
# dashboard/backend/storage.py
def save_routes(data: Dict) -> None:
    with open(settings.ROUTES_FILE, "w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2, ensure_ascii=False)
        handle.write("\n")
```

### Улучшенная версия (✅):

```python
# dashboard/backend/storage.py
import tempfile
import shutil
import fcntl
from pathlib import Path
from contextlib import contextmanager

@contextmanager
def file_lock(path: Path):
    """Context manager for file locking."""
    lock_path = path.with_suffix('.lock')
    try:
        with open(lock_path, 'w') as lock_file:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
            yield
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
    finally:
        if lock_path.exists():
            lock_path.unlink()

def save_routes(data: Dict) -> None:
    """Save routes atomically with file locking."""
    ensure_parent(settings.ROUTES_FILE)
    
    with file_lock(settings.ROUTES_FILE):
        # Write to temporary file first
        with tempfile.NamedTemporaryFile(
            mode='w',
            encoding='utf-8',
            dir=settings.ROUTES_FILE.parent,
            delete=False
        ) as tmp_file:
            json.dump(data, tmp_file, indent=2, ensure_ascii=False)
            tmp_file.write("\n")
            tmp_file.flush()
            os.fsync(tmp_file.fileno())  # Force write to disk
            temp_path = tmp_file.name
        
        # Atomic rename
        shutil.move(temp_path, settings.ROUTES_FILE)

def load_routes() -> Dict:
    """Load routes with file locking."""
    try:
        with file_lock(settings.ROUTES_FILE):
            with open(settings.ROUTES_FILE, "r", encoding="utf-8") as handle:
                data = json.load(handle)
    except FileNotFoundError:
        data = {}
    
    if "routes" not in data:
        data["routes"] = []
    if "plugins" not in data:
        data["plugins"] = default_plugins()
    if "l4_routes" not in data:
        data["l4_routes"] = []
    return data
```

---

## 5. Config Versioning & Backup

```python
# dashboard/backend/storage.py
import time
from pathlib import Path
from typing import List

def get_backup_dir() -> Path:
    """Get backup directory path."""
    backup_dir = settings.ROUTES_FILE.parent / "backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    return backup_dir

def create_backup(data: Dict) -> Path:
    """Create timestamped backup of routes."""
    backup_dir = get_backup_dir()
    timestamp = int(time.time())
    backup_path = backup_dir / f"routes.{timestamp}.json"
    
    with open(backup_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")
    
    # Clean old backups (keep last 50)
    cleanup_old_backups(max_backups=50)
    
    return backup_path

def cleanup_old_backups(max_backups: int = 50) -> None:
    """Remove old backup files, keeping only the most recent."""
    backup_dir = get_backup_dir()
    backups = sorted(backup_dir.glob("routes.*.json"), key=lambda p: p.stat().st_mtime)
    
    if len(backups) > max_backups:
        for old_backup in backups[:-max_backups]:
            old_backup.unlink()

def list_backups() -> List[dict]:
    """List all available backups."""
    backup_dir = get_backup_dir()
    backups = []
    
    for backup_path in sorted(backup_dir.glob("routes.*.json"), reverse=True):
        stat = backup_path.stat()
        timestamp = int(backup_path.stem.split(".")[-1])
        backups.append({
            "path": str(backup_path),
            "timestamp": timestamp,
            "size": stat.st_size,
            "created_at": datetime.fromtimestamp(timestamp).isoformat()
        })
    
    return backups

def restore_backup(timestamp: int) -> Dict:
    """Restore routes from backup."""
    backup_dir = get_backup_dir()
    backup_path = backup_dir / f"routes.{timestamp}.json"
    
    if not backup_path.exists():
        raise ValueError(f"Backup not found: {timestamp}")
    
    with open(backup_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    # Create backup of current state before restore
    current_data = load_routes()
    create_backup(current_data)
    
    # Restore
    save_routes(data)
    return data

def save_routes_with_backup(data: Dict) -> None:
    """Save routes and create backup."""
    # Create backup of current state
    if settings.ROUTES_FILE.exists():
        try:
            current_data = load_routes()
            create_backup(current_data)
        except Exception as e:
            logger.warning(f"Failed to create backup: {e}")
    
    # Save new data
    save_routes(data)
```

### Новые endpoints для backup management:

```python
# dashboard/backend/routers/backup.py
from fastapi import APIRouter, HTTPException
from ..storage import list_backups, restore_backup

router = APIRouter(tags=["Backup"])

@router.get("/api/backups")
def api_list_backups():
    """List all available backups."""
    return {"backups": list_backups()}

@router.post("/api/backups/{timestamp}/restore")
async def api_restore_backup(timestamp: int):
    """Restore configuration from backup."""
    try:
        data = restore_backup(timestamp)
        return {"status": "restored", "timestamp": timestamp}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
```

---

## 6. Health Check Endpoint

```python
# dashboard/backend/routers/health.py
from fastapi import APIRouter
from fastapi.responses import JSONResponse
import subprocess
import docker
from .. import settings

router = APIRouter(tags=["Health"])

def check_caddy() -> dict:
    """Check if Caddy is reachable."""
    try:
        result = subprocess.run(
            [settings.CADDY_BIN, "version"],
            capture_output=True,
            timeout=5
        )
        return {
            "status": "ok" if result.returncode == 0 else "error",
            "version": result.stdout.decode().strip() if result.returncode == 0 else None
        }
    except Exception as e:
        return {"status": "error", "error": str(e)}

def check_docker() -> dict:
    """Check Docker connection."""
    try:
        client = docker.from_env()
        client.ping()
        return {"status": "ok"}
    except Exception as e:
        return {"status": "error", "error": str(e)}

def check_cloudflare() -> dict:
    """Check Cloudflare API configuration."""
    if not settings.CLOUDFLARE_API_TOKEN:
        return {"status": "not_configured"}
    
    from ..cloudflare.hostnames import cf_configured
    return {"status": "ok" if cf_configured() else "error"}

def check_disk_space() -> dict:
    """Check available disk space."""
    import shutil
    total, used, free = shutil.disk_usage("/")
    free_gb = free // (2**30)
    
    return {
        "status": "ok" if free_gb > 1 else "warning",
        "free_gb": free_gb,
        "total_gb": total // (2**30),
        "used_percent": (used / total) * 100
    }

@router.get("/health")
async def health_check():
    """Comprehensive health check."""
    checks = {
        "caddy": check_caddy(),
        "docker": check_docker(),
        "cloudflare": check_cloudflare(),
        "disk": check_disk_space(),
    }
    
    # Overall status
    critical_checks = ["caddy", "docker", "disk"]
    has_critical_error = any(
        checks[name]["status"] == "error" 
        for name in critical_checks
    )
    
    status_code = 503 if has_critical_error else 200
    overall_status = "unhealthy" if has_critical_error else "healthy"
    
    return JSONResponse(
        {
            "status": overall_status,
            "timestamp": datetime.utcnow().isoformat(),
            "checks": checks
        },
        status_code=status_code
    )

@router.get("/ready")
async def readiness_check():
    """Simple readiness check for k8s."""
    return {"status": "ready"}

@router.get("/live")
async def liveness_check():
    """Simple liveness check for k8s."""
    return {"status": "alive"}
```

---

## 7. Structured Error Responses

```python
# dashboard/backend/errors.py
from typing import Optional, Any
from pydantic import BaseModel
from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError

class ErrorDetail(BaseModel):
    code: str
    message: str
    field: Optional[str] = None
    details: Optional[dict] = None

class ErrorResponse(BaseModel):
    error: ErrorDetail
    request_id: Optional[str] = None

def create_error_response(
    code: str,
    message: str,
    status_code: int = 400,
    field: Optional[str] = None,
    details: Optional[dict] = None,
    request_id: Optional[str] = None
) -> JSONResponse:
    """Create standardized error response."""
    error = ErrorResponse(
        error=ErrorDetail(
            code=code,
            message=message,
            field=field,
            details=details
        ),
        request_id=request_id
    )
    return JSONResponse(
        status_code=status_code,
        content=error.dict(exclude_none=True)
    )

# Exception handlers
async def http_exception_handler(request: Request, exc: HTTPException):
    """Handle HTTPException with structured format."""
    return create_error_response(
        code="HTTP_ERROR",
        message=exc.detail,
        status_code=exc.status_code,
        request_id=getattr(request.state, "correlation_id", None)
    )

async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Handle validation errors with structured format."""
    errors = exc.errors()
    first_error = errors[0] if errors else {}
    
    return create_error_response(
        code="VALIDATION_ERROR",
        message=first_error.get("msg", "Validation error"),
        status_code=422,
        field=".".join(str(loc) for loc in first_error.get("loc", [])),
        details={"errors": errors},
        request_id=getattr(request.state, "correlation_id", None)
    )

async def service_error_handler(request: Request, exc: Exception):
    """Handle ServiceError with structured format."""
    from .services.errors import ServiceError
    
    if isinstance(exc, ServiceError):
        return create_error_response(
            code="SERVICE_ERROR",
            message=exc.detail,
            status_code=exc.status_code,
            request_id=getattr(request.state, "correlation_id", None)
        )
    
    # Unexpected error
    return create_error_response(
        code="INTERNAL_ERROR",
        message="Internal server error",
        status_code=500,
        request_id=getattr(request.state, "correlation_id", None)
    )
```

### Register handlers:

```python
# dashboard/backend/main.py
from .errors import (
    http_exception_handler,
    validation_exception_handler,
    service_error_handler
)
from fastapi.exceptions import RequestValidationError

def create_app() -> FastAPI:
    # ...existing setup...
    
    # Register error handlers
    app.add_exception_handler(HTTPException, http_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(Exception, service_error_handler)
    
    return app
```

---

## 8. Background Tasks для Cloudflare Sync

```python
# dashboard/backend/services/background.py
from typing import Optional
import asyncio
from fastapi import BackgroundTasks
import logging

logger = logging.getLogger(__name__)

class SyncQueue:
    """Queue for Cloudflare sync operations with debouncing."""
    
    def __init__(self, debounce_seconds: float = 5.0):
        self.debounce_seconds = debounce_seconds
        self._pending_task: Optional[asyncio.Task] = None
        self._lock = asyncio.Lock()
    
    async def schedule_sync(self):
        """Schedule a sync operation with debouncing."""
        async with self._lock:
            # Cancel pending task if exists
            if self._pending_task and not self._pending_task.done():
                self._pending_task.cancel()
            
            # Schedule new task
            self._pending_task = asyncio.create_task(self._debounced_sync())
    
    async def _debounced_sync(self):
        """Execute sync after debounce delay."""
        try:
            await asyncio.sleep(self.debounce_seconds)
            logger.info("Starting debounced Cloudflare sync")
            
            from ..storage import load_routes
            from ..cloudflare.flow import sync_cloudflare_from_routes
            
            data = load_routes()
            result = await sync_cloudflare_from_routes(data)
            
            logger.info(f"Cloudflare sync completed: {result}")
        except asyncio.CancelledError:
            logger.info("Cloudflare sync cancelled (debounce)")
        except Exception as e:
            logger.error(f"Cloudflare sync failed: {e}", exc_info=True)

# Global queue instance
_sync_queue = SyncQueue()

async def schedule_cloudflare_sync():
    """Schedule Cloudflare sync with debouncing."""
    await _sync_queue.schedule_sync()
```

### Использование в routes:

```python
# dashboard/backend/services/routes.py
from .background import schedule_cloudflare_sync

async def create_route(validated: dict) -> dict:
    data = load_routes()
    if _domains_conflict(validated["domains"], data):
        raise ServiceError(409, "Route with same domains already exists")

    validated["id"] = str(uuid.uuid4())
    data.setdefault("routes", []).append(validated)
    save_routes(data)
    
    # Validate config synchronously
    write_and_validate_config(data)
    
    # Schedule CF sync in background
    await schedule_cloudflare_sync()
    
    return validated
```

---

## 9. Prometheus Metrics

```python
# dashboard/backend/metrics.py
from prometheus_client import Counter, Histogram, Gauge
import time

# Request metrics
REQUEST_COUNT = Counter(
    'http_requests_total',
    'Total HTTP requests',
    ['method', 'endpoint', 'status']
)

REQUEST_DURATION = Histogram(
    'http_request_duration_seconds',
    'HTTP request duration',
    ['method', 'endpoint']
)

# Business metrics
ROUTES_COUNT = Gauge(
    'caddy_routes_total',
    'Total number of Caddy routes'
)

CF_SYNC_COUNT = Counter(
    'cloudflare_sync_total',
    'Total Cloudflare sync operations',
    ['status']
)

CF_SYNC_DURATION = Histogram(
    'cloudflare_sync_duration_seconds',
    'Cloudflare sync duration'
)

def update_routes_gauge():
    """Update routes count metric."""
    from .storage import load_routes
    data = load_routes()
    ROUTES_COUNT.set(len(data.get("routes", [])))
```

### Middleware для metrics:

```python
# dashboard/backend/core/middleware.py
from ..metrics import REQUEST_COUNT, REQUEST_DURATION

class MetricsMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        start_time = time.time()
        
        response = await call_next(request)
        
        duration = time.time() - start_time
        
        REQUEST_COUNT.labels(
            method=request.method,
            endpoint=request.url.path,
            status=response.status_code
        ).inc()
        
        REQUEST_DURATION.labels(
            method=request.method,
            endpoint=request.url.path
        ).observe(duration)
        
        return response
```

### Metrics endpoint:

```python
# dashboard/backend/routers/metrics.py
from fastapi import APIRouter
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
from fastapi.responses import Response

router = APIRouter(tags=["Metrics"])

@router.get("/metrics")
async def metrics():
    """Prometheus metrics endpoint."""
    from ..metrics import update_routes_gauge
    
    # Update gauges
    update_routes_gauge()
    
    return Response(
        content=generate_latest(),
        media_type=CONTENT_TYPE_LATEST
    )
```

---

## 10. API Versioning

```python
# dashboard/backend/api.py
from fastapi import APIRouter

# API v1
v1_router = APIRouter(prefix="/api/v1")

# Include all routers under v1
from .routers import routers
for r in routers:
    v1_router.include_router(r, prefix="")

# Legacy support (redirect to v1)
legacy_router = APIRouter(prefix="/api", deprecated=True)
for r in routers:
    legacy_router.include_router(r, prefix="")

# Export both
router = APIRouter()
router.include_router(v1_router, tags=["v1"])
router.include_router(legacy_router, tags=["legacy"])
```

### Settings для versioning:

```python
# dashboard/backend/core/config.py
class Settings(BaseSettings):
    # ...existing...
    api_version: str = "1.0.0"
    api_versions_supported: list[str] = ["v1"]
```

---

## Итоговый чеклист изменений

### Критично (Week 1-2):
- [ ] Добавить bcrypt для паролей
- [ ] Реализовать JWT аутентификацию
- [ ] Добавить rate limiting (slowapi)
- [ ] Реализовать atomic file writes
- [ ] Добавить file locking
- [ ] Создать health check endpoints
- [ ] Реализовать config backup/restore

### Важно (Week 3-4):
- [ ] Structured error responses
- [ ] Background tasks для CF sync
- [ ] Prometheus metrics
- [ ] API versioning
- [ ] Улучшить логирование (не логировать пароли)
- [ ] Добавить CORS middleware
- [ ] Retry logic для CF API

### Nice-to-have (Week 5+):
- [ ] WebSocket для real-time updates
- [ ] Grafana dashboards
- [ ] E2E tests
- [ ] Docker secrets
- [ ] Performance optimization

---

**Приоритет реализации:** Начинать с критичных изменений, особенно безопасности!
