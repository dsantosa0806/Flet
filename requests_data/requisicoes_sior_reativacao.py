# ==========================================================
# REQUISIÇÕES SIOR - REATIVAÇÃO DE COBRANÇA
# ==========================================================
import json
import math
import time
import uuid
from datetime import datetime
from typing import Callable, Iterable, List, Dict, Any, Optional
from urllib.parse import urljoin

import pandas as pd
import requests


# ==========================================================
# URLS / CONSTANTES
# ==========================================================
BASE_HOST = "https://servicos.dnit.gov.br"
BASE_SIOR = f"{BASE_HOST}/sior"

URL_ANULAR_PAGE = f"{BASE_SIOR}/Cobranca/SuspensaoCobranca/Anular"
URL_LIST_SUSPENSOES_CONSULTA = f"{BASE_SIOR}/Cobranca/SuspensaoCobranca/ListSuspensoesConsulta"
URL_ADD_ALL_SUSPENSOES = f"{BASE_SIOR}/Cobranca/SuspensaoCobranca/AddAllSuspensoes"
URL_LIST_ANULAR_SUSPENSAO = f"{BASE_SIOR}/Cobranca/SuspensaoCobranca/ListAnularSuspensao"
URL_ANULAR = f"{BASE_SIOR}/Cobranca/SuspensaoCobranca/Anular"
URL_INDEX_BIND = f"{BASE_SIOR}/Cobranca/SuspensaoCobranca?Bind=True"

LIMITE_AUTOS_POR_REQUISICAO = 100

LogFn = Optional[Callable[[str], None]]


# ==========================================================
# LOG / HELPERS BÁSICOS
# ==========================================================
def _log(log: LogFn, mensagem: str) -> None:
    if log:
        log(mensagem)


def _guid(session: requests.Session) -> str:
    guid = getattr(session, "_sior_lt_guid_reativacao", None)

    if not guid:
        guid = str(uuid.uuid4())
        setattr(session, "_sior_lt_guid_reativacao", guid)

    return guid


def renovar_lt_guid(session: requests.Session) -> str:
    guid = str(uuid.uuid4())
    setattr(session, "_sior_lt_guid_reativacao", guid)
    return guid


def _sessao_expirada_texto(texto: str) -> bool:
    texto = texto or ""

    return (
        "A sua sessão expirou" in texto
        or "Account/Login" in texto
        or "/Account/Login" in texto
        or "Entrar com gov.br" in texto
    )


def _url_absoluta_sior(url: str) -> str:
    if not url:
        return URL_INDEX_BIND

    return urljoin(BASE_HOST, url)


# ==========================================================
# HEADERS
# ==========================================================
def preparar_headers_reativacao(session: requests.Session) -> None:
    session.headers.update(
        {
            "Accept": "*/*",
            "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
            "Origin": BASE_HOST,
            "Referer": URL_ANULAR_PAGE,
            "Host": "servicos.dnit.gov.br",
            "X-Lt-Session-Guid": _guid(session),
            "X-Requested-With": "XMLHttpRequest",
        }
    )


def _headers_ajax_json(session: requests.Session) -> Dict[str, str]:
    preparar_headers_reativacao(session)

    return {
        "Accept": "*/*",
        "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
        "Content-Type": "application/json; charset=UTF-8",
        "Origin": BASE_HOST,
        "Referer": URL_ANULAR_PAGE,
        "Host": "servicos.dnit.gov.br",
        "X-Lt-Session-Guid": _guid(session),
        "X-Requested-With": "XMLHttpRequest",
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "same-origin",
    }


def _headers_ajax_get(session: requests.Session) -> Dict[str, str]:
    preparar_headers_reativacao(session)

    return {
        "Accept": "*/*",
        "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
        "Referer": URL_ANULAR_PAGE,
        "Host": "servicos.dnit.gov.br",
        "X-Lt-Session-Guid": _guid(session),
        "X-Requested-With": "XMLHttpRequest",
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "same-origin",
    }


def _headers_ajax_form(session: requests.Session) -> Dict[str, str]:
    preparar_headers_reativacao(session)

    return {
        "Accept": "*/*",
        "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        "Origin": BASE_HOST,
        "Referer": URL_ANULAR_PAGE,
        "Host": "servicos.dnit.gov.br",
        "X-Lt-Session-Guid": _guid(session),
        "X-Requested-With": "XMLHttpRequest",
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "same-origin",
    }


