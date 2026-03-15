#!/usr/bin/env python3
"""Generate synthetic training data using a local LLM via Ollama.

Creates multi-turn pentesting conversations from scenario templates.
Each scenario defines a target setup and the generator produces
realistic tool calls, outputs, and analysis.

Usage:
    python scripts/generate_synthetic.py --count 100 --output data/processed/synthetic.jsonl
    python scripts/generate_synthetic.py --count 50 --model qwen2.5-coder:7b
"""

from __future__ import annotations

import argparse
import json
import random
import sys
import uuid
from pathlib import Path

import ollama

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "data"))
from schema import SYSTEM_PROMPT_TEMPLATE, Role, TrainingConversation, Turn

# ---------------------------------------------------------------------------
# Scenario templates — each defines a CTF-style situation
# ---------------------------------------------------------------------------

SCENARIOS = [
    {
        "name": "linux_easy_web",
        "description": "Easy Linux box with web app SQL injection and SUID privesc",
        "target_ip": "10.10.10.{rand}",
        "services": "22/tcp SSH, 80/tcp Apache",
        "attack_path": "nmap → gobuster → SQLi on login → creds → SSH → SUID binary → root",
        "difficulty": "easy",
        "category": ["web", "sqli", "privesc"],
    },
    {
        "name": "linux_medium_cms",
        "description": "Medium Linux box with CMS RCE and kernel exploit",
        "target_ip": "10.10.10.{rand}",
        "services": "22/tcp SSH, 80/tcp nginx, 3306/tcp MySQL",
        "attack_path": "nmap → nikto → CMS version → searchsploit → RCE → shell → linpeas → kernel exploit → root",
        "difficulty": "medium",
        "category": ["web", "rce", "kernel"],
    },
    {
        "name": "linux_hard_api",
        "description": "Hard Linux box with API fuzzing, JWT bypass, and docker escape",
        "target_ip": "10.10.10.{rand}",
        "services": "22/tcp SSH, 443/tcp HTTPS API, 8080/tcp dev server",
        "attack_path": "nmap → ffuf API endpoints → JWT token forge → admin access → command injection → docker group → escape → root",
        "difficulty": "hard",
        "category": ["api", "jwt", "docker"],
    },
    {
        "name": "linux_ftp_anon",
        "description": "Easy box with anonymous FTP containing credentials",
        "target_ip": "10.10.10.{rand}",
        "services": "21/tcp FTP (anon), 22/tcp SSH, 80/tcp Apache",
        "attack_path": "nmap → FTP anon login → download creds → SSH login → sudo -l → GTFOBins → root",
        "difficulty": "easy",
        "category": ["ftp", "privesc"],
    },
    {
        "name": "linux_smb_relay",
        "description": "Medium box with SMB shares containing sensitive data",
        "target_ip": "10.10.10.{rand}",
        "services": "22/tcp SSH, 139/tcp SMB, 445/tcp SMB, 80/tcp Apache",
        "attack_path": "nmap → enum4linux → smbclient → password file → SSH → cronjob writable script → root",
        "difficulty": "medium",
        "category": ["smb", "privesc", "cron"],
    },
    {
        "name": "web_lfi_to_rce",
        "description": "Web app with LFI leading to log poisoning RCE",
        "target_ip": "10.10.10.{rand}",
        "services": "80/tcp Apache with PHP app",
        "attack_path": "nmap → gobuster → find LFI param → read /etc/passwd → log poisoning via User-Agent → RCE → reverse shell → linpeas → SUID → root",
        "difficulty": "medium",
        "category": ["web", "lfi", "rce"],
    },
    {
        "name": "web_xxe_ssrf",
        "description": "XML parser vulnerable to XXE with internal SSRF",
        "target_ip": "10.10.10.{rand}",
        "services": "443/tcp HTTPS, 8080/tcp internal API",
        "attack_path": "nmap → discover XML upload → XXE to read files → SSRF to internal API → admin creds → SSH → privesc",
        "difficulty": "hard",
        "category": ["web", "xxe", "ssrf"],
    },
    {
        "name": "crypto_weak_hash",
        "description": "Web app with weak password hashing",
        "target_ip": "10.10.10.{rand}",
        "services": "22/tcp SSH, 80/tcp Node.js app, 27017/tcp MongoDB",
        "attack_path": "nmap → discover NoSQL injection → dump user hashes → crack MD5 → login → file upload RCE → shell → sudo misc → root",
        "difficulty": "medium",
        "category": ["nosql", "crypto", "web"],
    },
    {
        "name": "network_pivoting",
        "description": "Dual-homed host requiring network pivoting",
        "target_ip": "10.10.10.{rand}",
        "services": "22/tcp SSH, 80/tcp Apache on host1; 3306/tcp MySQL on host2 (internal)",
        "attack_path": "nmap → web exploit → shell on host1 → discover internal network → chisel/ssh tunnel → MySQL on host2 → creds → root",
        "difficulty": "hard",
        "category": ["pivoting", "network", "tunnel"],
    },
    {
        "name": "linux_wordpress",
        "description": "WordPress site with vulnerable plugin",
        "target_ip": "10.10.10.{rand}",
        "services": "22/tcp SSH, 80/tcp Apache WordPress",
        "attack_path": "nmap → wpscan → vulnerable plugin → exploit → shell → wp-config.php DB creds → password reuse → su root",
        "difficulty": "easy",
        "category": ["web", "wordpress", "privesc"],
    },
]

