#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["pymupdf"]
# ///
"""Extrai texto de raw/ para raw-text/ (derivado, fora do git).

  uv run tools/extract.py [--force] [PREFIXO]

PDFs viram texto com marcadores `[p. N]` no início de cada página, para facilitar
o localizador das notas de rodapé. DOCX e XLSX são lidos só com a biblioteca padrão.
PDFs sem texto (digitalizados) são listados no final: precisam de OCR.
"""
import argparse
import re
import sys
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

import pymupdf

ROOT = Path(__file__).resolve().parent.parent
RAW, OUT = ROOT / "raw", ROOT / "raw-text"
W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
S = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"


def pdf_text(path):
    pages = []
    with pymupdf.open(path) as doc:
        for i, page in enumerate(doc, 1):
            pages.append(f"[p. {i}]\n{page.get_text().strip()}")
    return "\n\n".join(pages)


def docx_text(path):
    with zipfile.ZipFile(path) as z:
        root = ET.fromstring(z.read("word/document.xml"))
    paras = ("".join(t.text or "" for t in p.iter(f"{W}t")) for p in root.iter(f"{W}p"))
    return "\n".join(p for p in paras if p.strip())


def xlsx_text(path):
    with zipfile.ZipFile(path) as z:
        shared = []
        if "xl/sharedStrings.xml" in z.namelist():
            sst = ET.fromstring(z.read("xl/sharedStrings.xml"))
            shared = ["".join(t.text or "" for t in si.iter(f"{S}t")) for si in sst.iter(f"{S}si")]
        out = []
        for name in sorted(n for n in z.namelist() if re.match(r"xl/worksheets/sheet\d+\.xml", n)):
            out.append(f"[{name.rsplit('/', 1)[1]}]")
            for row in ET.fromstring(z.read(name)).iter(f"{S}row"):
                cells = []
                for c in row.iter(f"{S}c"):
                    v = c.find(f"{S}v")
                    if v is None or v.text is None:
                        continue
                    cells.append(shared[int(v.text)] if c.get("t") == "s" else v.text)
                if cells:
                    out.append("\t".join(cells))
    return "\n".join(out)


EXTRACTORS = {".pdf": pdf_text, ".docx": docx_text, ".xlsx": xlsx_text}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("prefix", nargs="?", default="", help="só arquivos cujo caminho em raw/ começa com isto")
    ap.add_argument("--force", action="store_true", help="regerar mesmo se já existir")
    a = ap.parse_args()

    done = skipped = 0
    empty, failed = [], []
    for src in sorted(p for p in RAW.rglob("*") if p.is_file() and p.suffix.lower() in EXTRACTORS):
        rel = src.relative_to(RAW)
        if not rel.as_posix().startswith(a.prefix):
            continue
        dst = (OUT / rel).with_suffix(".txt")
        if dst.exists() and not a.force:
            skipped += 1
            continue
        try:
            text = EXTRACTORS[src.suffix.lower()](src)
        except Exception as e:  # noqa: BLE001 - segue para o próximo arquivo
            failed.append((rel.as_posix(), str(e)))
            continue
        if len(re.sub(r"\[p\. \d+\]|\s", "", text)) < 50:
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
