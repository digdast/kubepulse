# KubePulse — Cross-Platform Remote K3s & Kubernetes Monitor

**KubePulse** is a modern, lightweight, cross-platform (**Windows, Linux, macOS, and Docker**) graphical telemetry and management suite for remote **K3s** and **Kubernetes** clusters.

It connects remotely via **SSH Jump-Host (Proxmox -> K3s)**, **Direct SSH**, or **Local Kubeconfig (`kubectl`)** and streams real-time **CPU, Memory, and Storage** metrics for every node and service in a dark glassmorphic graphical interface.

---

## Key Features

- **Cross-Platform Native Execution**: Runs identically on **Windows**, **Linux**, **macOS**, and **Docker** (`Python 3.10+` + `FastAPI` + `Paramiko` + `WebSockets`).
- **3 Remote Connection Modes**:
  1. **SSH Jump Host (`ssh_jump`)**: Connects through a Proxmox / Bastion SSH host (`192.168.0.30`) directly into a K3s control-plane node (`192.168.0.81`) — zero local `kubectl` installation or port forwarding required.
  2. **Direct SSH (`ssh_direct`)**: SSH straight into any K3s/Kubernetes master node.
  3. **Local Kubeconfig (`kubeconfig`)**: Uses local `kubectl` on Windows, Linux, or macOS.
- **Full Service & Node Telemetry**:
  - **CPU Usage**: Live millicores (`mCores`) & `% of vCPU` per node and per service, compared against Kubernetes CPU requests and limits.
  - **Memory Usage**: Live `MiB` / `GiB` consumption per node and per service, with visual progress bars against pod memory limits.
  - **Storage Usage**:
    - Per-node root disk capacity & usage (`/`).
    - Shared cluster NFS storage capacity & usage (`/data`).
    - Per-service mounted volume map (`HostPath`, `PVC`, `EmptyDir/tmpfs`) with live directory byte sizes (`du -sb`) for `/data/*` volumes.
- **Interactive Graphical Operations**:
  - Live **Top 8 Services by Memory** and **Top 8 Services by CPU** bar charts.
  - Instant search, namespace filter pills (`media`, `default`, `kube-system`, `monitoring`, `metallb-system`, `kubernetes-dashboard`), and multi-column sorting (`Memory`, `CPU`, `Storage`, `Name`).
  - **1-Click Live Pod Logs Modal** and **1-Click Rolling Restart** for any Deployment, DaemonSet, or StatefulSet.
  - **Multi-Cluster Switcher Modal**: Add and switch between multiple K3s or Kubernetes clusters on the fly.

---

## Quick Start

### Windows
Double-click `run.bat` or run from PowerShell / Command Prompt:
```powershell
cd C:\scripts\kubepulse
.\run.bat
```

### Linux & macOS
```bash
cd kubepulse
chmod +x run.sh
./run.sh
```

### Cross-Platform Python CLI
```bash
python run.py --host 0.0.0.0 --port 7890
```
Then open **http://localhost:7890** in your browser.

### Docker / Docker Compose
```bash
docker compose up -d --build
```
Then open **http://localhost:7890**.
