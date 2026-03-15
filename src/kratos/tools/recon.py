"""Reconnaissance tools for network and service discovery."""

from __future__ import annotations

from kratos.domain.entities import ToolDefinition

nmap_scan = ToolDefinition(
    name="nmap_scan",
    description=(
        "Run an nmap scan against a target. Supports service detection, "
        "OS fingerprinting, script scanning, and custom flags. "
        "Use this as the FIRST step for any new target."
    ),
    parameters={
        "type": "object",
        "properties": {
            "target": {
                "type": "string",
                "description": "Target IP or hostname (e.g., '10.10.10.1')",
            },
            "flags": {
                "type": "string",
                "description": (
                    "Nmap flags (e.g., '-sV -sC -p-' for full scan, "
                    "'-sU --top-ports 50' for UDP). Default: '-sV -sC'"
                ),
            },
        },
        "required": ["target"],
    },
)

gobuster_dir = ToolDefinition(
    name="gobuster_dir",
    description=(
        "Run gobuster directory/file brute-force against a web server. "
        "Use after discovering an HTTP/HTTPS service."
    ),
    parameters={
        "type": "object",
        "properties": {
            "url": {
                "type": "string",
                "description": "Target URL (e.g., 'http://10.10.10.1:80')",
            },
            "wordlist": {
                "type": "string",
                "description": (
                    "Wordlist path. Default: "
                    "/usr/share/wordlists/dirb/common.txt"
                ),
            },
            "extensions": {
                "type": "string",
                "description": "File extensions to search (e.g., 'php,html,txt')",
            },
        },
        "required": ["url"],
    },
)

ffuf_fuzz = ToolDefinition(
    name="ffuf_fuzz",
    description=(
        "Run ffuf for web fuzzing (directories, parameters, vhosts). "
        "Faster alternative to gobuster with more flexibility."
    ),
    parameters={
        "type": "object",
        "properties": {
            "url": {
                "type": "string",
                "description": "URL with FUZZ keyword (e.g., 'http://10.10.10.1/FUZZ')",
            },
            "wordlist": {
                "type": "string",
                "description": "Wordlist path. Default: /usr/share/seclists/Discovery/Web-Content/common.txt",
            },
            "flags": {
                "type": "string",
                "description": "Extra flags (e.g., '-mc 200,301 -fs 0')",
            },
        },
        "required": ["url"],
    },
)

dns_enum = ToolDefinition(
    name="dns_enum",
    description=(
        "Enumerate DNS records for a domain. Discovers subdomains, "
        "mail servers, zone transfers."
    ),
    parameters={
        "type": "object",
        "properties": {
            "domain": {
                "type": "string",
                "description": "Target domain (e.g., 'example.com')",
            },
            "nameserver": {
                "type": "string",
                "description": "DNS server to query (optional)",
            },
        },
        "required": ["domain"],
    },
)


def get_recon_tools() -> list[ToolDefinition]:
    """Return all reconnaissance tool definitions."""
    return [nmap_scan, gobuster_dir, ffuf_fuzz, dns_enum]
