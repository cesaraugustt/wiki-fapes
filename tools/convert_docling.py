#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["docling", "pymupdf", "pyyaml", "easyocr", "onnxruntime"]
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
    uv run tools/convert_docling.py --retry-failed
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
RESTART_EVERY = 15          # recria cada worker a cada N arquivos para purgar VRAM/RAM
OCR_MIN_ALNUM_RATIO = 0.80  # proporção mínima Docling / PyMuPDF get_text (calibrado para descartes de cabeçalho/rodapé repetido)

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
    """Detecta se uma página tem camada de texto corrompida, vazia ou apenas carimbos digitais."""
    text = page.get_text()
    s = re.sub(r"\s", "", text)
    if len(s) < 25:
        # Sem camada de texto: suspeita se tiver imagens ou desenhos vetoriais
        has_visual = bool(page.get_images()) or len(page.get_drawings()) > 10
        return has_visual, "sem_texto_com_visual" if has_visual else "sem_texto"

    # Carimbos/watermarks conhecidos que disfarçam páginas escaneadas ou desenhadas
    # Ex: 'Docusign Envelope ID', carimbos do DIO, cabeçalho de assinatura digital
    clean_text = text.lower()
    is_mostly_stamp = (
        "docusign envelope id" in clean_text
        or "assinado digitalmente pelo dio" in clean_text
        or "e-docs - documento original" in clean_text
    ) and len(s) < 300
    if is_mostly_stamp:
        has_visual = bool(page.get_images()) or len(page.get_drawings()) > 20
        if has_visual:
            return True, "carimbo_com_visual_sem_corpo"

    # Muitas curvas vetoriais e pouco texto nativo (típico de páginas renderizadas como paths no DIO)
    if len(page.get_drawings()) > 100 and len(s) < 500:
        return True, "vetores_sem_texto_suficiente"

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
    from docling.datamodel.pipeline_options import EasyOcrOptions, OcrMode, PdfPipelineOptions
    from docling.document_converter import DocumentConverter, PdfFormatOption

    opts = PdfPipelineOptions()
    opts.do_ocr = force_ocr
    opts.do_table_structure = True
    ocr_options = EasyOcrOptions(lang=["pt", "en"])
    if force_ocr:
        ocr_options.mode = OcrMode.FULL_PAGE
    opts.ocr_options = ocr_options
    opts.accelerator_options = AcceleratorOptions(
        device={"cuda": AcceleratorDevice.CUDA, "cpu": AcceleratorDevice.CPU}.get(
            device, AcceleratorDevice.AUTO
        ),
        num_threads=4,
    )
    from docling.backend.pypdfium2_backend import PyPdfiumDocumentBackend

    pdf_format_kwargs = {"pipeline_options": opts}
    if force_ocr:
        pdf_format_kwargs["backend"] = PyPdfiumDocumentBackend

    return DocumentConverter(format_options={InputFormat.PDF: PdfFormatOption(**pdf_format_kwargs)})


def alnum_count(s: str) -> int:
    return sum(c.isalnum() for c in s)


def slugify(text: str) -> str:
    s = text.lower()
    s = re.sub(r"[^\w\s-]", "", s)
    return re.sub(r"[-\s]+", "-", s).strip("-")


def convert_one(job: dict, cache: dict, device: str) -> dict:
    import pymupdf as fitz

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

    def run_conversion(with_ocr: bool):
        if with_ocr not in cache:
            cache[with_ocr] = build_converter(with_ocr, device)
        d = cache[with_ocr].convert(str(src)).document
        if n_pages is not None:
            parts = [
                f"<!-- page {n} -->\n\n{d.export_to_markdown(page_no=n).strip()}"
                for n in sorted(d.pages.keys())
            ]
            b = "\n\n".join(parts)
            markers = len(re.findall(r"<!-- page \d+ -->", b))
        else:
            b = d.export_to_markdown().strip()
            markers = None
        return b, markers

    body, n_markers = run_conversion(force_ocr)

    def validate_body(b: str, markers: int | None, with_ocr: bool) -> list[str]:
        probs = []
        if n_pages is not None and markers != n_pages:
            probs.append(f"marcadores={markers} paginas={n_pages}")
        if n_pages is not None and not with_ocr and ref_alnum and ref_alnum > 200:
            out_alnum = alnum_count(re.sub(r"<!-- [^>]*-->", "", b))
            if out_alnum / ref_alnum < OCR_MIN_ALNUM_RATIO:
                probs.append(f"alnum_docling={out_alnum / ref_alnum:.0%} do get_text")
        if not re.sub(r"<!-- [^>]*-->|\s", "", b):
            probs.append("saida vazia")
        return probs

    problems = validate_body(body, n_markers, force_ocr)

    # Fallback automático: se conversão sem OCR falhou ou perdeu conteúdo essencial, retenta com EasyOCR
    if problems and not force_ocr and src.suffix.lower() == ".pdf":
        fallback_body, fallback_markers = run_conversion(True)
        fallback_problems = validate_body(fallback_body, fallback_markers, True)
        # Se o fallback resolveu ou melhorou a extração
        if not fallback_problems or ("saida vazia" in problems and "saida vazia" not in fallback_problems):
            force_ocr = True
            ocr_pages = list(range(1, (n_pages or 1) + 1))
            body, n_markers, problems = fallback_body, fallback_markers, fallback_problems

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


