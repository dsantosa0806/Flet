# ==========================================================
# REQUISIÇÕES - SUPER SAPIENS
# CRÉDITOS SUSPENSOS POR PARCELAMENTO ATUALMENTE
# ==========================================================
import os
import re
import json
import time
import base64
from datetime import datetime
from typing import Optional, Callable, Dict, Any, List

import requests


# ==========================================================
# CONFIGURAÇÕES
# ==========================================================
BACKEND = "https://supersapiensbackend.agu.gov.br"

URL_RELATORIO = (
    f"{BACKEND}/v1/administrativo/relatorio"
    "?populate=%5B%5D&context=%7B%7D"
)

TIPO_RELATORIO_CREDITOS_SUSPENSOS_PARCELAMENTO = 809

NOME_RELATORIO = (
    "CRÉDITOS SUSPENSOS POR PARCELAMENTO ATUALMENTE (DETALHADO)"
)

TIMEOUT_REQUEST = 60
TIMEOUT_DOWNLOAD = 180

# Relatório pesado:
# 180 tentativas x 5 segundos = até 15 minutos aguardando.
TENTATIVAS_DOCUMENTO = 180
PAUSA_DOCUMENTO_SEGUNDOS = 5

LogFn = Optional[Callable[[str], None]]


# ==========================================================
# HELPERS
# ==========================================================
def _log(log: LogFn, mensagem: str):
    if log:
        log(mensagem)
    else:
        print(mensagem)


def _headers(
    token: str,
    content_type: Optional[str] = None
) -> dict:
    headers = {
        "Accept": "application/json, text/plain, */*",
        "Authorization": f"Bearer {token}",
        "Origin": "https://supersapiens.agu.gov.br",
        "Referer": "https://supersapiens.agu.gov.br/",
    }

    if content_type:
        headers["Content-Type"] = content_type

    return headers


def _sanitizar_nome_arquivo(nome: str) -> str:
    nome = str(nome or "").strip()

    if not nome:
        nome = "relatorio.xlsx"

    nome = re.sub(
        r'[\\/:*?"<>|]+',
        "_",
        nome
    )

    nome = re.sub(
        r"\s+",
        " ",
        nome
    ).strip()

    return nome


def criar_pasta_downloads(diretorio_downloads: str):
    os.makedirs(
        diretorio_downloads,
        exist_ok=True
    )


def _b64url_decode(data: str) -> bytes:
    padding = "=" * (-len(data) % 4)

    return base64.urlsafe_b64decode(
        data + padding
    )


def _extrair_payload_token(token: str) -> dict:
    try:
        payload_b64 = token.split(".")[1]

        payload_json = _b64url_decode(
            payload_b64
        ).decode("utf-8")

        return json.loads(
            payload_json
        )

    except Exception:
        return {}


def _extrair_usuario_id_do_token(token: str):
    payload = _extrair_payload_token(
        token
    )

    return payload.get("id")


def _extrair_numero_documento_principal_do_token(token: str) -> Optional[str]:
    """
    A request capturada usa o parâmetro numeroDocumentoPrincipal.

    Para evitar CPF fixo no código, buscamos o campo username do JWT.
    No Super Sapiens, normalmente username vem como CPF/login numérico.
    """

    payload = _extrair_payload_token(
        token
    )

    username = str(
        payload.get("username") or ""
    ).strip()

    somente_digitos = re.sub(
        r"\D",
        "",
        username
    )

    if somente_digitos:
        return somente_digitos

    env_doc = os.getenv(
        "SS_NUMERO_DOCUMENTO_PRINCIPAL",
        ""
    ).strip()

    env_doc = re.sub(
        r"\D",
        "",
        env_doc
    )

    if env_doc:
        return env_doc

    return None


