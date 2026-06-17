import os
import json
import time
import base64
import shutil
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Tuple

import pandas as pd
import requests


# ==========================================================
# CONFIGURAÇÕES GERAIS
# ==========================================================

BACKEND = "https://supersapiensbackend.agu.gov.br"

URL_RELATORIO = (
    f"{BACKEND}/v1/administrativo/relatorio?populate=[]&context={{}}"
)

TIMEOUT_REQUEST = 60

PAUSA_ENTRE_REQUISICOES = 1.5

TENTATIVAS_DOCUMENTO = 10

PAUSA_DOCUMENTO_SEGUNDOS = 5


# ==========================================================
# DIRETÓRIOS
# ==========================================================

def obter_diretorio_base() -> str:
    """
    Define uma pasta base segura para salvar downloads e consolidados.

    Prioridade:
    1. Variável de ambiente SS_EXTINTOS_OUTPUT_DIR;
    2. config.PASTA_EXPORT_ADMIN, se existir;
    3. Pasta do próprio arquivo;
    4. Diretório atual.
    """

    env_dir = os.getenv("SS_EXTINTOS_OUTPUT_DIR")

    if env_dir:
        return env_dir

    try:
        import config

        pasta_admin = getattr(
            config,
            "PASTA_EXPORT_ADMIN",
            None
        )

        if pasta_admin:
            return pasta_admin

    except Exception:
        pass

    try:
        return os.path.dirname(
            os.path.abspath(__file__)
        )

    except Exception:
        return os.getcwd()


BASE_DIR = obter_diretorio_base()

PASTA_MODULO = os.path.join(
    BASE_DIR,
    "Sapiens_Extintos_Pagamento"
)

DOWNLOAD_DIR = os.path.join(
    PASTA_MODULO,
    "downloads"
)

ARQUIVO_CONSOLIDADO = os.path.join(
    PASTA_MODULO,
    "Relatorios_Consolidados.csv"
)


def garantir_diretorios() -> None:
    """
    Garante que as pastas necessárias existam.
    """

    os.makedirs(
        PASTA_MODULO,
        exist_ok=True
    )

    os.makedirs(
        DOWNLOAD_DIR,
        exist_ok=True
    )


# ==========================================================
# HEADERS
# ==========================================================

def montar_headers(
    token: str,
    content_type: Optional[str] = None
) -> dict:
    """
    Monta headers padrão para chamadas ao backend do Super Sapiens.
    """

    headers = {
        "Accept": "application/json, text/plain, */*",
        "Authorization": f"Bearer {token}",
        "Origin": "https://supersapiens.agu.gov.br",
        "Referer": "https://supersapiens.agu.gov.br/",
    }

    if content_type:
        headers["Content-Type"] = content_type

    return headers


# ==========================================================
# VALIDAÇÃO DE DATAS
# ==========================================================

def validar_periodo(
    data_inicio: str,
    data_fim: str
):
    """
    Valida e converte o período informado.

    Formato esperado:
    YYYY-MM-DD
    """

    if not data_inicio:
        raise ValueError(
            "Data início não informada."
        )

    if not data_fim:
        raise ValueError(
            "Data fim não informada."
        )

    try:
        data_ini = datetime.strptime(
            data_inicio,
            "%Y-%m-%d"
        ).date()

        data_fim_dt = datetime.strptime(
            data_fim,
            "%Y-%m-%d"
        ).date()

    except ValueError:
        raise ValueError(
            "As datas devem estar no formato YYYY-MM-DD. "
            "Exemplo: 2026-06-08."
        )

    if data_fim_dt < data_ini:
        raise ValueError(
            "A data fim não pode ser menor que a data início."
        )

    return data_ini, data_fim_dt


# ==========================================================
# GERAÇÃO DOS RELATÓRIOS
# ==========================================================

