"""Testes para o Seam 2: wiki_search.py."""
import sys
from pathlib import Path
import pytest

# Add scripts directory to sys.path
SCRIPTS_DIR = Path(__file__).resolve().parent.parent / ".agents" / "skills" / "wiki-fapes" / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from build_index import index_directory
from wiki_search import (
    sanitize_fts_query,
    search_index,
    get_page_content,
    get_outline,
    get_stats,
)


def test_sanitize_fts_query():
    # Palavras simples
    assert sanitize_fts_query("bolsa mestrado") == "bolsa mestrado"
    # Aspas balanceadas mantidas como frase
    assert sanitize_fts_query('"iniciação científica" fapes') == '"iniciação científica" fapes'
    # Aspas não balanceadas corrigidas/fechadas
    sanitized = sanitize_fts_query('"termo sem fechar')
    assert '"' not in sanitized or sanitized.count('"') % 2 == 0
    # Caracteres de controle do FTS5 removidos ou escapados
    assert ":" not in sanitize_fts_query("categoria:bolsa")
    assert "*" not in sanitize_fts_query("bolsa*")
    assert "^" not in sanitize_fts_query("início^")


def test_search_index_ranking_and_filters(tmp_path):
    docs_dir = tmp_path / "raw-md"
    bolsas_dir = docs_dir / "bolsas"
    editais_dir = docs_dir / "editais"
    bolsas_dir.mkdir(parents=True)
    editais_dir.mkdir(parents=True)

    db_path = tmp_path / ".index" / "search.db"

    doc1 = bolsas_dir / "tabela-bolsas-2023.md"
    doc1.write_text("""---
title: "Tabela de Bolsas 2023"
sources:
  - sha256: "h1"
---
<!-- page 1 -->
# Valores de Bolsas
O valor da bolsa ICT é R$ 900,00 mensais.
""", encoding="utf-8")

    doc2 = editais_dir / "edital-10-2026.md"
    doc2.write_text("""---
title: "Edital 10/2026 Dr Empreendedor"
sources:
  - sha256: "h2"
---
<!-- page 1 -->
# Recursos Financeiros
O edital destina R$ 10.662.000,00 para projetos.
""", encoding="utf-8")

    index_directory(source_dir=docs_dir, db_path=db_path)

    # Busca geral
    res1 = search_index(db_path, query="900 reais ICT", limit=5)
    assert len(res1["hits"]) >= 1
    assert "tabela-bolsas-2023.md" in res1["hits"][0]["file_path"]
    assert res1["hits"][0]["start_page"] == 1
    assert "900" in res1["hits"][0]["snippet"]
    assert res1["total_chars"] <= 4000

    # Filtro de pasta
    res2 = search_index(db_path, query="projetos", pasta="editais")
    assert len(res2["hits"]) >= 1
    assert "edital-10-2026.md" in res2["hits"][0]["file_path"]

    res_vazio = search_index(db_path, query="projetos", pasta="bolsas")
    assert len(res_vazio["hits"]) == 0

    # Filtro de ano
    res_ano = search_index(db_path, query="bolsa", ano=2023)
    assert len(res_ano["hits"]) >= 1
    assert "2023" in res_ano["hits"][0]["file_path"]


def test_get_page_content(tmp_path):
    doc_path = tmp_path / "raw-md" / "doc.md"
    doc_path.parent.mkdir(parents=True)
    doc_path.write_text("""---
title: Teste
---
<!-- page 1 -->
Texto da página um.
<!-- page 2 -->
Texto da página dois.
<!-- page 3 -->
Texto da página três.
""", encoding="utf-8")

    # Lê página 2
    p2 = get_page_content(doc_path, page_num=2)
    assert "Texto da página dois." in p2
    assert "Texto da página um." not in p2
    assert "Texto da página três." not in p2

    # Lê intervalo 1 a 2
    p1_2 = get_page_content(doc_path, page_num=1, to_page=2)
    assert "Texto da página um." in p1_2
    assert "Texto da página dois." in p1_2
    assert "Texto da página três." not in p1_2


def test_get_outline(tmp_path):
    doc_path = tmp_path / "raw-md" / "doc.md"
    doc_path.parent.mkdir(parents=True)
    doc_path.write_text("""---
title: Teste
---
<!-- page 1 -->
# Título 1
Texto 1.
## Subtítulo 1.1
Texto 2.
<!-- page 2 -->
# Título 2
### Seção Profunda
""", encoding="utf-8")

    outline = get_outline(doc_path)
    assert len(outline) == 4
    assert outline[0] == {"level": 1, "title": "Título 1", "page": 1}
    assert outline[1] == {"level": 2, "title": "Subtítulo 1.1", "page": 1}
    assert outline[2] == {"level": 1, "title": "Título 2", "page": 2}
    assert outline[3] == {"level": 3, "title": "Seção Profunda", "page": 2}


def test_get_stats(tmp_path):
    db_path = tmp_path / ".index" / "search.db"
    docs_dir = tmp_path / "raw-md"
    docs_dir.mkdir(parents=True)
    doc = docs_dir / "a.md"
    doc.write_text("# A\nTexto sem pagina.", encoding="utf-8")

    index_directory(source_dir=docs_dir, db_path=db_path)
    stats = get_stats(db_path)
    assert stats["total_files"] == 1
    assert stats["no_page_files"] == 1
    assert stats["total_chunks"] >= 1
    assert stats["db_size_bytes"] > 0
