# ==========================================================
# REQUISIÇÕES - SUPER SAPIENS - CONSULTA CRÉDITOS DÍVIDA
# ==========================================================
import json
import re
from typing import Any, Dict, List, Optional

import requests


# ==========================================================
# CONFIGURAÇÕES
# ==========================================================
BACKEND_SAPIENS = "https://supersapiensbackend.agu.gov.br"
URL_CREDITO_DIVIDA = f"{BACKEND_SAPIENS}/v1/divida/credito"

LIMIT_PADRAO = 100
TIMEOUT_PADRAO = 60

POPULATE_CREDITO_DIVIDA = [
    "credor",
    "credor.pessoa",
    "faseAtual",
    "faseAtual.especieStatus",
    "unidadeResponsavel",
    "especieStatusAtual",
    "processo",
    "processo.documentoAvulsoOrigem",
    "vinculacoesEtiquetas",
    "vinculacoesEtiquetas.etiqueta",
    "vinculacaoLoteAtual",
    "vinculacaoLoteAtual.lote",
    "especieCredito",
    "devedorPrincipal",
    "regional",
    "modalidadeDocumentoOrigem",
    "certidaoDividaAtivaAtual",
    "certidaoDividaAtivaCancelada",
    "usuarioInscricaoDivida",
    "unidadeInscricaoDivida",
    "creditoOrigem",
    "criadoPor",
    "atualizadoPor",
]


# ==========================================================
# HELPERS
# ==========================================================
def _log(log, mensagem: str) -> None:
    if log:
        log(mensagem)
    else:
        print(mensagem)


def _somente_digitos(valor: Any) -> str:
    return re.sub(r"\D", "", str(valor or ""))


def normalizar_raiz_cnpj(valor: str) -> str:
    """
    Aceita raiz nos formatos:
    - 02762115
    - 02.762.115

    Retorna sempre 8 dígitos.
    """
    raiz = _somente_digitos(valor)

    if len(raiz) != 8:
        raise ValueError(
            f"Raiz de CNPJ inválida: {valor}. "
            "Informe exatamente 8 dígitos. Ex: 02762115 ou 02.762.115."
        )

    return raiz


def _headers_sapiens(token: str) -> Dict[str, str]:
    return {
        "Accept": "application/json, text/plain, */*",
        "Authorization": f"Bearer {token}",
        "Origin": "https://supersapiens.agu.gov.br",
        "Referer": "https://supersapiens.agu.gov.br/",
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/149.0.0.0 Safari/537.36"
        ),
    }


def _montar_params_credito(where: Dict[str, Any], offset: int, limit: int) -> Dict[str, str]:
    return {
        "where": json.dumps(where, ensure_ascii=False, separators=(",", ":")),
        "limit": str(int(limit)),
        "offset": str(int(offset)),
        "order": json.dumps({}, ensure_ascii=False, separators=(",", ":")),
        "populate": json.dumps(
            POPULATE_CREDITO_DIVIDA,
            ensure_ascii=False,
            separators=(",", ":"),
        ),
        "context": json.dumps({}, ensure_ascii=False, separators=(",", ":")),
    }


