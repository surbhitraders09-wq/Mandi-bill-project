# Phase 0 — Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. (This repo has no git history; commit steps are omitted unless the user requests git.)

**Goal:** Finish base verification, then stand up the modern ERP foundation on the rebuilt FastAPI + React base: design tokens, component library, ERP shell, auth + RBAC, cmd+K global search, smart tables, audit log, and wired IA pages.

**Architecture:** Backend gains `auth` (users/roles/permissions), `audit` (activity_logs), and `search` domain modules with JWT + bcrypt + RBAC dependencies, seeded admin/roles. Frontend is a fresh Vite+React+TS+Tailwind 3.4 app: token-driven design system, hand-rolled component library, ERP shell (TopBar/Sidebar/StatusBar), Zustand auth + theme stores, TanStack Query, TanStack Table SmartTable, cmdk command palette. Existing `/api/automation/*`, `/api/bills`, `/api/settings`, `/api/logs` routes are preserved unchanged.

**Tech Stack:** FastAPI + SQLAlchemy async + aiosqlite (dev) · React 18 + Vite + TS · Tailwind 3.4 (locked) · Zustand · TanStack Query + Table · Radix primitives · cmdk · Recharts · PyJWT · bcrypt · pytest (backend) · Vitest (frontend smoke)

---

## Current State (verified at plan time)

- `backend/` rebuilt: FastAPI port 8000, 16 routes, 6 page objects, state machine, Fernet credential encryption, seeded settings (trader ID from env / placeholder, hammali 12.05 / cash threshold 200000), SQLite `mandi.db`. Server currently **down**; `/api/settings` response-model fix applied but unverified.
- `frontend/` not yet created.
- Python venv at `backend/venv`.

---

## Task 1: Finish base verification

**Files:**
- Modify: none (run only)
- Verify: `backend/app/api/routes/settings.py` (fix already applied)

- [ ] **Step 1: Start the backend**

```bash
cd /home/hereyashhh/mandi-automation-assistant/backend
nohup ./venv/bin/python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 > /tmp/backend-server.log 2>&1 &
sleep 4
curl -s http://localhost:8000/api/health
```

Expected: `{"status":"ok","version":"1.0.0"}`

- [ ] **Step 2: Verify settings endpoint (the pending fix)**

```bash
curl -s http://localhost:8000/api/settings | python3 -m json.tool
```

Expected: JSON with `items` object containing all 8 settings keys (e_mandi_username … auto_close_browser). No validation errors.

- [ ] **Step 3: Smoke the remaining read routes**

```bash
curl -s http://localhost:8000/api/bills
curl -s http://localhost:8000/api/logs
curl -s http://localhost:8000/api/automation/state
```

Expected: `200` JSON responses (bills/logs may be empty lists; state shows `"idle"`).

---

## Task 2: Backend auth foundations — models, security, RBAC

**Files:**
- Create: `backend/app/models/user.py`, `backend/app/models/activity_log.py`
- Modify: `backend/app/models/__init__.py`
- Create: `backend/app/core/jwt.py`, `backend/app/core/rbac.py`
- Modify: `backend/app/core/security.py` (add bcrypt hashing)
- Create: `backend/tests/conftest.py`, `backend/tests/test_auth.py`, `backend/tests/test_rbac.py`
- Modify: `backend/requirements.txt` (add `PyJWT==2.10.1`, `bcrypt==4.2.1`, `pytest==8.3.4`, `pytest-asyncio==0.25.2`, `httpx==0.28.1`)

**Models (`models/user.py`):**

```python
from datetime import datetime
from typing import Optional
from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class Role(Base):
    __tablename__ = "roles"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)


class RolePermission(Base):
    __tablename__ = "role_permissions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    role_id: Mapped[int] = mapped_column(ForeignKey("roles.id"), nullable=False, index=True)
    permission: Mapped[str] = mapped_column(String(100), nullable=False)


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    full_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role_id: Mapped[int] = mapped_column(ForeignKey("roles.id"), nullable=False)
    is_active: Mapped[bool] = mapped_column(Integer, default=1, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
```

**Models (`models/activity_log.py`):**

