import requests
import config
import os

caminho_padrao = config.caminho_padrao


def get_cod_infra(auto, s):
    url = "https://servicos.dnit.gov.br/sior/Infracao/ConsultaAutoInfracao/List"
    params = {
        "sort": "", "page": 1, "pageSize": 10, "group": "",
        "filter": "", "numeroauto": auto, "bind": "true",
        "calledfromapi": "true", "calledFromApi": "true"
    }

    try:
        response = s.get(url, params=params)
        if response.status_code == 200:
            data = response.json()
            if isinstance(data, dict) and 'Data' in data:
                infracoes = data.get('Data', [])
                if infracoes and isinstance(infracoes, list):
                    return infracoes[0].get('CodigoInfracao', None)
        return None
    except requests.exceptions.RequestException as e:
        print(f"Erro na requisição: {e}")
        return None


def get_relatorio_financeiro(auto, s, pasta_destino):
    cod_infra = get_cod_infra(auto, s)
    if not cod_infra:
        return 1

    financeiro_url = f'https://servicos.dnit.gov.br/sior/Infracao/ConsultaAutoInfracao/ExportarRelatorioFinanceiro/{cod_infra}?numeroAuto={auto}'
    s.headers.update({
        "Referer": f"https://servicos.dnit.gov.br/sior/Infracao/ConsultaAutoInfracao/Details/{cod_infra}"
    })

    try:
        financeiro_link_response = s.get(financeiro_url)
        if financeiro_link_response.status_code != 200:
            return 1

        true_finance_url = 'https://servicos.dnit.gov.br' + financeiro_link_response.text
        nome_arquivo = f'RelatorioFinanceiro_{auto}.pdf'
        to_save_file = os.path.join(pasta_destino, nome_arquivo)

        response = s.get(true_finance_url)
        response.raise_for_status()

        with open(to_save_file, "wb") as f:
            f.write(response.content)
        return 0

    except Exception as e:
        print(f"Erro ao baixar relatório financeiro do AIT {auto}: {e}")
        return 1


def get_relatorio_resumido(auto, s, pasta_destino):
    cod_infra = get_cod_infra(auto, s)
    if not cod_infra:
        return 1

    resumido_url = f'https://servicos.dnit.gov.br/sior/Infracao/ConsultaAutoInfracao/ExportarRelatorioAutoInfracaoResumido/{cod_infra}?numeroAuto={auto}'
    s.headers.update({
        "Referer": f"https://servicos.dnit.gov.br/sior/Infracao/ConsultaAutoInfracao/Details/{cod_infra}"
    })

    try:
        resumido_link_response = s.get(resumido_url)
        if resumido_link_response.status_code != 200:
            return 1

        true_resumido_url = 'https://servicos.dnit.gov.br' + resumido_link_response.text
        nome_arquivo = f'RelatorioResumido_{auto}.pdf'
        to_save_file = os.path.join(pasta_destino, nome_arquivo)

        response = s.get(true_resumido_url)
        response.raise_for_status()

        with open(to_save_file, "wb") as f:
            f.write(response.content)
        return 0

    except Exception as e:
        print(f"Erro ao baixar relatório resumido do AIT {auto}: {e}")
        return 1


def get_dados_auto(auto, s):
    """
    Realiza a consulta do Auto de Infração no SIOR via requisição autenticada.

    Parâmetros:
        auto (str): Número do auto de infração (ex: 'S013250314')
        s (requests.Session): Sessão autenticada com cookies válidos

    Retorna:
        dict | None: Dicionário com os dados retornados, ou None em caso de falha.
    """
    try:
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

        headers = {
            "Accept": "*/*",
            "Accept-Encoding": "gzip, deflate, br, zstd",
            "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
            "Referer": f"https://servicos.dnit.gov.br/sior/Infracao/ConsultaAutoInfracao?NumeroAuto={auto}&Bind=true&Page=1&PageSize=10",
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "same-origin",
            "X-Requested-With": "XMLHttpRequest",
            "sec-ch-ua": '"Google Chrome";v="137", "Chromium";v="137", "Not/A)Brand";v="24"',
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": '"Windows"'
        }

        response = s.get(url, params=params, headers=headers)

        # Verifica status HTTP
        if response.status_code == 200:
            json_result = response.json()
            # Garante que exista 'Data' como lista
            if 'Data' in json_result and isinstance(json_result['Data'], list):
                return json_result
            else:
                print(f"❌ Resposta inesperada para {auto}: {json_result}")
                return {"Data": []}
        else:
            print(f"❌ Erro HTTP {response.status_code} ao consultar auto {auto}")
            return {"Data": []}
    except Exception as e:
        print(f"❌ Erro ao consultar auto {auto}: {e}")
        return []  # retorna lista vazia em caso de falha


