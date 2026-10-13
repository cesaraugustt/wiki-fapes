---
type: Entidade
title: Avaliador
description: Especialista responsável pela análise técnica, mérito científico ou avaliação mercadológica de propostas e projetos submetidos à FAPES.
tags: [entidades, avaliacao, julgamento, sigfapes, merito]
status: draft
generated: { by: "gemini/antigravity", at: 2026-10-13T10:58:00Z }
sources:
  - id: edital-24-2026-ppp-es
    resource: https://fapes.es.gov.br/media/Editais/Edital Fapes 24-2026 PPP-ES.pdf
    local_path: raw/editais/edital-fapes-24-2026-ppp-es-ea033954.pdf
    sha256: ea033954524b80d8d83649a3e948e1a983e12cd9d3e4e163419a7e98aabf7bb7
    title: Edital FAPES nº 24/2026 — PPP-ES
  - id: edital-18-2026-startups
    resource: https://fapes.es.gov.br/media/Editais/EDITAL_FAPES_18-2026_-_PARCERIAS_ENTRE_STARTUPS (1).pdf
    local_path: raw/editais/edital-fapes-18-2026-parcerias-entre-startups-1-01e91d95.pdf
    sha256: 01e91d9549311ea16eab19fef46308ef23e9c165616286740e992e28dbf3d51a
    title: Edital FAPES nº 18/2026 — Parcerias entre Startups
  - id: resolucao-ccaf-321-2022
    resource: https://fapes.es.gov.br/media/Camaras/Resolucao_321-2022-Regimento_Camaras_de_Assessoramento-1.pdf
    local_path: raw/institucional/resolucao-321-2022-regimento-camaras-de-assessoramento-1-414800ad.pdf
    sha256: 414800ad35db59ba30544669a9243f40e1af756187d14206fb018c27ef45ac0f
    title: Resolução CCAF nº 321/2022 — Regimento Interno das Câmaras de Assessoramento
---

# Avaliador

O **Avaliador** é o agente responsável pelo exame técnico, julgamento de mérito e acompanhamento das propostas e projetos apoiados pela FAPES.[^edital-24-2026-ppp-1]

A regulação da FAPES divide os avaliadores em diferentes modalidades funcionais, variando conforme a natureza do edital (acadêmico, inovação ou institucional).

## Modalidades de avaliadores

| Modalidade | Atribuição | Requisitos de perfil | Origem normativa |
| :--- | :--- | :--- | :--- |
| **Avaliador Ad Hoc** | Parecer individual e independente sobre mérito científico de projetos submetidos e relatórios técnicos. | Especialista de área específica. Em editais de pesquisa científica (ex.: PPP-ES), exige-se residência fora do Espírito Santo. | Instrução de Serviço FAPES nº 080/2025;[^edital-24-2026-ppp-2] Edital 24/2026, item 3.2.[^edital-24-2026-ppp-3] |
| **Membro de Câmara de Assessoramento (CA)** | Julgamento colegiado de propostas em 10 áreas temáticas e acompanhamento da execução técnica. | Residência no Espírito Santo; título de doutor (áreas I a VIII) ou experiência comprovada (Inovação e Extensão); mandato de 2 anos. | Resolução CCAF nº 321/2022, arts. 2º e 3º.[^resolucao-ccaf-321-2022-1] |
| **Comitê de Especialistas** | Avaliação técnica e mercadológica em programas de inovação aberta, parcerias e aceleração de negócios. | Profissionais de mercado, pesquisadores e investidores qualificados. | Edital 18/2026, item 10.2.4.[^edital-18-2026-startups-1] |
| **Banca de Pitch** | Avaliação presencial ou remota em tempo real de apresentações orais de startups (3 a 5 min, ou 10 min em língua estrangeira). | Membros designados do comitê de inovação. | Edital 18/2026, item 10.2.4 a 10.2.6.[^edital-18-2026-startups-2] |
| **Equipe Técnica Interna** | Análise formal de enquadramento, habilitação documental e conferência de prestação de contas. | Servidores efetivos e técnicos comissionados da DITEC e DIRAF. | Edital 24/2026, item 3.1.[^edital-24-2026-ppp-4] |

## Regras de atuação e julgamento

### Conflito de interesses e impedimento

O avaliador não pode emitir parecer em propostas nas seguintes condições:[^edital-24-2026-ppp-5] [^resolucao-ccaf-321-2022-2]