def gerar_relatorios(
    token: str,
    data_inicio: str,
    data_fim: str
) -> List[Dict]:
    """
    Gera relatórios diários do tipo 'DÍVIDA ATIVA' para o credor DNIT.

    Parâmetros:
        token:
            Token Bearer válido do Super Sapiens.

        data_inicio:
            Data inicial no formato YYYY-MM-DD.

        data_fim:
            Data final no formato YYYY-MM-DD.

    Retorno:
        Lista de dicionários:
        [
            {
                "data": "2026-06-08",
                "id_relatorio": 123456
            }
        ]
    """

    data_ini, data_fim_dt = validar_periodo(
        data_inicio,
        data_fim
    )

    headers = montar_headers(
        token,
        content_type="text/plain"
    )

    resultados = []

    dia_atual = data_ini

    while dia_atual <= data_fim_dt:
        data_ref = dia_atual.strftime(
            "%Y-%m-%d"
        )

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
            resp = requests.post(
                URL_RELATORIO,
                headers=headers,
                data=json.dumps(payload),
                timeout=TIMEOUT_REQUEST
            )

        except Exception as ex:
            print(
                f"⚠️ Erro de conexão em {data_ref}: {ex}"
            )

            dia_atual += timedelta(days=1)
            continue

        if resp.status_code == 201:
            try:
                dados = resp.json()

                rel_id = dados.get("id")

                if rel_id:
                    print(
                        f"✅ Relatório gerado com sucesso "
                        f"(ID: {rel_id})"
                    )

                    resultados.append({
                        "data": data_ref,
                        "id_relatorio": rel_id
                    })

                else:
                    print(
                        f"⚠️ Resposta sem ID de relatório "
                        f"para {data_ref}."
                    )

            except Exception as ex:
                print(
                    f"⚠️ Erro ao interpretar resposta JSON "
                    f"para {data_ref}: {ex}"
                )

        else:
            print(
                f"❌ Erro ao gerar relatório {data_ref}: "
                f"{resp.status_code}"
            )

            try:
                print(
                    "Detalhes:",
                    resp.json()
                )

            except Exception:
                print(
                    "Resposta bruta:",
                    resp.text
                )

        dia_atual += timedelta(days=1)

        time.sleep(
            PAUSA_ENTRE_REQUISICOES
        )

    print(
        f"\n📊 Total de relatórios gerados: "
        f"{len(resultados)}"
    )

    return resultados


# ==========================================================
# CONSULTA DO DOCUMENTO DO RELATÓRIO
# ==========================================================

def obter_documento_id(
    token: str,
    id_relatorio: int
) -> Optional[int]:
    """
    Obtém o ID do documento vinculado ao relatório.
    """

    url = (
        f"{BACKEND}/v1/administrativo/relatorio/"
        f"{id_relatorio}?populate=%5B%22documento%22%5D"
    )

    headers = montar_headers(
        token
    )

    try:
        resp = requests.get(
            url,
            headers=headers,
            timeout=TIMEOUT_REQUEST
        )

    except Exception as ex:
        print(
            f"❌ Erro ao consultar relatório "
            f"{id_relatorio}: {ex}"
        )

        return None

    if resp.status_code != 200:
        print(
            f"❌ Falha ao consultar relatório "
            f"{id_relatorio}: {resp.status_code}"
        )

        try:
            print(
                "Detalhes:",
                resp.json()
            )

        except Exception:
            print(
                "Resposta bruta:",
                resp.text
            )

        return None

    try:
        dados = resp.json()

        documento = dados.get(
            "documento"
        )

        if (
            documento
            and isinstance(documento, dict)
        ):
            return documento.get(
                "id"
            )

    except Exception as ex:
        print(
            f"⚠️ Erro ao processar JSON do relatório "
            f"{id_relatorio}: {ex}"
        )

    return None


# ==========================================================
# CONSULTA DO COMPONENTE DIGITAL
# ==========================================================

