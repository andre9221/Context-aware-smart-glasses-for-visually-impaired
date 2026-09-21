"""firebase_logger.py

Background telemetry logger for Module 3 (Haptics & Cloud Telemetry).
Target: IEEE Sensors Journal.

Features:
- Non-blocking push_event() with bounded queue (maxsize 200) and drop-oldest overflow policy.
- Batch writes using a single multi-path update() call to /sessions/{session_id}/events/{pushId}.
- Periodic heartbeat to /sessions/{session_id}/status {online, battery, last_seen} every 5 s.
- Safe mock mode: prints compact line if SIMULATION_MODE is active or credentials are missing.
- Credentials loaded exclusively from config.py / environment; never logged or exposed.
- Robust exception handling: worker survives transient network/database errors.
"""

from __future__ import annotations

import math
import queue
import sys
import threading
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

# Ensure config imports resolve from project root
try:
    import config
except ImportError:
    project_root = Path(__file__).resolve().parent.parent
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))
    import config


def _sanitize_numeric(val: Any) -> Optional[float]:
    """Convert value to float, returning None if None, NaN, or inf."""
    if val is None:
        return None
    try:
        f = float(val)
        if math.isnan(f) or math.isinf(f):
            return None
        return f
    except (ValueError, TypeError):
        return None


def sanitize_event(event: Dict[str, Any]) -> Dict[str, Any]:
    """Sanitize event dictionary to ensure safe telemetry transmission.

    Rules:
    - Numbers and strings only.
    - Converts NaN and inf to None.
    - String fields capped to 32 characters.
    - Preserves ttc as float or None.
    """
    sanitized: Dict[str, Any] = {}

    # Numeric fields (NaN/inf converted to None)
    for num_key in ("ts", "distance", "latency_ms", "ttc"):
        sanitized[num_key] = _sanitize_numeric(event.get(num_key))

    # Effect ID (integer or None)
    eff_val = event.get("effect_id")
    eff_num = _sanitize_numeric(eff_val)
    if eff_num is not None:
        sanitized["effect_id"] = int(eff_num)
    else:
        sanitized["effect_id"] = None

    # String fields (capped to 32 characters)
    for str_key in ("azimuth", "class", "urgency"):
        val = event.get(str_key, "")
        if val is None:
            sanitized[str_key] = None
        else:
            if not isinstance(val, str):
                val = str(val)
            sanitized[str_key] = val[:32]

    # Preserve optional tracking keys (such as seq_id for testing)
    if "seq_id" in event:
        sanitized["seq_id"] = event["seq_id"]

    return sanitized


def generate_push_id() -> str:
    """Generate a chronological unique push ID for Firebase RTDB."""
    # Millisecond epoch prefix ensures chronological sorting
    prefix = hex(int(time.time() * 1000))[2:]
    suffix = uuid.uuid4().hex[:12]
    return f"-{prefix}_{suffix}"


