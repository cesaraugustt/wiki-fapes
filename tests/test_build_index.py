"""Testes para o Seam 1: build_index.py."""
import sqlite3
import tempfile
from pathlib import Path
import pytest
import yaml

import sys
from pathlib import Path

# Add scripts directory to sys.path
SCRIPTS_DIR = Path(__file__).resolve().parent.parent / ".agents" / "skills" / "wiki-fapes" / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from build_index import (
    parse_document,
    chunk_document,
    index_directory,
    estimate_tokens,
    split_table,
)



def test_parse_frontmatter():
    sample = """---
type: Fonte
title: "Edital 10/2026"
sources:
  - sha256: "abc123hash"
---
<!-- page 1 -->
# Título Principal
Texto da página 1.
"""
    meta, body = parse_document(sample)
    assert meta["title"] == "Edital 10/2026"
    assert meta["sources"][0]["sha256"] == "abc123hash"
    assert "# Título Principal" in body


def test_chunk_document_with_headings_and_pages():
    content = """<!-- page 1 -->
# Seção 1
Conteúdo da seção 1.

<!-- page 2 -->
## Subseção 1.1
Conteúdo da subseção 1.1 na página 2.
"""
    chunks = chunk_document(content, max_tokens=1200)
    assert len(chunks) >= 2
    # Chunk 1
    assert chunks[0]["start_page"] == 1
    assert "Seção 1" in chunks[0]["heading_path"]
    # Chunk 2
    assert chunks[1]["start_page"] == 2
    assert "Seção 1 > Subseção 1.1" == chunks[1]["heading_path"] or "Subseção 1.1" in chunks[1]["heading_path"]


def test_split_table_preserves_headers():
    header = "| Col A | Col B |\n|---|---|\n"
    rows = [f"| Dado {i}A | Dado {i}B |\n" for i in range(20)]
    table_text = header + "".join(rows)

    # Force small max_tokens so it splits
    chunks = split_table(table_text, max_tokens=25)
    assert len(chunks) > 1
    for c in chunks:
        lines = c.strip().split("\n")
        assert lines[0].strip() == "| Col A | Col B |"
        assert lines[1].strip() == "|---|---|"
        assert len(lines) > 2  # Has actual data rows


def test_chunking_long_paragraphs_exceeding_limit():
    long_para1 = "Palavra " * 300  # ~300 tokens
    long_para2 = "Outra " * 300
    long_para3 = "Mais " * 300
    long_para4 = "Final " * 300
    content = f"# Artigo 1\n\n{long_para1}\n\n{long_para2}\n\n{long_para3}\n\n{long_para4}"

    # max_tokens = 500: should split into multiple chunks under the same heading
    chunks = chunk_document(content, max_tokens=500)
    assert len(chunks) >= 2
    for c in chunks:
        assert c["heading_path"] == "Artigo 1"


def test_index_incremental_and_delete(tmp_path):
    docs_dir = tmp_path / "raw-md" / "bolsas"
    docs_dir.mkdir(parents=True)
    db_path = tmp_path / ".index" / "search.db"
    db_path.parent.mkdir(parents=True)

    doc1 = docs_dir / "doc1.md"
    doc1.write_text("""---
title: "Bolsa A"
sources:
  - sha256: "hash1"
---
<!-- page 1 -->
# Regra Bolsa
Valor da bolsa é 900 reais.
""", encoding="utf-8")

    doc2 = docs_dir / "doc2.md"
    doc2.write_text("""---
title: "Bolsa B"
sources:
  - sha256: "hash2"
---
<!-- page 1 -->
# Regra Auxílio
Auxílio transporte 450 reais.
""", encoding="utf-8")

    # Primeiro index
    stats1 = index_directory(source_dir=tmp_path / "raw-md", db_path=db_path)
    assert stats1["indexed_files"] == 2
    assert stats1["total_chunks"] >= 2

    # Segundo index: incremental (nenhum arquivo modificado)
    stats2 = index_directory(source_dir=tmp_path / "raw-md", db_path=db_path)
    assert stats2["indexed_files"] == 0  # Nenhum novo indexado
    assert stats2["skipped_files"] == 2

    # Deleta doc2 e roda de novo
    doc2.unlink()
    stats3 = index_directory(source_dir=tmp_path / "raw-md", db_path=db_path)
    assert stats3["deleted_files"] == 1

    # Verifica se doc2 sumiu do SQLite e FTS5
    conn = sqlite3.connect(db_path)
    rows = conn.execute("SELECT path FROM files").fetchall()
    assert len(rows) == 1
    assert "doc1.md" in rows[0][0]

    fts_rows = conn.execute("SELECT content FROM chunks_fts WHERE chunks_fts MATCH 'transporte'").fetchall()
    assert len(fts_rows) == 0

    fts_rows1 = conn.execute("SELECT content FROM chunks_fts WHERE chunks_fts MATCH 'bolsa'").fetchall()
    assert len(fts_rows1) >= 1
    conn.close()
