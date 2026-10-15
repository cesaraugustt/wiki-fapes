"""Suíte de avaliação do Skill wiki-fapes (9 casos de teste: 5 gabarito + 4 sintéticos)."""
import sys
from pathlib import Path
import pytest

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / ".agents" / "skills" / "wiki-fapes" / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from wiki_search import search_index, get_page_content

DB_PATH = Path(__file__).resolve().parent.parent / ".index" / "search.db"


@pytest.mark.skipif(not DB_PATH.exists(), reason="Requer .index/search.db construído")
class TestWikiFapesEvaluation:
    """Valida as 5 perguntas com resposta conhecida e os 4 casos sintéticos."""

    def test_case_1_prazo_pctf_final(self):
        """Pergunta 1: Prazo para PCTF final após término da vigência."""
        res = search_index(DB_PATH, query="prazo PCTF final término vigência", limit=5)
        assert len(res["hits"]) > 0

        # Verifica se o arquivo do Manual PCTF está nos resultados
        found_manual = any("resolucao-no-313-2022-manual-pctf" in h["file_path"] for h in res["hits"])
        assert found_manual, "Manual PCTF (Resolução 313/2022) deve constar nos resultados"

        # Leitura de página confirmando 30 dias
        content = get_page_content("raw-md/prestacao-contas/resolucao-no-313-2022-manual-pctf-7d37ba1c.md", page_num=8)
        assert "30 (trinta) dias após o término de vigência do TO" in content

    def test_case_2_encargos_patronais(self):
        """Pergunta 2: Limite máximo de obrigações patronais na Resolução 309/2022."""
        res = search_index(DB_PATH, query="obrigações patronais vencimentos vantagens fixas", limit=5)
        assert len(res["hits"]) > 0

        found_res309 = any("resolucao-309-2022" in h["file_path"] for h in res["hits"])
        assert found_res309, "Resolução 309/2022 deve ser localizada"

        content = get_page_content("raw-md/prestacao-contas/resolucao-309-2022-itens-financiaveis-e-nao-financiaveis-8efae902.md", page_num=4)
        assert "36,8%" in content

    def test_case_3_recursos_edital_10_2026(self):
        """Pergunta 3: Recursos totais do Edital 10/2026 (Dr. Empreendedor Capixaba)."""
        res = search_index(DB_PATH, query="Edital 10 2026 Dr Empreendedor Capixaba recursos financeiros", limit=5)
        assert len(res["hits"]) > 0

        found_edital = any("edital-fapes-n-10-2026-dr-empreendedor-capixaba" in h["file_path"] for h in res["hits"])
        assert found_edital, "Edital 10/2026 deve ser localizado"

        content = get_page_content("raw-md/editais/edital-fapes-n-10-2026-dr-empreendedor-capixaba-1-altera-o-f50a60d2.md", page_num=4)
        assert "10.662.000,00" in content

    def test_case_4_banco_banestes(self):
        """Pergunta 4: Banco oficial para abertura de conta corrente de projetos."""
        res = search_index(DB_PATH, query="abertura conta corrente Banestes", limit=5)
        assert len(res["hits"]) > 0

        # Verifica menção expressa a Banestes no primeiro resultado
        top_snippet = res["hits"][0]["snippet"]
        assert "Banestes" in top_snippet

    def test_case_5_revogacao_expressa(self):
        """Pergunta 5: Resolução anterior expressamente revogada pela Resolução 309/2022."""
        res = search_index(DB_PATH, query="Revogam se as disposições anteriores principalmente a Resolução 217", limit=3)
        assert len(res["hits"]) > 0

        found = any("resolucao-309-2022" in h["file_path"] for h in res["hits"])
        assert found
        content = get_page_content("raw-md/prestacao-contas/resolucao-309-2022-itens-financiaveis-e-nao-financiaveis-8efae902.md", page_num=1)
        assert "Resolução 217" in content

    def test_case_6_ausencia_no_acervo(self):
        """Caso sintético 1: Pergunta cuja resposta inexiste no acervo."""
        res = search_index(DB_PATH, query="intercâmbio estudantes fundamental Antártida FAPES", limit=5)
        # Nenhuma página primária deve conter bolsa para Antártida
        has_antartida = False
        for hit in res["hits"]:
            if "Antártida" in hit["snippet"]:
                has_antartida = True
        assert not has_antartida, "Não deve encontrar bolsas de intercâmbio na Antártida"

    def test_case_7_conflito_temporal_bolsas(self):
        """Caso sintético 2: Tabela de bolsas com histórico vs valor em vigor."""
        res = search_index(DB_PATH, query='"bolsas em vigor" ICT', pasta="bolsas", limit=5)
        assert len(res["hits"]) > 0

        # Localiza a tabela em vigor
        found_vigor = any("tabela-bolsas-em-vigor" in h["file_path"] for h in res["hits"])
        assert found_vigor, "Deve encontrar a tabela de bolsas em vigor"

        content = get_page_content("raw-md/bolsas/tabela-bolsas-em-vigor-atualizada-resolucao-324-2023-1-edbef59d.md", page_num=1)
        assert "900,00" in content

    def test_case_8_tabela_posdoc_exterior(self):
        """Caso sintético 3: Extração tabular de valor de bolsa no exterior."""
        res = search_index(DB_PATH, query="POSDOC Europa exterior", limit=5)
        assert len(res["hits"]) > 0

        # Verifica valor mais recente de US$ 3.080,00
        found_val = any("3.080,00" in h["snippet"] for h in res["hits"])
        assert found_val, "Deve identificar US$ 3.080,00 na tabela"

    def test_case_9_estrutura_sintese_wiki(self):
        """Caso sintético 4: Validação de compatibilidade com wiki OKF."""
        from build_index import parse_document
        sample_synth = """---
type: Regra de Negócio
title: Prazo de Prestação de Contas Final
status: draft
generated:
  by: wiki-fapes
  at: 2026-10-15T00:00:00Z
sources:
  - id: resolucao-no-313-2022
    resource: https://fapes.es.gov.br/media/resolucao-313.pdf
    local_path: raw-md/prestacao-contas/resolucao-no-313-2022-manual-pctf-7d37ba1c.md
---
O prazo para entrega da prestação de contas final é de 30 dias.[^resolucao-no-313-2022]

[^resolucao-no-313-2022]: raw-md/prestacao-contas/resolucao-no-313-2022-manual-pctf-7d37ba1c.md, p. 8
"""
        meta, body = parse_document(sample_synth)
        assert meta["type"] == "Regra de Negócio"
        assert meta["status"] == "draft"
        assert meta["generated"]["by"] == "wiki-fapes"
        assert "[^resolucao-no-313-2022]" in body
        assert "raw-md/prestacao-contas/resolucao-no-313-2022-manual-pctf-7d37ba1c.md, p. 8" in body