# ==========================================================
# PAYLOAD
# ==========================================================
def montar_payload_creditos_suspensos_parcelamento(
    numero_documento_principal: str
) -> dict:
    """
    Monta payload equivalente à request capturada:

    tipoRelatorio: 809
    parametro: numeroDocumentoPrincipal
    especieRelatorio: DÍVIDA ATIVA
    """

    return {
        "formato": "xlsx",
        "nomeRelatorio": None,
        "documento": None,
        "observacao": None,
        "tipoRelatorio": TIPO_RELATORIO_CREDITOS_SUSPENSOS_PARCELAMENTO,
        "parametros": json.dumps({
            "numeroDocumentoPrincipal": {
                "name": "numeroDocumentoPrincipal",
                "value": str(numero_documento_principal),
                "type": "string",
            }
        }),
        "status": None,
        "generoRelatorio": {
            "nome": "OPERACIONAL",
            "descricao": "OPERACIONAL",
            "especiesRelatorios": None,
            "@type": "GeneroRelatorio",
            "@id": "/v1/administrativo/genero_relatorio/3",
            "@context": "/api/doc/#model-GeneroRelatorio",
            "ativo": True,
        },
        "especieRelatorio": {
            "nome": "DÍVIDA ATIVA",
            "ativo": True,
            "descricao": "DÍVIDA ATIVA",
            "generoRelatorio": None,
            "@type": "EspecieRelatorio",
            "@id": "/v1/administrativo/especie_relatorio/10",
            "@context": "/api/doc/#model-EspecieRelatorio",
            "uuid": "44d05bfe-acd3-4bae-8088-f7cab84edb36",
        },
    }


# ==========================================================
# GERAÇÃO DO RELATÓRIO
# ==========================================================
def gerar_relatorio_creditos_suspensos_parcelamento(
    token: str,
    log: LogFn = None
) -> Dict[str, Any]:
    numero_documento_principal = _extrair_numero_documento_principal_do_token(
        token
    )

    if not numero_documento_principal:
        raise RuntimeError(
            "Não foi possível identificar o numeroDocumentoPrincipal no token. "
            "Verifique se o token possui o campo username ou defina a variável "
            "de ambiente SS_NUMERO_DOCUMENTO_PRINCIPAL."
        )

    payload = montar_payload_creditos_suspensos_parcelamento(
        numero_documento_principal=numero_documento_principal
    )

    _log(
        log,
        f"📤 Solicitando relatório: {NOME_RELATORIO}..."
    )

    _log(
        log,
        "🔎 Parâmetro numeroDocumentoPrincipal identificado a partir do token."
    )

    resp = requests.post(
        URL_RELATORIO,
        headers=_headers(
            token,
            content_type="text/plain"
        ),
        data=json.dumps(payload),
        timeout=TIMEOUT_REQUEST
    )

    if resp.status_code not in (200, 201):
        try:
            detalhe = json.dumps(
                resp.json(),
                ensure_ascii=False
            )
        except Exception:
            detalhe = resp.text

        raise RuntimeError(
            f"Falha ao gerar relatório. HTTP {resp.status_code}: {detalhe}"
        )

    dados = resp.json()

    id_relatorio = dados.get("id")

    if not id_relatorio:
        raise RuntimeError(
            f"Relatório criado, mas sem ID na resposta: {dados}"
        )

    _log(
        log,
        f"✅ Relatório solicitado com sucesso. ID: {id_relatorio}"
    )

    return {
        "id_relatorio": id_relatorio,
        "uuid": dados.get("uuid"),
        "criado_em": dados.get("criadoEm"),
        "resposta": dados,
    }


# ==========================================================
# CONSULTA DO RELATÓRIO
# ==========================================================
def consultar_relatorio_por_id(
    token: str,
    id_relatorio: int,
    log: LogFn = None
) -> Optional[dict]:
    url = (
        f"{BACKEND}/v1/administrativo/relatorio/{id_relatorio}"
        "?populate=%5B%22documento%22,%22tipoRelatorio%22%5D"
        "&context=%7B%7D"
    )

    resp = requests.get(
        url,
        headers=_headers(token),
        timeout=TIMEOUT_REQUEST
    )

    if resp.status_code != 200:
        _log(
            log,
            f"⚠️ Falha ao consultar relatório {id_relatorio}. HTTP {resp.status_code}"
        )
        return None

    return resp.json()


def listar_relatorios_recentes_usuario(
    token: str,
    usuario_id: int,
    limite: int = 10,
    log: LogFn = None
) -> List[dict]:
    """
    Fallback igual à request capturada:
    /relatorio?where={"criadoPor.id":"eq:ID"}&limit=10...
    """

    url = f"{BACKEND}/v1/administrativo/relatorio"

    params = {
        "where": json.dumps({
            "criadoPor.id": f"eq:{usuario_id}"
        }),
        "limit": limite,
        "offset": 0,
        "order": json.dumps({
            "id": "DESC"
        }),
        "populate": json.dumps([
            "documento",
            "tipoRelatorio",
            "vinculacoesEtiquetas",
            "vinculacoesEtiquetas.etiqueta",
        ]),
        "context": "{}",
    }

    resp = requests.get(
        url,
        headers=_headers(token),
        params=params,
        timeout=TIMEOUT_REQUEST
    )

    if resp.status_code != 200:
        _log(
            log,
            f"⚠️ Falha ao listar relatórios recentes. HTTP {resp.status_code}"
        )
        return []

    dados = resp.json()

    entidades = dados.get("entities")

    if isinstance(entidades, list):
        return entidades

    if isinstance(dados, list):
        return dados

    return []


