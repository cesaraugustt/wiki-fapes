#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "beautifulsoup4>=4.12.0",
#     "httpx>=0.27.0",
#     "lxml>=5.0.0",
# ]
# ///
"""Crawler robusto de documentos e editais da FAPES.

Uso:
  uv run tools/crawl.py --plan   descobre links no portal, checa HEAD assíncrono e gera _plan.json
  uv run tools/crawl.py --run    baixa os arquivos planejados com streaming e atualiza _manifest.csv

Características:
  - Descoberta dinâmica via menu da home da FAPES (sem slugs fixos com -2, -4).
  - Janela de editais encerrados: 2024 a 2026.
  - Concorrência assíncrona controlada (3 conexões paralelas) com delay ético.
  - Streaming direto para disco (evita estourar memória com PDFs de 70MB+).
  - Imutabilidade por URL: URLs já com status 'ok' no _manifest.csv são puladas no --plan.
  - Deduplicação por hash SHA-256 no armazenamento local.
  - Mantém o formato e as 10 colunas exatas do _manifest.csv.
"""
import argparse
import asyncio
import csv
import hashlib
import json
import re
import sys
import unicodedata
import urllib.robotparser
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import unquote, urljoin, urlparse

import httpx
from bs4 import BeautifulSoup

BASE = "https://fapes.es.gov.br"
UA = "fapes-wiki-crawler/0.2 (pesquisa; projeto de especificacao do novo sistema)"
DELAY = 1.0
CONCURRENCY = 3

_robot_parser: urllib.robotparser.RobotFileParser | None = None
_robot_lock = asyncio.Lock()


async def get_robot_parser(client: httpx.AsyncClient) -> urllib.robotparser.RobotFileParser:
    """Carrega e armazena em cache o robots.txt (404 = permitido tudo)."""
    global _robot_parser
    if _robot_parser is not None:
        return _robot_parser
    async with _robot_lock:
        if _robot_parser is not None:
            return _robot_parser
        parser = urllib.robotparser.RobotFileParser()
        try:
            r = await client.get(BASE + "/robots.txt", timeout=15.0)
            if r.status_code == 404:
                parser.parse(["User-agent: *", "Allow: /"])
            else:
                parser.parse(r.text.splitlines())
        except (httpx.HTTPError, OSError):
            parser.parse(["User-agent: *", "Allow: /"])
        _robot_parser = parser
        return _robot_parser


async def can_fetch(client: httpx.AsyncClient, url: str) -> bool:
    """Verifica se a URL é permitida segundo as regras de robots.txt."""
    rp = await get_robot_parser(client)
    return rp.can_fetch(UA, url)
ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "raw"
TMP_DIR = RAW / ".tmp"
MANIFEST = RAW / "_manifest.csv"
PLAN_FILE = RAW / "_plan.json"

FIELDS = [
    "url",
    "data_coleta",
    "sha256",
    "secao",
    "tipo",
    "status",
    "http_status",
    "content_type",
    "bytes",
    "local_path",
]

DIRS = {
    "editais-abertos": "editais",
    "editais-em-julgamento": "editais",
    "editais-encerrados": "editais",
    "legislacao": "legislacao",
    "prestacao-contas": "prestacao-contas",
    "formularios": "formularios",
    "institucional": "institucional",
    "bolsas": "bolsas",
}

# Seções cujas páginas-semente contêm texto substantivo e também devem ser salvas como HTML
HTML_SECTIONS = {"legislacao", "prestacao-contas", "formularios", "institucional", "bolsas"}

TARGET_YEARS = {"2024", "2025", "2026"}

EXCLUDE = re.compile(r"\.(mp4|mov|avi|mkv)($|\?)|/Livro-Fapes-20-Anos", re.IGNORECASE)

