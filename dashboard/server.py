"""
Local Telemetry HTTP & SSE Server with Role-Based Authentication

Serves the glassmorphic web dashboard on http://127.0.0.1:8080 with:
1. Token-based session authentication (Researcher, Caregiver, Admin)
2. Real-time Server-Sent Events (SSE) telemetry streaming
3. Protected telemetry and research dataset export endpoints
"""

import sys
import os
import json
import time
import secrets
import asyncio
from pathlib import Path
from typing import AsyncGenerator, Optional, Dict, Any

from fastapi import FastAPI, Response, HTTPException, Depends, Header, Query, Request, status
from fastapi.responses import HTMLResponse, FileResponse, StreamingResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import uvicorn

from config import (
    DASHBOARD_HOST,
    DASHBOARD_PORT,
    LOCAL_TELEMETRY_FILE,
    BASE_DIR,
)

app = FastAPI(title="Smart Glasses Caregiver & Researcher Portal")

DASHBOARD_DIR = BASE_DIR / "dashboard"

# Serve static CSS & JS
app.mount("/static", StaticFiles(directory=str(DASHBOARD_DIR)), name="static")

# ==============================================================================
# USER ACCOUNTS & SESSION STORE
# ==============================================================================
USERS: Dict[str, Dict[str, Any]] = {
    "researcher": {
        "password": "Glasses2026!",
        "name": "Lead Researcher",
        "email": "researcher@smartglasses.io",
        "role": "Lead Researcher",
        "avatar": "🔬",
    },
    "caregiver": {
        "password": "Caregiver2026!",
        "name": "Primary Caregiver",
        "email": "caregiver@smartglasses.io",
        "role": "Primary Caregiver",
        "avatar": "🩺",
    },
    "doctor": {
        "password": "Doctor2026!",
        "name": "Dr. Sarah Mitchell",
        "email": "doctor@visioncare.health",
        "role": "Doctor",
        "avatar": "🩻",
    },
    "patient": {
        "password": "Patient2026!",
        "name": "Alex Rivera",
        "email": "patient@visioncare.health",
        "role": "Patient",
        "avatar": "AR",
    },
    "admin": {
        "password": "admin123",
        "name": "Administrator",
        "email": "admin@smartglasses.io",
        "role": "Admin",
        "avatar": "⚡",
    },
}

# In-memory session token store: token -> {username, created_at, user_info}
ACTIVE_SESSIONS: Dict[str, Dict[str, Any]] = {}

# Global refs
_VIDEO_QUEUE = None
_DEPTH_GRID_QUEUE = None


class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    token: str
    user: Dict[str, Any]


def get_current_user(
    authorization: Optional[str] = Header(None),
    token: Optional[str] = Query(None),
) -> Dict[str, Any]:
    """Dependency validating active session token from header or query param."""
    extracted_token = None
    if authorization and authorization.startswith("Bearer "):
        extracted_token = authorization.split(" ")[1]
    elif token:
        extracted_token = token

    if not extracted_token or extracted_token not in ACTIVE_SESSIONS:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required. Invalid or expired session token.",
        )

    return ACTIVE_SESSIONS[extracted_token]["user"]


# ==============================================================================
# AUTHENTICATION API ROUTES
# ==============================================================================
@app.post("/api/auth/login")
async def api_login(req: LoginRequest):
    uname = req.username.strip().lower()
    user_record = USERS.get(uname)

    # Check email match if username wasn't directly found
    if not user_record:
        for u_key, u_val in USERS.items():
            if u_val["email"].lower() == uname:
                user_record = u_val
                uname = u_key
                break

    if not user_record or user_record["password"] != req.password:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials. Please verify username/email and password.",
        )

    # Generate secure session token
    session_token = secrets.token_hex(24)
    user_info = {
        "username": uname,
        "name": user_record["name"],
        "email": user_record["email"],
        "role": user_record["role"],
        "avatar": user_record["avatar"],
    }
    ACTIVE_SESSIONS[session_token] = {
        "username": uname,
        "created_at": time.time(),
        "user": user_info,
    }

    return {"status": "ok", "token": session_token, "user": user_info}


@app.get("/api/auth/me")
async def api_me(current_user: Dict[str, Any] = Depends(get_current_user)):
    return {"status": "ok", "user": current_user}