def obter_componente_digital_do_documento(
    token: str,
    id_documento: int
) -> Optional[int]:
    """
    Obtém o ID do componente digital vinculado a um documento.

    O relatório pode demorar alguns segundos para ficar pronto,
    por isso há tentativas com pausa.
    """

    url = (
        f"{BACKEND}/v1/administrativo/documento/"
        f"{id_documento}?populate=%5B%22componentesDigitais%22%5D"
    )

    headers = montar_headers(
        token
    )

    for tentativa in range(
        1,
        TENTATIVAS_DOCUMENTO + 1
    ):
        try:
            resp = requests.get(
                url,
                headers=headers,
                timeout=TIMEOUT_REQUEST
            )

        except Exception as ex:
            print(
                f"⚠️ Erro ao consultar documento "
                f"{id_documento} na tentativa "
                f"{tentativa}/{TENTATIVAS_DOCUMENTO}: {ex}"
            )

            time.sleep(
                PAUSA_DOCUMENTO_SEGUNDOS
            )

            continue

        if resp.status_code != 200:
            print(
                f"❌ Falha ao consultar documento "
                f"{id_documento}: {resp.status_code}"
            )

            time.sleep(
                PAUSA_DOCUMENTO_SEGUNDOS
            )

            continue

        try:
            dados = resp.json()

            componentes = dados.get(
                "componentesDigitais",
                []
            )

            if (
                isinstance(componentes, list)
                and componentes
            ):
                comp_id = componentes[0].get(
                    "id"
                )

                if comp_id:
                    print(
                        f"✅ Documento {id_documento} pronto. "
                        f"Componente digital: {comp_id}"
                    )

                    return comp_id

        except Exception as ex:
            print(
                f"⚠️ Erro ao ler JSON do documento "
                f"{id_documento}: {ex}"
            )

        print(
            f"⏳ Documento {id_documento} ainda sem "
            f"componente digital. Tentativa "
            f"{tentativa}/{TENTATIVAS_DOCUMENTO}. "
            f"Aguardando {PAUSA_DOCUMENTO_SEGUNDOS}s..."
        )

        time.sleep(
            PAUSA_DOCUMENTO_SEGUNDOS
        )

    print(
        f"⏰ Tempo limite atingido aguardando "
        f"documento {id_documento}."
    )

    return None


# ==========================================================
# DOWNLOAD DOS RELATÓRIOS
# ==========================================================

def identificar_extensao_download(
    content_type: str,
    conteudo: str = ""
) -> str:
    """
    Tenta identificar a extensão do arquivo retornado.
    """

    content_type = str(
        content_type or ""
    ).lower()

    conteudo = str(
        conteudo or ""
    ).lower()

    if (
        "spreadsheetml" in content_type
        or "excel" in content_type
        or "spreadsheetml" in conteudo
        or "excel" in conteudo
    ):
        return ".xlsx"

    if (
        "pdf" in content_type
        or "pdf" in conteudo
    ):
        return ".pdf"

    return ".xlsx"


def limpar_downloads_antigos(
    prefixo: str = "Relatorio_Extintos"
) -> None:
    """
    Remove arquivos antigos do módulo para evitar que a consolidação
    misture execuções anteriores.

    Esta função é chamada no início de baixar_relatorios().
    """

    garantir_diretorios()

    for nome in os.listdir(DOWNLOAD_DIR):
        if nome.startswith(prefixo):
            caminho = os.path.join(
                DOWNLOAD_DIR,
                nome
            )

            try:
                if os.path.isfile(caminho):
                    os.remove(caminho)

            except Exception as ex:
                print(
                    f"⚠️ Não foi possível remover arquivo antigo "
                    f"{caminho}: {ex}"
                )


