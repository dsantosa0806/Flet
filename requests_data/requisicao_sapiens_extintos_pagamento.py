import requests
import json
from datetime import datetime, timedelta
import time


# === Endpoint fixo do backend ===
BACKEND = "https://supersapiensbackend.agu.gov.br"
URL_RELATORIO = f"{BACKEND}/v1/administrativo/relatorio?populate=[]&context={{}}"


def gerar_relatorios(token: str, data_inicio: str, data_fim: str):
    """
    Gera relatórios diários do tipo 'DÍVIDA ATIVA' (1609) para o credor 902,
    percorrendo o período informado (ex: 01/10/2025 a 15/10/2025).

    Parâmetros:
        token (str): Token Bearer válido.
        data_inicio (str): Data inicial no formato 'YYYY-MM-DD'.
        data_fim (str): Data final no formato 'YYYY-MM-DD'.

    Retorno:
        list[dict]: [{data, id_relatorio}]
    """

    headers = {
        "Accept": "application/json, text/plain, */*",
        "Authorization": f"Bearer {token}",
        "Origin": "https://supersapiens.agu.gov.br",
        "Referer": "https://supersapiens.agu.gov.br/",
        "Content-Type": "text/plain",
    }

    data_ini = datetime.strptime(data_inicio, "%Y-%m-%d").date()
    data_fim_dt = datetime.strptime(data_fim, "%Y-%m-%d").date()

    resultados = []

    dia_atual = data_ini
    while dia_atual <= data_fim_dt:
        data_ref = dia_atual.strftime("%Y-%m-%d")
        payload = {
            "formato": "xlsx",
            "nomeRelatorio": None,
            "documento": None,
            "observacao": None,
            "tipoRelatorio": 1609,
            "parametros": json.dumps({
                "dataHoraInicio": {
                    "name": "dataHoraInicio",
                    "value": f"{data_ref}T00:00:00",
                    "type": "dateTime"
                },
                "dataHoraFim": {
                    "name": "dataHoraFim",
                    "value": f"{data_ref}T23:55:00",
                    "type": "dateTime"
                },
                "credor": {
                    "name": "credor",
                    "value": 902,
                    "type": "entity",
                    "class": "SuppCore\\DividaBackend\\Entity\\Credor",
                    "getter": "getPessoa"
                }
            }),
            "status": None,
            "generoRelatorio": {
                "nome": "OPERACIONAL",
                "descricao": "OPERACIONAL",
                "@type": "GeneroRelatorio",
                "@id": "/v1/administrativo/genero_relatorio/3",
            },
            "especieRelatorio": {
                "nome": "DÍVIDA ATIVA",
                "descricao": "DÍVIDA ATIVA",
                "@type": "EspecieRelatorio",
                "@id": "/v1/administrativo/especie_relatorio/10",
            },
        }

        print(f"📤 Gerando relatório para {data_ref}...")
        try:
            resp = requests.post(URL_RELATORIO, headers=headers, data=json.dumps(payload))
        except Exception as e:
            print(f"⚠️ Erro de conexão em {data_ref}: {e}")
            dia_atual += timedelta(days=1)
            continue

        if resp.status_code == 201:
            try:
                dados = resp.json()
                rel_id = dados.get("id")
                print(f"✅ Relatório gerado com sucesso (ID: {rel_id})")
                resultados.append({"data": data_ref, "id_relatorio": rel_id})
            except Exception:
                print(f"⚠️ Erro ao interpretar resposta JSON para {data_ref}")
        else:
            print(f"❌ Erro ao gerar relatório {data_ref}: {resp.status_code}")
            try:
                print("Detalhes:", resp.json())
            except:
                print("Resposta bruta:", resp.text)

        dia_atual += timedelta(days=1)
        time.sleep(1.5)  # leve pausa entre requests

    print(f"\n📊 Total de relatórios gerados: {len(resultados)}")
    return resultados


import os
import requests
import time
import base64
import pandas as pd
from datetime import datetime

BACKEND = "https://supersapiensbackend.agu.gov.br"
DOWNLOAD_DIR = os.path.join(os.getcwd(), "downloads")


def obter_documento_id(token: str, id_relatorio: int):
    """Obtém o ID do documento vinculado ao relatório."""
    url = f"{BACKEND}/v1/administrativo/relatorio/{id_relatorio}?populate=%5B%22documento%22%5D"
    headers = {
        "Accept": "application/json, text/plain, */*",
        "Authorization": f"Bearer {token}",
        "Origin": "https://supersapiens.agu.gov.br",
        "Referer": "https://supersapiens.agu.gov.br/",
    }

    resp = requests.get(url, headers=headers)
    if resp.status_code != 200:
        print(f"❌ Falha ao consultar relatório {id_relatorio}: {resp.status_code}")
        return None

    try:
        dados = resp.json()
        documento = dados.get("documento")
        if documento and isinstance(documento, dict):
            return documento.get("id")
    except Exception as e:
        print(f"⚠️ Erro ao processar JSON do relatório {id_relatorio}: {e}")

    return None


