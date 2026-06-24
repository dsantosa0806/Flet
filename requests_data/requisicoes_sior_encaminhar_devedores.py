# ==========================================================
# REQUISIÇÕES SIOR - ENCAMINHAR DEVEDORES
# ==========================================================
import time
import uuid
import unicodedata
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional
from urllib.parse import quote, urlencode

import pandas as pd
import requests


# ==========================================================
# URLS / CONSTANTES
# ==========================================================
BASE_HOST = "https://servicos.dnit.gov.br"
BASE_SIOR = f"{BASE_HOST}/sior"

URL_TELA_ENCAMINHAMENTO = f"{BASE_SIOR}/Cobranca/CCOBEEncaminhamento"
URL_LIST_DETALHE_AUTO = f"{BASE_SIOR}/Cobranca/CCOBEEncaminhamento/ListDetalheAutoInfracao"
URL_ENCAMINHAR_SELECIONADOS = f"{BASE_SIOR}/Cobranca/CCOBEEncaminhamento/EncaminharSelecionados"

# ==========================================================
# CORRELAÇÃO OFICIAL DA PLANILHA / SIOR
# ==========================================================
# Regra informada:
# Equipe Cobrança 1 -> código 2
# Equipe Cobrança 2 -> código 1
# Equipe Cobrança 3 -> código 3
# Equipe Cobrança 4 -> código 4
# Equipe Cobrança 5 -> código 5
EQUIPE_COD_NOME = {
    "2": "Equipe Cobrança 1",
    "1": "Equipe Cobrança 2",
    "3": "Equipe Cobrança 3",
    "4": "Equipe Cobrança 4",
    "5": "Equipe Cobrança 5",
}

def _normalizar_nome_equipe(valor: Any) -> str:
    texto = str(valor or "").strip().upper()
    texto = unicodedata.normalize("NFKD", texto)
    texto = "".join(ch for ch in texto if not unicodedata.combining(ch))
    texto = " ".join(texto.split())
    return texto


EQUIPE_NOME_COD = {
    _normalizar_nome_equipe(nome): codigo
    for codigo, nome in EQUIPE_COD_NOME.items()
}


def nome_equipe_por_codigo(equipe_codigo: Any) -> str:
    codigo = str(equipe_codigo or "").strip().replace(".0", "")
    return EQUIPE_COD_NOME.get(codigo, f"Equipe não mapeada")


def descricao_equipe_por_codigo(equipe_codigo: Any) -> str:
    codigo = str(equipe_codigo or "").strip().replace(".0", "")
    nome = nome_equipe_por_codigo(codigo)

    if nome == "Equipe não mapeada":
        return f"{nome} (código {codigo})"

    return f"{nome} (código {codigo})"


def codigo_equipe_por_nome(valor: Any) -> str:
    texto = str(valor or "").strip()

    if not texto:
        return ""

    texto_numero = texto.replace(".0", "")

    if texto_numero.isdigit():
        return texto_numero

    return EQUIPE_NOME_COD.get(_normalizar_nome_equipe(texto), "")


COLUNAS_LOG = [
    "DataHora",
    "Ordem",
    "Devedor",
    "DevedorNumero",
    "QtdeInformada",
    "EquipeCod",
    "EquipeNome",
    "EquipeDestino",
    "QtdeRetornadaSIOR",
    "QtdeSelecionada",
    "Status",
    "Mensagem",
    "RespostaStatus",
    "RespostaResumo",
]

COLUNAS_DETALHE = [
    "DataHora",
    "Ordem",
    "Devedor",
    "DevedorNumero",
    "QtdeInformada",
    "EquipeCod",
    "EquipeNome",
    "EquipeDestino",
    "StatusAcao",
    "CodigoProcessoCobranca",
    "CobrancaRowVersion",
    "NumeroAuto",
    "Auto",
    "SituacaoFase",
    "DevedorNome",
]

LogFn = Optional[Callable[[str], None]]


# ==========================================================
# HELPERS
# ==========================================================
def _log(log: LogFn, mensagem: str) -> None:
    if log:
        log(mensagem)


def _guid(session: requests.Session) -> str:
    guid = getattr(session, "_sior_lt_guid_encaminhar_devedores", None)

    if not guid:
        guid = str(uuid.uuid4())
        setattr(session, "_sior_lt_guid_encaminhar_devedores", guid)

    return guid


