#!/usr/bin/env python3
"""Avaliação e mineração contextual de Instituições e suas Unidades em raw-md/.

Processa os 580 arquivos markdown convertidos via Docling, respeitando as fronteiras
de páginas (<!-- page N -->), seções e tabelas para vincular estritamente cada unidade
organizacional à sua respectiva instituição mãe (sem vazamento interinstitucional).
"""
import glob
import json
import re
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW_MD = ROOT / "raw-md"

# Definição das instituições a rastrear
INSTITUTIONS = {
    # 1. ICTs e IES Públicas
    "UFES": {
        "name": "Universidade Federal do Espírito Santo",
        "category": "ICT / IES Pública Federal",
        "esfera": "Federal",
        "aliases": [r"\bUFES\b", r"\bUfes\b", r"Universidade Federal do Espírito Santo"],
    },
    "IFES": {
        "name": "Instituto Federal de Educação, Ciência e Tecnologia do Espírito Santo",
        "category": "ICT / IES Pública Federal",
        "esfera": "Federal",
        "aliases": [r"\bIFES\b", r"\bIfes\b", r"Instituto Federal do Espírito Santo", r"Instituto Federal de Educação, Ciência e Tecnologia do Espírito Santo"],
    },
    "INCAPER": {
        "name": "Instituto Capixaba de Pesquisa, Assistência Técnica e Extensão Rural",
        "category": "ICT Pública Estadual",
        "esfera": "Estadual",
        "aliases": [r"\bINCAPER\b", r"\bIncaper\b", r"Instituto Capixaba de Pesquisa"],
    },
    "FAMES": {
        "name": "Faculdade de Música do Espírito Santo",
        "category": "IES Pública Estadual",
        "esfera": "Estadual",
        "aliases": [r"\bFAMES\b", r"\bFames\b", r"Faculdade de Música do Espírito Santo"],
    },
    "FACELI": {
        "name": "Faculdade de Ensino Superior de Linhares",
        "category": "IES Pública Municipal",
        "esfera": "Municipal",
        "aliases": [r"\bFACELI\b", r"\bFaceli\b", r"Faculdade de Ensino Superior de Linhares"],
    },
    "ICEPI": {
        "name": "Instituto Capixaba de Ensino, Pesquisa e Inovação em Saúde",
        "category": "ICT Pública Estadual / Saúde (SESA)",
        "esfera": "Estadual",
        "aliases": [r"\bICEPi\b", r"\bICEPI\b", r"Instituto Capixaba de Ensino, Pesquisa e Inovação em Saúde"],
    },
    # 2. IES Privadas, Comunitárias e Confessionais
    "UVV": {
        "name": "Universidade Vila Velha",
        "category": "IES Privada / Comunitária",
        "esfera": "Privada",
        "aliases": [r"\bUVV\b", r"Universidade Vila Velha"],
    },
    "EMESCAM": {
        "name": "Escola Superior de Ciências da Santa Casa de Misericórdia de Vitória",
        "category": "IES Privada / Filantrópica",
        "esfera": "Privada",
        "aliases": [r"\bEMESCAM\b", r"\bEmescam\b", r"Escola Superior de Ciências da Santa Casa de Misericórdia de Vitória"],
    },
    "FAESA": {
        "name": "Centro Universitário FAESA",
        "category": "IES Privada",
        "esfera": "Privada",
        "aliases": [r"\bFAESA\b", r"\bFaesa\b", r"UNICAPE\s*-\s*FAESA"],
    },
    "FUCAPE": {
        "name": "FUCAPE Business School",
        "category": "IES Privada",
        "esfera": "Privada",
        "aliases": [r"\bFUCAPE\b", r"\bFucape\b", r"Fundação Instituto Capixaba de Pesquisas em Contabilidade"],
    },
    "MULTIVIX": {
        "name": "Faculdade / Centro Universitário Multivix",
        "category": "IES Privada",
        "esfera": "Privada",
        "aliases": [r"\bMULTIVIX\b", r"\bMultivix\b", r"UNES\s*-\s*MULTIVIX", r"FSG\s*-\s*MULTIVIX"],
    },
    "UNESC": {
        "name": "Centro Universitário do Espírito Santo",
        "category": "IES Privada / Comunitária",
        "esfera": "Privada",
        "aliases": [r"\bUNESC\b", r"\bUnesc\b", r"Centro Universitário do Espírito Santo"],
    },
    "FDV": {
        "name": "Faculdade de Direito de Vitória",
        "category": "IES Privada",
        "esfera": "Privada",
        "aliases": [r"\bFDV\b", r"Faculdade de Direito de Vitória"],
    },
    "ESFA": {
        "name": "Escola Superior São Francisco de Assis",
        "category": "IES Privada / Confessional",
        "esfera": "Privada",
        "aliases": [r"\bESFA\b", r"\bEsfa\b", r"Escola Superior São Francisco de Assis"],
    },
    "FAACZ": {
        "name": "Faculdades Integradas de Aracruz",
        "category": "IES Privada / Comunitária (Fundação São João Batista)",
        "esfera": "Privada",
        "aliases": [r"\bFAACZ\b", r"\bFaacz\b", r"Faculdades Integradas de Aracruz"],
    },
    "SAO_CAMILO": {
        "name": "Centro Universitário São Camilo - Espírito Santo",
        "category": "IES Privada / Confessional",
        "esfera": "Privada",
        "aliases": [r"São Camilo", r"Sao Camilo", r"Centro Universitário São Camilo"],
    },
    "UNISALES": {
        "name": "Centro Universitário Salesiano",
        "category": "IES Privada / Confessional",
        "esfera": "Privada",
        "aliases": [r"\bUNISALES\b", r"\bUnisales\b", r"Católica Salesiana", r"Faculdade Católica Salesiana"],
    },
    "ESTACIO": {
        "name": "Faculdade Estácio de Sá (Vitória e Vila Velha)",
        "category": "IES Privada",
        "esfera": "Privada",
        "aliases": [r"Estácio de Sá", r"Estacio de Sa", r"\bEstácio\b", r"\bEstacio\b"],
    },
    "FACULDADE_AMERICA": {
        "name": "Faculdade América",
        "category": "IES Privada",
        "esfera": "Privada",
        "aliases": [r"FACULDADE AMÉRICA", r"Faculdade América", r"Faculdade America"],
    },
    "PIO_XII": {
        "name": "Faculdade Pio XII",
        "category": "IES Privada",
        "esfera": "Privada",
        "aliases": [r"PIO XII", r"Pio XII", r"Faculdade Pio XII"],
    },
    "VALE_DO_CRICARE": {
        "name": "Centro Universitário Vale do Cricaré (UNIVC)",
        "category": "IES Privada",
        "esfera": "Privada",
        "aliases": [r"VALE DO CRICARÉ", r"Vale do Cricaré", r"Vale do Cricare", r"\bIVC\b", r"\bUNIVC\b"],
    },
    "FAVENI": {
        "name": "Faculdade Venda Nova do Imigrante (FAVENI)",
        "category": "IES Privada",
        "esfera": "Privada",
        "aliases": [r"\bFAVENI\b", r"\bFaveni\b", r"Faculdade Venda Nova do Imigrante"],
    },
    # 3. Fundações de Apoio
    "FEST": {
        "name": "Fundação Espírito-Santense de Tecnologia",
        "category": "Fundação de Apoio (UFES)",
        "esfera": "Privada (Sem fins lucrativos)",
        "aliases": [r"\bFEST\b", r"Fundação Espírito-Santense de Tecnologia"],
    },
    "FACTO": {
        "name": "Fundação de Apoio ao Desenvolvimento da Ciência e Tecnologia",
        "category": "Fundação de Apoio (IFES)",
        "esfera": "Privada (Sem fins lucrativos)",
        "aliases": [r"\bFACTO\b", r"Fundação de Apoio ao Desenvolvimento da Ciência e Tecnologia"],
    },
    "FCAA": {
        "name": "Fundação Ceciliano Abel de Almeida",
        "category": "Fundação de Apoio (UFES)",
        "esfera": "Privada (Sem fins lucrativos)",
        "aliases": [r"\bFCAA\b", r"Fundação Ceciliano Abel de Almeida"],
    },
    "FUNDAG": {
        "name": "Fundação de Apoio à Pesquisa Agrícola",
        "category": "Fundação de Apoio (INCAPER)",
        "esfera": "Privada (Sem fins lucrativos)",
        "aliases": [r"\bFUNDAG\b", r"Fundação de Apoio à Pesquisa Agrícola"],
    },
    # 4. Órgãos Públicos Estaduais (Demandantes e Parceiros)
    "SECTI": {
        "name": "Secretaria de Estado da Ciência, Tecnologia, Inovação e Educação Profissional",
        "category": "Órgão Público Estadual / Vinculador",
        "esfera": "Estadual",
        "aliases": [r"\bSECTI\b", r"\bSECTIDES\b", r"Secretaria de Estado da Ciência, Tecnologia"],
    },
    "SEDU": {
        "name": "Secretaria de Estado da Educação",
        "category": "Órgão Público Estadual / Demandante",
        "esfera": "Estadual",
        "aliases": [r"\bSEDU\b", r"\bSedu\b", r"Secretaria de Estado da Educação", r"Secretaria da Educação do Espírito Santo"],
    },
    "SESA": {
        "name": "Secretaria de Estado da Saúde",
        "category": "Órgão Público Estadual / Demandante",
        "esfera": "Estadual",
        "aliases": [r"\bSESA\b", r"\bSesa\b", r"Secretaria de Estado da Saúde"],
    },
    "SEGER": {
        "name": "Secretaria de Estado de Gestão e Recursos Humanos",
        "category": "Órgão Público Estadual / Demandante",
        "esfera": "Estadual",
        "aliases": [r"\bSEGER\b", r"\bSeger\b", r"Secretaria de Estado de Gestão e Recursos Humanos"],
    },
    "SEAG": {
        "name": "Secretaria de Estado da Agricultura, Abastecimento, Aquicultura e Pesca",
        "category": "Órgão Público Estadual / Demandante",
        "esfera": "Estadual",
        "aliases": [r"\bSEAG\b", r"\bSeag\b", r"Secretaria de Estado da Agricultura"],
    },
    "SECULT": {
        "name": "Secretaria de Estado da Cultura",
        "category": "Órgão Público Estadual / Demandante",
        "esfera": "Estadual",
        "aliases": [r"\bSECULT\b", r"\bSecult\b", r"Secretaria de Estado da Cultura"],
    },
    "AGERH": {
        "name": "Agência Estadual de Recursos Hídricos",
        "category": "Órgão Público Estadual / Autarquia",
        "esfera": "Estadual",
        "aliases": [r"\bAGERH\b", r"\bAgerh\b", r"Agência Estadual de Recursos Hídricos"],
    },
    "IDAF": {
        "name": "Instituto de Defesa Agropecuária e Florestal do Espírito Santo",
        "category": "Órgão Público Estadual / Autarquia",
        "esfera": "Estadual",
        "aliases": [r"\bIDAF\b", r"\bIdaf\b", r"Instituto de Defesa Agropecuária e Florestal"],
    },
    "IEMA": {
        "name": "Instituto Estadual de Meio Ambiente e Recursos Hídricos",
        "category": "Órgão Público Estadual / Autarquia",
        "esfera": "Estadual",
        "aliases": [r"\bIEMA\b", r"\bIema\b", r"Instituto Estadual de Meio Ambiente e Recursos Hídricos"],
    },
    "IJSN": {
        "name": "Instituto Jones dos Santos Neves",
        "category": "Órgão Público Estadual / Autarquia e Pesquisa",
        "esfera": "Estadual",
        "aliases": [r"\bIJSN\b", r"\bIjsn\b", r"Instituto Jones dos Santos Neves"],
    },
    "BANDES": {
        "name": "Banco de Desenvolvimento do Espírito Santo",
        "category": "Instituição Financeira Oficial Estadual",
        "esfera": "Estadual",
        "aliases": [r"\bBANDES\b", r"\bBandes\b", r"Banco de Desenvolvimento do Espírito Santo"],
    },
    "PRODEST": {
        "name": "Instituto de Tecnologia da Informação e Comunicação do Estado do ES",
        "category": "Empresa Pública Estadual de TIC",
        "esfera": "Estadual",
        "aliases": [r"\bPRODEST\b", r"\bProdest\b", r"Instituto de Tecnologia da Informação e Comunicação"],
    },
    # 5. Empresas e Parceiras Industriais
    "ARCELORMITTAL": {
        "name": "ArcelorMittal Brasil / Tubarão",
        "category": "Empresa Privada / Parceira Coinvestidora",
        "esfera": "Privada",
        "aliases": [r"ArcelorMittal", r"Arcelor Mittal", r"CST\b"],
    },
    "VALE": {
        "name": "Vale S.A.",
        "category": "Empresa Privada / Parceira Coinvestidora",
        "esfera": "Privada",
        "aliases": [r"\bVale S\.A\.", r"\bCompanhia Vale do Rio Doce\b"],
    },
    "SUZANO": {
        "name": "Suzano S.A.",
        "category": "Empresa Privada / Parceira Coinvestidora",
        "esfera": "Privada",
        "aliases": [r"\bSuzano\b", r"Suzano Papel e Celulose", r"Fibria\b", r"Aracruz Celulose"],
    },
    "PETROBRAS": {
        "name": "Petróleo Brasileiro S.A. (Petrobras)",
        "category": "Sociedade de Economia Mista / Parceira Coinvestidora",
        "esfera": "Federal / Mista",
        "aliases": [r"\bPetrobras\b", r"Petróleo Brasileiro"],
    },
    "ES_GAS": {
        "name": "Companhia de Gás do Espírito Santo (ES GÁS)",
        "category": "Empresa Privada Concessionária",
        "esfera": "Privada",
        "aliases": [r"ES GÁS", r"ES GAS", r"Companhia de Gás do Espírito Santo"],
    },
    "TECVITORIA": {
        "name": "Associação TecVitória (Parque Tecnológico / Incubadora)",
        "category": "Ambiente Promotor de Inovação / Terceiro Setor",
        "esfera": "Privada (Sem fins lucrativos)",
        "aliases": [r"TecVitória", r"TecVitoria", r"Associação TecVitória"],
    },
}

