# 📘 iqAudi360 — Team Developer & Operations Handbook

> **Audience:** Engineering Team, DevOps, and Platform Contributors  
> **Platform Version:** iqAudi360 v1.6.2 Enterprise SaaS  
> **Target Production Host:** `home.iqaudi.com` / `103.118.158.92`

---

## 1. Executive Summary

**iqAudi360** is an autonomous AI-driven penetration testing platform designed to execute non-destructive, zero-false-positive security assessments across web applications, network targets, source code, and cloud assets.

Unlike traditional signature-based scanners, iqAudi360 pairs Large Language Models (LLMs) with safe, isolated Docker runtime sandboxes. Autonomous agents navigate targets, analyze source code, formulate hypothesis-driven attack vectors, and verify vulnerabilities with proof-of-concept exploits before generating executive and technical reports.

---

## 2. System Architecture

```
[Web Browsers / REST Clients]
             │
             ▼
   [Nginx Reverse Proxy]
   - Port 80 / 443
   - OWASP Security Headers (CSP, X-Frame, XSS)
   - Static file delivery (/static/ -> css, js, icons)
             │
             ▼ (Reverse proxy to 127.0.0.1:4100)
    [Gunicorn WSGI Server]
   - 1 Worker process (-w 1) with 8 Threads (--threads 8)
   - Preserves in-memory singleton consistency
             │
             ▼
      [Flask Core GUI]
   ┌───────────────────────┬────────────────────────┐
   │ Auth & Multi-Tenancy  │ ScanManager Singleton  │
   │ - SQLite / Hybrid DB  │ - Active Job Tracker   │
   │ - 4-Tier RBAC Matrix  │ - Subprocess Launcher  │
   │ - Session & Auth API  │ - Live SSE Log Stream  │
   └───────────────────────┴────────────────────────┘
             │
             ▼
    [iqAudi360 AI Engine]
   - Autonomous Agent Graph (Recon, Analysis, Exploit, Report)
   - Sandboxed Docker Container Runtime
   - Structured Findings Catalog & SARIF / PDF Generators
```

---

## 3. Directory Layout

| Directory / File | Description |
|---|---|
| `strix/agents/` | Agent decision trees, prompts, and reasoning workflows |
| `strix/tools/` | Pentesting utilities (port scan, browser automation, proxy) |
| `strix/runtime/` | Docker sandbox container management and isolation barriers |
| `strix/report/` | Assessment reporting engine (Markdown, PDF, SARIF 2.1.0) |
| `strix/gui/app.py` | Main Flask application factory, routes, and error handling |
| `strix/gui/scanner.py` | `ScanManager` singleton managing background scan jobs |
| `strix/gui/data.py` | Multi-tenant scan data filtering, stats aggregation |
| `strix/gui/auth/db.py` | Hybrid SQLite/Firestore storage for users, tenants, and logs |
| `strix/gui/auth/rbac.py` | Permission definitions and role hierarchy rules |
| `strix/gui/auth/routes.py` | Authentication, self-registration, and member management APIs |
| `strix/gui/templates/` | Jinja2 HTML templates for the security console |
| `strix/gui/static/` | CSS, UI icons, and frontend JavaScript modules |
| `deploy/nginx/` | Hardened production Nginx reverse proxy configuration |

---

## 4. Multi-Tenant Role Matrix (RBAC)

The platform enforces 4 distinct roles with strict server-side authorization:

