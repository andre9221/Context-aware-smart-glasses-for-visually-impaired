"""main_haptic.py

Master Controller for Module 3 (Spatio-Tactile Haptics & Telemetry Streamer).
Consumes classified hazard packets from Queue B, encodes them into 3-axis tactile
commands, fires the LRA transducers FIRST, and logs telemetry to Firebase SECOND.

Target: IEEE Sensors Journal.
"""

from __future__ import annotations

import math
import queue
import sys
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

# Ensure config imports resolve from project root
try:
    import config
    from module3_haptic import haptic_encoder
    from module3_haptic.firebase_logger import FirebaseLogger
except ImportError:
    project_root = Path(__file__).resolve().parent.parent
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))
    import config
    from module3_haptic import haptic_encoder
    from module3_haptic.firebase_logger import FirebaseLogger

# Priority rank for pre-emption (higher rank pre-empts lower rank on same motor)
URGENCY_RANK: Dict[str, int] = {
    config.URGENCY_IMMINENT: 2,
    config.URGENCY_APPROACHING: 1,
    config.URGENCY_SAFE: 0,
}


def _extract_primary_hazard(
    packet_or_list: Union[Dict[str, Any], List[Dict[str, Any]]]
) -> Optional[Dict[str, Any]]:
    """Select the primary hazard dict representing the actuation packet."""
    if isinstance(packet_or_list, dict):
        return packet_or_list
    elif isinstance(packet_or_list, list) and len(packet_or_list) > 0:
        valid_items = [p for p in packet_or_list if isinstance(p, dict)]
        if not valid_items:
            return None

        # Pick item with lowest effective TTC (matching encoder logic)
        def _key(p: Dict[str, Any]) -> float:
            ttc = p.get("ttc")
            if ttc is None:
                return config.TTC_SENTINEL_SAFE
            try:
                val = float(ttc)
                if math.isnan(val) or val < config.TTC_MIN_VALID or val > config.TTC_MAX_VALID:
                    return config.TTC_SENTINEL_SAFE
                return val
            except (ValueError, TypeError):
                return config.TTC_SENTINEL_SAFE

        return min(valid_items, key=_key)
    return None


