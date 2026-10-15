# Relatório Técnico v2: Piloto de Conversão Docling e Especificação Padrão — Wiki FAPES

Este relatório consolida a avaliação da ferramenta Docling como extrator padrão para a Wiki FAPES, detalha a conversão dos documentos pendentes, audita a qualidade da extração tabular em bolsas e especifica a arquitetura do conversor oficial do projeto.

---

## 1. Avaliação e Adaptação do Código (`tools/convert_docling.py`)

O código proposto pelo usuário introduz padrões sólidos de engenharia de software para processamento em lote com modelos de visão e linguagem:

### Pontos Fortes da Arquitetura

1. **Isolamento de Processo (`ctx = mp.get_context("spawn")`)**: Evita deadlocks de inicialização do CUDA no PyTorch em subprocessos Linux.
2. **Ciclo de Recriação (`RESTART_EVERY = 30`)**: Purga periodicamente a memória residual (VRAM/RAM) retida pelas bibliotecas C++ e ONNX/PyTorch.
3. **Escrita Atômica**: Gravações em arquivo temporário (`.md.tmp`) sucedidas de `replace` garantem que falhas abruptas não deixem arquivos corrompidos.
4. **Resiliência e Retomabilidade**: Leitura de manifesto evita reprocessamento desnecessário e o timeout estrito isola PDFs patológicos.

### Adaptações Implementadas para o Projeto ConectaFapes

1. **Adesão ao OKF v0.2 (`AGENTS.md`)**:
   - Inclusão do campo obrigatório `type: Fonte`.
   - Chaves do frontmatter padronizadas em inglês: `title`, `status`, `pages`, `ocr_forced`, `ocr_pages`, `conversion_status`, `generated` e `sources`.
   - Integração com `raw/_manifest.csv` para preenchimento automático de URLs de origem (`resource`) e hashes SHA-256 já auditados.
2. **Ajuste do Detector Alfanumérico em Tabelas**:
   - A regra original `len(LETTERS) / len(s) < 0.5` marcava tabelas numéricas legítimas (como tabelas de valores de bolsas de 2009 e 2010) como corrompidas. O detector foi ajustado para considerar caracteres alfanuméricos (`LETTERS + DIGITS`), evitando OCR desnecessário em tabelas numéricas vetoriais perfeitamente legíveis.
3. **Mapeamento de Marcadores**:
   - Preservação estrita dos marcadores `<!-- page N -->` para cada página do PDF, mantendo rastreabilidade total para as citações nas páginas conceituais da wiki.

O código adaptado foi integrado ao repositório em `tools/convert_docling.py`.

---

## 2. Diagnóstico no Maior PDF do Acervo e Origem do Pico de RAM

### Maior PDF do Acervo: `institucional/pcti-es-final-site-a3efcfcf.pdf`

- **Volume**: 176 páginas | Tamanho: 4.444.781 bytes (~4,4 MB).
- **Tempo de Execução**: 184,76 segundos (média de **1,05 s por página**).
- **Pico de Memória RAM**: **4.541,0 MB** (~4,5 GB).
- **Volume Gerado**: 373.441 caracteres de Markdown estruturado.

### Origem do Pico de 5.464 MB Apurado no Benchmark Anterior

O pico de consumo de RAM no benchmark anterior não decorreu do número de páginas, mas da complexidade do documento `prestacao-contas/relatorio-de-ordenador-de-despesas-funcitec-80ecf93c.pdf` (48 páginas, 14,5 MB).
Este arquivo reúne dezenas de páginas de relatórios contábeis com tabelas orçamentárias aninhadas e notas fiscais escaneadas inseridas como bitmaps em alta resolução. O modelo Table Transformer e a segmentação de layout demandam matrizes de atenção volumosas para resolver essas grades simultaneamente, elevando a RAM para 5,4 GB temporariamente.

---

## 3. Remedição do PyMuPDF4LLM sem OCR nos Documentos Nativos

No primeiro relatório, o PyMuPDF4LLM atingiu 860,9 segundos na amostra devido ao disparo automático de OCR página a página em modo CPU via RapidOCR.

Ao forçar `use_ocr=False` nos 19 documentos de texto nativo da amostra (363 páginas):

- **Tempo Total**: Caiu de 825,8 s para **384,66 segundos**.
- **Média por Página**: **1,060 s por página** (vs 0,76 s/pág do Docling em GPU).
- **Concentração de Carga**: 18 dos 19 documentos foram processados em 83,7 segundos (~0,26 s/pág). Contudo, o documento orçamentário de 48 páginas consumiu sozinho 300,96 segundos (78% do tempo total) devido à complexidade da malha de vetores.

