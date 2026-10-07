# 🎙️ IqAudi360 — Teacher's Master Presentation Script (G-Meet Guide)

> **FOR YOUR EYES ONLY (Presenter Cheatsheet)**  
> Indha guide nee G-Meet-la screen share panni teammates-ku teach pannumbothu pakkathula vechikuradhuku.  
> Exactly enna pesanum, enna screen kaatanum, teammates tricky questions keta epdi pro maari answer panradhu nu ellame Tanglish-la step-by-step irukku!

---

## ⏱️ Meeting Outline (Total: 25 - 30 Mins)

| Phase | Topic | Time | Screen to Share |
|---|---|---|---|
| **Part 1** | Project Intro & Core Problem | 4 mins | Landing Page (`home.iqaudi.com`) |
| **Part 2** | Architecture & SaaS Transformation | 6 mins | Architecture Diagram / VS Code |
| **Part 3** | Multi-Tenant & RBAC Live Demo | 8 mins | Browser (Alpha vs Beta login) |
| **Part 4** | Autonomous Scan Execution | 5 mins | New Scan & Live Terminal |
| **Part 5** | Server Hosting & Linux Commands | 5 mins | SSH Terminal |
| **Part 6** | Q&A Handling (Pro Answers) | 5 mins | Open Discussion |

---

## 🎬 PART 1: Project Intro & Problem Statement (4 Mins)

### 🖥️ Screen to Show:
Browser-la `http://home.iqaudi.com` open panni vechikonga.

### 🗣️ Enna Pesanum (Script):
> *"Hey team! Innikki session-la namma develop panni deploy panniruka **iqAudi360** security platform pathi paaka porom.*
> 
> *Market-la already Nessus, Burp Suite, OWASP ZAP maari tools irukku. Aana adhu ellame static signatures use pannum — thousands of false positives tharum, manual verification theva padum.*
> 
> *Namma build pannirukura **iqAudi360** oru **Autonomous AI Multi-Agent Security Platform**. Idhula LLM agents isolated Docker container kulla run aagi, target application-oda source code & live endpoints-ah real pentester maari analyze panni, **zero false positive** verifications oda enterprise reports generate pannum.*
> 
> *Namma engine mattum illama, idhai oru **production-grade Multi-Tenant SaaS platform**-ah build pannirukom with enterprise RBAC, live streaming console, and dedicated server infrastructure."*

---

## 🏛️ PART 2: System Architecture & Folder Layout (6 Mins)

### 🖥️ Screen to Show:
VS Code folder structure open pannunga (`iqAudi360/`).

### 🗣️ Enna Pesanum (Script):
> *"Team, namma codebase-ah 3 distinct layers-ah structure pannirukom:*
> 
> 1. **Core AI Engine (`strix/agents/` & `strix/tools/`):**
>    * Idhula dhaan AI pentesting agents (Recon, Code Analyzer, Web Exploit, Validator) irukku.
>    * Isolated Docker container runtime (`strix/runtime/`) kulla run aagum so exploit test pandra sandbox safe-ah irukum.
> 
> 2. **Process Orchestrator (`strix/gui/scanner.py`):**
>    * Background scans manage panna **ScanManager Singleton** design pattern use pannirukom.
>    * Server-la multiple HTTP requests vandhaalum, in-memory single process instance dhaan active background jobs-ah track pannum.
> 
> 3. **Enterprise Web Console & Multi-Tenant RBAC (`strix/gui/auth/`):**
>    * Multi-tenancy, user session authentication, and permission matrix ellame modular architecture-la build pannirukom.
>    * `db.py` SQLite baseline storage and hybrid router vechu fast-ah run aagum."*

💡 **Pro Tip for You:** Teammates kitta "Strix" nu direct-ah emphasize panna venaam. *"Namma autonomous AI engine and tools layer"* nu sollunga.

---

## 🏢 PART 3: Multi-Tenant & RBAC Live Walkthrough (8 Mins)

### 🖥️ Screen to Show:
Two Browser Windows (or 1 Normal + 1 Incognito).

### 🗣️ Enna Pesanum & Enna Pannanum (Step-by-Step):

#### 1. Show SuperAdmin Power:
- Login: `superadmin@iqaudi360.com` / `pass@12345`
- Top bar-la iruka **Organization Switcher** kaatunga (`Enterprise Org Alpha` & `Beta Corp`).
- *"SuperAdmin can see all organizations, system audit logs, and manage platform users."*

#### 2. Demonstrate Multi-Tenant Isolation (The "WOW" Moment!):
- Window 1: Login as **Bob Admin** (`admin@beta.com` / `pass@12345`).
- Kaatunga: Beta Corp-la Scans count **0**, Findings **0**.
- Window 2: Login as **Alice Admin** (`admin@alpha.com` / `pass@12345`).
- Kaatunga: Alpha Org-la **15 Scans**, historical findings iruku.
- **Punch dialogue:** *"Notice that Beta Corp cannot see even a single scan or vulnerability of Alpha Org. Total data isolation enforced at the database query level!"*

