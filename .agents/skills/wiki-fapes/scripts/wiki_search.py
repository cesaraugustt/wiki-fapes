#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["pyyaml"]
# ///
"""CLI de busca e inspeção lexical ponderada (SQLite FTS5) no acervo FAPES."""

from __future__ import annotations

import argparse
import os
import re
import sqlite3
import sys
from pathlib import Path
from typing import Any


def sanitize_fts_query(raw_query: str) -> str:
    """Higieniza e escapa a consulta para FTS5, preservando frases exatas entre aspas."""
    raw = raw_query.strip()
    if not raw:
        return ""

    # Se houver aspas ímpares, fecha a última aspa ou remove
    if raw.count('"') % 2 != 0:
        raw = raw.replace('"', " ")

    parts: list[str] = []
    # Encontra frases entre aspas e termos soltos
    tokens = re.findall(r'("[^"]+"|\S+)', raw)

    reserved = {"AND", "OR", "NOT", "NEAR"}

    for token in tokens:
        if token.startswith('"') and token.endswith('"'):
            # Frase entre aspas: remove aspas internas e caracteres de controle do FTS5
            clean_phrase = re.sub(r'[*^:{}()~"]', ' ', token[1:-1]).strip()
            if clean_phrase:
                parts.append(f'"{clean_phrase}"')
        else:
            # Termo solto: substitui pontuação por espaço para não quebrar FTS5 (ex: 10/2026 -> 10 2026)
            clean_term = re.sub(r'[^\w\s]', ' ', token).strip()
            for sub_term in clean_term.split():
                if sub_term and sub_term.upper() not in reserved:
                    parts.append(sub_term)

    return " ".join(parts)


def format_snippet(content: str, query: str, max_chars: int = 400) -> str:
    """Gera um trecho contextual de ~max_chars centrado nos termos da consulta."""
    clean_text = " ".join(content.split())
    if len(clean_text) <= max_chars:
        return clean_text

    # Extrai palavras da query para busca
    words = re.findall(r"\w+", query.lower())
    match_pos = -1
    for w in words:
        if len(w) >= 3:
            pos = clean_text.lower().find(w)
            if pos != -1:
                match_pos = pos
                break

    if match_pos == -1:
        # Se não achou palavra exata, pega o início
        return clean_text[:max_chars].rstrip() + "..."

    half = max_chars // 2
    start = max(0, match_pos - half)
    end = min(len(clean_text), match_pos + half)

    # Ajusta para não cortar palavras no meio
    if start > 0:
        first_space = clean_text.find(" ", start)
        if first_space != -1 and first_space < start + 20:
            start = first_space + 1
    if end < len(clean_text):
        last_space = clean_text.rfind(" ", 0, end)
        if last_space != -1 and last_space > end - 20:
            end = last_space

    prefix = "..." if start > 0 else ""
    suffix = "..." if end < len(clean_text) else ""
    return prefix + clean_text[start:end].strip() + suffix


def search_index(
    db_path: Path,
    query: str,
    limit: int = 8,
    pasta: str | None = None,
    ano: int | None = None,
) -> dict[str, Any]:
    """Executa busca ponderada no FTS5 e retorna resultados formatados."""
    if not db_path.exists():
        return {"hits": [], "total_chars": 0, "error": f"Índice não encontrado em {db_path}"}

    sanitized = sanitize_fts_query(query)
    if not sanitized:
        return {"hits": [], "total_chars": 0, "error": "Consulta vazia ou inválida após sanitização."}

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    where_clauses = ["chunks_fts MATCH ?"]
    params: list[Any] = [sanitized]

    if pasta:
        where_clauses.append("(f.pasta = ? OR f.path LIKE ?)")
        params.extend([pasta, f"{pasta}/%"])

    if ano is not None:
        where_clauses.append("f.year = ?")
        params.append(ano)

    sql = f"""
    SELECT
        f.path,
        c.start_page,
        c.end_page,
        c.heading_path,
        c.content,
        bm25(chunks_fts, 1.0, 5.0, 10.0) as rank
    FROM chunks_fts
    JOIN chunks c ON c.id = chunks_fts.rowid
    JOIN files f ON f.id = c.file_id
    WHERE {" AND ".join(where_clauses)}
    ORDER BY rank
    LIMIT ?
    """
    params.append(limit)

    hits: list[dict[str, Any]] = []
    total_chars = 0

    try:
        rows = cursor.execute(sql, params).fetchall()
        # Se não encontrou resultados e a busca tem múltiplos termos sem OR explícito, tenta OR
        if not rows and " OR " not in sanitized:
            tokens = re.findall(r'("[^"]+"|\S+)', sanitized)
            if len(tokens) > 1:
                or_query = " OR ".join(tokens)
                or_params = [or_query] + params[1:]
                rows = cursor.execute(sql, or_params).fetchall()
                if rows:
                    sanitized = or_query
    except sqlite3.OperationalError as e:
        conn.close()
        return {"hits": [], "total_chars": 0, "error": f"Erro SQLite FTS5: {e}"}

    conn.close()

    for path, start_page, end_page, heading_path, content, rank in rows:
        snippet = format_snippet(content, query, max_chars=400)
        hit = {
            "file_path": path,
            "start_page": start_page,
            "end_page": end_page,
            "heading_path": heading_path,
            "snippet": snippet,
            "rank": rank,
        }
        hits.append(hit)

        # Estima caracteres formatados
        chars = len(path) + len(str(heading_path or "")) + len(snippet) + 50
        total_chars += chars

    return {
        "hits": hits,
        "total_chars": total_chars,
        "query": sanitized,
    }