def get_dados_auto_cobranca(auto: str, s: requests.Session) -> dict:
    """
    Consulta dados de cobrança do auto de infração no SIOR.

    Parâmetros:
        auto (str): Número do auto de infração (ex: 'S014253902')
        s (requests.Session): Sessão autenticada com cookies válidos

    Retorna:
        dict: Dicionário no mesmo formato de get_dados_auto, com chave 'Data' contendo os registros.
    """
    try:
        url = "https://servicos.dnit.gov.br/sior/Cobranca/CobrancaConsulta/List"
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
        headers = {
            "Accept": "*/*",
            "Accept-Encoding": "gzip, deflate, br, zstd",
            "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
            "Referer": f"https://servicos.dnit.gov.br/sior/Cobranca/CobrancaConsulta?NumeroAuto={auto}&Bind=true&Page=1&PageSize=10",
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "same-origin",
            "X-Requested-With": "XMLHttpRequest",
            "sec-ch-ua": '"Not)A;Brand";v="8", "Chromium";v="138", "Google Chrome";v="138"',
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": '"Windows"'
        }

        response = s.get(url, params=params, headers=headers)
        if response.status_code == 200:
            data = response.json()
            if 'Data' in data and isinstance(data['Data'], list):
                return data
            else:
                print(f"❌ Resposta inesperada para {auto}: {data}")
                return {"Data": []}
        else:
            print(f"❌ Erro HTTP {response.status_code} ao consultar auto cobrança {auto}")
            return {"Data": []}
    except Exception as e:
        print(f"❌ Erro ao consultar auto cobrança {auto}: {e}")
        return {"Data": []}


def get_acompanhamento_sior(equipe_id, s):
    url = "https://servicos.dnit.gov.br/sior/Cobranca/SupervisaoSapiensAcompanhamento/List"
    page = 1
    page_size = 1000
    todos_dados = []

    while True:
        params = {
            "sort": "",
            "page": page,
            "pageSize": page_size,
            "group": "",
            "filter": "",
            "equipeselecionada": equipe_id,
            "bind": "true",
            "calledfromapi": "true",
            "calledFromApi": "true"
        }
        try:
            response = s.get(url, params=params)
            response.raise_for_status()
            json_data = response.json()
            dados = json_data.get("Data", [])
            todos_dados.extend(dados)
            total = json_data.get("Total", len(todos_dados))
            if len(todos_dados) >= total:
                break
            page += 1
        except Exception as e:
            print(f"Erro na requisição página {page}: {e}")
            break

    return todos_dados


def get_valores_original(equipe_id, s):
    url = "https://servicos.dnit.gov.br/sior/Cobranca/SupervisaoSapiensDistribuicao/List"
    page = 1
    page_size = 1000
    todos_valores = []

    while True:
        params = {
            "sort": "",
            "page": page,
            "pageSize": page_size,
            "group": "",
            "filter": "",
            "equipeselecionada": equipe_id,
            "fase": 32,
            "calledfromapi": "true",
            "calledFromApi": "true"
        }
        try:
            response = s.get(url, params=params)
            response.raise_for_status()
            json_data = response.json()
            dados = json_data.get("Data", [])
            todos_valores.extend(dados)
            total = json_data.get("Total", len(todos_valores))
            if len(todos_valores) >= total:
                break
            page += 1
        except Exception as e:
            print(f"Erro na requisição de valores página {page}: {e}")
            break

    return todos_valores