```python
from datetime import datetime
from typing import Any, Optional
from sqlalchemy import DateTime, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class ActivityLog(Base):
    __tablename__ = "activity_logs"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    actor: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    action: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    entity: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    entity_id: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    old_value: Mapped[Optional[Any]] = mapped_column(JSON, nullable=True)
    new_value: Mapped[Optional[Any]] = mapped_column(JSON, nullable=True)
    ip: Mapped[Optional[str]] = mapped_column(String(45), nullable=True)
    details: Mapped[Optional[Any]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
```

**Security (`core/security.py`) additions:**

```python
import bcrypt


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except ValueError:
        return False
```

**JWT (`core/jwt.py`):**

```python
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional
import jwt
from app.config import settings

ALGORITHM = "HS256"
ACCESS_TTL = timedelta(hours=8)
REFRESH_TTL = timedelta(days=14)


def _secret() -> str:
    secret = settings.SECRET_KEY or settings.ENCRYPTION_KEY
    return secret


def create_token(subject: str, token_type: str = "access", extra: Optional[Dict[str, Any]] = None) -> str:
    now = datetime.now(timezone.utc)
    ttl = ACCESS_TTL if token_type == "access" else REFRESH_TTL
    payload: Dict[str, Any] = {
        "sub": subject,
        "type": token_type,
        "iat": now,
        "exp": now + ttl,
    }
    if extra:
        payload.update(extra)
    return jwt.encode(payload, _secret(), algorithm=ALGORITHM)


def decode_token(token: str) -> Dict[str, Any]:
    return jwt.decode(token, _secret(), algorithms=[ALGORITHM])
```

**RBAC (`core/rbac.py`):**

```python
from typing import List, Optional
from fastapi import Depends, HTTPException, Request
import jwt as pyjwt
from app.core.jwt import decode_token
from app.database import async_session_factory
from app.models.user import Role, RolePermission, User
from sqlalchemy import select

PERMISSIONS = {
    "administrator": ["*"],
    "operator": ["bills:*", "payments:*", "automation:*", "search:read", "dashboard:read"],
    "accountant": ["bills:read", "payments:*", "reports:read", "search:read", "dashboard:read", "settings:read"],
    "inspector": ["search:read", "dashboard:read", "bills:read", "payments:read", "reports:read", "audit:read"],
}


async def get_current_user(request: Request):
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Not authenticated")
    token = auth.split(" ", 1)[1]
    try:
        payload = decode_token(token)
    except pyjwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    if payload.get("type") != "access":
        raise HTTPException(status_code=401, detail="Not an access token")
    username = payload.get("sub")
    async with async_session_factory() as session:
        user = (await session.execute(select(User).where(User.username == username))).scalar_one_or_none()
        if not user or not user.is_active:
            raise HTTPException(status_code=401, detail="User not found or inactive")
        role = await session.get(Role, user.role_id)
    return {"id": user.id, "username": user.username, "role": role.name if role else None}


async def require_permission(permission: str):
    async def checker(user: dict = Depends(get_current_user)):
        role = user["role"]
        perms = PERMISSIONS.get(role, [])
        if "*" in perms or permission in perms or permission.split(":")[0] + ":*" in perms:
            return user
        raise HTTPException(status_code=403, detail=f"Missing permission: {permission}")
    return checker
```

**Tests (`tests/conftest.py`):**

```python
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault("MANDI_DATABASE_URL", "sqlite+aiosqlite:///./test_mandi.db")

import pytest
import asyncio
from httpx import AsyncClient, ASGITransport
from app.database import engine, async_session_factory, Base
from app.main import app


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session", autouse=True)
async def prepare_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    from app.seed import seed_defaults
    await seed_defaults()
    from app.core.security import hash_password
    from app.models.user import Role, User
    async with async_session_factory() as session:
        from sqlalchemy import select
        admin_role = Role(name="administrator", description="Full access")
        session.add(admin_role)
        await session.flush()
        session.add(Role(name="operator", description="Operations"))
        session.add(Role(name="accountant", description="Finance"))
        session.add(Role(name="inspector", description="View-only audit"))
        await session.flush()
        admin = User(username="admin", full_name="System Admin", password_hash=hash_password("admin123"), role_id=admin_role.id)
        session.add(admin)
        await session.commit()
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
```

**Tests (`tests/test_auth.py`):**

