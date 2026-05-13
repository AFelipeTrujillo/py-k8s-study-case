# K8s Multi-API + MySQL Learning Project

## Overview

A hands-on Kubernetes (v1.25.2) project to learn core concepts: Pods, Deployments, StatefulSets, Services (ClusterIP, NodePort), ConfigMaps, Secrets, and inter-service communication.

We create **3 FastAPI microservices** (v1, v2, v3) that connect to a **MySQL database** (StatefulSet) and expose data through a JSON endpoint.

## Architecture

```
                      ┌─────────────┐
                      │   NodePort  │
                      │  (30081-83) │
                      └──────┬──────┘
                             │
              ┌──────────────┼──────────────┐
              │              │              │
         ┌────▼────┐   ┌────▼────┐   ┌────▼────┐
         │  v1     │   │  v2     │   │  v3     │
         │ FastAPI │   │ FastAPI │   │ FastAPI │
         │Deploym. │   │Deploym. │   │Deploym. │
         └────┬────┘   └────┬────┘   └────┬────┘
              │              │              │
              └──────────────┼──────────────┘
                             │
                     ┌───────▼────────┐
                     │  ClusterIP     │
                     │  Service (DB)  │
                     └───────┬────────┘
                             │
                     ┌───────▼────────┐
                     │  MySQL         │
                     │  StatefulSet   │
                     │  (1 replica)   │
                     └────────────────┘
```

## Project Structure

```
k8s-multi-api/
├── apps/
│   ├── v1/
│   │   ├── main.py
│   │   ├── Dockerfile
│   │   └── requirements.txt
│   ├── v2/
│   │   ├── main.py
│   │   ├── Dockerfile
│   │   └── requirements.txt
│   └── v3/
│       ├── main.py
│       ├── Dockerfile
│       └── requirements.txt
├── docs/
│   └── migration-strategy.md
├── k8s/
│   ├── mysql/
│   │   ├── 01-namespace.yaml
│   │   ├── 02-secret.yaml
│   │   ├── 03-configmap.yaml
│   │   ├── 04-headless-service.yaml
│   │   └── 05-statefulset.yaml
│   ├── apis/
│   │   ├── 01-deployment-v1.yaml
│   │   ├── 02-deployment-v2.yaml
│   │   ├── 03-deployment-v3.yaml
│   │   ├── 04-service-v1.yaml
│   │   ├── 05-service-v2.yaml
│   │   └── 06-service-v3.yaml
│   └── init/
│       ├── 01-init-db-job.yaml
│       └── 02-migrate-db-job.yaml
├── AGENTS.md
└── README.md
```

## Components

### 1. FastAPI Apps (v1, v2, v3)

Each version is a simple FastAPI app:

- **`GET /`** → Returns JSON with:
  - `version`: The API version (v1, v2, or v3)
  - `hostname`: The pod name
  - `ip`: The pod IP address

- **`GET /users`** → Returns JSON list of users from MySQL database
  - Connects to MySQL via the ClusterIP service
  - Queries `users` table (`id`, `username`, `email`)
  - **v2 only**: also returns `first_name`, `last_name` and includes `GET /users/{id}` endpoint

### 2. MySQL StatefulSet

- 1 replica (suitable for local learning)
- StatefulSet with PersistentVolumeClaim (1GB)
- Headless service for stable network identity
- `users` table with: `id` (INT AUTO_INCREMENT), `username` (VARCHAR), `first_name` (VARCHAR), `last_name` (VARCHAR nullable), `email` (VARCHAR)
- Pre-populated with sample data via an init Job
- Schema migration supported via a dedicated migration Job (`02-migrate-db-job.yaml`)

### 3. Kubernetes Resources

| Resource | Kind | Purpose |
|---|---|---|
| `01-namespace.yaml` | Namespace | Isolate resources |
| `02-secret.yaml` | Secret | Store MySQL credentials |
| `03-configmap.yaml` | ConfigMap | DB connection settings |
| `04-headless-service.yaml` | Service (ClusterIP=None) | Stable DNS for MySQL pod |
| `05-statefulset.yaml` | StatefulSet | MySQL with persistent storage |
| `deployment-v*.yaml` | Deployment | FastAPI pods (3 replicas each) |
| `service-v*.yaml` | Service (NodePort) | Expose each API version |
| `01-init-db-job.yaml` | Job | Create table & seed data (new schema with first_name/last_name) |
| `02-migrate-db-job.yaml` | Job | Migrate existing DB from old schema (username only) to new schema (first_name/last_name) |

### 4. Networking

- **NodePorts**: Each API version exposed on a different port:
  - v1: NodePort **30081** → container port 8000
  - v2: NodePort **30082** → container port 8000
  - v3: NodePort **30083** → container port 8000
- **ClusterIP (headless)**: MySQL accessible at `mysql-0.mysql-service.<namespace>.svc.cluster.local:3306`

### 5. How to run locally (macOS Catalina + K8s 1.25.2)

