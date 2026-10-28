import asyncio
import os
from typing import Dict, Any, List
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Body
from fastapi.responses import HTMLResponse, JSONResponse
from .collector import KubePulseCollector

app = FastAPI(
    title="KubePulse — Cross-Platform Remote K3s & Kubernetes Telemetry Command Center",
    version="1.0.0",
)

collector = KubePulseCollector()
connected_clients: List[WebSocket] = []
TEMPLATES_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "templates")


async def telemetry_loop():
    while True:
        try:
            snap = await asyncio.to_thread(collector.collect_snapshot)
            dead_clients = []
            for ws in connected_clients:
                try:
                    await ws.send_json(snap)
                except Exception:
                    dead_clients.append(ws)
            for ws in dead_clients:
                if ws in connected_clients:
                    connected_clients.remove(ws)
        except Exception as exc:
            print(f"[KubePulse] Telemetry poll error: {exc}")
        await asyncio.sleep(5)


@app.on_event("startup")
async def on_startup():
    asyncio.create_task(telemetry_loop())


@app.get("/", response_class=HTMLResponse)
async def index():
    html_path = os.path.join(TEMPLATES_DIR, "index.html")
    with open(html_path, "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read())


@app.get("/api/telemetry")
async def get_telemetry():
    if collector.last_snapshot is not None:
        return JSONResponse(content=collector.last_snapshot)
    snap = await asyncio.to_thread(collector.collect_snapshot)
    return JSONResponse(content=snap)


@app.get("/api/telemetry/refresh")
async def force_refresh():
    snap = await asyncio.to_thread(collector.collect_snapshot)
    return JSONResponse(content=snap)


@app.get("/api/clusters")
async def list_clusters():
    return {
        "active_cluster_id": collector.active_cluster_id,
        "clusters": [
            {k: v for k, v in c.items() if k != "jump_pass"}
            for c in collector.clusters
        ],
    }


@app.post("/api/clusters")
async def save_cluster(payload: Dict[str, Any] = Body(...)):
    saved = collector.add_or_update_cluster(payload)
    snap = await asyncio.to_thread(collector.collect_snapshot)
    return {"cluster": saved, "snapshot": snap}


@app.post("/api/clusters/select")
async def select_cluster(payload: Dict[str, Any] = Body(...)):
    cid = payload.get("id", "")
    collector.active_cluster_id = cid
    snap = await asyncio.to_thread(collector.collect_snapshot)
    return snap


@app.post("/api/workload/restart")
async def restart_workload(payload: Dict[str, Any] = Body(...)):
    ns = payload.get("namespace", "default")
    name = payload.get("name", "")
    res = await asyncio.to_thread(collector.restart_workload, ns, name)
    return res


@app.get("/api/workload/logs")
async def workload_logs(namespace: str, name: str, tail: int = 80):
    res = await asyncio.to_thread(collector.get_workload_logs, namespace, name, tail)
    return res


@app.websocket("/ws/telemetry")
async def ws_telemetry(websocket: WebSocket):
    await websocket.accept()
    connected_clients.append(websocket)
    try:
        if collector.last_snapshot is not None:
            await websocket.send_json(collector.last_snapshot)
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        if websocket in connected_clients:
            connected_clients.remove(websocket)
    except Exception:
        if websocket in connected_clients:
            connected_clients.remove(websocket)
