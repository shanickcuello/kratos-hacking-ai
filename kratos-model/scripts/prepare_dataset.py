#!/usr/bin/env python3
"""Prepare training dataset from raw sources.

Reads raw writeups (HTML, markdown, text, PDF) from data/raw/ and converts
them into ChatML training conversations in data/processed/.

Optimized for 0xdf-style HTB writeups saved as HTML.

Usage:
    python scripts/prepare_dataset.py --input data/raw/ --output data/processed/train.jsonl
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import uuid
from html.parser import HTMLParser
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "data"))
from schema import SYSTEM_PROMPT_TEMPLATE, Role, TrainingConversation, Turn

# Shell prompt patterns found in 0xdf writeups
SHELL_PROMPT_RE = re.compile(
    r"(?:^|\n)"
    r"(?:oxdf@\w+|root@\w+|\w+@\w+|kali@kali)"
    r"[\$#]\s+(.+)",
)


# --- HTML text extraction --------------------------------------------------

class _HTMLTextExtractor(HTMLParser):
    """Extract readable text from HTML, skipping scripts/styles/nav."""

    _SKIP_TAGS = frozenset(("script", "style", "nav", "footer", "svg"))

    def __init__(self):
        super().__init__()
        self._parts: list[str] = []
        self._skip_depth = 0

    def handle_starttag(self, tag, attrs):
        if tag in self._SKIP_TAGS:
            self._skip_depth += 1
        elif tag in ("br", "p", "div", "h1", "h2", "h3", "h4", "li"):
            self._parts.append("\n")

    def handle_endtag(self, tag):
        if tag in self._SKIP_TAGS:
            self._skip_depth = max(0, self._skip_depth - 1)

    def handle_data(self, data):
        if self._skip_depth == 0:
            self._parts.append(data)

    def get_text(self) -> str:
        raw = "".join(self._parts)
        # Collapse excessive whitespace but keep newlines
        raw = re.sub(r"[ \t]+", " ", raw)
        raw = re.sub(r"\n{3,}", "\n\n", raw)
        return raw.strip()


def _html_to_text(html: str) -> str:
    ext = _HTMLTextExtractor()
    ext.feed(html)
    text = ext.get_text()
    return _clean_0xdf_noise(text)


def _clean_0xdf_noise(text: str) -> str:
    """Remove blog chrome noise from 0xdf-style HTML writeups."""
    # Remove the duplicated title header block at the top
    # Pattern: "HTB: Name |HTB: Name" or "HTB: Name | 0xdf hacks stuff"
    text = re.sub(r"^HTB:\s+\w[\w ]*\|[^\n]*\n", "", text)
    # Remove tag clouds (lines of space-separated lowercase words with hyphens)
    text = re.sub(
        r"\n(?:hackthebox|htb-|ctf|nmap|oscp)[\w\- ]{20,}\n",
        "\n", text,
    )
    # Remove date lines like "Apr 19, 2025" or "Oct 25, 2025"
    text = re.sub(
        r"\n(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{1,2},\s+\d{4}\s*\n",
        "\n", text,
    )
    # Remove "0xdf hacks stuff" and variations
    text = re.sub(r"0xdf hacks stuff", "", text)
    # Remove lonely "TOC" lines
    text = re.sub(r"\nTOC\n", "\n", text)
    # Remove "Box Info" header noise
    text = re.sub(r"\nBox Info\n", "\n", text)
    # Remove rating/time metadata ("00:06:01 NLTE", "User", "Root", etc.)
    text = re.sub(r"\d{2}:\d{2}:\d{2} NLTE", "", text)
    # Remove "Creator" lines
    text = re.sub(r"\nCreator\n[^\n]+\n", "\n", text)
    # Remove "Rated Difficulty" / "Radar Graph" lines
    text = re.sub(r"\n(?:Rated Difficulty|Radar Graph)\n", "\n", text)
    # Remove "Release Date" / "Retire Date" / "OS" metadata blocks
    text = re.sub(
        r"\n(?:Release Date|Retire Date|OS)\n[^\n]*\n",
        "\n", text,
    )
    # Collapse leftover whitespace
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


# --- Content extraction -----------------------------------------------------

def _extract_blocks(text: str) -> list[dict]:
    """Split writeup text into (analysis, command, output) blocks.

    Detects shell prompts (oxdf@hacky$, root@box#, kali@kali$) and
    treats the lines after a prompt until the next prompt/section as
    the command output.
    """
    blocks: list[dict] = []
    # Split on section-level headers
    sections = re.split(r"\n(?=[A-Z][A-Za-z /]+\n)", text)

    for section in sections:
        section = section.strip()
        if not section or len(section) < 30:
            continue

        # Find all shell commands in this section
        commands_with_output: list[dict] = []
        last_end = 0
        analysis_parts: list[str] = []

        for m in SHELL_PROMPT_RE.finditer(section):
            # Text before this command is analysis
            before = section[last_end:m.start()].strip()
            if before:
                analysis_parts.append(before)

            cmd = m.group(1).strip()
            # Find output: text from end of command to next prompt or section
            cmd_end = m.end()
            next_match = SHELL_PROMPT_RE.search(section, cmd_end)
            if next_match:
                output = section[cmd_end:next_match.start()].strip()
            else:
                output = section[cmd_end:].strip()
                # Limit output to ~2000 chars
                if len(output) > 2000:
                    output = output[:2000] + "\n[...truncated...]"

            commands_with_output.append({
                "command": cmd,
                "output": output,
            })
            last_end = next_match.start() if next_match else len(section)

        # Remaining text after last command
        remaining = section[last_end:].strip()
        if remaining and not SHELL_PROMPT_RE.match(remaining):
            analysis_parts.append(remaining)

        analysis = "\n".join(analysis_parts).strip()
        # Clean residual noise
        analysis = re.sub(r"HTB:\s+\w[\w ]*\n", "", analysis)
        analysis = re.sub(r"\b(?:Easy|Medium|Hard|Insane)\s*$", "", analysis, flags=re.M)
        # Remove lines that are just whitespace or single short words
        lines = [l for l in analysis.split("\n") if len(l.strip()) > 3]
        analysis = "\n".join(lines).strip()

        if analysis or commands_with_output:
            blocks.append({
                "analysis": analysis,
                "commands": commands_with_output,
            })

    return blocks


def _to_tool_call(command: str) -> str:
    return (
        "<tool_call>\n"
        + json.dumps({"name": "run_command", "arguments": {"command": command}})
        + "\n</tool_call>"
    )


def _blocks_to_conversation(
    blocks: list[dict],
    source_file: str,
) -> TrainingConversation | None:
    """Convert extracted blocks into a multi-turn training conversation."""
    # Filter out blocks with no useful content
    useful = [b for b in blocks if b["commands"] or len(b["analysis"]) > 50]
    if len(useful) < 2:
        return None

    tool_list = (
        "nmap_scan, gobuster_dir, ffuf_fuzz, sqlmap_inject, "
        "nikto_scan, searchsploit, metasploit_run, hydra_brute, "
        "linpeas_run, sudo_check, suid_find, hash_crack, "
        "run_command, read_file, write_file, curl_request"
    )
    system_prompt = SYSTEM_PROMPT_TEMPLATE.format(tool_list=tool_list)
    turns = [Turn(role=Role.SYSTEM, content=system_prompt)]
    turns.append(Turn(
        role=Role.USER,
        content="Analyze and exploit the target. Walk me through your approach.",
    ))

    for block in useful:
        # Assistant turn: reasoning + tool calls
        assistant_parts = []
        if block["analysis"]:
            # Keep analysis concise for training
            analysis = block["analysis"][:1500]
            assistant_parts.append(analysis)

        for cmd_info in block["commands"]:
            assistant_parts.append(_to_tool_call(cmd_info["command"]))

        if assistant_parts:
            turns.append(Turn(
                role=Role.ASSISTANT,
                content="\n\n".join(assistant_parts),
            ))

        # Tool result turns with REAL output from the writeup
        for cmd_info in block["commands"]:
            output = cmd_info["output"] or f"[Command executed: {cmd_info['command']}]"
            turns.append(Turn(
                role=Role.TOOL,
                content=f"<tool_result>\n{output}\n</tool_result>",
            ))

    if len(turns) < 4:
        return None

    return TrainingConversation(
        id=str(uuid.uuid4())[:8],
        turns=turns,
        metadata={
            "source": source_file,
            "source_type": "writeup",
            "num_turns": len(turns),
            "num_commands": sum(
                len(b["commands"]) for b in useful
            ),
        },
    )


# --- File reading -----------------------------------------------------------

def _read_file_content(path: Path) -> str:
    """Read and extract text from various file formats."""
    suffix = path.suffix.lower()

    if suffix == ".html":
        html = path.read_text(errors="replace")
        return _html_to_text(html)

    if suffix == ".pdf":
        try:
            import fitz
            doc = fitz.open(str(path))
            text = "\n".join(page.get_text() for page in doc)
            doc.close()
            return text
        except ImportError:
            print(f"  [WARN] PyMuPDF not installed, skipping: {path.name}")
            return ""

    return path.read_text(errors="replace")


# --- Main -------------------------------------------------------------------

def prepare_dataset(input_dir: Path, output_path: Path) -> int:
    """Process all raw files and write training JSONL."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    skipped = 0

    with open(output_path, "w") as out:
        for path in sorted(input_dir.rglob("*")):
            if path.is_dir():
                continue
            if path.suffix.lower() not in (".md", ".txt", ".pdf", ".html"):
                continue

            text = _read_file_content(path)
            if not text or len(text) < 500:
                skipped += 1
                continue

            blocks = _extract_blocks(text)
            conv = _blocks_to_conversation(blocks, path.name)
            if conv:
                out.write(json.dumps(conv.to_dict()) + "\n")
                count += 1
                cmds = conv.metadata["num_commands"]
                print(f"  ✓ {path.name}: {conv.metadata['num_turns']} turns, {cmds} commands")
            else:
                skipped += 1
                print(f"  ✗ {path.name}: not enough content, skipped")

    print(f"\nDone: {count} conversations written, {skipped} skipped")
    print(f"Output: {output_path}")
    return count


def main():
    parser = argparse.ArgumentParser(description="Prepare training dataset")
    parser.add_argument(
        "--input", "-i", default="data/raw",
        help="Input directory with raw writeups",
    )
    parser.add_argument(
        "--output", "-o", default="data/processed/train.jsonl",
        help="Output JSONL file",
    )
    args = parser.parse_args()

    base = Path(__file__).resolve().parent.parent
    input_dir = base / args.input
    output_path = base / args.output

    if not input_dir.exists():
        print(f"Input directory not found: {input_dir}")
        sys.exit(1)

    prepare_dataset(input_dir, output_path)


if __name__ == "__main__":
    main()