```python
import pytest


@pytest.mark.asyncio
async def test_login_success_and_me(client):
    resp = await client.post("/api/v1/auth/login", json={"username": "admin", "password": "admin123"})
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["access_token"]
    headers = {"Authorization": f"Bearer {data['access_token']}"}
    me = await client.get("/api/v1/auth/me", headers=headers)
    assert me.status_code == 200
    assert me.json()["username"] == "admin"


@pytest.mark.asyncio
async def test_login_wrong_password(client):
    resp = await client.post("/api/v1/auth/login", json={"username": "admin", "password": "wrong"})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_me_without_token(client):
    resp = await client.get("/api/v1/auth/me")
    assert resp.status_code == 401
```

**Tests (`tests/test_rbac.py`):**

```python
import pytest


async def _login(client, username="admin", password="admin123"):
    resp = await client.post("/api/v1/auth/login", json={"username": username, "password": password})
    assert resp.status_code == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


@pytest.mark.asyncio
async def test_inspector_cannot_mutate_settings(client):
    headers = await _login(client, "admin")
    # create inspector user
    from app.core.security import hash_password
    from app.database import async_session_factory
    from app.models.user import Role, User
    from sqlalchemy import select
    async with async_session_factory() as session:
        role = (await session.execute(select(Role).where(Role.name == "inspector"))).scalar_one()
        u = User(username="inspector1", password_hash=hash_password("inspector123"), role_id=role.id)
        session.add(u)
        await session.commit()
    resp = await client.post("/api/v1/auth/login", json={"username": "inspector1", "password": "inspector123"})
    insp = {"Authorization": f"Bearer {resp.json()['access_token']}"}
    update = await client.put("/api/v1/settings/hammali_rate", json={"value": "99"}, headers=insp)
    assert update.status_code == 403
    read = await client.get("/api/v1/settings", headers=insp)
    assert read.status_code == 200
```

---

## Task 3: Backend auth/audit/search modules + routes + seed

**Files:**
- Create: `backend/app/domain/__init__.py`, `backend/app/domain/auth/__init__.py`, `backend/app/domain/auth/schemas.py`, `backend/app/domain/auth/service.py`, `backend/app/domain/auth/router.py`
- Create: `backend/app/domain/audit/__init__.py`, `backend/app/domain/audit/router.py`
- Create: `backend/app/domain/search/__init__.py`, `backend/app/domain/search/router.py`
- Create: `backend/app/core/audit.py`
- Modify: `backend/app/seed.py` (seed roles + admin), `backend/app/main.py` (mount `/api/v1` routers), `backend/app/database.py` (import new models in `init_db`), `backend/app/models/__init__.py`

**Audit core (`core/audit.py`):**

```python
from typing import Any, Optional
from fastapi import Request
from app.services.logging_service import log as db_log


async def record_audit(
    action: str,
    entity: Optional[str] = None,
    entity_id: Optional[str] = None,
    old_value: Optional[Any] = None,
    new_value: Optional[Any] = None,
    actor: Optional[str] = None,
    request: Optional[Request] = None,
    details: Optional[Any] = None,
) -> None:
    ip = request.client.host if request and request.client else None
    await db_log("INFO", f"AUDIT {action} {entity or ''} {entity_id or ''}".strip(),
                 details={"actor": actor, "old_value": old_value, "new_value": new_value, "ip": ip, "extra": details})
```

(ActivityLog table is created; `core/audit.py` writes through the existing logging pipeline so `/api/logs` + activity are consistent. The dedicated `activity_logs` table wiring for rich before/after rows is completed in Phase 1 master-data services.)

**Auth schemas (`domain/auth/schemas.py`):**

```python
from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=100)
    password: str = Field(..., min_length=1, max_length=255)


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: dict


class UserOut(BaseModel):
    id: int
    username: str
    full_name: str | None
    role: str | None
```

**Auth service (`domain/auth/service.py`):**

