import os
from pathlib import Path

from sarvamai import SarvamAI

ROOT = Path(__file__).resolve().parent.parent
OUTPUTS = ROOT / "outputs"

LLM_MODEL = "sarvam-105b-conversations"
STT_MODEL = "saaras:v4"  # v4 needed for `keyterms` (fixes "IndiaMART" heard as "India Art" on v3)
# translit returns Roman text the regex layer reads directly; codemix only replaces it if
# src/compare_stt_modes.py shows it wins (override per run with VANI_STT_MODE)
STT_MODE = os.environ.get("VANI_STT_MODE", "translit")
TTS_MODEL = "bulbul:v4-flash"


def load_env(path: Path = ROOT / ".env") -> None:
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, _, v = line.partition("=")
            os.environ.setdefault(k.strip(), v.strip())


_client = None


def client() -> SarvamAI:
    global _client
    if _client is None:
        load_env()
        key = os.environ.get("SARVAM_API_KEY")
        if not key:
            raise RuntimeError("SARVAM_API_KEY is not set. Put it in .env")
        _client = SarvamAI(api_subscription_key=key, timeout=60)
    return _client
