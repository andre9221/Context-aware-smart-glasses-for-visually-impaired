"""sim_haptic.py

Terminal Visualizer and Mock Feeder for Spatio-Tactile Haptic Simulation (Module 3).
Provides:
1. MockQueueBFeeder: Background thread pushing scripted hazard scenarios to Queue B.
2. TerminalVisualizer: In-place redrawn 3-column [ LEFT ][ CENTER ][ RIGHT ] display
   showing active LRA motor pulses (🔥), effect ID, urgency, repeat_ms, and dropped packets.
3. Non-blocking per-motor retrigger scheduler.

Target: IEEE Sensors Journal.
"""

from __future__ import annotations

import copy
import queue
import sys
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

# Ensure imports resolve from root or package
try:
    import config
    from module3_haptic import haptic_encoder
except ImportError:
    project_root = Path(__file__).resolve().parent.parent
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))
    import config
    from module3_haptic import haptic_encoder

# Human-readable effect descriptions from DRV2605L Library 6 (LRA)
EFFECT_DESCRIPTIONS: Dict[int, str] = {
    7: "Soft Bump 100%",
    8: "Soft Bump 60%",
    9: "Soft Bump 30%",
    4: "Sharp Click 100%",
    5: "Sharp Click 60%",
    6: "Sharp Click 30%",
    16: "1000ms Alert 100%",
    15: "750ms Alert 100%",
    10: "Double Click 100%",
    11: "Double Click 60%",
    3: "Strong Click 30%",
}


def get_scripted_scenarios() -> List[Union[Dict[str, Any], List[Dict[str, Any]]]]:
    """Return the list of 6 scripted test scenarios for Queue B simulation.

    1. person center TTC 1.5
    2. vehicle left TTC 0.5
    3. overhead branch right TTC 1.4
    4. simultaneous L+R hazards (as a list)
    5. bad packet (unknown class)
    6. packet with ttc None
    """
    now = time.time()
    return [
        # Scenario 1: person center TTC 1.5
        {
            "ts": now,
            "azimuth": "C",
            "distance": 1.8,
            "ttc": 1.5,
            "class": "person",
            "elevation": "head",
        },
        # Scenario 2: vehicle left TTC 0.5
        {
            "ts": now,
            "azimuth": "L",
            "distance": 3.0,
            "ttc": 0.5,
            "class": "vehicle",
            "elevation": "ground",
        },
        # Scenario 3: overhead branch right TTC 1.4
        {
            "ts": now,
            "azimuth": "R",
            "distance": 1.2,
            "ttc": 1.4,
            "class": "overhead",
            "elevation": "head",
        },
        # Scenario 4: simultaneous L+R hazards (as a list)
        [
            {
                "ts": now,
                "azimuth": "L",
                "distance": 2.5,
                "ttc": 0.6,
                "class": "vehicle",
                "elevation": "ground",
            },
            {
                "ts": now,
                "azimuth": "R",
                "distance": 1.0,
                "ttc": 1.8,
                "class": "wall",
                "elevation": "ground",
            },
        ],
        # Scenario 5: bad packet (unknown class) -> dropped & counted
        {
            "ts": now,
            "azimuth": "C",
            "distance": 2.0,
            "ttc": 1.0,
            "class": "drone",
            "elevation": "head",
        },
        # Scenario 6: packet with ttc None -> safe urgency
        {
            "ts": now,
            "azimuth": "C",
            "distance": 1.1,
            "ttc": None,
            "class": "wall",
            "elevation": "ground",
        },
    ]


class MockQueueBFeeder:
    """Mock Queue B feeder thread that periodically pushes scripted hazard packets."""

    def __init__(self, q: queue.Queue, interval_sec: float = 2.0) -> None:
        self.queue: queue.Queue = q
        self.interval_sec: float = interval_sec
        self._stop_event: threading.Event = threading.Event()
        self._thread: Optional[threading.Thread] = None

    def start(self) -> None:
        """Start background feeder thread."""
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._run_loop, name="MockQueueBFeeder", daemon=True
        )
        self._thread.start()

    def stop(self) -> None:
        """Signal feeder thread to stop and wait for termination."""
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.0)

    def _run_loop(self) -> None:
        idx = 0
        while not self._stop_event.is_set():
            scenarios = get_scripted_scenarios()
            scenario = scenarios[idx % len(scenarios)]
            idx += 1

            # Update timestamp to current epoch
            now = time.time()
            if isinstance(scenario, list):
                payload = []
                for p in scenario:
                    item = copy.deepcopy(p)
                    item["ts"] = now
                    payload.append(item)
            else:
                payload = copy.deepcopy(scenario)
                payload["ts"] = now

            self.queue.put(payload)
            self._stop_event.wait(self.interval_sec)


