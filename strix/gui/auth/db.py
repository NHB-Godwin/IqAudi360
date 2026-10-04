"""Hybrid resilient database layer for iqAudi360.

Supports both Google Cloud Firestore and local SQLite:
  • If Firestore credentials are configured and valid -> Uses Firestore (cloud persistence)
  • If Firestore is unavailable or fails -> Gracefully falls back to SQLite (zero downtime)

All public function signatures match routes.py expectations identically.
"""

from __future__ import annotations

import logging
import os
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Database Configuration & Backend Detection
# ---------------------------------------------------------------------------

_custom_db = os.environ.get("DATABASE_PATH")
DB_PATH = Path(_custom_db) if _custom_db else (
    Path(__file__).resolve().parent.parent.parent.parent / "iqaudi360_auth.db"
)

COL_USERS = "users"
COL_TENANTS = "tenants"
COL_MEMBERS = "tenant_members"
COL_SCANS = "scan_ownership"
COL_AUDIT = "audit_logs"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _get_firestore():
    """Return Firestore client if available, else None."""
    try:
        from strix.gui.auth.firebase import get_firestore_client
        return get_firestore_client()
    except Exception as exc:
        logger.debug("Firestore client check: %s", exc)
        return None


def can_use_firestore() -> bool:
    """Check if Firestore client is initialized and operational."""
    return _get_firestore() is not None


# ===========================================================================
#  SQLITE BACKEND IMPLEMENTATION
# ===========================================================================

