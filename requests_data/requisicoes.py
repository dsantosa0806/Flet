import requests
import config
import os
from datetime import datetime


caminho_padrao = config.caminho_padrao


def get_cod_infra(auto, s):
    # Sanitiza a entrada removendo caracteres indesejados
    url = "https://servicos.dnit.gov.br/sior/Infracao/ConsultaAutoInfracao/List"
    params = {
        "sort": "",
        "page": 1,
        "pageSize": 10,
        "group": "",
        "filter": "",
        "numeroauto": auto,
        "bind": "true",
        "calledfromapi": "true",
        "calledFromApi": "true"
    }

    try:
        response = s.get(url, params=params)

        if response.status_code == 200:
            data = response.json()  # Converte a resposta para JSON
            if isinstance(data, dict) and 'Data' in data:  # Verifica se existe a chave 'data'
                infracoes = data.get('Data', [])  # Obtém a lista de infrações
                if infracoes and isinstance(infracoes, list):  # Verifica se há infrações
                    return infracoes[0].get('CodigoInfracao', None)  # Retorna o primeiro Código de Infração encontrado
        return None  # Retorna None se não encontrar nada válido

    except requests.exceptions.RequestException as e:
        print(f"Erro na requisição: {e}")
        return None


def get_relatorio_financeiro(auto, s, pasta_destino):
    cod_infra = get_cod_infra(auto, s)
    if not cod_infra:
        return 1

    financeiro_url = f'https://servicos.dnit.gov.br/sior/Infracao/ConsultaAutoInfracao/ExportarRelatorioFinanceiro/{cod_infra}?numeroAuto={auto}'
    s.headers.update(
        {"Referer": f"https://servicos.dnit.gov.br/sior/Infracao/ConsultaAutoInfracao/Details/{cod_infra}"})

    financeiro_link_response = s.get(financeiro_url)
    if financeiro_link_response.status_code != 200:
        return 1

    true_finance_url = 'https://servicos.dnit.gov.br' + financeiro_link_response.text
    nome_arquivo = f'RelatorioFinanceiro_{auto}.pdf'
    to_save_file = os.path.join(pasta_destino, nome_arquivo)

    response = s.get(true_finance_url)
    if response.status_code == 200:
        with open(to_save_file, "wb") as f:
            f.write(response.content)
        return 0
    return 1


def get_relatorio_resumido(auto, s, pasta_destino):
    cod_infra = get_cod_infra(auto, s)
    if not cod_infra:
        return 1

    resumido_url = f'https://servicos.dnit.gov.br/sior/Infracao/ConsultaAutoInfracao/ExportarRelatorioAutoInfracaoResumido/{cod_infra}?numeroAuto={auto}'
    s.headers.update({
        "Referer": f"https://servicos.dnit.gov.br/sior/Infracao/ConsultaAutoInfracao/Details/{cod_infra}"
    })

    resumido_link_response = s.get(resumido_url)
    if resumido_link_response.status_code != 200:
        return 1

    true_resumido_url = 'https://servicos.dnit.gov.br' + resumido_link_response.text
    nome_arquivo = f'RelatorioResumido_{auto}.pdf'
    to_save_file = os.path.join(pasta_destino, nome_arquivo)

    response = s.get(true_resumido_url)
    if response.status_code == 200:
        with open(to_save_file, "wb") as f:
            f.write(response.content)
        return 0
    else:
        print(f"Erro na requisição do Relatório Resumido: {response.status_code}")
        return 1