# Sementes canônicas de segurança (caso o menu da home não contenha algum link pontual)
FALLBACK_SEEDS = {
    "editais-abertos": [
        "/edital-aberto-formação-científica",
        "/editais-abertos-pesquisa-4",
        "/difusao-do-conhecimento",
        "/editais-abertos-extensao-2",
        "/inovacao",
        "/chamadas-internacionais",
    ],
    "editais-em-julgamento": [
        "/editais-em-julgamento-carreira-cientifica-2",
        "/editais-em-julgamento-pesquisa-2",
        "/editais-em-julgamento-difusao-2",
        "/editais-em-julgamento-extensao-2",
        "/editais-em-julgamento-inovacao-2",
        "/editais-em-julgamento-chamadas-internacionais-2",
    ],
    "editais-encerrados": ["/Editais/Encerrados"],
    "legislacao": ["/legislacao", "/leis", "/resolucoes", "/decretos", "/portarias", "/notatecnica"],
    "prestacao-contas": [
        "/prestacao-de-contas",
        "/orientacoes",
        "/manual",
        "/itens-financiaveis-e-nao-financiaveis",
        "/instrucoes-de-uso-de-diarias",
        "/formularios-2",
        "/tutoriais-prestacao-contas",
        "/termo-de-fomento-colaboracao-cooperacao",
        "/relatorio-ordenador-de-despesas-2",
    ],
    "formularios": ["/formularios", "/tutoriais", "/perguntas-frequentes"],
    "institucional": [
        "/pcti-es",
        "/conselho-cientifico-administrativo-ccaf",
        "/camaras-de-assessoramento",
        "/competencias",
        "/UECI",
        "/sobre-a-ueci",
        "/normas-de-procedimento-UECI",
        "/legislacoes-e-publicacoes-ueci",
        "/contatos-ueci",
    ],
    "bolsas": [
        "/valores-de-bolsas-e-auxilios",
        "/calendario-de-pagamento-de-bolsas-da-fapes-ano-2026",
        "/nossa-bolsa",
    ],
}


def read_manifest() -> list[dict]:
    if not MANIFEST.exists():
        return []
    with MANIFEST.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def save_manifest(rows: list[dict]) -> None:
    RAW.mkdir(exist_ok=True)
    with MANIFEST.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def normalize_url(href: str, base_url: str = BASE) -> str:
    url = urljoin(base_url, href.strip())
    parsed = urlparse(url)
    return parsed._replace(fragment="").geturl()


def is_fapes_host(url: str) -> bool:
    host = urlparse(url).netloc.lower()
    return host in {"fapes.es.gov.br", "www.fapes.es.gov.br"}


async def discover_sections(client: httpx.AsyncClient) -> dict[str, set[str]]:
    """Descobre rotas de seções navegando pela homepage da FAPES."""
    sections: dict[str, set[str]] = {s: set(urls) for s, urls in FALLBACK_SEEDS.items()}

    try:
        if not await can_fetch(client, BASE):
            print(f"[aviso] Home {BASE} bloqueada por robots.txt.")
            return {s: {urljoin(BASE, u) for u in urls} for s, urls in sections.items()}
        resp = await client.get(BASE, timeout=25.0)
        resp.raise_for_status()
    except (httpx.HTTPError, OSError) as e:
        print(f"[aviso] Falha ao ler home da FAPES para descoberta: {e}. Usando sementes padrão.")
        return {s: {urljoin(BASE, u) for u in urls} for s, urls in sections.items()}

    soup = BeautifulSoup(resp.text, "lxml")

    # Mapear links da barra de navegação e menu
    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        text = a.get_text(" ", strip=True)
        if not href or href.startswith(("#", "javascript:")):
            continue
        full_url = normalize_url(href)
        if not is_fapes_host(full_url):
            continue

        path_orig = urlparse(full_url).path
        path_lower = path_orig.lower()
        text_lower = text.lower()

        # Editais Abertos
        if "edital-aberto" in path_lower or ("aberto" in text_lower and "edital" in text_lower):
            sections["editais-abertos"].add(path_orig)
        # Editais em Julgamento
        elif "julgamento" in path_lower or "julgamento" in text_lower:
            sections["editais-em-julgamento"].add(path_orig)
        # Editais Encerrados
        elif "encerrado" in path_lower or "encerrados" in text_lower:
            if "teletrabalho" not in path_lower:
                sections["editais-encerrados"].add(path_orig)
        # Legislação
        elif any(k in path_lower for k in ["/leis", "/resolucoes", "/decretos", "/portarias", "/notatecnica"]):
            sections["legislacao"].add(path_orig)
        # Prestação de contas
        elif any(k in path_lower for k in ["prestacao", "diarias", "itens-financiaveis"]):
            sections["prestacao-contas"].add(path_orig)
        # Bolsas
        elif any(k in path_lower for k in ["bolsa", "auxilio"]):
            sections["bolsas"].add(path_orig)

    # Converte tudo para URLs absolutas
    return {s: {urljoin(BASE, u) for u in urls} for s, urls in sections.items()}