```python
from sqlalchemy import select
from fastapi import HTTPException
from app.core.jwt import create_token, decode_token
from app.core.security import hash_password, verify_password
from app.database import async_session_factory
from app.models.user import Role, User


async def authenticate(username: str, password: str) -> dict:
    async with async_session_factory() as session:
        user = (await session.execute(select(User).where(User.username == username))).scalar_one_or_none()
        if not user or not verify_password(password, user.password_hash):
            raise HTTPException(status_code=401, detail="Invalid username or password")
        role = await session.get(Role, user.role_id)
        return {
            "access_token": create_token(user.username, "access", {"role": role.name if role else None}),
            "refresh_token": create_token(user.username, "refresh"),
            "user": {"id": user.id, "username": user.username, "full_name": user.full_name, "role": role.name if role else None},
        }


async def refresh_access(refresh_token: str) -> dict:
    try:
        payload = decode_token(refresh_token)
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid refresh token")
    if payload.get("type") != "refresh":
        raise HTTPException(status_code=401, detail="Not a refresh token")
    return {
        "access_token": create_token(payload["sub"], "access", {"role": payload.get("role")}),
        "token_type": "bearer",
    }
```

**Auth router (`domain/auth/router.py`):**

```python
from fastapi import APIRouter, Depends
from app.core.rbac import get_current_user
from app.domain.auth.schemas import LoginRequest, TokenResponse, UserOut
from app.domain.auth.service import authenticate, refresh_access

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
async def login(payload: LoginRequest) -> dict:
    return await authenticate(payload.username, payload.password)


@router.post("/refresh", response_model=dict)
async def refresh(payload: dict) -> dict:
    return await refresh_access(payload["refresh_token"])


@router.get("/me", response_model=UserOut)
async def me(user: dict = Depends(get_current_user)) -> dict:
    return user
```

**Audit router (`domain/audit/router.py`):**

```python
from fastapi import APIRouter, Depends, Query
from app.core.rbac import require_permission
from app.services import logging_service

router = APIRouter(prefix="/api/v1/audit", tags=["audit"])


@router.get("")
async def list_audit(
    level: str | None = Query(None),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    _=Depends(require_permission("audit:read")),
):
    result = await logging_service.get_logs(level=level, limit=limit, offset=offset)
    return {"items": [{"id": l.id, "level": l.level, "message": l.message,
                       "details": l.details, "created_at": l.created_at.isoformat()}
                      for l in result["items"]],
            "total": result["total"], "limit": result["limit"], "offset": result["offset"]}
```

**Search router (`domain/search/router.py`):**

```python
from fastapi import APIRouter, Depends, Query
from sqlalchemy import or_, select
from app.core.rbac import require_permission
from app.database import async_session_factory
from app.models.bill import Bill

router = APIRouter(prefix="/api/v1/search", tags=["search"])


@router.get("")
async def global_search(
    q: str = Query("", min_length=0, max_length=200),
    limit: int = Query(10, ge=1, le=50),
    _=Depends(require_permission("search:read")),
):
    term = q.strip()
    bills = []
    if term:
        like = f"%{term}%"
        async with async_session_factory() as session:
            rows = (await session.execute(
                select(Bill).where(or_(
                    Bill.bill_number.like(like),
                    Bill.trader_name.like(like),
                    Bill.commodity.like(like),
                    Bill.vehicle_number.like(like),
                )).limit(limit)
            )).scalars().all()
            bills = [{"type": "bill", "id": b.id, "title": f"Bill {b.bill_number}",
                      "subtitle": f"{b.trader_name} · {b.commodity}",
                      "route": f"/bills/{b.id}"} for b in rows]
    return {"items": bills}
```

**Seed additions (`seed.py`) — append inside `seed_defaults()`:**

```python
from sqlalchemy import select
from app.core.security import hash_password
from app.models.user import Role, User

async with async_session_factory() as session:
    existing_roles = {r.name for r in (await session.execute(select(Role))).scalars().all()}
    role_map = {}
    for name, desc in [("administrator", "Full access"), ("operator", "Operations"),
                       ("accountant", "Finance"), ("inspector", "View-only audit")]:
        if name not in existing_roles:
            r = Role(name=name, description=desc)
            session.add(r)
            await session.flush()
            role_map[name] = r.id
        else:
            r = (await session.execute(select(Role).where(Role.name == name))).scalar_one()
            role_map[name] = r.id
    admin_exists = (await session.execute(select(User).where(User.username == "admin"))).scalar_one_or_none()
    if not admin_exists:
        session.add(User(username="admin", full_name="System Administrator",
                         password_hash=hash_password("admin123"), role_id=role_map["administrator"]))
    await session.commit()
```

**Main mount (`main.py`):** include routers `auth.router`, `audit.router`, `search.router` alongside existing ones. **DB init (`database.py`):** add `user`, `activity_log` to the `init_db` model imports.

