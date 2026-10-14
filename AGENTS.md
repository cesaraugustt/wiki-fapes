# Wiki FAPES

Base de conhecimento mantida por um agente de IA, no padrão LLM Wiki (Karpathy),
com o formato de armazenamento **Open Knowledge Format (OKF) v0.2**.

Objetivo: extrair dos documentos publicados pela FAPES (<https://fapes.es.gov.br/>)
as regras, entidades, processos e requisitos necessários para especificar o
novo sistema que substituirá o SIGFAPES.

O humano cura as fontes, faz as perguntas e **revisa** o conteúdo.
O agente lê, sintetiza, conecta e mantém a wiki.

## Estrutura de pastas

```text
raw/                    fontes originais — IMUTÁVEL, nunca modificar; FORA do git (.gitignore)
  editais/ legislacao/ prestacao-contas/ bolsas/ institucional/ formularios/
  _manifest.csv         url, data_coleta, sha256, secao, tipo, status, http_status, content_type, bytes
                        (único arquivo de raw/ versionado no git)
raw-text/               texto extraído dos PDFs/HTML (derivado; fora do git; pode ser regerado)
wiki/                   BUNDLE OKF — mantido pelo agente
  index.md              catálogo (progressive disclosure)
  log.md                histórico de mudanças
  fontes/               um conceito por documento raw (type: Fonte)
  programas/            uma página-família por programa; compara edições e lista o que mudou
  editais/              um conceito por edital (slug: edital-NN-AAAA-programa)
  normas/               leis, resoluções, portarias, notas técnicas
  entidades/            proponente, bolsista, projeto, bolsa, avaliador...
  regras/               regras de negócio extraídas
  # criar só quando houver conteúdo:
  processos/            fluxos (submissão, julgamento, implementação de bolsa, prestação de contas...)
  requisitos/           o que o novo sistema precisa cobrir
  respostas/            respostas de consultas valiosas, guardadas para acumular
```

Subpastas dentro de `wiki/` podem ter `index.md` próprio.

## Formato OKF (resumo do que importa aqui)

- Toda página `.md` da wiki (exceto `index.md` e `log.md`, que são reservados)
  começa com frontmatter YAML. O único campo obrigatório é `type`.
- `index.md` não tem frontmatter, exceto o da raiz, que declara `okf_version: "0.2"`.
- Links entre conceitos: markdown padrão com caminho absoluto a partir de `wiki/`,
  ex.: `[Prestação de contas](/processos/prestacao-de-contas.md)`.
  Links quebrados são tolerados (conhecimento ainda não escrito), mas o lint os lista.
- Nomes de arquivo: minúsculas, sem acento, com hífens (`itens-financiaveis.md`).
- O conteúdo é escrito em **português (pt-BR)**; chaves do frontmatter ficam em inglês.

### Frontmatter padrão

```yaml
---
type: Regra de Negócio        # obrigatório; ver tipos abaixo
title: Prazo para prestação de contas de bolsa
description: Uma frase resumindo a página.
resource: https://fapes.es.gov.br/...   # obrigatório em Fonte e Edital; opcional nos demais
tags: [prestacao-de-contas, bolsas]
status: draft                 # draft | stable | deprecated
generated: { by: <agente/modelo>, at: 2026-10-07T00:00:00Z }
verified:                     # SÓ o humano preenche (ver Regras de confiança)
  - { by: human:<id>, at: 2026-10-08T00:00:00Z }
stale_after: 2027-01-01T00:00:00Z   # opcional; útil para editais com prazo
sources:
  - id: edital-24-2026
    resource: https://fapes.es.gov.br/media/Editais/edital-24-2026.pdf   # URL original
    local_path: raw/editais/edital-24-2026-ppp-es-ab12cd34.pdf          # cópia local (fora do git)
    sha256: <hash do arquivo>                                          # igual ao _manifest.csv
    title: Edital FAPES nº 24/2026 — PPP-ES
    last_modified: 2026-08-01T00:00:00Z                  # se conhecido
---
```

Datas sempre em ISO 8601 com fuso (`Z`).

### Tipos de conceito usados (livres; criar novos se necessário)

`Fonte`, `Edital`, `Norma`, `Entidade`, `Regra de Negócio`, `Processo`,
`Requisito`, `Formulário`, `Resposta`, `Glossário`.

## Citações (obrigatório)

- Toda afirmação factual cita a fonte por **nota de rodapé cujo rótulo é o `id` em `sources`**:

```text
  O prazo é de 60 dias após o término da vigência.[^edital-24-2026]

  [^edital-24-2026]: Edital 24/2026, item 12.3, p. 18
```

- A nota de rodapé **sempre inclui o localizador** (item/artigo/página).
- Sem fonte → marcar `(a verificar)` e não afirmar como fato.
- Fontes divergentes → registrar a contradição explicitamente na página,
  citando ambas. Não escolher uma silenciosamente.
- Norma revogada ou edital superado → `status: deprecated` e link para o que a substitui.

## Regras de confiança

- O agente escreve `generated` em tudo que cria ou altera.
- O agente **nunca** escreve `verified` com `human:`. Só o humano confirma.
  Páginas novas nascem `status: draft`; o humano promove para `stable` ao revisar.
- Ao responder consultas, indicar quando a resposta se apoia em páginas `draft`/não verificadas.
- Se `now >= stale_after`, tratar a informação como possivelmente vencida e avisar.

## Fluxo de ingestão

Quando o humano adicionar fontes em `raw/` e pedir ingestão:

1. Conferir a entrada no `raw/_manifest.csv` (url de origem, data de coleta, hash).
2. Ler o documento completo (usar `raw-text/` se for PDF).
3. **Discutir os pontos principais com o humano antes de escrever.**
4. Criar a página em `wiki/fontes/` (type `Fonte`) com resumo e metadados.
5. Criar/atualizar páginas de edital, norma, entidades, regras, processos e requisitos afetados.
   Uma fonte pode tocar 10–15 páginas; isso é normal.
6. Conectar com links; citar com notas de rodapé.
7. Comparar com edições anteriores do mesmo tipo de edital e registrar o que mudou.
8. Atualizar `wiki/index.md` (e `index.md` das subpastas) com descrição de uma linha.
9. Adicionar entrada em `wiki/log.md`.

## Fluxo de consulta

1. Ler `wiki/index.md` e localizar as páginas relevantes.
2. Ler essas páginas e sintetizar a resposta, citando as páginas da wiki
   (e, quando necessário, as fontes em `raw/`).
3. Se a resposta não está na wiki, dizer claramente. Não preencher com conhecimento geral.
4. Se a resposta for valiosa, oferecer salvá-la em `wiki/respostas/` (type `Resposta`).

## Distinção crítica: publicado vs. sistema atual

A wiki reflete o que a **FAPES publica**. Ela **não** descreve o comportamento interno
do SIGFAPES atual (telas, campos, regras implementadas, modelo de dados), a menos que
existam fontes em `raw/sigfapes/` (manuais, prints, dumps de esquema, documentação interna).
Sempre rotular em requisitos e regras: `origem: norma publicada` ou `origem: sistema atual`.
Se uma regra publicada parecer divergir do comportamento do sistema, registrar como pergunta em aberto.

## Coleta de dados (crawler)

- Respeitar `robots.txt`, usar delay entre requisições e User-Agent identificado.
- Nunca baixar em lote sem plano aprovado pelo humano.
- Registrar cada arquivo em `raw/_manifest.csv`; deduplicar por hash.

## Lint

Quando o humano pedir lint/auditoria, verificar e reportar em lista numerada com correção sugerida:

1. Páginas sem frontmatter ou sem `type`.
2. Contradições entre páginas ou fontes.
3. Páginas órfãs (sem links de entrada) e links quebrados.
4. Conceitos citados em prosa que ainda não têm página.
5. Afirmações sem nota de rodapé ou com `id` inexistente em `sources`.
6. Páginas com `now >= stale_after` e normas/editais possivelmente superados por fontes mais novas.
7. Páginas `stable` que linkam para páginas `deprecated`.
8. Páginas `draft` antigas aguardando revisão humana.
9. Entradas de `raw/` sem página em `wiki/fontes/` (e o inverso).

## Regras gerais

- Nunca modificar nada em `raw/` depois de baixado.
- Sempre atualizar `index.md` e `log.md` após mudanças na wiki.
- `log.md` segue o OKF: títulos de data `## YYYY-MM-DD`, **entradas mais novas no topo**,
  prefixos em negrito (`**Creation**`, `**Update**`, `**Deprecation**`).
- Linguagem clara e simples; frases curtas; tabelas para regras comparáveis entre editais.
- Produção textual: aplicar a skill `humanizer` em todo o conteúdo da wiki.
- Trabalhar um passo por vez: propor o plano e esperar aprovação antes de escrever
  arquivos em lote ou rodar downloads.
- Na dúvida sobre como categorizar algo, perguntar ao humano.
- Mudanças neste `AGENTS.md` só com aprovação do humano; sugerir melhorias quando um erro se repetir.

## Agent skills

### Issue tracker

GitHub Issues via `gh` CLI. See `docs/agents/issue-tracker.md`.

### Triage labels

Canonical roles mapped 1:1 (`needs-triage`, `needs-info`, `ready-for-agent`, `ready-for-human`, `wontfix`). See `docs/agents/triage-labels.md`.

### Domain docs

Single-context layout (`CONTEXT.md` + `docs/adr/`). See `docs/agents/domain.md`.