def extract_links_from_html(html: str, page_url: str, secao: str) -> dict[str, str]:
    """Extrai links para arquivos (.pdf, docx, etc.) de uma página HTML."""
    found: dict[str, str] = {}
    soup = BeautifulSoup(html, "lxml")

    # Se for a página de Editais Encerrados, extrai das tabelas dos anos alvo
    if "encerrados" in secao.lower() or "encerrados" in page_url.lower():
        for heading in soup.find_all(re.compile(r"^h[1-6]$")):
            htext = heading.get_text(" ", strip=True)
            m = re.search(r"Editais Encerrados\s+(\d{4})", htext)
            if not m or m.group(1) not in TARGET_YEARS:
                continue
            table = heading.find_next("table")
            if not table:
                continue
            for a in table.find_all("a", href=True):
                h = unquote(a["href"].strip())
                if re.search(r"(/media/[^?#]+\.[a-zA-Z0-9]{2,5}|\.pdf)($|\?)", h, re.IGNORECASE) and not EXCLUDE.search(h):
                    url = normalize_url(h, page_url)
                    if is_fapes_host(url):
                        found[url] = secao
        return found

    # Outras páginas de editais ou seções gerais
    for a in soup.find_all("a", href=True):
        h = unquote(a["href"].strip())
        if re.search(r"(/media/[^?#]+\.[a-zA-Z0-9]{2,5}|\.(pdf|docx?|xlsx?|odt|ods|csv|zip))($|\?)", h, re.IGNORECASE) and not EXCLUDE.search(h):
            url = normalize_url(h, page_url)
            if is_fapes_host(url):
                found[url] = secao

    return found