def aguardar_documento_relatorio(
    token: str,
    id_relatorio: int,
    log: LogFn = None,
    tentativas: int = TENTATIVAS_DOCUMENTO,
    espera_segundos: int = PAUSA_DOCUMENTO_SEGUNDOS
) -> Optional[int]:
    """
    Aguarda o relatório pesado ser processado e receber documento.

    Como este relatório costuma demorar mais de 5 minutos,
    usamos 180 tentativas de 5 segundos.
    """

    usuario_id = _extrair_usuario_id_do_token(
        token
    )

    inicio = time.time()

    for tentativa in range(1, tentativas + 1):
        dados = consultar_relatorio_por_id(
            token=token,
            id_relatorio=id_relatorio,
            log=log
        )

        if dados:
            documento = dados.get("documento")

            if isinstance(documento, dict) and documento.get("id"):
                doc_id = documento.get("id")

                tempo_total = int(
                    time.time() - inicio
                )

                _log(
                    log,
                    (
                        f"✅ Documento vinculado encontrado. "
                        f"Documento ID: {doc_id}. "
                        f"Tempo aguardado: {tempo_total}s."
                    )
                )

                return doc_id

        # Fallback pela listagem recente do usuário
        if usuario_id:
            recentes = listar_relatorios_recentes_usuario(
                token=token,
                usuario_id=usuario_id,
                limite=10,
                log=log
            )

            for item in recentes:
                if int(item.get("id", 0)) != int(id_relatorio):
                    continue

                documento = item.get("documento")

                if isinstance(documento, dict) and documento.get("id"):
                    doc_id = documento.get("id")

                    tempo_total = int(
                        time.time() - inicio
                    )

                    _log(
                        log,
                        (
                            f"✅ Documento encontrado pela listagem recente. "
                            f"Documento ID: {doc_id}. "
                            f"Tempo aguardado: {tempo_total}s."
                        )
                    )

                    return doc_id

        tempo_total = int(
            time.time() - inicio
        )

        _log(
            log,
            (
                f"⏳ Relatório {id_relatorio} ainda sem documento "
                f"({tentativa}/{tentativas}). "
                f"Tempo aguardado: {tempo_total}s. "
                f"Nova tentativa em {espera_segundos}s..."
            )
        )

        time.sleep(
            espera_segundos
        )

    return None


# ==========================================================
# COMPONENTE DIGITAL
# ==========================================================
def obter_componente_digital_do_documento(
    token: str,
    id_documento: int,
    log: LogFn = None,
    tentativas: int = TENTATIVAS_DOCUMENTO,
    espera_segundos: int = PAUSA_DOCUMENTO_SEGUNDOS
) -> Optional[int]:
    """
    Consulta o documento até localizar componentesDigitais[0].id.
    """

    url = (
        f"{BACKEND}/v1/administrativo/documento/{id_documento}"
        "?populate=%5B%22componentesDigitais%22%5D"
        "&context=%7B%7D"
    )

    inicio = time.time()

    for tentativa in range(1, tentativas + 1):
        resp = requests.get(
            url,
            headers=_headers(token),
            timeout=TIMEOUT_REQUEST
        )

        if resp.status_code != 200:
            _log(
                log,
                f"⚠️ Falha ao consultar documento {id_documento}. HTTP {resp.status_code}"
            )

            time.sleep(
                espera_segundos
            )
            continue

        dados = resp.json()

        componentes = dados.get("componentesDigitais") or []

        if isinstance(componentes, list) and componentes:
            comp_id = componentes[0].get("id")

            if comp_id:
                tempo_total = int(
                    time.time() - inicio
                )

                _log(
                    log,
                    (
                        f"✅ Componente digital localizado. "
                        f"ID: {comp_id}. "
                        f"Tempo aguardado nesta etapa: {tempo_total}s."
                    )
                )

                return comp_id

        tempo_total = int(
            time.time() - inicio
        )

        _log(
            log,
            (
                f"⏳ Documento {id_documento} ainda sem componente digital "
                f"({tentativa}/{tentativas}). "
                f"Tempo aguardado: {tempo_total}s. "
                f"Nova tentativa em {espera_segundos}s..."
            )
        )

        time.sleep(
            espera_segundos
        )

    return None


