<div align="center">

# ☸️ KubePulse
### Next-Generation Cross-Platform Remote K3s & Kubernetes Telemetry Command Center

[![Platform](https://img.shields.io/badge/Platform-Windows%20%7C%20Linux%20%7C%20macOS%20%7C%20Docker%20%7C%20K3s-0ea5e9?style=for-the-badge&logo=kubernetes&logoColor=white)](https://github.com/digdast/kubepulse)
[![Python](https://img.shields.io/badge/Python-3.10%2B-10b981?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-WebSockets%205s%20Stream-6366f1?style=for-the-badge&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![Architecture](https://img.shields.io/badge/Multi--Cluster-SSH%20Jump%20%7C%20Direct%20SSH%20%7C%20Kubeconfig-a855f7?style=for-the-badge)](https://github.com/digdast/kubepulse)

**Real-Time CPU (`mCores`), Memory (`MiB/GiB`), and Storage (`Root Disk / NFS / HostPath / PVC / tmpfs`) Telemetry with 1-Click Container Logs & Zero-Downtime Rolling Restarts.**

---

![KubePulse Command Center Overview](docs/screenshots/kubepulse-command-center.png)

</div>

---

## ⚡ Overview

**KubePulse** is a high-performance, dark-glassmorphic graphical observability and operations suite engineered for **K3s** and **Kubernetes** clusters. Designed to run natively on **Windows**, **Linux**, **macOS**, **Docker**, or directly inside **Kubernetes (`monitoring/kubesonarr`)**, it eliminates the need for heavyweight Prometheus/Grafana stacks when you want instant, sub-100ms visibility into every node, pod, service, and storage mount.

---

## 🖼️ High-Resolution Interface Gallery

### 1. Full Telemetry Command Center (`7-Node HA K3s Cluster`)
Real-time executive KPI gauges across **52 vCPUs**, **88 GiB RAM**, **Node Root Storage**, and **1.5 TB Shared NFS (`/data`)**, paired with live Top Memory & Top CPU service bar charts:

![KubePulse Command Center](docs/screenshots/kubepulse-command-center.png)

---

### 2. Per-Service CPU, Memory & Storage Telemetry Matrix
Interactive workload matrix with instant namespace filtering (`ALL`, `authentik`, `dns`, `kube-system`, `media`, `monitoring`, `npm`, `portainer`, `tomcat`, `web`), multi-column sorting (`Memory`, `CPU`, `Storage`, `Name`), real-time utilization bars against Kubernetes limits, HostPath/NFS directory byte sizing (`du -sb`), and clickable Ingress routes:

![KubePulse Services Telemetry Matrix](docs/screenshots/kubepulse-services-telemetry.png)

---

### 3. Multi-Node Hardware & Storage Topology (`3 Control-Plane/etcd + 4 Workers`)
Live hardware telemetry cards for every control-plane and worker node showing IP addresses, roles (`control-plane, etcd` / `worker`), vCPU millicore load, RAM utilization, and root disk usage:

![KubePulse 7-Node Topology](docs/screenshots/kubepulse-nodes-topology.png)

---

### 4. Live Container Log Streamer & Rolling Restart Controls
1-click live container stdout/stderr log inspection and zero-downtime `kubectl rollout restart` execution directly from the graphical dashboard:

![KubePulse Live Container Logs](docs/screenshots/kubepulse-live-logs.png)

---

## 🏗️ System Architecture

```mermaid
flowchart LR
    subgraph Client["🖥️ Operator Workstation / Browser"]
        UI["Glassmorphic Web UI\n(HTML5 / CSS3 / WebSockets)"]
    end

    subgraph Engine["⚡ KubePulse Core (Windows / Linux / macOS / K3s Pod)"]
        API["FastAPI + Uvicorn\n(/ws/telemetry • /api/*)"]
        COL["KubePulseCollector\n(Concurrent ThreadPool Engine)"]
        UI <-->|"5s Live JSON Stream"| API
        API <--> COL
    end

    subgraph Modes["🔌 3 Connection Transports"]
        M1["SSH Jump-Host\n(Proxmox Bastion -> K3s Master)"]
        M2["Direct SSH\n(K3s Control Plane)"]
        M3["Local Kubeconfig\n(Native kubectl)"]
        COL --> M1 & M2 & M3
    end

    subgraph Cluster["☸️ 7-Node HA K3s Cluster"]
        CP["3x Control-Plane / etcd\nk8s-cp-01 (.81) • cp-02 (.82) • cp-03 (.87)"]
        WK["4x Worker Nodes (AVX2)\nk8s-worker-01..04 (.83 - .86)"]
        ST["Shared NFS /data + HostPath + tmpfs"]
        M1 & M2 & M3 --> CP
        CP --- WK
        CP & WK --- ST
    end
```

---

## 🚀 Key Capabilities

| Capability | Technical Implementation |
| :--- | :--- |
| **Cross-Platform Execution** | Runs identically on **Windows 10/11**, **Linux**, **macOS**, **Docker**, and inside **K3s** (`NodePort 30789`). |
| **Agentless Remote SSH Jump-Host** | Connects through a Proxmox VE or Bastion host directly into a K3s control plane—zero local `kubectl` installation or kubeconfig certificate copying required. |
| **Parallel Telemetry Pipeline** | Executes `kubectl get`, `kubectl top nodes/pods`, `/readyz` latency probes, `df -B1`, and parallel `du -sb` volume inspections concurrently in `< 100ms` API latency. |
| **Deep Storage Observability** | Tracks per-node root disk capacity, shared NFS `/data` pool usage, `PersistentVolumeClaims`, `RAM-tmpfs` mounts, and per-service directory consumption. |
| **Active Day-2 Operations** | Includes 1-click **Live Container Logs** (`--all-containers=true`) and 1-click **Zero-Downtime Rolling Restarts** (`kubectl rollout restart`). |

---

## 🛠️ Quick Start

### 1. Windows (1-Click Launcher)
Double-click `run.bat` or run from PowerShell:
```powershell
git clone https://github.com/digdast/kubepulse.git
cd kubepulse
.\run.bat
```

### 2. Linux & macOS
```bash
git clone https://github.com/digdast/kubepulse.git
cd kubepulse
chmod +x run.sh
./run.sh
```

### 3. Deploy Natively Inside K3s / Kubernetes (`monitoring/kubesonarr`)
```bash
kubectl apply -f k8s-kubesonarr.yaml
```
- **NodePort Access**: `http://<any-k3s-node-ip>:30789`
- **Ingress Hostnames**: `http://kubesonarr.local` / `http://kubesonarr.ertechlab.com`

### 4. Docker Compose
```bash
docker compose up -d --build
```
Open **http://localhost:7890** in your browser.
