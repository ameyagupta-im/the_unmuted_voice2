import base64
import os
import sys

from sarvamai import SarvamAI


def load_env_file(path=".env"):
    if not os.path.exists(path):
        return
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            os.environ.setdefault(key.strip(), value.strip())


load_env_file()

api_key = os.environ.get("SARVAM_API_KEY")
if not api_key:
    sys.exit("SARVAM_API_KEY is not set. Paste your key into .env and run again.")

client = SarvamAI(api_subscription_key=api_key)

response = client.text_to_speech.convert(
    text="Namaste, welcome to Sarvam",
    language_code="hi-IN",
)

audio_bytes = base64.b64decode(response.audios[0])
output_path = "output.wav"
with open(output_path, "wb") as f:
    f.write(audio_bytes)

print(f"Saved audio to {output_path}")
