# ==========================================================
# REQUISIÇÕES - SUPER SAPIENS
# TAREFAS EM ABERTO EM UM SETOR ATUALMENTE - DETALHADO
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

TIPO_RELATORIO_TAREFAS_ABERTO_SETOR = 427

SETOR_ID_PADRAO = 54391
SETOR_NOME_PADRAO = "MULTAS DE TRÂNSITO - SAPIENS DÍVIDA"

UNIDADE_ID_PADRAO = 3541
UNIDADE_NOME_PADRAO = (
    "PROCURADORIA FEDERAL ESPECIALIZADA JUNTO AO "
    "DEPARTAMENTO NACIONAL DE INFRAESTRUTURA DE TRANSPORTES"
)

TIMEOUT_REQUEST = 60
TIMEOUT_DOWNLOAD = 120

TENTATIVAS_DOCUMENTO = 18
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


def _extrair_usuario_id_do_token(token: str):
    """
    Extrai o campo id do payload JWT.
    Usado apenas como fallback para consultar a listagem de relatórios recentes.
    """

    try:
        payload_b64 = token.split(".")[1]

        padding = "=" * (-len(payload_b64) % 4)

        payload_json = base64.urlsafe_b64decode(
            payload_b64 + padding
        ).decode("utf-8")

        payload = json.loads(
            payload_json
        )

        return payload.get("id")

    except Exception:
        return None


# ==========================================================
# GERAÇÃO DO RELATÓRIO
# ==========================================================
def montar_payload_tarefas_em_aberto_setor(
    setor_id: int = SETOR_ID_PADRAO
) -> dict:
    """
    Monta o payload equivalente à request capturada no navegador.
    """

    return {
        "formato": "xlsx",
        "nomeRelatorio": None,
        "documento": None,
        "observacao": None,
        "tipoRelatorio": TIPO_RELATORIO_TAREFAS_ABERTO_SETOR,
        "parametros": json.dumps({
            "setor": {
                "name": "setor",
                "value": int(setor_id),
                "type": "entity",
                "class": "SuppCore\\AdministrativoBackend\\Entity\\Setor",
                "getter": "getNome",
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
            "nome": "TAREFAS",
            "ativo": True,
            "descricao": "TAREFA",
            "generoRelatorio": None,
            "@type": "EspecieRelatorio",
            "@id": "/v1/administrativo/especie_relatorio/2",
            "@context": "/api/doc/#model-EspecieRelatorio",
            "uuid": "94717970-fdf0-4494-b3ca-bfe3894e4f28",
        },
        "unidade": {
            "ativo": True,
            "sigla": "PFE-DNIT",
            "prefixoNUP": "00784",
            "@type": "setor",
            "@id": f"/v1/administrativo/setor/{UNIDADE_ID_PADRAO}",
            "@context": "/api/doc/#model-setor",
            "nome": UNIDADE_NOME_PADRAO,
        },
    }


def gerar_relatorio_tarefas_em_aberto_setor(
    token: str,
    setor_id: int = SETOR_ID_PADRAO,
    log: LogFn = None
) -> Dict[str, Any]:
    """
    Solicita a geração do relatório tipo 427.

    Retorna:
        {
            "id_relatorio": 123,
            "uuid": "...",
            "criado_em": "..."
        }
    """

    payload = montar_payload_tarefas_em_aberto_setor(
        setor_id=setor_id
    )

    _log(
        log,
        f"📤 Solicitando relatório de tarefas em aberto do setor {setor_id}..."
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
        detalhe = ""

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
# CONSULTA DO RELATÓRIO / DOCUMENTO
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
    Fallback baseado na request capturada:
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
    Aguarda o relatório ser processado e possuir documento vinculado.
    """

    usuario_id = _extrair_usuario_id_do_token(
        token
    )

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

                _log(
                    log,
                    f"✅ Documento vinculado encontrado. Documento ID: {doc_id}"
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

                    _log(
                        log,
                        f"✅ Documento encontrado pela listagem recente. Documento ID: {doc_id}"
                    )

                    return doc_id

        _log(
            log,
            (
                f"⏳ Relatório {id_relatorio} ainda sem documento "
                f"({tentativa}/{tentativas}). Aguardando {espera_segundos}s..."
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
                _log(
                    log,
                    f"✅ Componente digital localizado. ID: {comp_id}"
                )

                return comp_id

        _log(
            log,
            (
                f"⏳ Documento {id_documento} ainda sem componente digital "
                f"({tentativa}/{tentativas}). Aguardando {espera_segundos}s..."
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

    timestamp = datetime.now().strftime(
        "%Y-%m-%d_%H-%M-%S"
    )

    # ======================================================
    # CASO 1: JSON com base64
    # ======================================================
    if "json" in content_type:
        dados = resp.json()

        nome_arquivo = dados.get(
            "fileName",
            f"Tarefas_Em_Aberto_Setor_{timestamp}.xlsx"
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
        f"Tarefas_Em_Aberto_Setor_{comp_id}_{timestamp}.xlsx"
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
def executar_fluxo_tarefas_em_aberto_setor(
    token: str,
    diretorio_downloads: str,
    setor_id: int = SETOR_ID_PADRAO,
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

    relatorio = gerar_relatorio_tarefas_em_aberto_setor(
        token=token,
        setor_id=setor_id,
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
            f"Relatório {id_relatorio} não gerou documento dentro do tempo limite."
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