async def plan() -> None:
    """Descobre arquivos no portal e gera o plano _plan.json sem baixar conteúdo."""
    manifest_rows = read_manifest()
    # Só pula se estiver 'ok' no manifesto E o arquivo existir fisicamente no disco
    known_ok_urls = {
        r["url"]
        for r in manifest_rows
        if r["status"] == "ok" and r.get("local_path") and (ROOT / r["local_path"]).exists()
    }

    missing_on_disk = len([r for r in manifest_rows if r["status"] == "ok"]) - len(known_ok_urls)
    if missing_on_disk > 0:
        print(f"[alerta] {missing_on_disk} arquivos constam no manifesto como 'ok' mas NÃO estão no disco. Serão replanejados.")

    print(f"Lendo manifesto existente: {len(known_ok_urls)} arquivos verificados no disco serão pulados.")

    limits = httpx.Limits(max_keepalive_connections=5, max_connections=CONCURRENCY)
    async with httpx.AsyncClient(headers={"User-Agent": UA}, follow_redirects=True, limits=limits) as client:
        print("Descobrindo rotas das seções no portal FAPES...")
        sections = await discover_sections(client)

        found_candidates: dict[str, str] = {}

        for secao, page_urls in sections.items():
            print(f"  Varrer seção [{secao}] ({len(page_urls)} páginas-semente)...")
            for page_url in sorted(page_urls):
                if secao in HTML_SECTIONS:
                    found_candidates.setdefault(page_url, secao)

                try:
                    await asyncio.sleep(DELAY)
                    if not await can_fetch(client, page_url):
                        print(f"    [bloqueado por robots.txt] {page_url}")
                        continue
                    resp = await client.get(page_url, timeout=20.0)
                    if resp.status_code == 200:
                        page_links = extract_links_from_html(resp.text, page_url, secao)
                        found_candidates.update(page_links)
                    else:
                        print(f"    [aviso] HTTP {resp.status_code} ao ler {page_url}")
                except (httpx.HTTPError, OSError) as e:
                    print(f"    [erro de rede] Falha ao ler {page_url}: {e}")

        # Filtrar URLs já conhecidas
        new_urls = {url: sec for url, sec in found_candidates.items() if url not in known_ok_urls}

        print(f"\nTotal descoberto: {len(found_candidates)} arquivos/páginas.")
        print(f"Inéditos para planejar: {len(new_urls)} (os demais já constam no _manifest.csv).")

        if not new_urls:
            print("Nenhum arquivo novo para baixar. O repositório está 100% atualizado.")
            RAW.mkdir(exist_ok=True)
            PLAN_FILE.write_text("[]", encoding="utf-8")
            return

        print("\nConsultando cabeçalhos HEAD assíncrono para os novos arquivos...")
        sem = asyncio.Semaphore(CONCURRENCY)

        async def inspect(url: str, secao: str) -> dict:
            async with sem:
                await asyncio.sleep(DELAY / 2)
                size, ctype = None, None
                try:
                    if not await can_fetch(client, url):
                        return {"url": url, "secao": secao, "bytes": None, "content_type": "bloqueado por robots.txt"}
                    r = await client.head(url, timeout=15.0)
                    size_header = r.headers.get("content-length")
                    size = int(size_header) if size_header and size_header.isdigit() else None
                    ctype = r.headers.get("content-type")
                except httpx.HTTPStatusError as e:
                    ctype = f"erro HTTP {e.response.status_code}"
                except (httpx.HTTPError, OSError) as e:
                    ctype = f"erro de rede: {e}"
                return {"url": url, "secao": secao, "bytes": size, "content_type": ctype}

        tasks = [inspect(url, sec) for url, sec in sorted(new_urls.items())]
        items = await asyncio.gather(*tasks)

        total_bytes = sum(it["bytes"] or 0 for it in items)
        for it in items:
            sz_str = f"{it['bytes']/1024:.1f} KB" if it["bytes"] else "?"
            print(f"{it['secao']:24} {sz_str:>12}  {it['url']}")

        RAW.mkdir(exist_ok=True)
        PLAN_FILE.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\n{len(items)} novos arquivos (~{total_bytes/1e6:.1f} MB).")
        print(f"Plano salvo em {PLAN_FILE.relative_to(ROOT)}. Revise e rode com --run para baixar.")