def _normalizar_registro_credito(item: Dict[str, Any]) -> Dict[str, Any]:
    """
    Mantém o mesmo molde usado pela consulta atual por CPF/CNPJ.
    Campos extras foram preservados para enriquecer a aba Geral do XLSX,
    sem prejudicar as colunas que já existem.
    """
    return {
        "id": item.get("id"),
        "numeroCredito": item.get("numeroCredito"),
        "numeroCreditoSistemaOriginario": item.get("numeroCreditoSistemaOriginario"),
        "valorOriginario": item.get("valorOriginario"),
        "dataVencimento": item.get("dataVencimento"),
        "dataInicioMultaMora": item.get("dataInicioMultaMora"),
        "dataInicioSelic": item.get("dataInicioSelic"),
        "descricaoComplementoFundamentoLegal": item.get("descricaoComplementoFundamentoLegal"),
        "dataConstituicaoDefinitiva": item.get("dataConstituicaoDefinitiva"),
        "defesaApresentada": item.get("defesaApresentada"),
        "dataNotificacaoInicial": item.get("dataNotificacaoInicial"),
        "dataDecursoPrazoDefesa": item.get("dataDecursoPrazoDefesa"),
        "postIt": item.get("postIt"),
        "dataDocumentoOrigem": item.get("dataDocumentoOrigem"),
        "numeroDocumentoOrigem": item.get("numeroDocumentoOrigem"),
        "saldoAtualizado": item.get("saldoAtualizado"),
        "dataAtualizacao": item.get("dataAtualizacao"),
        "dataValidadeAtualizacao": item.get("dataValidadeAtualizacao"),
        "dataInscricaoDivida": item.get("dataInscricaoDivida"),
        "valorInscricaoDivida": item.get("valorInscricaoDivida"),
        "numeroInscricaoDivida": item.get("numeroInscricaoDivida"),
        "raizDevedorPrincipal": item.get("raizDevedorPrincipal"),
        "devedorPrincipal": item.get("devedorPrincipal"),
        "credor": item.get("credor"),
        "regional": item.get("regional"),
        "unidadeResponsavel": item.get("unidadeResponsavel"),
        "faseAtual": item.get("faseAtual"),
        "especieStatusAtual": item.get("especieStatusAtual"),
        "especieCredito": item.get("especieCredito"),
        "modalidadeDocumentoOrigem": item.get("modalidadeDocumentoOrigem"),
        "certidaoDividaAtivaAtual": item.get("certidaoDividaAtivaAtual"),
        "certidaoDividaAtivaCancelada": item.get("certidaoDividaAtivaCancelada"),
        "vinculacoesEtiquetas": item.get("vinculacoesEtiquetas"),
        "creditoOrigem": item.get("creditoOrigem"),
        "usuarioInscricaoDivida": item.get("usuarioInscricaoDivida"),
        "unidadeInscricaoDivida": item.get("unidadeInscricaoDivida"),
        "criadoPor": item.get("criadoPor"),
        "atualizadoPor": item.get("atualizadoPor"),
        "processo": item.get("processo"),
    }


def _consultar_creditos_paginado(
    token: str,
    where: Dict[str, Any],
    descricao_log: str,
    limit: int = LIMIT_PADRAO,
    timeout: int = TIMEOUT_PADRAO,
    log=None,
) -> Dict[str, Any]:
    if not token:
        raise RuntimeError("Token inválido — não foi fornecido JWT.")

    headers = _headers_sapiens(token)
    registros: List[Dict[str, Any]] = []
    offset = 0
    pagina = 1
    total_api: Optional[int] = None

    while True:
        params = _montar_params_credito(
            where=where,
            offset=offset,
            limit=limit,
        )

        resp = requests.get(
            URL_CREDITO_DIVIDA,
            headers=headers,
            params=params,
            timeout=timeout,
        )

        if resp.status_code in (401, 403):
            raise RuntimeError(
                "Token do Super Sapiens expirado ou sem autorização. "
                "Faça novo login e tente novamente."
            )

        if resp.status_code != 200:
            raise RuntimeError(
                f"Erro HTTP {resp.status_code}: {resp.text[:500]}"
            )

        data = resp.json()
        entidades = data.get("entities", [])

        if not isinstance(entidades, list):
            raise RuntimeError(
                f"Resposta inesperada do Super Sapiens: {str(data)[:500]}"
            )

        total_api = data.get("total", total_api)

        if not entidades:
            break

        for item in entidades:
            registros.append(
                _normalizar_registro_credito(item)
            )

        _log(
            log,
            (
                f"✅ {descricao_log} — página {pagina}: "
                f"{len(entidades)} registro(s) capturado(s) "
                f"(total parcial: {len(registros)})."
            ),
        )

        if total_api is not None:
            try:
                if len(registros) >= int(total_api):
                    break
            except Exception:
                pass

        if len(entidades) < int(limit):
            break

        offset += int(limit)
        pagina += 1

    _log(
        log,
        f"📊 {descricao_log} — total de registros coletados: {len(registros)}.",
    )

    return {
        "total": len(registros),
        "total_api": total_api,
        "records": registros,
    }