# ==========================================================
# DOWNLOAD
# ==========================================================
def baixar_componente_digital(
    token: str,
    comp_id: int,
    diretorio_downloads: str,
    log: LogFn = None
) -> Optional[str]:
    """
    Baixa o componente digital.
    O backend pode retornar:
    - JSON com campo conteudo em base64;
    - ou binário direto.
    """

    criar_pasta_downloads(
        diretorio_downloads
    )

    url = (
        f"{BACKEND}/v1/administrativo/componente_digital/{comp_id}/download"
        "?context=%7B%7D&populate=%5B%5D"
    )

    _log(
        log,
        f"📥 Baixando componente digital {comp_id}..."
    )

    resp = requests.get(
        url,
        headers=_headers(token),
        timeout=TIMEOUT_DOWNLOAD
    )

    if resp.status_code != 200:
        raise RuntimeError(
            f"Erro ao baixar componente {comp_id}. HTTP {resp.status_code}: {resp.text}"
        )

    content_type = resp.headers.get(
        "Content-Type",
        ""
    ).lower()

    texto_inicial = resp.text[:20].strip() if resp.text else ""

    timestamp = datetime.now().strftime(
        "%Y-%m-%d_%H-%M-%S"
    )

    # ======================================================
    # CASO 1: JSON com base64
    # ======================================================
    if "json" in content_type or texto_inicial.startswith("{"):
        dados = resp.json()

        nome_arquivo = dados.get(
            "fileName",
            f"Creditos_Suspensos_Parcelamento_{timestamp}.xlsx"
        )

        nome_arquivo = _sanitizar_nome_arquivo(
            nome_arquivo
        )

        conteudo = dados.get(
            "conteudo",
            ""
        )

        if not conteudo:
            raise RuntimeError(
                f"Componente {comp_id} não retornou conteúdo para download."
            )

        if "base64," in conteudo:
            conteudo = conteudo.split(
                "base64,",
                1
            )[1]

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
    # CASO 2: binário direto
    # ======================================================
    nome_arquivo = _sanitizar_nome_arquivo(
        f"Creditos_Suspensos_Parcelamento_{comp_id}_{timestamp}.xlsx"
    )

    caminho = os.path.join(
        diretorio_downloads,
        nome_arquivo
    )

    with open(caminho, "wb") as f:
        f.write(
            resp.content
        )

    _log(
        log,
        f"✅ Arquivo binário salvo em: {caminho}"
    )

    return caminho


# ==========================================================
# FLUXO COMPLETO
# ==========================================================
def executar_fluxo_creditos_suspensos_parcelamento(
    token: str,
    diretorio_downloads: str,
    log: LogFn = None
) -> Dict[str, Any]:
    """
    Fluxo completo:
    1. Gera relatório;
    2. Aguarda documento;
    3. Aguarda componente digital;
    4. Baixa XLSX.
    """

    criar_pasta_downloads(
        diretorio_downloads
    )

    relatorio = gerar_relatorio_creditos_suspensos_parcelamento(
        token=token,
        log=log
    )

    id_relatorio = relatorio["id_relatorio"]

    doc_id = aguardar_documento_relatorio(
        token=token,
        id_relatorio=id_relatorio,
        log=log
    )

    if not doc_id:
        raise RuntimeError(
            (
                f"Relatório {id_relatorio} não gerou documento dentro do tempo limite. "
                "Aumente TENTATIVAS_DOCUMENTO se necessário."
            )
        )

    comp_id = obter_componente_digital_do_documento(
        token=token,
        id_documento=doc_id,
        log=log
    )

    if not comp_id:
        raise RuntimeError(
            f"Documento {doc_id} não gerou componente digital dentro do tempo limite."
        )

    arquivo = baixar_componente_digital(
        token=token,
        comp_id=comp_id,
        diretorio_downloads=diretorio_downloads,
        log=log
    )

    if not arquivo:
        raise RuntimeError(
            "Não foi possível baixar o arquivo do relatório."
        )

    return {
        "id_relatorio": id_relatorio,
        "id_documento": doc_id,
        "id_componente": comp_id,
        "arquivo": arquivo,
    }