# ==========================================================
# REQUISIÇÕES SIOR - SUSPENSÃO DE COBRANÇA
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

URL_CREATE_PAGE = f"{BASE_SIOR}/Cobranca/SuspensaoCobranca/Create"
URL_ADD_ALL = f"{BASE_SIOR}/Cobranca/SuspensaoCobranca/AddAllInfracoes"
URL_LIST = f"{BASE_SIOR}/Cobranca/SuspensaoCobranca/ListInfracoes"
URL_CREATE = f"{BASE_SIOR}/Cobranca/SuspensaoCobranca/Create"
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
    """
    Mantém um X-Lt-Session-Guid fixo por tela/lote.

    Regra:
    - Dentro do mesmo lote, o GUID permanece o mesmo.
    - Entre lotes, a função renovar_lt_guid() cria outro GUID.
    """
    guid = getattr(session, "_sior_lt_guid", None)

    if not guid:
        guid = str(uuid.uuid4())
        setattr(session, "_sior_lt_guid", guid)

    return guid


def renovar_lt_guid(session: requests.Session) -> str:
    """
    Gera um novo X-Lt-Session-Guid.

    Usado no início de cada lote para simular nova abertura da tela
    de Suspensão de Cobrança.
    """
    guid = str(uuid.uuid4())
    setattr(session, "_sior_lt_guid", guid)
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
    """
    Converte URL relativa retornada pelo SIOR em URL absoluta.

    Exemplo:
    /sior/Cobranca/SuspensaoCobranca?Bind=True
    """
    if not url:
        return URL_INDEX_BIND

    return urljoin(BASE_HOST, url)


def preparar_headers_suspensao(session: requests.Session) -> None:
    """
    Prepara headers mínimos para operar na tela de Suspensão.

    A Session recebida deve vir do fluxo iniciar_sessao_sior(),
    ou seja, com cookies já obtidos/sincronizados pelo login SIOR.
    """
    session.headers.update(
        {
            "Accept": "*/*",
            "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
            "Origin": BASE_HOST,
            "Referer": URL_CREATE_PAGE,
            "Host": "servicos.dnit.gov.br",
            "X-Lt-Session-Guid": _guid(session),
            "X-Requested-With": "XMLHttpRequest",
        }
    )


def _headers_ajax_json(session: requests.Session) -> Dict[str, str]:
    preparar_headers_suspensao(session)

    return {
        "Accept": "*/*",
        "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
        "Content-Type": "application/json; charset=UTF-8",
        "Origin": BASE_HOST,
        "Referer": URL_CREATE_PAGE,
        "Host": "servicos.dnit.gov.br",
        "X-Lt-Session-Guid": _guid(session),
        "X-Requested-With": "XMLHttpRequest",
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "same-origin",
    }


