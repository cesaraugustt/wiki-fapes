#!/usr/bin/env python3
"""Crawler da seção de Editais da FAPES (somente biblioteca padrão).

Uso:
  python tools/crawl.py --plan [--round 1|2]   lista PDFs/links, tamanho (HEAD); não baixa
  python tools/crawl.py --run  [--round 1|2]   baixa o plano aprovado e atualiza o manifest

Rodadas:
  1 = editais abertos + em julgamento
  2 = editais encerrados
Resultados de editais ficam de fora (dados pessoais).
"""
import argparse
import csv
import hashlib
import html.parser
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import urllib.robotparser
from datetime import datetime, timezone
from pathlib import Path

BASE = "https://fapes.es.gov.br"
UA = "fapes-wiki-crawler/0.1 (pesquisa; projeto de especificacao do novo sistema)"
DELAY = 2.0
ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "raw"
MANIFEST = RAW / "_manifest.csv"
PLAN_FILE = RAW / "_plan.json"
FIELDS = ["url", "data_coleta", "sha256", "secao", "tipo", "status",
          "http_status", "content_type", "bytes", "local_path"]

ROUNDS = {
    1: {
        "editais-abertos": [
            "/edital-aberto-formação-científica", "/editais-abertos-pesquisa-4",
            "/difusao-do-conhecimento", "/editais-abertos-extensao-2",
            "/inovacao", "/chamadas-internacionais",
        ],
        "editais-em-julgamento": [
            "/editais-em-julgamento-carreira-cientifica-2", "/editais-em-julgamento-pesquisa-2",
            "/editais-em-julgamento-difusao-2", "/editais-em-julgamento-extensao-2",
            "/editais-em-julgamento-inovacao-2", "/editais-em-julgamento-chamadas-internacionais-2",
        ],
    },
    2: {"editais-encerrados": ["/Editais/Encerrados"]},
}


class Links(html.parser.HTMLParser):
    def __init__(self):
        super().__init__()
        self.hrefs = []

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            href = dict(attrs).get("href")
            if href:
                self.hrefs.append(href)


_last = 0.0
_robots = None


def polite_open(url, method="GET"):
    """Aplica delay entre requisições e checa robots.txt (404 = tudo permitido)."""
    global _last, _robots
    if _robots is None:
        _robots = urllib.robotparser.RobotFileParser()
        try:
            req = urllib.request.Request(BASE + "/robots.txt", headers={"User-Agent": UA})
            _robots.parse(urllib.request.urlopen(req, timeout=30).read().decode().splitlines())
        except urllib.error.HTTPError as e:
            if e.code == 404:
                _robots.parse(["User-agent: *", "Allow: /"])
            else:
                raise
    if not _robots.can_fetch(UA, url):
        raise PermissionError(f"bloqueado por robots.txt: {url}")
    wait = DELAY - (time.monotonic() - _last)
    if wait > 0:
        time.sleep(wait)
    req = urllib.request.Request(urllib.parse.quote(url, safe=":/?&=%#+"), method=method,
                                 headers={"User-Agent": UA})
    try:
        return urllib.request.urlopen(req, timeout=60)
    finally:
        _last = time.monotonic()


def collect(round_no):
    """Retorna {url_absoluta: secao} com os PDFs/arquivos linkados nas páginas-semente."""
    found = {}
    for secao, pages in ROUNDS[round_no].items():
        for page in pages:
            with polite_open(BASE + page) as r:
                body = r.read().decode("utf-8", "replace")
            p = Links()
            p.feed(body)
            for h in p.hrefs:
                h = urllib.parse.unquote(h)
                if re.search(r"/media/|\.pdf($|\?)", h, re.I):
                    url = urllib.parse.urljoin(BASE + "/", h)
                    if urllib.parse.urlparse(url).netloc == "fapes.es.gov.br":
                        found.setdefault(url, secao)
    return found


def plan(round_no):
    found = collect(round_no)
    items, total = [], 0
    for url, secao in sorted(found.items()):
        size, ctype = None, None
        try:
            with polite_open(url, "HEAD") as r:
                size = int(r.headers.get("Content-Length") or 0) or None
                ctype = r.headers.get("Content-Type")
        except Exception as e:  # noqa: BLE001 - relatório, não aborta
            ctype = f"erro: {e}"
        total += size or 0
        items.append({"url": url, "secao": secao, "bytes": size, "content_type": ctype})
        print(f"{secao:24} {size or '?':>10}  {url}")
    RAW.mkdir(exist_ok=True)
    PLAN_FILE.write_text(json.dumps(items, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\n{len(items)} arquivos, ~{total/1e6:.1f} MB. Plano salvo em {PLAN_FILE.relative_to(ROOT)}")


def read_manifest():
    if not MANIFEST.exists():
        return []
    with MANIFEST.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def run():
    if not PLAN_FILE.exists():
        sys.exit("rode --plan antes de --run")
    items = json.loads(PLAN_FILE.read_text(encoding="utf-8"))
    rows = read_manifest()
    by_url = {r["url"] for r in rows}
    by_hash = {r["sha256"]: r["local_path"] for r in rows if r["sha256"]}
    dest_dir = RAW / "editais"
    dest_dir.mkdir(parents=True, exist_ok=True)
    for it in items:
        if it["url"] in by_url:
            continue
        with polite_open(it["url"]) as r:
            data = r.read()
            status, ctype = r.status, r.headers.get("Content-Type")
        digest = hashlib.sha256(data).hexdigest()
        ext = Path(urllib.parse.urlparse(it["url"]).path).suffix.lower() or ".bin"
        if digest in by_hash:
            local = by_hash[digest]  # conteúdo duplicado: não grava de novo
        else:
            name = Path(urllib.parse.urlparse(it["url"]).path).stem
            slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")[:80]
            local = f"raw/editais/{slug}-{digest[:8]}{ext}"
            (ROOT / local).write_bytes(data)
            by_hash[digest] = local
        row = {
            "url": it["url"], "data_coleta": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "sha256": digest, "secao": it["secao"], "tipo": ext.lstrip("."),
            "status": "ok", "http_status": status, "content_type": ctype,
            "bytes": len(data), "local_path": local,
        }
        rows.append(row)
        print("ok", local)
        with MANIFEST.open("w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=FIELDS)
            w.writeheader()
            w.writerows(rows)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--plan", action="store_true")
    g.add_argument("--run", action="store_true")
    ap.add_argument("--round", type=int, choices=ROUNDS, default=1)
    a = ap.parse_args()
    plan(a.round) if a.plan else run()
