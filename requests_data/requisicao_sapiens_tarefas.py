# ==========================================================
# REQUISIÇÕES - SUPER SAPIENS - RELATÓRIOS DE TAREFAS
# ==========================================================
import os
import json
import time
import base64
from datetime import datetime

import pandas as pd
import requests


# ==========================================================
# CONFIGURAÇÕES
# ==========================================================
BACKEND = "https://supersapiensbackend.agu.gov.br"

URL_RELATORIO = (
    f"{BACKEND}/v1/administrativo/relatorio"
    "?populate=[]&context={}"
)

USUARIOS_NOMES = {
    61554: "Arthur",
    551246: "Yan",
    324199: "Raiana",
    324236: "Sabrina",
    313836: "Luiza",
}


# ==========================================================
# HELPERS
# ==========================================================
def _log(log, mensagem: str):
    """
    Envia logs para a aba Flet quando uma função log for informada.
    Caso contrário, usa print normalmente.
    """
    if log:
        log(mensagem)
    else:
        print(mensagem)


def _headers(token: str, content_type: str | None = None):
    headers = {
        "Accept": "application/json, text/plain, */*",
        "Authorization": f"Bearer {token}",
        "Origin": "https://supersapiens.agu.gov.br",
        "Referer": "https://supersapiens.agu.gov.br/",
    }

    if content_type:
        headers["Content-Type"] = content_type

    return headers


def criar_pasta_downloads(diretorio_downloads: str):
    os.makedirs(diretorio_downloads, exist_ok=True)


# ==========================================================
# GERAÇÃO DOS RELATÓRIOS
# ==========================================================
def gerar_relatorios(
    token: str,
    data_referencia: str,
    usuarios: list[int],
    log=None
):
    """
    Gera relatórios de tarefas no Super Sapiens para cada usuário informado.

    Parâmetros:
        token: Bearer token válido.
        data_referencia: Data no formato YYYY-MM-DD.
        usuarios: Lista de códigos de usuários.
        log: Função opcional para registrar logs na interface.

    Retorno:
        list[dict]: [{"usuario": codigo, "id_relatorio": id}]
    """

    headers = _headers(
        token,
        content_type="text/plain"
    )

    data_hora_inicio = f"{data_referencia}T00:00:00"
    data_hora_fim = f"{data_referencia}T23:55:00"

    resultados = []

    for usuario in usuarios:
        nome_usuario = USUARIOS_NOMES.get(
            int(usuario),
            str(usuario)
        )

        payload = {
            "formato": "xlsx",
            "nomeRelatorio": None,
            "documento": None,
            "observacao": None,
            "tipoRelatorio": 869,
            "parametros": json.dumps({
                "usuario": {
                    "name": "usuario",
                    "value": int(usuario),
                    "type": "entity",
                    "class": "SuppCore\\AdministrativoBackend\\Entity\\Usuario",
                    "getter": "getNome",
                },
                "dataHoraInicio": {
                    "name": "dataHoraInicio",
                    "value": data_hora_inicio,
                    "type": "dateTime",
                },
                "dataHoraFim": {
                    "name": "dataHoraFim",
                    "value": data_hora_fim,
                    "type": "dateTime",
                },
            }),
            "status": None,
            "generoRelatorio": {
                "nome": "OPERACIONAL",
                "descricao": "OPERACIONAL",
                "@type": "GeneroRelatorio",
                "@id": "/v1/administrativo/genero_relatorio/3",
            },
            "especieRelatorio": {
                "nome": "TAREFAS",
                "descricao": "TAREFA",
                "@type": "EspecieRelatorio",
                "@id": "/v1/administrativo/especie_relatorio/2",
            },
            "unidade": {
                "@type": "setor",
                "@id": "/v1/administrativo/setor/3541",
                "nome": (
                    "PROCURADORIA FEDERAL ESPECIALIZADA JUNTO AO "
                    "DEPARTAMENTO NACIONAL DE INFRAESTRUTURA DE TRANSPORTES"
                ),
            },
            "setor": {
                "@type": "setor",
                "@id": "/v1/administrativo/setor/54391",
                "nome": "MULTAS DE TRÂNSITO - SAPIENS DÍVIDA",
            },
        }

        _log(
            log,
            f"📤 Gerando relatório para {nome_usuario} ({usuario}) em {data_referencia}..."
        )

        try:
            resp = requests.post(
                URL_RELATORIO,
                headers=headers,
                data=json.dumps(payload),
                timeout=60
            )

        except Exception as ex:
            _log(
                log,
                f"⚠️ Erro de conexão para usuário {usuario}: {ex}"
            )
            continue

        if resp.status_code == 201:
            dados = resp.json()
            id_relatorio = dados.get("id")

            _log(
                log,
                f"✅ Relatório gerado para {nome_usuario}. ID: {id_relatorio}"
            )

            resultados.append({
                "usuario": int(usuario),
                "nome_usuario": nome_usuario,
                "id_relatorio": id_relatorio
            })

        else:
            _log(
                log,
                f"❌ Erro ao gerar relatório para {nome_usuario} ({usuario}): {resp.status_code}"
            )

            try:
                _log(
                    log,
                    f"Detalhes: {resp.json()}"
                )
            except Exception:
                _log(
                    log,
                    f"Resposta bruta: {resp.text}"
                )

    return resultados