```bash
# 1. Build Docker images (from project root)
docker build -t api-v1:latest ./apps/v1
docker build -t api-v2:latest ./apps/v2
docker build -t api-v3:latest ./apps/v3

# 2. Load images into cluster (if using minikube)
minikube image load api-v1:latest
minikube image load api-v2:latest
minikube image load api-v3:latest

# 3. Apply k8s manifests (in order)
kubectl apply -f k8s/mysql/01-namespace.yaml
kubectl apply -f k8s/mysql/02-secret.yaml
kubectl apply -f k8s/mysql/03-configmap.yaml
kubectl apply -f k8s/mysql/04-headless-service.yaml
kubectl apply -f k8s/mysql/05-statefulset.yaml

kubectl apply -f k8s/apis/01-deployment-v1.yaml
kubectl apply -f k8s/apis/02-deployment-v2.yaml
kubectl apply -f k8s/apis/03-deployment-v3.yaml
kubectl apply -f k8s/apis/04-service-v1.yaml
kubectl apply -f k8s/apis/05-service-v2.yaml
kubectl apply -f k8s/apis/06-service-v3.yaml

kubectl apply -f k8s/init/01-init-db-job.yaml

# 4. Test
curl http://localhost:30081/   # v1
curl http://localhost:30082/   # v2
curl http://localhost:30083/   # v3
curl http://localhost:30081/users  # DB query (old schema)
curl http://localhost:30082/users  # DB query (new schema with first_name/last_name)
```

### 6. Database Migrations

When evolving the schema (e.g., adding `first_name` and `last_name` to v2), use the migration Job:

```bash
# Run migration on an existing cluster with old data
kubectl apply -f k8s/init/02-migrate-db-job.yaml

# Wait for completion
kubectl wait --for=condition=complete job/migrate-db-job -n mysql-ns --timeout=60s

# Check logs
kubectl logs job/migrate-db-job -n mysql-ns

# Rebuild and redeploy the updated API
docker build -t api-v2:latest ./apps/v2
minikube image load api-v2:latest
kubectl rollout restart deployment/api-v2 -n mysql-ns
```

## API Versions Summary

| Version | Endpoints | Features | DB Schema |
|---|---|---|---|
| **v1** (read-only) | `GET /`, `GET /users` | Basic query | `id, username, email` |
| **v2** (read-only+) | `GET /`, `GET /users`, `GET /users/{id}` | `first_name`, `last_name`, single user lookup | `+ first_name, last_name` |
| **v3** (full CRUD) | `GET /`, `GET /users`, `GET /users/{id}`, `POST /users`, `PUT /users/{id}`, `PATCH /users/{id}`, `DELETE /users/{id}`, `GET /health/live`, `GET /health/ready` | Pagination, search, sort, audit logging, Pydantic validation, health probes | `+ audit_log table` |

---

## v3 — CRUD API Details

### Request/Response Examples

```bash
# CREATE — POST /users (201 Created)
curl -X POST http://localhost:30083/users \
  -H "Content-Type: application/json" \
  -d '{"username":"jane.doe","first_name":"Jane","last_name":"Doe","email":"jane@example.com"}'
# Response: {"id":11,"username":"jane.doe","first_name":"Jane","last_name":"Doe","email":"jane@example.com"}

# LIST with pagination — GET /users?page=1&page_size=3&sort=email&order=desc
curl "http://localhost:30083/users?page=1&page_size=3&sort=email&order=desc"

# SEARCH — GET /users?search=alice
curl "http://localhost:30083/users?search=alice"

# READ — GET /users/{id}
curl http://localhost:30083/users/1

# FULL UPDATE — PUT /users/{id} (all fields required)
curl -X PUT http://localhost:30083/users/11 \
  -H "Content-Type: application/json" \
  -d '{"username":"jane.updated","first_name":"Jane","last_name":"Updated","email":"jane@newdomain.com"}'

# PARTIAL UPDATE — PATCH /users/{id} (only provided fields)
curl -X PATCH http://localhost:30083/users/11 \
  -H "Content-Type: application/json" \
  -d '{"last_name":"Smith"}'

# DELETE — DELETE /users/{id} (204 No Content)
curl -X DELETE http://localhost:30083/users/11 -v
```

### HTTP Status Codes Used

| Code | Meaning | When |
|---|---|---|
| **200** | OK | GET, PUT, PATCH success |
| **201** | Created | POST success |
| **204** | No Content | DELETE success |
| **400** | Bad Request | PATCH with no fields |
| **404** | Not Found | User ID doesn't exist |
| **409** | Conflict | Duplicate username |
| **422** | Unprocessable Entity | Validation error (Pydantic) |
| **503** | Service Unavailable | DB connection failed |

### Pydantic Validation Rules

- `username`: min 3 chars, trimmed, unique in DB
- `email`: must contain `@`, trimmed
- `first_name`: required (for POST/PUT)
- `last_name`: optional (nullable in DB)

---

## sQuick Rebuild & Rollout (v3 only)

