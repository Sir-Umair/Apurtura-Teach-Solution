# APTURA TECH SOLUTIONS - TECHNICAL REPORT & ARCHITECTURE
**1-Month Internship Program – Batch 02 | Week 03 Task**  
**Module:** Enterprise Python Development & Architecture  
**File:** task2.md  

---

## QUESTION 01: HIGH-SCALABILITY ARCHITECTURAL REDESIGN

### 1. Scale Requirements Overview
- **Target Scale:** 500 Enterprise Companies (Tenants)
- **Employee Density:** >10,000 Employees per Company
- **Total Active User Base:** **5,000,000+ Active Employees**
- **Peak Traffic Scenario:** Shift starts (08:30 AM – 09:15 AM) generating ~5 million concurrent clock-in events (~50,000 requests/second burst).

---

### 2. Enterprise Architectural Blueprint

```
+-----------------------------------------------------------------------------------+
|                                 CLIENT APPLICATIONS                               |
|        Mobile Apps (iOS/Android)  |  Web Portals  |  Biometric IoT Devices        |
+------------------------------------------+----------------------------------------+
                                           |
                                   [ TLS / HTTPS ]
                                           v
+-----------------------------------------------------------------------------------+
|                         API GATEWAY & LOAD BALANCER LAYER                         |
|      Kong / NGINX Ingress Controller + AWS Application Load Balancers (ALB)      |
|           - Rate Limiting   - JWT Auth   - WAF Protection   - SSL Offloading      |
+------------------------------------------+----------------------------------------+
                                           |
    +--------------------------------------+----------------------------------+
    |                                      |                                  |
    v                                      v                                  v
+-----------------------+     +-----------------------+     +-----------------------+
| AUTH & USER SERVICE   |     | ATTENDANCE INGESTION  |     | PAYROLL ENGINE        |
| (Stateless Pods)      |     | (High-Throughput Pods)|     | (Batch & On-Demand)   |
+-----------+-----------+     +-----------+-----------+     +-----------+-----------+
            |                             |                             |
            |                             v                             v
            |                 +-----------------------+     +-----------------------+
            |                 | APACHE KAFKA MSG QUEUE|     | REDIS CACHE CLUSTER   |
            |                 | (Stream Ingestion)    |     | (Session & Metadata)  |
            |                 +-----------+-----------+     +-----------+-----------+
            |                             |                             |
            +-----------------------------+-----------------------------+
                                          |
                                          v
+-----------------------------------------------------------------------------------+
|                        DISTRIBUTED MULTI-TENANT DATABASE LAYER                    |
|       Primary-Replica PostgreSQL + CockroachDB / Cassandra for Time-Series        |
|                  - Tenant-based Database Sharding (Shard Key: Tenant_ID)          |
|                  - Row-Level Security (RLS) & Storage Isolation                   |
+-----------------------------------------------------------------------------------+
```

---

### 3. Key Architectural Pillars

1. **Multi-Tenant Database Architecture & Sharding:**
   - Shard PostgreSQL database clusters horizontally using `tenant_id`.
   - Range-partition attendance history tables by month (`attendance_2026_08`, `attendance_2026_09`).
2. **Asynchronous Event Ingestion (Apache Kafka):**
   - Clock-in requests write to an in-memory Kafka event stream instead of executing heavy synchronous database inserts during peak morning hours.
3. **Redis Distributed Caching Layer:**
   - Caches employee profiles, active shift states, and tax tables to eliminate 95% of read database load.
4. **Microservices Containerization (Kubernetes):**
   - Decouples Auth, Attendance Ingestion, Payroll Engine, and Report Exporters into independently auto-scaling pods.

---

## QUESTION 02: FIVE FAILURE SCENARIOS & RECOVERY STRATEGIES

| # | Failure Scenario | Risk Impact | Primary Safeguard | Recovery Time (RTO) | Data Loss (RPO) |
|---|------------------|-------------|-------------------|---------------------|-----------------|
| 1 | **Data File Corruption** | High | Atomic Writes + Backup Mirroring | < 5 Seconds | 0 Seconds |
| 2 | **Invalid / Malicious Input** | Medium | Strict Schema Validation & Sanitization | Immediate | 0 Seconds |
| 3 | **Concurrent Access / Race Conditions** | High | Pessimistic / Optimistic Database Locking | Automatic Retry (< 50ms) | 0 Seconds |
| 4 | **System Crash / Power Outage** | Critical | Write-Ahead Logging (WAL) & Journaling | < 30 Seconds | < 1 Second |
| 5 | **Network Interruption** | High | Offline Local Queue & Eventual Consistency | Auto-sync on Reconnect | 0 Seconds |

### Detailed Recovery Protocols

1. **Corrupted Data Files:**
   - **Atomic Writes:** Saves updates to `.tmp` file before executing atomic replacement (`os.replace`).
   - **Auto-Recovery:** Detects corrupted primary file and auto-restores state from `.bak` snapshot.

2. **Invalid Input:**
   - Restricts hours (`0.0 <= hours <= 24.0`) and sanitizes data types to prevent runtime crashes.

3. **Concurrent Access:**
   - Enforces database row locking and transaction idempotency keys to prevent duplicate clock-in records.

4. **System Crash:**
   - Uses Write-Ahead Logging (WAL) to replay journal logs on startup and restore non-committed transactions.

5. **Network Interruption:**
   - Client applications store clock-in events in local SQLite storage when offline, automatically flushing to the server once reconnected.
