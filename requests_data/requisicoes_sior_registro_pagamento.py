# ==========================================================
# REQUISIÇÕES SIOR - REGISTRO DE PAGAMENTO
# ==========================================================
import json
import re
import time
from datetime import datetime
from typing import Callable, Dict, Any, List, Optional

import pandas as pd
import requests


# ==========================================================
# CONSTANTES
# ==========================================================
BASE_HOST = "https://servicos.dnit.gov.br"
BASE_SIOR = f"{BASE_HOST}/sior"

URL_CONSULTA_AUTO_LIST = (
    f"{BASE_SIOR}/Infracao/ConsultaAutoInfracao/List"
)

URL_CONSULTA_AUTO_PAGE = (
    f"{BASE_SIOR}/Infracao/ConsultaAutoInfracao/"
    "?SituacoesInfracaoSelecionadas=0"
)

URL_REGISTRO_PAGAMENTO_INDEX = (
    f"{BASE_SIOR}/Cobranca/CCOBEPagamento?Bind=True"
)

URL_REGISTRO_PAGAMENTO_CREATE = (
    f"{BASE_SIOR}/Cobranca/CCOBEPagamento/Create"
)

URL_OBTER_INFRACAO = (
    f"{BASE_SIOR}/Cobranca/CCOBEPagamento/ObterInfracao"
)

# Usado também pela aba Flet no safe_get()
URL_REGISTRO_PAGAMENTO_PAGE = URL_REGISTRO_PAGAMENTO_INDEX

LIMITE_REGISTROS_POR_EXECUCAO = 2000

LogFn = Optional[Callable[[str], None]]


COLUNAS_LOG = [
    "DataHora",
    "Linha",
    "NumeroAuto",
    "DataPagamento",
    "NumeroDocArrecadacao",
    "Observacao",
    "Status",
    "Mensagem",
    "IdCobranca",
    "CobrancaCodigoProcesso",
    "RowVersionConverted",
    "NumeroAutoSIOR",
]


# ==========================================================
# LOG
# ==========================================================
def _log(log: LogFn, mensagem: str) -> None:
    if log:
        log(mensagem)


# ==========================================================
# HELPERS DE SESSÃO / HEADERS
# ==========================================================
def _sessao_expirada_texto(texto: str) -> bool:
    texto = texto or ""

    return (
        "A sua sessão expirou" in texto
        or "Account/Login" in texto
        or "/Account/Login" in texto
        or "Entrar com gov.br" in texto
    )


def preparar_headers_registro_pagamento(
    session: requests.Session,
) -> None:
    """
    Headers globais mínimos para a sessão requests autenticada.

    A sessão deve vir do fluxo padrão:
    navegador, session = iniciar_sessao_sior(...)
    seguido de sincronizar_cookies_navegador_para_session(...)
    """

    session.headers.update(
        {
            "Accept": "*/*",
            "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
            "Origin": BASE_HOST,
            "Referer": URL_REGISTRO_PAGAMENTO_INDEX,
            "Host": "servicos.dnit.gov.br",
            "X-Requested-With": "XMLHttpRequest",
        }
    )


def _headers_html(
    referer: str | None = None,
) -> Dict[str, str]:
    return {
        "Accept": (
            "text/html,application/xhtml+xml,"
            "application/xml;q=0.9,*/*;q=0.8"
        ),
        "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
        "Referer": referer or f"{BASE_SIOR}/",
        "Host": "servicos.dnit.gov.br",
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
    }


def _headers_ajax(
    referer: str,
    content_type: str | None = None,
) -> Dict[str, str]:

    headers = {
        "Accept": "*/*",
        "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
        "Origin": BASE_HOST,
        "Referer": referer,
        "Host": "servicos.dnit.gov.br",
        "X-Requested-With": "XMLHttpRequest",
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "same-origin",
    }

    if content_type:
        headers["Content-Type"] = content_type

    return headers