def renovar_lt_guid(session: requests.Session) -> str:
    guid = str(uuid.uuid4())
    setattr(session, "_sior_lt_guid_encaminhar_devedores", guid)
    return guid


def _sessao_expirada_texto(texto: str) -> bool:
    texto = texto or ""
    texto_lower = texto.lower()

    return (
        "a sua sessão expirou" in texto_lower
        or "account/login" in texto_lower
        or "/account/login" in texto_lower
        or "entrar com gov.br" in texto_lower
        or "acesso.gov.br" in texto_lower
    )


def normalizar_devedor_numero(valor: Any) -> str:
    """
    Retorna somente dígitos do CPF/CNPJ informado.
    """
    return "".join(ch for ch in str(valor or "") if ch.isdigit())


def url_tela_encaminhamento_devedor(devedor: Any = None) -> str:
    if devedor is None or str(devedor).strip() == "":
        return f"{URL_TELA_ENCAMINHAMENTO}?Bind=true"

    devedor_qs = quote(str(devedor).strip(), safe="")
    return (
        f"{URL_TELA_ENCAMINHAMENTO}/?"
        f"Devedor={devedor_qs}&Bind=true&Page=1&PageSize=10"
    )


def preparar_headers_encaminhar_devedores(
    session: requests.Session,
    devedor: Any = None,
) -> None:
    """
    Prepara headers mínimos para operar nos endpoints de Encaminhamento.

    A Session deve vir do fluxo iniciar_sessao_sior(), com cookies já
    sincronizados entre Selenium e requests.Session.
    """
    session.headers.update(
        {
            "Accept": "*/*",
            "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
            "Origin": BASE_HOST,
            "Referer": url_tela_encaminhamento_devedor(devedor),
            "Host": "servicos.dnit.gov.br",
            "X-Lt-Session-Guid": _guid(session),
            "X-Requested-With": "XMLHttpRequest",
        }
    )


def _headers_html(session: requests.Session, referer: str = None) -> Dict[str, str]:
    preparar_headers_encaminhar_devedores(session)

    return {
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
        "Referer": referer or f"{BASE_SIOR}/",
        "Host": "servicos.dnit.gov.br",
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
        "X-Lt-Session-Guid": _guid(session),
    }


def _headers_get_detalhe(
    session: requests.Session,
    devedor: Any,
) -> Dict[str, str]:
    preparar_headers_encaminhar_devedores(session, devedor=devedor)

    return {
        "Accept": "application/json; charset=utf-8",
        "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
        "Referer": url_tela_encaminhamento_devedor(devedor),
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "same-origin",
        "X-Lt-Session-Guid": _guid(session),
        "X-Requested-With": "XMLHttpRequest",
    }


def _headers_post_encaminhar(
    session: requests.Session,
    devedor: Any,
) -> Dict[str, str]:
    preparar_headers_encaminhar_devedores(session, devedor=devedor)

    return {
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        "Referer": url_tela_encaminhamento_devedor(devedor),
        "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
        "Origin": BASE_HOST,
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "same-origin",
        "X-Lt-Session-Guid": _guid(session),
        "X-Requested-With": "XMLHttpRequest",
    }


def inicializar_tela_encaminhar_devedores(
    session: requests.Session,
    log: LogFn = None,
    timeout: int = 60,
    renovar_guid: bool = True,
) -> None:
    """
    Abre a tela de Encaminhamento via requests.Session antes de operar
    os endpoints AJAX.
    """
    if renovar_guid:
        renovar_lt_guid(session)

    preparar_headers_encaminhar_devedores(session)

    _log(log, "🌐 Inicializando tela de Encaminhamento de Devedores via requests.Session...")

    resp = session.get(
        url_tela_encaminhamento_devedor(),
        headers=_headers_html(session),
        timeout=timeout,
        allow_redirects=True,
    )

    if resp.status_code not in (200, 201, 204):
        raise RuntimeError(
            "Falha ao acessar tela de Encaminhamento de Devedores. "
            f"HTTP {resp.status_code}: {resp.text[:500]}"
        )

    if _sessao_expirada_texto(resp.text or ""):
        raise RuntimeError(
            "Sessão expirada ao acessar a tela de Encaminhamento de Devedores."
        )

    _log(log, "✅ Tela de Encaminhamento de Devedores inicializada.")