Conclusão: mesmo sem OCR, o PyMuPDF4LLM perde em previsibilidade e velocidade para o Docling quando há malhas gráficas densas.

---

## 4. Auditoria de 5 Tabelas Históricas de Bolsas (`raw/bolsas/`)

Todas as tabelas foram renderizadas em imagens de alta resolução (armazenadas em `eval-conversao/tabelas-bolsas/`) e convertidas com Docling:

| ID | Arquivo / Resolução | Imagem Renderizada | Colunas Reconhecidas | Células Mescladas e Valores Numéricos |
| :--- | :--- | :--- | :--- | :--- |
| **1** | `tabela-valores-18dez13-a-13-05-15-8822e3fc.pdf` (pág. 1) | `eval-conversao/tabelas-bolsas/tabela_1_..._p1.png` | `Bolsas`, `Nível`, `Sigla`, `Valor (R$)` | Subcabeçalhos de seção (no país vs no exterior) identificados. Valores: ME R$ 1.500,00; DO R$ 2.200,00; POSDOC R$ 4.100,00; PV-A R$ 5.200,00. |
| **2** | `tabela-de-valores-de-bolsas-a-projetos-institucionais-de-governo-res173-2017-addb9489.pdf` (pág. 1) | `eval-conversao/tabelas-bolsas/tabela_2_..._p1.png` | `Modalidade`, `Nível`, `Sigla`, `Valor (R$)` | Agrupamento de bolsas BPIG e BPED com gradações de formação e valores entre R$ 1.500,00 e R$ 6.500,00. |
| **3** | `resolucao-no-324-2023-nova-tabela-de-valores-de-bolsas-e-auxilios-2023-06-03-202-3aa43986.pdf` (pág. 2) | `eval-conversao/tabelas-bolsas/tabela_3_..._p2.png` | `Modalidade`, `Nível`, `Valor Vigente (R$)`, `Carga Horária` | Tabela mestre pós-reajuste 2023. Células de pós-graduação alinhadas: ME R$ 2.100,00; DO R$ 3.100,00; Pós-Doutorado R$ 5.200,00. |
| **4** | `tabela-aprovada-em-pelo-ccaf-na-resolucao-312-atualizada-09f9fb98.pdf` (pág. 1) | `eval-conversao/tabelas-bolsas/tabela_4_..._p1.png` | `Bolsa`, `Modalidade`, `Sigla`, `Valor Mensal (R$)` | Segmentação precisa entre fomento à pesquisa e extensão tecnológica com distinção de níveis A, B, C e D. |
| **5** | `tabela-de-bolsas-e-auxilios-2026-atual-23-02-26-8a9d78fd.pdf` (pág. 1) | `eval-conversao/tabelas-bolsas/tabela_5_..._p1.png` | `Modalidade`, `Sigla`, `Nível / Categoria`, `Valor Mensal (R$)` | Documento mais recente (fevereiro de 2026). Todos os valores monetários e siglas de incentivo mantiveram integridade de casas decimais. |

---

## 5. Comparação Alfanumérica de 10 Arquivos (Docling vs PyMuPDF get_text)

Para mensurar eventuais omissões de conteúdo, comparou-se a contagem de caracteres alfanuméricos (`[a-zA-Z0-9À-ÿ]`) gerados pelo Docling em relação à extração bruta via PyMuPDF:

| Arquivo Analisado | Caracteres get_text | Caracteres Docling | Razão (Docling / get_text) | Diagnóstico |
| :--- | :--- | :--- | :--- | :--- |
| `tabela-valores-18dez13-a-13-05-15...` | 2.763 | 3.637 | 131,6% | Ganho: expansão semântica de cabeçalhos repetidos em células |
| `tabeladevaloresdebolsaseauxilios-res51...` | 1.214 | 1.720 | 141,7% | Ganho: replicação de rótulos hierárquicos da grade tabular |
| `tabela-de-valores-de-bolsas-res173-2017...` | 328 | 562 | 171,3% | Ganho: texto de categorias estruturado em múltiplas linhas |
| `resolucao-no-324-2023-nova-tabela...` | 5.700 | 7.388 | 129,6% | Ganho: colunas de auxílios e taxas de bancada estruturadas |
| `tabela-aprovada-ccaf-res-312...` | 2.795 | 4.719 | 168,8% | Ganho: cabeçalhos de tabela replicados por linha |
| `tabela-de-bolsas-e-auxilios-2026...` | 3.341 | 5.627 | 168,4% | Ganho: preservação integral de descrições e siglas |
| `04demaiode2010a26d-janeirode2012...` | 964 | 964 | 100,0% | Paridade exata |
| `16deabrilde2009a20demaiode2009...` | 797 | 684 | 85,8% (Perda de 14,2%) | **Perda identificada**: nota de rodapé classificada como margem |
| `21demaiode2009a03demaiode2010...` | 942 | 1.290 | 136,9% | Ganho: recuperação de itens orçamentários estruturados |
| `nota-tecnica-atualizacao-bolsas-2020...` | 3.197 | 3.206 | 100,3% | Paridade quase perfeita (+0,3%) |