def run_haptic_module(
    queue_b: queue.Queue,
    duration_sec: Optional[float] = None,
    stop_event: Optional[threading.Event] = None,
    driver_override: Optional[Any] = None,
    logger_override: Optional[Any] = None,
    use_visualizer: Optional[bool] = None,
) -> int:
    """Main execution loop for Module 3.

    1. Reads incoming hazard packets from Queue B.
    2. Encodes via haptic_encoder.
    3. Fires tactile actuation FIRST (via visualizer or DRV2605L driver).
       Catches driver exceptions, tracks fire_errors, and continues running.
    4. Computes latency_ms = (fire_time - packet_ts) * 1000 and logs SECOND.
    5. Schedules non-blocking repeat retriggering:
       - A same-urgency packet refreshes the hazard timeout without restarting the effect.
       - A higher-urgency packet pre-empts immediately.
       - A downgrade is accepted once the current effect's minimum play time has elapsed.
       - If no packet refreshes a motor within HAZARD_TIMEOUT_MS (500 ms), stops retriggering.
    6. Shuts down gracefully on KeyboardInterrupt or stop_event.

    Returns:
        Cumulative count of driver fire errors encountered.
    """
    if stop_event is None:
        stop_event = threading.Event()

    # Determine visualizer vs hardware driver mode
    show_visualizer = (
        use_visualizer
        if use_visualizer is not None
        else (config.SIMULATION_MODE and driver_override is None)
    )

    visualizer = None
    hardware_driver = None

    if show_visualizer:
        from module3_haptic.sim_haptic import TerminalVisualizer
        visualizer = TerminalVisualizer()
    elif driver_override is not None:
        hardware_driver = driver_override
    else:
        # Lazy import of hardware driver: no top-level hardware imports
        from module3_haptic import drv2605l_driver
        hardware_driver = drv2605l_driver
        try:
            drv2605l_driver.init()
        except Exception as e:
            sys.stderr.write(f"[HARDWARE WARNING] Driver init skipped: {e}\n")

    # Telemetry Logger
    logger = logger_override if logger_override is not None else FirebaseLogger()

    # Per-motor state tracking: motor_index -> state dict
    motor_scheduler: Dict[int, Dict[str, Any]] = {
        m: {
            "active": False,
            "effect_id": None,
            "repeat_ms": None,
            "urgency": None,
            "urgency_rank": -1,
            "last_fire_time": 0.0,
            "next_retrigger": 0.0,
            "timeout_deadline": 0.0,
            "hazard_class": None,
        }
        for m in (
            config.MOTOR_INDEX_LEFT,
            config.MOTOR_INDEX_CENTER,
            config.MOTOR_INDEX_RIGHT,
        )
    }

    fire_errors: int = 0
    start_mono = time.monotonic()
    hazard_timeout_sec = config.HAZARD_TIMEOUT_MS / 1000.0

    try:
        while not stop_event.is_set():
            if duration_sec is not None:
                if (time.monotonic() - start_mono) >= duration_sec:
                    break

            now_mono = time.monotonic()
            now_wall = time.time()

            # ------------------------------------------------------------------
            # 1. READ QUEUE B & ENCODE
            # ------------------------------------------------------------------
            try:
                packet_payload = queue_b.get(timeout=0.02)
                res = haptic_encoder.encode(packet_payload)

                if res is not None:
                    motor_idx, effect_id, repeat_ms, urgency = res
                    primary_packet = _extract_primary_hazard(packet_payload) or {}

                    sched = motor_scheduler[motor_idx]
                    new_rank = URGENCY_RANK.get(urgency, 0)
                    old_rank = sched["urgency_rank"] if sched["active"] else -1

                    should_fire = False
                    fire_error_msg: Optional[str] = None

                    # Check transition conditions:
                    if sched["active"] and new_rank == old_rank and sched["effect_id"] == effect_id:
                        # Same urgency: Refresh timeout without restarting the effect
                        sched["timeout_deadline"] = now_mono + hazard_timeout_sec
                        should_fire = False
                    elif sched["active"] and new_rank < old_rank:
                        # Downgrade: Accepted once current effect's minimum play time has elapsed
                        min_play_ms = config.EFFECT_MIN_DURATION_MS.get(
                            sched["effect_id"], config.DEFAULT_MIN_PLAY_TIME_MS
                        )
                        elapsed_ms = (now_mono - sched.get("effect_start_time", sched["last_fire_time"])) * 1000.0
                        if elapsed_ms >= min_play_ms:
                            should_fire = True
                        else:
                            # Not ready for downgrade yet; refresh timeout deadline and wait
                            sched["timeout_deadline"] = now_mono + hazard_timeout_sec
                            should_fire = False
                    else:
                        # Higher urgency (pre-emption) or new motor activation: fire immediately
                        should_fire = True

                    # ----------------------------------------------------------
                    # 2. FIRE HAPTIC FIRST (wrapped in try/except)
                    # ----------------------------------------------------------
                    fire_wall_time = time.time()
                    fire_mono_time = time.monotonic()

                    if should_fire:
                        if hardware_driver is not None:
                            try:
                                hardware_driver.fire(motor_idx, effect_id, repeat_ms)
                            except Exception as exc:
                                fire_errors += 1
                                fire_error_msg = str(exc)

                        if visualizer is not None:
                            cls_name = primary_packet.get("class", "unknown")
                            ttc = primary_packet.get("ttc")
                            ttc_str = f"{ttc:.2f}s" if isinstance(ttc, (int, float)) else str(ttc)
                            dist = primary_packet.get("distance", 0.0)
                            desc = f"{cls_name.upper()} @ {primary_packet.get('azimuth')} (TTC: {ttc_str}, Dist: {dist:.1f}m)"

                            visualizer.update_actuation(
                                motor_index=motor_idx,
                                effect_id=effect_id,
                                repeat_ms=repeat_ms,
                                urgency=urgency,
                                hazard_desc=desc,
                            )

                        # Update state for newly triggered effect
                        sched["active"] = True
                        sched["effect_id"] = effect_id
                        sched["repeat_ms"] = repeat_ms
                        sched["urgency"] = urgency
                        sched["urgency_rank"] = new_rank
                        sched["effect_start_time"] = fire_mono_time
                        sched["last_fire_time"] = fire_mono_time
                        sched["next_retrigger"] = fire_mono_time + (repeat_ms / 1000.0)
                        sched["timeout_deadline"] = fire_mono_time + hazard_timeout_sec
                        sched["hazard_class"] = primary_packet.get("class")

                    # ----------------------------------------------------------
                    # 3. LOG SECOND (Compute latency_ms at moment of firing)
                    # ----------------------------------------------------------
                    raw_ts = primary_packet.get("ts")
                    if isinstance(raw_ts, (int, float)) and not math.isnan(raw_ts):
                        latency_ms = max(0.0, (fire_wall_time - float(raw_ts)) * 1000.0)
                    else:
                        latency_ms = 0.0

                    event_log_payload = {
                        "ts": raw_ts if raw_ts is not None else fire_wall_time,
                        "azimuth": primary_packet.get("azimuth"),
                        "distance": primary_packet.get("distance"),
                        "ttc": primary_packet.get("ttc"),
                        "class": primary_packet.get("class"),
                        "effect_id": effect_id,
                        "urgency": urgency,
                        "latency_ms": latency_ms,
                    }

                    if fire_error_msg is not None:
                        event_log_payload["error"] = fire_error_msg

                    if "seq_id" in primary_packet:
                        event_log_payload["seq_id"] = primary_packet["seq_id"]

                    logger.push_event(event_log_payload)

            except queue.Empty:
                pass

            # ------------------------------------------------------------------
            # 4. NON-BLOCKING RETRIGGER & TIMEOUT SCHEDULER
            # ------------------------------------------------------------------
            now_mono = time.monotonic()
            for m, sched in motor_scheduler.items():
                if sched["active"]:
                    # Hazard timeout check: clear motor if no refresh within 500 ms
                    if now_mono >= sched["timeout_deadline"]:
                        sched["active"] = False
                        sched["effect_id"] = None
                        sched["urgency_rank"] = -1
                        if visualizer is not None:
                            visualizer.motor_states[m]["active"] = False
                            visualizer.motor_states[m]["retrigger_enabled"] = False
                    elif sched["repeat_ms"] is not None and now_mono >= sched["next_retrigger"]:
                        # Retrigger interval elapsed: fire repeat pulse
                        if hardware_driver is not None:
                            try:
                                hardware_driver.fire(m, sched["effect_id"], sched["repeat_ms"])
                            except Exception as exc:
                                fire_errors += 1

                        sched["next_retrigger"] = now_mono + (sched["repeat_ms"] / 1000.0)

            # Step and render visualizer if active
            if visualizer is not None:
                visualizer.step_scheduler()
                visualizer.render()
                time.sleep(0.02)  # ~50 Hz update

    except KeyboardInterrupt:
        pass
    finally:
        # Graceful shutdown: stop timers, flush and close logger
        if logger is not None:
            try:
                logger.close()
            except Exception:
                pass

        if visualizer is not None:
            visualizer.restore_terminal()

        print("[MODULE 3] Haptic Controller shutdown cleanly.")

    return fire_errors


def main() -> None:
    """Standalone entry point: starts mock Queue B feeder and runs master loop."""
    print("=" * 76)
    print("   CONTEXT-AWARE SMART GLASSES — MODULE 3 MASTER RUNNER")
    print("        (Standalone Testbed: Mock Feeder -> Haptics -> Telemetry)")
    print("=" * 76)

    from module3_haptic.sim_haptic import MockQueueBFeeder

    queue_b: queue.Queue = queue.Queue(maxsize=20)
    feeder = MockQueueBFeeder(queue_b, interval_sec=2.0)
    feeder.start()

    try:
        run_haptic_module(queue_b=queue_b)
    finally:
        feeder.stop()


if __name__ == "__main__":
    main()