1. Integrar a equipe da proposta como coordenador ou membro participante;
2. Ter cônjuge, companheiro ou parente até terceiro grau participando da proposta;
3. Manter interesse econômico, societário ou pessoal direto ou indireto no resultado;
4. Estar em litígio administrativo ou judicial com o proponente ou membros da equipe;
5. Fazer parte do quadro permanente ou terceirizado da FAPES (vedação restrita a consultores ad hoc externos).

### Acesso ao sistema e sigilo

No modelo vigente do SIGFAPES, cada parecerista utiliza credencial pessoal. Antes de visualizar o teor técnico ou os anexos da proposta, o avaliador precisa firmar eletronicamente o termo de sigilo e confidencialidade.[^edital-24-2026-ppp-6]

### Sistema de pontuação e divergência de notas

Nos editais acadêmicos:

- Cada proposta recebe avaliação independente de no mínimo 2 (dois) avaliadores ad hoc.[^edital-24-2026-ppp-7]
- Se houver diferença igual ou superior a 30% entre as duas primeiras notas, e pelo menos uma delas for maior ou igual a 70 pontos, a proposta é remetida a um terceiro avaliador ad hoc.[^edital-24-2026-ppp-8]
- A nota final resultante é calculada pela média simples entre as duas notas que apresentarem menor diferença entre si.[^edital-24-2026-ppp-9]

### Obrigação de coordenadores financiados

Pesquisadores que celebram Termo de Outorga com a FAPES assumem o compromisso compulsório de atuar como avaliadores ad hoc da Fundação durante o período de vigência do projeto e nos 12 meses seguintes à conclusão.[^edital-24-2026-ppp-10]

---

## Requisitos para o novo sistema

A substituição do SIGFAPES demanda a implementação dos seguintes requisitos funcionais para a entidade Avaliador:

1. **Cadastro unificado de pareceristas**: registro com árvore de áreas do conhecimento (padrão CNPq), instituição de vínculo, endereço/UF para controle de territorialidade e titulação formal.
2. **Checagem algorítmica de conflitos**: bloqueio de atribuição de proposta quando o avaliador for da mesma instituição e departamento do coordenador, tiver coautoria recente identificada no Lattes ou integrar a mesma chamada.
3. **Módulo de bancas de pitch**: suporte a preenchimento de notas durante apresentações síncronas com consolidação de notas e pesos em tempo real.
4. **Acionamento automático de terceiro avaliador**: cálculo automático da disparidade (>= 30% com nota >= 70) com inclusão da proposta na fila de pareceristas de desempate.
5. **Rastreamento de obrigações de contrapartida**: vinculação do histórico de pareceres emitidos ao CPF do coordenador, impedindo novas concessões a beneficiários inadimplentes com a obrigação de parecerista ad hoc.

---

[^edital-24-2026-ppp-1]: Edital FAPES 24/2026 (PPP-ES), glossário, p. 49.
[^edital-24-2026-ppp-2]: Edital FAPES 24/2026 (PPP-ES), item 7.3, p. 46.
[^edital-24-2026-ppp-3]: Edital FAPES 24/2026 (PPP-ES), item 3.2, p. 20.
[^edital-24-2026-ppp-4]: Edital FAPES 24/2026 (PPP-ES), item 3.1, p. 19.
[^edital-24-2026-ppp-5]: Edital FAPES 24/2026 (PPP-ES), item 3.2, p. 20-21.
[^edital-24-2026-ppp-6]: Edital FAPES 24/2026 (PPP-ES), item 3.2, p. 20.
[^edital-24-2026-ppp-7]: Edital FAPES 24/2026 (PPP-ES), item 3.2.1.1, p. 23.
[^edital-24-2026-ppp-8]: Edital FAPES 24/2026 (PPP-ES), item 3.2.1.1, p. 23.
[^edital-24-2026-ppp-9]: Edital FAPES 24/2026 (PPP-ES), item 3.2.1.1, p. 23.
[^edital-24-2026-ppp-10]: Edital FAPES 24/2026 (PPP-ES), item 13.1.20, p. 32.
[^resolucao-ccaf-321-2022-1]: Resolução CCAF nº 321/2022, Anexo Único, arts. 2º e 3º, p. 2.
[^resolucao-ccaf-321-2022-2]: Resolução CCAF nº 321/2022, Anexo Único, art. 7º, p. 3.
[^edital-18-2026-startups-1]: Edital FAPES 18/2026 (Parcerias entre Startups), item 10.2.4, p. 7.
[^edital-18-2026-startups-2]: Edital FAPES 18/2026 (Parcerias entre Startups), item 10.2.4 a 10.2.6, p. 7-8.
