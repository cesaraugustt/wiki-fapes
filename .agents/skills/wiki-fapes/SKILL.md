---
name: wiki-fapes
description: Consulta o acervo documental da FAPES em raw-md/ com busca textual ponderada (SQLite FTS5 BM25), leitura exata de páginas originais, citação formal (raw-md/<caminho>.md, p. N), resolução de vigência e geração de sínteses para a wiki OKF.
---

# Wiki FAPES Skill

Esta skill habilita consultas confiáveis ao acervo normativo e administrativo da FAPES convertido em `raw-md/`.

---

## Ferramentas Disponíveis

Todos os comandos devem ser executados via `uv run`:

1. **Busca Textual BM25**:

   ```bash
   uv run .agents/skills/wiki-fapes/scripts/wiki_search.py search "<consulta>" [-k 8] [--pasta <pasta>] [--ano <ano>]
   ```

   - Aceita frases exatas entre aspas: `"iniciação científica"`.
   - Pastas disponíveis: `bolsas`, `editais`, `legislacao`, `prestacao-contas`, `formularios`, `institucional`.
   - Saída estruturada contendo arquivo, página, caminho de cabeçalhos e trecho de ~400 caracteres.

2. **Leitura Exata de Página(s)**:

   ```bash
   uv run .agents/skills/wiki-fapes/scripts/wiki_search.py page <arquivo> <pagina> [--ate <pagina_final>]
   ```

   - Retorna o texto original primário entre os marcadores `<!-- page N -->`.

3. **Árvore de Cabeçalhos (Outline)**:

   ```bash
   uv run .agents/skills/wiki-fapes/scripts/wiki_search.py outline <arquivo>
   ```

4. **Estatísticas do Índice**:

   ```bash
   uv run .agents/skills/wiki-fapes/scripts/wiki_search.py stats
   ```

5. **Reindexação Incremental**:

   ```bash
   uv run .agents/skills/wiki-fapes/scripts/build_index.py
   ```

---

## Protocolo de Execução Obrigatório

Siga sempre as 6 etapas abaixo:

1. **Buscar no Acervo**:
   - Execute `wiki_search.py search "<termos-chave>"`.
   - Se os resultados forem vagos ou dispersos, refine a consulta com termos específicos ou filtre por `--pasta` / `--ano`.

2. **Ler a Página Original Antes de Afirmar**:
   - Antes de cravar qualquer **valor monetário, prazo, percentual, requisito de habilitação ou critério de pontuação**, execute `wiki_search.py page <arquivo> <n>` e inspecione o texto completo do artigo ou parágrafo.

3. **Citação Obrigatória**:
   - Toda resposta factual deve citar expressamente a fonte e a página no formato:
     `raw-md/<caminho>.md, p. N`
   - Exemplo: `raw-md/prestacao-contas/resolucao-no-313-2022-manual-pctf-7d37ba1c.md, p. 8`.

4. **Resolução de Vigência e Conflitos**:
   - Se encontrar fontes divergentes de anos distintos, aplique o princípio da sucessão temporal (*lex posterior derogat priori*): adote a norma mais recente e alerte o usuário sobre a norma antiga desconsiderada.
   - Consulte `references/vigencia-e-conflitos.md` para a cronologia de tabelas de bolsas e resoluções do CCAF.
   - Para valores de bolsas em aberto, utilize sempre a Resolução 324/2023 (atualizada pela 352/2025).

5. **Acervo Negativo (Não Alucinar)**:
   - Se o fato ou documento pesquisado não constar nos resultados após refinamento, informe com clareza: *"Informação não localizada no acervo da FAPES."*
   - Nunca complete com conhecimento genérico de fora do acervo nem invente regras.

6. **Geração de Sínteses para a Wiki**:
   - Ao ser solicitado criar ou atualizar páginas em `wiki/`, siga o padrão OKF v0.2 (`AGENTS.md`):
     - Frontmatter YAML com `type`, `title`, `description`, `status: draft`, `generated` e `sources`.
     - Corpo em português formal claro (aplicando `humanizer`).
     - Citações por nota de rodapé indexada pelo id da fonte com localização de item e página.