# ==========================================================
# CONSULTA DO DOCUMENTO DO RELATÓRIO
# ==========================================================
def obter_documento_id(
    token: str,
    id_relatorio: int,
    log=None
):
    """
    Obtém o ID do documento vinculado ao relatório.
    """

    url = (
        f"{BACKEND}/v1/administrativo/relatorio/{id_relatorio}"
        "?populate=%5B%22documento%22%5D"
    )

    resp = requests.get(
        url,
        headers=_headers(token),
        timeout=60
    )

    if resp.status_code != 200:
        _log(
            log,
            f"❌ Falha ao consultar relatório {id_relatorio}: {resp.status_code}"
        )
        return None

    try:
        dados = resp.json()
        documento = dados.get("documento")

        if documento and isinstance(documento, dict):
            return documento.get("id")

    except Exception as ex:
        _log(
            log,
            f"⚠️ Erro ao processar JSON do relatório {id_relatorio}: {ex}"
        )

    return None


# ==========================================================
# CONSULTA DO COMPONENTE DIGITAL
# ==========================================================
def obter_componente_digital_do_documento(
    token: str,
    id_documento: int,
    log=None,
    tentativas: int = 10,
    espera_segundos: int = 5
):
    """
    Aguarda o documento ficar pronto e retorna o ID do componente digital.
    """

    url = (
        f"{BACKEND}/v1/administrativo/documento/{id_documento}"
        "?populate=%5B%22componentesDigitais%22%5D"
    )

    for tentativa in range(1, tentativas + 1):
        resp = requests.get(
            url,
            headers=_headers(token),
            timeout=60
        )

        if resp.status_code != 200:
            _log(
                log,
                f"❌ Falha ao consultar documento {id_documento}: {resp.status_code}"
            )
            time.sleep(espera_segundos)
            continue

        try:
            dados = resp.json()
            componentes = dados.get("componentesDigitais", [])

            if isinstance(componentes, list) and componentes:
                comp_id = componentes[0].get("id")

                _log(
                    log,
                    f"✅ Documento {id_documento} pronto. Componente digital: {comp_id}"
                )

                return comp_id

        except Exception as ex:
            _log(
                log,
                f"⚠️ Erro ao ler JSON do documento {id_documento}: {ex}"
            )

        _log(
            log,
            (
                f"⏳ Documento {id_documento} ainda sem componente digital "
                f"({tentativa}/{tentativas}). Aguardando {espera_segundos}s..."
            )
        )

        time.sleep(espera_segundos)

    _log(
        log,
        f"⏰ Tempo limite atingido aguardando documento {id_documento}."
    )

    return None


# ==========================================================
# DOWNLOAD DO COMPONENTE DIGITAL
# ==========================================================
def baixar_componente(
    token: str,
    comp_id: int,
    usuario: int,
    diretorio_downloads: str,
    log=None
):
    """
    Faz download do componente digital e salva localmente.
    Pode vir em Base64 ou binário.
    """

    criar_pasta_downloads(diretorio_downloads)

    url = (
        f"{BACKEND}/v1/administrativo/componente_digital/{comp_id}/download"
        "?context={}&populate=[]"
    )

    resp = requests.get(
        url,
        headers=_headers(token),
        timeout=120
    )

    if resp.status_code != 200:
        _log(
            log,
            f"❌ Erro ao baixar componente {comp_id}: {resp.status_code}"
        )
        return None

    nome_usuario = USUARIOS_NOMES.get(
        int(usuario),
        str(usuario)
    )

    content_type = resp.headers.get(
        "Content-Type",
        ""
    )

    # ======================================================
    # CASO 1: retorno JSON com conteúdo Base64
    # ======================================================
    if "application/json" in content_type:
        dados = resp.json()
        conteudo = dados.get("conteudo", "")

        if not conteudo:
            _log(
                log,
                f"⚠️ Nenhum conteúdo encontrado para componente {comp_id}"
            )
            return None

        if "base64," in conteudo:
            conteudo = conteudo.split("base64,", 1)[1]

        extensao = ".xlsx"

        if "application/pdf" in dados.get("conteudo", ""):
            extensao = ".pdf"

        nome_arquivo = (
            f"Relatorio_Tarefas_{nome_usuario}_{usuario}_{comp_id}{extensao}"
        )

        caminho = os.path.join(
            diretorio_downloads,
            nome_arquivo
        )

        with open(caminho, "wb") as f:
            f.write(
                base64.b64decode(conteudo)
            )

        _log(
            log,
            f"✅ Arquivo salvo em: {caminho}"
        )

        return caminho

    # ======================================================
    # CASO 2: retorno binário direto
    # ======================================================
    nome_arquivo = (
        f"Relatorio_Tarefas_{nome_usuario}_{usuario}_{comp_id}.xlsx"
    )

    caminho = os.path.join(
        diretorio_downloads,
        nome_arquivo
    )

    with open(caminho, "wb") as f:
        f.write(resp.content)

    _log(
        log,
        f"✅ Arquivo binário salvo em: {caminho}"
    )

    return caminho


