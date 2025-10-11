# ============================================
# requisicoes_cadin.py – Consulta CADIN (CPF/CNPJ)
# ============================================

import requests
import time


def consultar_cadin(token: str, lista_documentos: list):
    """
    Realiza a consulta de CPF ou CNPJ no CADIN utilizando o token JWT válido.
    Retorna uma lista com todos os registros encontrados.
    """
    resultados = []
    url_base = "https://cadin.pgfn.gov.br/cadastro/apirest/registro"

    headers_base = {
        "authority": "cadin.pgfn.gov.br",
        "accept": "application/json, text/plain, */*",
        "accept-encoding": "gzip, deflate, br, zstd",
        "accept-language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
        "origin": "https://cadin.pgfn.gov.br",
        "priority": "u=1, i",
        "referer": "https://cadin.pgfn.gov.br/",
        "sec-ch-ua": '"Google Chrome";v="141", "Not?A_Brand";v="8", "Chromium";v="141"',
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": '"Windows"',
        "sec-fetch-dest": "empty",
        "sec-fetch-mode": "cors",
        "sec-fetch-site": "same-origin",
        "user-agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/141.0.0.0 Safari/537.36"
        ),
    }

    for doc in lista_documentos:
        # Sanitiza o documento (remove pontos, traços, barras)
        doc = "".join(ch for ch in str(doc) if ch.isdigit())

        # Determina tipo de documento
        tipo = "cnpj" if len(doc) > 11 else "cpf"
        url = f"{url_base}/{doc}/{tipo}"

        headers = headers_base.copy()
        headers["authorization"] = f"Bearer {token.strip()}"

        print(f"🔎 Consultando {tipo.upper()} {doc} ...")

        try:
            response = requests.get(url, headers=headers, timeout=30)

            if response.status_code == 200:
                try:
                    data = response.json()
                    if isinstance(data, list):
                        resultados.extend(data)
                    elif isinstance(data, dict):
                        resultados.append(data)
                    print(f"✅ {tipo.upper()} {doc} → {len(data) if isinstance(data, list) else 1} registro(s)")
                except Exception as ex_json:
                    print(f"⚠️ Erro ao decodificar JSON para {doc}: {ex_json}")

            elif response.status_code == 403:
                print(f"❌ Acesso negado (403) – token inválido ou expirado para {doc}")
            elif response.status_code == 404:
                print(f"⚠️ Nenhum registro encontrado para {doc}")
            else:
                print(f"⚠️ Erro {response.status_code} ao consultar {doc}: {response.text[:200]}")

            # Pausa mínima entre consultas para evitar bloqueio
            time.sleep(0.5)

        except requests.exceptions.RequestException as ex_req:
            print(f"❌ Erro de conexão para {doc}: {ex_req}")

    print(f"\n📊 Total de registros coletados: {len(resultados)}")
    return resultados
