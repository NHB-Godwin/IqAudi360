# 🛡️ iqAudi360 — Teammates Project Architecture & Handover Guide

> **Prepared for:** Team Knowledge Sharing & Live Google Meet Walkthrough  
> **Platform:** iqAudi360 Autonomous AI Pentesting & Security Operations Suite  
> **Confidential & Proprietary**

---

## 🎯 1. Project Overview & Platform Purpose

### Enna Idhu? (What is iqAudi360?)
**iqAudi360** is an enterprise-grade, autonomous AI penetration testing platform. 
Traditional security scanners (like Nessus or OWASP ZAP) only send pre-configured attack strings and generate hundreds of false positives. 

**iqAudi360 works differently:**
- It uses **LLM-driven autonomous AI agents** (DeepSeek / Claude / GPT) running in an isolated Docker sandbox.
- AI analyzes code, tests live web applications, explores attack surfaces, verifies if a bug is truly exploitable, and writes professional remediation reports with **zero false positives**.
- We transformed this engine into a **complete SaaS product** featuring multi-tenant isolation, role-based access control (RBAC), and web dashboards.

---

## 🏛️ 2. Platform Architecture & Code Structure

A quick guide to how the project is organized inside the codebase:

```
iqAudi360/
├── strix/
│   ├── agents/          # Autonomous AI pentesting agents & decision graphs
│   ├── tools/           # Pentesting tools (Proxy, Browser, Terminal, Port scanners)
│   ├── runtime/         # Isolated Docker sandbox for safe exploit execution
│   ├── report/          # Report engines (Markdown, PDF, SARIF 2.1.0 output)
│   ├── gui/             # Web Application (Flask + Gunicorn + Jinja2)
│   │   ├── app.py       # Main Flask factory, routes & error handlers
│   │   ├── scanner.py   # ScanManager singleton (manages active scan processes)
│   │   ├── data.py      # Scan data aggregation & multi-tenant filtering
│   │   ├── templates/   # UI HTML templates (Dashboard, Scans, Findings, Reports)
│   │   ├── static/      # CSS styles, SVG assets, client-side JS
│   │   └── auth/        # Multi-Tenant & RBAC authentication engine
│   │       ├── db.py    # Hybrid SQLite/Firestore tenant storage & credentials
│   │       ├── rbac.py  # Permission matrix & role evaluation rules
│   │       ├── routes.py# Auth routes (login, register, org management)
│   │       └── decorators.py # @require_auth, @require_role, context injection
```

### Key Architectural Concepts to Explain:
1. **Separation of Engine & Web GUI**:
   The security engine executes independently in the background, while the Web GUI (`strix/gui`) provides real-time streaming, monitoring, and control via Server-Sent Events (SSE).
2. **ScanManager Singleton (`ScanManager.get_instance()`)**:
   In-memory process registry that tracks running scan subprocesses.  
   *(Crucial note: Gunicorn runs with `-w 1 --threads 8` so that all HTTP threads share the exact same ScanManager memory!)*

---

## 🏢 3. Multi-Tenant Architecture & RBAC System

### What is Multi-Tenancy?
In our SaaS model, multiple independent organizations (e.g., **Enterprise Org Alpha** and **Beta Corp**) share the same server and software, but **their data is completely isolated**:
- Beta Corp users **cannot** see Alpha Org's scans, vulnerabilities, or reports.
- Each scan recorded in the database is tagged with its owner `tenant_id`.

### The 4 Platform Roles & Powers Matrix:

| Feature / Action | 👑 SUPERADMIN | ⚡ ADMIN (Org Admin) | 💻 DEV (Developer) | 📊 CLIENT |
| :--- | :---: | :---: | :---: | :---: |
| **New Scan Launch** | ✅ Yes | ✅ Yes | ✅ Yes | ✅ Yes |
| **Stop Active Scan** | ✅ Yes | ✅ Yes | ✅ Yes | ❌ No |
| **Live Terminal / Agent Logs** | ✅ Full Stream | ✅ Full Stream | ✅ Full Stream | ❌ Blocked |
| **View Findings & Vulns** | ✅ Yes | ✅ Yes | ✅ Yes | ✅ Yes |
| **Download PDF/SARIF Reports** | ✅ Yes | ✅ Yes | ✅ Yes | ✅ Yes |
| **Add / Invite Members** | ✅ Any Role | ✅ Dev & Client | ✅ Client Only | ❌ No |
| **Change Member Roles** | ✅ Any Role | ✅ Dev & Client | ❌ No | ❌ No |
| **Organization Settings** | ✅ Global | ✅ Own Org | ❌ No | ❌ No |
| **Security Audit Logs** | ✅ All Orgs | ✅ Own Org | ❌ No | ❌ No |
| **Global Platform Admin** | ✅ Yes | ❌ No | ❌ No | ❌ No |

