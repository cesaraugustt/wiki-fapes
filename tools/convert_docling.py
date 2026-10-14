#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["docling", "pymupdf", "pyyaml"]
# ///
"""Converte raw/ -> raw-md/ com Docling (GPU), espelhando a estrutura de pastas.

Padrão OKF v0.2 para a Wiki FAPES.
- Não altera raw/ nem raw-text/.
- Retomável: manifesto com sha256 + status; arquivos já convertidos são pulados.
- Worker persistente com timeout e isolamento de processo.
- Detector de páginas corrompidas (fontes CID sem ToUnicode, glifos quebrados).
  Se alguma página for suspeita, ativa OCR forçado na conversão.
- Marcadores <!-- page N --> em PDFs.
- Frontmatter OKF v0.2 estrito com type: Fonte, chaves em inglês e fontes mapeadas.

Uso:
    uv run tools/convert_docling.py --limit 5
    uv run tools/convert_docling.py --missing-only
    nohup uv run tools/convert_docling.py > raw-md/_conversion.log 2>&1 &
"""
import argparse
import csv
import hashlib
import multiprocessing as mp
import re
import sys
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "raw"
RAW_TEXT = ROOT / "raw-text"
RAW_MD = ROOT / "raw-md"
MANIFEST_FILE = RAW / "_manifest.csv"

EXTS = {".pdf", ".docx", ".html", ".htm", ".xlsx", ".pptx"}
RESTART_EVERY = 30          # recria worker a cada N arquivos para purgar VRAM/RAM
OCR_MIN_ALNUM_RATIO = 0.85  # proporção mínima Docling / PyMuPDF get_text

FIELDS = ["rel", "sha256", "status", "pages", "ocr_forced", "ocr_pages", "seconds", "detail"]

# ----------------------------------------------------------- Detector de Corrupção --
FUNC = set(
    "de da do das dos que o a e para em um uma com no na os as por se ao é não "
    "the of and to in is for on fapes edital bolsa processo artigo resolucao".split()
)
ALNUM = re.compile(r"[A-Za-z0-9À-ÖØ-öø-ÿ]")
WORD = re.compile(r"[A-Za-zÀ-ÖØ-öø-ÿ]+")
BAD = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\ufffd\u2700-\u27bf\ue000-\uf8ff]")


def page_is_suspect(page) -> tuple[bool, str]:
    """Detecta se uma página tem camada de texto corrompida ou vazia."""
    text = page.get_text()
    s = re.sub(r"\s", "", text)
    if len(s) < 25:
        # Sem camada de texto: suspeita se tiver imagem
        has_img = bool(page.get_images())
        return has_img, "sem_texto_com_imagem" if has_img else "sem_texto"

    # Caracteres inválidos / controle / private use area
    bad_matches = len(BAD.findall(s))
    if bad_matches / len(s) > 0.02:
        return True, f"caracteres_invalidos_{bad_matches}"

    # Caracteres alfanuméricos vs símbolos (considerando letras e dígitos para não quebrar tabelas)
    alnum_matches = len(ALNUM.findall(s))
    if alnum_matches / len(s) < 0.45:
        return True, "baixa_densidade_alfanumerica"

    # Frequência de palavras comuns (detecta texto cifrado/deslocado como 9LWyULD)
    words = WORD.findall(text.lower())
    if len(words) >= 30:
        func_count = sum(1 for w in words if w in FUNC)
        if func_count / len(words) < 0.05:
            return True, f"vocabulario_anomalo_{func_count}_em_{len(words)}"

    return False, "ok"


# ------------------------------------------------------------------------- Worker --
def build_converter(force_ocr: bool, device: str):
    from docling.datamodel.accelerator_options import AcceleratorDevice, AcceleratorOptions
    from docling.datamodel.base_models import InputFormat
    from docling.datamodel.pipeline_options import PdfPipelineOptions, RapidOcrOptions
    from docling.document_converter import DocumentConverter, PdfFormatOption

    opts = PdfPipelineOptions()
    opts.do_ocr = force_ocr
    opts.do_table_structure = True
    opts.ocr_options = RapidOcrOptions(force_full_page_ocr=force_ocr)
    opts.accelerator_options = AcceleratorOptions(
        device={"cuda": AcceleratorDevice.CUDA, "cpu": AcceleratorDevice.CPU}.get(
            device, AcceleratorDevice.AUTO
        ),
        num_threads=4,
    )
    return DocumentConverter(format_options={InputFormat.PDF: PdfFormatOption(pipeline_options=opts)})


def alnum_count(s: str) -> int:
    return sum(c.isalnum() for c in s)


