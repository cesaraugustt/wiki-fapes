#!/usr/bin/env python3
"""CLI mínimo para a wiki OKF (somente biblioteca padrão).

  python tools/okf.py index                 regenera o catálogo em wiki/index.md
  python tools/okf.py find TERMO [--type T] [--tag X] [--status S] [--regex]
  python tools/okf.py read CONCEITO [--links]     ex.: read editais/edital-24-2026-ppp-es

CONCEITO é o caminho dentro de wiki/ sem o sufixo .md.
"""
import argparse
import re
import sys
from pathlib import Path

WIKI = Path(__file__).resolve().parent.parent / "wiki"
RESERVED = {"index.md", "log.md"}
START, END = "<!-- catalog:start -->", "<!-- catalog:end -->"


def parse_scalar(v):
    v = v.strip()
    if v.startswith("[") and v.endswith("]"):
        return [parse_scalar(x) for x in split_top(v[1:-1]) if x.strip()]
    if v.startswith("{") and v.endswith("}"):
        out = {}
        for part in split_top(v[1:-1]):
            if ":" in part:
                k, _, val = part.partition(":")
                out[k.strip()] = parse_scalar(val)
        return out
    if len(v) >= 2 and v[0] == v[-1] and v[0] in "\"'":
        return v[1:-1]
    return v


def split_top(s):
    """Divide por vírgula fora de [] e {}."""
    parts, depth, cur = [], 0, ""
    for ch in s:
        if ch in "[{":
            depth += 1
        elif ch in "]}":
            depth -= 1
        if ch == "," and depth == 0:
            parts.append(cur)
            cur = ""
        else:
            cur += ch
    return parts + [cur]


def parse_frontmatter(text):
    """Retorna (meta, corpo). Cobre escalares, listas/mapas inline e listas em bloco."""
    if not text.startswith("---"):
        return {}, text
    m = re.match(r"---\s*\n(.*?)\n---\s*\n?(.*)", text, re.S)
    if not m:
        return {}, text
    meta, key = {}, None
    for line in m.group(1).splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if line.startswith((" ", "\t")):  # continuação de lista/mapa em bloco
            s = line.strip()
            if key is None:
                continue
            if s.startswith("- "):
                item = s[2:].strip()
                if not isinstance(meta[key], list):
                    meta[key] = []
                if ":" in item and not item.startswith(("{", "[", '"', "'")):
                    k, _, v = item.partition(":")
                    meta[key].append({k.strip(): parse_scalar(v)})
                else:
                    meta[key].append(parse_scalar(item))
            elif ":" in s and isinstance(meta[key], list) and meta[key] and isinstance(meta[key][-1], dict):
                k, _, v = s.partition(":")
                meta[key][-1][k.strip()] = parse_scalar(v)
            continue
        k, _, v = line.partition(":")
        key = k.strip()
        v = re.sub(r"\s+#.*$", "", v).strip()
        meta[key] = parse_scalar(v) if v else ""
    return meta, m.group(2)


def concepts():
    for p in sorted(WIKI.rglob("*.md")):
        if p.name in RESERVED:
            continue
        text = p.read_text(encoding="utf-8")
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
    text = idx.read_text(encoding="utf-8")
    new = "\n".join(block) + "\n"
    if START in text and END in text:
        text = re.sub(re.escape(START) + r".*?" + re.escape(END) + r"\n?", lambda _: new, text, flags=re.S)
    else:
        text = re.sub(r"\nAinda sem conteúdo ingerido\.\n?", "\n", text).rstrip() + "\n\n" + new
    idx.write_text(text, encoding="utf-8")
    print(f"index: {sum(len(v) for v in groups.values())} conceitos")


def cmd_find(a):
    pat = re.compile(a.term if a.regex else re.escape(a.term), re.I)
    for cid, _p, meta, body in concepts():
        if a.type and meta.get("type", "").lower() != a.type.lower():
            continue
        if a.tag and a.tag not in (meta.get("tags") or []):
            continue
        if a.status and meta.get("status") != a.status:
            continue
        head = " ".join(str(meta.get(k, "")) for k in ("title", "description", "tags"))
        hit = pat.search(head) or next((pat.search(l) and l for l in body.splitlines() if pat.search(l)), None)
        if not hit:
            continue
        snippet = "" if hasattr(hit, "re") else " | " + hit.strip()[:100]
        print(f"{cid}  [{meta.get('type', '?')}/{meta.get('status', '?')}]{snippet}")


def cmd_read(a):
    p = WIKI / f"{a.concept.removesuffix('.md')}.md"
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
    f.set_defaults(fn=cmd_find)
    r = sub.add_parser("read")
    r.add_argument("concept")
    r.add_argument("--links", action="store_true")
    r.set_defaults(fn=cmd_read)
    a = ap.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()