class TerminalVisualizer:
    """Renders in-place 3-column spatio-tactile neckband haptic state."""

    def __init__(self) -> None:
        # Per-motor state: 0 (Left), 1 (Center), 2 (Right)
        self.motor_states: Dict[int, Dict[str, Any]] = {
            m: {
                "active": False,
                "effect_id": None,
                "repeat_ms": None,
                "urgency": None,
                "active_until": 0.0,
                "next_retrigger": 0.0,
                "retrigger_enabled": False,
                "pulse_count": 0,
            }
            for m in (
                config.MOTOR_INDEX_LEFT,
                config.MOTOR_INDEX_CENTER,
                config.MOTOR_INDEX_RIGHT,
            )
        }
        self.last_hazard_desc: str = "Awaiting hazard packets..."
        self._setup_terminal()

    def _setup_terminal(self) -> None:
        """Hide cursor for clean in-place terminal drawing."""
        sys.stdout.write("\033[?25l")  # Hide cursor
        sys.stdout.flush()

    def restore_terminal(self) -> None:
        """Restore cursor visibility and clear screen."""
        sys.stdout.write("\033[?25h\n")  # Show cursor
        sys.stdout.flush()

    def update_actuation(
        self,
        motor_index: int,
        effect_id: int,
        repeat_ms: int,
        urgency: str,
        hazard_desc: str = "",
    ) -> None:
        """Activate motor with a tactile pulse and schedule non-blocking retriggering."""
        now = time.monotonic()
        # Pulse visual active timeout (e.g. 350ms or repeat_ms / 1000, whichever is smaller)
        active_window = min(0.35, (repeat_ms / 1000.0) * 0.8)

        # Clear other motors if hazard changed focus
        for m in self.motor_states:
            if m != motor_index:
                self.motor_states[m]["retrigger_enabled"] = False
                self.motor_states[m]["active"] = False

        state = self.motor_states[motor_index]
        state["active"] = True
        state["effect_id"] = effect_id
        state["repeat_ms"] = repeat_ms
        state["urgency"] = urgency
        state["active_until"] = now + active_window
        state["next_retrigger"] = now + (repeat_ms / 1000.0)
        state["retrigger_enabled"] = True
        state["pulse_count"] += 1

        if hazard_desc:
            self.last_hazard_desc = hazard_desc

    def step_scheduler(self) -> None:
        """Non-blocking retrigger check and pulse-decay update."""
        now = time.monotonic()
        for m, state in self.motor_states.items():
            # Check if active visual pulse expired
            if state["active"] and now >= state["active_until"]:
                state["active"] = False

            # Check if scheduled non-blocking repeat trigger is due
            if state["retrigger_enabled"] and now >= state["next_retrigger"]:
                active_window = min(0.35, (state["repeat_ms"] / 1000.0) * 0.8)
                state["active"] = True
                state["active_until"] = now + active_window
                state["next_retrigger"] = now + (state["repeat_ms"] / 1000.0)
                state["pulse_count"] += 1

    def render(self) -> None:
        """Render the 3-column in-place visualization without scrolling spam."""
        cols = {0: "LEFT", 1: "CENTER", 2: "RIGHT"}
        col_width = 24

        lines = []
        lines.append("\033[H\033[J")  # ANSI clear screen & move to top-left
        lines.append("=" * 76)
        lines.append(
            "   CONTEXT-AWARE SMART GLASSES — SPATIO-TACTILE HAPTIC SIMULATOR"
        )
        lines.append(
            "             (Module 3 Neckband LRAs | IEEE Sensors Journal)"
        )
        lines.append("=" * 76)
        dropped = haptic_encoder.get_dropped_count()
        lines.append(
            f" Runtime: SIMULATION_MODE={config.SIMULATION_MODE} | Dropped Packets: {dropped}"
        )
        lines.append("-" * 76)

        # Header columns
        header_row = (
            f"[ {cols[0]:^{col_width-4}} ] "
            f"[ {cols[1]:^{col_width-4}} ] "
            f"[ {cols[2]:^{col_width-4}} ]"
        )
        lines.append(header_row)

        # Build column rows
        rows = [[] for _ in range(5)]
        for m in (0, 1, 2):
            st = self.motor_states[m]
            if st["active"]:
                eff_id = st["effect_id"]
                eff_name = EFFECT_DESCRIPTIONS.get(eff_id, "Unknown")
                urg_str = f"Urg: {str(st['urgency']).upper()}"
                eff_str = f"Effect: #{eff_id}"
                rep_str = f"Repeat: {st['repeat_ms']}ms"

                rows[0].append(f"[ {'🔥 FIRE 🔥':^{col_width-4}} ]")
                rows[1].append(f"[ {eff_str:^{col_width-4}} ]")
                rows[2].append(f"[ {eff_name:^{col_width-4}} ]")
                rows[3].append(f"[ {urg_str:^{col_width-4}} ]")
                rows[4].append(f"[ {rep_str:^{col_width-4}} ]")
            else:
                rows[0].append(f"[ {'(IDLE)':^{col_width-4}} ]")
                rows[1].append(f"[ {'':^{col_width-4}} ]")
                rows[2].append(f"[ {'':^{col_width-4}} ]")
                rows[3].append(f"[ {'':^{col_width-4}} ]")
                rows[4].append(f"[ {'':^{col_width-4}} ]")

        for row in rows:
            lines.append(" ".join(row))

        lines.append("-" * 76)
        lines.append(f" Hazard Feed : {self.last_hazard_desc}")
        lines.append(" Control     : Press Ctrl+C to terminate simulation.")
        lines.append("=" * 76)

        sys.stdout.write("\n".join(lines) + "\n")
        sys.stdout.flush()