- [ ] **Step 1:** Write model, security, jwt, rbac files above.
- [ ] **Step 2:** Run `pytest tests/test_auth.py tests/test_rbac.py -v` — tests initially fail (no routes). Then add domain modules + routes + seed, rerun until green.
- [ ] **Step 3:** Restart backend; verify:
  ```bash
  curl -s -X POST http://localhost:8000/api/v1/auth/login -H 'Content-Type: application/json' -d '{"username":"admin","password":"admin123"}'
  curl -s "http://localhost:8000/api/v1/search?q=10" -H "Authorization: Bearer $TOKEN"
  ```

---

## Task 4: Frontend scaffold + dependencies

**Files:**
- Create: `frontend/` (Vite React TS project via `npm create vite@latest . -- --template react-ts`)
- Create: `frontend/package.json`, `vite.config.ts`, `tsconfig*.json`, `index.html`, `src/main.tsx`, `src/App.tsx`
- Modify: `frontend/tailwind.config.js`, `frontend/postcss.config.js`

- [ ] **Step 1:** Scaffold and install locked deps:

```bash
cd /home/hereyashhh/mandi-automation-assistant
npm create vite@latest frontend -- --template react-ts
cd frontend
npm install
npm install zustand @tanstack/react-query @tanstack/react-table @radix-ui/react-dialog @radix-ui/react-dropdown-menu @radix-ui/react-toast @radix-ui/react-label @radix-ui/react-select @radix-ui/react-switch @radix-ui/react-tooltip recharts cmdk lucide-react
npm install -D tailwindcss@3.4.17 postcss autoprefixer @types/node
npx tailwindcss init -p
```

- [ ] **Step 2:** Configure `tailwind.config.js` content globs + dark class; `vite.config.ts` with `@` alias to `src`.
- [ ] **Step 3:** `npm run build` passes (type-safe template).

---

## Task 5: Design tokens + Tailwind theme

**Files:**
- Create: `frontend/src/styles/tokens.css`, `frontend/src/styles/base.css`
- Modify: `frontend/src/index.css` (import tokens), `frontend/tailwind.config.js`

- [ ] **Step 1:** Define token sets for `:root` (light) and `[data-theme="dark"]`, `[data-theme="high-contrast"]`, and `[data-font-size="large"]` overrides. Use the token groups from the plan §7: color, status, typography scale, spacing, radii, shadow, motion.

```css
:root {
  --color-bg: #f6f7f9;
  --color-surface: #ffffff;
  --color-border: #e2e5ea;
  --color-text: #16181d;
  --color-muted: #5b6472;
  --color-primary: #1a7f4d;
  --color-primary-foreground: #ffffff;
  --color-accent: #d97b1e;
  --color-success: #1a7f4d;
  --color-warning: #c77d1f;
  --color-danger: #c0392b;
  --color-info: #2563eb;
  --radius-sm: 4px; --radius-md: 8px; --radius-lg: 12px;
  --font-sans: 'Inter', 'Noto Sans Devanagari', system-ui, sans-serif;
}
[data-theme="dark"] {
  --color-bg: #0f1115; --color-surface: #181b21; --color-border: #2a2f38;
  --color-text: #e8eaee; --color-muted: #9aa3b0;
  --color-primary: #2ea06b;
  --color-success: #2ea06b; --color-warning: #e0a04a; --color-danger: #e26356; --color-info: #5b8def;
}
[data-theme="high-contrast"] { --color-bg: #000; --color-surface: #000; --color-border: #fff;
  --color-text: #fff; --color-muted: #fff; --color-primary: #ffd400; --color-primary-foreground: #000; }
[data-font-size="large"] { font-size: 18px; }
```

- [ ] **Step 2:** Map tokens to Tailwind `colors`, `borderRadius`, `fontFamily`, `boxShadow` in `tailwind.config.js`:

```js
module.exports = {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  darkMode: ["class", '[data-theme="dark"]'],
  theme: {
    extend: {
      colors: {
        bg: "var(--color-bg)", surface: "var(--color-surface)", border: "var(--color-border)",
        text: "var(--color-text)", muted: "var(--color-muted)",
        primary: { DEFAULT: "var(--color-primary)", foreground: "var(--color-primary-foreground)" },
        accent: "var(--color-accent)",
        success: "var(--color-success)", warning: "var(--color-warning)",
        danger: "var(--color-danger)", info: "var(--color-info)",
      },
      borderRadius: { sm: "var(--radius-sm)", md: "var(--radius-md)", lg: "var(--radius-lg)" },
      fontFamily: { sans: ["var(--font-sans)"], mono: ["ui-monospace", "monospace"] },
    },
  },
  plugins: [],
};
```