def inicializar_tela_registro_pagamento(
    session: requests.Session,
    log: LogFn = None,
    timeout: int = 60,
) -> None:
    """
    Inicializa/valida a tela real usada pelo SIOR para Registro de Pagamento.

    A rota funcional antiga é:
    /sior/Cobranca/CCOBEPagamento?Bind=True

    Não usa rota inventada de /RegistroPagamento/Create.
    """

    preparar_headers_registro_pagamento(
        session
    )

    _log(
        log,
        "🌐 Inicializando tela de Registro de Pagamento no SIOR..."
    )

    resp = session.get(
        URL_REGISTRO_PAGAMENTO_INDEX,
        headers=_headers_html(
            referer=f"{BASE_SIOR}/"
        ),
        timeout=timeout,
        allow_redirects=True,
    )

    if resp.status_code not in (200, 201, 204):
        raise RuntimeError(
            "Falha ao inicializar tela de Registro de Pagamento. "
            f"HTTP {resp.status_code}: {resp.text[:500]}"
        )

    if _sessao_expirada_texto(
        resp.text or ""
    ):
        raise RuntimeError(
            "Sessão expirada ao inicializar Registro de Pagamento. "
            "Os cookies do navegador não foram sincronizados corretamente para a Session."
        )

    preparar_headers_registro_pagamento(
        session
    )

    _log(
        log,
        "✅ Tela de Registro de Pagamento inicializada com sucesso."
    )


# ==========================================================
# REQUESTS DIRETAS DO REGISTRO DE PAGAMENTO
# ==========================================================
def get_cod_infra(
    auto: str,
    session: requests.Session,
    log: LogFn = None,
    timeout: int = 60,
):
    """
    Busca o Código da Infração pelo Número do Auto.

    Mantém a mesma lógica do código antigo funcional.
    """

    preparar_headers_registro_pagamento(
        session
    )

    params = {
        "sort": "",
        "page": 1,
        "pageSize": 10,
        "group": "",
        "filter": "",
        "numeroauto": auto,
        "bind": "true",
        "calledfromapi": "true",
        "calledFromApi": "true",
    }

    headers = _headers_ajax(
        referer=(
            f"{BASE_SIOR}/Infracao/ConsultaAutoInfracao"
            f"?NumeroAuto={auto}&Bind=true&Page=1&PageSize=10"
        )
    )

    try:
        resp = session.get(
            URL_CONSULTA_AUTO_LIST,
            params=params,
            headers=headers,
            timeout=timeout,
        )

        if resp.status_code != 200:
            _log(
                log,
                f"❌ Erro HTTP {resp.status_code} ao buscar CódigoInfração de {auto}."
            )
            return None

        texto = resp.text or ""

        if _sessao_expirada_texto(
            texto
        ):
            raise RuntimeError(
                f"Sessão expirada ao consultar CódigoInfração do auto {auto}."
            )

        data = resp.json()

        if isinstance(data, dict) and "Data" in data:
            infracoes = data.get(
                "Data",
                []
            )

            if infracoes and isinstance(
                infracoes,
                list
            ):
                return infracoes[0].get(
                    "CodigoInfracao",
                    None
                )

        return None

    except requests.exceptions.RequestException as ex:
        _log(
            log,
            f"❌ Erro na requisição get_cod_infra para {auto}: {ex}"
        )
        return None


def get_dados_infracao(
    session: requests.Session,
    id_cobranca,
    log: LogFn = None,
    timeout: int = 60,
):
    """
    Consulta os dados da infração a partir do idCobranca/CodigoInfracao.

    Retorno esperado:
    {
        "CobrancaCodigoProcesso": ...,
        "RowVersionConverted": ...,
        "NumeroAuto": ...,
        ...
    }
    """

    preparar_headers_registro_pagamento(
        session
    )

    params = {
        "idCobranca": id_cobranca
    }

    headers = _headers_ajax(
        referer=URL_REGISTRO_PAGAMENTO_CREATE
    )

    try:
        resp = session.get(
            URL_OBTER_INFRACAO,
            headers=headers,
            params=params,
            timeout=timeout,
        )

        if resp.status_code != 200:
            _log(
                log,
                f"❌ HTTP {resp.status_code} ao buscar dados da infração {id_cobranca}."
            )
            return None

        texto = resp.text or ""

        if _sessao_expirada_texto(
            texto
        ):
            raise RuntimeError(
                "Sessão expirada ao buscar dados da infração para Registro de Pagamento."
            )

        return resp.json()

    except requests.exceptions.RequestException as ex:
        _log(
            log,
            f"❌ Erro ao buscar dados da infração {id_cobranca}: {ex}"
        )
        return None