# ==========================================================
# CONSULTA POR CPF/CNPJ COMPLETO
# ==========================================================
def get_creditos_sapiens(token: str, documento: str, log=None) -> dict:
    """
    Consulta créditos no Super Sapiens por CPF/CNPJ completo do devedor.
    Mantém o retorno histórico:
        {"total": int, "records": list}
    """
    documento_limpo = _somente_digitos(documento)

    where = {
        "andX": [
            {
                "devedorPrincipal.numeroDocumentoPrincipal": f"eq:{documento_limpo}"
            }
        ]
    }

    try:
        return _consultar_creditos_paginado(
            token=token,
            where=where,
            descricao_log=f"Documento {documento_limpo}",
            log=log,
        )

    except Exception as ex:
        _log(
            log,
            f"❌ Falha na requisição Super Sapiens para {documento_limpo}: {ex}",
        )
        return {"total": 0, "records": []}


# ==========================================================
# CONSULTA POR RAIZ DO DEVEDOR PRINCIPAL - CNPJ
# ==========================================================
def get_creditos_sapiens_por_raiz_devedor(
    token: str,
    raiz_cnpj: str,
    log=None,
) -> dict:
    """
    Consulta créditos no Super Sapiens pela raiz do devedor principal.

    Request equivalente:
    where={"andX":[{"raizDevedorPrincipal":"like:%02762115%"}]}

    Retorno no mesmo molde da consulta por CPF/CNPJ:
        {"total": int, "records": list, "raiz": str}
    """
    raiz = normalizar_raiz_cnpj(raiz_cnpj)

    where = {
        "andX": [
            {
                "raizDevedorPrincipal": f"like:%{raiz}%"
            }
        ]
    }

    try:
        resultado = _consultar_creditos_paginado(
            token=token,
            where=where,
            descricao_log=f"Raiz CNPJ {raiz}",
            log=log,
        )
        resultado["raiz"] = raiz
        return resultado

    except Exception as ex:
        _log(
            log,
            f"❌ Falha na requisição Super Sapiens para raiz {raiz}: {ex}",
        )
        return {"total": 0, "records": [], "raiz": raiz}


def get_dados_credito_raiz_devedor_sapiens(
    token: str,
    raiz_cnpj: str,
    limit: int = LIMIT_PADRAO,
    log=None,
    timeout: int = TIMEOUT_PADRAO,
) -> dict:
    """
    Alias compatível com versões anteriores do código.
    """
    raiz = normalizar_raiz_cnpj(raiz_cnpj)

    where = {
        "andX": [
            {
                "raizDevedorPrincipal": f"like:%{raiz}%"
            }
        ]
    }

    resultado = _consultar_creditos_paginado(
        token=token,
        where=where,
        descricao_log=f"Raiz CNPJ {raiz}",
        limit=limit,
        timeout=timeout,
        log=log,
    )

    return {
        "Data": resultado.get("records", []),
        "records": resultado.get("records", []),
        "Total": resultado.get("total", 0),
        "total": resultado.get("total", 0),
        "Raiz": raiz,
        "raiz": raiz,
    }


def get_dados_creditos_raizes_devedores_sapiens(
    token: str,
    raizes: List[str],
    log=None,
    timeout: int = TIMEOUT_PADRAO,
) -> dict:
    """
    Consulta múltiplas raízes de CNPJ e consolida os dados no mesmo molde
    da consulta por CPF/CNPJ.
    """
    todos: List[Dict[str, Any]] = []
    erros: List[Dict[str, str]] = []

    for idx, raiz_original in enumerate(raizes, start=1):
        try:
            raiz = normalizar_raiz_cnpj(raiz_original)
            _log(
                log,
                f"🔎 Consultando raiz {idx}/{len(raizes)}: {raiz}",
            )

            resultado = get_dados_credito_raiz_devedor_sapiens(
                token=token,
                raiz_cnpj=raiz,
                log=log,
                timeout=timeout,
            )

            registros = resultado.get("records") or resultado.get("Data") or []

            for registro in registros:
                registro["RaizPesquisada"] = raiz
                registro["ConsultaPor"] = "Raiz CNPJ"

            todos.extend(registros)

        except Exception as ex:
            erros.append({
                "Raiz": str(raiz_original),
                "Erro": str(ex),
            })
            _log(
                log,
                f"❌ Erro ao consultar raiz {raiz_original}: {ex}",
            )

    return {
        "Data": todos,
        "records": todos,
        "Total": len(todos),
        "total": len(todos),
        "Erros": erros,
        "erros": erros,
    }