# ==========================================================
# FLUXO COMPLETO DE DOWNLOAD
# ==========================================================
def baixar_relatorios(
    token: str,
    relatorios: list[dict],
    diretorio_downloads: str,
    log=None
):
    """
    Fluxo completo:
    relatório -> documento -> componente digital -> download.
    """

    criar_pasta_downloads(diretorio_downloads)

    arquivos_baixados = []

    for idx, item in enumerate(relatorios, 1):
        usuario = item["usuario"]
        relatorio_id = item["id_relatorio"]
        nome_usuario = item.get(
            "nome_usuario",
            USUARIOS_NOMES.get(usuario, str(usuario))
        )

        _log(
            log,
            (
                f"\n📄 [{idx}/{len(relatorios)}] Processando relatório "
                f"{relatorio_id} - {nome_usuario} ({usuario})..."
            )
        )

        time.sleep(5)

        doc_id = obter_documento_id(
            token,
            relatorio_id,
            log=log
        )

        if not doc_id:
            _log(
                log,
                f"⚠️ Nenhum documento encontrado no relatório {relatorio_id}."
            )
            continue

        comp_id = obter_componente_digital_do_documento(
            token,
            doc_id,
            log=log
        )

        if not comp_id:
            _log(
                log,
                f"⚠️ Documento {doc_id} não possui componente digital disponível."
            )
            continue

        caminho = baixar_componente(
            token,
            comp_id,
            usuario,
            diretorio_downloads,
            log=log
        )

        if caminho:
            arquivos_baixados.append(caminho)

    return arquivos_baixados


# ==========================================================
# EXTRAÇÃO / CONSOLIDAÇÃO DOS RELATÓRIOS
# ==========================================================
def extrair_relatorios_downloads(
    diretorio_downloads: str,
    caminho_saida_csv: str | None = None,
    log=None
):
    """
    Percorre todos os relatórios Excel no diretório informado,
    extrai os campos a partir da linha 10 e adiciona o campo 'Usuário'
    conforme o nome encontrado na linha 6.

    Retorna:
        DataFrame consolidado.
    """

    if not os.path.exists(diretorio_downloads):
        raise FileNotFoundError(
            f"Pasta de downloads não encontrada: {diretorio_downloads}"
        )

    colunas = [
        "Id",
        "NUP",
        "Inicio_prazo",
        "Final_prazo",
        "Setor",
        "Especie"
    ]

    todos_dados = []

    _log(
        log,
        f"\n📂 Procurando relatórios em: {diretorio_downloads}"
    )

    arquivos_excel = [
        f for f in os.listdir(diretorio_downloads)
        if f.lower().endswith((".xlsx", ".xls"))
    ]

    if not arquivos_excel:
        _log(
            log,
            "⚠️ Nenhum arquivo Excel encontrado na pasta de downloads."
        )

        return pd.DataFrame(
            columns=colunas + ["Usuário"]
        )

    for arquivo in arquivos_excel:
        caminho_arquivo = os.path.join(
            diretorio_downloads,
            arquivo
        )

        _log(
            log,
            f"📑 Processando arquivo: {arquivo}"
        )

        try:
            usuario_raw = pd.read_excel(
                caminho_arquivo,
                header=None,
                nrows=6
            ).iloc[5, 0]

            usuario_nome = (
                str(usuario_raw)
                .replace("usuario:", "")
                .replace("usuário:", "")
                .strip()
                .upper()
            )

            df = pd.read_excel(
                caminho_arquivo,
                skiprows=9,
                dtype=str
            )

            colunas_existentes = [
                col for col in colunas
                if col in df.columns
            ]

            df = df[colunas_existentes].copy()
            df["Usuário"] = usuario_nome

            todos_dados.append(df)

            _log(
                log,
                f"✅ {arquivo}: {len(df)} registros extraídos ({usuario_nome})"
            )

        except Exception as ex:
            _log(
                log,
                f"⚠️ Erro ao processar {arquivo}: {ex}"
            )

    if not todos_dados:
        _log(
            log,
            "❌ Nenhum relatório válido foi processado."
        )

        return pd.DataFrame(
            columns=colunas + ["Usuário"]
        )

    df_final = pd.concat(
        todos_dados,
        ignore_index=True
    )

    for campo in ["Id", "NUP"]:
        if campo in df_final.columns:
            df_final[campo] = df_final[campo].astype(str)

    _log(
        log,
        (
            f"\n✅ Extração concluída: {len(df_final)} registros "
            f"de {len(todos_dados)} arquivos."
        )
    )

    if caminho_saida_csv is None:
        caminho_saida_csv = os.path.join(
            diretorio_downloads,
            "Relatorios_Consolidados.csv"
        )

    df_final.to_csv(
        caminho_saida_csv,
        index=False,
        sep=";",
        encoding="utf-8-sig"
    )

    _log(
        log,
        f"📁 CSV consolidado salvo em: {caminho_saida_csv}"
    )

    return df_final