def post_registro_pagamento(
    session: requests.Session,
    codigo_processo_infracao,
    row_version,
    data_pagamento: str,
    numero_doc_arrecadacao: str,
    observacao: str,
    numero_auto: str,
    log: LogFn = None,
    timeout: int = 60,
) -> Dict[str, Any]:
    """
    Envia o POST para registrar pagamento no SIOR.

    Mantém payload e endpoint do código antigo funcional.
    """

    preparar_headers_registro_pagamento(
        session
    )

    headers = _headers_ajax(
        referer=URL_REGISTRO_PAGAMENTO_CREATE,
        content_type="application/x-www-form-urlencoded; charset=UTF-8",
    )

    payload = {
        "CodigoProcessoInfracao": str(
            codigo_processo_infracao
        ),
        "RowVersionConverted": str(
            row_version
        ),
        "DataPagamento": str(
            data_pagamento
        ),
        "NumeroDocumentoArrecadacao": str(
            numero_doc_arrecadacao
        ),
        "Observacao": str(
            observacao or ""
        ),
        "NumeroAuto": str(
            numero_auto
        ),
        "submitOrigin": "undefined",
    }

    try:
        resp = session.post(
            URL_REGISTRO_PAGAMENTO_CREATE,
            headers=headers,
            data=payload,
            timeout=timeout,
        )

        if resp.status_code not in (200, 201, 204):
            return {
                "success": False,
                "message": (
                    f"HTTP {resp.status_code}: "
                    f"{resp.text[:500]}"
                ),
                "url": None,
            }

        texto = resp.text or ""

        if _sessao_expirada_texto(
            texto
        ):
            raise RuntimeError(
                "Sessão expirada ao enviar Registro de Pagamento."
            )

        try:
            result = resp.json()
        except json.JSONDecodeError:
            return {
                "success": False,
                "message": f"Resposta inesperada: {resp.text[:500]}",
                "url": None,
            }

        if result.get("status") == "ok":
            action = (
                result.get("actions", [{}]) or [{}]
            )[0]

            options = action.get(
                "options",
                {}
            )

            return {
                "success": True,
                "message": options.get(
                    "message",
                    "Registro de pagamento realizado com sucesso."
                ),
                "url": options.get(
                    "url"
                ),
            }

        return {
            "success": False,
            "message": result.get(
                "message",
                "Erro desconhecido ao registrar pagamento."
            ),
            "url": None,
        }

    except requests.exceptions.RequestException as ex:
        return {
            "success": False,
            "message": f"❌ Erro de requisição: {ex}",
            "url": None,
        }


# ==========================================================
# NORMALIZAÇÃO
# ==========================================================
def normalizar_data_pagamento(valor) -> str:
    """
    Converte o valor da planilha para dd/mm/aaaa sem warning do pandas.
    """

    if pd.isna(valor) or str(valor).strip() == "":
        return ""

    if hasattr(valor, "strftime"):
        try:
            return valor.strftime("%d/%m/%Y")
        except Exception:
            pass

    texto = str(valor).strip()

    if re.match(r"^\d{4}-\d{2}-\d{2}", texto):
        try:
            data = pd.to_datetime(
                texto,
                format="%Y-%m-%d %H:%M:%S",
                errors="coerce",
            )

            if pd.isna(data):
                data = pd.to_datetime(
                    texto[:10],
                    format="%Y-%m-%d",
                    errors="raise",
                )

            return data.strftime(
                "%d/%m/%Y"
            )

        except Exception:
            pass

    try:
        data = pd.to_datetime(
            texto,
            format="%d/%m/%Y",
            errors="raise",
        )

        return data.strftime(
            "%d/%m/%Y"
        )

    except Exception:
        return texto


