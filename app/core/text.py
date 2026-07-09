"""Conversao de markdown minima e segura para as anotacoes.

Escapa HTML primeiro (evita XSS) e depois aplica um subconjunto de markdown:
negrito, italico, codigo, titulos, listas e quebras de linha.
"""
from __future__ import annotations

import html
import re

from markupsafe import Markup

_BOLD = re.compile(r"\*\*(.+?)\*\*")
_ITALIC = re.compile(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)")
_CODE = re.compile(r"`(.+?)`")


def markdown_to_html(text: str) -> Markup:
    if not text:
        return Markup("")
    escaped = html.escape(text)
    lines = escaped.split("\n")
    out: list[str] = []
    in_list = False
    for raw in lines:
        line = raw.rstrip()
        if line.startswith("- ") or line.startswith("* "):
            if not in_list:
                out.append("<ul>")
                in_list = True
            out.append(f"<li>{_inline(line[2:])}</li>")
            continue
        if in_list:
            out.append("</ul>")
            in_list = False
        if line.startswith("### "):
            out.append(f"<h4>{_inline(line[4:])}</h4>")
        elif line.startswith("## "):
            out.append(f"<h3>{_inline(line[3:])}</h3>")
        elif line.startswith("# "):
            out.append(f"<h2>{_inline(line[2:])}</h2>")
        elif not line:
            out.append("<br>")
        else:
            out.append(f"<p>{_inline(line)}</p>")
    if in_list:
        out.append("</ul>")
    return Markup("".join(out))


def _inline(text: str) -> str:
    text = _BOLD.sub(r"<strong>\1</strong>", text)
    text = _ITALIC.sub(r"<em>\1</em>", text)
    text = _CODE.sub(r"<code>\1</code>", text)
    return text
