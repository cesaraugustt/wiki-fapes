#!/usr/bin/env python3
"""Crawler de documentos e editais da FAPES (somente biblioteca padrão).

Uso:
  python tools/crawl.py --plan [--round 1|2|3]   lista PDFs/links, tamanho (HEAD); não baixa
  python tools/crawl.py --run                     baixa o plano aprovado e atualiza o manifest

Rodadas:
  1 = editais abertos + em julgamento
  2 = editais encerrados
  3 = legislação, prestação de contas, formulários e institucional
"""
import argparse
import csv
import hashlib
import html.parser
import json
import re
import sys
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
import urllib.robotparser
from datetime import UTC, datetime
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
    3: {
        "legislacao": ["/leis", "/resolucoes", "/decretos", "/portarias", "/notatecnica"],
        "prestacao-contas": [
            "/prestacao-de-contas", "/orientacoes", "/manual", "/itens-financiaveis-e-nao-financiaveis",
            "/instrucoes-de-uso-de-diarias", "/formularios-2", "/tutoriais-prestacao-contas",
            "/termo-de-fomento-colaboracao-cooperacao", "/relatorio-ordenador-de-despesas-2",
        ],
        "formularios": ["/formularios", "/tutoriais", "/perguntas-frequentes"],
        "institucional": [
            "/pcti-es", "/conselho-cientifico-administrativo-ccaf", "/camaras-de-assessoramento",
            "/competencias", "/UECI", "/sobre-a-ueci", "/normas-de-procedimento-UECI",
            "/legislacoes-e-publicacoes-ueci",
        ],
    },
}
# secao -> subpasta de raw/ (padrão: o próprio nome da seção)
DIRS = {"editais-abertos": "editais", "editais-em-julgamento": "editais", "editais-encerrados": "editais"}
# rodadas cujas páginas-semente também são fontes (o conteúdo está no HTML)
SAVE_PAGES = {3}
# fora do escopo: vídeos (sem transcrição não viram texto) e o e-book comemorativo
EXCLUDE = re.compile(r"\.(mp4|mov|avi|mkv)($|\?)|/Livro-Fapes-20-Anos", re.IGNORECASE)


class Links(html.parser.HTMLParser):
    def __init__(self):
        super().__init__()
        self.hrefs = []

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            href = dict(attrs).get("href")
            if href:
                self.hrefs.append(href)


_last_request_time = 0.0
_robot_parser = None


def polite_open(url, method="GET"):
    """Aplica delay entre requisições e checa robots.txt (404 = tudo permitido)."""
    global _last_request_time, _robot_parser
    if _robot_parser is None:
        _robot_parser = urllib.robotparser.RobotFileParser()
        try:
            wait = DELAY - (time.monotonic() - _last_request_time)
            if wait > 0:
                time.sleep(wait)
            req = urllib.request.Request(BASE + "/robots.txt", headers={"User-Agent": UA})
            _robot_parser.parse(urllib.request.urlopen(req, timeout=30).read().decode().splitlines())
            _last_request_time = time.monotonic()
        except urllib.error.HTTPError as e:
            if e.code == 404:
                _robot_parser.parse(["User-agent: *", "Allow: /"])
            else:
                raise
    if not _robot_parser.can_fetch(UA, url):
        raise PermissionError(f"bloqueado por robots.txt: {url}")
    wait = DELAY - (time.monotonic() - _last_request_time)
    if wait > 0:
        time.sleep(wait)
    req = urllib.request.Request(urllib.parse.quote(url, safe=":/?&=%#+"), method=method,
                                 headers={"User-Agent": UA})
    try:
        return urllib.request.urlopen(req, timeout=60)
    finally:
        _last_request_time = time.monotonic()


def collect(round_no):
    """Retorna {url_absoluta: secao} com os PDFs/arquivos linkados nas páginas-semente."""
    found = {}
    for secao, pages in ROUNDS[round_no].items():
        for page in pages:
            if round_no in SAVE_PAGES:
                found.setdefault(BASE + page, secao)
            with polite_open(BASE + page) as r:
                body = r.read().decode("utf-8", "replace")
            p = Links()
            p.feed(body)
            for h in p.hrefs:
                h = urllib.parse.unquote(h)
                if re.search(r"/media/|\.pdf($|\?)", h, re.IGNORECASE) and not EXCLUDE.search(h):
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
    by_url = {r["url"] for r in rows if r["status"] == "ok"}
    by_hash = {r["sha256"]: r["local_path"] for r in rows if r["sha256"]}

    def save(rows):
        with MANIFEST.open("w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=FIELDS)
            w.writeheader()
            w.writerows(rows)

    for it in items:
        if it["url"] in by_url:
            continue
        now = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
        rows = [r for r in rows if r["url"] != it["url"]]  # descarta tentativa anterior com erro
        try:
            with polite_open(it["url"]) as r:
                data = r.read()
                status, ctype = r.status, r.headers.get("Content-Type")
        except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
            code = getattr(e, "code", "")
            rows.append({"url": it["url"], "data_coleta": now, "sha256": "", "secao": it["secao"],
                         "tipo": "", "status": "erro", "http_status": code, "content_type": "",
                         "bytes": "", "local_path": ""})
            print("ERRO", code or e, it["url"])
            save(rows)
            continue
        digest = hashlib.sha256(data).hexdigest()
        path = Path(urllib.parse.urlparse(it["url"]).path)
        ext = path.suffix.lower()
        if not ext:
            ext = ".html" if "html" in (ctype or "") else ".bin"
        if digest in by_hash:
            local = by_hash[digest]  # conteúdo duplicado: não grava de novo
        else:
            ascii_name = unicodedata.normalize("NFKD", path.stem or "index").encode("ascii", "ignore").decode()
            slug = re.sub(r"[^a-z0-9]+", "-", ascii_name.lower()).strip("-")[:80] or "arquivo"
            folder = DIRS.get(it["secao"], it["secao"])
            local = f"raw/{folder}/{slug}-{digest[:8]}{ext}"
            (ROOT / local).parent.mkdir(parents=True, exist_ok=True)
            (ROOT / local).write_bytes(data)
            by_hash[digest] = local
        row = {
            "url": it["url"], "data_coleta": now,
            "sha256": digest, "secao": it["secao"], "tipo": ext.lstrip("."),
            "status": "ok", "http_status": status, "content_type": ctype,
            "bytes": len(data), "local_path": local,
        }
        rows.append(row)
        by_url.add(it["url"])
        print("ok", local)
        save(rows)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--plan", action="store_true")
    g.add_argument("--run", action="store_true")
    ap.add_argument("--round", type=int, choices=ROUNDS, default=1)
    a = ap.parse_args()
    plan(a.round) if a.plan else run()