def _headers_html(referer: str = None) -> Dict[str, str]:
    return {
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
        "Referer": referer or f"{BASE_SIOR}/",
        "Host": "servicos.dnit.gov.br",
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
    }


# ==========================================================
# INICIALIZAÇÃO DA TELA / CICLO DE LOTE
# ==========================================================
def inicializar_tela_reativacao(
    session: requests.Session,
    log: LogFn = None,
    timeout: int = 60,
    renovar_guid: bool = False,
) -> None:
    """
    Inicializa a tela de Reativação/Anulação de Suspensão.

    Fluxo equivalente ao navegador:
    1. Acessa a tela base Bind.
    2. Abre a tela /Anular.
    3. Prepara headers AJAX com Referer da tela /Anular.
    """
    if renovar_guid:
        renovar_lt_guid(session)

    preparar_headers_reativacao(session)

    _log(log, "🌐 Inicializando tela de Reativação via requests.Session...")

    resp_bind = session.get(
        URL_INDEX_BIND,
        headers=_headers_html(referer=f"{BASE_SIOR}/"),
        timeout=timeout,
        allow_redirects=True,
    )

    if resp_bind.status_code not in (200, 201, 204):
        raise RuntimeError(
            f"Falha ao acessar tela Bind da reativação. "
            f"HTTP {resp_bind.status_code}: {resp_bind.text[:500]}"
        )

    if _sessao_expirada_texto(resp_bind.text or ""):
        raise RuntimeError(
            "Sessão expirada ao acessar tela Bind da reativação via requests.Session."
        )

    time.sleep(0.2)

    resp_anular = session.get(
        URL_ANULAR_PAGE,
        headers=_headers_html(referer=URL_INDEX_BIND),
        timeout=timeout,
        allow_redirects=True,
    )

    if resp_anular.status_code != 200:
        raise RuntimeError(
            f"Falha ao inicializar tela Anular/Reativar via Session. "
            f"HTTP {resp_anular.status_code}: {resp_anular.text[:500]}"
        )

    if _sessao_expirada_texto(resp_anular.text or ""):
        raise RuntimeError(
            "A tela Anular retornou login/sessão expirada via requests.Session. "
            "Os cookies do navegador não foram sincronizados corretamente para a Session."
        )

    preparar_headers_reativacao(session)

    _log(log, "✅ Tela Anular/Reativar inicializada via requests.Session.")


def navegar_pos_reativacao(
    session: requests.Session,
    resp_create: requests.Response,
    log: LogFn = None,
    timeout: int = 60,
) -> None:
    """
    Após o POST /Anular, o SIOR retorna notify-after-navigate.
    Simulamos a navegação para encerrar corretamente o ciclo do lote.
    """
    url_navegacao = URL_INDEX_BIND

    try:
        dados = resp_create.json()

        for action in dados.get("actions", []) or []:
            options = action.get("options", {}) or {}
            url = options.get("url")

            if url:
                url_navegacao = _url_absoluta_sior(url)
                break

    except Exception:
        url_navegacao = URL_INDEX_BIND

    _log(log, f"➡️ Navegando pós-reativação: {url_navegacao}")

    resp = session.get(
        url_navegacao,
        headers=_headers_html(referer=URL_ANULAR_PAGE),
        timeout=timeout,
        allow_redirects=True,
    )

    if resp.status_code not in (200, 201, 204):
        raise RuntimeError(
            f"Falha ao navegar pós-reativação. "
            f"HTTP {resp.status_code}: {resp.text[:500]}"
        )

    if _sessao_expirada_texto(resp.text or ""):
        raise RuntimeError("Sessão expirada ao navegar pós-reativação.")

    _log(log, "✅ Navegação pós-reativação concluída.")


# ==========================================================
# UTILITÁRIOS
# ==========================================================
def chunked(
    lista: List[str],
    tamanho: int = LIMITE_AUTOS_POR_REQUISICAO,
) -> Iterable[List[str]]:
    for i in range(0, len(lista), tamanho):
        yield lista[i:i + tamanho]


def _extrair_campo_data(valor: Any) -> str:
    if isinstance(valor, dict):
        return valor.get("DateString", "")

    return valor or ""