def baixar_relatorios(
    token: str,
    relatorios: List[Dict],
    limpar_antes: bool = True
) -> List[str]:
    """
    Fluxo completo:
    relatório → documento → componente → download.

    Cada arquivo baixado é nomeado com a data do relatório.

    Parâmetros:
        token:
            Token Bearer válido.

        relatorios:
            Lista retornada por gerar_relatorios().

        limpar_antes:
            Se True, apaga arquivos antigos da pasta downloads antes
            de iniciar uma nova execução.

    Retorno:
        Lista de caminhos dos arquivos baixados.
    """

    garantir_diretorios()

    if limpar_antes:
        limpar_downloads_antigos()

    arquivos_baixados = []

    if not relatorios:
        print(
            "⚠️ Lista de relatórios vazia. "
            "Nenhum download será realizado."
        )

        return arquivos_baixados

    headers = montar_headers(
        token
    )

    for item in relatorios:
        relatorio_id = item.get(
            "id_relatorio"
        )

        data_ref = item.get(
            "data"
        )

        if not relatorio_id:
            print(
                f"⚠️ Item sem id_relatorio ignorado: {item}"
            )

            continue

        data_sufixo = (
            f"_{data_ref}"
            if data_ref
            else ""
        )

        print(
            f"\n📄 Processando relatório {relatorio_id} "
            f"(data {data_ref or '---'})..."
        )

        doc_id = obter_documento_id(
            token,
            relatorio_id
        )

        if not doc_id:
            print(
                f"⚠️ Nenhum documento encontrado no relatório "
                f"{relatorio_id}."
            )

            continue

        comp_id = obter_componente_digital_do_documento(
            token,
            doc_id
        )

        if not comp_id:
            print(
                f"⚠️ Documento {doc_id} não possui componente "
                f"digital disponível."
            )

            continue

        url_download = (
            f"{BACKEND}/v1/administrativo/componente_digital/"
            f"{comp_id}/download?context={{}}&populate=[]"
        )

        try:
            resp = requests.get(
                url_download,
                headers=headers,
                timeout=TIMEOUT_REQUEST
            )

        except Exception as ex:
            print(
                f"❌ Erro de conexão ao baixar componente "
                f"{comp_id}: {ex}"
            )

            continue

        if resp.status_code != 200:
            print(
                f"❌ Erro ao baixar componente {comp_id}: "
                f"{resp.status_code}"
            )

            try:
                print(
                    "Detalhes:",
                    resp.json()
                )

            except Exception:
                print(
                    "Resposta bruta:",
                    resp.text
                )

            continue

        content_type = resp.headers.get(
            "Content-Type",
            ""
        )

        try:
            if "application/json" in content_type.lower():
                dados = resp.json()

                conteudo = dados.get(
                    "conteudo",
                    ""
                )

                if not conteudo:
                    print(
                        f"⚠️ Nenhum conteúdo encontrado para "
                        f"componente {comp_id}."
                    )

                    continue

                extensao = identificar_extensao_download(
                    content_type,
                    conteudo
                )

                if "base64," in conteudo:
                    conteudo = conteudo.split(
                        "base64,",
                        1
                    )[1]

                nome_arquivo = (
                    f"Relatorio_Extintos{data_sufixo}_"
                    f"{comp_id}{extensao}"
                )

                caminho = os.path.join(
                    DOWNLOAD_DIR,
                    nome_arquivo
                )

                with open(caminho, "wb") as f:
                    f.write(
                        base64.b64decode(conteudo)
                    )

                print(
                    f"✅ Arquivo salvo em: {caminho}"
                )

                arquivos_baixados.append(
                    caminho
                )

            else:
                extensao = identificar_extensao_download(
                    content_type
                )

                nome_arquivo = (
                    f"Relatorio_Extintos{data_sufixo}_"
                    f"{comp_id}{extensao}"
                )

                caminho = os.path.join(
                    DOWNLOAD_DIR,
                    nome_arquivo
                )

                with open(caminho, "wb") as f:
                    f.write(
                        resp.content
                    )

                print(
                    f"✅ Arquivo binário salvo em: {caminho}"
                )

                arquivos_baixados.append(
                    caminho
                )

        except Exception as ex:
            print(
                f"❌ Erro ao salvar componente {comp_id}: {ex}"
            )

            continue

        time.sleep(
            PAUSA_ENTRE_REQUISICOES
        )

    print(
        f"\n📦 Total de arquivos baixados: "
        f"{len(arquivos_baixados)}"
    )

    return arquivos_baixados


# ==========================================================
# EXTRAÇÃO / CONSOLIDAÇÃO
# ==========================================================

