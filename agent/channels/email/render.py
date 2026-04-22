"""Jinja2 renderer for email templates.

Renders a template into (subject, body_markdown). The template's first
`Subject: ...` line is pulled out as the subject; the rest is the body.
"""
from __future__ import annotations

import pathlib

from jinja2 import Environment, FileSystemLoader, select_autoescape

_TEMPLATE_DIR = pathlib.Path(__file__).parent / "templates"

_env = Environment(
    loader=FileSystemLoader(str(_TEMPLATE_DIR)),
    autoescape=select_autoescape(),
    trim_blocks=True,
    lstrip_blocks=True,
)


def render(template_name: str, **ctx) -> tuple[str, str]:
    tmpl = _env.get_template(template_name)
    text = tmpl.render(**ctx)
    lines = text.splitlines()
    subject = ""
    body_start = 0
    for i, line in enumerate(lines):
        if line.startswith("Subject:"):
            subject = line[len("Subject:"):].strip()
            body_start = i + 1
            break
    body = "\n".join(lines[body_start:]).strip()
    return subject, body
