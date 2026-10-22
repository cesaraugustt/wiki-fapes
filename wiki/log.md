# Log

## 2026-10-22

- **Update**: `tools/instituicoes.json` unificado como base canônica do catálogo de entidades da FAPES: 76 instituições consolidadas, com unidades organizacionais categorizadas e lista de papéis institucionais, eliminando o campo CNPJ para evitar divergências cadastrais.
- **Creation**: `tools/build_instituicoes_json.py` como gerador oficial de `tools/instituicoes.json`.
- **Deprecation**: Expurgados 11 arquivos legados e intermediários obsoletos da pasta `tools/` (`extract.py`, `extract_institutions.py`, `extract_companies.py`, `build_clean_instituicoes_json.py`, `build_unified_institutions_json.py`, `instituicoes_unidades.json`, `companies_extracted.*`, `institutions_extracted.*` e `institutions_raw_md_evaluated.json`).
- **Update**: [wiki/entidades/instituicoes-atendidas.md](/entidades/instituicoes-atendidas.md) atualizado para referenciar `tools/instituicoes.json`.

## 2026-10-19

- **Update**: [wiki/entidades/avaliador.md](/entidades/avaliador.md) atualizado e humanizado com base nas novas fontes normativas e editais incorporados ao acervo: expansão de 16 para 22 modalidades avaliativas, inclusão das regras de convocação e prioridade algorítmica da IS FAPES nº 080/2025, tabela oficial de remuneração em VRTE e regime de gratuidade compulsória da IS FAPES nº 048/2026, comitês de governança interinstitucional (Inova SEGER e Comunidades Empreendedoras), comitês multilaterais transnacionais (RAMP/PILAR e SBEP), atuação da Comissão Interna de Diversidade e especificação de novos requisitos para o ConectaFapes.
- **Update**: [wiki/entidades/instituicoes-atendidas.md](/entidades/instituicoes-atendidas.md) atualizado com mineração das 646 fontes de `raw-md/`: incorporadas novas entidades parceiras e demandantes do Relatório de Gestão FUNCITEC 2025/2026 (SEAMA, ADERES, ARSP, ALES, DER-ES, SEJUS, SETADES, SEDH, SETUR, SEDURB e parceria federal RFB/ALF-VIT/SERPRO), mapeamento de ambientes e indústrias (Jurong, ITV, Lume Robotics na DI 011/2025, Instituto Sustentabilidade Brasil), modelo normativo de representação da Resolução CCAF nº 168/2017 (Instituição, Unidade com CNPJ filial e Representante Legal por unidade ou global com mandato vigente), eliminação do gargalo legado de cadastro manual via e-mail do SigFapes, hierarquia acadêmica de bolsas de pós-graduação do PROCAP 2027 e governança interna das unidades funcionais da FAPES (CCAF, DIREX, DITEC, DIRAF, GETEC, GEPOF, NUPAR, NUPEX, UECI e ASJUR).

## 2026-10-15

- **Update**: [wiki/entidades/avaliador.md](/entidades/avaliador.md) reavaliado integralmente a partir de mineração profunda nos 580 arquivos de `raw-md/`, expandindo a tipologia de 10 para 16 modalidades funcionais com mapeamento exato de competências, requisitos de titulação, territorialidade, dinâmica de notas e correspondência com as tipologias de editais da FAPES.
- **Creation**: `tools/instituicoes_unidades.json` e `tools/build_unified_institutions_json.py` consolidando 46 instituições (ICTs públicas, IES privadas, fundações de apoio, secretarias/autarquias estaduais e ambientes de inovação) com hierarquia de unidades organizacionais, papéis de projeto e fontes rastreáveis no acervo.
- **Update**: [wiki/entidades/instituicoes-atendidas.md](/entidades/instituicoes-atendidas.md) reavaliado integralmente a partir da mineração contextual em 580 arquivos de `raw-md/`, incorporando 18 IES privadas participantes do Nossa Bolsa/PROCAP, NITs apoiados pela Resolução 283/2021, hubs setoriais (FINDESLAB e Sincades Tech) e expurgando vazamentos interinstitucionais de unidades.
- **Creation**: `tools/evaluate_institutions_raw_md.py` minerador contextual por limites de bloco, tabela e parágrafo em documentos markdown Docling, gerando base auditada em `tools/institutions_raw_md_evaluated.json`.
- **Update**: `tools/convert_docling.py` atualizado com migração de OCR para EasyOCR (`EasyOcrOptions`), fallback automático para PDFs com saída vazia ou anômala, calibração da razão alfanumérica para 80%, suporte a páginas com carimbos digitais (Docusign/DIO) ou vetores gráficos e nova flag `--retry-failed` com consolidação do manifesto.
- **Update**: [docs/decisoes/docling-eval.md](/docs/decisoes/docling-eval.md) Seção 7 adicionada com diagnóstico da conversão de 653 arquivos e resolução de falhas para execução na máquina com GPU.

## 2026-10-14

- **Update**: Homologação do Docling (GPU) como extrator padrão para `raw-md/` (substituindo `raw-text/`), formalizado em [docs/decisoes/docling-eval.md](/docs/decisoes/docling-eval.md) e `tools/convert_docling.py`. Conversão piloto de 154 documentos elegíveis concluída com 100% de sucesso e quarentena zerada.
- **Update**: Expurgados 111 falsos positivos em empresas e 267 falsos positivos em unidades públicas; bases `tools/companies_extracted.*` e `tools/institutions_extracted.*` regeradas exclusivamente com dados auditados e validados.

- **Update**: [wiki/entidades/instituicoes-atendidas.md](/entidades/instituicoes-atendidas.md) seção 6 ampliada com tabelas nominais de Startups (Lume Robotics, Dersalis, Jade Autism, Endelevo, Multifidelidade, Buskar.me, PicPay, Vix Team) e Grandes Empresas Coinvestidoras (ArcelorMittal, Vale, Suzano, Petrobras, Marcopolo, ES GÁS, Sincades).
- **Creation**: `tools/extract_companies.py` minerador especializado em empresas privadas e startups, gerando bases brutas de 139 registros em `tools/companies_extracted.csv` e `tools/companies_extracted.json`.
- **Creation**: [wiki/entidades/instituicoes-atendidas.md](/entidades/instituicoes-atendidas.md) catálogo mestre das instituições atendidas e conveniadas com a FAPES (ICTs públicas, IES privadas, fundações de apoio, secretarias e autarquias estaduais, incubadoras e empresas), estruturando hierarquia de unidades (administrativas, acadêmicas, PPGs, NITs, laboratórios e campi) e requisitos para modelagem do ConectaFapes.
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
