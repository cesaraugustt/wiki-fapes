#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["pymupdf"]
# ///
"""Extrai texto de raw/ para raw-text/ (derivado, fora do git).

  uv run tools/extract.py [--force] [PREFIXO]
  uv run tools/extract.py --ocr [PREFIXO]     OCR só nos PDFs que saíram sem texto (requer ocrmypdf)

PDFs viram texto com marcadores `[p. N]` no início de cada página, para facilitar
o localizador das notas de rodapé. DOCX e XLSX são lidos só com a biblioteca padrão.
PDFs sem texto (digitalizados) são listados no final: precisam de OCR.
"""
import argparse
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
from html.parser import HTMLParser
from pathlib import Path
from xml.etree import ElementTree as ET

import pymupdf

ROOT = Path(__file__).resolve().parent.parent
RAW, OUT = ROOT / "raw", ROOT / "raw-text"
W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
S = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
A = "{http://schemas.openxmlformats.org/drawingml/2006/main}"


def _extract_openxml_paras(root, ns_uri):
    paras = ("".join(t.text or "" for t in p.iter(f"{ns_uri}t")) for p in root.iter(f"{ns_uri}p"))
    return [p for p in paras if p.strip()]


def pdf_text(path):
    pages = []
    with pymupdf.open(path) as doc:
        for i, page in enumerate(doc, 1):
            pages.append(f"[p. {i}]\n{page.get_text().strip()}")
    return "\n\n".join(pages)


def docx_text(path):
    with zipfile.ZipFile(path) as z:
        root = ET.fromstring(z.read("word/document.xml"))
    return "\n".join(_extract_openxml_paras(root, W))


def xlsx_text(path):
    with zipfile.ZipFile(path) as z:
        shared = []
        if "xl/sharedStrings.xml" in z.namelist():
            sst = ET.fromstring(z.read("xl/sharedStrings.xml"))
            shared = ["".join(t.text or "" for t in si.iter(f"{S}t")) for si in sst.iter(f"{S}si")]
        out = []
        sheet_files = [n for n in z.namelist() if re.match(r"xl/worksheets/sheet\d+\.xml", n)]
        sheet_files.sort(key=lambda n: int(re.findall(r"\d+", n)[-1]) if re.findall(r"\d+", n) else 0)
        for name in sheet_files:
            out.append(f"[{name.rsplit('/', 1)[1]}]")
            for row in ET.fromstring(z.read(name)).iter(f"{S}row"):
                cells = []
                for c in row.iter(f"{S}c"):
                    t = c.get("t")
                    val = None
                    if t == "s":
                        v = c.find(f"{S}v")
                        if v is not None and v.text and v.text.isdigit():
                            idx = int(v.text)
                            if 0 <= idx < len(shared):
                                val = shared[idx]
                    elif t == "inlineStr":
                        val = "".join(elem.text or "" for elem in c.iter(f"{S}t"))
                    else:
                        v = c.find(f"{S}v")
                        if v is not None and v.text is not None:
                            val = v.text
                    if val is not None:
                        cells.append(val)
                if cells:
                    out.append("\t".join(cells))
    return "\n".join(out)


class _Text(HTMLParser):
    SKIP = frozenset({"script", "style", "noscript", "nav", "header", "footer", "head", "svg"})
    BLOCK = frozenset({"p", "div", "br", "li", "tr", "h1", "h2", "h3", "h4", "h5", "h6", "section", "article"})

    def __init__(self):
        super().__init__()
        self.out, self.skip, self.href = [], 0, None

    def handle_starttag(self, tag, attrs):
        if tag in self.SKIP:
            self.skip += 1
        if tag in self.BLOCK:
            self.out.append("\n")
        if tag == "a":
            self.href = dict(attrs).get("href")

    def handle_endtag(self, tag):
        if tag in self.SKIP and self.skip:
            self.skip -= 1
        if tag == "a":
            if self.href and not self.skip and not self.href.startswith(("#", "javascript")):
                self.out.append(f" <{self.href}>")
            self.href = None

    def handle_data(self, data):
        if not self.skip:
            self.out.append(data)


def html_text(path):
    p = _Text()
    p.feed(Path(path).read_text(encoding="utf-8", errors="replace"))
    lines = (" ".join(l.split()) for l in "".join(p.out).splitlines())
    return "\n".join(l for l in lines if l)


def pptx_text(path):
    with zipfile.ZipFile(path) as z:
        slides = sorted((n for n in z.namelist() if re.match(r"ppt/slides/slide\d+\.xml", n)),
                        key=lambda n: int(re.findall(r"\d+", n)[-1]))
        out = []
        for i, n in enumerate(slides, 1):
            root = ET.fromstring(z.read(n))
            paras = _extract_openxml_paras(root, A)
            out.append(f"[slide {i}]\n" + "\n".join(paras))
    return "\n\n".join(out)


EXTRACTORS = {".pdf": pdf_text, ".docx": docx_text, ".xlsx": xlsx_text,
              ".html": html_text, ".pptx": pptx_text}


def is_empty(text):
    return len(re.sub(r"\[p\. \d+\]|\s", "", text)) < 50


def ocr_text(path):
    """OCR via ocrmypdf (tesseract, português). Não altera o original: só lê o texto do sidecar."""
    if not shutil.which("ocrmypdf"):
        raise RuntimeError("ocrmypdf não instalado")
    with tempfile.TemporaryDirectory() as tmp:
        side = Path(tmp) / "side.txt"
        try:
            subprocess.run(["ocrmypdf", "--force-ocr", "-l", "por", "--sidecar", str(side), str(path),
                            str(Path(tmp) / "out.pdf")], check=True, capture_output=True)
        except subprocess.CalledProcessError as e:
            err = e.stderr.decode("utf-8", errors="replace").strip() if e.stderr else str(e)
            raise RuntimeError(f"ocrmypdf falhou: {err}") from e
        pages = side.read_text(encoding="utf-8").split("\f")
    return "\n\n".join(f"[p. {i}]\n{p.strip()}" for i, p in enumerate(pages, 1) if p.strip() or i == 1)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("prefix", nargs="?", default="", help="só arquivos cujo caminho em raw/ começa com isto")
    ap.add_argument("--force", action="store_true", help="regerar mesmo se já existir")
    ap.add_argument("--ocr", action="store_true", help="aplicar OCR (ocrmypdf) nos PDFs extraídos sem texto")
    a = ap.parse_args()

    done = skipped = 0
    empty, failed = [], []
    for src in sorted(p for p in RAW.rglob("*") if p.is_file() and p.suffix.lower() in EXTRACTORS):
        rel = src.relative_to(RAW)
        if not rel.as_posix().startswith(a.prefix):
            continue
        dst = (OUT / rel).with_suffix(".txt")
        if a.ocr:  # só PDFs já extraídos sem texto
            if src.suffix.lower() != ".pdf" or not dst.exists() or not is_empty(dst.read_text(encoding="utf-8")):
                continue
        elif dst.exists() and not a.force:
            skipped += 1
            continue
        try:
            text = ocr_text(src) if a.ocr else EXTRACTORS[src.suffix.lower()](src)
        except Exception as e:  # noqa: BLE001 - segue para o próximo arquivo
            failed.append((rel.as_posix(), str(e)))
            continue
        if is_empty(text):
            empty.append(rel.as_posix())
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_text(text, encoding="utf-8")
        done += 1

    print(f"extraídos: {done}, já existiam: {skipped}, sem texto: {len(empty)}, erros: {len(failed)}")
    for p in empty:
        print("  sem texto (OCR?):", p)
    for p, e in failed:
        print("  erro:", p, "-", e)
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