def normalizar_doc_arrecadacao(valor) -> str:
    if pd.isna(valor):
        return ""

    texto = str(
        valor
    ).strip()

    if texto.endswith(".0"):
        texto = texto[:-2]

    texto = "".join(
        c for c in texto
        if c.isdigit()
    )

    return texto


def normalizar_observacao(valor) -> str:
    if pd.isna(valor):
        return ""

    return str(
        valor
    ).strip()


def normalizar_auto(valor) -> str:
    if pd.isna(valor):
        return ""

    return str(
        valor
    ).strip().upper()


def _registro_log_base(
    linha: int,
    numero_auto: str,
    data_pagamento: str,
    numero_doc_arrecadacao: str,
    observacao: str,
    status: str,
    mensagem: str,
    id_cobranca=None,
    dados_infracao: Dict[str, Any] = None,
) -> Dict[str, Any]:

    dados_infracao = dados_infracao or {}

    return {
        "DataHora": datetime.now().strftime(
            "%d/%m/%Y %H:%M:%S"
        ),
        "Linha": linha,
        "NumeroAuto": numero_auto,
        "DataPagamento": data_pagamento,
        "NumeroDocArrecadacao": numero_doc_arrecadacao,
        "Observacao": observacao,
        "Status": status,
        "Mensagem": mensagem,
        "IdCobranca": id_cobranca or "",
        "CobrancaCodigoProcesso": dados_infracao.get(
            "CobrancaCodigoProcesso",
            ""
        ),
        "RowVersionConverted": dados_infracao.get(
            "RowVersionConverted",
            ""
        ),
        "NumeroAutoSIOR": dados_infracao.get(
            "NumeroAuto",
            ""
        ),
    }


