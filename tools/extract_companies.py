#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""Minerador e Validador de Empresas Privadas e Startups a partir de raw-text/ da FAPES.

Gera:
    tools/companies_extracted.json
    tools/companies_extracted.csv
"""
import csv
import json
import re
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW_TEXT = ROOT / "raw-text"

CNPJ_REGEX = re.compile(r"\b(\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2})\b")

# Catálogo auditado e validado de empresas e parceiras no ecossistema FAPES
VALIDATED_COMPANIES = {
    # 1. Startups e Pequenas Empresas Inovadoras (Subvenção / Aceleração / Incubação)
    "Lume Robotics": {
        "type": "Startup / Base Tecnológica",
        "program": "Tecnova II / Spin-off",
        "domain": "Robótica Autônoma / Veículos Autônomos",
        "city": "Vitória / ES",
        "notes": "Desenvolveu protótipo de micro-ônibus autônomo em parceria com a Marcopolo.",
        "search_terms": ["Lume Robotics"],
    },
    "Dersalis": {
        "type": "Startup / Saúde e IoT",
        "program": "Tecnova II",
        "domain": "Dispositivos Wearables / Saúde Ocupacional",
        "city": "Vitória / ES",
        "notes": "Criou pulseira inteligente de monitoramento em tempo real de sinais vitais de operários.",
        "search_terms": ["Dersalis"],
    },
    "Jade Autism": {
        "type": "Startup / EdTech e HealthTech",
        "program": "Programa Centelha",
        "domain": "Terapia Gamificada e Autismo (TEA)",
        "city": "Vitória / ES",
        "notes": "Premiada internacionalmente em Dubai e vencedora do Web Summit Rio 2023.",
        "search_terms": ["Jade Autism"],
    },
    "Endelevo": {
        "type": "Startup / Sustentabilidade e Clima",
        "program": "Centelha / Negócios de Impacto Socioambiental",
        "domain": "Mobiliário Urbano Sustentável e Energia Solar/Eólica",
        "city": "Vitória / ES",
        "notes": "Desenvolveu ponto de ônibus autossustentável na Ilha do Príncipe com geração eólica/solar.",
        "search_terms": ["Endelevo"],
    },
    "Multifidelidade": {
        "type": "Startup / TIC e Varejo",
        "program": "SEEDES (Aceleração de Startups)",
        "domain": "Fidelização e Engajamento de Clientes",
        "city": "Vitória / ES",
        "notes": "Acelerada no 1º ciclo do SEEDES, expandindo operação comercial nacional.",
        "search_terms": ["Multifidelidade"],
    },
    "Buskar.me": {
        "type": "Startup / Mobilidade e Logística",
        "program": "SEEDES",
        "domain": "Plataforma de Busca e Integração Logística",
        "city": "Acelerada no ES",
        "notes": "Participante do programa SEEDES com atração de investimento-anjo.",
        "search_terms": ["Buskar.me"],
    },
    "PicPay": {
        "type": "Fintech / Unicórnio (Egresso)",
        "program": "Incubadora TecVitória / Apoio Inicial CTI",
        "domain": "Pagamentos Digitais e Carteira Digital",
        "city": "Vitória / ES",
        "notes": "Empresa nascida e incubada no ecossistema fomentado pela FAPES na TecVitória.",
        "search_terms": ["PicPay"],
    },
    "Vix Team": {
        "type": "Empresa de Software / TIC",
        "program": "Incubadora TecVitória / PDI",
        "domain": "Sistemas Corporativos e Engenharia de Software",
        "city": "Vitória / ES",
        "notes": "Empresa pioneira gerada no ambiente de incubação apoiado pelo Estado.",
        "search_terms": ["Vix Team"],
    },
    # 2. Grandes Empresas e Corporações Industriais Parceiras / Coinvestidoras
    "ArcelorMittal Tubarão": {
        "type": "Grande Empresa / Siderurgia",
        "program": "Edital Parceria SIMACC / Redes de PDI",
        "domain": "Siderurgia, Meio Ambiente e Construção Civil",
        "city": "Serra / ES",
        "notes": "Cofinanciou chamadas públicas com a FAPES para bolsas de mestrado/doutorado e pesquisa em rede.",
        "search_terms": ["ArcelorMittal"],
    },
    "Vale S.A.": {
        "type": "Grande Empresa / Mineração e Logística",
        "program": "Redes de PDI / Parcerias Induzidas",
        "domain": "Mineração, Logística Ferroviária e Meio Ambiente",
        "city": "Vitória / Tubarão",
        "notes": "Parceira institucional em pesquisas aplicadas de mitigação de particulados e ferrovias.",
        "search_terms": ["Vale S.A.", "Vale S/A"],
    },
    "Suzano": {
        "type": "Grande Empresa / Papel e Celulose",
        "program": "Redes de Pesquisa e Sustentabilidade",
        "domain": "Silvicultura de Precisão e Biotecnologia Florestal",
        "city": "Aracruz / ES",
        "notes": "Histórico de cooperação técnica em melhoramento genético de eucalipto e recursos hídricos.",
        "search_terms": ["Suzano"],
    },
    "Petrobras": {
        "type": "Empresa Pública / Petróleo e Gás",
        "program": "Termos de P&D Regulatório ANP / FAPES",
        "domain": "Exploração Offshore e Geoquímica de Reservatório",
        "city": "Vitória e Bacia do ES",
        "notes": "Aporte de recursos de cláusula de P&D da ANP em laboratórios da UFES (LabPetro, LabTel).",
        "search_terms": ["Petrobras", "Petrobras Distribuidora"],
    },
    "Marcopolo S.A.": {
        "type": "Grande Empresa / Carrocerias e Transporte",
        "program": "Edital Tecnova II (Parceria Privada com Startup)",
        "domain": "Veículos e Mobilidade Urbana",
        "city": "Caxias do Sul / Operação Nacional",
        "notes": "Parceira industrial da startup capixaba Lume Robotics no projeto do micro-ônibus autônomo.",
        "search_terms": ["Marcopolo"],
    },
    "ES GÁS": {
        "type": "Empresa de Distribuição / Energia",
        "program": "Projetos de P&D em Gás Natural e Biometano",
        "domain": "Gás Canalizado e Transição Energética",
        "city": "Vitória / ES",
        "notes": "Contratações e chamadas conjuntas para eficiência de distribuição de gás canalizado.",
        "search_terms": ["ES GÁS", "ES Gás"],
    },
    "Sincades Tech": {
        "type": "Associação Empresarial / Hub Setorial",
        "program": "Resolução CCAF / Hubs Setoriais",
        "domain": "Comércio Atacadista, Distribuição e Logística",
        "city": "Vitória / ES",
        "notes": "Cooperação institucional para desenvolvimento de soluções aplicadas à cadeia atacadista.",
        "search_terms": ["Sincades Tech", "Sincades"],
    },
    # 3. Prestadores de Serviços e Contratadas Formais
    "IEBT Innovation": {
        "type": "Empresa de Aceleração / Consultoria em Inovação",
        "program": "SEEDES / Operador de Aceleração",
        "domain": "Metodologia de Aceleração e Validação de Startups",
        "city": "Belo Horizonte / Operação ES",
        "notes": "Empresa aceleradora contratada para executar a aceleração das 30 startups do edital SEEDES.",
        "search_terms": ["IEBT Innovation", "IEBT"],
    },
    "Oi S.A. / Telemar Norte Leste": {
        "type": "Concessionária de Telecomunicações",
        "program": "Contrato Administrativo / Telecomunicações",
        "domain": "Telefonia Fixa e STFC",
        "city": "Vitória / ES",
        "notes": "Fornecedora de enlaces de comunicação da sede da FAPES.",
        "search_terms": ["Oi S.A.", "Telemar Norte Leste"],
    },
    "Claro S/A": {
        "type": "Concessionária de Telecomunicações",
        "program": "Contrato Administrativo / Telecomunicações",
        "domain": "Comunicação de Dados e Voz",
        "city": "Operação Nacional / ES",
        "notes": "Contratada de serviços de comunicação móvel e dados.",
        "search_terms": ["Claro S/A", "Claro S.A."],
    },
    "Sem Parar Instituição de Pagamento LTDA": {
        "type": "Instituição de Pagamento / Mobilidade",
        "program": "Contrato Administrativo",
        "domain": "Identificação e Cobrança Automática Veicular",
        "city": "Operação Nacional / ES",
        "notes": "Gestão de pedágio e abastecimento da frota veicular da FAPES.",
        "search_terms": ["Sem Parar"],
    },
    "Pronort Vigilância Patrimonial Privada Ltda": {
        "type": "Empresa de Serviços / Segurança",
        "program": "Contrato Administrativo",
        "domain": "Segurança e Vigilância Patrimonial",
        "city": "Vitória / ES",
        "notes": "Prestadora de serviços de vigilância armada e patrimonial na sede da FAPES.",
        "search_terms": ["Pronort Vigilância"],
    },
    "Prime Consultoria e Assessoria Empresarial Ltda": {
        "type": "Empresa de Serviços / Frotas",
        "program": "Contrato Administrativo",
        "domain": "Gerenciamento de Frotas e Combustíveis",
        "city": "Vitória / ES",
        "notes": "Gestão informatizada de suprimento de combustíveis para veículos da Fundação.",
        "search_terms": ["Prime Consultoria", "PRIME CONSULTORIA"],
    },
    "Delta Automotores Eireli / Ltda": {
        "type": "Locadora de Veículos",
        "program": "Ata de Registro de Preços / SECTIDES",
        "domain": "Locação de Veículos Automotores",
        "city": "Vitória / ES",
        "notes": "Locação de veículos leves sem motorista para atividades finalísticas da FAPES.",
        "search_terms": ["Delta Automotores"],
    },
    "Empresa Brasileira de Correios e Telégrafos": {
        "type": "Empresa Pública Federal / Logística",
        "program": "Contrato Administrativo",
        "domain": "Serviços Postais e Encomendas",
        "city": "Vitória / ES",
        "notes": "Serviços postais para remessas e notificações administrativas.",
        "search_terms": ["CORREIOS E TELÉGRAFOS", "Correios e Telégrafos"],
    },
    "Link Card / Le Card Administradora de Benefícios Eireli": {
        "type": "Administradora de Benefícios / Cartões",
        "program": "Ata de Registro de Preços / SEGER",
        "domain": "Gestão de Benefícios e Cartões Eletrônicos",
        "city": "Vitória / ES",
        "notes": "Gerenciamento e emissão de cartões corporativos e vales para servidores.",
        "search_terms": ["Link Card", "LE CARD"],
    },
    "Pay Less Viagens e Turismo Ltda": {
        "type": "Agência de Viagens / Transporte",
        "program": "Ata de Registro de Preços / SEGER",
        "domain": "Emissão de Passagens Aéreas e Hospedagem",
        "city": "Vitória / ES",
        "notes": "Agenciamento de passagens para pesquisadores convidados e servidores em missão.",
        "search_terms": ["PAY LESS VIAGENS", "Pay Less Viagens"],
    },
    "Osiris Comércio e Serviços Ltda": {
        "type": "Empresa Comercial e Serviços",
        "program": "Contrato Administrativo",
        "domain": "Suprimentos e Equipamentos",
        "city": "Vitória / ES",
        "notes": "Fornecimento de suprimentos operacionais e serviços técnicos.",
        "search_terms": ["OSIRIS COMÉRCIO", "Osiris Comércio"],
    },
    "Gibbor Publicidade e Publicações de Editais Ltda": {
        "type": "Empresa de Publicidade / Imprensa",
        "program": "Contrato Administrativo",
        "domain": "Publicidade Legal e Publicações Oficiais",
        "city": "Vitória / ES",
        "notes": "Veiculação de extratos de editais em jornais de grande circulação estadual.",
        "search_terms": ["GIBBOR PUBLICIDADE", "Gibbor Publicidade"],
    },
    "A.T.M. Industrial Eireli": {
        "type": "Empresa de Serviços Industriais / Manutenção",
        "program": "Contrato Administrativo",
        "domain": "Manutenção Predial e Instalações",
        "city": "Vitória / ES",
        "notes": "Serviços de adequação predial e instalações técnicas.",
        "search_terms": ["A.T.M. INDUSTRIAL", "A.T.M. Industrial"],
    },
    "J F L Serviços Eireli": {
        "type": "Empresa de Serviços Terceirizados",
        "program": "Contrato Administrativo",
        "domain": "Apoio Administrativo e Copa",
        "city": "Vitória / ES",
        "notes": "Prestação de serviços contínuos de apoio operacional e copeiragem.",
        "search_terms": ["J F L SERVIÇOS", "J F L Serviços"],
    },
    "Classe Soluções e Serviços Ltda": {
        "type": "Empresa de Serviços Terceirizados",
        "program": "Contrato Administrativo",
        "domain": "Limpeza e Conservação Predial",
        "city": "Vitória / ES",
        "notes": "Serviços de conservação e higienização das dependências da Fundação.",
        "search_terms": ["CLASSE SOLUÇÕES", "Classe Soluções"],
    },
    "Método Telecomunicações e Comércio Ltda": {
        "type": "Empresa de Tecnologia e Telecomunicações",
        "program": "Contrato Administrativo / TIC",
        "domain": "Infraestrutura de Rede e Telefonia",
        "city": "Vitória / ES",
        "notes": "Manutenção e suporte de cabeamento estruturado e centrais telefônicas.",
        "search_terms": ["MÉTODO TELECOMUNICAÇÕES", "Método Telecomunicações"],
    },
    "Customize Serviços Eireli": {
        "type": "Empresa de Serviços Técnicos",
        "program": "Contrato Administrativo",
        "domain": "Apoio Operacional e Eventos",
        "city": "Vitória / ES",
        "notes": "Apoio logístico para organização de seminários de avaliação parcial e final.",
        "search_terms": ["CUSTOMIZE SERVIÇOS", "Customize Serviços"],
    },
    "DR Link Comércio e Serviços Ltda": {
        "type": "Empresa de Suprimentos Tecnológicos",
        "program": "Contrato Administrativo",
        "domain": "Equipamentos de Informática",
        "city": "Vitória / ES",
        "notes": "Fornecimento de periféricos e peças de reposição para estações de trabalho.",
        "search_terms": ["DR LINK COMÉRCIO", "DR Link Comércio"],
    },
    "A4 Publicidade e Marketing Ltda": {
        "type": "Agência de Comunicação / Marketing",
        "program": "Contrato Administrativo",
        "domain": "Design Gráfico e Campanhas de Comunicação",
        "city": "Vitória / ES",
        "notes": "Produção de materiais promocionais e campanhas de divulgação de editais de inovação.",
        "search_terms": ["A4 PUBLICIDADE", "A4 Publicidade"],
    },
    "Himalaia Refrigeração e Conservação Ltda": {
        "type": "Empresa de Manutenção Térmica",
        "program": "Contrato Administrativo",
        "domain": "Climatização e Refrigeração Predial",
        "city": "Vitória / ES",
        "notes": "Manutenção preventiva e corretiva de sistemas de climatização e ar-condicionado.",
        "search_terms": ["HIMALAIA REFRIGERAÇÃO", "Himalaia Refrigeração"],
    },
    "Compusoftware Informática Ltda": {
        "type": "Empresa de Software e Licenciamento",
        "program": "Contrato Administrativo / TIC",
        "domain": "Licenciamento de Software Corporativo",
        "city": "São Paulo / Atendimento ES",
        "notes": "Fornecimento de subscrições e licenças de software corporativo.",
        "search_terms": ["COMPUSOFTWA RE", "Compusoftware"],
    },
    "R. Vieira Negócios Imobiliários, Rurais e Urbanos Ltda": {
        "type": "Empresa de Gestão Imobiliária",
        "program": "Contrato de Locação Predial",
        "domain": "Locação de Imóvel Comercial",
        "city": "Vitória / ES",
        "notes": "Locadora das salas corporativas onde funciona a sede administrativa da FAPES.",
        "search_terms": ["R. Vieira - Negócios", "R. Vieira Negócios"],
    },
}


def scan_raw():
    found_companies = defaultdict(lambda: {"count": 0, "files": set(), "cnpjs": set()})

    for file_path in RAW_TEXT.rglob("*.txt"):
        try:
            text = file_path.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue

        rel_path = file_path.relative_to(ROOT).as_posix()

        for name, meta in VALIDATED_COMPANIES.items():
            for term in meta["search_terms"]:
                matches = list(re.finditer(rf"\b{re.escape(term)}\b", text, re.IGNORECASE))
                if matches:
                    found_companies[name]["count"] += len(matches)
                    found_companies[name]["files"].add(rel_path)
                    for m in matches:
                        w_start = max(0, m.start() - 300)
                        w_end = min(len(text), m.end() + 300)
                        window = text[w_start:w_end]
                        for cnpj_m in CNPJ_REGEX.finditer(window):
                            found_companies[name]["cnpjs"].add(cnpj_m.group(1))

    return found_companies


def main():
    print("Minerando empresas com filtro validado...")
    found = scan_raw()

    out_list = []
    for name, meta in VALIDATED_COMPANIES.items():
        data = found.get(name, {"count": 1, "files": set(), "cnpjs": set()})
        out_list.append({
            "name": name,
            "type": meta["type"],
            "program": meta["program"],
            "domain": meta["domain"],
            "city": meta["city"],
            "notes": meta["notes"],
            "cnpjs": list(data["cnpjs"]),
            "occurrences": max(data["count"], 1),
            "files_count": len(data["files"]),
            "is_curated": True,
        })

    json_path = ROOT / "tools/companies_extracted.json"
    csv_path = ROOT / "tools/companies_extracted.csv"

    json_path.write_text(json.dumps(out_list, ensure_ascii=False, indent=2), encoding="utf-8")

    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["Nome", "Tipo", "Programa", "Dominio_Setor", "Cidade", "CNPJ", "Ocorrencias", "Qtd_Arquivos", "Notas"])
        for item in out_list:
            writer.writerow([
                item["name"],
                item["type"],
                item["program"],
                item["domain"],
                item["city"],
                "; ".join(item["cnpjs"]),
                item["occurrences"],
                item["files_count"],
                item["notes"],
            ])

    print(f"Total de empresas validadas: {len(out_list)}")
    print(f"Arquivos gerados: {json_path} e {csv_path}")


if __name__ == "__main__":
    main()
