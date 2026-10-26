"""F5-B local HTTP fixture: real loopback transport, NO Ollama/Qwen/model."""
from __future__ import annotations

import http.server
import json
import threading
import time

from .autonomy import AutonomyBrain
from .episodic_memory import ExperienceMemory
from .ollama_local_client import (
    OllamaEndpoint, OllamaLocalClient, advisory_from_transport,
)
from .passive_memory import PassiveObservationJournal
from .passive_sources import PassiveRead
from .pc_hypothesis_contract import start_optional_pc_cycle
from .perception import PerceptionEvent, PerceptionSnapshot


class _MockOllama(http.server.BaseHTTPRequestHandler):
    def log_message(self, *_args: object) -> None:
        pass

    def do_POST(self) -> None:
        if self.path != "/api/chat":
            self.send_error(404)
            return
        size = int(self.headers.get("Content-Length", "0"))
        if not 0 < size <= 8192:
            self.send_error(413)
            return
        body = json.loads(self.rfile.read(size))
        request_id = json.loads(body["messages"][1]["content"])["request_id"]
        pc_response = {
            "schema_version": 1, "request_id": request_id,
            "source": "pc_qwen_unverified",
            "hypotheses": [{
                "kind": "object_label", "category": "unknown",
                "confidence": 0, "ttl_s": 1,
            }],
        }
        envelope = {
            "model": body["model"], "done": True,
            "message": {"role": "assistant",
                        "content": json.dumps(pc_response)},
        }
        payload = json.dumps(envelope).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)


def run_demo() -> dict:
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), _MockOllama)
    server.daemon_threads = True
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    memory = ExperienceMemory()
    try:
        journal = PassiveObservationJournal(memory)
        event = PerceptionEvent(
            "object_label", "unknown", "mock", 100., 1., .97,
            track_id="track-fixture-unknown",
        )
        read = PassiveRead("ok", PerceptionSnapshot(
            "mock", (event,), 100.), 1, "mock_fixture_unix")
        cycle = start_optional_pc_cycle(
            AutonomyBrain(memory), read, journal=journal,
            now_monotonic_s=100., now_wall_epoch_s=1_780_000_000.,
        )
        client = OllamaLocalClient(
            OllamaEndpoint(f"http://127.0.0.1:{server.server_port}"))
        measured = client.query(cycle.request, timeout_s=1.)
        # Demonstration clocks are MOCK. They are not the host monotonic time.
        result = advisory_from_transport(cycle, measured,
                                         now_monotonic_s=100.1)
        if (measured.status != "ok"
                or result.status != "hypotheses_unverified"
                or result.local_intent != cycle.local_intent
                or result.hypotheses[0].verified
                or memory.experience_count() != 0):
            raise RuntimeError("fixture transport failed closed")
        return {
            "scenario": "synthetic_loopback_http_server",
            "http_response": measured.status,
            "local_intention": result.local_intent.intention,
            "pc_status": result.status,
            "pc_hypothesis_verified": result.hypotheses[0].verified,
            "actual_ollama_queries": 0,
            "actual_qwen_inferences": 0,
            "loopback_fixture_http_calls": 1,
            "motor_commands_issued": result.motor_commands_issued,
            "speaker_commands_issued": result.speaker_commands_issued,
            "robot_hardware_validated": False,
        }
    finally:
        memory.close()
        server.shutdown()
        server.server_close()
        worker.join(timeout=2)


def main() -> int:
    print(json.dumps(run_demo(), sort_keys=True, allow_nan=False))
    return 0


if __name__=="__main__":
    raise SystemExit(main())