# ==========================================================
# REQUESTS PRINCIPAIS
# ==========================================================
def listar_detalhe_auto_infracao_devedor(
    session: requests.Session,
    devedor: Any,
    equipe_codigo: Any,
    log: LogFn = None,
    timeout: int = 60,
) -> Dict[str, Any]:
    """
    Executa o GET ListDetalheAutoInfracao e monta o payload
    Selecionados[idx][Key]/Selecionados[idx][Value] para o POST.
    """
    devedor_original = str(devedor or "").strip()
    devedor_numero = normalizar_devedor_numero(devedor_original)
    equipe_codigo = str(equipe_codigo or "").strip()

    params = {
        "equipeCodigoProcesso": equipe_codigo,
        "devedorNumeroInscricao": devedor_numero,
        "sort": "",
        "group": "",
        "filter": "",
        "devedor": devedor_original,
        "bind": "true",
        "_": int(time.time() * 1000),
    }

    _log(
        log,
        f"🔎 Consultando devedor {devedor_original} | {descricao_equipe_por_codigo(equipe_codigo)}..."
    )

    resp = session.get(
        URL_LIST_DETALHE_AUTO,
        headers=_headers_get_detalhe(session, devedor_original),
        params=params,
        timeout=timeout,
    )

    if resp.status_code != 200:
        raise RuntimeError(
            "Falha no GET ListDetalheAutoInfracao. "
            f"HTTP {resp.status_code}: {resp.text[:1000]}"
        )

    texto = resp.text or ""

    if _sessao_expirada_texto(texto):
        raise RuntimeError(
            "Sessão expirada no GET ListDetalheAutoInfracao."
        )

    try:
        data = resp.json()
    except Exception:
        raise RuntimeError(
            f"Resposta inválida no GET ListDetalheAutoInfracao: {texto[:1000]}"
        )

    dados = data.get("Data", [])

    if not isinstance(dados, list):
        raise RuntimeError(
            f"Resposta inesperada no ListDetalheAutoInfracao: {data}"
        )

    pares = []
    selecionados_validos = 0

    for idx, item in enumerate(dados):
        codigo_processo = item.get("CodigoProcessoCobranca")
        row_version = item.get("CobrancaRowVersion")

        if codigo_processo is None or row_version is None:
            continue

        pares.append((f"Selecionados[{selecionados_validos}][Key]", str(codigo_processo)))
        pares.append((f"Selecionados[{selecionados_validos}][Value]", str(row_version)))
        selecionados_validos += 1

    payload = urlencode(pares)

    total_api = data.get("Total", len(dados))

    _log(
        log,
        f"📋 Devedor {devedor_original}: {len(dados)} auto(s) retornado(s); "
        f"{selecionados_validos} selecionado(s) válido(s)."
    )

    if total_api and int(total_api or 0) > len(dados):
        _log(
            log,
            "⚠ O SIOR informou Total maior que a quantidade retornada em Data. "
            "Valide se a tela está devolvendo todos os autos esperados."
        )

    return {
        "payload": payload,
        "dados": dados,
        "total_api": total_api,
        "qtde_retornada": len(dados),
        "qtde_selecionada": selecionados_validos,
        "json": data,
    }


def encaminhar_selecionados_devedor(
    session: requests.Session,
    payload_selecionados: str,
    devedor: Any,
    log: LogFn = None,
    timeout: int = 120,
) -> Dict[str, Any]:
    """
    Executa o POST EncaminharSelecionados.
    """
    devedor_original = str(devedor or "").strip()

    if not payload_selecionados:
        raise RuntimeError(
            "Payload de selecionados vazio. Nenhum auto será encaminhado."
        )

    _log(log, f"📤 Encaminhando autos do devedor {devedor_original}...")

    resp = session.post(
        URL_ENCAMINHAR_SELECIONADOS,
        headers=_headers_post_encaminhar(session, devedor_original),
        data=payload_selecionados,
        timeout=timeout,
    )

    if resp.status_code != 200:
        raise RuntimeError(
            "Falha no POST EncaminharSelecionados. "
            f"HTTP {resp.status_code}: {resp.text[:1000]}"
        )

    texto = resp.text or ""

    if _sessao_expirada_texto(texto):
        raise RuntimeError(
            "Sessão expirada no POST EncaminharSelecionados."
        )

    try:
        content = resp.json()
    except Exception:
        raise RuntimeError(
            f"Resposta inválida no POST EncaminharSelecionados: {texto[:1000]}"
        )

    status = str(content.get("status", "")).lower()

    if status != "ok":
        raise RuntimeError(
            f"POST EncaminharSelecionados retornou status inesperado: {content}"
        )

    _log(log, f"✅ Devedor {devedor_original} encaminhado com sucesso.")

    return content