```bash
docker build -t api-v3:latest ./apps/v3
minikube image load api-v3:latest
kubectl rollout restart deployment/api-v3 -n mysql-ns
kubectl rollout status deployment/api-v3 -n mysql-ns
```

---

## Logs & Debugging

```bash
# Follow logs for a specific version
kubectl logs -n mysql-ns -l app=api,version=v3 -f --tail=50
kubectl logs -n mysql-ns -l app=api,version=v2 -f --tail=50
kubectl logs -n mysql-ns -l app=api,version=v1 -f --tail=50

# Follow logs from all API pods at once
kubectl logs -n mysql-ns -l app=api -f --tail=20 --max-log-requests=9

# Logs from a specific deployment
kubectl logs -n mysql-ns deployment/api-v3 --tail=100
kubectl logs -n mysql-ns deployment/api-v2 --tail=100
kubectl logs -n mysql-ns deployment/api-v1 --tail=100

# Previous logs from a crashed pod
kubectl logs -n mysql-ns -l app=api,version=v3 --previous --tail=50

# Logs from MySQL
kubectl logs -n mysql-ns mysql-0 --tail=50

# Logs from init/migration jobs
kubectl logs job/init-db-job -n mysql-ns
kubectl logs job/migrate-db-job -n mysql-ns

# Pod details and events
kubectl describe pod -n mysql-ns -l app=api,version=v3
kubectl get pods -n mysql-ns -o wide
kubectl get events -n mysql-ns --sort-by='.lastTimestamp' | tail -30
```

### Health Probes Check

```bash
# Check if pods are ready
kubectl get pods -n mysql-ns -l app=api,version=v3 \
  -o jsonpath='{range .items[*]}{.metadata.name}{"\t"}Ready: {.status.containerStatuses[0].ready}{"\n"}{end}'

# Port forward to test health endpoints directly
kubectl port-forward -n mysql-ns deployment/api-v3 8080:8000
# Then in another terminal:
curl http://localhost:8080/health/live
curl http://localhost:8080/health/ready
```

---

## Database Queries

```bash
# List all users
kubectl exec -it -n mysql-ns mysql-0 -- mysql -u root -prootpassword testdb -e "SELECT * FROM users;"

# List audit logs (v3)
kubectl exec -it -n mysql-ns mysql-0 -- mysql -u root -prootpassword testdb -e "SELECT * FROM audit_log;"

# Interactive MySQL shell
kubectl exec -it -n mysql-ns mysql-0 -- mysql -u root -prootpassword testdb
```

---

## Troubleshooting

### "Error connecting to MySQL" in logs

```bash
# 1. Check MySQL is running
kubectl get pods -n mysql-ns | grep mysql

# 2. Check MySQL logs
kubectl logs -n mysql-ns mysql-0 --tail=20

# 3. Test connection from within an API pod
kubectl exec -it -n mysql-ns deploy/api-v3 -- python3 -c "
import mysql.connector
conn = mysql.connector.connect(
  host='mysql-0.mysql-service.mysql-ns.svc.cluster.local',
  user='root', password='rootpassword', database='testdb'
)
print('Connected!' if conn else 'Failed')
"
```

### Pods in CrashLoopBackOff

```bash
# Check the last crash reason
kubectl describe pod -n mysql-ns -l app=api,version=v3 | grep -A 15 "Last State:"

# Check previous logs before crash
kubectl logs -n mysql-ns -l app=api,version=v3 --previous --tail=30

# Verify environment variables
kubectl get pods -n mysql-ns -l app=api,version=v3 -o yaml | grep -A 5 "env:"
```

### Init Job doesn't complete

```bash
# Check job logs
kubectl logs job/init-db-job -n mysql-ns

# Delete and retry
kubectl delete job init-db-job -n mysql-ns
kubectl apply -f k8s/init/01-init-db-job.yaml
```

### Duplicate username error (409)

The `username` column has a UNIQUE constraint. Use a different username or delete the existing one first.

### Readiness probe failing

The readiness probe checks DB connectivity. If MySQL is down, fix MySQL first and pods will auto-recover.

```bash
kubectl exec -it -n mysql-ns deploy/api-v3 -- curl -s http://localhost:8000/health/ready
```

---

## Clean Up

```bash
# Delete entire namespace (everything)
kubectl delete ns mysql-ns

# Or delete selectively
kubectl delete -f k8s/init/01-init-db-job.yaml
kubectl delete -f k8s/apis/06-service-v3.yaml
kubectl delete -f k8s/apis/03-deployment-v3.yaml
# ... etc

# Delete persistent data
kubectl delete pvc -n mysql-ns --all
```

---

## Notes for AI Agents

- All manifests are in `k8s/` organized by component
- Always apply MySQL resources BEFORE API resources
- The init Job must run AFTER MySQL is ready (sleep 10s handles this)
- v3 has `livenessProbe` and `readinessProbe` — v1 and v2 do not (intentionally, for comparison)
- The `audit_log` table is created by the init Job; if missing, v3 silently skips audit logging
- When editing YAML with heredocs (`<<'EOF'`), use `mysql -e "..."` instead to avoid YAML parsing issues