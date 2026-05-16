import requests
import config
import os
from bs4 import BeautifulSoup
import re
import time

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
            response = s.get(url, params=params, timeout=60)
            response.raise_for_status()
            json_data = response.json()
            dados = json_data.get("Data", [])
            todos_dados.extend(dados)
            total = json_data.get("Total", len(todos_dados))
            if len(todos_dados) >= total:
                break
            page += 1
        except requests.exceptions.HTTPError as e:
            if e.response is not None and e.response.status_code == 500:
                raise RuntimeError("Erro no servidor ao consultar acompanhamento. Tente novamente mais tarde.")
            raise RuntimeError(f"Erro HTTP: {e}")
        except Exception as e:
            raise RuntimeError(f"Erro na requisição página {page}: {e}")

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
            response = s.get(url, params=params, timeout=60)
            response.raise_for_status()
            json_data = response.json()
            dados = json_data.get("Data", [])
            todos_valores.extend(dados)
            total = json_data.get("Total", len(todos_valores))
            if len(todos_valores) >= total:
                break
            page += 1
        except requests.exceptions.HTTPError as e:
            if e.response is not None and e.response.status_code == 500:
                raise RuntimeError("Erro no servidor ao consultar valores originais. Tente novamente mais tarde.")
            raise RuntimeError(f"Erro HTTP: {e}")
        except Exception as e:
            raise RuntimeError(f"Erro na requisição de valores página {page}: {e}")

    return todos_valores