async def run() -> None:
    """Executa os downloads planejados com streaming, semáforo e atualização incremental do manifest."""
    if not PLAN_FILE.exists():
        sys.exit("Erro: execute 'uv run tools/crawl.py --plan' antes de rodar '--run'.")

    items = json.loads(PLAN_FILE.read_text(encoding="utf-8"))
    if not items:
        print("Plano vazio. Nada a baixar.")
        return

    manifest_rows = read_manifest()
    by_url = {
        r["url"]
        for r in manifest_rows
        if r["status"] == "ok" and r.get("local_path") and (ROOT / r["local_path"]).exists()
    }
    by_hash = {
        r["sha256"]: r["local_path"]
        for r in manifest_rows
        if r["sha256"] and r.get("local_path") and (ROOT / r["local_path"]).exists()
    }

    TMP_DIR.mkdir(parents=True, exist_ok=True)
    sem = asyncio.Semaphore(CONCURRENCY)
    write_lock = asyncio.Lock()

    limits = httpx.Limits(max_keepalive_connections=5, max_connections=CONCURRENCY)
    async with httpx.AsyncClient(headers={"User-Agent": UA}, follow_redirects=True, limits=limits) as client:

        async def download_one(it: dict) -> None:
            url = it["url"]
            secao = it["secao"]

            if url in by_url:
                return

            if not await can_fetch(client, url):
                print(f"[bloqueado por robots.txt] {url}")
                return

            now = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
            tmp_file = TMP_DIR / f"dl-{hashlib.md5(url.encode()).hexdigest()[:12]}.tmp"

            async with sem:
                await asyncio.sleep(DELAY / 2)
                data_hash = hashlib.sha256()
                status_code, ctype, total_downloaded = None, None, 0

                for attempt in range(3):
                    try:
                        async with client.stream("GET", url, timeout=45.0) as resp:
                            status_code = resp.status_code
                            ctype = resp.headers.get("content-type")
                            resp.raise_for_status()

                            with tmp_file.open("wb") as f:
                                async for chunk in resp.aiter_bytes(chunk_size=65536):
                                    f.write(chunk)
                                    data_hash.update(chunk)
                                    total_downloaded += len(chunk)
                        break
                    except (httpx.HTTPError, OSError, asyncio.TimeoutError) as e:
                        if tmp_file.exists():
                            tmp_file.unlink(missing_ok=True)
                        if attempt < 2:
                            await asyncio.sleep(3)
                            continue
                        # Falha definitiva
                        err_code = (
                            str(e.response.status_code)
                            if isinstance(e, httpx.HTTPStatusError)
                            else e.__class__.__name__
                        )
                        print(f"ERRO ao baixar {url}: {e}")
                        async with write_lock:
                            # Remove linha anterior com erro se houver
                            nonlocal manifest_rows
                            manifest_rows = [r for r in manifest_rows if r["url"] != url]
                            manifest_rows.append({
                                "url": url,
                                "data_coleta": now,
                                "sha256": "",
                                "secao": secao,
                                "tipo": "",
                                "status": "erro",
                                "http_status": str(err_code),
                                "content_type": "",
                                "bytes": "",
                                "local_path": "",
                            })
                            save_manifest(manifest_rows)
                        return

            digest = data_hash.hexdigest()
            url_path = Path(urlparse(url).path)
            ext = url_path.suffix.lower()
            if not ext:
                ext = ".html" if "html" in (ctype or "").lower() else ".bin"

            async with write_lock:
                if digest in by_hash:
                    # Conteúdo idêntico já baixado antes: reutiliza o arquivo existente
                    local = by_hash[digest]
                    if tmp_file.exists():
                        tmp_file.unlink(missing_ok=True)
                else:
                    stem = url_path.stem or "index"
                    ascii_name = unicodedata.normalize("NFKD", stem).encode("ascii", "ignore").decode()
                    slug = re.sub(r"[^a-z0-9]+", "-", ascii_name.lower()).strip("-")[:80] or "arquivo"
                    folder = DIRS.get(secao, secao)
                    local = f"raw/{folder}/{slug}-{digest[:8]}{ext}"
                    dest = ROOT / local
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    tmp_file.replace(dest)
                    by_hash[digest] = local

                manifest_rows = [r for r in manifest_rows if r["url"] != url]
                manifest_rows.append({
                    "url": url,
                    "data_coleta": now,
                    "sha256": digest,
                    "secao": secao,
                    "tipo": ext.lstrip("."),
                    "status": "ok",
                    "http_status": str(status_code),
                    "content_type": ctype or "",
                    "bytes": str(total_downloaded),
                    "local_path": local,
                })
                by_url.add(url)
                save_manifest(manifest_rows)
                print(f"OK ({total_downloaded/1024:.1f} KB) -> {local}")

        tasks = [download_one(it) for it in items]
        await asyncio.gather(*tasks)

    # Limpeza de resíduos temporários
    if TMP_DIR.exists():
        for f in TMP_DIR.glob("*.tmp"):
            f.unlink(missing_ok=True)

    print("\nExecução do crawler concluída com sucesso.")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--plan", action="store_true", help="Gera plano de download em raw/_plan.json sem baixar")
    g.add_argument("--run", action="store_true", help="Baixa os arquivos do plano e atualiza _manifest.csv")
    a = ap.parse_args()

    if a.plan:
        asyncio.run(plan())
    elif a.run:
        asyncio.run(run())


if __name__ == "__main__":
    main()