def _registro_log_base(
    auto: str,
    motivo: str,
    status: str,
    mensagem: str,
    item_sior: Optional[Dict[str, Any]] = None,
    lote: Optional[int] = None,
) -> Dict[str, Any]:
    item_sior = item_sior or {}

    return {
        "DataHora": datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
        "Lote": lote,
        "AUTO": auto,
        "MOTIVO": motivo,
        "Status": status,
        "Mensagem": mensagem,
        "InfracaoCodigoProcesso": item_sior.get("InfracaoCodigoProcesso", ""),
        "NUPSapiensSei": item_sior.get("NUPSapiensSei", ""),
        "Devedor": item_sior.get("Devedor", ""),
        "TipoRecuperacaoCredito": item_sior.get("TipoRecuperacaoCredito", ""),
        "DataConstituicaoDefinitiva": _extrair_campo_data(
            item_sior.get("DataConstituicaoDefinitiva", "")
        ),
        "ValorOriginal": item_sior.get("ValorOriginal", ""),
        "Enquadramento": item_sior.get("Enquadramento", ""),
        "Id": item_sior.get("Id", ""),
    }


# ==========================================================
# REQUESTS SIOR - REATIVAÇÃO
# ==========================================================
def consultar_suspensoes_para_reativacao(
    session: requests.Session,
    autos: List[str],
    log: LogFn = None,
    timeout: int = 60,
) -> Dict[str, Any]:
    """
    Primeira request da ordem informada:

    POST ListSuspensoesConsulta

    Ela consulta quais autos suspensos existem para reativação.
    """
    preparar_headers_reativacao(session)

    payload = {
        "sort": "",
        "page": 1,
        "pageSize": max(10, len(autos)),
        "group": "",
        "filter": "",
        "NumeroAuto": "\r\n".join(autos),
        "NUPSapiensSei": "",
        "Devedor": "",
    }

    _log(
        log,
        f"🔎 Consultando suspensões disponíveis para reativação | {len(autos)} AIT(s)."
    )

    resp = session.post(
        URL_LIST_SUSPENSOES_CONSULTA,
        headers=_headers_ajax_form(session),
        data=payload,
        timeout=timeout,
    )

    if resp.status_code not in (200, 201):
        raise RuntimeError(
            f"Falha no ListSuspensoesConsulta. "
            f"HTTP {resp.status_code}: {resp.text[:1000]}"
        )

    texto = resp.text or ""

    if _sessao_expirada_texto(texto):
        raise RuntimeError(
            f"Sessão expirada no ListSuspensoesConsulta: {texto[:1000]}"
        )

    try:
        dados = resp.json()
    except Exception:
        raise RuntimeError(
            f"Resposta inválida do ListSuspensoesConsulta: {resp.text[:1000]}"
        )

    total = dados.get(
        "Total",
        len(dados.get("Data", []) or [])
    )

    _log(
        log,
        f"📋 ListSuspensoesConsulta retornou {total} registro(s)."
    )

    return dados


def add_all_suspensoes(
    session: requests.Session,
    autos: List[str],
    return_total: bool,
    log: LogFn = None,
    timeout: int = 60,
) -> Dict[str, Any]:
    """
    Segunda e terceira requests da ordem informada:

    POST AddAllSuspensoes returnTotal=True
    POST AddAllSuspensoes returnTotal=False
    """
    preparar_headers_reativacao(session)

    payload = {
        "NumeroAuto": "\r\n".join(autos),
        "returnTotal": return_total,
    }

    etapa = "validando/contando" if return_total else "carregando lista temporária"

    _log(
        log,
        f"📥 AddAllSuspensoes ({etapa}) | {len(autos)} AIT(s)."
    )

    resp = session.post(
        URL_ADD_ALL_SUSPENSOES,
        headers=_headers_ajax_json(session),
        data=json.dumps(payload, ensure_ascii=False),
        timeout=timeout,
    )

    if resp.status_code not in (200, 201, 204):
        raise RuntimeError(
            f"Falha no AddAllSuspensoes returnTotal={return_total}. "
            f"HTTP {resp.status_code}: {resp.text[:1000]}"
        )

    texto = (resp.text or "").strip()

    if not texto:
        return {
            "Total": None,
            "Raw": "",
            "returnTotal": return_total,
            "status_code": resp.status_code,
        }

    if _sessao_expirada_texto(texto):
        raise RuntimeError(
            f"Sessão expirada no AddAllSuspensoes returnTotal={return_total}: {texto[:1000]}"
        )

    try:
        dados = resp.json()

        if isinstance(dados, dict):
            dados["returnTotal"] = return_total
            dados["status_code"] = resp.status_code
            return dados

        return {
            "Data": dados,
            "returnTotal": return_total,
            "status_code": resp.status_code,
        }

    except Exception:
        return {
            "Raw": texto,
            "returnTotal": return_total,
            "status_code": resp.status_code,
        }