def resolve_file_path(file_path_str: str, base_dir: Path | None = None) -> Path:
    """Resolve caminho para o arquivo original em raw-md."""
    p = Path(file_path_str)
    if p.is_file():
        return p

    # Tenta prefixos comuns
    candidates = [
        p,
        Path("raw-md") / p,
        Path.cwd() / p,
        Path.cwd() / "raw-md" / p,
    ]
    if base_dir:
        candidates.extend([
            base_dir / p,
            base_dir / "raw-md" / p,
        ])

    for c in candidates:
        if c.is_file():
            return c

    # Se passou sem o .md, tenta com .md
    if not p.suffix:
        for c in candidates:
            with_md = c.with_suffix(".md")
            if with_md.is_file():
                return with_md

    return p


def get_page_content(file_path: Path | str, page_num: int, to_page: int | None = None) -> str:
    """Extrai o texto original correspondente à(s) página(s) solicitada(s)."""
    p = resolve_file_path(str(file_path))
    if not p.is_file():
        return f"Erro: Arquivo não encontrado: {file_path}"

    text = p.read_text(encoding="utf-8", errors="replace")
    if "<!-- page " not in text:
        return f"Aviso: O arquivo '{p.name}' não contém marcadores de página (<!-- page N -->).\n\nConteúdo completo:\n\n{text}"

    if to_page is None:
        to_page = page_num

    pages_found: list[tuple[int, int]] = []  # (page_num, start_index)
    for m in re.finditer(r"<!--\s*page\s+(\d+)\s*-->", text):
        num = int(m.group(1))
        pages_found.append((num, m.end()))

    if not pages_found:
        return f"Nenhum marcador de página encontrado em {p.name}."

    # Encontra o trecho correspondente
    target_start = -1
    target_end = len(text)

    for i, (p_num, start_idx) in enumerate(pages_found):
        if p_num == page_num and target_start == -1:
            target_start = start_idx
        if p_num > to_page:
            target_end = pages_found[i][1] - len(f"<!-- page {p_num} -->")
            break

    if target_start == -1:
        max_page = pages_found[-1][0]
        return f"Página {page_num} não encontrada em {p.name}. O documento vai até a página {max_page}."

    page_text = text[target_start:target_end].strip()
    return page_text


def get_outline(file_path: Path | str) -> list[dict[str, Any]]:
    """Gera a árvore de cabeçalhos markdown com respectivos números de página."""
    p = resolve_file_path(str(file_path))
    if not p.is_file():
        return []

    lines = p.read_text(encoding="utf-8", errors="replace").splitlines()
    outline: list[dict[str, Any]] = []
    current_page: int | None = None

    for line in lines:
        pm = re.match(r"^\s*<!--\s*page\s+(\d+)\s*-->", line)
        if pm:
            current_page = int(pm.group(1))
            continue

        hm = re.match(r"^(#{1,6})\s+(.+?)\s*$", line)
        if hm:
            level = len(hm.group(1))
            title = hm.group(2).strip()
            outline.append({
                "level": level,
                "title": title,
                "page": current_page,
            })

    return outline