def _sqlite_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH), timeout=15.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode = WAL;")
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def _sqlite_init_db() -> None:
    conn = _sqlite_conn()
    with conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            user_id TEXT PRIMARY KEY,
            email TEXT UNIQUE NOT NULL,
            display_name TEXT,
            photo_url TEXT,
            is_superadmin INTEGER DEFAULT 0,
            status TEXT DEFAULT 'active',
            created_at TEXT NOT NULL,
            last_login_at TEXT
        );

        CREATE TABLE IF NOT EXISTS tenants (
            tenant_id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            created_by TEXT NOT NULL,
            status TEXT DEFAULT 'active',
            created_at TEXT NOT NULL,
            FOREIGN KEY (created_by) REFERENCES users(user_id)
        );

        CREATE TABLE IF NOT EXISTS tenant_members (
            membership_id TEXT PRIMARY KEY,
            tenant_id TEXT NOT NULL,
            user_id TEXT NOT NULL,
            role TEXT NOT NULL,
            status TEXT DEFAULT 'active',
            created_at TEXT NOT NULL,
            UNIQUE(tenant_id, user_id),
            FOREIGN KEY (tenant_id) REFERENCES tenants(tenant_id) ON DELETE CASCADE,
            FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS scan_ownership (
            scan_id TEXT PRIMARY KEY,
            tenant_id TEXT NOT NULL,
            created_by TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY (tenant_id) REFERENCES tenants(tenant_id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS audit_logs (
            id TEXT PRIMARY KEY,
            timestamp TEXT NOT NULL,
            actor_user_id TEXT,
            actor_email TEXT,
            tenant_id TEXT,
            action TEXT NOT NULL,
            resource_type TEXT,
            resource_id TEXT,
            result TEXT NOT NULL,
            ip_address TEXT,
            details TEXT
        );

        CREATE INDEX IF NOT EXISTS idx_tm_user   ON tenant_members(user_id);
        CREATE INDEX IF NOT EXISTS idx_tm_tenant ON tenant_members(tenant_id);
        CREATE INDEX IF NOT EXISTS idx_so_tenant ON scan_ownership(tenant_id);
        CREATE INDEX IF NOT EXISTS idx_al_tenant ON audit_logs(tenant_id);
        CREATE INDEX IF NOT EXISTS idx_al_ts     ON audit_logs(timestamp);
        """)
    conn.close()
    _sqlite_seed_demo()
    _sqlite_migrate_scans()


def _sqlite_seed_demo() -> None:
    now = _now()
    conn = _sqlite_conn()
    try:
        with conn:
            conn.execute(
                "INSERT OR IGNORE INTO users VALUES ('uid_super_01','superadmin@iqaudi360.com','Super Admin',NULL,1,'active',?,?)",
                (now, now),
            )
            conn.execute("UPDATE users SET is_superadmin=1, status='active' WHERE user_id='uid_super_01'")
            conn.execute(
                "INSERT OR IGNORE INTO tenants VALUES ('org_alpha_workspace','Enterprise Org Alpha','uid_super_01','active',?)",
                (now,),
            )
            demo = [
                ("uid_super_01", "superadmin@iqaudi360.com", "Super Admin", 1, "mem_super_alpha", "ADMIN"),
                ("uid_admin_a",  "admin@alpha.com",          "Alice Admin",  0, "mem_admin_alpha", "ADMIN"),
                ("uid_dev_a",    "dev@alpha.com",            "Dan Dev",      0, "mem_dev_alpha",   "DEV"),
                ("uid_client_a", "client@alpha.com",         "Charlie Client", 0, "mem_client_alpha", "CLIENT"),
            ]
            for uid, email, name, is_super, mid, role in demo:
                conn.execute(
                    "INSERT OR IGNORE INTO users VALUES (?,?,?,NULL,?,'active',?,?)",
                    (uid, email, name, is_super, now, now),
                )
                conn.execute(
                    "INSERT OR IGNORE INTO tenant_members VALUES (?,?,?,?,'active',?)",
                    (mid, "org_alpha_workspace", uid, role, now),
                )
    except Exception as exc:
        logger.debug("_sqlite_seed_demo info: %s", exc)
    finally:
        conn.close()


def _sqlite_migrate_scans() -> None:
    try:
        from strix.core.paths import runs_base_dir
        base_dir = runs_base_dir()
        if not base_dir.is_dir():
            return
        conn = _sqlite_conn()
        with conn:
            cur = conn.execute("SELECT tenant_id FROM tenants ORDER BY created_at ASC LIMIT 1")
            row = cur.fetchone()
            if row:
                for child in base_dir.iterdir():
                    if child.is_dir():
                        conn.execute(
                            "INSERT OR IGNORE INTO scan_ownership VALUES (?,?,?,?)",
                            (child.name, row["tenant_id"], "system_bootstrap", _now()),
                        )
        conn.close()
    except Exception as exc:
        logger.debug("_sqlite_migrate_scans: %s", exc)


def _sqlite_get_or_create_user(uid: str, email: str, display_name: str | None = None, photo_url: str | None = None) -> dict[str, Any]:
    conn = _sqlite_conn()
    now = _now()
    with conn:
        cur = conn.execute("SELECT * FROM users WHERE user_id = ?", (uid,))
        row = cur.fetchone()
        if row:
            conn.execute(
                "UPDATE users SET last_login_at = ?, display_name = COALESCE(?, display_name) WHERE user_id = ?",
                (now, display_name, uid),
            )
            cur = conn.execute("SELECT * FROM users WHERE user_id = ?", (uid,))
            return dict(cur.fetchone())

        cur = conn.execute("SELECT COUNT(*) as total FROM users")
        is_first = cur.fetchone()["total"] == 0
        name = display_name or email.split("@")[0].capitalize()
        conn.execute(
            "INSERT INTO users VALUES (?,?,?,?,?,'active',?,?)",
            (uid, email.lower(), name, photo_url, 1 if is_first else 0, now, now),
        )
        tid = f"org_{uuid.uuid4().hex[:12]}"
        org_name = "Primary Security Workspace" if is_first else f"{name}'s Organization"
        conn.execute("INSERT INTO tenants VALUES (?,?,?,'active',?)", (tid, org_name, uid, now))
        mid = f"mem_{uuid.uuid4().hex[:12]}"
        conn.execute("INSERT INTO tenant_members VALUES (?,?,?,'ADMIN','active',?)", (mid, tid, uid, now))
        if is_first:
            _sqlite_migrate_scans()
        cur = conn.execute("SELECT * FROM users WHERE user_id = ?", (uid,))
        result = dict(cur.fetchone())
    conn.close()
    return result


def _sqlite_get_user_by_id(uid: str) -> dict[str, Any] | None:
    conn = _sqlite_conn()
    cur = conn.execute("SELECT * FROM users WHERE user_id = ?", (uid,))
    row = cur.fetchone()
    conn.close()
    return dict(row) if row else None


def _sqlite_get_user_by_email(email: str) -> dict[str, Any] | None:
    conn = _sqlite_conn()
    cur = conn.execute("SELECT * FROM users WHERE LOWER(email) = LOWER(?)", (email.strip(),))
    row = cur.fetchone()
    conn.close()
    return dict(row) if row else None


def _sqlite_list_all_users() -> list[dict[str, Any]]:
    conn = _sqlite_conn()
    rows = [dict(r) for r in conn.execute("SELECT * FROM users ORDER BY created_at DESC").fetchall()]
    conn.close()
    return rows


def _sqlite_update_user_status(uid: str, status: str) -> bool:
    if status not in ("active", "disabled"):
        return False
    conn = _sqlite_conn()
    with conn:
        conn.execute("UPDATE users SET status = ? WHERE user_id = ?", (status, uid))
    conn.close()
    return True


def _sqlite_set_user_superadmin(uid: str, is_superadmin: bool) -> bool:
    conn = _sqlite_conn()
    with conn:
        conn.execute("UPDATE users SET is_superadmin = ? WHERE user_id = ?", (1 if is_superadmin else 0, uid))
    conn.close()
    return True


def _sqlite_create_tenant(name: str, created_by: str) -> dict[str, Any]:
    conn = _sqlite_conn()
    now = _now()
    tid = f"org_{uuid.uuid4().hex[:12]}"
    mid = f"mem_{uuid.uuid4().hex[:12]}"
    with conn:
        conn.execute("INSERT INTO tenants VALUES (?,?,?,'active',?)", (tid, name.strip(), created_by, now))
        conn.execute("INSERT INTO tenant_members VALUES (?,?,?,'ADMIN','active',?)", (mid, tid, created_by, now))
        cur = conn.execute("SELECT * FROM tenants WHERE tenant_id = ?", (tid,))
        tenant = dict(cur.fetchone())
    conn.close()
    return tenant


def _sqlite_get_tenant_by_id(tenant_id: str) -> dict[str, Any] | None:
    conn = _sqlite_conn()
    cur = conn.execute("SELECT * FROM tenants WHERE tenant_id = ?", (tenant_id,))
    row = cur.fetchone()
    conn.close()
    return dict(row) if row else None


def _sqlite_list_tenants_for_user(user_id: str, is_superadmin: bool = False) -> list[dict[str, Any]]:
    conn = _sqlite_conn()
    if is_superadmin:
        rows = [dict(r) for r in conn.execute("SELECT * FROM tenants ORDER BY created_at DESC").fetchall()]
    else:
        rows = [dict(r) for r in conn.execute("""
            SELECT t.*, tm.role, tm.status as member_status FROM tenants t
            JOIN tenant_members tm ON t.tenant_id = tm.tenant_id
            WHERE tm.user_id = ? AND tm.status = 'active' AND t.status = 'active'
            ORDER BY t.created_at DESC""", (user_id,)).fetchall()]
    conn.close()
    return rows


def _sqlite_list_all_tenants() -> list[dict[str, Any]]:
    conn = _sqlite_conn()
    rows = [dict(r) for r in conn.execute("""
        SELECT t.*,
               (SELECT COUNT(*) FROM tenant_members WHERE tenant_id = t.tenant_id) as member_count,
               (SELECT COUNT(*) FROM scan_ownership WHERE tenant_id = t.tenant_id) as scan_count
        FROM tenants t ORDER BY t.created_at DESC""").fetchall()]
    conn.close()
    return rows


def _sqlite_update_tenant_status(tenant_id: str, status: str) -> bool:
    if status not in ("active", "suspended"):
        return False
    conn = _sqlite_conn()
    with conn:
        conn.execute("UPDATE tenants SET status = ? WHERE tenant_id = ?", (status, tenant_id))
    conn.close()
    return True


def _sqlite_update_tenant_name(tenant_id: str, name: str) -> bool:
    conn = _sqlite_conn()
    with conn:
        conn.execute("UPDATE tenants SET name = ? WHERE tenant_id = ?", (name.strip(), tenant_id))
    conn.close()
    return True


def _sqlite_get_tenant_membership(tenant_id: str, user_id: str) -> dict[str, Any] | None:
    conn = _sqlite_conn()
    cur = conn.execute("""
        SELECT tm.*, t.name as tenant_name, t.status as tenant_status FROM tenant_members tm
        JOIN tenants t ON tm.tenant_id = t.tenant_id WHERE tm.tenant_id = ? AND tm.user_id = ?""",
        (tenant_id, user_id))
    row = cur.fetchone()
    conn.close()
    return dict(row) if row else None


def _sqlite_list_tenant_members(tenant_id: str) -> list[dict[str, Any]]:
    conn = _sqlite_conn()
    rows = [dict(r) for r in conn.execute("""
        SELECT tm.membership_id, tm.tenant_id, tm.user_id, tm.role, tm.status, tm.created_at as joined_at,
               u.email, u.display_name, u.photo_url, u.last_login_at FROM tenant_members tm
        JOIN users u ON tm.user_id = u.user_id WHERE tm.tenant_id = ? ORDER BY tm.created_at ASC""",
        (tenant_id,)).fetchall()]
    conn.close()
    return rows


def _sqlite_add_tenant_member(tenant_id: str, user_id: str, role: str = "DEV") -> dict[str, Any] | None:
    if role not in ("ADMIN", "DEV", "CLIENT"):
        return None
    conn = _sqlite_conn()
    now = _now()
    mid = f"mem_{uuid.uuid4().hex[:12]}"
    try:
        with conn:
            conn.execute("""INSERT INTO tenant_members VALUES (?,?,?,?,'active',?)
                ON CONFLICT(tenant_id, user_id) DO UPDATE SET role = ?, status = 'active'""",
                (mid, tenant_id, user_id, role, now, role))
            cur = conn.execute("SELECT * FROM tenant_members WHERE membership_id = ?", (mid,))
            row = cur.fetchone()
            return dict(row) if row else {"membership_id": mid, "tenant_id": tenant_id, "user_id": user_id, "role": role}
    except Exception as exc:
        logger.error("_sqlite_add_tenant_member: %s", exc)
        return None
    finally:
        conn.close()


def _sqlite_update_tenant_member_role(tenant_id: str, user_id: str, new_role: str) -> bool:
    if new_role not in ("ADMIN", "DEV", "CLIENT"):
        return False
    conn = _sqlite_conn()
    with conn:
        conn.execute("UPDATE tenant_members SET role = ? WHERE tenant_id = ? AND user_id = ?", (new_role, tenant_id, user_id))
    conn.close()
    return True


def _sqlite_update_tenant_member_status(tenant_id: str, user_id: str, status: str) -> bool:
    if status not in ("active", "disabled"):
        return False
    conn = _sqlite_conn()
    with conn:
        conn.execute("UPDATE tenant_members SET status = ? WHERE tenant_id = ? AND user_id = ?", (status, tenant_id, user_id))
    conn.close()
    return True


def _sqlite_remove_tenant_member(tenant_id: str, user_id: str) -> bool:
    conn = _sqlite_conn()
    with conn:
        conn.execute("DELETE FROM tenant_members WHERE tenant_id = ? AND user_id = ?", (tenant_id, user_id))
    conn.close()
    return True


def _sqlite_record_scan_ownership(scan_id: str, tenant_id: str, created_by: str) -> bool:
    conn = _sqlite_conn()
    now = _now()
    try:
        with conn:
            conn.execute("INSERT OR REPLACE INTO scan_ownership VALUES (?,?,?,?)", (scan_id, tenant_id, created_by, now))
        return True
    except Exception as exc:
        logger.error("_sqlite_record_scan_ownership: %s", exc)
        return False
    finally:
        conn.close()


def _sqlite_get_scan_ownership(scan_id: str) -> dict[str, Any] | None:
    conn = _sqlite_conn()
    cur = conn.execute("SELECT * FROM scan_ownership WHERE scan_id = ?", (scan_id,))
    row = cur.fetchone()
    conn.close()
    return dict(row) if row else None


def _sqlite_list_scans_for_tenant(tenant_id: str) -> list[str]:
    conn = _sqlite_conn()
    rows = conn.execute("SELECT scan_id FROM scan_ownership WHERE tenant_id = ? ORDER BY created_at DESC", (tenant_id,)).fetchall()
    conn.close()
    return [r["scan_id"] for r in rows]


def _sqlite_log_audit_event(actor_user_id, actor_email, tenant_id, action,
                            resource_type=None, resource_id=None, result="success",
                            ip_address=None, details=None) -> None:
    eid = f"audit_{uuid.uuid4().hex[:16]}"
    now = _now()
    conn = _sqlite_conn()
    try:
        with conn:
            conn.execute(
                "INSERT INTO audit_logs VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (eid, now, actor_user_id, actor_email, tenant_id, action, resource_type, resource_id, result, ip_address, details),
            )
    except Exception as exc:
        logger.error("_sqlite_log_audit_event: %s", exc)
    finally:
        conn.close()


def _sqlite_list_audit_logs(tenant_id=None, limit=100) -> list[dict[str, Any]]:
    conn = _sqlite_conn()
    if tenant_id:
        rows = conn.execute("SELECT * FROM audit_logs WHERE tenant_id = ? ORDER BY timestamp DESC LIMIT ?", (tenant_id, limit)).fetchall()
    else:
        rows = conn.execute("SELECT * FROM audit_logs ORDER BY timestamp DESC LIMIT ?", (limit,)).fetchall()
    result = [dict(r) for r in rows]
    conn.close()
    return result


# ===========================================================================
#  FIRESTORE BACKEND IMPLEMENTATION
# ===========================================================================

def _fs_seed_demo(db) -> None:
    now = _now()
    # Superadmin user
    ref = db.collection(COL_USERS).document("uid_super_01")
    if not ref.get().exists:
        ref.set({
            "user_id": "uid_super_01", "email": "superadmin@iqaudi360.com",
            "display_name": "Super Admin", "photo_url": None, "is_superadmin": True,
            "status": "active", "created_at": now, "last_login_at": now,
        })
    # Org Alpha
    org = db.collection(COL_TENANTS).document("org_alpha_workspace")
    if not org.get().exists:
        org.set({
            "tenant_id": "org_alpha_workspace", "name": "Enterprise Org Alpha",
            "created_by": "uid_super_01", "status": "active", "created_at": now,
        })
    # Demo accounts
    demo = [
        ("uid_super_01", "superadmin@iqaudi360.com", "Super Admin", "ADMIN", True, "mem_super_alpha"),
        ("uid_admin_a",  "admin@alpha.com",          "Alice Admin",  "ADMIN", False, "mem_admin_alpha"),
        ("uid_dev_a",    "dev@alpha.com",            "Dan Dev",      "DEV",   False, "mem_dev_alpha"),
        ("uid_client_a", "client@alpha.com",         "Charlie Client", "CLIENT", False, "mem_client_alpha"),
    ]
    for uid, email, name, role, is_super, mem_id in demo:
        u = db.collection(COL_USERS).document(uid)
        if not u.get().exists:
            u.set({
                "user_id": uid, "email": email, "display_name": name, "photo_url": None,
                "is_superadmin": is_super, "status": "active", "created_at": now, "last_login_at": now,
            })
        m = db.collection(COL_MEMBERS).document(mem_id)
        if not m.get().exists:
            m.set({
                "membership_id": mem_id, "tenant_id": "org_alpha_workspace",
                "user_id": uid, "role": role, "status": "active", "created_at": now,
            })


def _fs_get_or_create_user(db, uid: str, email: str, display_name: str | None = None, photo_url: str | None = None) -> dict[str, Any]:
    now = _now()
    ref = db.collection(COL_USERS).document(uid)
    doc = ref.get()
    if doc.exists:
        updates: dict[str, Any] = {"last_login_at": now}
        if display_name:
            updates["display_name"] = display_name
        ref.update(updates)
        data = doc.to_dict()
        data.update(updates)
        return data

    is_first = len(db.collection(COL_USERS).limit(1).get()) == 0
    name = display_name or email.split("@")[0].capitalize()
    user_data = {
        "user_id": uid, "email": email.lower(), "display_name": name,
        "photo_url": photo_url, "is_superadmin": is_first,
        "status": "active", "created_at": now, "last_login_at": now,
    }
    ref.set(user_data)
    tid = f"org_{uuid.uuid4().hex[:12]}"
    org_name = "Primary Security Workspace" if is_first else f"{name}'s Organization"
    db.collection(COL_TENANTS).document(tid).set({
        "tenant_id": tid, "name": org_name, "created_by": uid, "status": "active", "created_at": now,
    })
    mid = f"mem_{uuid.uuid4().hex[:12]}"
    db.collection(COL_MEMBERS).document(mid).set({
        "membership_id": mid, "tenant_id": tid, "user_id": uid, "role": "ADMIN", "status": "active", "created_at": now,
    })
    return user_data


def _fs_get_user_by_id(db, uid: str) -> dict[str, Any] | None:
    doc = db.collection(COL_USERS).document(uid).get()
    return doc.to_dict() if doc.exists else None


def _fs_get_user_by_email(db, email: str) -> dict[str, Any] | None:
    res = db.collection(COL_USERS).where("email", "==", email.strip().lower()).limit(1).get()
    return res[0].to_dict() if res else None


def _fs_list_all_users(db) -> list[dict[str, Any]]:
    docs = db.collection(COL_USERS).order_by("created_at", direction="DESCENDING").get()
    return [d.to_dict() for d in docs]


def _fs_update_user_status(db, uid: str, status: str) -> bool:
    if status not in ("active", "disabled"):
        return False
    db.collection(COL_USERS).document(uid).update({"status": status})
    return True


def _fs_set_user_superadmin(db, uid: str, is_superadmin: bool) -> bool:
    db.collection(COL_USERS).document(uid).update({"is_superadmin": is_superadmin})
    return True


def _fs_create_tenant(db, name: str, created_by: str) -> dict[str, Any]:
    now = _now()
    tid = f"org_{uuid.uuid4().hex[:12]}"
    mid = f"mem_{uuid.uuid4().hex[:12]}"
    data = {
        "tenant_id": tid, "name": name.strip(), "created_by": created_by,
        "status": "active", "created_at": now,
    }
    db.collection(COL_TENANTS).document(tid).set(data)
    db.collection(COL_MEMBERS).document(mid).set({
        "membership_id": mid, "tenant_id": tid, "user_id": created_by,
        "role": "ADMIN", "status": "active", "created_at": now,
    })
    return data


def _fs_get_tenant_by_id(db, tenant_id: str) -> dict[str, Any] | None:
    doc = db.collection(COL_TENANTS).document(tenant_id).get()
    return doc.to_dict() if doc.exists else None


def _fs_list_tenants_for_user(db, user_id: str, is_superadmin: bool = False) -> list[dict[str, Any]]:
    if is_superadmin:
        docs = db.collection(COL_TENANTS).order_by("created_at", direction="DESCENDING").get()
        return [d.to_dict() for d in docs]
    mems = db.collection(COL_MEMBERS).where("user_id", "==", user_id).where("status", "==", "active").get()
    result = []
    for m in mems:
        md = m.to_dict()
        t = _fs_get_tenant_by_id(db, md["tenant_id"])
        if t and t.get("status") == "active":
            t["role"] = md.get("role")
            result.append(t)
    return result


def _fs_list_all_tenants(db) -> list[dict[str, Any]]:
    result = []
    for doc in db.collection(COL_TENANTS).order_by("created_at", direction="DESCENDING").get():
        data = doc.to_dict()
        mems = db.collection(COL_MEMBERS).where("tenant_id", "==", data["tenant_id"]).get()
        scans = db.collection(COL_SCANS).where("tenant_id", "==", data["tenant_id"]).get()
        data["member_count"] = len(mems)
        data["scan_count"] = len(scans)
        result.append(data)
    return result


def _fs_update_tenant_status(db, tenant_id: str, status: str) -> bool:
    if status not in ("active", "suspended"):
        return False
    db.collection(COL_TENANTS).document(tenant_id).update({"status": status})
    return True


def _fs_update_tenant_name(db, tenant_id: str, name: str) -> bool:
    db.collection(COL_TENANTS).document(tenant_id).update({"name": name.strip()})
    return True


def _fs_get_tenant_membership(db, tenant_id: str, user_id: str) -> dict[str, Any] | None:
    res = db.collection(COL_MEMBERS).where("tenant_id", "==", tenant_id).where("user_id", "==", user_id).limit(1).get()
    if not res:
        return None
    mem = res[0].to_dict()
    t = _fs_get_tenant_by_id(db, tenant_id)
    if t:
        mem["tenant_name"] = t.get("name")
        mem["tenant_status"] = t.get("status")
    return mem


def _fs_list_tenant_members(db, tenant_id: str) -> list[dict[str, Any]]:
    mems = db.collection(COL_MEMBERS).where("tenant_id", "==", tenant_id).order_by("created_at").get()
    result = []
    for m in mems:
        md = m.to_dict()
        u = _fs_get_user_by_id(db, md["user_id"])
        if u:
            md.update({
                "email": u.get("email"), "display_name": u.get("display_name"),
                "photo_url": u.get("photo_url"), "last_login_at": u.get("last_login_at"),
                "joined_at": md.get("created_at"),
            })
        result.append(md)
    return result


def _fs_add_tenant_member(db, tenant_id: str, user_id: str, role: str = "DEV") -> dict[str, Any] | None:
    if role not in ("ADMIN", "DEV", "CLIENT"):
        return None
    now = _now()
    existing = db.collection(COL_MEMBERS).where("tenant_id", "==", tenant_id).where("user_id", "==", user_id).limit(1).get()
    if existing:
        existing[0].reference.update({"role": role, "status": "active"})
        d = existing[0].to_dict()
        d["role"] = role
        d["status"] = "active"
        return d
    mid = f"mem_{uuid.uuid4().hex[:12]}"
    mem = {
        "membership_id": mid, "tenant_id": tenant_id, "user_id": user_id,
        "role": role, "status": "active", "created_at": now,
    }
    db.collection(COL_MEMBERS).document(mid).set(mem)
    return mem


def _fs_update_tenant_member_role(db, tenant_id: str, user_id: str, new_role: str) -> bool:
    if new_role not in ("ADMIN", "DEV", "CLIENT"):
        return False
    res = db.collection(COL_MEMBERS).where("tenant_id", "==", tenant_id).where("user_id", "==", user_id).limit(1).get()
    if res:
        res[0].reference.update({"role": new_role})
        return True
    return False


def _fs_update_tenant_member_status(db, tenant_id: str, user_id: str, status: str) -> bool:
    if status not in ("active", "disabled"):
        return False
    res = db.collection(COL_MEMBERS).where("tenant_id", "==", tenant_id).where("user_id", "==", user_id).limit(1).get()
    if res:
        res[0].reference.update({"status": status})
        return True
    return False


def _fs_remove_tenant_member(db, tenant_id: str, user_id: str) -> bool:
    res = db.collection(COL_MEMBERS).where("tenant_id", "==", tenant_id).where("user_id", "==", user_id).limit(1).get()
    for doc in res:
        doc.reference.delete()
    return True


def _fs_record_scan_ownership(db, scan_id: str, tenant_id: str, created_by: str) -> bool:
    try:
        db.collection(COL_SCANS).document(scan_id).set({
            "scan_id": scan_id, "tenant_id": tenant_id, "created_by": created_by, "created_at": _now(),
        })
        return True
    except Exception as exc:
        logger.error("_fs_record_scan_ownership: %s", exc)
        return False


def _fs_get_scan_ownership(db, scan_id: str) -> dict[str, Any] | None:
    doc = db.collection(COL_SCANS).document(scan_id).get()
    return doc.to_dict() if doc.exists else None


def _fs_list_scans_for_tenant(db, tenant_id: str) -> list[str]:
    docs = db.collection(COL_SCANS).where("tenant_id", "==", tenant_id).order_by("created_at", direction="DESCENDING").get()
    return [d.to_dict().get("scan_id", d.id) for d in docs]


def _fs_log_audit_event(db, actor_user_id, actor_email, tenant_id, action,
                        resource_type=None, resource_id=None, result="success",
                        ip_address=None, details=None) -> None:
    eid = f"audit_{uuid.uuid4().hex[:16]}"
    try:
        db.collection(COL_AUDIT).document(eid).set({
            "id": eid, "timestamp": _now(), "actor_user_id": actor_user_id,
            "actor_email": actor_email, "tenant_id": tenant_id, "action": action,
            "resource_type": resource_type, "resource_id": resource_id,
            "result": result, "ip_address": ip_address, "details": details,
        })
    except Exception as exc:
        logger.error("_fs_log_audit_event: %s", exc)


def _fs_list_audit_logs(db, tenant_id=None, limit=100) -> list[dict[str, Any]]:
    q = db.collection(COL_AUDIT).order_by("timestamp", direction="DESCENDING").limit(limit)
    if tenant_id:
        q = q.where("tenant_id", "==", tenant_id)
    return [d.to_dict() for d in q.get()]


# ===========================================================================
#  PUBLIC API (HYBRID ROUTER WITH ZERO-DOWNTIME FALLBACK)
# ===========================================================================

def init_db() -> None:
    """Initialize database — initializes SQLite baseline and syncs Firestore if available."""
    try:
        _sqlite_init_db()
        logger.info("SQLite storage initialized at: %s", DB_PATH)
    except Exception as exc:
        logger.error("SQLite init error: %s", exc)

    fs = _get_firestore()
    if fs is not None:
        try:
            _fs_seed_demo(fs)
            logger.info("Firestore storage initialized and demo accounts verified.")
        except Exception as exc:
            logger.warning("Firestore demo seeding warning: %s", exc)


def seed_demo_accounts() -> None:
    _sqlite_seed_demo()
    fs = _get_firestore()
    if fs is not None:
        try:
            _fs_seed_demo(fs)
        except Exception as exc:
            logger.debug("Firestore seed_demo: %s", exc)


def get_or_create_user(uid: str, email: str, display_name: str | None = None, photo_url: str | None = None) -> dict[str, Any]:
    fs = _get_firestore()
    if fs is not None:
        try:
            user = _fs_get_or_create_user(fs, uid, email, display_name, photo_url)
            # Also sync to SQLite for offline resilience
            try:
                _sqlite_get_or_create_user(uid, email, display_name, photo_url)
            except Exception:
                pass
            return user
        except Exception as exc:
            logger.warning("Firestore get_or_create_user error, falling back to SQLite: %s", exc)
    return _sqlite_get_or_create_user(uid, email, display_name, photo_url)


def get_user_by_id(uid: str) -> dict[str, Any] | None:
    fs = _get_firestore()
    if fs is not None:
        try:
            user = _fs_get_user_by_id(fs, uid)
            if user:
                return user
        except Exception as exc:
            logger.debug("Firestore get_user_by_id error: %s", exc)
    return _sqlite_get_user_by_id(uid)


def get_user_by_email(email: str) -> dict[str, Any] | None:
    fs = _get_firestore()
    if fs is not None:
        try:
            user = _fs_get_user_by_email(fs, email)
            if user:
                return user
        except Exception as exc:
            logger.debug("Firestore get_user_by_email error: %s", exc)
    return _sqlite_get_user_by_email(email)


def list_all_users() -> list[dict[str, Any]]:
    fs = _get_firestore()
    if fs is not None:
        try:
            return _fs_list_all_users(fs)
        except Exception as exc:
            logger.debug("Firestore list_all_users error: %s", exc)
    return _sqlite_list_all_users()


def update_user_status(uid: str, status: str) -> bool:
    fs = _get_firestore()
    if fs is not None:
        try:
            _fs_update_user_status(fs, uid, status)
        except Exception as exc:
            logger.debug("Firestore update_user_status error: %s", exc)
    return _sqlite_update_user_status(uid, status)


def set_user_superadmin(uid: str, is_superadmin: bool) -> bool:
    fs = _get_firestore()
    if fs is not None:
        try:
            _fs_set_user_superadmin(fs, uid, is_superadmin)
        except Exception as exc:
            logger.debug("Firestore set_user_superadmin error: %s", exc)
    return _sqlite_set_user_superadmin(uid, is_superadmin)


def create_tenant(name: str, created_by: str) -> dict[str, Any]:
    fs = _get_firestore()
    if fs is not None:
        try:
            t = _fs_create_tenant(fs, name, created_by)
            try:
                _sqlite_create_tenant(name, created_by)
            except Exception:
                pass
            return t
        except Exception as exc:
            logger.warning("Firestore create_tenant error: %s", exc)
    return _sqlite_create_tenant(name, created_by)


def get_tenant_by_id(tenant_id: str) -> dict[str, Any] | None:
    fs = _get_firestore()
    if fs is not None:
        try:
            t = _fs_get_tenant_by_id(fs, tenant_id)
            if t:
                return t
        except Exception as exc:
            logger.debug("Firestore get_tenant_by_id error: %s", exc)
    return _sqlite_get_tenant_by_id(tenant_id)


def list_tenants_for_user(user_id: str, is_superadmin: bool = False) -> list[dict[str, Any]]:
    fs = _get_firestore()
    if fs is not None:
        try:
            res = _fs_list_tenants_for_user(fs, user_id, is_superadmin)
            if res:
                return res
        except Exception as exc:
            logger.debug("Firestore list_tenants_for_user error: %s", exc)
    return _sqlite_list_tenants_for_user(user_id, is_superadmin)


def list_all_tenants() -> list[dict[str, Any]]:
    fs = _get_firestore()
    if fs is not None:
        try:
            return _fs_list_all_tenants(fs)
        except Exception as exc:
            logger.debug("Firestore list_all_tenants error: %s", exc)
    return _sqlite_list_all_tenants()


def update_tenant_status(tenant_id: str, status: str) -> bool:
    fs = _get_firestore()
    if fs is not None:
        try:
            _fs_update_tenant_status(fs, tenant_id, status)
        except Exception as exc:
            logger.debug("Firestore update_tenant_status error: %s", exc)
    return _sqlite_update_tenant_status(tenant_id, status)


def update_tenant_name(tenant_id: str, name: str) -> bool:
    fs = _get_firestore()
    if fs is not None:
        try:
            _fs_update_tenant_name(fs, tenant_id, name)
        except Exception as exc:
            logger.debug("Firestore update_tenant_name error: %s", exc)
    return _sqlite_update_tenant_name(tenant_id, name)


def get_tenant_membership(tenant_id: str, user_id: str) -> dict[str, Any] | None:
    fs = _get_firestore()
    if fs is not None:
        try:
            m = _fs_get_tenant_membership(fs, tenant_id, user_id)
            if m:
                return m
        except Exception as exc:
            logger.debug("Firestore get_tenant_membership error: %s", exc)
    return _sqlite_get_tenant_membership(tenant_id, user_id)


def list_tenant_members(tenant_id: str) -> list[dict[str, Any]]:
    fs = _get_firestore()
    if fs is not None:
        try:
            return _fs_list_tenant_members(fs, tenant_id)
        except Exception as exc:
            logger.debug("Firestore list_tenant_members error: %s", exc)
    return _sqlite_list_tenant_members(tenant_id)


def add_tenant_member(tenant_id: str, user_id: str, role: str = "DEV") -> dict[str, Any] | None:
    fs = _get_firestore()
    if fs is not None:
        try:
            m = _fs_add_tenant_member(fs, tenant_id, user_id, role)
            try:
                _sqlite_add_tenant_member(tenant_id, user_id, role)
            except Exception:
                pass
            return m
        except Exception as exc:
            logger.warning("Firestore add_tenant_member error: %s", exc)
    return _sqlite_add_tenant_member(tenant_id, user_id, role)


def update_tenant_member_role(tenant_id: str, user_id: str, new_role: str) -> bool:
    fs = _get_firestore()
    if fs is not None:
        try:
            _fs_update_tenant_member_role(fs, tenant_id, user_id, new_role)
        except Exception as exc:
            logger.debug("Firestore update_tenant_member_role error: %s", exc)
    return _sqlite_update_tenant_member_role(tenant_id, user_id, new_role)


def update_tenant_member_status(tenant_id: str, user_id: str, status: str) -> bool:
    fs = _get_firestore()
    if fs is not None:
        try:
            _fs_update_tenant_member_status(fs, tenant_id, user_id, status)
        except Exception as exc:
            logger.debug("Firestore update_tenant_member_status error: %s", exc)
    return _sqlite_update_tenant_member_status(tenant_id, user_id, status)


def remove_tenant_member(tenant_id: str, user_id: str) -> bool:
    fs = _get_firestore()
    if fs is not None:
        try:
            _fs_remove_tenant_member(fs, tenant_id, user_id)
        except Exception as exc:
            logger.debug("Firestore remove_tenant_member error: %s", exc)
    return _sqlite_remove_tenant_member(tenant_id, user_id)


def record_scan_ownership(scan_id: str, tenant_id: str, created_by: str) -> bool:
    fs = _get_firestore()
    if fs is not None:
        try:
            _fs_record_scan_ownership(fs, scan_id, tenant_id, created_by)
        except Exception as exc:
            logger.debug("Firestore record_scan_ownership error: %s", exc)
    return _sqlite_record_scan_ownership(scan_id, tenant_id, created_by)


def get_scan_ownership(scan_id: str) -> dict[str, Any] | None:
    fs = _get_firestore()
    if fs is not None:
        try:
            s = _fs_get_scan_ownership(fs, scan_id)
            if s:
                return s
        except Exception as exc:
            logger.debug("Firestore get_scan_ownership error: %s", exc)
    return _sqlite_get_scan_ownership(scan_id)


def list_scans_for_tenant(tenant_id: str) -> list[str]:
    fs = _get_firestore()
    if fs is not None:
        try:
            scans = _fs_list_scans_for_tenant(fs, tenant_id)
            if scans:
                return scans
        except Exception as exc:
            logger.debug("Firestore list_scans_for_tenant error: %s", exc)
    return _sqlite_list_scans_for_tenant(tenant_id)


def log_audit_event(actor_user_id, actor_email, tenant_id, action,
                    resource_type=None, resource_id=None, result="success",
                    ip_address=None, details=None) -> None:
    fs = _get_firestore()
    if fs is not None:
        try:
            _fs_log_audit_event(fs, actor_user_id, actor_email, tenant_id, action,
                                resource_type, resource_id, result, ip_address, details)
        except Exception as exc:
            logger.debug("Firestore log_audit_event error: %s", exc)
    _sqlite_log_audit_event(actor_user_id, actor_email, tenant_id, action,
                            resource_type, resource_id, result, ip_address, details)


def list_audit_logs(tenant_id=None, limit=100) -> list[dict[str, Any]]:
    fs = _get_firestore()
    if fs is not None:
        try:
            logs = _fs_list_audit_logs(fs, tenant_id, limit)
            if logs:
                return logs
        except Exception as exc:
            logger.debug("Firestore list_audit_logs error: %s", exc)
    return _sqlite_list_audit_logs(tenant_id, limit)