def run_simulator(
    duration_sec: Optional[float] = None, interval_sec: float = 2.0
) -> None:
    """Run standalone simulation: Feeder -> Queue B -> Encoder -> Visualizer."""
    q: queue.Queue = queue.Queue(maxsize=20)
    feeder = MockQueueBFeeder(q, interval_sec=interval_sec)
    visualizer = TerminalVisualizer()

    feeder.start()
    start_time = time.monotonic()

    try:
        while True:
            # Check duration limit if set
            if duration_sec is not None:
                if (time.monotonic() - start_time) >= duration_sec:
                    break

            # Non-blocking packet fetch (20ms timeout for ~50Hz check)
            try:
                packet = q.get(timeout=0.02)
                res = haptic_encoder.encode(packet)
                if res is not None:
                    motor_idx, effect_id, repeat_ms, urgency = res
                    # Format descriptive text for terminal display
                    if isinstance(packet, list):
                        desc = f"Multi-Hazard ({len(packet)} hazards) -> Motor {motor_idx} chosen (TTC priority)"
                    else:
                        cls_name = packet.get("class", "unknown")
                        ttc = packet.get("ttc")
                        ttc_str = f"{ttc:.2f}s" if isinstance(ttc, (int, float)) else str(ttc)
                        dist = packet.get("distance", 0.0)
                        desc = f"{cls_name.upper()} @ {packet.get('azimuth')} (TTC: {ttc_str}, Dist: {dist:.1f}m)"

                    visualizer.update_actuation(
                        motor_index=motor_idx,
                        effect_id=effect_id,
                        repeat_ms=repeat_ms,
                        urgency=urgency,
                        hazard_desc=desc,
                    )
                else:
                    # Dropped or empty packet
                    if isinstance(packet, dict):
                        cls_name = packet.get("class", "unknown")
                        visualizer.last_hazard_desc = (
                            f"DROPPED: Malformed or Unknown Class ({cls_name!r})"
                        )
                    else:
                        visualizer.last_hazard_desc = "DROPPED: Malformed packet payload"
            except queue.Empty:
                pass

            # Step non-blocking timers and render UI
            visualizer.step_scheduler()
            visualizer.render()
            time.sleep(0.03)  # ~30 FPS terminal refresh

    except KeyboardInterrupt:
        pass
    finally:
        feeder.stop()
        visualizer.restore_terminal()
        print("\n[SIMULATION] Haptic Simulator stopped gracefully.")


if __name__ == "__main__":
    run_simulator()
