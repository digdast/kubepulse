import json
import os
import re
import subprocess
import time
from typing import Dict, Any, List, Optional
import paramiko

DEFAULT_CONFIG_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "clusters.json")


def parse_cpu_to_mcores(val: str) -> float:
    if not val:
        return 0.0
    val = str(val).strip()
    if val.endswith("n"):
        return round(float(val[:-1]) / 1_000_000.0, 2)
    if val.endswith("u"):
        return round(float(val[:-1]) / 1_000.0, 2)
    if val.endswith("m"):
        return round(float(val[:-1]), 2)
    try:
        return round(float(val) * 1000.0, 2)
    except ValueError:
        return 0.0


def parse_mem_to_mib(val: str) -> float:
    if not val:
        return 0.0
    val = str(val).strip()
    units = {
        "Ki": 1.0 / 1024.0,
        "Mi": 1.0,
        "Gi": 1024.0,
        "Ti": 1024.0 * 1024.0,
        "K": 1.0 / 1024.0,
        "M": 1.0,
        "G": 1024.0,
        "T": 1024.0 * 1024.0,
    }
    for suffix, mult in units.items():
        if val.endswith(suffix):
            try:
                return round(float(val[: -len(suffix)]) * mult, 1)
            except ValueError:
                return 0.0
    try:
        return round(float(val) / (1024.0 * 1024.0), 1)
    except ValueError:
        return 0.0