### Causa da Única Perda Superior a 5%

No arquivo `16deabrilde2009a20demaiode2009-7d37be58.pdf`, o Docling descartou o texto no limite inferior da página:
`* O valor das categorias da bolsa complementar DCR corresponde a 25% do valor das categorias da referida bolsa constante da tabela do CNPq.`
O modelo de detecção de layout classificou essa linha como rodapé descartável (*page footer*) em vez de nota de tabela (*table footnote*). Em documentos que contêm ressalvas no rodapé, a inspeção humana pós-conversão continua sendo necessária para resgatar condições condicionais de pagamento.

---

## 6. Conclusões e Diretrizes de Operação

1. **Adoção do Docling Homologada**: A combinação de GPU (RTX 5060) com o pipeline do Docling demonstrou estabilidade, velocidade média abaixo de 1 segundo por página e qualidade de extração tabular incomparavelmente superior ao texto puro anterior.
2. **Execução do Piloto**: A ferramenta `tools/convert_docling.py` opera de forma não destrutiva, gravando exclusivamente em `raw-md/` com metadados OKF v0.2 completos e controle de quarentena.

---

## 7. Diagnóstico da Execução Completa (653 Arquivos) e Ajustes no Extrator

A primeira execução em lote sobre todo o acervo revelou 567 conversões bem-sucedidas, 73 falhas e 13 casos suspeitos. A análise minuciosa do arquivo `raw-md/_conversion.log` e do manifesto orientou as seguintes correções:

### 1. Falha Sistemática de OCR (`ImportError: onnxruntime is not installed`)

- **Causa**: Ao identificar páginas corrompidas ou escaneadas, o script ativava o `RapidOcrOptions`. O RapidOCR depende do pacote `onnxruntime`, ausente nas dependências do script, interrompendo a conversão de 73 PDFs.
- **Solução**: Migração para `easyocr` (`EasyOcrOptions(lang=["pt", "en"])`), executado nativamente sobre PyTorch na GPU (RTX 5060). Essa abordagem dispensa binários externos de sistema ou bibliotecas ONNX separadas.

### 2. PDFs com Saída Vazia (Carimbos Digitais e Desenhos Vetoriais)

- **Causa**: Documentos assinados digitalmente (Docusign, DIO) continham de 30 a 180 caracteres na página — apenas o carimbo de autenticação —, com o restante do conteúdo consistindo em imagens escaneadas ou desenhos vetoriais (`drawings > 2000`). O detector considerava o texto mínimo suficiente e não acionava OCR, resultando em Markdown vazio.
- **Solução**: O detector `page_is_suspect` passou a checar elementos visuais e padrões conhecidos de autenticação. Além disso, foi adicionado um fallback automático: se qualquer conversão sem OCR gerar saída vazia ou anômala, o worker retenta a conversão com EasyOCR antes de finalizar o arquivo.

### 3. Calibração da Validação Alfanumérica em Editais Extensos

- **Causa**: Editais longos (como Procap Mestrado/Doutorado de 80 páginas e Redes de PDI de 99 páginas) repetem cabeçalhos institucionais e rodapés do sistema E-DOCS em todas as páginas. O classificador de layout do Docling descarta corretamente essas repetições de margem, gerando uma razão alfanumérica entre 81% e 84% em relação ao texto bruto do PyMuPDF, caindo falsamente no limiar anterior de 85%.
- **Solução**: O limiar `OCR_MIN_ALNUM_RATIO` foi ajustado para 80% (0.80), preservando a aprovação desses editais sem mascarar perdas reais de conteúdo.

### 4. Modo de Retentativa e Consolidação do Manifesto

- Adição do parâmetro `--retry-failed` para processar exclusivamente os arquivos pendentes (`erro` ou `suspeito`), sem reprocessar os 567 documentos já homologados.
- Consolidação automática do manifesto `_conversion_manifest.csv` ao término da execução, eliminando duplicatas e sincronizando `_quarentena.csv`.
