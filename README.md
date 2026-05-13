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
│       └── 01-init-db-job.yaml
└── AGENTS.md
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

### 2. MySQL StatefulSet

- 1 replica (suitable for local learning)
- StatefulSet with PersistentVolumeClaim (1GB)
- Headless service for stable network identity
- `users` table with: `id` (INT AUTO_INCREMENT), `username` (VARCHAR), `email` (VARCHAR)
- Pre-populated with sample data via an init Job

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
| `01-init-db-job.yaml` | Job | Create table & seed data |

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
curl http://localhost:30081/users  # DB query
```

### 6. Future Improvements (Next Steps)

- [ ] Replace NodePort with **Ingress** (NGINX Ingress Controller)
- [ ] Add **Ingress routes**: `/v1`, `/v2`, `/v3` → respective services
- [ ] Add **ConfigMap** for API version label (instead of hardcoding)
- [ ] Implement **Health checks** (livenessProbe, readinessProbe)
- [ ] Add **Horizontal Pod Autoscaler**
- [ ] Use **Helm** to package everything
- [ ] Add **Service Mesh** (Istio or Linkerd)