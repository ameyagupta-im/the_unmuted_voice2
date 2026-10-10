"""Live voice demo: a person plays the seller into the browser microphone and
VANI adapts in real time (brief FAQ Q3: the mid-call switch must respond to what
the seller actually says).

  python src/web_app.py      ->  http://127.0.0.1:5050

Each call is saved as it happens to outputs/live_sessions/<call_id>/
(switch_log.json, transcript.json, persona_spec.json, per-turn audio), so the
switch log of the judged live call is a real artifact, not a reconstruction.
"""
import base64
import json
import sys
import time
import uuid
from pathlib import Path

from flask import Flask, jsonify, request, send_from_directory

sys.path.insert(0, str(Path(__file__).resolve().parent))
from config import OUTPUTS  # noqa: E402
from data_pipeline import load_seller_master  # noqa: E402
from integrations import on_call_end, pre_call  # noqa: E402
from live_engine import LiveCall  # noqa: E402
from persona_generator import generate_persona  # noqa: E402

STATIC = Path(__file__).resolve().parent / "static"
SESSIONS = OUTPUTS / "live_sessions"
DEMO_SELLERS = [
    (3419775, "Chennai idli-machine maker · English-preferring professional · goal meeting"),
    (1243794, "Delhi clamps trader · fatigued, past complaint · goal complaint recovery"),
    (56768582, "Hyderabad rice-bran firm · busy owner (Rohan) · goal meeting · Telugu offered"),
    (113839910, "Cotton fabric trader · warm, interested · goal meeting (playbook test seller)"),
    (19070168, "Socks trader · small local trader · goal nurture"),
    (269277443, "Chennai chemicals firm · called 9x · goal respectful exit"),
]

app = Flask(__name__, static_folder=str(STATIC))
_sellers = None
_calls = {}


def sellers():
    global _sellers
    if _sellers is None:
        _sellers = load_seller_master()
    return _sellers


def _float(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _b64(audio):
    return base64.b64encode(audio).decode("ascii") if audio else None


def _save(call_id: str, call: LiveCall, extra: dict = None):
    d = SESSIONS / call_id
    d.mkdir(parents=True, exist_ok=True)
    summ = call.summary()
    if extra:
        summ.update(extra)
    (d / "switch_log.json").write_text(json.dumps(summ["switch_log"], ensure_ascii=False, indent=2), encoding="utf-8")
    (d / "transcript.json").write_text(json.dumps(summ, ensure_ascii=False, indent=2, default=str), encoding="utf-8")


def _turn_payload(r):
    return {"turn": r.turn, "seller_text": r.seller_text, "stt_language": r.stt_language,
            "signals_tier1": r.signals_tier1, "signals_tier2": r.signals_tier2, "switches": r.switches,
            "reply": r.reply, "audio": _b64(r.audio), "delivery": r.delivery, "outcome": r.call_outcome,
            "end_call": r.end_call, "latency_ms": r.latency_ms, "hangup_risk": r.hangup_risk,
            "ignored": getattr(r, "ignored", False)}


@app.get("/")
def index():
    return send_from_directory(STATIC, "index.html")


@app.get("/api/sellers")
def list_sellers():
    return jsonify([{"seller_id": s, "label": l} for s, l in DEMO_SELLERS])


@app.post("/api/call/start")
def start_call():
    seller_id = int(request.json["seller_id"])
    rows = sellers().loc[sellers().fk_glusr_usr_id == seller_id]
    if rows.empty:
        return jsonify({"error": f"seller {seller_id} not found"}), 404
    spec = generate_persona(rows.iloc[0].to_dict())
    persona = spec.to_dict()
    if spec.blocked:
        return jsonify({"blocked": True, "reason": spec.block_reason, "persona": persona})
    clearance = pre_call(seller_id)
    if not clearance.allowed:
        return jsonify({"blocked": True, "reason": "; ".join(clearance.reasons), "persona": persona})
    call = LiveCall(persona)
    call_id = f"{seller_id}_{time.strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:4]}"
    _calls[call_id] = call
    d = SESSIONS / call_id
    d.mkdir(parents=True, exist_ok=True)
    (d / "persona_spec.json").write_text(json.dumps(persona, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    r = call.start()
    if r.audio:
        (d / "turn00_vani.wav").write_bytes(r.audio)
    _save(call_id, call)
    return jsonify({"call_id": call_id, "persona": persona, "warnings": clearance.warnings, **_turn_payload(r)})


@app.post("/api/call/<call_id>/turn")
def seller_turn(call_id):
    call = _calls.get(call_id)
    if call is None:
        return jsonify({"error": "unknown call"}), 404
    if call.ended:
        return jsonify({"error": "call already ended"}), 400
    d = SESSIONS / call_id
    if "audio" in request.files:
        f = request.files["audio"]
        audio = f.read()
        name = f.filename or "turn.webm"
        (d / f"turn{call.turn + 1:02d}_seller.{name.rsplit('.', 1)[-1]}").write_bytes(audio)
        r = call.seller_turn(audio=audio, audio_filename=name, interrupted=request.form.get("interrupted") == "1",
                             heard_fraction=_float(request.form.get("heard_fraction")))
    else:
        r = call.seller_turn(text=(request.form.get("text") or (request.get_json(silent=True) or {}).get("text") or ""))
    if r.audio:
        (d / f"turn{r.turn:02d}_vani.wav").write_bytes(r.audio)
    extra = {"integrations": on_call_end(call, call_id)} if r.end_call else None
    _save(call_id, call, extra)
    return jsonify({**_turn_payload(r), **(extra or {})})


@app.get("/api/call/<call_id>/log")
def call_log(call_id):
    call = _calls.get(call_id)
    if call is None:
        return jsonify({"error": "unknown call"}), 404
    return jsonify(call.summary())


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sellers()
    print("VANI live demo on http://127.0.0.1:5050")
    app.run(host="127.0.0.1", port=5050, debug=False, threaded=True)
