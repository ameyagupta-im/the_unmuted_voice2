# Campaign dryrun test

Schedule: {"allowed_start_time": "09:00", "allowed_end_time": "21:00", "allowed_days": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"], "timezone": "Asia/Kolkata"}

| Agent | Contacts |
|---|---|
| vani_female_neutral | 1 |
| vani_female_calm | 1 |
| vani_male_crisp | 1 |

Left out:
- 113839910: no phone number in the phones file
- 1: not in the seller data

Agent ids missing in outputs/sarvam/agent_ids.json for: vani_female_neutral, vani_female_calm, vani_male_crisp (create the agents first: src/sarvam_deploy.py).