# Padrões para extração contextual de unidades
UNIT_EXTRACTORS = [
    # Pró-Reitorias
    (r"\b(Pró-Reitoria de [A-Za-zÀ-ÿ\s/–-]+(?:\([A-Z]+\))?|PRPPG|PROEX|PROPLAN|PROAD|PROGRAD)\b", "Administrativa"),
    # NITs e Inovação
    (r"\b(Núcleo de Inovação Tecnológica[A-Za-zÀ-ÿ\s/–-]*|INIT-Ufes|Agifes|Inova UVV|Hub Fucape|NIT-Incaper|Agência de Inovação[A-Za-zÀ-ÿ\s/–-]*)", "NIT / Inovação"),
    # Centros de Ensino / Acadêmicas
    (r"\b(Centro [A-Za-zÀ-ÿ\s/–-]+|Faculdade de [A-Za-zÀ-ÿ\s/–-]+|CCHN|CT|CCS|CCE|CCJE|CEFD|CEUNES|CCAE|CEET Vasco Coutinho|Centro Técnico Criativo)\b", "Acadêmica"),
    # Departamentos
    (r"\b(Departamento de [A-Za-zÀ-ÿ\s/–-]+)\b", "Departamento"),
    # PPGs
    (r"\b(Programa de Pós-Graduação em [A-Za-zÀ-ÿ\s/–-]+|PPG[A-Z0-9\s/–-]+|ProfEPT)\b", "Pós-Graduação / PPG"),
    # Laboratórios
    (r"\b(Laboratório de [A-Za-zÀ-ÿ\s/–-]+|LabTel|LabPetro|Lab NB-3|LabPOC|Lab\.GES|LACEN)\b", "Laboratório"),
    # Campi
    (r"\b(Campus [A-Za-zÀ-ÿ\s/–-]+|Campi [A-Za-zÀ-ÿ\s/–-]+)\b", "Campus"),
    # Fazendas Experimentais
    (r"\b(Fazenda Experimental [A-Za-zÀ-ÿ\s/–-]+|Centro Regional de Desenvolvimento Rural[A-Za-zÀ-ÿ\s/–-]*|CRDR[A-Za-zÀ-ÿ\s/–-]*)\b", "Estação de Pesquisa / Fazenda"),
]