@app.post("/api/auth/logout")
async def api_logout(
    authorization: Optional[str] = Header(None),
    token: Optional[str] = Query(None),
):
    extracted_token = None
    if authorization and authorization.startswith("Bearer "):
        extracted_token = authorization.split(" ")[1]
    elif token:
        extracted_token = token

    if extracted_token and extracted_token in ACTIVE_SESSIONS:
        del ACTIVE_SESSIONS[extracted_token]

    return {"status": "ok", "message": "Logged out successfully."}


# ==============================================================================
# DASHBOARD STATIC & ASSET ROUTES
# ==============================================================================
@app.get("/", response_class=HTMLResponse)
async def get_index():
    index_path = DASHBOARD_DIR / "index.html"
    if index_path.exists():
        return FileResponse(str(index_path))
    return HTMLResponse("<h1>Dashboard index.html not found</h1>", status_code=404)


@app.get("/style.css")
async def get_css():
    return FileResponse(str(DASHBOARD_DIR / "style.css"), media_type="text/css")


@app.get("/app.js")
async def get_js():
    return FileResponse(str(DASHBOARD_DIR / "app.js"), media_type="application/javascript")


@app.get("/favicon.ico")
async def get_favicon():
    # Return 204 No Content for favicon to eliminate browser 404 logs
    return Response(status_code=204)


# ==============================================================================
# PROTECTED TELEMETRY & RESEARCH DATA ENDPOINTS
# ==============================================================================
@app.get("/api/telemetry")
async def get_telemetry(current_user: Dict[str, Any] = Depends(get_current_user)):
    """Returns the latest 50 events from the local JSONL log."""
    events = []
    if LOCAL_TELEMETRY_FILE.exists():
        try:
            with open(LOCAL_TELEMETRY_FILE, "r", encoding="utf-8") as f:
                lines = f.readlines()
                for line in lines[-50:]:
                    if line.strip():
                        events.append(json.loads(line))
        except Exception as e:
            print(f"[Server] Read error: {e}")
    return {"status": "ok", "count": len(events), "events": events, "user": current_user["username"]}


async def event_generator() -> AsyncGenerator[str, None]:
    """Tails the local telemetry log and streams new events via SSE."""
    file_pos = 0
    if LOCAL_TELEMETRY_FILE.exists():
        file_pos = LOCAL_TELEMETRY_FILE.stat().st_size

    while True:
        await asyncio.sleep(0.15)
        if not LOCAL_TELEMETRY_FILE.exists():
            continue

        try:
            current_size = LOCAL_TELEMETRY_FILE.stat().st_size
            if current_size > file_pos:
                with open(LOCAL_TELEMETRY_FILE, "r", encoding="utf-8") as f:
                    f.seek(file_pos)
                    new_lines = f.readlines()
                    file_pos = f.tell()

                for line in new_lines:
                    if line.strip():
                        yield f"data: {line.strip()}\n\n"
        except Exception:
            pass


@app.get("/api/stream")
async def sse_telemetry_stream(token: Optional[str] = Query(None)):
    """SSE endpoint for live browser updates. Requires valid session token."""
    if not token or token not in ACTIVE_SESSIONS:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session token required for real-time telemetry stream.",
        )

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# Global latest depth matrix (set by main.py via inject_depth_grid)
_LATEST_DEPTH_CM: Optional[list] = None


def inject_depth_grid(matrix_meters):
    """Called by main.py to push latest 8x8 depth matrix (in meters) into the server."""
    global _LATEST_DEPTH_CM
    try:
        import numpy as np
        arr = np.array(matrix_meters, dtype=np.float64)
        cm = (arr * 100.0).tolist()
        _LATEST_DEPTH_CM = cm
    except Exception:
        pass


@app.get("/api/depth_grid")
async def get_depth_grid(token: Optional[str] = Query(None)):
    """Returns the latest 8x8 ToF depth grid in cm as JSON."""
    global _LATEST_DEPTH_CM
    # Drain the queue to get the freshest frame
    if _DEPTH_GRID_QUEUE is not None:
        while not _DEPTH_GRID_QUEUE.empty():
            try:
                raw = _DEPTH_GRID_QUEUE.get_nowait()
                import numpy as np
                arr = np.array(raw, dtype=np.float64)
                _LATEST_DEPTH_CM = (arr * 100.0).tolist()
            except Exception:
                pass
    if _LATEST_DEPTH_CM is None:
        return JSONResponse({"status": "waiting", "grid": None})
    # Sanitize NaN/Inf → -1 so JSON serialization never fails
    import math
    def _sanitize(v):
        if isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
            return -1.0
        return v
    safe_grid = [[_sanitize(v) for v in row] for row in _LATEST_DEPTH_CM]
    return JSONResponse({"status": "ok", "grid": safe_grid})