def slugify(text: str) -> str:
    s = text.lower()
    s = re.sub(r"[^\w\s-]", "", s)
    return re.sub(r"[-\s]+", "-", s).strip("-")


def convert_one(job: dict, cache: dict, device: str) -> dict:
    import fitz  # PyMuPDF

    src = Path(job["src"])
    dst = Path(job["dst"])
    t0 = time.time()
    ocr_pages, n_pages, ref_alnum = [], None, None

    if src.suffix.lower() == ".pdf":
        with fitz.open(src) as pdf:
            n_pages = len(pdf)
            ref_alnum = sum(alnum_count(p.get_text()) for p in pdf)
            for i, p in enumerate(pdf, 1):
                suspect, _ = page_is_suspect(p)
                if suspect:
                    ocr_pages.append(i)

    force_ocr = bool(ocr_pages)

    if force_ocr not in cache:
        cache[force_ocr] = build_converter(force_ocr, device)

    doc = cache[force_ocr].convert(str(src)).document

    if n_pages is not None:
        parts = [
            f"<!-- page {n} -->\n\n{doc.export_to_markdown(page_no=n).strip()}"
            for n in sorted(doc.pages.keys())
        ]
        body = "\n\n".join(parts)
        n_markers = len(re.findall(r"<!-- page \d+ -->", body))
    else:
        body = doc.export_to_markdown().strip()
        n_markers = None

    # Validação pós-conversão
    problems = []
    if n_pages is not None and n_markers != n_pages:
        problems.append(f"marcadores={n_markers} paginas={n_pages}")
    if n_pages is not None and not force_ocr and ref_alnum and ref_alnum > 200:
        out_alnum = alnum_count(re.sub(r"<!-- [^>]*-->", "", body))
        if out_alnum / ref_alnum < OCR_MIN_ALNUM_RATIO:
            problems.append(f"alnum_docling={out_alnum / ref_alnum:.0%} do get_text")
    if not re.sub(r"<!-- [^>]*-->|\s", "", body):
        problems.append("saida vazia")

    status = "suspeito" if problems else "ok"

    # Metadados do manifesto original (se disponível)
    meta = job.get("meta", {})
    resource_url = meta.get("url", "")
    slug_id = slugify(src.stem)
    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    front = (
        "---\n"
        "type: Fonte\n"
        f"title: \"{src.stem}\"\n"
        f"status: draft\n"
        f"pages: {n_pages if n_pages is not None else 'null'}\n"
        f"ocr_forced: {str(force_ocr).lower()}\n"
        f"ocr_pages: {ocr_pages}\n"
        f"conversion_status: {status}\n"
        f"generated:\n"
        f"  by: docling-gpu\n"
        f"  at: {now_iso}\n"
        "sources:\n"
        f"  - id: \"{slug_id}\"\n"
        f"    resource: \"{resource_url}\"\n"
        f"    local_path: \"raw/{job['rel']}\"\n"
        f"    sha256: \"{job['sha256']}\"\n"
        "---\n\n"
    )

    dst.parent.mkdir(parents=True, exist_ok=True)
    tmp = dst.with_suffix(".md.tmp")
    tmp.write_text(front + body + "\n", encoding="utf-8")
    tmp.replace(dst)

    return {
        "rel": job["rel"],
        "sha256": job["sha256"],
        "status": status,
        "pages": n_pages or "",
        "ocr_forced": force_ocr,
        "ocr_pages": " ".join(map(str, ocr_pages)),
        "seconds": round(time.time() - t0, 1),
        "detail": "; ".join(problems),
    }


def worker_main(conn, device):
    cache = {}
    while True:
        job = conn.recv()
        if job is None:
            break
        try:
            conn.send(convert_one(job, cache, device))
        except Exception as e:
            conn.send({
                "rel": job["rel"],
                "sha256": job["sha256"],
                "status": "erro",
                "pages": "",
                "ocr_forced": "",
                "ocr_pages": "",
                "seconds": "",
                "detail": f"{type(e).__name__}: {e}"[:300] + " | " + traceback.format_exc()[-200:].replace("\n", " "),
            })


# --------------------------------------------------------------------------- Main --
def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def load_raw_manifest() -> dict:
    rows = {}
    if MANIFEST_FILE.exists():
        with MANIFEST_FILE.open(newline="", encoding="utf-8") as f:
            for r in csv.DictReader(f):
                lp = r.get("local_path", "")
                if lp.startswith("raw/"):
                    rel = lp[4:]
                    rows[rel] = r
    return rows