- [ ] **Step 3:** `npm run build` passes.

---

## Task 6: UI component library

**Files (create under `frontend/src/components/ui/`):**
- `button.tsx`, `input.tsx`, `label.tsx`, `card.tsx`, `badge.tsx`, `dialog.tsx`, `toast.tsx` (+ `toaster.tsx`, `use-toast.ts`), `select.tsx`, `switch.tsx`, `empty-state.tsx`, `skeleton.tsx`
- Create: `frontend/src/lib/utils.ts` (cn helper)

**`lib/utils.ts`:**

```ts
import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";
import { cn } from "./cn";
```

(Install `clsx` + `tailwind-merge`; use a single `cn` export: `export function cn(...inputs: ClassValue[]) { return twMerge(clsx(inputs)); }`)

**`button.tsx` (core pattern — all components follow Radix + cn):**

```tsx
import { forwardRef, type ButtonHTMLAttributes } from "react";
import { cn } from "@/lib/utils";
import { Loader2 } from "lucide-react";

export type ButtonVariant = "primary" | "secondary" | "ghost" | "danger" | "outline";
export type ButtonSize = "sm" | "md" | "lg" | "icon";

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  size?: ButtonSize;
  loading?: boolean;
}

const variants: Record<ButtonVariant, string> = {
  primary: "bg-primary text-primary-foreground hover:opacity-90",
  secondary: "bg-surface border border-border hover:bg-muted/10",
  ghost: "hover:bg-muted/10",
  danger: "bg-danger text-white hover:opacity-90",
  outline: "border border-border bg-transparent hover:bg-muted/10",
};
const sizes: Record<ButtonSize, string> = {
  sm: "h-8 px-3 text-xs", md: "h-10 px-4 text-sm", lg: "h-11 px-6 text-base", icon: "h-9 w-9",
};

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant = "primary", size = "md", loading, children, disabled, ...props }, ref) => (
    <button ref={ref} disabled={disabled || loading}
      className={cn("inline-flex items-center justify-center gap-2 rounded-md font-medium transition-colors focus-visible:outline-2 focus-visible:outline-info disabled:pointer-events-none disabled:opacity-60",
        variants[variant], sizes[size], className)}
      {...props}>
      {loading && <Loader2 className="h-4 w-4 animate-spin" />}
      {children}
    </button>
  ),
);
Button.displayName = "Button";
```

- [ ] **Step 1:** Write `cn` util + Button + Input + Label + Card + Badge + Skeleton + EmptyState + Switch + Select (Radix) + Dialog (Radix) + Toast (Radix) following the Button pattern (variant/size, `cn`, `forwardRef`, focus styles).
- [ ] **Step 2:** `npm run build` passes. Manual spot-check in a scratch page.

---

## Task 7: ERP shell — Layout, TopBar, Sidebar, StatusBar, theme

**Files:**
- Create: `frontend/src/components/layout/app-shell.tsx`, `top-bar.tsx`, `sidebar.tsx`, `status-bar.tsx`, `theme-provider.tsx`, `command-palette.tsx`
- Create: `frontend/src/stores/theme.ts`, `frontend/src/stores/auth.ts`, `frontend/src/stores/ui.ts`
- Create: `frontend/src/lib/api.ts` (fetch client + refresh interceptor)
- Create: `frontend/src/constants.ts` (nav groups)

**Nav groups (`constants.ts`):**