def clean_unit_name(u: str) -> str:
    u = re.sub(r"\s+", " ", u).strip(" -:;,.*#|()[]\"'")
    # Remove junk endings
    u = re.sub(r"\s+(da|do|de|e|com|em)$", "", u, flags=re.IGNORECASE)
    return u

def is_valid_unit(u: str, utype: str) -> bool:
    if len(u) < 3 or len(u) > 75:
        return False
    ul = u.lower()
    junk = ["edital", "termo", "concess", "artigo", "parágrafo", "cláusula", "recurso", "anexo", "critério", "cadastro", "pesquisa para o sus"]
    if utype != "NIT / Inovação" and any(jw in ul for jw in junk):
        return False
    return True

def run_extraction():
    results = {}
    for inst_id, meta in INSTITUTIONS.items():
        results[inst_id] = {
            "name": meta["name"],
            "category": meta["category"],
            "esfera": meta["esfera"],
            "occurrences": 0,
            "files": set(),
            "citations": [], # list of (file, page)
            "units": defaultdict(set),
        }

    compiled_aliases = {
        inst_id: [re.compile(a, re.IGNORECASE if len(a) > 4 else 0) for a in meta["aliases"]]
        for inst_id, meta in INSTITUTIONS.items()
    }

    all_md = sorted(glob.glob("raw-md/**/*.md", recursive=True))
    print(f"Processando {len(all_md)} arquivos markdown em raw-md/...")

    for fpath in all_md:
        try:
            content = open(fpath, encoding="utf-8", errors="replace").read()
        except Exception:
            continue

        rel_path = Path(fpath).as_posix()

        # Quebrar documento em blocos delimitados por páginas ou seções
        # Cada bloco preserva o número da página
        page_splits = re.split(r"(<!-- page (\d+) -->)", content)
        
        current_page = 1
        blocks = []
        i = 0
        if len(page_splits) == 1:
            blocks.append((1, content))
        else:
            # page_splits[0] is pre-page text
            if page_splits[0].strip():
                blocks.append((1, page_splits[0]))
            i = 1
            while i < len(page_splits):
                current_page = int(page_splits[i+1])
                block_content = page_splits[i+2] if i+2 < len(page_splits) else ""
                blocks.append((current_page, block_content))
                i += 3

        # Para cada bloco de página, procurar quebras por parágrafos/seções
        for page_num, block in blocks:
            # Se for tabela do Nossa Bolsa, tratar linha a linha!
            if "| " in block and any(x in block.lower() for x in ["curso", "vagas", "município", "turno", "ies"]):
                for line in block.split("\n"):
                    if not line.strip().startswith("|"):
                        continue
                    cols = [c.strip() for c in line.split("|")]
                    line_str = " ".join(cols)
                    for inst_id, regexes in compiled_aliases.items():
                        if any(r.search(line_str) for r in regexes):
                            results[inst_id]["occurrences"] += 1
                            results[inst_id]["files"].add(rel_path)
                            if len(results[inst_id]["citations"]) < 5:
                                results[inst_id]["citations"].append(f"{rel_path}, p. {page_num}")
                            # Se a linha tem município ou campus, capturar
                            for col in cols:
                                if any(x in col.lower() for x in ["campus", "faculdade", "unes", "fsg", "colatina", "serra", "cachoeiro", "aracruz", "linhare"]):
                                    clean_c = clean_unit_name(col)
                                    if 3 < len(clean_c) < 50:
                                        results[inst_id]["units"]["Campus"].add(clean_c)

            # Sub-blocos por seções ou parágrafos de ~500 caracteres
            paragraphs = block.split("\n\n")
            for para in paragraphs:
                para_clean = para.strip()
                if not para_clean:
                    continue

                # Checar quais instituições são citadas NESTE parágrafo
                para_matched_insts = []
                for inst_id, regexes in compiled_aliases.items():
                    for r in regexes:
                        if r.search(para_clean):
                            para_matched_insts.append(inst_id)
                            results[inst_id]["occurrences"] += 1
                            results[inst_id]["files"].add(rel_path)
                            if len(results[inst_id]["citations"]) < 5:
                                results[inst_id]["citations"].append(f"{rel_path}, p. {page_num}")
                            break

                # Se houver correspondência de UMA ou POUCAS instituições no parágrafo,
                # procurar unidades que estejam no mesmo parágrafo
                if 1 <= len(para_matched_insts) <= 2:
                    for u_regex, u_type in UNIT_EXTRACTORS:
                        for u_match in re.finditer(u_regex, para_clean, re.IGNORECASE):
                            raw_u = u_match.group(1).strip()
                            clean_u = clean_unit_name(raw_u)
                            if is_valid_unit(clean_u, u_type):
                                for matched_id in para_matched_insts:
                                    results[matched_id]["units"][u_type].add(clean_u)

    return results

if __name__ == "__main__":
    data = run_extraction()
    out = {}
    for k, v in data.items():
        out[k] = {
            "name": v["name"],
            "category": v["category"],
            "esfera": v["esfera"],
            "occurrences": v["occurrences"],
            "files_count": len(v["files"]),
            "sample_citations": v["citations"],
            "units": {utype: sorted(list(ulist)) for utype, ulist in v["units"].items() if ulist}
        }
    out_file = ROOT / "tools" / "institutions_raw_md_evaluated.json"
    out_file.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Avaliação concluída e salva em {out_file}!")