def load_conversion_manifest(path: Path) -> dict:
    rows = {}
    if path.exists():
        with path.open(newline="", encoding="utf-8") as f:
            for r in csv.DictReader(f):
                rows[r["rel"]] = r
    return rows


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--raw", default="raw", help="pasta de origem (padrão: raw)")
    ap.add_argument("--out", default="raw-md", help="pasta de saída (padrão: raw-md)")
    ap.add_argument("--device", default="cuda", choices=["cuda", "cpu", "auto"])
    ap.add_argument("--timeout", type=int, default=300, help="segundos por arquivo (padrão: 300s)")
    ap.add_argument("--limit", type=int, default=0, help="processa no máximo N arquivos")
    ap.add_argument("--only", default="", help="só caminhos que contenham este texto")
    ap.add_argument("--missing-only", action="store_true", help="processa só os arquivos que não existem em raw-text/")
    args = ap.parse_args()

    raw, out = Path(args.raw), Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    manifest_path = out / "_conversion_manifest.csv"
    done = load_conversion_manifest(manifest_path)
    raw_manifest = load_raw_manifest()

    all_files = sorted(
        (p for p in raw.rglob("*")
         if p.is_file() and p.suffix.lower() in EXTS and not p.name.startswith("_")),
        key=lambda p: p.stat().st_size,
    )

    if args.missing_only:
        files = []
        for p in all_files:
            rel = p.relative_to(raw).as_posix()
            txt_equiv = (RAW_TEXT / rel).with_suffix(".txt")
            if not txt_equiv.exists():
                files.append(p)
    else:
        files = all_files

    if args.only:
        files = [p for p in files if args.only in str(p)]

    print(f"Total de arquivos elegíveis para conversão: {len(files)}")

    ctx = mp.get_context("spawn")

    def spawn():
        parent, child = ctx.Pipe()
        proc = ctx.Process(target=worker_main, args=(child, args.device), daemon=True)
        proc.start()
        return proc, parent

    def stop(proc, conn, graceful=True):
        if graceful:
            try:
                conn.send(None)
                proc.join(10)
            except Exception:
                pass
        if proc.is_alive():
            proc.terminate()
            proc.join(3)
        if proc.is_alive():
            proc.kill()

    new_file = not manifest_path.exists()
    mf = manifest_path.open("a", newline="", encoding="utf-8")
    writer = csv.DictWriter(mf, fieldnames=FIELDS)
    if new_file:
        writer.writeheader()

    proc, conn = spawn()
    processed = 0
    total = len(files)

    try:
        for i, src in enumerate(files, 1):
            rel = src.relative_to(raw).as_posix()
            dst = (out / rel).with_suffix(".md")

            meta = raw_manifest.get(rel, {})
            sha = meta.get("sha256") or sha256_of(src)

            prev = done.get(rel)
            if prev and prev["sha256"] == sha and prev["status"] in ("ok", "suspeito") and dst.exists():
                continue

            if args.limit and processed >= args.limit:
                break

            if processed and processed % RESTART_EVERY == 0:
                stop(proc, conn)
                proc, conn = spawn()

            job_payload = {
                "src": str(src),
                "dst": str(dst),
                "rel": rel,
                "sha256": sha,
                "meta": meta,
            }

            conn.send(job_payload)
            if conn.poll(args.timeout):
                try:
                    row = conn.recv()
                except EOFError:
                    row = None
            else:
                row = None

            if row is None:
                alive = proc.is_alive()
                stop(proc, conn, graceful=False)
                row = {
                    "rel": rel,
                    "sha256": sha,
                    "status": "timeout" if alive else "erro",
                    "pages": "",
                    "ocr_forced": "",
                    "ocr_pages": "",
                    "seconds": args.timeout,
                    "detail": "timeout" if alive else "worker encerrou inesperadamente",
                }
                proc, conn = spawn()

            writer.writerow(row)
            mf.flush()
            processed += 1
            print(f"[{i}/{total}] {row['status']:<8} {rel} ({row['seconds']}s) {row['detail']}", flush=True)
    finally:
        stop(proc, conn)
        mf.close()

    # Quarentena de arquivos com status diferente de 'ok'
    latest = load_conversion_manifest(manifest_path)
    bad = [r for r in latest.values() if r["status"] != "ok"]
    quarentena_path = out / "_quarentena.csv"
    with quarentena_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(bad)

    by_status = {}
    for r in latest.values():
        by_status[r["status"]] = by_status.get(r["status"], 0) + 1
    print(f"\nResumo: {by_status} | Quarentena: {len(bad)} -> {quarentena_path}")


if __name__ == "__main__":
    sys.exit(main())