def extrair_data_relatorio_do_nome(
    nome_arquivo: str
) -> str:
    """
    Extrai a data do nome do arquivo.

    Exemplo:
    Relatorio_Extintos_2026-06-08_123456.xlsx
    → 08/06/2026
    """

    partes_nome = str(
        nome_arquivo
    ).split("_")

    for parte in partes_nome:
        if (
            len(parte) == 10
            and parte[:4].isdigit()
            and parte[4] == "-"
        ):
            try:
                return datetime.strptime(
                    parte,
                    "%Y-%m-%d"
                ).strftime(
                    "%d/%m/%Y"
                )

            except Exception:
                continue

    return "N/D"


def corrigir_string_latin1(valor):
    """
    Corrige possíveis textos com problemas de encoding.
    Mantém compatibilidade com sua rotina original.
    """

    if not isinstance(valor, str):
        return valor

    try:
        return valor.encode(
            "latin1",
            errors="ignore"
        ).decode(
            "latin1"
        )

    except Exception:
        return valor


def preparar_lista_arquivos_excel(
    arquivos_baixados: Optional[List[str]] = None
) -> List[str]:
    """
    Define quais arquivos serão processados.

    Se arquivos_baixados for informado, processa apenas esses arquivos.
    Caso contrário, processa todos os Excel da pasta DOWNLOAD_DIR.
    """

    garantir_diretorios()

    if arquivos_baixados:
        arquivos = []

        for caminho in arquivos_baixados:
            if (
                caminho
                and os.path.exists(caminho)
                and caminho.lower().endswith((".xlsx", ".xls"))
            ):
                arquivos.append(
                    caminho
                )

        return arquivos

    arquivos = []

    for nome in os.listdir(DOWNLOAD_DIR):
        if nome.lower().endswith((".xlsx", ".xls")):
            arquivos.append(
                os.path.join(
                    DOWNLOAD_DIR,
                    nome
                )
            )

    return arquivos


def extrair_relatorios_downloads(
    arquivos_baixados: Optional[List[str]] = None,
    caminho_saida: Optional[str] = None
) -> Tuple[pd.DataFrame, str]:
    """
    Percorre relatórios Excel, extrai os campos a partir da linha 10
    e adiciona o campo 'Data do Relatório' obtido do nome do arquivo.

    Parâmetros:
        arquivos_baixados:
            Lista opcional com caminhos específicos para processar.
            Recomendo passar a lista retornada por baixar_relatorios(),
            para evitar misturar arquivos antigos.

        caminho_saida:
            Caminho opcional do CSV consolidado.

    Retorno:
        tuple:
            (df_final, caminho_csv)
    """

    garantir_diretorios()

    if not caminho_saida:
        caminho_saida = ARQUIVO_CONSOLIDADO

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

    arquivos_excel = preparar_lista_arquivos_excel(
        arquivos_baixados
    )

    print(
        f"\n📂 Procurando relatórios no diretório: "
        f"{DOWNLOAD_DIR}"
    )

    if not arquivos_excel:
        print(
            "⚠️ Nenhum arquivo Excel encontrado para consolidar."
        )

        df_vazio = pd.DataFrame(
            columns=colunas + ["Data do Relatório"]
        )

        return df_vazio, ""

    for caminho_arquivo in arquivos_excel:
        arquivo = os.path.basename(
            caminho_arquivo
        )

        print(
            f"📑 Processando arquivo: {arquivo}"
        )

        data_relatorio = extrair_data_relatorio_do_nome(
            arquivo
        )

        if data_relatorio == "N/D":
            print(
                f"⚠️ Data não identificada no nome do arquivo: "
                f"{arquivo}"
            )

        try:
            df = pd.read_excel(
                caminho_arquivo,
                skiprows=9,
                dtype=str
            )

            colunas_existentes = [
                col
                for col in colunas
                if col in df.columns
            ]

            if not colunas_existentes:
                print(
                    f"⚠️ Nenhuma coluna esperada encontrada em "
                    f"{arquivo}."
                )

                continue

            df = df[
                colunas_existentes
            ].copy()

            for col in df.select_dtypes(
                include="object"
            ).columns:
                df[col] = df[col].map(
                    corrigir_string_latin1
                )

            df["Data do Relatório"] = data_relatorio

            todos_dados.append(
                df
            )

            print(
                f"✅ {arquivo}: {len(df)} registros extraídos "
                f"({data_relatorio})"
            )

        except Exception as ex:
            print(
                f"⚠️ Erro ao processar {arquivo}: {ex}"
            )

    if not todos_dados:
        print(
            "❌ Nenhum relatório válido foi processado."
        )

        df_vazio = pd.DataFrame(
            columns=colunas + ["Data do Relatório"]
        )

        return df_vazio, ""

    df_final = pd.concat(
        todos_dados,
        ignore_index=True
    )

    if "Num_credito" in df_final.columns:
        df_final["Num_credito"] = (
            df_final["Num_credito"]
            .astype(str)
            .str.replace(r"\.0$", "", regex=True)
        )

        df_final["Num_credito"] = df_final[
            "Num_credito"
        ].apply(
            lambda x: f"'{x}" if x.isdigit() else x
        )

    for col in colunas:
        if col not in df_final.columns:
            df_final[col] = None

    df_final = df_final[
        colunas + ["Data do Relatório"]
    ]

    print(
        f"\n✅ Extração concluída: {len(df_final)} registros "
        f"de {len(todos_dados)} arquivo(s)."
    )

    os.makedirs(
        os.path.dirname(caminho_saida),
        exist_ok=True
    )

    df_final.to_csv(
        caminho_saida,
        index=False,
        sep=";",
        encoding="utf-8-sig"
    )

    print(
        f"📁 Arquivo CSV salvo com sucesso em: "
        f"{caminho_saida}"
    )

    return df_final, caminho_saida


