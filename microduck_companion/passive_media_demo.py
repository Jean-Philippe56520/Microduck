"""F3-C: offline demo using OEM-shaped metadata, NOT real mediad output.

Synthetic-only: media.video and media.detections are modeled after pinned
WebRTC notifications, not a local socket subscription. Local OEM socket
supports only hello and raw media.frame; neither is called here. Sound cue
labels are entirely fictional and never trigger actuator or emergency stop.
"""
from __future__ import annotations

from dataclasses import asdict
import json

from .passive_media_router import (
    MockAudioCueRouter, OEM_REVISION_REVIEWED,
    parse_oem_shape_notification,
)


def _bytes(data: dict) -> bytes:
    return json.dumps(data, sort_keys=True, allow_nan=False).encode("utf-8")


def run_demo() -> dict:
    messages = (
        {"jsonrpc":"2.0","method":"media.video","params":{
            "width":720, "height":1280, "rotate":90,
            "mono_ns":1_001_000_000, "real_ns":1_801_000_000,
        }},
        {"jsonrpc":"2.0","method":"media.detections","params":{
            "width":720, "height":1280, "took_ms":63.5,
            "boxes":[{"x0":10.,"y0":20.,"x1":110.,"y1":220.,
                      "score":1.38}],
        }},
        {"jsonrpc":"2.0","method":"media.detections","params":{
            "width":720, "height":1280, "took_ms":62.3, "boxes":[],
        }},
    )
    media = tuple(parse_oem_shape_notification(_bytes(m)) for m in messages)
    audio = MockAudioCueRouter()
    cues = []
    for i, cue in enumerate((
        "petting_start", "keyword_microduck", "keyword_stop",
        "keyword_viens", "petting_end",
    ), start=1):
        sample = float(100+i)
        cues.append(audio.route(_bytes({
            "schema_version":1, "sequence":i,
            "sample_monotonic_s":sample, "cue":cue,
        }), now_monotonic_s=sample+.1))
    if any(x.category!="unknown" or x.motor_commands_issued
           or x.verified_sensor or x.media_bytes_stored for x in media):
        raise RuntimeError("OEM-shaped fixture cannot authenticate a sensor")
    if any(x.category!="unknown" or x.motor_commands_issued
           or x.stops_robot or x.verified_microphone or x.audio_bytes_stored
           for x in cues):
        raise RuntimeError("mock audio cannot grant speech or motor authority")
    return {
        "environment":"mock_only_no_live_transport",
        "oem_revision_read_in_source":OEM_REVISION_REVIEWED,
        "oem_notification_shapes_parsed":len(media),
        "media_reports":[asdict(r) for r in media],
        "mock_audio_reports":[asdict(r) for r in cues],
        "oem_media_frame_requests":0,
        "oem_web_rtc_subscriptions":0,
        "microphone_samples_acquired":0,
        "image_bytes_acquired":0,
        "camera_or_microphone_validated":False,
        "motor_commands_issued":0,
        "emergency_stops_issued":0,
    }


def main() -> int:
    print(json.dumps(run_demo(),sort_keys=True,allow_nan=False))
    return 0


if __name__=="__main__":
    raise SystemExit(main())
