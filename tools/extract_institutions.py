#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""Minerador de Instituições, Unidades e CNPJs a partir dos textos extraídos da FAPES (raw-text/).

Uso:
    uv run tools/extract_institutions.py [--output tools/institutions_extracted.json] [--csv tools/institutions.csv]
"""
import argparse
import csv
import json
import re
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW_TEXT = ROOT / "raw-text"

CNPJ_REGEX = re.compile(r"\b(\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2})\b")

# Instituições conhecidas e termos frequentes na FAPES
KNOWN_INSTITUTIONS = {
    # ICTs e IES Públicas
    "UFES": {
        "name": "Universidade Federal do Espírito Santo",
        "category": "ICT / IES Pública",
        "esfera": "Federal",
        "aliases": ["UFES", "Universidade Federal do Espírito Santo", "Ufes"],
    },
    "IFES": {
        "name": "Instituto Federal de Educação, Ciência e Tecnologia do Espírito Santo",
        "category": "ICT / IES Pública",
        "esfera": "Federal",
        "aliases": ["IFES", "Instituto Federal do Espírito Santo", "Ifes"],
    },
    "INCAPER": {
        "name": "Instituto Capixaba de Pesquisa, Assistência Técnica e Extensão Rural",
        "category": "ICT Pública Estadual",
        "esfera": "Estadual",
        "aliases": ["INCAPER", "Incaper", "Instituto Capixaba de Pesquisa"],
    },
    "FAMES": {
        "name": "Faculdade de Música do Espírito Santo",
        "category": "IES Pública Estadual",
        "esfera": "Estadual",
        "aliases": ["FAMES", "Fames", "Faculdade de Música do Espírito Santo"],
    },
    "FACELI": {
        "name": "Faculdade de Ensino Superior de Linhares",
        "category": "IES Pública Municipal",
        "esfera": "Municipal",
        "aliases": ["FACELI", "Faceli"],
    },
    "ICEPI": {
        "name": "Instituto Capixaba de Ensino, Pesquisa e Inovação em Saúde",
        "category": "ICT Pública Estadual / Saúde",
        "esfera": "Estadual",
        "aliases": ["ICEPi", "ICEPI", "Instituto Capixaba de Ensino, Pesquisa e Inovação em Saúde"],
    },
    # IES Privadas e Comunitárias
    "UVV": {
        "name": "Universidade Vila Velha",
        "category": "IES Privada",
        "esfera": "Privada",
        "aliases": ["UVV", "Universidade Vila Velha"],
    },
    "EMESCAM": {
        "name": "Escola Superior de Ciências da Santa Casa de Misericórdia de Vitória",
        "category": "IES Privada / Filantrópica",
        "esfera": "Privada",
        "aliases": ["EMESCAM", "Emescam"],
    },
    "FAESA": {
        "name": "Centro Universitário FAESA",
        "category": "IES Privada",
        "esfera": "Privada",
        "aliases": ["FAESA", "Faesa"],
    },
    "FUCAPE": {
        "name": "FUCAPE Business School",
        "category": "IES Privada",
        "esfera": "Privada",
        "aliases": ["FUCAPE", "Fucape"],
    },
    "MULTIVIX": {
        "name": "Faculdade Multivix",
        "category": "IES Privada",
        "esfera": "Privada",
        "aliases": ["MULTIVIX", "Multivix"],
    },
    "UNESC": {
        "name": "Centro Universitário do Espírito Santo",
        "category": "IES Privada",
        "esfera": "Privada",
        "aliases": ["UNESC", "Unesc"],
    },
    "FDV": {
        "name": "Faculdade de Direito de Vitória",
        "category": "IES Privada",
        "esfera": "Privada",
        "aliases": ["FDV", "Faculdade de Direito de Vitória"],
    },
    "ESFA": {
        "name": "Escola Superior São Francisco de Assis",
        "category": "IES Privada",
        "esfera": "Privada",
        "aliases": ["ESFA", "Esfa"],
    },
    "FAACZ": {
        "name": "Faculdades Integradas de Aracruz",
        "category": "IES Privada",
        "esfera": "Privada",
        "aliases": ["FAACZ", "Faacz"],
    },
    "CETEM": {
        "name": "Centro Tecnológico do Mármore e Granito",
        "category": "ICT / Centro Tecnológico",
        "esfera": "Privada",
        "aliases": ["CETEM", "Cetem"],
    },
    "UNISALES": {
        "name": "Centro Universitário Salesiano",
        "category": "IES Privada",
        "esfera": "Privada",
        "aliases": ["UNISALES", "Unisales", "Salesiano"],
    },
    "SAO CAMILO": {
        "name": "Centro Universitário São Camilo",
        "category": "IES Privada",
        "esfera": "Privada",
        "aliases": ["São Camilo", "Sao Camilo"],
    },
    # Fundações de Apoio
    "FEST": {
        "name": "Fundação Espírito-Santense de Tecnologia",
        "category": "Fundação de Apoio (UFES)",
        "esfera": "Privada",
        "aliases": ["FEST", "Fest", "Fundação Espírito-Santense de Tecnologia"],
    },
    "FACTO": {
        "name": "Fundação de Apoio ao Desenvolvimento da Ciência e Tecnologia (IFES)",
        "category": "Fundação de Apoio (IFES)",
        "esfera": "Privada",
        "aliases": ["FACTO", "Facto"],
    },
    "FCAA": {
        "name": "Fundação Ceciliano Abel de Almeida",
        "category": "Fundação de Apoio (UFES)",
        "esfera": "Privada",
        "aliases": ["FCAA", "Fundação Ceciliano Abel de Almeida"],
    },
    # Órgãos Públicos Estaduais
    "SEDU": {
        "name": "Secretaria de Estado da Educação",
        "category": "Órgão Público Estadual",
        "esfera": "Estadual",
        "aliases": ["SEDU", "Secretaria de Estado da Educação", "Sedu"],
    },
    "SESA": {
        "name": "Secretaria de Estado da Saúde",
        "category": "Órgão Público Estadual",
        "esfera": "Estadual",
        "aliases": ["SESA", "Secretaria de Estado da Saúde", "Sesa"],
    },
    "SEGER": {
        "name": "Secretaria de Estado de Gestão e Recursos Humanos",
        "category": "Órgão Público Estadual",
        "esfera": "Estadual",
        "aliases": ["SEGER", "Secretaria de Estado de Gestão e Recursos Humanos", "Seger"],
    },
    "SEAG": {
        "name": "Secretaria de Estado da Agricultura, Abastecimento, Aquicultura e Pesca",
        "category": "Órgão Público Estadual",
        "esfera": "Estadual",
        "aliases": ["SEAG", "Secretaria de Estado da Agricultura", "Seag"],
    },
    "SECULT": {
        "name": "Secretaria de Estado da Cultura",
        "category": "Órgão Público Estadual",
        "esfera": "Estadual",
        "aliases": ["SECULT", "Secretaria de Estado da Cultura", "Secult"],
    },
    "SECTI": {
        "name": "Secretaria de Estado da Ciência, Tecnologia, Inovação e Educação Profissional",
        "category": "Órgão Público Estadual",
        "esfera": "Estadual",
        "aliases": ["SECTI", "SECTIDES", "Secretaria de Estado da Ciência, Tecnologia"],
    },
    "AGERH": {
        "name": "Agência Estadual de Recursos Hídricos",
        "category": "Órgão Público Estadual / Autarquia",
        "esfera": "Estadual",
        "aliases": ["AGERH", "Agerh"],
    },
    "IDAF": {
        "name": "Instituto de Defesa Agropecuária e Florestal do Espírito Santo",
        "category": "Órgão Público Estadual / Autarquia",
        "esfera": "Estadual",
        "aliases": ["IDAF", "Idaf"],
    },
    "IEMA": {
        "name": "Instituto Estadual de Meio Ambiente e Recursos Hídricos",
        "category": "Órgão Público Estadual / Autarquia",
        "esfera": "Estadual",
        "aliases": ["IEMA", "Iema"],
    },
    "IJSN": {
        "name": "Instituto Jones dos Santos Neves",
        "category": "Órgão Público Estadual / Instituto de Pesquisa",
        "esfera": "Estadual",
        "aliases": ["IJSN", "Ijsn", "Instituto Jones dos Santos Neves"],
    },
    "BANDES": {
        "name": "Banco de Desenvolvimento do Espírito Santo",
        "category": "Instituição Financeira / Governamental",
        "esfera": "Estadual",
        "aliases": ["BANDES", "Bandes"],
    },
    "PRODEST": {
        "name": "Instituto de Tecnologia da Informação e Comunicação do Estado do Espírito Santo",
        "category": "Empresa Pública Estadual de TIC",
        "esfera": "Estadual",
        "aliases": ["PRODEST", "Prodest"],
    },
}

# Expressões regulares para captura de unidades organizacionais
UNIT_PATTERNS = [
    # Pró-reitorias e Reitorias
    (r"\b(Pró-Reitoria de [A-Za-zÀ-ÿ\s/–-]+(?:\([A-Z]+\))?)", "Administrativa"),
    (r"\b(PRPPG|PROEX|PROPLAN|PROAD|PROGRAD)\b", "Administrativa"),
    # NITs e Inovação
    (r"\b(Núcleo de Inovação Tecnológica[A-Za-zÀ-ÿ\s/–-]*|NIT[\s-]+[A-Za-zÀ-ÿ]+|Agência de Inovação[A-Za-zÀ-ÿ\s/–-]*)", "NIT / Inovação"),
    # Centros e Faculdades
    (r"\b(Centro [A-Za-zÀ-ÿ\s/–-]+|Faculdade de [A-Za-zÀ-ÿ\s/–-]+)", "Acadêmica"),
    (r"\b(CCHN|CT|CCS|CCA|CEUNES|CCJE|CEFD|CAR)\b", "Acadêmica"),
    # Departamentos
    (r"\b(Departamento de [A-Za-zÀ-ÿ\s/–-]+)", "Departamento"),
    # Programas de Pós-Graduação (PPGs)
    (r"\b(Programa de Pós-Graduação em [A-Za-zÀ-ÿ\s/–-]+|PPG[A-Z0-9\s/–-]+)", "Pós-Graduação / PPG"),
    # Laboratórios
    (r"\b(Laboratório de [A-Za-zÀ-ÿ\s/–-]+|Lab[A-Za-z0-9À-ÿ\s/–-]+)", "Laboratório"),
    # Campi
    (r"\b(Campus [A-Za-zÀ-ÿ\s/–-]+)", "Campus / Unidade Descentralizada"),
    # Incubadoras
    (r"\b(Incubadora [A-Za-zÀ-ÿ\s/–-]+|TecVitória|Itacaranha)", "Incubadora"),
]

# Padrões de identificação de executora/beneficiada
EXECUTORA_PATTERNS = [
    re.compile(r"Instituição Executora\s*[:–-]?\s*([^\n\r,;.]+)", re.IGNORECASE),
    re.compile(r"Instituição Proponente\s*[:–-]?\s*([^\n\r,;.]+)", re.IGNORECASE),
    re.compile(r"Instituição Beneficiada\s*[:–-]?\s*([^\n\r,;.]+)", re.IGNORECASE),
    re.compile(r"Razão Social\s*[:–-]?\s*([^\n\r,;.]+)", re.IGNORECASE),
    re.compile(r"Nome da Empresa\s*[:–-]?\s*([^\n\r,;.]+)", re.IGNORECASE),
]


JUNK_UNIT_WORDS = [
    "e-docs", "documento original", "tabela", "anexo", "termo", "concess", "distribui",
    "docente", "artigo", "parágrafo", "cláusula", "pesquisa", "pagamento", "foto", "fapes",
    "projeto", "edital", "valor", "recursos", "bolsa", "critério", "cadastrados", "cadastro",
    "relatório", "vigência", "contratação", "prestação", "centro empresarial", "torre norte",
    "dados", "proponente", "beneficiár", "coordenador", "orientador", "stricto sensu"
]


def is_valid_unit(name: str, utype: str) -> bool:
    nl = name.lower()
    if any(jw in nl for jw in JUNK_UNIT_WORDS):
        return False
    if re.match(r"^\d", name) or re.search(r"\d{3,}", name):
        return False
    if len(name.split()) > 7 or len(name) < 4:
        return False

    if utype == "NIT / Inovação":
        if not any(x in nl for x in ["núcleo de inovação tecnológica", "agência de inovação", "nit-"]):
            if nl != "núcleo de inovação tecnológica":
                return False
        if any(bad in nl for bad in ["renato", "art", "informará", "ainda", "apoio", "academia"]):
            return False

    elif utype == "Incubadora":
        if not any(x in nl for x in ["tecvitória", "ifes", "sul capixaba", "growup", "prosperas", "itacaranha"]):
            return False

    elif utype == "Pós-Graduação / PPG":
        valid_ppg = (
            nl.startswith("programa de pós-graduação em ")
            or nl in ["profept", "ppgps"]
            or any(f"ppg {disc}" in nl for disc in ["biotecnologia", "bioquímica", "química", "física", "saúde", "doenças", "educação", "informática"])
        )
        if not valid_ppg:
            return False

    elif utype == "Campus / Unidade Descentralizada":
        valid_campi = ["alegre", "goiabeiras", "maruípe", "são mateus", "vitória", "vila velha", "serra", "cariacica", "colatina", "linhares", "cachoeiro", "itapina", "santa teresa", "venda nova", "aracruz", "guarapari"]
        if not any(c in nl for c in valid_campi):
            return False

    elif utype == "Laboratório":
        valid_labs = ["nb-3", "labtel", "labpetro", "ensaios", "lacen", "lab.ges", "cpid", "labpoca", "espectroscopia", "neurotoxicologia", "biotecnologia", "telecomunicações", "sistemas eletrônicos"]
        if not any(x in nl for x in valid_labs):
            return False

    elif utype == "Acadêmica":
        if name in ["CT", "CCS", "CCHN", "CCE", "CCJE", "CEFD", "CEUNES", "CCAE", "CEET Vasco Coutinho", "CTC", "CDM", "CRJ"]:
            return True
        valid_centers = ["centro tecnológico", "ciências da saúde", "ciências humanas", "ciências exatas", "ciências jurídicas", "ciências agrárias", "educação física", "vasco coutinho", "técnico criativo", "desenvolvimento metalmecânico", "referência das juventudes"]
        if not any(x in nl for x in valid_centers):
            return False

    return True


def extract():
    institution_counts = defaultdict(lambda: {"count": 0, "files": set(), "cnpjs": set(), "units": defaultdict(set)})
    all_cnpjs = defaultdict(lambda: {"files": set(), "contexts": []})
    generic_executors = defaultdict(lambda: {"count": 0, "files": set()})

    for file_path in RAW_TEXT.rglob("*.txt"):
        try:
            text = file_path.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue

        rel_path = file_path.relative_to(ROOT).as_posix()

        # 1. Buscar CNPJs e seus contextos
        for match in CNPJ_REGEX.finditer(text):
            cnpj = match.group(1)
            start = max(0, match.start() - 150)
            end = min(len(text), match.end() + 150)
            context = text[start:end].replace("\n", " ").strip()
            all_cnpjs[cnpj]["files"].add(rel_path)
            if len(all_cnpjs[cnpj]["contexts"]) < 3:
                all_cnpjs[cnpj]["contexts"].append(context)

        # 2. Buscar Instituições Conhecidas
        for inst_key, inst_meta in KNOWN_INSTITUTIONS.items():
            found_in_file = False
            for alias in inst_meta["aliases"]:
                pattern = rf"\b{re.escape(alias)}\b"
                matches = list(re.finditer(pattern, text, re.IGNORECASE if len(alias) > 4 else 0))
                if matches:
                    institution_counts[inst_key]["count"] += len(matches)
                    institution_counts[inst_key]["files"].add(rel_path)
                    found_in_file = True

                    # Se achou no arquivo, procura CNPJs perto (até 300 caracteres)
                    for m in matches:
                        w_start = max(0, m.start() - 300)
                        w_end = min(len(text), m.end() + 300)
                        window = text[w_start:w_end]
                        for c_match in CNPJ_REGEX.finditer(window):
                            institution_counts[inst_key]["cnpjs"].add(c_match.group(1))

            # 3. Buscar Unidades para instituições encontradas
            if found_in_file:
                for unit_regex, unit_type in UNIT_PATTERNS:
                    for u_match in re.finditer(unit_regex, text, re.IGNORECASE):
                        unit_name = u_match.group(1).strip()
                        unit_clean = re.sub(r"\s+", " ", unit_name).strip(" -:;,.")
                        if is_valid_unit(unit_clean, unit_type):
                            institution_counts[inst_key]["units"][unit_type].add(unit_clean)

        # 4. Buscar cláusulas explícitas de Executora / Razão Social
        for pat in EXECUTORA_PATTERNS:
            for m in pat.finditer(text):
                candidate = m.group(1).strip()
                cand_clean = re.sub(r"\s+", " ", candidate).strip(" -:;,.")
                if (
                    4 < len(cand_clean) < 70
                    and not cand_clean.startswith("[")
                    and not any(bad in cand_clean.lower() for bad in ["sistema", "anuência", "anuencia", "sigfapes", "prestar", "prejuízo"])
                ):
                    generic_executors[cand_clean]["count"] += 1
                    generic_executors[cand_clean]["files"].add(rel_path)

    return institution_counts, all_cnpjs, generic_executors


def main():
    parser = argparse.ArgumentParser(description="Extrai instituições e unidades.")
    parser.add_argument("--json", default="tools/institutions_extracted.json", help="Arquivo JSON de saída.")
    parser.add_argument("--csv", default="tools/institutions_extracted.csv", help="Arquivo CSV de saída.")
    args = parser.parse_args()

    print("Iniciando extração em raw-text/...")
    inst_counts, cnpjs, generic_execs = extract()

    # Formatar para saída serializável
    out_data = {
        "institutions": {},
        "top_generic_executors": [],
        "cnpjs_detected": {},
    }

    for k, data in inst_counts.items():
        meta = KNOWN_INSTITUTIONS.get(k, {})
        out_data["institutions"][k] = {
            "name": meta.get("name", k),
            "category": meta.get("category", "Outra"),
            "esfera": meta.get("esfera", "N/A"),
            "occurrences": data["count"],
            "files_count": len(data["files"]),
            "cnpjs": list(data["cnpjs"]),
            "sample_files": sorted(list(data["files"]))[:5],
            "units": {utype: sorted(list(ulist))[:30] for utype, ulist in data["units"].items() if ulist},
        }

    # Top executores genéricos / empresas
    for cand, cdata in sorted(generic_execs.items(), key=lambda x: x[1]["count"], reverse=True)[:60]:
        out_data["top_generic_executors"].append({
            "name": cand,
            "count": cdata["count"],
            "files_count": len(cdata["files"]),
            "sample_files": sorted(list(cdata["files"]))[:3],
        })

    # CNPJs com contexto
    for cnpj, cinfo in sorted(cnpjs.items(), key=lambda x: len(x[1]["files"]), reverse=True)[:50]:
        out_data["cnpjs_detected"][cnpj] = {
            "files_count": len(cinfo["files"]),
            "sample_contexts": cinfo["contexts"][:2],
        }

    out_json = ROOT / args.json
    out_json.write_text(json.dumps(out_data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Resultado salvo em {out_json}")

    # Salvar CSV resumido das instituições
    out_csv = ROOT / args.csv
    with open(out_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["Sigla", "Nome", "Categoria", "Esfera", "Ocorrencias", "Arquivos", "CNPJs", "Qtd_Unidades_Mapeadas"])
        for k, v in out_data["institutions"].items():
            total_units = sum(len(ulist) for ulist in v["units"].values())
            writer.writerow([
                k,
                v["name"],
                v["category"],
                v["esfera"],
                v["occurrences"],
                v["files_count"],
                "; ".join(v["cnpjs"]),
                total_units,
            ])
    print(f"CSV salvo em {out_csv}")


if __name__ == "__main__":
    main()
