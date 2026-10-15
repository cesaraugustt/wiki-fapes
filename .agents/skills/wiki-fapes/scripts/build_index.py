#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["pyyaml"]
# ///
"""Indexador incremental estrutural em SQLite FTS5 para o acervo documental FAPES."""

from __future__ import annotations

import argparse
import hashlib
import re
import sqlite3
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml


def estimate_tokens(text: str) -> int:
    """Estimativa de tokens baseada em caracteres (~4 caracteres por token)."""
    return max(1, len(text) // 4)


def parse_document(text: str) -> tuple[dict[str, Any], str]:
    """Extrai frontmatter YAML e corpo do documento markdown."""
    if not text.startswith("---"):
        return {}, text
    m = re.match(r"^---\s*\n(.*?)\n---\s*\n?(.*)$", text, re.DOTALL)
    if not m:
        return {}, text
    try:
        data = yaml.safe_load(m.group(1))
        meta = data if isinstance(data, dict) else {}
    except yaml.YAMLError:
        meta = {}
    return meta, m.group(2)


def extract_year(path: Path, meta: dict[str, Any]) -> int | None:
    """Extrai ano do documento com base no nome do arquivo, caminho ou frontmatter."""
    match = re.search(r"\b(19\d{2}|20\d{2})\b", path.as_posix())
    if match:
        return int(match.group(1))

    for field in ("last_modified", "stale_after"):
        val = meta.get(field)
        if isinstance(val, str):
            ym = re.search(r"\b(19\d{2}|20\d{2})\b", val)
            if ym:
                return int(ym.group(1))

    gen = meta.get("generated")
    if isinstance(gen, dict) and isinstance(gen.get("at"), str):
        ym = re.search(r"\b(19\d{2}|20\d{2})\b", gen["at"])
        if ym:
            return int(ym.group(1))

    title = meta.get("title", "")
    if isinstance(title, str):
        ym = re.search(r"\b(19\d{2}|20\d{2})\b", title)
        if ym:
            return int(ym.group(1))

    return None


def split_table(table_text: str, max_tokens: int = 1200) -> list[str]:
    """Divide uma tabela markdown grande por linhas de dados preservando o cabeçalho."""
    lines = [line for line in table_text.strip().splitlines() if line.strip()]
    if len(lines) < 3:
        return [table_text]

    header_line = lines[0]
    sep_line = lines[1]
    data_rows = lines[2:]

    header_block = f"{header_line}\n{sep_line}\n"
    header_tokens = estimate_tokens(header_block)

    chunks: list[str] = []
    current_rows: list[str] = []
    current_tokens = header_tokens

    for row in data_rows:
        row_str = row + "\n"
        row_tokens = estimate_tokens(row_str)
        if current_rows and (current_tokens + row_tokens > max_tokens):
            chunk_content = header_block + "".join(current_rows)
            chunks.append(chunk_content)
            current_rows = [row_str]
            current_tokens = header_tokens + row_tokens
        else:
            current_rows.append(row_str)
            current_tokens += row_tokens

    if current_rows:
        chunks.append(header_block + "".join(current_rows))

    return chunks if chunks else [table_text]


def chunk_document(text: str, max_tokens: int = 1200) -> list[dict[str, Any]]:
    """Divide o documento markdown por cabeçalhos (#), páginas e parágrafos."""
    lines = text.splitlines(keepends=True)
    chunks: list[dict[str, Any]] = []

    current_page: int | None = None
    heading_stack: list[tuple[int, str]] = []  # (level, title)

    # Parser linear robusto
    blocks: list[dict[str, Any]] = []
    current_table: list[str] = []
    table_start_page: int | None = None
    table_end_page: int | None = None

    current_text: list[str] = []
    text_start_page: int | None = None
    text_end_page: int | None = None

    def flush_table():
        nonlocal current_table, table_start_page, table_end_page
        if current_table:
            tb_str = "".join(current_table)
            blocks.append({
                "type": "table",
                "content": tb_str,
                "start_page": table_start_page,
                "end_page": table_end_page,
            })
            current_table = []
            table_start_page = None
            table_end_page = None

    def flush_text():
        nonlocal current_text, text_start_page, text_end_page
        if current_text:
            tx_str = "".join(current_text)
            if tx_str.strip():
                blocks.append({
                    "type": "text",
                    "content": tx_str,
                    "start_page": text_start_page,
                    "end_page": text_end_page,
                })
            current_text = []
            text_start_page = None
            text_end_page = None

    for line in lines:
        # 1. Marcador de página
        pm = re.match(r"^\s*<!--\s*page\s+(\d+)\s*-->", line)
        if pm:
            current_page = int(pm.group(1))
            if current_table:
                table_end_page = current_page
            if current_text:
                text_end_page = current_page
            blocks.append({"type": "page_marker", "page": current_page})
            continue

        # 2. Cabeçalho markdown
        hm = re.match(r"^(#{1,6})\s*(.*?)\s*$", line)
        if hm:
            flush_table()
            flush_text()
            level = len(hm.group(1))
            title = hm.group(2).strip()
            if title:
                while heading_stack and heading_stack[-1][0] >= level:
                    heading_stack.pop()
                heading_stack.append((level, title))
                h_path = " > ".join(t for _, t in heading_stack)
                blocks.append({
                    "type": "heading",
                    "level": level,
                    "title": title,
                    "heading_path": h_path,
                    "page": current_page,
                })
            continue

        # 3. Linha de tabela markdown (| ... |)
        stripped = line.strip()
        if stripped.startswith("|") and stripped.endswith("|") and len(stripped) > 1:
            flush_text()
            if table_start_page is None:
                table_start_page = current_page
            table_end_page = current_page
            current_table.append(line)
            continue

        # Se estava em tabela e veio linha sem barra, fecha tabela
        if current_table:
            flush_table()

        # 4. Parágrafo / texto normal
        if not stripped:
            # Quebra de parágrafo em linha em branco
            flush_text()
            continue

        if text_start_page is None:
            text_start_page = current_page
        text_end_page = current_page
        current_text.append(line)

    flush_table()
    flush_text()

    # Agrupa blocos em chunks estruturados
    current_heading_path = ""
    current_chunk_parts: list[str] = []
    chunk_start_page: int | None = None
    chunk_end_page: int | None = None
    current_chunk_tokens = 0

    def flush_chunk():
        nonlocal current_chunk_parts, chunk_start_page, chunk_end_page, current_chunk_tokens
        if not current_chunk_parts:
            return
        body = "".join(current_chunk_parts).strip()
        if body:
            chunks.append({
                "chunk_index": len(chunks),
                "start_page": chunk_start_page,
                "end_page": chunk_end_page,
                "heading_path": current_heading_path,
                "content": body,
                "token_count": estimate_tokens(body),
            })
        current_chunk_parts = []
        chunk_start_page = None
        chunk_end_page = None
        current_chunk_tokens = 0

    for blk in blocks:
        b_type = blk["type"]

        if b_type == "page_marker":
            p = blk["page"]
            if chunk_start_page is None:
                chunk_start_page = p
            chunk_end_page = p
            continue

        if b_type == "heading":
            flush_chunk()
            current_heading_path = blk["heading_path"]
            chunk_start_page = blk["page"]
            chunk_end_page = blk["page"]
            continue

        if b_type == "table":
            t_content = blk["content"]
            t_tokens = estimate_tokens(t_content)

            if t_tokens > max_tokens:
                flush_chunk()
                sub_tables = split_table(t_content, max_tokens=max_tokens)
                for st in sub_tables:
                    chunks.append({
                        "chunk_index": len(chunks),
                        "start_page": blk["start_page"],
                        "end_page": blk["end_page"],
                        "heading_path": current_heading_path,
                        "content": st.strip(),
                        "token_count": estimate_tokens(st),
                    })
                continue
            else:
                if current_chunk_tokens + t_tokens > max_tokens:
                    flush_chunk()
                current_chunk_parts.append(t_content)
                current_chunk_tokens += t_tokens
                if chunk_start_page is None:
                    chunk_start_page = blk["start_page"]
                chunk_end_page = blk["end_page"]
                continue

        if b_type == "text":
            txt = blk["content"]
            txt_tokens = estimate_tokens(txt)

            if txt_tokens > max_tokens:
                flush_chunk()
                sub_lines = txt.splitlines(keepends=True)
                sub_buf: list[str] = []
                sub_tok = 0
                for sl in sub_lines:
                    stk = estimate_tokens(sl)
                    if sub_buf and (sub_tok + stk > max_tokens):
                        sb_content = "".join(sub_buf).strip()
                        if sb_content:
                            chunks.append({
                                "chunk_index": len(chunks),
                                "start_page": blk["start_page"],
                                "end_page": blk["end_page"],
                                "heading_path": current_heading_path,
                                "content": sb_content,
                                "token_count": estimate_tokens(sb_content),
                            })
                        sub_buf = [sl]
                        sub_tok = stk
                    else:
                        sub_buf.append(sl)
                        sub_tok += stk
                if sub_buf:
                    sb_content = "".join(sub_buf).strip()
                    if sb_content:
                        chunks.append({
                            "chunk_index": len(chunks),
                            "start_page": blk["start_page"],
                            "end_page": blk["end_page"],
                            "heading_path": current_heading_path,
                            "content": sb_content,
                            "token_count": estimate_tokens(sb_content),
                        })
                continue

            if current_chunk_parts and (current_chunk_tokens + txt_tokens > max_tokens):
                flush_chunk()

            current_chunk_parts.append(txt)
            current_chunk_tokens += txt_tokens
            if chunk_start_page is None:
                chunk_start_page = blk["start_page"]
            chunk_end_page = blk["end_page"]

    flush_chunk()
    return chunks


def init_db(db_path: Path) -> sqlite3.Connection:
    """Cria tabelas do banco SQLite e tabela virtual FTS5."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.execute("PRAGMA journal_mode = WAL;")

    conn.execute("""
    CREATE TABLE IF NOT EXISTS files (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        path TEXT UNIQUE NOT NULL,
        sha256 TEXT NOT NULL,
        title TEXT,
        year INTEGER,
        pasta TEXT,
        has_pages BOOLEAN,
        mtime REAL,
        indexed_at TEXT
    );
    """)

    conn.execute("""
    CREATE TABLE IF NOT EXISTS chunks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        file_id INTEGER NOT NULL,
        chunk_index INTEGER NOT NULL,
        start_page INTEGER,
        end_page INTEGER,
        heading_path TEXT,
        content TEXT NOT NULL,
        token_count INTEGER,
        FOREIGN KEY(file_id) REFERENCES files(id) ON DELETE CASCADE
    );
    """)

    conn.execute("""
    CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5(
        content,
        heading_path,
        doc_title,
        tokenize='unicode61 remove_diacritics 2'
    );
    """)

    conn.commit()
    return conn


def index_directory(
    source_dir: Path,
    db_path: Path,
    max_tokens: int = 1200,
    rebuild: bool = False,
) -> dict[str, Any]:
    """Indexa incrementalmente os arquivos markdown no SQLite FTS5."""
    if rebuild and db_path.exists():
        db_path.unlink()

    conn = init_db(db_path)
    cursor = conn.cursor()

    existing_files: dict[str, tuple[int, str]] = {}
    for row in cursor.execute("SELECT id, path, sha256 FROM files"):
        existing_files[row[1]] = (row[0], row[2])

    indexed_count = 0
    skipped_count = 0
    deleted_count = 0
    seen_paths: set[str] = set()

    all_md_files = sorted(source_dir.rglob("*.md"))

    for md_path in all_md_files:
        rel_path = md_path.relative_to(source_dir).as_posix()
        seen_paths.add(rel_path)

        text = md_path.read_text(encoding="utf-8", errors="replace")
        meta, body = parse_document(text)

        sha256 = ""
        sources = meta.get("sources")
        if isinstance(sources, list) and sources and isinstance(sources[0], dict):
            sha256 = sources[0].get("sha256", "")
        if not sha256:
            sha256 = hashlib.sha256(text.encode("utf-8")).hexdigest()

        if rel_path in existing_files:
            file_id, old_sha = existing_files[rel_path]
            if old_sha == sha256:
                skipped_count += 1
                continue
            cursor.execute("DELETE FROM chunks_fts WHERE rowid IN (SELECT id FROM chunks WHERE file_id = ?)", (file_id,))
            cursor.execute("DELETE FROM files WHERE id = ?", (file_id,))

        title = meta.get("title") or md_path.stem
        year = extract_year(md_path, meta)
        pasta = rel_path.split("/")[0] if "/" in rel_path else "(raiz)"
        has_pages = "<!-- page " in text
        mtime = md_path.stat().st_mtime
        indexed_at = datetime.now(timezone.utc).isoformat()

        cursor.execute(
            """
            INSERT INTO files (path, sha256, title, year, pasta, has_pages, mtime, indexed_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (rel_path, sha256, title, year, pasta, has_pages, mtime, indexed_at),
        )
        file_id = cursor.lastrowid

        chunks = chunk_document(body, max_tokens=max_tokens)
        for c in chunks:
            cursor.execute(
                """
                INSERT INTO chunks (file_id, chunk_index, start_page, end_page, heading_path, content, token_count)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (file_id, c["chunk_index"], c["start_page"], c["end_page"], c["heading_path"], c["content"], c["token_count"]),
            )
            chunk_id = cursor.lastrowid

            cursor.execute(
                """
                INSERT INTO chunks_fts (rowid, content, heading_path, doc_title)
                VALUES (?, ?, ?, ?)
                """,
                (chunk_id, c["content"], c["heading_path"], title),
            )

        indexed_count += 1
        if indexed_count % 50 == 0:
            conn.commit()

    for old_path, (old_id, _) in existing_files.items():
        if old_path not in seen_paths:
            cursor.execute("DELETE FROM chunks_fts WHERE rowid IN (SELECT id FROM chunks WHERE file_id = ?)", (old_id,))
            cursor.execute("DELETE FROM files WHERE id = ?", (old_id,))
            deleted_count += 1

    conn.commit()

    total_chunks = cursor.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]
    total_files = cursor.execute("SELECT COUNT(*) FROM files").fetchone()[0]
    no_page_files = cursor.execute("SELECT COUNT(*) FROM files WHERE has_pages = 0").fetchone()[0]

    conn.close()

    return {
        "indexed_files": indexed_count,
        "skipped_files": skipped_count,
        "deleted_files": deleted_count,
        "total_files": total_files,
        "total_chunks": total_chunks,
        "no_page_files": no_page_files,
    }


def main():
    parser = argparse.ArgumentParser(description="Indexador FTS5 para acervo FAPES")
    parser.add_argument("--source-dir", default="raw-md", type=Path, help="Diretório dos arquivos .md")
    parser.add_argument("--db", default=".index/search.db", type=Path, help="Caminho do banco SQLite")
    parser.add_argument("--max-tokens", default=1200, type=int, help="Limite de tokens por chunk")
    parser.add_argument("--rebuild", action="store_true", help="Reconstrói o índice do zero")
    args = parser.parse_args()

    start_time = time.time()
    print(f"Indexando acervo a partir de {args.source_dir}...")
    stats = index_directory(
        source_dir=args.source_dir,
        db_path=args.db,
        max_tokens=args.max_tokens,
        rebuild=args.rebuild,
    )
    elapsed = time.time() - start_time

    print(f"\n--- Estatísticas de Indexação ---")
    print(f"Arquivos indexados: {stats['indexed_files']}")
    print(f"Arquivos inalterados (pulados): {stats['skipped_files']}")
    print(f"Arquivos removidos: {stats['deleted_files']}")
    print(f"Total de arquivos no índice: {stats['total_files']}")
    print(f"Total de chunks gerados: {stats['total_chunks']}")
    print(f"Arquivos sem marcador de página: {stats['no_page_files']}")
    print(f"Tempo total: {elapsed:.2f}s")


if __name__ == "__main__":
    main()