# ==========================================================
# LIMPEZA OPCIONAL
# ==========================================================

def limpar_pasta_downloads() -> None:
    """
    Remove toda a pasta de downloads do módulo.
    Use apenas se quiser reiniciar completamente a extração.
    """

    if os.path.exists(DOWNLOAD_DIR):
        shutil.rmtree(
            DOWNLOAD_DIR,
            ignore_errors=True
        )

    os.makedirs(
        DOWNLOAD_DIR,
        exist_ok=True
    )


# ==========================================================
# PIPELINE COMPLETO
# ==========================================================

def executar_pipeline_extintos_pagamento(
    token: str,
    data_inicio: str,
    data_fim: str
) -> dict:
    """
    Executa o pipeline completo:
    gerar → baixar → consolidar.

    Esta função é útil caso você queira chamar tudo de uma vez.

    Retorno:
        dict com:
        - relatorios
        - arquivos
        - df
        - caminho_csv
    """

    print(
        "🚀 Iniciando pipeline de relatórios "
        "Extintos por Pagamento..."
    )

    print(
        f"📅 Período de referência: "
        f"{data_inicio} → {data_fim}"
    )

    relatorios = gerar_relatorios(
        token,
        data_inicio,
        data_fim
    )

    if not relatorios:
        print(
            "⚠️ Nenhum relatório foi gerado. "
            "Encerrando execução."
        )

        return {
            "relatorios": [],
            "arquivos": [],
            "df": pd.DataFrame(),
            "caminho_csv": ""
        }

    arquivos = baixar_relatorios(
        token,
        relatorios,
        limpar_antes=True
    )

    if not arquivos:
        print(
            "⚠️ Nenhum arquivo foi baixado. "
            "Verifique logs e permissões."
        )

        return {
            "relatorios": relatorios,
            "arquivos": [],
            "df": pd.DataFrame(),
            "caminho_csv": ""
        }

    df_final, caminho_csv = extrair_relatorios_downloads(
        arquivos_baixados=arquivos
    )

    print(
        "\n✅ Processo concluído com sucesso!"
    )

    print(
        f"📁 Arquivo final: {caminho_csv}"
    )

    return {
        "relatorios": relatorios,
        "arquivos": arquivos,
        "df": df_final,
        "caminho_csv": caminho_csv
    }