# ==========================================================
# PIPELINE
# ==========================================================
def _get_numero_auto(item: Dict[str, Any]) -> str:
    for chave in (
        "NumeroAuto",
        "Auto",
        "NumeroAutoInfracao",
        "AutoInfracao",
        "Numero",
    ):
        valor = item.get(chave)
        if valor:
            return str(valor)

    return ""


def _resumo_resposta(content: Any) -> str:
    try:
        if isinstance(content, dict):
            # Mantém resumo curto para não poluir o XLSX.
            partes = []
            for chave in ("status", "message", "Message", "mensagem", "Mensagem"):
                if chave in content:
                    partes.append(f"{chave}={content.get(chave)}")
            return " | ".join(partes) if partes else str(content)[:500]
        return str(content)[:500]
    except Exception:
        return ""


def _registro_log(
    ordem: int,
    devedor: Any,
    qtde_informada: int,
    equipe_codigo: Any,
    qtde_retornada: int,
    qtde_selecionada: int,
    status: str,
    mensagem: str,
    resposta: Any = None,
) -> Dict[str, Any]:
    return {
        "DataHora": datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
        "Ordem": ordem,
        "Devedor": str(devedor or "").strip(),
        "DevedorNumero": normalizar_devedor_numero(devedor),
        "QtdeInformada": qtde_informada,
        "EquipeCod": str(equipe_codigo or "").strip(),
        "EquipeNome": nome_equipe_por_codigo(equipe_codigo),
        "EquipeDestino": descricao_equipe_por_codigo(equipe_codigo),
        "QtdeRetornadaSIOR": qtde_retornada,
        "QtdeSelecionada": qtde_selecionada,
        "Status": status,
        "Mensagem": mensagem,
        "RespostaStatus": resposta.get("status", "") if isinstance(resposta, dict) else "",
        "RespostaResumo": _resumo_resposta(resposta),
    }