def listar_anular_suspensao(
    session: requests.Session,
    page_size: int = LIMITE_AUTOS_POR_REQUISICAO,
    log: LogFn = None,
    timeout: int = 60,
) -> Dict[str, Any]:
    """
    Quarta request da ordem informada:

    GET ListAnularSuspensao
    """
    preparar_headers_reativacao(session)

    params = {
        "sort": "",
        "page": 1,
        "pageSize": max(10, int(page_size)),
        "group": "",
        "filter": "",
        "_": int(time.time() * 1000),
    }

    resp = session.get(
        URL_LIST_ANULAR_SUSPENSAO,
        params=params,
        headers=_headers_ajax_get(session),
        timeout=timeout,
    )

    if resp.status_code not in (200, 201):
        raise RuntimeError(
            f"Falha no ListAnularSuspensao. "
            f"HTTP {resp.status_code}: {resp.text[:1000]}"
        )

    texto = resp.text or ""

    if _sessao_expirada_texto(texto):
        raise RuntimeError(
            f"Sessão expirada no ListAnularSuspensao: {texto[:1000]}"
        )

    try:
        dados = resp.json()
    except Exception:
        raise RuntimeError(
            f"Resposta inválida do ListAnularSuspensao: {resp.text[:1000]}"
        )

    total = dados.get(
        "Total",
        len(dados.get("Data", []) or [])
    )

    _log(
        log,
        f"📋 ListAnularSuspensao retornou {total} registro(s)."
    )

    return dados


def criar_reativacao(
    session: requests.Session,
    observacao: str,
    log: LogFn = None,
    timeout: int = 120,
) -> requests.Response:
    """
    Quinta request da ordem informada:

    POST /Cobranca/SuspensaoCobranca/Anular

    Observação:
    Apesar do nome do endpoint ser Anular, no fluxo de negócio
    ele representa a reativação/anulação da suspensão.
    """
    preparar_headers_reativacao(session)

    headers = {
        "Accept": "*/*",
        "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
        "Origin": BASE_HOST,
        "Referer": URL_ANULAR_PAGE,
        "Host": "servicos.dnit.gov.br",
        "X-Lt-Session-Guid": _guid(session),
        "X-Requested-With": "XMLHttpRequest",
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "same-origin",
    }

    files = {
        "Observacao": (None, observacao),
        "submitOrigin": (None, "undefined"),
    }

    _log(log, "📝 Confirmando reativação no SIOR...")

    resp = session.post(
        URL_ANULAR,
        headers=headers,
        files=files,
        timeout=timeout,
    )

    if resp.status_code not in (200, 201, 204, 302):
        raise RuntimeError(
            f"Falha no POST Anular/Reativar. "
            f"HTTP {resp.status_code}: {resp.text[:1000]}"
        )

    texto = resp.text or ""

    if _sessao_expirada_texto(texto):
        raise RuntimeError(
            f"Sessão expirada no POST Anular/Reativar: {texto[:1000]}"
        )

    if texto.strip():
        try:
            dados = resp.json()

            if isinstance(dados, dict):
                status = str(dados.get("status", "")).lower()

                if status and status != "ok":
                    raise RuntimeError(
                        f"POST Anular/Reativar retornou status inesperado: {dados}"
                    )

        except ValueError:
            pass

    navegar_pos_reativacao(
        session=session,
        resp_create=resp,
        log=log,
    )

    return resp


