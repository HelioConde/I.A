from __future__ import annotations

import json
import tempfile
import threading
import unittest
import sys
from pathlib import Path
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from brain_ssd.hud.server import create_server
from brain_ssd.hud.state import HudRuntime, HudStateStore
from brain_ssd.observability.bus import BrainEventBus
from brain_ssd.observability.demo import build_demo_events
from brain_ssd.observability.events import BrainEvent, EventStatus
from brain_ssd.observability.narrator import EventNarrator
from brain_ssd.observability.replay import phase4d_replay_events
from brain_ssd.observability.snapshots import read_snapshot, write_snapshot


class HudObservabilityTests(unittest.TestCase):
    def test_phase4ew_validation_metadata_is_explicit(self):
        runtime = HudRuntime()
        runtime.state.reset(
            data_source="PHASE 4E-W WINDOWS LIVE",
            demo_data=False,
            validation={"track": "PHASE 4E-W", "platform": "Windows Native", "canonical_phase4e": False, "target_8gb": "NOT_TESTED"},
        )
        validation = runtime.state.snapshot()["validation"]
        self.assertEqual(validation["track"], "PHASE 4E-W")
        self.assertEqual(validation["platform"], "Windows Native")
        self.assertFalse(validation["canonical_phase4e"])
        self.assertEqual(validation["target_8gb"], "NOT_TESTED")

    def test_event_roundtrip_and_unknown_forward_compatibility(self):
        original = BrainEvent(
            event_type="future_event",
            component="new_component",
            status=EventStatus.INFO,
            metrics={"finite": 1.5, "bad": float("inf")},
            payload_summary={"items": [1, 2]},
        )
        restored = BrainEvent.from_json(original.to_json())
        self.assertEqual(restored, original)
        self.assertEqual(restored.event_type, "FUTURE_EVENT")
        self.assertEqual(restored.status, "INFO")
        self.assertIsNone(restored.metrics["bad"])
        self.assertFalse(restored.known_type)

    def test_bus_orders_events_and_drops_oldest_without_blocking(self):
        bus = BrainEventBus(capacity=8)
        published = [bus.publish(BrainEvent("WARNING", "TEST")) for _ in range(12)]
        self.assertEqual([event.sequence for event in published], list(range(1, 13)))
        self.assertEqual([event.sequence for event in bus.snapshot()], list(range(5, 13)))
        self.assertEqual(bus.dropped_count, 4)

    def test_hud_can_be_disconnected_and_does_not_mutate_input_payload(self):
        payload = {"query": "unchanged", "nested": [1, 2]}
        event = BrainEvent("QUERY_RECEIVED", "INPUT", payload_summary=payload)
        payload["nested"].append(3)
        runtime = HudRuntime()
        runtime.emit(event)
        self.assertEqual(runtime.state.snapshot()["query"], "unchanged")
        self.assertEqual(event.payload_summary["nested"], [1, 2])
        runtime.close()
        runtime.emit(BrainEvent("WARNING", "TEST"))

    def test_narrator_and_state_projection_metrics(self):
        narrator = EventNarrator()
        event = BrainEvent("PAGE_ACTIVATED", "BRAIN", payload_summary={"page_id": 7, "topic": "SQLite"})
        self.assertIn("ativada", narrator.narrate(event))
        store = HudStateStore()
        for demo_event in build_demo_events(1.0):
            store.apply(demo_event)
        state = store.snapshot()
        self.assertEqual(state["mode"], "COMPLETE")
        self.assertEqual(state["brain"]["active_pages"], 3)
        self.assertEqual(state["context"]["tokens"], 1204)
        self.assertEqual(state["core"]["ttft_ms"], 1020.0)
        self.assertEqual(state["storage"]["physical_bytes"], 1024**2)
        self.assertEqual(state["work_avoided"]["inhibited_candidates"], 1)
        self.assertEqual(state["bottleneck"]["component"], "CORE")

    def test_demo_is_explicit_and_isolated(self):
        events = build_demo_events(1.0)
        self.assertTrue(events)
        self.assertTrue(all(event.demo_data for event in events))
        self.assertTrue(all(event.run_id.startswith("demo-") for event in events))
        self.assertIn("[DEMO DATA]", events[-1].payload_summary["answer"])

    def test_snapshot_privacy_and_atomic_roundtrip(self):
        store = HudStateStore()
        for event in build_demo_events(1.0):
            store.apply(event)
        with tempfile.TemporaryDirectory() as directory:
            target = write_snapshot(
                Path(directory) / "snapshot.json",
                store.snapshot(),
                hide_query=True,
                hide_records=True,
                hide_answer=True,
            )
            snapshot = read_snapshot(target)
            self.assertEqual(snapshot["query"], "[QUERY HIDDEN]")
            self.assertEqual(snapshot["answer"], "[ANSWER HIDDEN]")
            self.assertTrue(all(record["excerpt"] == "[RECORD TEXT HIDDEN]" for record in snapshot["knowledge"]["records"]))
            self.assertFalse(target.with_suffix(".json.tmp").exists())

    def test_phase4d_replay_uses_canonical_results(self):
        result = ROOT / "results/phase4d/end-to-end.json"
        events, phases, source = phase4d_replay_events(result, ROOT)
        self.assertEqual(events[0].event_type, "QUERY_RECEIVED")
        self.assertEqual(events[-1].event_type, "ANSWER_READY")
        self.assertFalse(any(event.demo_data for event in events))
        self.assertIn("PHASE 4D REPLAY", source)
        self.assertTrue(any(phase["phase"] == "4D" and phase["status"] == "COMPLETE" for phase in phases))
        canonical = json.loads(result.read_text(encoding="utf-8"))
        expected = next(run for run in canonical["runs"] if run["variant"] == "brain_ssd")
        self.assertEqual(events[-1].payload_summary["answer"], expected["answer"])
        self.assertEqual(events[-2].metrics["pressure"], "UNKNOWN")

    def test_server_starts_serves_state_static_and_stops(self):
        runtime = HudRuntime()
        runtime.emit(BrainEvent("QUERY_RECEIVED", "INPUT", payload_summary={"query": "secret"}))
        server = create_server(runtime, ROOT / "hud", "127.0.0.1", 0, hide_query=True)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        host, port = server.server_address
        try:
            with urlopen(f"http://{host}:{port}/api/health", timeout=3) as response:
                self.assertEqual(json.load(response)["status"], "ok")
            with urlopen(f"http://{host}:{port}/api/state", timeout=3) as response:
                self.assertEqual(json.load(response)["query"], "[QUERY HIDDEN]")
            with urlopen(f"http://{host}:{port}/", timeout=3) as response:
                self.assertIn(b"Cognitive Observatory", response.read())
        finally:
            server.shutdown()
            server.server_close()
            runtime.close()
            thread.join(timeout=3)
        self.assertFalse(thread.is_alive())

    def test_negative_duration_is_rejected(self):
        for duration in (-0.1, -1):
            with self.subTest(duration=duration):
                with self.assertRaises(ValueError):
                    BrainEvent("WARNING", "TEST", duration_ms=duration)


if __name__ == "__main__":
    unittest.main()