class FirebaseLogger:
    """Thread-safe, non-blocking telemetry streamer to Firebase Realtime Database."""

    def __init__(
        self,
        db_client: Optional[Any] = None,
        session_id: Optional[str] = None,
        mock_mode: Optional[bool] = None,
        auto_start_worker: bool = True,
    ) -> None:
        self._session_id: str = session_id or config.SESSION_ID
        self._queue: queue.Queue = queue.Queue(maxsize=200)
        self._dropped_events: int = 0
        self._lock: threading.Lock = threading.Lock()
        self._stop_event: threading.Event = threading.Event()
        self._worker_thread: Optional[threading.Thread] = None

        self._db_client: Optional[Any] = db_client
        self._db_ref: Optional[Any] = None
        self._last_status_write: float = 0.0

        # Determine mock mode:
        # If mock_mode is explicit, use it.
        # Otherwise, enable mock mode if SIMULATION_MODE is on OR credentials are missing.
        if mock_mode is not None:
            self._is_mock = mock_mode
        elif config.SIMULATION_MODE or self._db_client is not None:
            self._is_mock = (self._db_client is None) and config.SIMULATION_MODE
        else:
            cred_file = Path(config.FIREBASE_CRED_PATH)
            self._is_mock = not cred_file.is_file()

        # Initialize Real Firebase Admin SDK if not in mock mode and no client injected
        if not self._is_mock and self._db_client is None:
            self._init_firebase_sdk()

        if auto_start_worker:
            self.start_worker()

    def _init_firebase_sdk() -> None:
        """Initialize Firebase Admin SDK using path from config.py."""
        try:
            import firebase_admin
            from firebase_admin import credentials, db

            cred_path = Path(config.FIREBASE_CRED_PATH)
            if not cred_path.is_file():
                # Fallback gracefully to mock mode if credentials file is absent
                self._is_mock = True
                return

            cred = credentials.Certificate(str(cred_path))
            try:
                firebase_admin.get_app()
            except ValueError:
                firebase_admin.initialize_app(
                    cred, {"databaseURL": config.FIREBASE_DB_URL}
                )
            self._db_ref = db.reference()
            self._is_mock = False
        except Exception:
            # Never crash on initialization failure; fallback to mock mode
            self._is_mock = True

    def start_worker(self) -> None:
        """Start the background worker thread."""
        with self._lock:
            if self._worker_thread is None or not self._worker_thread.is_alive():
                self._stop_event.clear()
                self._worker_thread = threading.Thread(
                    target=self._worker_loop, name="FirebaseLoggerWorker", daemon=True
                )
                self._worker_thread.start()

    def get_dropped_events(self) -> int:
        """Return cumulative count of dropped telemetry events."""
        with self._lock:
            return self._dropped_events

    def is_alive(self) -> bool:
        """Return True if background worker thread is currently running."""
        with self._lock:
            return self._worker_thread is not None and self._worker_thread.is_alive()

    def push_event(self, event: Dict[str, Any]) -> None:
        """Enqueue an event for telemetry transmission.

        Must return immediately and NEVER block the caller (execution < 5 ms).
        Drops the oldest event on queue overflow.
        """
        try:
            if not isinstance(event, dict):
                with self._lock:
                    self._dropped_events += 1
                return

            sanitized = sanitize_event(event)

            try:
                self._queue.put_nowait(sanitized)
            except queue.Full:
                # Overflow policy: drop OLDEST event to make room
                with self._lock:
                    try:
                        self._queue.get_nowait()
                        self._dropped_events += 1
                    except queue.Empty:
                        pass
                    try:
                        self._queue.put_nowait(sanitized)
                    except queue.Full:
                        self._dropped_events += 1
        except Exception:
            # push_event must never raise an exception into the caller
            pass

    def _worker_loop(self) -> None:
        """Background thread worker loop: batches events and sends periodic status."""
        batch: List[Dict[str, Any]] = []
        batch_deadline = time.monotonic() + 0.5  # 500 ms window
        self._last_status_write = 0.0  # Force immediate initial status write

        while not self._stop_event.is_set():
            now = time.monotonic()

            # Heartbeat check: update /sessions/{session_id}/status every 5 s
            if (now - self._last_status_write) >= 5.0:
                self._write_status(online=True)
                self._last_status_write = time.monotonic()

            # Calculate remaining timeout for 500 ms batch window
            timeout = max(0.01, min(0.1, batch_deadline - now))

            try:
                item = self._queue.get(timeout=timeout)
                batch.append(item)
                if len(batch) >= 20:
                    self._flush_batch(batch)
                    batch = []
                    batch_deadline = time.monotonic() + 0.5
            except queue.Empty:
                if batch and time.monotonic() >= batch_deadline:
                    self._flush_batch(batch)
                    batch = []
                    batch_deadline = time.monotonic() + 0.5

        # Process any remaining events in queue upon shutdown
        while not self._queue.empty():
            try:
                batch.append(self._queue.get_nowait())
                if len(batch) >= 20:
                    self._flush_batch(batch)
                    batch = []
            except queue.Empty:
                break

        if batch:
            self._flush_batch(batch)

    def _flush_batch(self, batch: List[Dict[str, Any]]) -> None:
        """Write a batch of events using a single multi-path update() call."""
        if not batch:
            return

        try:
            if self._is_mock:
                for ev in batch:
                    ttc_val = ev.get("ttc")
                    ttc_repr = f"{ttc_val:.2f}s" if ttc_val is not None else "None"
                    lat_val = ev.get("latency_ms")
                    lat_repr = f"{lat_val:.1f}ms" if lat_val is not None else "None"
                    print(
                        f"[FIREBASE MOCK] Event pushed: az={ev.get('azimuth')} "
                        f"cls={ev.get('class')} eff=#{ev.get('effect_id')} urg={ev.get('urgency')} "
                        f"ttc={ttc_repr} lat={lat_repr}"
                    )
            else:
                # Build single multi-path update dictionary
                updates: Dict[str, Any] = {}
                for ev in batch:
                    push_id = generate_push_id()
                    updates[f"sessions/{self._session_id}/events/{push_id}"] = ev

                if self._db_client is not None:
                    # Fake / custom DB client receives single update() call
                    self._db_client.update(updates)
                elif self._db_ref is not None:
                    # Real Firebase RTDB multi-path update
                    self._db_ref.update(updates)
        except Exception as e:
            # Worker survives exceptions and keeps running
            sys.stderr.write(f"[FIREBASE ERROR] Failed writing batch of {len(batch)} events: {e}\n")

    def _write_status(self, online: bool) -> None:
        """Write system status heartbeat to /sessions/{session_id}/status."""
        status_payload = {
            "online": online,
            "battery": None,  # Real source not connected yet; do not fake it
            "last_seen": float(time.time()),  # Epoch float updated with each heartbeat
        }

        try:
            if self._is_mock:
                pass
            elif self._db_client is not None:
                self._db_client.update({f"sessions/{self._session_id}/status": status_payload})
            elif self._db_ref is not None:
                status_node = self._db_ref.child(f"sessions/{self._session_id}/status")
                status_node.set(status_payload)
        except Exception as e:
            sys.stderr.write(f"[FIREBASE ERROR] Failed writing status: {e}\n")

    def close(self) -> None:
        """Gracefully terminate logger: flush remaining events and write offline status."""
        self._stop_event.set()
        if self._worker_thread and self._worker_thread.is_alive():
            self._worker_thread.join(timeout=2.0)

        # Final offline status write
        self._write_status(online=False)