def executar_encaminhamento_devedores(
    session: requests.Session,
    df_molde: pd.DataFrame,
    log: LogFn = None,
    validar_qtde_informada: bool = True,
    pausa_entre_devedores: float = 0.5,
) -> Dict[str, pd.DataFrame]:
    """
    Executa o fluxo completo por linha/combinação Devedor + EquipeCod.

    Segurança padrão:
    - se validar_qtde_informada=True, o POST só é enviado quando a quantidade
      retornada pelo SIOR é igual à Qtde informada na planilha. Isso evita
      encaminhar mais autos do que o administrador confirmou.
    """
    if df_molde is None or df_molde.empty:
        return {
            "logs": pd.DataFrame(columns=COLUNAS_LOG),
            "detalhes": pd.DataFrame(columns=COLUNAS_DETALHE),
        }

    registros_logs: List[Dict[str, Any]] = []
    registros_detalhes: List[Dict[str, Any]] = []

    total_linhas = len(df_molde)

    for idx, row in df_molde.reset_index(drop=True).iterrows():
        ordem = idx + 1
        devedor = str(row.get("Devedor", "")).strip()
        qtde_informada = int(row.get("Qtde", 0) or 0)
        equipe_codigo = str(row.get("EquipeCod", "")).strip()

        try:
            _log(
                log,
                f"🚀 {ordem}/{total_linhas} | Devedor {devedor} | "
                f"{descricao_equipe_por_codigo(equipe_codigo)} | Qtde informada {qtde_informada}."
            )

            resultado_get = listar_detalhe_auto_infracao_devedor(
                session=session,
                devedor=devedor,
                equipe_codigo=equipe_codigo,
                log=log,
            )

            dados = resultado_get.get("dados", []) or []
            qtde_retornada = int(resultado_get.get("qtde_retornada", 0) or 0)
            qtde_selecionada = int(resultado_get.get("qtde_selecionada", 0) or 0)
            payload = resultado_get.get("payload", "")

            for item in dados:
                registros_detalhes.append(
                    {
                        "DataHora": datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
                        "Ordem": ordem,
                        "Devedor": devedor,
                        "DevedorNumero": normalizar_devedor_numero(devedor),
                        "QtdeInformada": qtde_informada,
                        "EquipeCod": equipe_codigo,
                        "EquipeNome": nome_equipe_por_codigo(equipe_codigo),
                        "EquipeDestino": descricao_equipe_por_codigo(equipe_codigo),
                        "StatusAcao": "RETORNADO_GET",
                        "CodigoProcessoCobranca": item.get("CodigoProcessoCobranca", ""),
                        "CobrancaRowVersion": item.get("CobrancaRowVersion", ""),
                        "NumeroAuto": _get_numero_auto(item),
                        "Auto": item.get("Auto", ""),
                        "SituacaoFase": item.get("SituacaoFase", ""),
                        "DevedorNome": item.get("DevedorNome", item.get("Devedor", "")),
                    }
                )

            if qtde_selecionada <= 0 or not payload:
                mensagem = "Nenhum auto válido retornado pelo SIOR para encaminhamento."
                _log(log, f"⚠ {devedor}: {mensagem}")

                registros_logs.append(
                    _registro_log(
                        ordem=ordem,
                        devedor=devedor,
                        qtde_informada=qtde_informada,
                        equipe_codigo=equipe_codigo,
                        qtde_retornada=qtde_retornada,
                        qtde_selecionada=qtde_selecionada,
                        status="ERRO",
                        mensagem=mensagem,
                    )
                )
                continue

            if validar_qtde_informada and qtde_retornada != qtde_informada:
                mensagem = (
                    "Divergência de quantidade. "
                    f"Planilha informou {qtde_informada}, mas o SIOR retornou {qtde_retornada}. "
                    "POST não enviado por segurança."
                )
                _log(log, f"❌ {devedor}: {mensagem}")

                registros_logs.append(
                    _registro_log(
                        ordem=ordem,
                        devedor=devedor,
                        qtde_informada=qtde_informada,
                        equipe_codigo=equipe_codigo,
                        qtde_retornada=qtde_retornada,
                        qtde_selecionada=qtde_selecionada,
                        status="ERRO",
                        mensagem=mensagem,
                    )
                )
                continue

            resposta_post = encaminhar_selecionados_devedor(
                session=session,
                payload_selecionados=payload,
                devedor=devedor,
                log=log,
            )

            registros_logs.append(
                _registro_log(
                    ordem=ordem,
                    devedor=devedor,
                    qtde_informada=qtde_informada,
                    equipe_codigo=equipe_codigo,
                    qtde_retornada=qtde_retornada,
                    qtde_selecionada=qtde_selecionada,
                    status="SUCESSO",
                    mensagem="Encaminhamento realizado com sucesso no SIOR.",
                    resposta=resposta_post,
                )
            )

            # Atualiza os detalhes daquele devedor para indicar que a ação efetivou.
            for item in registros_detalhes:
                if item.get("Ordem") == ordem:
                    item["StatusAcao"] = "ENCAMINHADO"

        except Exception as ex:
            mensagem = str(ex)
            _log(log, f"❌ Falha no devedor {devedor}: {mensagem}")

            registros_logs.append(
                _registro_log(
                    ordem=ordem,
                    devedor=devedor,
                    qtde_informada=qtde_informada,
                    equipe_codigo=equipe_codigo,
                    qtde_retornada=0,
                    qtde_selecionada=0,
                    status="ERRO",
                    mensagem=mensagem,
                )
            )

        time.sleep(pausa_entre_devedores)

    df_logs = pd.DataFrame(registros_logs)
    df_detalhes = pd.DataFrame(registros_detalhes)

    for coluna in COLUNAS_LOG:
        if coluna not in df_logs.columns:
            df_logs[coluna] = ""

    for coluna in COLUNAS_DETALHE:
        if coluna not in df_detalhes.columns:
            df_detalhes[coluna] = ""

    return {
        "logs": df_logs[COLUNAS_LOG],
        "detalhes": df_detalhes[COLUNAS_DETALHE],
    }