def worker_main(conn, device: str, worker_id: int = 0):
    cache = {}
    while True:
        try:
            job = conn.recv()
        except (EOFError, KeyboardInterrupt):
            break
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
                "detail": f"[w{worker_id}] {type(e).__name__}: {e}"[:300] + " | " + traceback.format_exc()[-200:].replace("\n", " "),
            })


# --------------------------------------------------------------------------- Main --
class WorkerSlot:
    def __init__(self, slot_id: int, ctx, device: str):
        self.slot_id = slot_id
        self.ctx = ctx
        self.device = device
        self.proc = None
        self.conn = None
        self.active_job = None
        self.t_start = 0.0
        self.jobs_done = 0
        self.spawn()

    def spawn(self):
        self.stop(graceful=False)
        parent, child = self.ctx.Pipe()
        self.proc = self.ctx.Process(
            target=worker_main,
            args=(child, self.device, self.slot_id),
            daemon=True,
        )
        self.proc.start()
        self.conn = parent
        self.active_job = None
        self.t_start = 0.0

    def stop(self, graceful=True):
        if self.conn is not None:
            if graceful:
                try:
                    self.conn.send(None)
                except Exception:
                    pass
        if self.proc is not None:
            if graceful:
                self.proc.join(timeout=3)
            if self.proc.is_alive():
                self.proc.terminate()
                self.proc.join(timeout=2)
            if self.proc.is_alive():
                self.proc.kill()
                self.proc.join(timeout=1)
            self.proc = None
        if self.conn is not None:
            try:
                self.conn.close()
            except Exception:
                pass
            self.conn = None


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
    ap.add_argument("--workers", type=int, default=2, help="número de workers paralelos (padrão: 2; máx recomendado: 2 em GPU 8GB)")
    ap.add_argument("--timeout", type=int, default=600, help="segundos por arquivo (padrão: 600s)")
    ap.add_argument("--limit", type=int, default=0, help="processa no máximo N arquivos")
    ap.add_argument("--only", default="", help="só caminhos que contenham este texto")
    ap.add_argument("--missing-only", action="store_true", help="processa só os arquivos que não existem em raw-text/")
    ap.add_argument("--retry-failed", action="store_true", help="reprocessa apenas arquivos com status diferente de 'ok' (erros e suspeitos)")
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
    elif args.retry_failed:
        files = [
            p for p in all_files
            if p.relative_to(raw).as_posix() not in done or done[p.relative_to(raw).as_posix()]["status"] != "ok"
        ]
    else:
        files = all_files

    if args.only:
        files = [p for p in files if args.only in str(p)]

    # Prepara lista de jobs pendentes
    jobs = []
    for src in files:
        rel = src.relative_to(raw).as_posix()
        dst = (out / rel).with_suffix(".md")
        meta = raw_manifest.get(rel, {})
        sha = meta.get("sha256") or sha256_of(src)

        prev = done.get(rel)
        if not args.retry_failed and prev and prev["sha256"] == sha and prev["status"] == "ok" and dst.exists():
            continue

        jobs.append({
            "src": str(src),
            "dst": str(dst),
            "rel": rel,
            "sha256": sha,
            "meta": meta,
        })
        if args.limit and len(jobs) >= args.limit:
            break

    total_jobs = len(jobs)
    num_workers = max(1, args.workers)
    print(f"Total de arquivos elegíveis para conversão: {total_jobs} | Workers: {num_workers} ({args.device})")

    if total_jobs == 0:
        return 0

    ctx = mp.get_context("spawn")
    new_file = not manifest_path.exists()
    mf = manifest_path.open("a", newline="", encoding="utf-8")
    writer = csv.DictWriter(mf, fieldnames=FIELDS)
    if new_file:
        writer.writeheader()

    slots = [WorkerSlot(i, ctx, args.device) for i in range(num_workers)]
    job_idx = 0
    processed = 0

    try:
        while processed < total_jobs:
            # 1. Aloca jobs para slots livres
            for slot in slots:
                if slot.active_job is None and job_idx < total_jobs:
                    if slot.jobs_done >= RESTART_EVERY:
                        slot.spawn()
                        slot.jobs_done = 0
                    job = jobs[job_idx]
                    job_idx += 1
                    slot.active_job = job
                    slot.t_start = time.time()
                    try:
                        slot.conn.send(job)
                    except Exception:
                        slot.spawn()
                        slot.conn.send(job)

            # 2. Monitora slots ativos
            any_busy = False
            for slot in slots:
                if slot.active_job is None:
                    continue
                any_busy = True
                rel = slot.active_job["rel"]
                sha = slot.active_job["sha256"]

                data_ready = False
                try:
                    data_ready = slot.conn.poll(0.05)
                except Exception:
                    data_ready = False

                if data_ready:
                    try:
                        row = slot.conn.recv()
                    except EOFError:
                        row = None

                    if row is None:
                        alive = slot.proc.is_alive() if slot.proc else False
                        slot.stop(graceful=False)
                        row = {
                            "rel": rel,
                            "sha256": sha,
                            "status": "erro",
                            "pages": "",
                            "ocr_forced": "",
                            "ocr_pages": "",
                            "seconds": round(time.time() - slot.t_start, 1),
                            "detail": f"[w{slot.slot_id}] worker encerrou inesperadamente (alive={alive})",
                        }
                        slot.spawn()
                        slot.jobs_done = 0
                    else:
                        slot.jobs_done += 1

                    slot.active_job = None
                    writer.writerow(row)
                    mf.flush()
                    processed += 1
                    w_tag = f"[w{slot.slot_id}]" if num_workers > 1 else ""
                    print(
                        f"[{processed}/{total_jobs}] {row['status']:<8} {rel} ({row['seconds']}s) {w_tag} {row['detail']}".strip(),
                        flush=True,
                    )

                elif time.time() - slot.t_start > args.timeout:
                    alive = slot.proc.is_alive() if slot.proc else False
                    slot.stop(graceful=False)
                    row = {
                        "rel": rel,
                        "sha256": sha,
                        "status": "timeout" if alive else "erro",
                        "pages": "",
                        "ocr_forced": "",
                        "ocr_pages": "",
                        "seconds": args.timeout,
                        "detail": f"[w{slot.slot_id}] timeout após {args.timeout}s",
                    }
                    slot.spawn()
                    slot.jobs_done = 0
                    slot.active_job = None
                    writer.writerow(row)
                    mf.flush()
                    processed += 1
                    w_tag = f"[w{slot.slot_id}]" if num_workers > 1 else ""
                    print(
                        f"[{processed}/{total_jobs}] {row['status']:<8} {rel} ({row['seconds']}s) {w_tag} {row['detail']}".strip(),
                        flush=True,
                    )

            if not any_busy and job_idx >= total_jobs:
                break
            time.sleep(0.02)
    finally:
        for slot in slots:
            slot.stop(graceful=True)
        mf.close()

    # Quarentena e consolidação do manifesto sem duplicatas
    latest = load_conversion_manifest(manifest_path)
    with manifest_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        for rel_key in sorted(latest.keys()):
            w.writerow(latest[rel_key])

    bad = [r for r in latest.values() if r["status"] != "ok"]
    quarentena_path = out / "_quarentena.csv"
    with quarentena_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(bad)

    by_status = {}
    for r in latest.values():
        by_status[r["status"]] = by_status.get(r["status"], 0) + 1
    print(f"\nResumo consolidado: {by_status} | Quarentena: {len(bad)} -> {quarentena_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