#### 3. Explain the 4 Roles:
- **SUPERADMIN:** Full platform master.
- **ADMIN:** Organization manager — team invite pannalaam, audit logs paakalaam, scans run pannalaam.
- **DEV:** Technical engineer — scans run pannalaam, **Live Terminal stream** paakalaam, scan stop pannalaam, and Client roles add pannalaam.
- **CLIENT:** Executive/auditor — read-only view with scan launch ability, sensitive raw terminal logs blocked.

#### 4. Explain Registration Flow:
- Show `/register`: *"Pudhu user sign up pannumbothu avanga `UNASSIGNED` state-la irupaanga. Organization Admin avangala select panni role kudutha dhaan workspace access kidaikkum. SaaS security best practice!"*

---

## ⚡ PART 4: Live Scan Execution (5 Mins)

### 🖥️ Screen to Show:
`New Scan` Page -> Live Scan Console.

### 🗣️ Enna Pesanum & Enna Pannanum:
1. Click **New Scan**.
2. Target: Edhadhu URL (e.g. `http://example.com` or local target).
3. Mode: Select **Quick Scan**.
4. Check *"I certify I am authorized to test"* -> Click **Start Autonomous Scan**.
5. Live Console open aagum:
   - **Stopwatch:** Active scan duration.
   - **Reasoning Cards:** AI agent enna step yosikudhu nu real-time-la varum.
   - **Live Terminal (SSE):** Real-time server-sent events stream.
   - Show the **Stop Scan** button.

---

## 💻 PART 5: Server Hosting & Commands Cheatsheet (5 Mins)

### 🖥️ Screen to Show:
SSH Terminal connected to `ubuntu@103.118.158.92`.

### 🗣️ Enna Pesanum:
> *"Namma platform production-la Ubuntu cloud server-la host aagirukku. Architecture idhudhaan:*
> - **Domain Routing:** `home.iqaudi.com` -> Nginx Reverse Proxy (Port 80)
> - **WSGI App Server:** Gunicorn running on port 4100
> - **Systemd Service:** `iqaudi360.service` handles process lifecycle"

### Live-ah Terminal-la indha 3 cmds run panni kaatunga:

1. **Check Status:**
   ```bash
   sudo systemctl status iqaudi360
   ```
   *(Kaatunga: Active (running) nu green-la irukku)*

2. **View Live Logs:**
   ```bash
   sudo journalctl -u iqaudi360 -f
   ```
   *(Browser-la page click panni logs real-time-la stream aaguradha kaatunga, then Ctrl+C)*

3. **Deploy Updates:**
   ```bash
   cd /home/ubuntu/iqaudi360 && git pull && sudo systemctl restart iqaudi360
   ```
   *(Explain: "Namma repo-la push pandra code-ah server-la deploy panna idhu dhaan standard command")*

---

## 🧠 PART 6: Tricky Questions & Pro Answers (Trap Defense!)

Teammates keka koodiya questions & neenga solla vendiya confident answers:

### Q1: "Gunicorn-la yen `-w 1` potrukkom? Multiple workers pota innum fast-ah irukaadhe?"
> **Your Answer:** *"Romba good question! Namma `ScanManager` background scans-ah in-memory singleton registry-la handle pannudhu. Multiple workers potta memory split aagi, worker A scan start pannumbothu worker B kitta 'Scan not found 404' error varum. Adhanaala `-w 1` with `--threads 8` potrukom — idhu thread-safe concurrent web traffic-um handle pannum, single memory consistency-um preserve pannum."*

### Q2: "Beta Corp user Alpha Org scan ID URL-la direct-ah type panna paaka mudiyuma?"
> **Your Answer:** *"No, mudiyadhu! Namma backend-la `@require_tenant_scan_access` decorator enforce pannirukom. Scan ID direct-ah adichaalum database-la tenant ownership check panni 403 Forbidden throw pannum."*

### Q3: "Docker container engayavathu leak aagi server-ah crash panniduma?"
> **Your Answer:** *"No! AI agents direct-ah host server-la run aagala. Dedicated isolated Docker sandbox container kulla network and resource limits oda run aagudhu. Security-wise completely isolated."*

### Q4: "Password security epdi handle aagudhu?"
> **Your Answer:** *"Passwords plaintext-la save aagala. Werkzeug security package oda scrypt cryptographic hashing algorithms use panni SQLite database-la store aagudhu."*

---

## 🏁 Wrap-Up Line:
> *"Avlo dhaan team! Code repo-la `TEAMMATE_DEVELOPER_HANDBOOK.md` potruken, daily commands & architecture adhula iruku. Any questions?"*

*(Idhai follow pannina meeting 100% blockbuster hit bro!)*