def get_stats(db_path: Path) -> dict[str, Any]:
    """Retorna estatísticas do banco de busca SQLite."""
    if not db_path.exists():
        return {"error": f"Índice {db_path} não encontrado."}

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    total_files = cursor.execute("SELECT COUNT(*) FROM files").fetchone()[0]
    total_chunks = cursor.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]
    no_page_files = cursor.execute("SELECT COUNT(*) FROM files WHERE has_pages = 0").fetchone()[0]
    conn.close()

    db_size = db_path.stat().st_size

    return {
        "total_files": total_files,
        "total_chunks": total_chunks,
        "no_page_files": no_page_files,
        "db_size_bytes": db_size,
        "db_size_mb": round(db_size / (1024 * 1024), 2),
    }


def main():
    parser = argparse.ArgumentParser(description="CLI de busca e consulta FAPES")
    parser.add_argument("--db", default=".index/search.db", type=Path, help="Caminho do banco SQLite")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Subcomando search
    p_search = subparsers.add_parser("search", help="Busca no acervo FTS5")
    p_search.add_argument("query", type=str, help="Termo ou frase de busca")
    p_search.add_argument("-k", "--limit", default=8, type=int, help="Número de resultados")
    p_search.add_argument("--pasta", type=str, default=None, help="Filtrar por pasta (bolsas, editais, etc.)")
    p_search.add_argument("--ano", type=int, default=None, help="Filtrar por ano")

    # Subcomando page
    p_page = subparsers.add_parser("page", help="Exibe texto original de página(s)")
    p_page.add_argument("arquivo", type=str, help="Caminho do arquivo em raw-md")
    p_page.add_argument("pagina", type=int, help="Número da página")
    p_page.add_argument("--ate", type=int, default=None, help="Página final do intervalo")

    # Subcomando outline
    p_outline = subparsers.add_parser("outline", help="Lista cabeçalhos e páginas do documento")
    p_outline.add_argument("arquivo", type=str, help="Caminho do arquivo em raw-md")

    # Subcomando stats
    subparsers.add_parser("stats", help="Exibe estatísticas do índice")

    args = parser.parse_args()

    if args.command == "search":
        res = search_index(
            db_path=args.db,
            query=args.query,
            limit=args.limit,
            pasta=args.pasta,
            ano=args.ano,
        )
        if "error" in res:
            print(f"Erro: {res['error']}", file=sys.stderr)
            sys.exit(1)

        hits = res["hits"]
        if not hits:
            print(f"Nenhum resultado encontrado para: '{args.query}'")
            return

        print(f"Encontrados {len(hits)} resultados para '{res['query']}':\n")
        output_buffer: list[str] = []
        for i, h in enumerate(hits, 1):
            pages_str = f"p. {h['start_page']}" if h["start_page"] else "(sem p.)"
            if h["end_page"] and h["end_page"] != h["start_page"]:
                pages_str = f"p. {h['start_page']}-{h['end_page']}"

            hpath = f" [{h['heading_path']}]" if h["heading_path"] else ""
            block = (
                f"{i}. raw-md/{h['file_path']}, {pages_str}{hpath}\n"
                f"   \"{h['snippet']}\"\n"
            )
            output_buffer.append(block)

        full_output = "\n".join(output_buffer)
        # Limita saída total a ~4.000 caracteres
        if len(full_output) > 4000:
            full_output = full_output[:3950].rstrip() + "\n\n... [saída truncada em 4.000 caracteres]"
        print(full_output)

    elif args.command == "page":
        content = get_page_content(args.arquivo, page_num=args.pagina, to_page=args.ate)
        print(content)

    elif args.command == "outline":
        outline = get_outline(args.arquivo)
        if not outline:
            print(f"Nenhum cabeçalho encontrado em {args.arquivo}")
            return
        for item in outline:
            indent = "  " * (item["level"] - 1)
            p_str = f"(p. {item['page']})" if item["page"] else ""
            print(f"{indent}- {item['title']} {p_str}".rstrip())

    elif args.command == "stats":
        stats = get_stats(args.db)
        if "error" in stats:
            print(f"Erro: {stats['error']}", file=sys.stderr)
            sys.exit(1)
        print("--- Estatísticas do Índice FAPES ---")
        print(f"Total de arquivos indexados: {stats['total_files']}")
        print(f"Total de chunks estruturais: {stats['total_chunks']}")
        print(f"Arquivos sem marcador de página: {stats['no_page_files']}")
        print(f"Tamanho do banco: {stats['db_size_mb']} MB ({stats['db_size_bytes']} bytes)")


if __name__ == "__main__":
    main()