### User Lifecycle & Registration Workflow:
1. **Self-Registration (`/register`)**: New users create an account with work email & password. They enter as `UNASSIGNED`.
2. **Admin Assignment (`Organizations & Members`)**: Organization Admins or SuperAdmin invite the user's email into their organization and assign their exact role (`ADMIN`, `DEV`, or `CLIENT`).
3. **Instant Activation**: Once assigned, the user gets full tenant access corresponding to their role.

---

## 🚀 4. Server Hosting & Infrastructure Architecture

Our production server setup on Ubuntu Linux:

```
[Internet User]
       │
       ▼
[Cloud DNS: home.iqaudi.com / secure.iqaudi.com / api.iqaudi.com]
       │
       ▼
[Nginx Reverse Proxy (Port 80/443)] ── Static Assets (CSS, JS, Icons)
       │
       ▼ (Reverse proxy to 127.0.0.1:4100)
[Gunicorn WSGI Application Server (-w 1 --threads 8)]
       │
       ▼
[Flask Web App & ScanManager Engine]
       │
       ▼
[Docker Sandbox / Autonomous Agents / SQLite Database]
```

### Server Configuration Files:
- **Systemd Service**: `/etc/systemd/system/iqaudi360.service` (manages background startup, environment keys, auto-restart)
- **Nginx Config**: `/etc/nginx/sites-available/iqaudi360` (handles domains, static files, SSL, reverse proxy)
- **App Directory**: `/home/ubuntu/iqaudi360`

---

## 💻 5. Essential Commands Cheatsheet (Most Important!)

Explain these commands to teammates during the meeting:

### 1. SSH Server Login:
```bash
ssh -p 18755 ubuntu@103.118.158.92
```

### 2. Update Code & Deploy Changes (Standard Workflow):
```bash
cd /home/ubuntu/iqaudi360
git pull
sudo systemctl restart iqaudi360
```

### 3. Check Service Status & Health:
```bash
sudo systemctl status iqaudi360
```

### 4. Monitor Live Application Logs in Real-Time:
```bash
sudo journalctl -u iqaudi360 -f
```

### 5. Check / Reload Nginx Configuration:
```bash
sudo nginx -t
sudo systemctl reload nginx
```

---

## 🎤 6. Google Meet Live Demonstration Script (Step-by-Step Flow)

Use this 5-step agenda when presenting to your teammates:

1. **Step 1: Introduction (3 mins)**
   - Open `http://home.iqaudi.com`.
   - Explain the concept: *"This is iqAudi360, our autonomous AI pentesting platform. It tests web apps and APIs using autonomous AI agents."*

2. **Step 2: SuperAdmin Master View (3 mins)**
   - Log in as `superadmin@iqaudi360.com` (`pass@12345`).
   - Show the Organizations switcher (switch between **Org Alpha** and **Beta Corp**).
   - Show **Platform Users Directory** and **Audit Logs**.

3. **Step 3: Multi-Tenant Role Isolation (4 mins)**
   - Log in as **Dave Dev** (`dev@beta.com` / `pass@12345`).
   - Show how Beta Corp starts with a clean dashboard (0 scans, isolated from Alpha).
   - Show that DEV has **Live Terminal stream** access and can add **CLIENT** members.
   - Contrast with **Charlie Client** (`client@alpha.com`), who has a simplified view without raw logs.

4. **Step 4: Launching a Scan (3 mins)**
   - Click **New Scan** -> enter target URL -> Select **Quick Scan** -> Launch.
   - Show the real-time AI reasoning cards, execution log streaming, and findings counter.

5. **Step 5: Server Architecture & Git Deployment (5 mins)**
   - Open SSH terminal on screen.
   - Demonstrate `git pull && sudo systemctl restart iqaudi360`.
   - Show `systemctl status` and `journalctl -u iqaudi360 -f`.
   - Open for team questions!

---
*Created with iqAudi360 Platform Suite • Keep confidential within the engineering team.*
