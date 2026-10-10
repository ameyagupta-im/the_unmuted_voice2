"""Writes the Sarvam Voice Agents configuration for VANI: one agent per (voice gender, voice style).

  python src/sarvam_deploy.py            -> outputs/sarvam/agents/<agent_key>.json + .md (dashboard setup guide)
  python src/sarvam_deploy.py --apply    -> explains how to push (see below); never pushes anything itself

Sarvam has no public REST endpoint for creating or editing an agent (docs/sarvam_platform_notes.md): agents are
configured in the dashboard or through Sarvam's MCP server (configure_agent), which needs a browser sign-in.
Deployments, campaigns, cohorts and instant calls DO have REST endpoints (src/sarvam_api.py) and reference an
agent by its app_id + app_version, recorded in outputs/sarvam/agent_ids.json once the agents exist.
"""
import argparse
import json
import sys

from config import OUTPUTS
from sarvam_platform import agent_bundle, missing_placeholders, voice_agents

OUT = OUTPUTS / "sarvam" / "agents"
IDS = OUTPUTS / "sarvam" / "agent_ids.json"


def guide(b) -> str:
    inputs = "\n".join(f"| `{v['name']}` | {v['description']} | {v['default'] or '—'} |" for v in b["variables"]["input"])
    outputs = "\n".join(f"| `{v['name']}` | {v['type']} | {', '.join(v['values']) if v['values'] else '—'} | {v['extraction_prompt']} |"
                        for v in b["variables"]["output"])
    voices = "\n".join(f"| {lang} | `{vid}` |" for lang, vid in b["voice"]["per_language_voices"].items())
    return f"""# {b['name']}  (`{b['agent_key']}`)

Set up in the Sarvam dashboard (Build), or ask the MCP server's `configure_agent` to apply `{b['agent_key']}.json`.
After saving, commit a version and record its app_id and version in `outputs/sarvam/agent_ids.json`.

## Greeting (every call overrides it with the seller's own opening: `initial_bot_message`)
{b['greeting']}

## Instruction
Paste the `instruction` field of `{b['agent_key']}.json`. Placeholders are written `{{{{name}}}}`: insert each as the
matching agent variable with `@` if the editor does not convert them.

## Input variables (one CSV column / agent_variables key each; "send to LLM" on)
| Name | Description | Default |
|---|---|---|
{inputs}

## Output variables (extracted after the call)
| Name | Type | Values | Extraction prompt |
|---|---|---|---|
{outputs}

Successful when: `{b['variables']['successful_when']}`

## Voice (Speakers & voice, per-language voices on; model {b['voice']['model']})
| Starting language | Voice |
|---|---|
{voices}

{b['voice']['note']}.

## Conversation settings
{json.dumps(b['conversation_settings'], indent=2)}

## Pronunciation dictionary (Advanced)
```json
{json.dumps({"pronunciations": b['pronunciations']}, ensure_ascii=False, indent=2)}
```

## Core tools
{', '.join(b['core_tools'])}
"""


def main(apply: bool):
    OUT.mkdir(parents=True, exist_ok=True)
    for key, spec in voice_agents().items():
        b = agent_bundle(key, spec)
        bad = missing_placeholders(b["instruction"] + b["greeting"])
        if bad:
            raise SystemExit(f"{key}: placeholders without an input variable: {bad}")
        (OUT / f"{key}.json").write_text(json.dumps(b, ensure_ascii=False, indent=2), encoding="utf-8")
        (OUT / f"{key}.md").write_text(guide(b), encoding="utf-8")
        print(f"{key}: instruction {len(b['instruction']):,} chars, voices {b['voice']['per_language_voices']}")
    if not IDS.exists():
        IDS.write_text(json.dumps({k: {"app_id": "", "app_version": None} for k in voice_agents()}, indent=2), encoding="utf-8")
    if apply:
        print("\nNo REST endpoint creates agents. To push: connect the Sarvam MCP server once in an interactive "
              "Claude Code session (claude mcp add --transport http sarvam-voice-agents https://mcp.sarvam.ai/voice-agents, "
              "then /mcp -> Authenticate), and ask it to configure each agent from outputs/sarvam/agents/<key>.json. "
              "Or paste each <key>.md into the dashboard.")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    main(ap.parse_args().apply)
