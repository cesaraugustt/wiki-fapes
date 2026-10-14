# Log

## 2026-10-14

- **Creation**: [wiki/entidades/instituicoes-atendidas.md](/entidades/instituicoes-atendidas.md) catálogo mestre das instituições atendidas e conveniadas com a FAPES (ICTs públicas, IES privadas, fundações de apoio, secretarias e autarquias estaduais, incubadoras e empresas), estruturando hierarquia de unidades (administrativas, acadêmicas, PPGs, NITs, laboratórios e campi) e requisitos para modelagem do novo SIGFAPES.
- **Creation**: `tools/extract_institutions.py` minerador de instituições, unidades organizacionais e CNPJs em lote sobre `raw-text/`, com saída consolidada em JSON e CSV.
- **Update**: [wiki/index.md](/index.md) atualizado com a inclusão de `instituicoes-atendidas.md`.

## 2026-10-13

- **Update**: [wiki/entidades/avaliador.md](file:///home/cesar_augusto/projetos/fapes-wiki/wiki/entidades/avaliador.md) ampliado de 5 para 10 modalidades de avaliadores com base em 130 editais encerrados (adicionados Comitê Julgador CNPq/FAPES, Comissão Bipartida do PPSUS, Comitê Regional Gênesis, Bancas de Acompanhamento SAP/SAF, Comitê Gestor e Comissões de IES), aplicando os princípios da skill humanizer.
- **Creation**: [wiki/entidades/avaliador.md](file:///home/cesar_augusto/projetos/fapes-wiki/wiki/entidades/avaliador.md) categorizando modalidades (ad hoc, CAs, comitê de especialistas, banca de pitch e equipe interna), critérios de impedimento, fluxo de notas e requisitos para novo sistema.
- **Update**: [AGENTS.md](file:///home/user/projetos/fapes-wiki/AGENTS.md) com diretriz para aplicar princípios da skill `humanizer` na produção textual da wiki.
- **Update**: [wiki/index.md](file:///home/user/projetos/fapes-wiki/wiki/index.md) regenerado com primeiro conceito catalogado.
- **Update**: AGENTS.md: `resource` passa a ser a URL original, com `local_path` e `sha256` nas fontes; entra `wiki/programas/`; `raw/` e `raw-text/` fora do git.
- **Creation**: coleta da rodada 1 de Editais (abertos e em julgamento): 159 arquivos em `raw/editais/`, registrados em `raw/_manifest.csv`. Ainda sem páginas em `fontes/`.
- **Creation**: `tools/crawl.py` (coleta) e `tools/okf.py` (index, find, read).
- Início do projeto
- Criação da estrutura inicial do bundle