def obter_componente_digital_do_documento(token: str, id_documento: int):
    """Obtém o ID do componente digital vinculado a um documento."""
    url = f"{BACKEND}/v1/administrativo/documento/{id_documento}?populate=%5B%22componentesDigitais%22%5D"
    headers = {
        "Accept": "application/json, text/plain, */*",
        "Authorization": f"Bearer {token}",
        "Origin": "https://supersapiens.agu.gov.br",
        "Referer": "https://supersapiens.agu.gov.br/",
    }

    for tentativa in range(10):
        resp = requests.get(url, headers=headers)
        if resp.status_code != 200:
            print(f"❌ Falha ao consultar documento {id_documento}: {resp.status_code}")
            time.sleep(5)
            continue

        try:
            dados = resp.json()
            comps = dados.get("componentesDigitais", [])
            if isinstance(comps, list) and comps:
                comp_id = comps[0].get("id")
                print(f"✅ Documento {id_documento} pronto. Componente digital: {comp_id}")
                return comp_id
        except Exception as e:
            print(f"⚠️ Erro ao ler JSON do documento {id_documento}: {e}")

        print(f"⏳ Documento {id_documento} ainda sem componente digital... aguardando 5s.")
        time.sleep(5)

    print(f"⏰ Tempo limite atingido aguardando documento {id_documento}.")
    return None


def baixar_relatorios(token: str, relatorios: list[dict]):
    """
    Fluxo completo: relatório → documento → componente → download.
    Cada arquivo baixado é nomeado com a data do relatório.
    """
    if not os.path.exists(DOWNLOAD_DIR):
        os.makedirs(DOWNLOAD_DIR)

    arquivos_baixados = []

    for item in relatorios:
        relatorio_id = item["id_relatorio"]
        data_ref = item.get("data")  # Data vinda da geração (ex: 2025-10-14)
        data_sufixo = f"_{data_ref}" if data_ref else ""

        print(f"\n📄 Processando relatório {relatorio_id} (data {data_ref or '---'})...")

        doc_id = obter_documento_id(token, relatorio_id)
        if not doc_id:
            print(f"⚠️ Nenhum documento encontrado no relatório {relatorio_id}")
            continue

        comp_id = obter_componente_digital_do_documento(token, doc_id)
        if not comp_id:
            print(f"⚠️ Documento {doc_id} não possui componente digital disponível.")
            continue

        # --- download do arquivo ---
        url = f"{BACKEND}/v1/administrativo/componente_digital/{comp_id}/download?context={{}}&populate=[]"
        headers = {
            "Accept": "application/json, text/plain, */*",
            "Authorization": f"Bearer {token}",
            "Origin": "https://supersapiens.agu.gov.br",
            "Referer": "https://supersapiens.agu.gov.br/",
        }

        resp = requests.get(url, headers=headers)
        if resp.status_code != 200:
            print(f"❌ Erro ao baixar componente {comp_id}: {resp.status_code}")
            continue

        content_type = resp.headers.get("Content-Type", "")
        if "application/json" in content_type:
            dados = resp.json()
            conteudo = dados.get("conteudo", "")
            if not conteudo:
                print(f"⚠️ Nenhum conteúdo encontrado para componente {comp_id}")
                continue

            if "base64," in conteudo:
                conteudo = conteudo.split("base64,")[1]

            extensao = ".xlsx" if "application/vnd.openxmlformats" in dados.get("conteudo", "") else ".pdf"
            nome_arquivo = f"Relatorio_Extintos{data_sufixo}_{comp_id}{extensao}"
            caminho = os.path.join(DOWNLOAD_DIR, nome_arquivo)

            with open(caminho, "wb") as f:
                f.write(base64.b64decode(conteudo))
            print(f"✅ Arquivo salvo em: {caminho}")
            arquivos_baixados.append(caminho)

        else:
            nome_arquivo = f"Relatorio_Extintos{data_sufixo}_{comp_id}.xlsx"
            caminho = os.path.join(DOWNLOAD_DIR, nome_arquivo)
            with open(caminho, "wb") as f:
                f.write(resp.content)
            print(f"✅ Arquivo binário salvo em: {caminho}")
            arquivos_baixados.append(caminho)

        time.sleep(1.5)

    print(f"\n📦 Total de arquivos baixados: {len(arquivos_baixados)}")
    return arquivos_baixados