def _no_camera_frame() -> bytes:
    """Return a small black JPEG with 'NO CAMERA' text when no real feed is available."""
    try:
        import cv2
        import numpy as np

        frame = np.zeros((360, 640, 3), dtype=np.uint8)
        cv2.putText(frame, "NO CAMERA FEED", (160, 180),
                    cv2.FONT_HERSHEY_SIMPLEX, 1.0, (80, 80, 80), 2)
        ret, jpeg = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 50])
        return jpeg.tobytes() if ret else b""
    except Exception:
        return b""


_LATEST_VIDEO_FRAME: Optional[bytes] = None

async def video_stream_generator() -> AsyncGenerator[bytes, None]:
    """Generates MJPEG stream from real video queue with broadcast caching."""
    global _LATEST_VIDEO_FRAME, _VIDEO_QUEUE

    while True:
        try:
            if _VIDEO_QUEUE is not None:
                while not _VIDEO_QUEUE.empty():
                    try:
                        _LATEST_VIDEO_FRAME = _VIDEO_QUEUE.get_nowait()
                    except Exception:
                        break

            frame_bytes = _LATEST_VIDEO_FRAME if _LATEST_VIDEO_FRAME is not None else _no_camera_frame()

            if frame_bytes:
                yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')

            await asyncio.sleep(0.04)  # ~25 FPS
        except Exception:
            await asyncio.sleep(0.05)

@app.get("/api/video_feed")
async def video_feed(token: Optional[str] = Query(None)):
    """MJPEG stream endpoint for live camera feed."""
    return StreamingResponse(
        video_stream_generator(),
        media_type="multipart/x-mixed-replace; boundary=frame",
        headers={
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Pragma": "no-cache",
            "Expires": "0"
        }
    )


@app.get("/api/camera/snapshot")
async def camera_snapshot():
    """Captures and downloads a single high-res JPEG snapshot."""
    frame_bytes = None
    if _VIDEO_QUEUE is not None and not _VIDEO_QUEUE.empty():
        try:
            frame_bytes = _VIDEO_QUEUE.get_nowait()
        except Exception:
            pass

    if not frame_bytes:
        frame_bytes = _no_camera_frame()

    return Response(
        content=frame_bytes,
        media_type="image/jpeg",
        headers={"Content-Disposition": f"attachment; filename=glasses_snapshot_{int(time.time())}.jpg"}
    )


@app.get("/api/export/csv")
async def export_csv(current_user: Dict[str, Any] = Depends(get_current_user)):
    """Exports trial CSV dataset. Requires authentication."""
    csv_path = BASE_DIR / "logs" / "telemetry_events.csv"
    if csv_path.exists():
        return FileResponse(
            str(csv_path),
            filename="smart_glasses_trials.csv",
            media_type="text/csv",
        )
    return Response(content="timestamp,distance_m\n", media_type="text/csv")


def run_dashboard_server(stop_event=None, queue_video_feed=None, queue_depth_grid=None):
    """Entrypoint to launch dashboard server."""
    global _VIDEO_QUEUE, _DEPTH_GRID_QUEUE
    _VIDEO_QUEUE = queue_video_feed
    _DEPTH_GRID_QUEUE = queue_depth_grid

    # Free port if already bound (stale process from previous run)
    import socket, os, signal as _signal
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
        sock.bind(('0.0.0.0', DASHBOARD_PORT))
        sock.close()
    except OSError:
        # Port truly stuck — find and kill the holder
        try:
            import subprocess
            r = subprocess.check_output(
                ['fuser', f'{DASHBOARD_PORT}/tcp'], stderr=subprocess.DEVNULL
            ).decode().strip()
            for pid_str in r.split():
                try:
                    os.kill(int(pid_str), _signal.SIGKILL)
                except Exception:
                    pass
            time.sleep(1)
        except Exception:
            pass

    print(f"[Dashboard Server] Serving with Authentication on http://{DASHBOARD_HOST}:{DASHBOARD_PORT}")
    cfg = uvicorn.Config(
        app,
        host=DASHBOARD_HOST,
        port=DASHBOARD_PORT,
        log_level="warning",
        access_log=False,
    )
    server = uvicorn.Server(cfg)
    server.run()


if __name__ == "__main__":
    run_dashboard_server()
