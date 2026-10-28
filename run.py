#!/usr/bin/env python3
"""
KubePulse Cross-Platform Launcher (Windows, Linux, macOS)
Starts the KubePulse FastAPI server and optionally opens the graphical dashboard in the default browser.
"""
import argparse
import platform
import socket
import threading
import time
import webbrowser
import uvicorn


def get_local_ip() -> str:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


def main():
    parser = argparse.ArgumentParser(
        description="KubePulse — Cross-Platform Remote K3s & Kubernetes Graphical Telemetry Monitor"
    )
    parser.add_argument("--host", default="0.0.0.0", help="Bind address (default: 0.0.0.0)")
    parser.add_argument("--port", type=int, default=7890, help="HTTP port (default: 7890)")
    parser.add_argument("--no-browser", action="store_true", help="Do not auto-open browser on startup")
    parser.add_argument("--reload", action="store_true", help="Enable hot-reload for development")
    args = parser.parse_args()

    local_url = f"http://localhost:{args.port}"
    lan_url = f"http://{get_local_ip()}:{args.port}"
    os_info = f"{platform.system()} {platform.release()} ({platform.machine()})"

    print("=" * 72)
    print("  KubePulse v1.0.0 — Remote K3s & Kubernetes Graphical Monitor")
    print("=" * 72)
    print(f"  Platform   : {os_info}")
    print(f"  Local URL  : {local_url}")
    print(f"  LAN URL    : {lan_url}")
    print("=" * 72)

    if not args.no_browser:
        def _open_browser():
            time.sleep(1.5)
            try:
                webbrowser.open(local_url)
            except Exception:
                pass
        threading.Thread(target=_open_browser, daemon=True).start()

    uvicorn.run(
        "kubepulse.app:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        log_level="info",
    )


if __name__ == "__main__":
    main()