# ==========================================================
# PIPELINE PRINCIPAL
# ==========================================================
def executar_registros_pagamento(
    session: requests.Session,
    df_molde: pd.DataFrame,
    log: LogFn = None,
    pausa_entre_registros: float = 0.5,
) -> pd.DataFrame:
    """
    Executa registro de pagamento auto a auto.

    Fluxo:
    1. Busca CodigoInfracao pelo NumeroAuto.
    2. Busca dados da infração em CCOBEPagamento/ObterInfracao.
    3. Extrai CobrancaCodigoProcesso e RowVersionConverted.
    4. Envia POST para CCOBEPagamento/Create.
    5. Retorna DataFrame de logs.
    """

    if df_molde.empty:
        return pd.DataFrame(
            columns=COLUNAS_LOG
        )

    preparar_headers_registro_pagamento(
        session
    )

    registros_logs: List[Dict[str, Any]] = []

    total = len(
        df_molde
    )

    _log(
        log,
        f"🚀 Iniciando registro de pagamento de {total} AIT(s)."
    )

    for idx, row in df_molde.reset_index(drop=True).iterrows():
        linha_planilha = idx + 2

        numero_auto = normalizar_auto(
            row.get("NumeroAuto", "")
        )

        data_pagamento = normalizar_data_pagamento(
            row.get("DataPagamento", "")
        )

        numero_doc_arrecadacao = normalizar_doc_arrecadacao(
            row.get("NumeroDocArrecadacao", "")
        )

        observacao = normalizar_observacao(
            row.get("Observacao", "")
        )

        _log(
            log,
            f"🔎 [{idx + 1}/{total}] Processando {numero_auto}..."
        )

        id_cobranca = None
        dados_infracao = {}

        try:
            # ==================================================
            # 1. BUSCA CODIGO INFRAÇÃO / ID COBRANÇA
            # ==================================================
            id_cobranca = get_cod_infra(
                numero_auto,
                session,
                log=log,
            )

            if not id_cobranca:
                msg = (
                    f"Não encontrado id_cobranca/CodigoInfracao para o auto {numero_auto}."
                )

                _log(
                    log,
                    f"⚠ {numero_auto}: {msg}"
                )

                registros_logs.append(
                    _registro_log_base(
                        linha=linha_planilha,
                        numero_auto=numero_auto,
                        data_pagamento=data_pagamento,
                        numero_doc_arrecadacao=numero_doc_arrecadacao,
                        observacao=observacao,
                        status="ERRO",
                        mensagem=msg,
                    )
                )

                continue

            _log(
                log,
                f"✅ {numero_auto}: id_cobranca/CodigoInfracao localizado: {id_cobranca}."
            )

            # ==================================================
            # 2. BUSCA DADOS DA INFRAÇÃO
            # ==================================================
            dados_infracao = get_dados_infracao(
                session,
                id_cobranca,
                log=log,
            )

            if not dados_infracao:
                msg = (
                    f"Não foi possível obter dados da infração {numero_auto}."
                )

                _log(
                    log,
                    f"⚠ {numero_auto}: {msg}"
                )

                registros_logs.append(
                    _registro_log_base(
                        linha=linha_planilha,
                        numero_auto=numero_auto,
                        data_pagamento=data_pagamento,
                        numero_doc_arrecadacao=numero_doc_arrecadacao,
                        observacao=observacao,
                        status="ERRO",
                        mensagem=msg,
                        id_cobranca=id_cobranca,
                    )
                )

                continue

            codigo_proc = dados_infracao.get(
                "CobrancaCodigoProcesso"
            )

            row_version = dados_infracao.get(
                "RowVersionConverted"
            )

            numero_auto_sior = dados_infracao.get(
                "NumeroAuto",
                numero_auto
            )

            if (
                codigo_proc is None
                or codigo_proc == ""
                or row_version is None
                or row_version == ""
            ):
                msg = (
                    "Dados da infração incompletos. "
                    "CobrancaCodigoProcesso ou RowVersionConverted não retornaram."
                )

                _log(
                    log,
                    f"⚠ {numero_auto}: {msg}"
                )

                registros_logs.append(
                    _registro_log_base(
                        linha=linha_planilha,
                        numero_auto=numero_auto,
                        data_pagamento=data_pagamento,
                        numero_doc_arrecadacao=numero_doc_arrecadacao,
                        observacao=observacao,
                        status="ERRO",
                        mensagem=msg,
                        id_cobranca=id_cobranca,
                        dados_infracao=dados_infracao,
                    )
                )

                continue

            # ==================================================
            # 3. POST REGISTRO PAGAMENTO
            # ==================================================
            resultado = post_registro_pagamento(
                session=session,
                codigo_processo_infracao=codigo_proc,
                row_version=row_version,
                data_pagamento=data_pagamento,
                numero_doc_arrecadacao=numero_doc_arrecadacao,
                observacao=observacao,
                numero_auto=numero_auto_sior,
                log=log,
            )

            success = bool(
                resultado.get("success")
            )

            mensagem = str(
                resultado.get("message", "")
            ).strip()

            if not mensagem:
                mensagem = (
                    "Registro de pagamento realizado com sucesso."
                    if success
                    else "Falha ao registrar pagamento."
                )

            if success:
                _log(
                    log,
                    f"✅ {numero_auto}: {mensagem}"
                )

                status = "SUCESSO"

            else:
                _log(
                    log,
                    f"❌ {numero_auto}: {mensagem}"
                )

                status = "ERRO"

            registros_logs.append(
                _registro_log_base(
                    linha=linha_planilha,
                    numero_auto=numero_auto,
                    data_pagamento=data_pagamento,
                    numero_doc_arrecadacao=numero_doc_arrecadacao,
                    observacao=observacao,
                    status=status,
                    mensagem=mensagem,
                    id_cobranca=id_cobranca,
                    dados_infracao=dados_infracao,
                )
            )

        except Exception as ex:
            msg = str(
                ex
            )

            _log(
                log,
                f"❌ {numero_auto}: {msg}"
            )

            registros_logs.append(
                _registro_log_base(
                    linha=linha_planilha,
                    numero_auto=numero_auto,
                    data_pagamento=data_pagamento,
                    numero_doc_arrecadacao=numero_doc_arrecadacao,
                    observacao=observacao,
                    status="ERRO",
                    mensagem=msg,
                    id_cobranca=id_cobranca,
                    dados_infracao=dados_infracao,
                )
            )

        time.sleep(
            pausa_entre_registros
        )

    return pd.DataFrame(
        registros_logs,
        columns=COLUNAS_LOG,
    )