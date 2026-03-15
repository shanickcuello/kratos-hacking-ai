"""Web application testing tools."""

from __future__ import annotations

from kratos.domain.entities import ToolDefinition

sqlmap_inject = ToolDefinition(
    name="sqlmap_inject",
    description=(
        "Run sqlmap for SQL injection testing. Automatically detects "
        "and exploits SQL injection vulnerabilities."
    ),
    parameters={
        "type": "object",
        "properties": {
            "url": {
                "type": "string",
                "description": "Target URL with parameter (e.g., 'http://10.10.10.1/page?id=1')",
            },
            "flags": {
                "type": "string",
                "description": (
                    "Extra sqlmap flags (e.g., '--dbs' to enumerate databases, "
                    "'--dump -T users' to dump a table). "
                    "Always runs with --batch for non-interactive mode."
                ),
            },
        },
        "required": ["url"],
    },
)

nikto_scan = ToolDefinition(
    name="nikto_scan",
    description=(
        "Run nikto web vulnerability scanner against a web server. "
        "Finds default files, misconfigurations, outdated software."
    ),
    parameters={
        "type": "object",
        "properties": {
            "host": {
                "type": "string",
                "description": "Target host (e.g., '10.10.10.1' or 'http://10.10.10.1:8080')",
            },
            "flags": {
                "type": "string",
                "description": "Extra nikto flags (e.g., '-Tuning x' for specific tests)",
            },
        },
        "required": ["host"],
    },
)

curl_request = ToolDefinition(
    name="curl_request",
    description=(
        "Make HTTP requests with curl. Useful for testing APIs, "
        "sending payloads, checking headers, downloading files."
    ),
    parameters={
        "type": "object",
        "properties": {
            "url": {
                "type": "string",
                "description": "Target URL",
            },
            "method": {
                "type": "string",
                "description": "HTTP method (GET, POST, PUT, DELETE). Default: GET",
            },
            "data": {
                "type": "string",
                "description": "Request body data (for POST/PUT)",
            },
            "headers": {
                "type": "string",
                "description": "Custom headers as comma-separated 'Key: Value' pairs",
            },
            "flags": {
                "type": "string",
                "description": "Extra curl flags (e.g., '-k' for insecure, '-L' for follow redirects)",
            },
        },
        "required": ["url"],
    },
)


def get_web_tools() -> list[ToolDefinition]:
    """Return all web testing tool definitions."""
    return [sqlmap_inject, nikto_scan, curl_request]