def get_valor_corrigido(auto: str, s: requests.Session):
    """
    Consulta os dados financeiros do auto
    através da aba _Financeiro do SIOR.

    Retorna:
    {
        "NumeroAuto": str,
        "CodigoInfracao": str,
        "DevedorNumero": str,
        "ValorOriginal": str,
        "ValorCorrigido": str,
        "FatorMultiplicador": float
    }
    """

    try:

        # =====================================================
        # 1. CÓDIGO INFRAÇÃO
        # =====================================================
        cod_infra = get_cod_infra(auto, s)

        if not cod_infra:

            print(
                f"❌ Código infra não localizado "
                f"para {auto}"
            )

            return None

        # =====================================================
        # 2. DETAILS
        # =====================================================
        details_url = (
            "https://servicos.dnit.gov.br/"
            f"sior/Infracao/"
            f"ConsultaAutoInfracao/Details/"
            f"{cod_infra}"
        )

        headers_details = {

            "Accept":
                "text/html,application/xhtml+xml,"
                "application/xml;q=0.9,image/avif,"
                "image/webp,image/apng,*/*;q=0.8,"
                "application/signed-exchange;v=b3;q=0.7",

            "Referer":
                "https://servicos.dnit.gov.br/"
                "sior/Cobranca/CobrancaConsulta",

            "Upgrade-Insecure-Requests":
                "1",

            "User-Agent":
                "Mozilla/5.0 "
                "(Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 "
                "(KHTML, like Gecko) "
                "Chrome/148.0.0.0 Safari/537.36"
        }

        response_details = s.get(
            details_url,
            headers=headers_details,
            timeout=60
        )

        if response_details.status_code != 200:

            print(
                f"❌ Erro ao acessar Details "
                f"{cod_infra}: "
                f"{response_details.status_code}"
            )

            return None

        html = response_details.text

        # =====================================================
        # DEBUG OPCIONAL
        # =====================================================
        # with open(
        #     f"debug_details_{auto}.html",
        #     "w",
        #     encoding="utf-8"
        # ) as f:
        #     f.write(html)

        # =====================================================
        # 3. EXTRAÇÃO URL FINANCEIRO
        # =====================================================
        regex_financeiro = re.search(

            rf'(/sior/Infracao/ConsultaAutoInfracao/'
            rf'_Financeiro/{cod_infra}\?[^"]+)',

            html
        )

        if not regex_financeiro:

            print(
                f"❌ URL financeiro não localizada "
                f"para {auto}"
            )

            return None

        financeiro_path = regex_financeiro.group(1)

        # =====================================================
        # AJUSTE HTML ENCODE
        # =====================================================
        financeiro_path = (
            financeiro_path
            .replace("\\u0026", "&")
            .replace("\\/", "/")
        )

        financeiro_url = (
            "https://servicos.dnit.gov.br"
            + financeiro_path
        )


        # =====================================================
        # 4. REQUEST FINANCEIRO
        # =====================================================
        headers_financeiro = {

            "Accept":
                "text/html, */*; q=0.01",

            "Referer":
                details_url,

            "X-Requested-With":
                "XMLHttpRequest",

            "User-Agent":
                "Mozilla/5.0 "
                "(Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 "
                "(KHTML, like Gecko) "
                "Chrome/148.0.0.0 Safari/537.36"
        }

        response_financeiro = s.get(
            financeiro_url,
            headers=headers_financeiro,
            timeout=60
        )


        if response_financeiro.status_code != 200:

            print(
                f"❌ Erro financeiro {auto}: "
                f"{response_financeiro.status_code}"
            )

            return None

        financeiro_html = response_financeiro.text

        # =====================================================
        # DEBUG OPCIONAL
        # =====================================================
        # with open(
        #     f"debug_financeiro_{auto}.html",
        #     "w",
        #     encoding="utf-8"
        # ) as f:
        #     f.write(financeiro_html)

        # =====================================================
        # 5. PARSER FINANCEIRO
        # =====================================================
        soup = BeautifulSoup(
            financeiro_html,
            "html.parser"
        )

        # =====================================================
        # EXTRAÇÃO POR LABEL
        # =====================================================
        def extrair_valor(label_texto):

            try:

                labels = soup.find_all(
                    ["label", "span", "td", "strong"]
                )

                for label in labels:

                    texto = label.get_text(
                        strip=True
                    )

                    if (
                        label_texto.lower()
                        in texto.lower()
                    ):

                        parent = label.parent

                        if parent:

                            textos = list(
                                parent.stripped_strings
                            )

                            for item in textos:

                                if (
                                    item.strip()
                                    != texto.strip()
                                ):
                                    return item.strip()

                # ==========================================
                # FALLBACK REGEX
                # ==========================================
                regex = re.search(

                    rf'{label_texto}.*?'
                    rf'([\d\.\,\-\/]+)',

                    financeiro_html,

                    re.I | re.S
                )

                if regex:
                    return regex.group(1)

                return ""

            except Exception as ex:

                print(
                    f"❌ Erro extração "
                    f"{label_texto}: {ex}"
                )

                return ""

        # =====================================================
        # EXTRAÇÕES
        # =====================================================
        valor_original = extrair_valor(
            "Valor Original"
        )

        valor_corrigido = extrair_valor(
            "Valor Corrigido"
        )

        devedor_numero = (
            extrair_valor("CPF/CNPJ")
            or extrair_valor("CPF")
            or extrair_valor("CNPJ")
        )

        # =====================================================
        # CONVERSÃO
        # =====================================================
        def converter_moeda(valor):

            try:

                valor = str(valor)

                valor = re.sub(
                    r"[^\d,.-]",
                    "",
                    valor
                )

                valor = (
                    valor
                    .replace(".", "")
                    .replace(",", ".")
                )

                return float(valor)

            except:
                return 0.0

        valor_original_float = converter_moeda(
            valor_original
        )

        valor_corrigido_float = converter_moeda(
            valor_corrigido
        )

        # =====================================================
        # FATOR
        # =====================================================
        fator = 0

        if valor_original_float > 0:

            fator = (
                valor_corrigido_float
                / valor_original_float
            )

        # =====================================================
        # RESULTADO
        # =====================================================
        resultado = {

            "NumeroAuto":
                auto,

            "CodigoInfracao":
                cod_infra,

            "DevedorNumero":
                devedor_numero,

            "ValorOriginal":
                valor_original,

            "ValorCorrigido":
                valor_corrigido,

            "FatorMultiplicador":
                round(fator, 4)
        }


        return resultado

    except Exception as ex:

        print(
            f"❌ Erro ao obter "
            f"valor corrigido {auto}: {ex}"
        )

        return None