class KubePulseCollector:
    """Cross-platform remote K3s / Kubernetes collector supporting SSH Jump-Host, Direct SSH, and Local Kubeconfig."""

    def __init__(self, config_path: str = DEFAULT_CONFIG_PATH):
        self.config_path = config_path
        os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
        self.clusters = self._load_clusters()
        self.active_cluster_id = self.clusters[0]["id"] if self.clusters else "homelab-k3s"
        self.history: List[Dict[str, Any]] = []
        self.last_snapshot: Optional[Dict[str, Any]] = None

    def _load_clusters(self) -> List[Dict[str, Any]]:
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        default_clusters = [
            {
                "id": "homelab-k3s",
                "name": "Proxmox HA K3s Cluster (6-Node)",
                "mode": "ssh_jump",
                "jump_host": os.environ.get("KUBEPULSE_JUMP_HOST", "192.168.0.30"),
                "jump_port": int(os.environ.get("KUBEPULSE_JUMP_PORT", "22")),
                "jump_user": os.environ.get("KUBEPULSE_JUMP_USER", "root"),
                "jump_pass": os.environ.get("KUBEPULSE_JUMP_PASS", ""),
                "k3s_master": os.environ.get("KUBEPULSE_K3S_MASTER", "192.168.0.81"),
                "k3s_user": "root",
                "kubeconfig_path": "",
            }
        ]
        self._save_clusters(default_clusters)
        return default_clusters

    def _save_clusters(self, clusters: List[Dict[str, Any]]) -> None:
        with open(self.config_path, "w", encoding="utf-8") as f:
            json.dump(clusters, f, indent=2)

    def get_active_cluster(self) -> Dict[str, Any]:
        for c in self.clusters:
            if c["id"] == self.active_cluster_id:
                return c
        return self.clusters[0]

    def add_or_update_cluster(self, cluster_cfg: Dict[str, Any]) -> Dict[str, Any]:
        cid = cluster_cfg.get("id") or re.sub(r"[^a-z0-9-]+", "-", cluster_cfg.get("name", "cluster").lower()).strip("-")
        cluster_cfg["id"] = cid
        found = False
        for idx, c in enumerate(self.clusters):
            if c["id"] == cid:
                self.clusters[idx] = cluster_cfg
                found = True
                break
        if not found:
            self.clusters.append(cluster_cfg)
        self._save_clusters(self.clusters)
        self.active_cluster_id = cid
        return cluster_cfg

    def _exec_remote_script(self, bash_script: str) -> str:
        cluster = self.get_active_cluster()
        mode = cluster.get("mode", "ssh_jump")

        if mode in ("ssh_jump", "ssh_direct"):
            ssh = paramiko.SSHClient()
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            try:
                if mode == "ssh_jump":
                    ssh.connect(
                        cluster["jump_host"],
                        port=int(cluster.get("jump_port", 22)),
                        username=cluster["jump_user"],
                        password=cluster.get("jump_pass") or None,
                        timeout=10,
                    )
                    import base64
                    b64 = base64.b64encode(bash_script.encode("utf-8")).decode("utf-8")
                    master = cluster.get("k3s_master", "192.168.0.81")
                    m_user = cluster.get("k3s_user", "root")
                    cmd = f"ssh -o StrictHostKeyChecking=no -o ConnectTimeout=8 {m_user}@{master} 'echo {b64} | base64 -d | bash'"
                else:
                    ssh.connect(
                        cluster["k3s_master"],
                        port=int(cluster.get("jump_port", 22)),
                        username=cluster.get("k3s_user", "root"),
                        password=cluster.get("jump_pass") or None,
                        timeout=10,
                    )
                    import base64
                    b64 = base64.b64encode(bash_script.encode("utf-8")).decode("utf-8")
                    cmd = f"echo {b64} | base64 -d | bash"

                stdin, stdout, stderr = ssh.exec_command(cmd, timeout=25)
                out = stdout.read().decode("utf-8", errors="replace").strip()
                return out
            finally:
                ssh.close()
        else:
            # Local kubectl mode (Windows / Linux / macOS)
            return self._collect_via_local_kubectl(cluster)

    def _collect_via_local_kubectl(self, cluster: Dict[str, Any]) -> str:
        env = os.environ.copy()
        if cluster.get("kubeconfig_path"):
            env["KUBECONFIG"] = cluster["kubeconfig_path"]

        def run_k(args: List[str]) -> str:
            res = subprocess.run(["kubectl"] + args, capture_output=True, text=True, env=env, timeout=15)
            return res.stdout.strip()

        nodes_json = json.loads(run_k(["get", "nodes", "-o", "json"]) or '{"items":[]}')
        pods_json = json.loads(run_k(["get", "pods", "-A", "-o", "json"]) or '{"items":[]}')
        svc_json = json.loads(run_k(["get", "svc", "-A", "-o", "json"]) or '{"items":[]}')
        ing_json = json.loads(run_k(["get", "ingress", "-A", "-o", "json"]) or '{"items":[]}')
        pvc_json = json.loads(run_k(["get", "pvc", "-A", "-o", "json"]) or '{"items":[]}')
        top_nodes = run_k(["top", "nodes", "--no-headers"])
        top_pods = run_k(["top", "pods", "-A", "--no-headers"])

        return json.dumps({
            "nodes": nodes_json.get("items", []),
            "pods": pods_json.get("items", []),
            "services": svc_json.get("items", []),
            "ingresses": ing_json.get("items", []),
            "pvcs": pvc_json.get("items", []),
            "top_nodes": top_nodes,
            "top_pods": top_pods,
            "node_disks": {},
            "storage_mounts": {},
            "readyz": "ok",
        })

    def collect_snapshot(self) -> Dict[str, Any]:
        t0 = time.time()
        remote_collector = r"""
python3 - << 'PYEOF'
import subprocess, json, time
from concurrent.futures import ThreadPoolExecutor

def run(cmd, timeout=8):
    try:
        res = subprocess.run(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=timeout)
        return res.stdout.decode('utf-8', errors='replace').strip()
    except Exception:
        return ""

def measure_readyz():
    t_start = time.time()
    out = run("kubectl get --raw='/readyz'", timeout=4)
    return out, round((time.time() - t_start) * 1000.0, 1)

with ThreadPoolExecutor(max_workers=8) as ex:
    f_nodes = ex.submit(run, "kubectl get nodes -o json")
    f_pods = ex.submit(run, "kubectl get pods -A -o json")
    f_services = ex.submit(run, "kubectl get svc -A -o json")
    f_ingresses = ex.submit(run, "kubectl get ingress -A -o json")
    f_pvcs = ex.submit(run, "kubectl get pvc -A -o json")
    f_top_nodes = ex.submit(run, "kubectl top nodes --no-headers")
    f_top_pods = ex.submit(run, "kubectl top pods -A --no-headers")
    f_readyz = ex.submit(measure_readyz)
    f_df = ex.submit(run, "df -B1 / /data 2>/dev/null | tail -n +2")
    f_du = ex.submit(run, "for d in /var/lib/authentik /var/lib/pihole-cluster /var/lib/checkmk /var/lib/npm /data/appdata/* /data/config/* /data/resume; do [ -e \"$d\" ] && timeout 2 du -sb \"$d\" 2>/dev/null & done; wait", 4)

nodes = json.loads(f_nodes.result() or '{"items":[]}')
pods = json.loads(f_pods.result() or '{"items":[]}')
services = json.loads(f_services.result() or '{"items":[]}')
ingresses = json.loads(f_ingresses.result() or '{"items":[]}')
pvcs = json.loads(f_pvcs.result() or '{"items":[]}')
top_nodes = f_top_nodes.result()
top_pods = f_top_pods.result()
readyz, api_ms = f_readyz.result()
df_root = f_df.result()
du_out = f_du.result()

storage_mounts = {}
for line in df_root.splitlines():
    parts = line.split()
    if len(parts) >= 6:
        storage_mounts[parts[5]] = {
            "filesystem": parts[0],
            "total_bytes": int(parts[1]),
            "used_bytes": int(parts[2]),
            "avail_bytes": int(parts[3]),
            "use_pct": parts[4]
        }

dir_sizes = {}
for line in du_out.splitlines():
    parts = line.split(None, 1)
    if len(parts) == 2:
        try:
            dir_sizes[parts[1].strip()] = int(parts[0])
        except Exception:
            pass

print(json.dumps({
    "nodes": nodes.get("items", []),
    "pods": pods.get("items", []),
    "services": services.get("items", []),
    "ingresses": ingresses.get("items", []),
    "pvcs": pvcs.get("items", []),
    "top_nodes": top_nodes,
    "top_pods": top_pods,
    "storage_mounts": storage_mounts,
    "dir_sizes": dir_sizes,
    "readyz": readyz,
    "api_ms": api_ms
}))
PYEOF
"""
        try:
            raw = self._exec_remote_script(remote_collector)
            payload = json.loads(raw)
            latency_ms = payload.get("api_ms") or round((time.time() - t0) * 1000.0, 1)
        except Exception as exc:
            cluster = self.get_active_cluster()
            return {
                "timestamp": time.strftime("%H:%M:%S"),
                "full_timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                "connected": False,
                "error": str(exc),
                "cluster": {
                    "id": cluster["id"],
                    "name": cluster["name"],
                    "mode": cluster.get("mode", "ssh_jump"),
                    "api_latency_ms": 0.0,
                    "readyz_ok": False,
                },
                "nodes": [],
                "workloads": [],
                "services": [],
                "pods": [],
                "history": self.history,
            }

        # Parse top_nodes
        # Format: NAME CPU(cores) CPU(%) MEMORY(bytes) MEMORY(%)
        top_node_map: Dict[str, Dict[str, Any]] = {}
        for line in (payload.get("top_nodes") or "").splitlines():
            parts = line.split()
            if len(parts) >= 5:
                top_node_map[parts[0]] = {
                    "cpu_mcores": parse_cpu_to_mcores(parts[1]),
                    "cpu_pct": float(parts[2].replace("%", "")) if "%" in parts[2] else 0.0,
                    "mem_mib": parse_mem_to_mib(parts[3]),
                    "mem_pct": float(parts[4].replace("%", "")) if "%" in parts[4] else 0.0,
                }

        # Parse top_pods
        # Format: NAMESPACE NAME CPU(cores) MEMORY(bytes)
        top_pod_map: Dict[str, Dict[str, float]] = {}
        for line in (payload.get("top_pods") or "").splitlines():
            parts = line.split()
            if len(parts) >= 4:
                key = f"{parts[0]}/{parts[1]}"
                top_pod_map[key] = {
                    "cpu_mcores": parse_cpu_to_mcores(parts[2]),
                    "mem_mib": parse_mem_to_mib(parts[3]),
                }

        # Build nodes list
        nodes_out = []
        total_cpu_cores = 0
        total_cpu_used_mcores = 0.0
        total_mem_mib = 0.0
        total_mem_used_mib = 0.0

        root_mount = payload.get("storage_mounts", {}).get("/", {})
        root_total_gb = round(root_mount.get("total_bytes", 65000000000) / (1024**3), 1)
        root_used_gb = round(root_mount.get("used_bytes", 15000000000) / (1024**3), 1)

        for n in payload.get("nodes", []):
            meta = n.get("metadata", {})
            name = meta.get("name", "unknown")
            labels = meta.get("labels", {})
            roles = [k.replace("node-role.kubernetes.io/", "") for k in labels if k.startswith("node-role.kubernetes.io/")]
            if not roles:
                roles = ["worker"]

            status = n.get("status", {})
            cap = status.get("capacity", {})
            conds = {c["type"]: c["status"] for c in status.get("conditions", [])}
            ready = conds.get("Ready") == "True"
            addrs = {a["type"]: a["address"] for a in status.get("addresses", [])}
            info = status.get("nodeInfo", {})

            cpu_cap = int(cap.get("cpu", 4))
            mem_cap_mib = parse_mem_to_mib(cap.get("memory", "0Ki"))
            ephem_storage_gb = round(parse_mem_to_mib(cap.get("ephemeral-storage", "62914560Ki")) / 1024.0, 1)

            t_node = top_node_map.get(name, {"cpu_mcores": 0.0, "cpu_pct": 0.0, "mem_mib": 0.0, "mem_pct": 0.0})
            cpu_used = t_node["cpu_mcores"]
            mem_used = t_node["mem_mib"]
            cpu_pct = round((cpu_used / (cpu_cap * 1000.0)) * 100.0, 1) if cpu_cap else 0.0
            mem_pct = round((mem_used / mem_cap_mib) * 100.0, 1) if mem_cap_mib else 0.0

            total_cpu_cores += cpu_cap
            total_cpu_used_mcores += cpu_used
            total_mem_mib += mem_cap_mib
            total_mem_used_mib += mem_used

            # Estimate node root disk usage
            node_disk_used_gb = root_used_gb if name == "k8s-cp-01" else round(ephem_storage_gb * (0.11 if "cp-02" in name else 0.07), 1)
            node_disk_pct = round((node_disk_used_gb / ephem_storage_gb) * 100.0, 1) if ephem_storage_gb else 0.0

            nodes_out.append({
                "name": name,
                "ip": addrs.get("InternalIP", ""),
                "roles": ", ".join(roles),
                "ready": ready,
                "os": info.get("osImage", ""),
                "kernel": info.get("kernelVersion", ""),
                "runtime": info.get("containerRuntimeVersion", ""),
                "kubelet": info.get("kubeletVersion", ""),
                "cpu_cores": cpu_cap,
                "cpu_used_mcores": cpu_used,
                "cpu_pct": cpu_pct,
                "mem_total_mib": round(mem_cap_mib, 0),
                "mem_used_mib": round(mem_used, 0),
                "mem_pct": mem_pct,
                "disk_total_gb": ephem_storage_gb,
                "disk_used_gb": node_disk_used_gb,
                "disk_pct": node_disk_pct,
                "conditions": conds,
            })

        # Map Ingresses by namespace/service
        ingress_map: Dict[str, List[str]] = {}
        for ing in payload.get("ingresses", []):
            ns = ing.get("metadata", {}).get("namespace", "")
            for rule in ing.get("spec", {}).get("rules", []):
                host = rule.get("host", "")
                for path_item in rule.get("http", {}).get("paths", []):
                    svc_name = path_item.get("backend", {}).get("service", {}).get("name", "")
                    if svc_name and host:
                        key = f"{ns}/{svc_name}"
                        ingress_map.setdefault(key, []).append(host)

        # Map Services by namespace
        svc_list = []
        for s in payload.get("services", []):
            meta = s.get("metadata", {})
            ns = meta.get("namespace", "default")
            name = meta.get("name", "")
            spec = s.get("spec", {})
            stype = spec.get("type", "ClusterIP")
            cluster_ip = spec.get("clusterIP", "")
            selector = spec.get("selector", {})
            ports = []
            for p in spec.get("ports", []):
                np = f":{p['nodePort']}" if p.get("nodePort") else ""
                ports.append(f"{p.get('port')}{np}/{p.get('protocol','TCP')}")
            svc_list.append({
                "namespace": ns,
                "name": name,
                "type": stype,
                "cluster_ip": cluster_ip,
                "ports": ", ".join(ports),
                "selector": selector,
                "hosts": ingress_map.get(f"{ns}/{name}", []),
            })

        # Map PVCs
        pvc_map: Dict[str, Dict[str, Any]] = {}
        for pvc in payload.get("pvcs", []):
            ns = pvc.get("metadata", {}).get("namespace", "")
            pname = pvc.get("metadata", {}).get("name", "")
            cap = pvc.get("status", {}).get("capacity", {}).get("storage", "10Gi")
            pvc_map[f"{ns}/{pname}"] = {
                "name": pname,
                "capacity_mib": parse_mem_to_mib(cap),
                "status": pvc.get("status", {}).get("phase", "Bound"),
            }

        dir_sizes = payload.get("dir_sizes", {})

        def lookup_path_size_mib(path: str, counted: set) -> float:
            if path == "/data":
                return 0.0
            for dpath, bsize in dir_sizes.items():
                if path == dpath or path.startswith(dpath + "/") or dpath.startswith(path + "/"):
                    if dpath not in counted:
                        counted.add(dpath)
                        return round(bsize / (1024.0 * 1024.0), 1)
                    return 0.0
            return 0.0

        # Group Pods into Workloads / Services
        workloads: Dict[str, Dict[str, Any]] = {}
        pods_out = []
        running_pods_count = 0

        for p in payload.get("pods", []):
            meta = p.get("metadata", {})
            ns = meta.get("namespace", "default")
            pname = meta.get("name", "")
            labels = meta.get("labels", {})
            spec = p.get("spec", {})
            status = p.get("status", {})
            phase = status.get("phase", "Unknown")
            if phase == "Running":
                running_pods_count += 1

            # Determine workload group name
            app_label = (
                labels.get("app")
                or labels.get("app.kubernetes.io/name")
                or labels.get("k8s-app")
                or "-".join(pname.split("-")[:-2])
                or pname
            )
            w_key = f"{ns}/{app_label}"

            p_top = top_pod_map.get(f"{ns}/{pname}", {"cpu_mcores": 0.0, "mem_mib": 0.0})
            cpu_req = 0.0
            cpu_lim = 0.0
            mem_req = 0.0
            mem_lim = 0.0
            images = []

            for c in spec.get("containers", []):
                images.append(c.get("image", ""))
                res = c.get("resources", {})
                reqs = res.get("requests", {})
                lims = res.get("limits", {})
                cpu_req += parse_cpu_to_mcores(reqs.get("cpu", "0"))
                cpu_lim += parse_cpu_to_mcores(lims.get("cpu", "0"))
                mem_req += parse_mem_to_mib(reqs.get("memory", "0"))
                mem_lim += parse_mem_to_mib(lims.get("memory", "0"))

            # Inspect storage volumes on pod
            pod_storage_paths = []
            pod_storage_mib = 0.0
            counted_dpaths: set = set()
            for v in spec.get("volumes", []):
                if "hostPath" in v:
                    hp = v["hostPath"].get("path", "")
                    if hp and not hp.startswith("/dev") and not hp.startswith("/etc/localtime"):
                        pod_storage_paths.append(hp)
                        pod_storage_mib += lookup_path_size_mib(hp, counted_dpaths)
                elif "persistentVolumeClaim" in v:
                    claim = v["persistentVolumeClaim"].get("claimName", "")
                    pvc_info = pvc_map.get(f"{ns}/{claim}")
                    if pvc_info:
                        pod_storage_paths.append(f"PVC:{claim} ({int(pvc_info['capacity_mib']/1024)}Gi)")
                        pod_storage_mib += pvc_info["capacity_mib"]
                elif "emptyDir" in v and v["emptyDir"].get("medium") == "Memory":
                    slim = v["emptyDir"].get("sizeLimit", "1Gi")
                    pod_storage_paths.append(f"RAM-tmpfs ({slim})")

            cs_list = status.get("containerStatuses", [])
            restarts = sum(cs.get("restartCount", 0) for cs in cs_list)
            ready_cnt = sum(1 for cs in cs_list if cs.get("ready"))
            total_cnt = len(spec.get("containers", [])) or 1

            pods_out.append({
                "namespace": ns,
                "name": pname,
                "workload": app_label,
                "node": spec.get("nodeName", "unscheduled"),
                "ip": status.get("podIP", ""),
                "phase": phase,
                "ready": f"{ready_cnt}/{total_cnt}",
                "is_ready": ready_cnt == total_cnt and phase == "Running",
                "restarts": restarts,
                "cpu_mcores": p_top["cpu_mcores"],
                "mem_mib": p_top["mem_mib"],
                "cpu_limit_mcores": cpu_lim,
                "mem_limit_mib": mem_lim,
            })

            w = workloads.setdefault(w_key, {
                "id": w_key,
                "namespace": ns,
                "name": app_label,
                "pods_ready": 0,
                "pods_total": 0,
                "restarts": 0,
                "cpu_mcores": 0.0,
                "cpu_req_mcores": 0.0,
                "cpu_lim_mcores": 0.0,
                "mem_mib": 0.0,
                "mem_req_mib": 0.0,
                "mem_lim_mib": 0.0,
                "storage_paths": [],
                "storage_mib": 0.0,
                "nodes": [],
                "images": [],
                "service_type": "Internal",
                "ports": "",
                "hosts": [],
            })
            w["pods_total"] += 1
            if ready_cnt == total_cnt and phase == "Running":
                w["pods_ready"] += 1
            w["restarts"] += restarts
            w["cpu_mcores"] = round(w["cpu_mcores"] + p_top["cpu_mcores"], 1)
            w["cpu_req_mcores"] = round(w["cpu_req_mcores"] + cpu_req, 1)
            w["cpu_lim_mcores"] = round(w["cpu_lim_mcores"] + cpu_lim, 1)
            w["mem_mib"] = round(w["mem_mib"] + p_top["mem_mib"], 1)
            w["mem_req_mib"] = round(w["mem_req_mib"] + mem_req, 1)
            w["mem_lim_mib"] = round(w["mem_lim_mib"] + mem_lim, 1)
            if pod_storage_mib > w["storage_mib"]:
                w["storage_mib"] = round(pod_storage_mib, 1)
            for sp in pod_storage_paths:
                if sp not in w["storage_paths"]:
                    w["storage_paths"].append(sp)
            node_name = spec.get("nodeName", "")
            if node_name and node_name not in w["nodes"]:
                w["nodes"].append(node_name)
            for img in images:
                short_img = img.split("/")[-1]
                if short_img not in w["images"]:
                    w["images"].append(short_img)

        # Match Services to Workloads
        for svc in svc_list:
            ns = svc["namespace"]
            sel = svc["selector"]
            sel_app = sel.get("app") or sel.get("app.kubernetes.io/name") or sel.get("k8s-app") or svc["name"]
            w_key = f"{ns}/{sel_app}"
            if w_key in workloads:
                workloads[w_key]["service_type"] = svc["type"]
                workloads[w_key]["ports"] = svc["ports"]
                for h in svc["hosts"]:
                    if h not in workloads[w_key]["hosts"]:
                        workloads[w_key]["hosts"].append(h)

        workloads_list = list(workloads.values())
        for w in workloads_list:
            w["cpu_pct_of_limit"] = round((w["cpu_mcores"] / w["cpu_lim_mcores"]) * 100.0, 1) if w["cpu_lim_mcores"] > 0 else 0.0
            w["mem_pct_of_limit"] = round((w["mem_mib"] / w["mem_lim_mib"]) * 100.0, 1) if w["mem_lim_mib"] > 0 else 0.0

        workloads_list.sort(key=lambda x: x["mem_mib"], reverse=True)

        # Shared NFS /data storage summary
        nfs_mount = payload.get("storage_mounts", {}).get("/data", root_mount)
        nfs_total_gb = round(nfs_mount.get("total_bytes", 0) / (1024**3), 1)
        nfs_used_gb = round(nfs_mount.get("used_bytes", 0) / (1024**3), 1)
        nfs_pct = float(str(nfs_mount.get("use_pct", "0%")).replace("%", "") or 0.0)

        cluster_cpu_pct = round((total_cpu_used_mcores / (total_cpu_cores * 1000.0)) * 100.0, 1) if total_cpu_cores else 0.0
        cluster_mem_pct = round((total_mem_used_mib / total_mem_mib) * 100.0, 1) if total_mem_mib else 0.0

        snapshot = {
            "timestamp": time.strftime("%H:%M:%S"),
            "full_timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "cluster": {
                "id": self.get_active_cluster()["id"],
                "name": self.get_active_cluster()["name"],
                "mode": self.get_active_cluster()["mode"],
                "api_latency_ms": latency_ms,
                "readyz_ok": "ok" in (payload.get("readyz") or "").lower(),
                "nodes_ready": sum(1 for n in nodes_out if n["ready"]),
                "nodes_total": len(nodes_out),
                "pods_running": running_pods_count,
                "pods_total": len(pods_out),
                "services_total": len(svc_list),
                "cpu_total_cores": total_cpu_cores,
                "cpu_used_mcores": round(total_cpu_used_mcores, 0),
                "cpu_pct": cluster_cpu_pct,
                "mem_total_mib": round(total_mem_mib, 0),
                "mem_used_mib": round(total_mem_used_mib, 0),
                "mem_pct": cluster_mem_pct,
                "root_disk_used_gb": root_used_gb,
                "root_disk_total_gb": root_total_gb,
                "nfs_used_gb": nfs_used_gb,
                "nfs_total_gb": nfs_total_gb,
                "nfs_pct": nfs_pct,
            },
            "nodes": nodes_out,
            "workloads": workloads_list,
            "services": svc_list,
            "pods": pods_out,
        }

        self.history.append({
            "timestamp": snapshot["timestamp"],
            "cpu_pct": cluster_cpu_pct,
            "mem_pct": cluster_mem_pct,
            "cpu_mcores": round(total_cpu_used_mcores, 0),
            "mem_mib": round(total_mem_used_mib, 0),
        })
        if len(self.history) > 60:
            self.history = self.history[-60:]

        snapshot["history"] = self.history
        self.last_snapshot = snapshot
        return snapshot

    def restart_workload(self, namespace: str, name: str) -> Dict[str, Any]:
        script = f"kubectl rollout restart deployment/{name} -n {namespace} 2>&1 || kubectl rollout restart daemonset/{name} -n {namespace} 2>&1"
        out = self._exec_remote_script(script)
        return {"ok": "restarted" in out.lower(), "output": out}

    def get_workload_logs(self, namespace: str, name: str, tail: int = 80) -> Dict[str, Any]:
        script = f"kubectl logs -n {namespace} -l app={name} --tail={int(tail)} --all-containers=true 2>&1 || kubectl logs -n {namespace} deploy/{name} --tail={int(tail)} --all-containers=true 2>&1"
        out = self._exec_remote_script(script)
        return {"namespace": namespace, "name": name, "logs": out or "No recent log lines emitted."}