```ts
export const NAV_GROUPS = [
  { label: "Overview", items: [
    { label: "Dashboard", route: "/dashboard", icon: "layout-dashboard", permission: "dashboard:read" },
  ]},
  { label: "Farmers", items: [
    { label: "Registration", route: "/farmers", permission: "farmers:read" },
    { label: "Payments", route: "/farmers/payments", permission: "payments:read" },
  ]},
  { label: "Traders", items: [
    { label: "Registration", route: "/traders", permission: "traders:read" },
    { label: "Stock", route: "/traders/stock", permission: "stock:read" },
  ]},
  { label: "Operations", items: [
    { label: "Stock", route: "/stock", permission: "stock:read" },
    { label: "Payments", route: "/payments", permission: "payments:read" },
    { label: "Bills", route: "/bills", permission: "bills:read" },
    { label: "Reports", route: "/reports", permission: "reports:read" },
  ]},
  { label: "Documents", items: [{ label: "Document Center", route: "/documents", permission: "documents:read" }]},
  { label: "System", items: [
    { label: "Automation", route: "/automation", permission: "automation:read" },
    { label: "Notifications", route: "/notifications", permission: "notifications:read" },
    { label: "Activity Log", route: "/audit", permission: "audit:read" },
    { label: "Settings", route: "/settings", permission: "settings:read" },
  ]},
] as const;
```

**API client (`lib/api.ts`):**

```ts
import { useAuthStore } from "@/stores/auth";

const BASE = import.meta.env.VITE_API_BASE ?? "http://localhost:8000";

export async function api<T = any>(path: string, options: RequestInit = {}): Promise<T> {
  const { getAccess, getRefresh, setSession, clear } = useAuthStore.getState();
  const headers = new Headers(options.headers);
  headers.set("Content-Type", "application/json");
  const token = getAccess();
  if (token) headers.set("Authorization", `Bearer ${token}`);
  let res = await fetch(`${BASE}${path}`, { ...options, headers });
  if (res.status === 401 && token && path !== "/api/v1/auth/login") {
    const refresh = getRefresh();
    if (refresh) {
      const rr = await fetch(`${BASE}/api/v1/auth/refresh`, { method: "POST",
        headers: { "Content-Type": "application/json" }, body: JSON.stringify({ refresh_token: refresh }) });
      if (rr.ok) {
        const data = await rr.json();
        setSession({ ...useAuthStore.getState().user!, access_token: data.access_token, refresh_token: refresh });
        const headers2 = new Headers(options.headers);
        headers2.set("Authorization", `Bearer ${data.access_token}`);
        res = await fetch(`${BASE}${path}`, { ...options, headers: headers2 });
      } else { clear(); }
    }
  }
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body?.error?.message ?? body?.detail ?? `Request failed (${res.status})`);
  }
  return res.json();
}
```

**Auth store (`stores/auth.ts`):**

```ts
import { create } from "zustand";
import { persist } from "zustand/middleware";

interface AuthState {
  user: { id: number; username: string; full_name?: string; role?: string } | null;
  access_token: string | null;
  refresh_token: string | null;
  setSession: (s: Partial<AuthState>) => void;
  clear: () => void;
  getAccess: () => string | null;
  getRefresh: () => string | null;
}

export const useAuthStore = create<AuthState>()(persist(
  (set, get) => ({
    user: null, access_token: null, refresh_token: null,
    setSession: (s) => set(s),
    clear: () => set({ user: null, access_token: null, refresh_token: null }),
    getAccess: () => get().access_token,
    getRefresh: () => get().refresh_token,
  }),
  { name: "mandi-auth" },
));
```

**Theme store (`stores/theme.ts`):**

```ts
import { create } from "zustand";
import { persist } from "zustand/middleware";

export type ThemeMode = "light" | "dark" | "high-contrast";
export type FontSize = "normal" | "large";

interface ThemeState { theme: ThemeMode; fontSize: FontSize; setTheme: (t: ThemeMode) => void; setFontSize: (f: FontSize) => void; }

export const useThemeStore = create<ThemeState>()(persist(
  (set) => ({
    theme: "light", fontSize: "normal",
    setTheme: (theme) => set({ theme }),
    setFontSize: (fontSize) => set({ fontSize }),
  }),
  { name: "mandi-theme" },
));
```

**Theme provider (`theme-provider.tsx`):** applies `data-theme` + `data-font-size` attributes on `document.documentElement` whenever the store changes.

**Command palette (`command-palette.tsx`):** cmdk-based; opens on `Ctrl+K` / `Cmd+K`; items from the `NAV_GROUPS` (routes) + `/api/v1/search` results (bill hits, keyboard-navigable, Enter navigates). `Esc` closes.

**App shell (`app-shell.tsx`):** `[TopBar][Sidebar][main outlet][StatusBar]`; sidebar collapses; mobile drawer. StatusBar shows automation state (from `/api/automation/state` polling) + backend health + version.