def _headers_ajax_get(session: requests.Session) -> Dict[str, str]:
    preparar_headers_suspensao(session)

    return {
        "Accept": "*/*",
        "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
        "Referer": URL_CREATE_PAGE,
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
def inicializar_tela_suspensao(
    session: requests.Session,
    log: LogFn = None,
    timeout: int = 60,
    renovar_guid: bool = False,
) -> None:
    """
    Inicializa a tela de Suspensão de Cobrança via requests.Session.

    Importante:
    - O SIOR usa uma lista temporária por sessão/tela.
    - Antes de cada lote, abrimos novamente a tela Create.
    - Isso evita erro de TempData/ListInfracoes entre lotes.
    """
    if renovar_guid:
        renovar_lt_guid(session)

    preparar_headers_suspensao(session)

    _log(log, "🌐 Inicializando tela de Suspensão via requests.Session...")

    # 1) Simula chegada na listagem após eventual Create anterior.
    resp_bind = session.get(
        URL_INDEX_BIND,
        headers=_headers_html(referer=f"{BASE_SIOR}/"),
        timeout=timeout,
        allow_redirects=True,
    )

    if resp_bind.status_code not in (200, 201, 204):
        raise RuntimeError(
            f"Falha ao acessar tela Bind da suspensão. "
            f"HTTP {resp_bind.status_code}: {resp_bind.text[:500]}"
        )

    if _sessao_expirada_texto(resp_bind.text or ""):
        raise RuntimeError(
            "Sessão expirada ao acessar tela Bind da suspensão via requests.Session."
        )

    time.sleep(0.2)

    # 2) Abre a tela Create, onde os endpoints AJAX passam a operar.
    resp_create = session.get(
        URL_CREATE_PAGE,
        headers=_headers_html(referer=URL_INDEX_BIND),
        timeout=timeout,
        allow_redirects=True,
    )

    if resp_create.status_code != 200:
        raise RuntimeError(
            f"Falha ao inicializar tela Create de suspensão via Session. "
            f"HTTP {resp_create.status_code}: {resp_create.text[:500]}"
        )

    if _sessao_expirada_texto(resp_create.text or ""):
        raise RuntimeError(
            "A tela Create retornou login/sessão expirada via requests.Session. "
            "Os cookies do navegador não foram sincronizados corretamente para a Session."
        )

    preparar_headers_suspensao(session)

    _log(log, "✅ Tela Create inicializada via requests.Session.")


def navegar_pos_create_suspensao(
    session: requests.Session,
    resp_create: requests.Response,
    log: LogFn = None,
    timeout: int = 60,
) -> None:
    """
    Após o Create, o SIOR retorna uma action notify-after-navigate com URL.

    No navegador, após cadastrar, a página navega para:
    /sior/Cobranca/SuspensaoCobranca?Bind=True

    Como estamos em requests, simulamos essa navegação para encerrar
    corretamente o ciclo do lote.
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

    _log(log, f"➡️ Navegando pós-Create: {url_navegacao}")

    resp = session.get(
        url_navegacao,
        headers=_headers_html(referer=URL_CREATE_PAGE),
        timeout=timeout,
        allow_redirects=True,
    )

    if resp.status_code not in (200, 201, 204):
        raise RuntimeError(
            f"Falha ao navegar pós-Create. "
            f"HTTP {resp.status_code}: {resp.text[:500]}"
        )

    if _sessao_expirada_texto(resp.text or ""):
        raise RuntimeError("Sessão expirada ao navegar pós-Create.")

    _log(log, "✅ Navegação pós-Create concluída.")


# ==========================================================
# UTILITÁRIOS
# ==========================================================
def chunked(
    lista: List[str],
    tamanho: int = LIMITE_AUTOS_POR_REQUISICAO,
) -> Iterable[List[str]]:
    """
    Quebra a lista de autos em blocos.

    Regra SIOR:
    - Processar no máximo 100 autos por requisição.
    """
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
# REQUESTS SIOR
# ==========================================================
def add_all_infracoes(
    session: requests.Session,
    autos: List[str],
    return_total: bool,
    log: LogFn = None,
    timeout: int = 60,
) -> Dict[str, Any]:
    """
    Executa o endpoint AddAllInfracoes.

    Fluxo correto observado no SIOR:

    1) returnTotal=True
       - Valida/conta os autos.
       - Retorna JSON: {"Total": X}

    2) returnTotal=False
       - Carrega efetivamente os autos na lista temporária.
       - Normalmente retorna corpo vazio.
    """
    preparar_headers_suspensao(session)

    payload = {
        "NumeroAuto": "\r\n".join(autos),
        "returnTotal": return_total,
    }

    etapa = "validando/contando" if return_total else "carregando lista temporária"

    _log(
        log,
        f"📥 AddAllInfracoes ({etapa}) | {len(autos)} AIT(s)."
    )

    resp = session.post(
        URL_ADD_ALL,
        headers=_headers_ajax_json(session),
        data=json.dumps(payload, ensure_ascii=False),
        timeout=timeout,
    )

    if resp.status_code not in (200, 201, 204):
        raise RuntimeError(
            f"Falha no AddAllInfracoes returnTotal={return_total}. "
            f"HTTP {resp.status_code}: {resp.text[:1000]}"
        )

    texto = (resp.text or "").strip()

    # No returnTotal=False, o SIOR pode retornar corpo vazio.
    if not texto:
        return {
            "Total": None,
            "Raw": "",
            "returnTotal": return_total,
            "status_code": resp.status_code,
        }

    if _sessao_expirada_texto(texto):
        raise RuntimeError(
            f"Sessão expirada no AddAllInfracoes returnTotal={return_total}: {texto[:1000]}"
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


def listar_infracoes_suspensao(
    session: requests.Session,
    page_size: int = LIMITE_AUTOS_POR_REQUISICAO,
    log: LogFn = None,
    timeout: int = 60,
) -> Dict[str, Any]:
    """
    Lista os AITs atualmente carregados na tela de suspensão.
    """
    preparar_headers_suspensao(session)

    params = {
        "sort": "",
        "page": 1,
        "pageSize": max(10, int(page_size)),
        "group": "",
        "filter": "",
        "_": int(time.time() * 1000),
    }

    resp = session.get(
        URL_LIST,
        params=params,
        headers=_headers_ajax_get(session),
        timeout=timeout,
    )

    if resp.status_code not in (200, 201):
        raise RuntimeError(
            f"Falha no ListInfracoes. HTTP {resp.status_code}: {resp.text[:1000]}"
        )

    texto = resp.text or ""

    if _sessao_expirada_texto(texto):
        raise RuntimeError(
            f"Sessão expirada no ListInfracoes: {texto[:1000]}"
        )

    try:
        data = resp.json()
    except Exception:
        raise RuntimeError(
            f"Resposta inválida do ListInfracoes: {resp.text[:1000]}"
        )

    total = data.get(
        "Total",
        len(data.get("Data", []) or [])
    )

    _log(
        log,
        f"📋 ListInfracoes retornou {total} registro(s)."
    )

    return data


def criar_suspensao(
    session: requests.Session,
    observacao: str,
    log: LogFn = None,
    timeout: int = 120,
) -> requests.Response:
    """
    Confirma a suspensão para os AITs carregados na lista temporária.

    O envio é multipart/form-data, equivalente ao navegador.
    Após o POST, simula a navegação retornada pelo SIOR.
    """
    preparar_headers_suspensao(session)

    headers = {
        "Accept": "*/*",
        "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
        "Origin": BASE_HOST,
        "Referer": URL_CREATE_PAGE,
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

    _log(log, "📝 Confirmando suspensão no SIOR...")

    resp = session.post(
        URL_CREATE,
        headers=headers,
        files=files,
        timeout=timeout,
    )

    if resp.status_code not in (200, 201, 204, 302):
        raise RuntimeError(
            f"Falha no Create suspensão. HTTP {resp.status_code}: {resp.text[:1000]}"
        )

    texto = resp.text or ""

    if _sessao_expirada_texto(texto):
        raise RuntimeError(
            f"Sessão expirada no Create suspensão: {texto[:1000]}"
        )

    if texto.strip():
        try:
            dados = resp.json()

            if isinstance(dados, dict):
                status = str(dados.get("status", "")).lower()

                if status and status != "ok":
                    raise RuntimeError(
                        f"Create retornou status inesperado: {dados}"
                    )

        except ValueError:
            # Em alguns cenários o SIOR pode retornar HTML/corpo não JSON.
            pass

    navegar_pos_create_suspensao(
        session=session,
        resp_create=resp,
        log=log,
    )

    return resp


# ==========================================================
# PIPELINE PRINCIPAL
# ==========================================================
def executar_suspensoes_por_motivo(
    session: requests.Session,
    df_molde: pd.DataFrame,
    log: LogFn = None,
    tamanho_lote: int = LIMITE_AUTOS_POR_REQUISICAO,
    pausa_entre_lotes: float = 1.0,
) -> pd.DataFrame:
    """
    Executa a suspensão agrupando por MOTIVO.

    Regra essencial:
    - O endpoint Create recebe uma única Observacao.
    - Portanto, cada lote deve conter apenas autos com o mesmo MOTIVO.

    Fluxo por lote:
    1. Inicializa tela Create via requests.Session.
    2. AddAllInfracoes returnTotal=True.
    3. AddAllInfracoes returnTotal=False.
    4. ListInfracoes.
    5. Create.
    6. Navegação pós-Create.
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
                # 0) ABRE/REINICIALIZA A TELA CREATE PARA O LOTE
                # ==================================================
                inicializar_tela_suspensao(
                    session=session,
                    log=log,
                    renovar_guid=True,
                )

                time.sleep(0.3)

                # ==================================================
                # 1) PRIMEIRO ADD - returnTotal=True
                # Apenas valida/conta os autos.
                # Response esperada: {"Total": X}
                # ==================================================
                resposta_validacao = add_all_infracoes(
                    session=session,
                    autos=bloco,
                    return_total=True,
                    log=log,
                )

                total_add = resposta_validacao.get(
                    "Total",
                    0
                )

                _log(
                    log,
                    f"✅ AddAllInfracoes returnTotal=True retornou Total={total_add}."
                )

                if int(total_add or 0) <= 0:
                    msg = (
                        "AddAllInfracoes returnTotal=True não aceitou nenhum AIT do lote. "
                        "ListInfracoes/Create não serão executados."
                    )

                    _log(
                        log,
                        f"⚠ {msg}"
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

                    continue

                # ==================================================
                # 2) SEGUNDO ADD - returnTotal=False
                # Este passo carrega autos na lista temporária.
                # Response esperada: corpo vazio.
                # ==================================================
                add_all_infracoes(
                    session=session,
                    autos=bloco,
                    return_total=False,
                    log=log,
                )

                _log(
                    log,
                    "✅ AddAllInfracoes returnTotal=False executado. "
                    "Autos enviados para a lista temporária."
                )

                time.sleep(0.5)

                # ==================================================
                # 3) LISTA OS AUTOS CARREGADOS
                # ==================================================
                resposta_lista = listar_infracoes_suspensao(
                    session=session,
                    page_size=max(
                        LIMITE_AUTOS_POR_REQUISICAO,
                        len(bloco)
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
                    bloco
                )

                extras = sorted(
                    autos_lista - autos_bloco
                )

                encontrados = [
                    auto
                    for auto in bloco
                    if auto in mapa_lista
                ]

                ausentes = [
                    auto
                    for auto in bloco
                    if auto not in mapa_lista
                ]

                # ==================================================
                # SEGURANÇA: EVITA SUSPENSÃO INDEVIDA
                # ==================================================
                if extras:
                    msg = (
                        "A lista temporária do SIOR contém AIT(s) fora do lote atual. "
                        "Operação abortada para evitar suspensão indevida: "
                        + ", ".join(extras[:10])
                    )

                    _log(
                        log,
                        f"❌ {msg}"
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

                    continue

                for auto in ausentes:
                    msg = (
                        "AIT não retornou em ListInfracoes após AddAllInfracoes."
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

                if not encontrados:
                    _log(
                        log,
                        "⚠ Nenhum AIT do lote foi confirmado na lista. Create não será enviado."
                    )

                    continue

                # ==================================================
                # 4) CREATE - EFETIVA SUSPENSÃO
                # ==================================================
                criar_suspensao(
                    session=session,
                    observacao=motivo,
                    log=log,
                )

                for auto in encontrados:
                    registros_logs.append(
                        _registro_log_base(
                            auto=auto,
                            motivo=motivo,
                            status="SUCESSO",
                            mensagem="Suspensão registrada com sucesso no SIOR.",
                            item_sior=mapa_lista.get(auto),
                            lote=lote_global,
                        )
                    )

                _log(
                    log,
                    f"✅ Lote {lote_global} finalizado com {len(encontrados)} sucesso(s)."
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