| Capability | 👑 SUPERADMIN | ⚡ ADMIN | 💻 DEV | 📊 CLIENT |
|---|:---:|:---:|:---:|:---:|
| **Launch Security Scans** | ✅ | ✅ | ✅ | ✅ |
| **Abort Running Scan** | ✅ | ✅ | ✅ | ❌ |
| **Live Terminal Stream** | ✅ | ✅ | ✅ | ❌ |
| **View Findings & Vulns** | ✅ | ✅ | ✅ | ✅ |
| **Download PDF/SARIF** | ✅ | ✅ | ✅ | ✅ |
| **Add / Invite Members** | ✅ (All roles) | ✅ (Dev & Client) | ✅ (Client only) | ❌ |
| **Edit Member Roles** | ✅ (All roles) | ✅ (Dev & Client) | ❌ | ❌ |
| **Organization Settings**| ✅ (Global) | ✅ (Own tenant) | ❌ | ❌ |
| **View Audit Logs** | ✅ (All tenants)| ✅ (Own tenant) | ❌ | ❌ |
| **System Administration**| ✅ | ❌ | ❌ | ❌ |

---

## 5. Standard Environments & Access URLs

| Environment | URL | Purpose |
|---|---|---|
| **Primary Dashboard** | `http://home.iqaudi.com` | Production Web Application |
| **Secure Platform Portal** | `http://secure.iqaudi.com` | Direct secure access point |
| **API Endpoint** | `http://api.iqaudi.com` | REST API gateway |

### Pre-Seeded Evaluation Accounts:
*(Password for all seeded accounts: `pass@12345`)*

- **Platform SuperAdmin:** `superadmin@iqaudi360.com`
- **Tenant 1 (Enterprise Org Alpha):**
  - Org Admin: `admin@alpha.com`
  - Developer: `dev@alpha.com`
  - Client: `client@alpha.com`
- **Tenant 2 (Beta Corp):**
  - Org Admin: `admin@beta.com`
  - Developer: `dev@beta.com`
  - Client: `client@beta.com`

---

## 6. Daily Operations Cheatsheet

### 1. SSH Server Connection:
```bash
ssh -p 18755 ubuntu@103.118.158.92
```

### 2. Standard Code Pull & Deploy Workflow:
Always execute this sequence after pushing commits to GitHub `main`:
```bash
cd /home/ubuntu/iqaudi360
git pull
sudo systemctl restart iqaudi360
```

### 3. Check Service Status:
```bash
sudo systemctl status iqaudi360
```

### 4. Tail Real-Time Application Logs:
```bash
sudo journalctl -u iqaudi360 -f
```

### 5. Test and Reload Nginx:
```bash
sudo nginx -t
sudo systemctl reload nginx
```

---

## 7. Developer Guidelines & Architecture Notes

### Why Gunicorn uses `-w 1 --threads 8`:
The `ScanManager` stores active scans in Python memory (`ScanManager.get_instance()`). If Gunicorn spawns multiple independent worker processes, background jobs registered on worker 1 would return a `404 Not Found` when polled by worker 2.  
**Rule:** Always keep `-w 1` with multiple threads (`--threads 8` or higher) to ensure consistent in-memory job coordination.

### Data Isolation Rule:
Every route that serves scan data or reports must pass the current user's `tenant_id`:
```python
tenant_id = g.current_tenant.get("tenant_id") if g.current_tenant else "__NO_TENANT__"
scans = list_all_scans(tenant_id=tenant_id)
```
Never call `list_all_scans(None)` for non-superadmin users.

---

## 8. Troubleshooting Common Issues

| Symptom | Cause | Solution |
|---|---|---|
| **HTTP 502 Bad Gateway** | Gunicorn service is down or crashed | Run `sudo systemctl restart iqaudi360` and inspect `journalctl -u iqaudi360 -n 50`. |
| **Static files 403 Forbidden** | Nginx permission mismatch on static folder | Run `sudo chmod o+x /home/ubuntu` and `sudo chmod -R o+r /home/ubuntu/iqaudi360/strix/gui/static/`. |
| **Scan shows "Failed to start"** | Missing API key or Docker daemon stopped | Check `systemctl status docker` and verify `IQAUDI360_LLM` and `LLM_API_KEY` in systemd service file. |
| **New user cannot see scans** | User is in `UNASSIGNED` state | Have the Org Admin go to **Organizations & Members** and add the user's email with a role. |

---
*iqAudi360 Engineering Manual • Version 1.6.2 • Keep Confidential*