def extrair_relatorios_downloads():
    """
    Percorre todos os relatórios Excel no diretório 'downloads',
    extrai os campos a partir da linha 10 e adiciona o campo
    'Data do Relatório' obtido do nome do arquivo.
    Retorna um DataFrame consolidado e salva em CSV UTF-8-SIG.
    """

    # Caminho absoluto da raiz do projeto (onde está o main.py)
    raiz_projeto = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    # Caminho absoluto da pasta downloads
    diretorio_downloads = os.path.join(raiz_projeto, "downloads")

    if not os.path.exists(diretorio_downloads):
        raise FileNotFoundError(
            f"❌ Pasta 'downloads' não encontrada no caminho esperado:\n{diretorio_downloads}"
        )

    # Colunas fixas esperadas nos relatórios
    colunas = [
        "Num_credito",
        "Num_origem",
        "Nup",
        "Unidade",
        "Especie_credito",
        "Devedor",
        "Valor_pago",
    ]

    todos_dados = []

    print(f"\n📂 Procurando relatórios no diretório: {diretorio_downloads}")

    arquivos_excel = [
        f for f in os.listdir(diretorio_downloads)
        if f.lower().endswith((".xlsx", ".xls"))
    ]

    if not arquivos_excel:
        print("⚠️ Nenhum arquivo Excel encontrado na pasta 'downloads'.")
        return pd.DataFrame(columns=colunas + ["Data do Relatório"])

    for arquivo in arquivos_excel:
        caminho_arquivo = os.path.join(diretorio_downloads, arquivo)
        print(f"📑 Processando arquivo: {arquivo}")

        # Extrai a data do nome do arquivo (ex: 2025-10-01 → 01/10/2025)
        data_relatorio = None
        partes_nome = arquivo.split("_")
        for parte in partes_nome:
            if len(parte) == 10 and parte[:4].isdigit() and parte[4] == "-":
                try:
                    data_relatorio = datetime.strptime(parte, "%Y-%m-%d").strftime("%d/%m/%Y")
                    break
                except Exception:
                    continue

        if not data_relatorio:
            print(f"⚠️ Data não identificada no nome do arquivo: {arquivo}")
            data_relatorio = "N/D"

        try:
            # Lê dados a partir da linha 10 (índice 9)
            df = pd.read_excel(caminho_arquivo, skiprows=9, dtype=str)

            # Mantém apenas as colunas relevantes, se existirem
            colunas_existentes = [col for col in colunas if col in df.columns]
            df = df[colunas_existentes]

            # Corrige possíveis strings corrompidas (versão moderna sem applymap)
            for col in df.select_dtypes(include="object").columns:
                df[col] = df[col].map(
                    lambda x: x.encode("latin1", errors="ignore").decode("latin1") if isinstance(x, str) else x
                )

            # Adiciona campo com a data do relatório
            df["Data do Relatório"] = data_relatorio

            todos_dados.append(df)
            print(f"✅ {arquivo}: {len(df)} registros extraídos ({data_relatorio})")

        except Exception as e:
            print(f"⚠️ Erro ao processar {arquivo}: {e}")

    if not todos_dados:
        print("❌ Nenhum relatório válido foi processado.")
        return pd.DataFrame(columns=colunas + ["Data do Relatório"])

    # Consolida todos os DataFrames
    df_final = pd.concat(todos_dados, ignore_index=True)

    # 🔒 Garante que o campo Num_credito seja tratado como texto puro
    if "Num_credito" in df_final.columns:
        df_final["Num_credito"] = df_final["Num_credito"].astype(str)
        df_final["Num_credito"] = df_final["Num_credito"].str.replace(r"\.0$", "", regex=True)
        df_final["Num_credito"] = df_final["Num_credito"].apply(
            lambda x: f"'{x}" if x.isdigit() else x
        )

    # Garante que todas as colunas estejam presentes (mesmo que vazias)
    for col in colunas:
        if col not in df_final.columns:
            df_final[col] = None

    # Reorganiza a ordem final das colunas
    df_final = df_final[colunas + ["Data do Relatório"]]

    print(f"\n✅ Extração concluída: {len(df_final)} registros de {len(todos_dados)} arquivos.")

    # Caminho de saída do CSV
    caminho_saida = os.path.join(raiz_projeto, "Relatorios_Consolidados.csv")

    # Salva em CSV com separador ';' e encoding compatível com Excel BR
    df_final.to_csv(caminho_saida, index=False, sep=";", encoding="utf-8-sig")

    print(f"📁 Arquivo CSV salvo com sucesso em: {caminho_saida}")
    return df_final
