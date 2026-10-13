#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["pyyaml"]
# ///
"""CLI para a wiki OKF.

  uv run tools/okf.py index                 regenera o catálogo em wiki/index.md
  uv run tools/okf.py find TERMO [--type T] [--tag X] [--status S] [--regex] [--limit N]
  uv run tools/okf.py read CONCEITO [--links]     ex.: read /editais/edital-24-2026-ppp-es

CONCEITO é o caminho relativo a wiki/ com ou sem '/' inicial e com ou sem '.md'.
"""
import argparse
import re
import sys
from pathlib import Path

import yaml

WIKI = Path(__file__).resolve().parent.parent / "wiki"
RESERVED = {"index.md", "log.md", "README.md"}
START, END = "<!-- catalog:start -->", "<!-- catalog:end -->"


def parse_frontmatter(text: str) -> tuple[dict, str]:
    """Retorna (meta, corpo) usando PyYAML seguro."""
    if not text.startswith("---"):
        return {}, text
    m = re.match(r"---\s*\n(.*?)\n---\s*\n?(.*)", text, re.DOTALL)
    if not m:
        return {}, text
    try:
        data = yaml.safe_load(m.group(1))
        meta = data if isinstance(data, dict) else {}
    except yaml.YAMLError:
        meta = {}
    return meta, m.group(2)


def concepts():
    for p in sorted(WIKI.rglob("*.md")):
        if p.name in RESERVED:
            continue
        text = p.read_text(encoding="utf-8", errors="replace")
        meta, body = parse_frontmatter(text)
        cid = p.relative_to(WIKI).with_suffix("").as_posix()
        yield cid, p, meta, body


def cmd_index(_):
    groups = {}
    for cid, _p, meta, _b in concepts():
        folder = cid.split("/")[0] if "/" in cid else "(raiz)"
        title = meta.get("title") or Path(cid).name
        desc = meta.get("description", "")
        line = f"- [{title}](/{cid}.md)" + (f" — {desc}" if desc else "")
        groups.setdefault(folder, []).append(line)
    block = [START]
    for folder in sorted(groups):
        block += [f"\n## {folder}\n", *groups[folder]]
    if not groups:
        block.append("\nAinda sem conteúdo ingerido.")
    block.append("\n" + END)
    idx = WIKI / "index.md"
    text = idx.read_text(encoding="utf-8") if idx.exists() else "# Wiki FAPES\n\n"
    new = "\n".join(block) + "\n"
    if START in text and END in text:
        text = re.sub(re.escape(START) + r".*?" + re.escape(END) + r"\n?", lambda _: new, text, flags=re.DOTALL)
    else:
        text = re.sub(r"\nAinda sem conteúdo ingerido\.\n?", "\n", text).rstrip() + "\n\n" + new
    idx.parent.mkdir(parents=True, exist_ok=True)
    idx.write_text(text, encoding="utf-8")
    print(f"index: {sum(len(v) for v in groups.values())} conceitos")


def cmd_find(a):
    pat = re.compile(a.term if a.regex else re.escape(a.term), re.IGNORECASE)
    needles = [t.lower() for t in a.term.split()] if not a.regex else []
    hits = []
    for cid, _p, meta, body in concepts():
        if a.type and str(meta.get("type", "")).lower() != a.type.lower():
            continue
        if a.tag and a.tag not in (meta.get("tags") or []):
            continue
        if a.status and meta.get("status") != a.status:
            continue
        title = str(meta.get("title", ""))
        desc = str(meta.get("description", ""))
        tags = " ".join(str(t) for t in (meta.get("tags") or []))
        head = f"{title} {desc} {tags}"

        head_match = pat.search(head)
        body_line = next((l for l in body.splitlines() if pat.search(l)), None)
        if not head_match and not body_line:
            continue

        if needles:
            strong = head.lower()
            weak = body.lower()
            score = sum(3 * strong.count(n) + (1 if n in weak else 0) for n in needles)
        else:
            score = 1

        snippet = f" | {body_line.strip()[:100]}" if (body_line and not head_match) else ""
        hits.append((score, cid, meta.get("type", "?"), meta.get("status", "?"), title, snippet))

    if not hits:
        print(f"nenhum resultado para '{a.term}'")
        return

    hits.sort(key=lambda h: (-h[0], h[1]))
    limit = getattr(a, "limit", 15) or 15
    for score, cid, ctype, status, title, snippet in hits[:limit]:
        info = f"  [{score:>2}] {cid} [{ctype}/{status}]"
        if title:
            info += f" — {title}"
        if snippet:
            info += snippet
        print(info)


def cmd_read(a):
    rel = a.concept.lstrip("/").removesuffix(".md")
    p = WIKI / f"{rel}.md"
    if not p.exists():
        sys.exit(f"não encontrado: {a.concept}")
    text = p.read_text(encoding="utf-8")
    print(text)
    if a.links:
        _, body = parse_frontmatter(text)
        print("\n# links de saída")
        for t, h in re.findall(r"\[([^\]]+)\]\((/[^)\s]+\.md)\)", body):
            print(f"- {h}  ({t})")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("index").set_defaults(fn=cmd_index)

    f = sub.add_parser("find")
    f.add_argument("term")
    f.add_argument("--type")
    f.add_argument("--tag")
    f.add_argument("--status")
    f.add_argument("--regex", action="store_true")
    f.add_argument("--limit", type=int, default=15)
    f.set_defaults(fn=cmd_find)

    r = sub.add_parser("read")
    r.add_argument("concept")
    r.add_argument("--links", action="store_true")
    r.set_defaults(fn=cmd_read)

    a = ap.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()