- [ ] **Step 1:** Write stores + api client + constants.
- [ ] **Step 2:** Write theme provider + shell components.
- [ ] **Step 3:** Wire command palette with search API.
- [ ] **Step 4:** `npm run build` passes.

---

## Task 8: Auth pages, routing, guards

**Files:**
- Create: `frontend/src/pages/login.tsx`, `frontend/src/pages/dashboard.tsx`
- Create: `frontend/src/components/layout/protected-route.tsx`, `frontend/src/components/layout/permission.tsx`
- Modify: `frontend/src/App.tsx` (router: `/login` public; `/*` under shell → `ProtectedRoute`)

**Login page:** username/password form; calls `api("/api/v1/auth/login", { method: "POST", body })`; on success `setSession` + redirect to `/dashboard`; shows error toast. Include theme toggle.

**ProtectedRoute:** if no user → redirect `/login`. **Permission component:** hides children when role lacks permission (uses `PERMISSIONS` map mirrored from backend).

- [ ] **Step 1:** Write login + guards.
- [ ] **Step 2:** Write a placeholder Dashboard (KPI cards from `/api/automation/state` + `/api/bills` counts + skeleton loading).
- [ ] **Step 3:** `npm run build` + manual login flow against running backend.

---

## Task 9: SmartTable + wiring all IA pages

**Files:**
- Create: `frontend/src/components/data/smart-table.tsx`
- Create: `frontend/src/pages/` placeholders for `farmers`, `traders`, `stock`, `payments`, `bills`, `reports`, `documents`, `notifications`, `automation`, `settings`, `audit`
- Modify: `frontend/src/App.tsx` (add all routes)

**SmartTable (`components/data/smart-table.tsx`):** wraps `@tanstack/react-table`; props: `columns`, `data`, `loading`, `onExport`. Features: sortable headers, column hide menu, search filter, pagination, CSV export (client-side blob), sticky header, empty/error states (EmptyState component), skeleton rows when loading. Generic over row type:

```tsx
import { useReactTable, getCoreRowModel, getSortedRowModel, getPaginationRowModel, getFilteredRowModel, flexRender, type ColumnDef } from "@tanstack/react-table";
// ...standard TanStack wiring; exportToCsv(data, columns) helper using Blob + URL.createObjectURL
```

**Settings page:** reads `/api/settings`, renders grouped form (portal credentials password fields, hammali rate, cash threshold, automation timeout, auto-close toggle), saves via `PUT /api/v1/settings/{key}`.

**Audit page:** table of `/api/v1/audit` items.

- [ ] **Step 1:** Write SmartTable.
- [ ] **Step 2:** Write all placeholder pages (each: PageHeader + EmptyState "Module in Phase N").
- [ ] **Step 3:** Settings + Audit pages with real data.
- [ ] **Step 4:** Wire all routes in App.tsx.
- [ ] **Step 5:** `npm run build` + full smoke test (login → navigate → search → settings save → audit).

---

## Task 10: End-to-end verification

- [ ] **Step 1:** Backend: `cd backend && ./venv/bin/pytest -v` — all green.
- [ ] **Step 2:** Frontend: `cd frontend && npm run build` — passes.
- [ ] **Step 3:** Start both servers; verify in browser: login as `admin/admin123`, dark mode toggle, cmd+K search returns a bill after one is created, smart tables sort/export, settings save persists, audit log shows login.

**Phase 0 done when:** ERP shell renders with grouped nav, cmd+K search works, auth/RBAC enforced, every list uses SmartTable, settings + audit pages live, existing `/api/automation/*` untouched and reachable from the Automation page.

---

## Self-Review

- **Spec coverage:** §5 nav, §6 components, §7 tokens, §8 dashboard placeholder, §9.14 settings, §9.13 activity log, §13 frontend arch, §14 backend arch, §15 RBAC, §21 migration finish-base — all covered by Tasks 1–10. Farmer/trader/stock/payment/bill/report/document modules are Phase 1+ (deferred intentionally).
- **Placeholder scan:** none (all code blocks concrete).
- **Type consistency:** `api<T>` used uniformly; `useAuthStore` names match across api client, auth page, guards; token payload `role` key consistent in service + refresh.