GENERATION_PROMPT = """You are a cybersecurity training data generator.

Generate a REALISTIC multi-turn penetration testing conversation for this scenario:

**Scenario**: {description}
**Target**: {target_ip}
**Services**: {services}
**Expected attack path**: {attack_path}
**Difficulty**: {difficulty}

Generate the conversation as a JSON array of messages. Each message has "role" and "content".
The assistant should:
1. Explain reasoning BEFORE each action
2. Use <tool_call>{{"name": "tool_name", "arguments": {{}}}}</tool_call> tags for tool usage
3. Analyze tool output realistically after each <tool_result>
4. Progress through the full attack path
5. Find the flag at the end

Use realistic tool outputs (nmap banners, gobuster results, exploit output, etc.).
Include BOTH user.txt and root.txt flags.

Respond ONLY with the JSON array. No markdown fences, no extra text.

Tools available: nmap_scan, gobuster_dir, ffuf_fuzz, sqlmap_inject, nikto_scan,
searchsploit, metasploit_run, hydra_brute, linpeas_run, sudo_check, suid_find,
hash_crack, run_command, read_file, write_file, curl_request
"""


def _generate_one(
    client: ollama.Client,
    model: str,
    scenario: dict,
) -> TrainingConversation | None:
    """Generate a single training conversation from a scenario."""
    target_ip = scenario["target_ip"].format(rand=random.randint(1, 254))

    prompt = GENERATION_PROMPT.format(
        description=scenario["description"],
        target_ip=target_ip,
        services=scenario["services"],
        attack_path=scenario["attack_path"],
        difficulty=scenario["difficulty"],
    )

    try:
        response = client.chat(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            options={"temperature": 0.8, "num_predict": 4096},
        )
    except Exception as e:
        print(f"  [ERROR] Ollama call failed: {e}")
        return None

    content = response.get("message", {}).get("content", "")

    # Try to parse JSON from response
    try:
        # Strip markdown fences if present
        cleaned = content.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.split("\n", 1)[1]
            cleaned = cleaned.rsplit("```", 1)[0]

        messages = json.loads(cleaned)
        if not isinstance(messages, list) or len(messages) < 4:
            print("  [WARN] Too few messages, skipping")
            return None
    except json.JSONDecodeError:
        print("  [WARN] Failed to parse JSON, skipping")
        return None

    # Build the system prompt
    tool_list = (
        "nmap_scan, gobuster_dir, ffuf_fuzz, sqlmap_inject, "
        "nikto_scan, searchsploit, metasploit_run, hydra_brute, "
        "linpeas_run, sudo_check, suid_find, hash_crack, "
        "run_command, read_file, write_file, curl_request"
    )
    system_prompt = SYSTEM_PROMPT_TEMPLATE.format(tool_list=tool_list)

    turns = [Turn(role=Role.SYSTEM, content=system_prompt)]
    for msg in messages:
        role_str = msg.get("role", "user")
        if role_str not in ("user", "assistant", "tool"):
            continue
        turns.append(Turn(
            role=Role(role_str),
            content=msg.get("content", ""),
        ))

    return TrainingConversation(
        id=str(uuid.uuid4())[:8],
        turns=turns,
        metadata={
            "source": f"synthetic_{scenario['name']}",
            "source_type": "synthetic",
            "scenario": scenario["name"],
            "difficulty": scenario["difficulty"],
            "category": scenario["category"],
            "num_turns": len(turns),
        },
    )


def generate_dataset(
    count: int,
    output_path: Path,
    model: str,
    host: str,
) -> int:
    """Generate synthetic training conversations."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    client = ollama.Client(host=host)

    generated = 0
    with open(output_path, "w") as out:
        for i in range(count):
            scenario = random.choice(SCENARIOS)
            print(f"[{i + 1}/{count}] Generating: {scenario['name']}...")

            conv = _generate_one(client, model, scenario)
            if conv:
                out.write(json.dumps(conv.to_dict()) + "\n")
                generated += 1
                print(f"  ✓ {conv.metadata['num_turns']} turns")
            else:
                print("  ✗ Failed, skipping")

    print(f"\nGenerated {generated}/{count} conversations → {output_path}")
    return generated


def main():
    parser = argparse.ArgumentParser(
        description="Generate synthetic pentesting training data",
    )
    parser.add_argument(
        "--count", "-n", type=int, default=100,
        help="Number of conversations to generate",
    )
    parser.add_argument(
        "--output", "-o", default="data/processed/synthetic.jsonl",
        help="Output JSONL file",
    )
    parser.add_argument(
        "--model", default="qwen2.5-coder:7b",
        help="Ollama model to use for generation",
    )
    parser.add_argument(
        "--host", default="http://localhost:11434",
        help="Ollama host URL",
    )
    args = parser.parse_args()

    base = Path(__file__).resolve().parent.parent
    output_path = base / args.output

    generate_dataset(args.count, output_path, args.model, args.host)


if __name__ == "__main__":
    main()