# ==========================================================
# PIPELINE PRINCIPAL
# ==========================================================
def executar_reativacoes_por_motivo(
    session: requests.Session,
    df_molde: pd.DataFrame,
    log: LogFn = None,
    tamanho_lote: int = LIMITE_AUTOS_POR_REQUISICAO,
    pausa_entre_lotes: float = 1.0,
) -> pd.DataFrame:
    """
    Executa a reativação agrupando por MOTIVO.

    Regra:
    - O endpoint Anular recebe uma única Observacao.
    - Portanto, cada lote deve conter apenas autos com o mesmo MOTIVO.

    Fluxo por lote:
    1. Inicializa tela /Anular via requests.Session.
    2. ListSuspensoesConsulta.
    3. AddAllSuspensoes returnTotal=True.
    4. AddAllSuspensoes returnTotal=False.
    5. ListAnularSuspensao.
    6. POST Anular.
    7. Navegação pós-reativação.
    """
    if df_molde.empty:
        return pd.DataFrame()

    registros_logs: List[Dict[str, Any]] = []
    lote_global = 0

    df = df_molde.copy()

    df["AUTO"] = (
        df["AUTO"]
        .fillna("")
        .astype(str)
        .str.strip()
        .str.upper()
    )

    df["MOTIVO"] = (
        df["MOTIVO"]
        .fillna("")
        .astype(str)
        .str.strip()
    )

    grupos = df.groupby(
        "MOTIVO",
        dropna=False,
        sort=False
    )

    total_grupos = len(grupos)

    _log(
        log,
        f"🧩 {total_grupos} grupo(s) de motivo identificado(s)."
    )

    for idx_motivo, (motivo, df_grupo) in enumerate(grupos, 1):

        autos_grupo = df_grupo["AUTO"].tolist()

        qtd_lotes = math.ceil(
            len(autos_grupo) / tamanho_lote
        )

        _log(
            log,
            f"🔎 Motivo {idx_motivo}/{total_grupos}: "
            f"{len(autos_grupo)} AIT(s), {qtd_lotes} lote(s)."
        )

        for bloco in chunked(
            autos_grupo,
            tamanho_lote
        ):
            lote_global += 1

            _log(
                log,
                f"🚀 Lote {lote_global}: processando {len(bloco)} AIT(s)."
            )

            try:
                # ==================================================
                # 0) ABRE/REINICIALIZA A TELA ANULAR PARA O LOTE
                # ==================================================
                inicializar_tela_reativacao(
                    session=session,
                    log=log,
                    renovar_guid=True,
                )

                time.sleep(0.3)

                # ==================================================
                # 1) CONSULTA AUTOS SUSPENSOS DISPONÍVEIS
                # ==================================================
                resposta_consulta = consultar_suspensoes_para_reativacao(
                    session=session,
                    autos=bloco,
                    log=log,
                )

                dados_consulta = resposta_consulta.get(
                    "Data",
                    []
                ) or []

                mapa_consulta = {
                    str(item.get("NumeroAuto", "")).strip().upper(): item
                    for item in dados_consulta
                    if item.get("NumeroAuto")
                }

                encontrados_consulta = [
                    auto
                    for auto in bloco
                    if auto in mapa_consulta
                ]

                ausentes_consulta = [
                    auto
                    for auto in bloco
                    if auto not in mapa_consulta
                ]

                for auto in ausentes_consulta:
                    msg = (
                        "AIT não retornou em ListSuspensoesConsulta. "
                        "Provavelmente não está suspenso ou não está disponível para reativação."
                    )

                    registros_logs.append(
                        _registro_log_base(
                            auto=auto,
                            motivo=motivo,
                            status="ERRO",
                            mensagem=msg,
                            lote=lote_global,
                        )
                    )

                    _log(
                        log,
                        f"⚠ {auto}: {msg}"
                    )

                if not encontrados_consulta:
                    _log(
                        log,
                        "⚠ Nenhum AIT do lote foi localizado como suspenso. "
                        "AddAllSuspensoes/Anular não serão enviados."
                    )

                    continue

                # ==================================================
                # 2) ADD returnTotal=True
                # ==================================================
                resposta_validacao = add_all_suspensoes(
                    session=session,
                    autos=encontrados_consulta,
                    return_total=True,
                    log=log,
                )

                total_add = resposta_validacao.get(
                    "Total",
                    0
                )

                _log(
                    log,
                    f"✅ AddAllSuspensoes returnTotal=True retornou Total={total_add}."
                )

                if int(total_add or 0) <= 0:
                    msg = (
                        "AddAllSuspensoes returnTotal=True não aceitou nenhum AIT do lote. "
                        "ListAnularSuspensao/Anular não serão executados."
                    )

                    _log(
                        log,
                        f"⚠ {msg}"
                    )

                    for auto in encontrados_consulta:
                        registros_logs.append(
                            _registro_log_base(
                                auto=auto,
                                motivo=motivo,
                                status="ERRO",
                                mensagem=msg,
                                item_sior=mapa_consulta.get(auto),
                                lote=lote_global,
                            )
                        )

                    continue

                # ==================================================
                # 3) ADD returnTotal=False
                # ==================================================
                add_all_suspensoes(
                    session=session,
                    autos=encontrados_consulta,
                    return_total=False,
                    log=log,
                )

                _log(
                    log,
                    "✅ AddAllSuspensoes returnTotal=False executado. "
                    "Autos enviados para a lista temporária de reativação."
                )

                time.sleep(0.5)

                # ==================================================
                # 4) LISTA AUTOS CARREGADOS PARA ANULAR/REATIVAR
                # ==================================================
                resposta_lista = listar_anular_suspensao(
                    session=session,
                    page_size=max(
                        LIMITE_AUTOS_POR_REQUISICAO,
                        len(encontrados_consulta)
                    ),
                    log=log,
                )

                dados_lista = resposta_lista.get(
                    "Data",
                    []
                ) or []

                mapa_lista = {
                    str(item.get("NumeroAuto", "")).strip().upper(): item
                    for item in dados_lista
                    if item.get("NumeroAuto")
                }

                autos_lista = set(
                    mapa_lista.keys()
                )

                autos_bloco = set(
                    encontrados_consulta
                )

                extras = sorted(
                    autos_lista - autos_bloco
                )

                encontrados_lista = [
                    auto
                    for auto in encontrados_consulta
                    if auto in mapa_lista
                ]

                ausentes_lista = [
                    auto
                    for auto in encontrados_consulta
                    if auto not in mapa_lista
                ]

                # ==================================================
                # SEGURANÇA: EVITA REATIVAÇÃO INDEVIDA
                # ==================================================
                if extras:
                    msg = (
                        "A lista temporária do SIOR contém AIT(s) fora do lote atual. "
                        "Operação abortada para evitar reativação indevida: "
                        + ", ".join(extras[:10])
                    )

                    _log(
                        log,
                        f"❌ {msg}"
                    )

                    for auto in encontrados_consulta:
                        registros_logs.append(
                            _registro_log_base(
                                auto=auto,
                                motivo=motivo,
                                status="ERRO",
                                mensagem=msg,
                                item_sior=mapa_consulta.get(auto),
                                lote=lote_global,
                            )
                        )

                    continue

                for auto in ausentes_lista:
                    msg = (
                        "AIT não retornou em ListAnularSuspensao após AddAllSuspensoes."
                    )

                    registros_logs.append(
                        _registro_log_base(
                            auto=auto,
                            motivo=motivo,
                            status="ERRO",
                            mensagem=msg,
                            item_sior=mapa_consulta.get(auto),
                            lote=lote_global,
                        )
                    )

                    _log(
                        log,
                        f"⚠ {auto}: {msg}"
                    )

                if not encontrados_lista:
                    _log(
                        log,
                        "⚠ Nenhum AIT do lote foi confirmado na lista de reativação. "
                        "POST Anular não será enviado."
                    )

                    continue

                # ==================================================
                # 5) POST ANULAR - EFETIVA REATIVAÇÃO
                # ==================================================
                criar_reativacao(
                    session=session,
                    observacao=motivo,
                    log=log,
                )

                for auto in encontrados_lista:
                    registros_logs.append(
                        _registro_log_base(
                            auto=auto,
                            motivo=motivo,
                            status="SUCESSO",
                            mensagem="Reativação registrada com sucesso no SIOR.",
                            item_sior=mapa_lista.get(auto) or mapa_consulta.get(auto),
                            lote=lote_global,
                        )
                    )

                _log(
                    log,
                    f"✅ Lote {lote_global} finalizado com {len(encontrados_lista)} sucesso(s)."
                )

            except Exception as ex:
                msg = str(ex)

                _log(
                    log,
                    f"❌ Erro no lote {lote_global}: {msg}"
                )

                for auto in bloco:
                    registros_logs.append(
                        _registro_log_base(
                            auto=auto,
                            motivo=motivo,
                            status="ERRO",
                            mensagem=msg,
                            lote=lote_global,
                        )
                    )

            time.sleep(
                pausa_entre_lotes
            )

    return pd.DataFrame(
        registros_logs
    )