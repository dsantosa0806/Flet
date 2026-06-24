# ==========================================================
# REQUISIÇÕES SIOR - RECUPERAÇÃO DE CRÉDITOS PFE
# ==========================================================
import os
import re
import time
from datetime import datetime
from typing import Callable, Dict, Any, Optional, List, Tuple

import pandas as pd
import requests


# ==========================================================
# URLS / CONSTANTES
# ==========================================================
BASE_HOST = "https://servicos.dnit.gov.br"
BASE_SIOR = f"{BASE_HOST}/sior"

URL_TELA_RECUPERACAO_PFE = f"{BASE_SIOR}/Cobranca/RecuperacaoPFE/"
URL_LIST_RECUPERACAO_PFE = f"{BASE_SIOR}/Cobranca/RecuperacaoPFE/List"

VALORES_PISO = [500, 550, 600, 650, 700, 750, 800, 850, 900, 950]
PISO_PADRAO = 650

LogFn = Optional[Callable[[str], None]]


# ==========================================================
# LOG / HELPERS BÁSICOS
# ==========================================================
def _log(log: LogFn, mensagem: str) -> None:
    if log:
        log(mensagem)


def _sessao_expirada_texto(texto: str) -> bool:
    texto = texto or ""

    return (
        "A sua sessão expirou" in texto
        or "Account/Login" in texto
        or "/Account/Login" in texto
        or "Entrar com gov.br" in texto
        or "entrar com gov.br" in texto.lower()
    )


def somente_digitos(valor) -> str:
    return re.sub(r"\D", "", str(valor or ""))


def aplicar_mascara_cpf_cnpj(numero: str) -> str:
    """Aplica máscara a CPF ou CNPJ sem alterar valores inválidos."""
    digitos = somente_digitos(numero)

    if len(digitos) == 11:
        return f"{digitos[:3]}.{digitos[3:6]}.{digitos[6:9]}-{digitos[9:]}"

    if len(digitos) == 14:
        return f"{digitos[:2]}.{digitos[2:5]}.{digitos[5:8]}/{digitos[8:12]}-{digitos[12:]}"

    return str(numero or "")


def classificar_pessoa(numero: str) -> str:
    digitos = somente_digitos(numero)

    if len(digitos) == 11:
        return "Pessoa Física"

    if len(digitos) == 14:
        return "Pessoa Jurídica"

    return "Inválido"


def converter_numero_br(valor) -> float:
    """
    Converte números em formatos comuns do SIOR para float.

    Aceita exemplos:
    - 650
    - 650.25
    - 650,25
    - R$ 1.234,56
    - 1,234.56
    """
    if valor is None:
        return 0.0

    if isinstance(valor, (int, float)):
        try:
            return float(valor)
        except Exception:
            return 0.0

    texto = str(valor).strip()

    if not texto:
        return 0.0

    texto = re.sub(r"[^0-9,\.\-]", "", texto)

    if not texto:
        return 0.0

    try:
        # Formato BR: 1.234,56
        if "," in texto and "." in texto:
            if texto.rfind(",") > texto.rfind("."):
                texto = texto.replace(".", "").replace(",", ".")
            else:
                texto = texto.replace(",", "")

        # Formato simples com vírgula decimal: 650,25
        elif "," in texto:
            texto = texto.replace(".", "").replace(",", ".")

        return float(texto)

    except Exception:
        return 0.0


def _extrair_valor_data(valor) -> str:
    if isinstance(valor, dict):
        return valor.get("DateString") or valor.get("dateString") or valor.get("Value") or ""

    return valor or ""


# ==========================================================
# HEADERS / INICIALIZAÇÃO DA TELA
# ==========================================================
def preparar_headers_recuperacao_pfe(session: requests.Session) -> None:
    """
    Prepara headers mínimos para operar na tela RecuperacaoPFE.

    A Session deve vir do fluxo iniciar_sessao_sior(), já com cookies válidos.
    """
    session.headers.update(
        {
            "Accept": "*/*",
            "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
            "Origin": BASE_HOST,
            "Referer": URL_TELA_RECUPERACAO_PFE,
            "Host": "servicos.dnit.gov.br",
            "X-Lt-Session-Guid": getattr(session, "_sior_lt_guid", ""),
            "X-Requested-With": "XMLHttpRequest",
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "same-origin",
        }
    )


def _headers_html(referer: str = None) -> Dict[str, str]:
    return {
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
        "Referer": referer or f"{BASE_SIOR}/",
        "Host": "servicos.dnit.gov.br",
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
    }


def _headers_ajax_get(session: requests.Session) -> Dict[str, str]:
    preparar_headers_recuperacao_pfe(session)

    return {
        "Accept": "*/*",
        "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
        "Referer": URL_TELA_RECUPERACAO_PFE,
        "Host": "servicos.dnit.gov.br",
        "X-Lt-Session-Guid": getattr(session, "_sior_lt_guid", ""),
        "X-Requested-With": "XMLHttpRequest",
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "same-origin",
    }


def inicializar_tela_recuperacao_pfe(
    session: requests.Session,
    log: LogFn = None,
    timeout: int = 60,
) -> None:
    """
    Inicializa a tela Recuperação PFE antes de consumir o endpoint List.
    """
    preparar_headers_recuperacao_pfe(session)

    _log(log, "🌐 Inicializando tela Recuperação de Créditos PFE via requests.Session...")

    response = session.get(
        URL_TELA_RECUPERACAO_PFE,
        headers=_headers_html(referer=f"{BASE_SIOR}/"),
        timeout=timeout,
        allow_redirects=True,
    )

    if response.status_code != 200:
        raise RuntimeError(
            f"Falha ao inicializar tela Recuperação PFE. "
            f"HTTP {response.status_code}: {response.text[:500]}"
        )

    if _sessao_expirada_texto(response.text or ""):
        raise RuntimeError(
            "Sessão expirada ao inicializar a tela Recuperação PFE via requests.Session."
        )

    preparar_headers_recuperacao_pfe(session)
    _log(log, "✅ Tela Recuperação PFE inicializada com sucesso.")


# ==========================================================
# CONSULTA / ENRIQUECIMENTO
# ==========================================================
def _normalizar_data_api(json_result: Dict[str, Any]) -> List[Dict[str, Any]]:
    dados_normalizados = []

    for bloco in json_result.get("Data", []) or []:
        if isinstance(bloco, list):
            dados_normalizados.extend([item for item in bloco if isinstance(item, dict)])
        elif isinstance(bloco, dict):
            dados_normalizados.append(bloco)

    return dados_normalizados


def consultar_pagina_recuperacao_pfe(
    session: requests.Session,
    page: int,
    page_size: int,
    timeout: int = 90,
) -> Tuple[List[Dict[str, Any]], int]:
    preparar_headers_recuperacao_pfe(session)

    params = {
        "sort": "",
        "page": page,
        "pageSize": page_size,
        "group": "",
        "filter": "",
        "bind": "true",
        "calledfromapi": "true",
        "calledFromApi": "true",
        "_": int(time.time() * 1000),
    }

    response = session.get(
        URL_LIST_RECUPERACAO_PFE,
        params=params,
        headers=_headers_ajax_get(session),
        timeout=timeout,
    )

    if response.status_code != 200:
        raise RuntimeError(
            f"Erro na requisição Recuperação PFE página {page}. "
            f"HTTP {response.status_code}: {response.text[:1000]}"
        )

    texto = response.text or ""

    if _sessao_expirada_texto(texto):
        raise RuntimeError(
            f"Sessão expirada ao consultar Recuperação PFE página {page}."
        )

    try:
        json_result = response.json()
    except Exception:
        raise RuntimeError(
            f"Resposta inválida na página {page}: {texto[:1000]}"
        )

    dados = _normalizar_data_api(json_result)
    total_api = int(json_result.get("Total") or len(dados))

    return dados, total_api


def enriquecer_dataframe_recuperacao(
    df: pd.DataFrame,
    piso: float,
) -> pd.DataFrame:
    if df.empty:
        return df

    df = df.copy()

    if "DevedorNumeroInscricao" in df.columns:
        df["DevedorNumeroInscricao_Digitos"] = (
            df["DevedorNumeroInscricao"]
            .fillna("")
            .astype(str)
            .apply(somente_digitos)
        )

        df["DevedorNumeroInscricao"] = (
            df["DevedorNumeroInscricao"]
            .fillna("")
            .astype(str)
            .apply(aplicar_mascara_cpf_cnpj)
        )

        df["TipoPessoa"] = df["DevedorNumeroInscricao_Digitos"].apply(classificar_pessoa)

    elif "DevedorIdentificacao" in df.columns:
        df["TipoPessoa"] = df["DevedorIdentificacao"].apply(classificar_pessoa)

    else:
        df["TipoPessoa"] = "Não identificado"

    if "ValorTotal" in df.columns:
        df["ValorTotalNumerico"] = df["ValorTotal"].apply(converter_numero_br)
        df["ClassificacaoPiso"] = df["ValorTotalNumerico"].apply(
            lambda valor: "Acima do Piso" if valor > float(piso) else "Abaixo do Piso"
        )
    else:
        df["ValorTotalNumerico"] = 0.0
        df["ClassificacaoPiso"] = "Sem ValorTotal"

    if "QtdeAutos" in df.columns:
        df["QtdeAutosNumerico"] = pd.to_numeric(df["QtdeAutos"], errors="coerce").fillna(0).astype(int)
    else:
        df["QtdeAutosNumerico"] = 0

    # Normaliza campos de data que eventualmente venham como dict.
    for coluna in df.columns:
        try:
            if df[coluna].apply(lambda v: isinstance(v, dict)).any():
                df[coluna] = df[coluna].apply(_extrair_valor_data)
        except Exception:
            pass

    # Reorganiza colunas mais importantes no início.
    colunas_prioritarias = [
        "DevedorIdentificacao",
        "DevedorNumeroInscricao",
        "TipoPessoa",
        "QtdeAutos",
        "QtdeAutosNumerico",
        "ValorTotal",
        "ValorTotalNumerico",
        "ClassificacaoPiso",
    ]

    colunas = list(df.columns)

    for coluna in reversed(colunas_prioritarias):
        if coluna in colunas:
            colunas.insert(0, colunas.pop(colunas.index(coluna)))

    return df[colunas]


def enviar_requisicao_get(
    session: requests.Session,
    piso: float = PISO_PADRAO,
    page_size: int = 100000,
    log: LogFn = None,
    timeout: int = 90,
) -> pd.DataFrame:
    """
    Percorre todas as páginas do endpoint RecuperacaoPFE/List e retorna DataFrame enriquecido.
    """
    inicio = datetime.now()
    dados = []
    page = 1
    total_api = None

    preparar_headers_recuperacao_pfe(session)

    while True:
        registros_pagina, total_api = consultar_pagina_recuperacao_pfe(
            session=session,
            page=page,
            page_size=page_size,
            timeout=timeout,
        )

        if not registros_pagina:
            _log(log, "ℹ️ Nenhum dado encontrado ou última página alcançada.")
            break

        dados.extend(registros_pagina)

        _log(
            log,
            f"📄 Página {page} carregada com {len(registros_pagina)} registro(s). "
            f"Total acumulado: {len(dados)} / {total_api}.",
        )

        if total_api is not None and len(dados) >= total_api:
            break

        page += 1

    df = pd.DataFrame(dados)
    df = enriquecer_dataframe_recuperacao(df, piso=piso)

    fim = datetime.now()
    duracao = str(fim - inicio).split(".")[0]

    _log(
        log,
        f"✅ Varredura Recuperação PFE executada em {duracao}. Total de registros: {len(df)}.",
    )

    return df


# ==========================================================
# ANÁLISES / EXPORTAÇÃO
# ==========================================================
def _coluna_chave_devedor(df: pd.DataFrame) -> str:
    for coluna in [
        "DevedorNumeroInscricao_Digitos",
        "DevedorNumeroInscricao",
        "DevedorIdentificacao",
        "Devedor",
        "NomeDevedor",
    ]:
        if coluna in df.columns:
            return coluna

    return "__indice__"


def _formatar_percentual(valor) -> pd.Series:
    try:
        return valor.round(2)
    except AttributeError:
        return round(float(valor or 0), 2)


def criar_resumos_analiticos(
    df: pd.DataFrame,
    piso: float,
    logs_df: Optional[pd.DataFrame] = None,
) -> Dict[str, pd.DataFrame]:
    """
    Cria as abas analíticas do XLSX com foco principal em QtdeAutosNumerico.

    Regra de negócio:
    - A classificação Acima/Abaixo do Piso continua sendo feita por devedor,
      a partir do ValorTotalNumerico.
    - As análises principais passam a somar QtdeAutosNumerico para demonstrar
      a quantidade real de autos disponíveis em cada grupo.
    """
    logs_df = logs_df if logs_df is not None else pd.DataFrame()

    if df.empty:
        return {
            "Resumo Geral": pd.DataFrame(
                [
                    {"Indicador": "Piso utilizado", "Valor": piso},
                    {"Indicador": "Total de registros/devedores", "Valor": 0},
                    {"Indicador": "Total de devedores únicos", "Valor": 0},
                    {"Indicador": "Total de autos disponíveis", "Valor": 0},
                    {"Indicador": "Autos acima do piso", "Valor": 0},
                    {"Indicador": "Autos abaixo do piso", "Valor": 0},
                    {"Indicador": "ValorTotal somado", "Valor": 0},
                ]
            ),
            "Resumo Autos Piso": pd.DataFrame(),
            "TipoPessoa": pd.DataFrame(),
            "Classificacao Piso": pd.DataFrame(),
            "Tipo x Piso": pd.DataFrame(),
            "Top Devedores Autos": pd.DataFrame(),
            "Top Devedores Valor": pd.DataFrame(),
            "Logs": logs_df,
        }

    df = df.copy()

    chave_devedor = _coluna_chave_devedor(df)
    if chave_devedor == "__indice__":
        df[chave_devedor] = df.index.astype(str)

    if "TipoPessoa" not in df.columns:
        df["TipoPessoa"] = "Não identificado"

    if "ClassificacaoPiso" not in df.columns:
        df["ClassificacaoPiso"] = "Sem classificação"

    if "QtdeAutosNumerico" not in df.columns:
        df["QtdeAutosNumerico"] = 0

    if "ValorTotalNumerico" not in df.columns:
        df["ValorTotalNumerico"] = 0.0

    df["QtdeAutosNumerico"] = (
        pd.to_numeric(df["QtdeAutosNumerico"], errors="coerce")
        .fillna(0)
        .astype(int)
    )

    df["ValorTotalNumerico"] = (
        pd.to_numeric(df["ValorTotalNumerico"], errors="coerce")
        .fillna(0.0)
        .astype(float)
    )

    total_registros = len(df)
    total_devedores = int(df[chave_devedor].nunique(dropna=True))
    total_autos = int(df["QtdeAutosNumerico"].sum())
    valor_total = float(df["ValorTotalNumerico"].sum())

    mask_acima = df["ClassificacaoPiso"].eq("Acima do Piso")
    mask_abaixo = df["ClassificacaoPiso"].eq("Abaixo do Piso")

    devedores_acima = int(mask_acima.sum())
    devedores_abaixo = int(mask_abaixo.sum())

    autos_acima = int(df.loc[mask_acima, "QtdeAutosNumerico"].sum())
    autos_abaixo = int(df.loc[mask_abaixo, "QtdeAutosNumerico"].sum())

    valor_acima = float(df.loc[mask_acima, "ValorTotalNumerico"].sum())
    valor_abaixo = float(df.loc[mask_abaixo, "ValorTotalNumerico"].sum())

    resumo_geral = pd.DataFrame(
        [
            {"Indicador": "Piso utilizado", "Valor": piso},
            {"Indicador": "Total de registros/devedores", "Valor": total_registros},
            {"Indicador": "Total de devedores únicos", "Valor": total_devedores},
            {"Indicador": "Total de autos disponíveis", "Valor": total_autos},
            {"Indicador": "Autos acima do piso", "Valor": autos_acima},
            {"Indicador": "Autos abaixo do piso", "Valor": autos_abaixo},
            {
                "Indicador": "% autos acima do piso",
                "Valor": round((autos_acima / total_autos) * 100, 2) if total_autos else 0,
            },
            {
                "Indicador": "% autos abaixo do piso",
                "Valor": round((autos_abaixo / total_autos) * 100, 2) if total_autos else 0,
            },
            {"Indicador": "Devedores acima do piso", "Valor": devedores_acima},
            {"Indicador": "Devedores abaixo do piso", "Valor": devedores_abaixo},
            {
                "Indicador": "% devedores acima do piso",
                "Valor": round((devedores_acima / total_registros) * 100, 2) if total_registros else 0,
            },
            {
                "Indicador": "% devedores abaixo do piso",
                "Valor": round((devedores_abaixo / total_registros) * 100, 2) if total_registros else 0,
            },
            {"Indicador": "ValorTotal somado", "Valor": valor_total},
            {"Indicador": "ValorTotal acima do piso", "Valor": valor_acima},
            {"Indicador": "ValorTotal abaixo do piso", "Valor": valor_abaixo},
            {
                "Indicador": "Média de autos por devedor",
                "Valor": round(total_autos / total_registros, 2) if total_registros else 0,
            },
            {
                "Indicador": "Valor médio por auto",
                "Valor": round(valor_total / total_autos, 2) if total_autos else 0,
            },
            {"Indicador": "Data/Hora da análise", "Valor": datetime.now().strftime("%d/%m/%Y %H:%M:%S")},
        ]
    )

    def agregar_por(colunas: List[str]) -> pd.DataFrame:
        resumo = (
            df.groupby(colunas, dropna=False)
            .agg(
                QuantidadeRegistros=(chave_devedor, "count"),
                QuantidadeDevedores=(chave_devedor, pd.Series.nunique),
                QtdeAutosNumerico=("QtdeAutosNumerico", "sum"),
                ValorTotalNumerico=("ValorTotalNumerico", "sum"),
            )
            .reset_index()
        )

        resumo["PercentualAutos"] = _formatar_percentual(
            (resumo["QtdeAutosNumerico"] / total_autos) * 100 if total_autos else 0
        )

        resumo["PercentualDevedores"] = _formatar_percentual(
            (resumo["QuantidadeDevedores"] / total_devedores) * 100 if total_devedores else 0
        )

        resumo["PercentualValorTotal"] = _formatar_percentual(
            (resumo["ValorTotalNumerico"] / valor_total) * 100 if valor_total else 0
        )

        resumo["AutosPorDevedor"] = resumo.apply(
            lambda row: round(
                row["QtdeAutosNumerico"] / row["QuantidadeDevedores"],
                2,
            )
            if row.get("QuantidadeDevedores", 0)
            else 0,
            axis=1,
        )

        resumo["ValorMedioPorAuto"] = resumo.apply(
            lambda row: round(
                row["ValorTotalNumerico"] / row["QtdeAutosNumerico"],
                2,
            )
            if row.get("QtdeAutosNumerico", 0)
            else 0,
            axis=1,
        )

        colunas_metricas = [
            "QuantidadeRegistros",
            "QuantidadeDevedores",
            "PercentualDevedores",
            "QtdeAutosNumerico",
            "PercentualAutos",
            "AutosPorDevedor",
            "ValorTotalNumerico",
            "PercentualValorTotal",
            "ValorMedioPorAuto",
        ]

        resumo = resumo[colunas + colunas_metricas]

        return resumo.sort_values(
            by=["QtdeAutosNumerico", "ValorTotalNumerico"],
            ascending=[False, False],
        ).reset_index(drop=True)

    resumo_tipo = agregar_por(["TipoPessoa"])
    resumo_piso = agregar_por(["ClassificacaoPiso"])
    resumo_tipo_piso = agregar_por(["TipoPessoa", "ClassificacaoPiso"])

    # Aba direta para leitura rápida do foco principal: autos por classificação de piso.
    resumo_autos_piso = resumo_piso.copy()

    colunas_top = [
        coluna
        for coluna in [
            "DevedorIdentificacao",
            "DevedorNumeroInscricao",
            "TipoPessoa",
            "QtdeAutos",
            "QtdeAutosNumerico",
            "ValorTotal",
            "ValorTotalNumerico",
            "ClassificacaoPiso",
        ]
        if coluna in df.columns
    ]

    top_base = df[colunas_top].copy() if colunas_top else pd.DataFrame()

    if not top_base.empty and "QtdeAutosNumerico" in top_base.columns:
        if "ValorMedioPorAuto" not in top_base.columns:
            top_base["ValorMedioPorAuto"] = top_base.apply(
                lambda row: round(
                    float(row.get("ValorTotalNumerico", 0) or 0) /
                    int(row.get("QtdeAutosNumerico", 0) or 0),
                    2,
                )
                if int(row.get("QtdeAutosNumerico", 0) or 0) > 0
                else 0,
                axis=1,
            )

        top_devedores_autos = (
            top_base.sort_values(
                ["QtdeAutosNumerico", "ValorTotalNumerico"],
                ascending=[False, False],
            )
            .head(1000)
            .reset_index(drop=True)
        )
    else:
        top_devedores_autos = pd.DataFrame()

    if not top_base.empty and "ValorTotalNumerico" in top_base.columns:
        top_devedores_valor = (
            top_base.sort_values(
                ["ValorTotalNumerico", "QtdeAutosNumerico"],
                ascending=[False, False],
            )
            .head(1000)
            .reset_index(drop=True)
        )
    else:
        top_devedores_valor = pd.DataFrame()

    amostra = df.head(5000).copy()

    return {
        "Resumo Geral": resumo_geral,
        "Resumo Autos Piso": resumo_autos_piso,
        "TipoPessoa": resumo_tipo,
        "Classificacao Piso": resumo_piso,
        "Tipo x Piso": resumo_tipo_piso,
        "Top Devedores Autos": top_devedores_autos,
        "Top Devedores Valor": top_devedores_valor,
        "Amostra Dados": amostra,
        "Logs": logs_df,
    }

def _ajustar_largura_abas(writer) -> None:
    for ws in writer.sheets.values():
        try:
            for column_cells in ws.columns:
                max_length = 0
                column_letter = column_cells[0].column_letter

                for cell in column_cells:
                    try:
                        max_length = max(max_length, len(str(cell.value or "")))
                    except Exception:
                        pass

                ws.column_dimensions[column_letter].width = min(max_length + 2, 80)
        except Exception:
            pass


def exportar_csv_bruto(
    caminho_csv: str,
    df: pd.DataFrame,
) -> None:
    os.makedirs(os.path.dirname(caminho_csv), exist_ok=True)
    df.to_csv(caminho_csv, index=False, encoding="utf-8-sig", sep=";")


def exportar_xlsx_analise(
    caminho_xlsx: str,
    df: pd.DataFrame,
    piso: float,
    df_logs: Optional[pd.DataFrame] = None,
) -> None:
    os.makedirs(os.path.dirname(caminho_xlsx), exist_ok=True)

    resumos = criar_resumos_analiticos(
        df=df,
        piso=piso,
        logs_df=df_logs,
    )

    with pd.ExcelWriter(caminho_xlsx, engine="openpyxl") as writer:
        for nome_aba, df_aba in resumos.items():
            nome_seguro = str(nome_aba)[:31]
            df_aba.to_excel(writer, sheet_name=nome_seguro, index=False)

        _ajustar_largura_abas(writer)


def exportar_resultados_recuperacao_pfe(
    pasta_saida: str,
    df: pd.DataFrame,
    piso: float,
    df_logs: Optional[pd.DataFrame] = None,
    prefixo: str = "analise_recuperacao_creditos_pfe",
) -> Dict[str, str]:
    ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")

    os.makedirs(pasta_saida, exist_ok=True)

    caminho_csv = os.path.join(
        pasta_saida,
        f"{prefixo}_dados_brutos_{ts}.csv",
    )

    caminho_xlsx = os.path.join(
        pasta_saida,
        f"{prefixo}_{ts}.xlsx",
    )

    exportar_csv_bruto(
        caminho_csv=caminho_csv,
        df=df,
    )

    exportar_xlsx_analise(
        caminho_xlsx=caminho_xlsx,
        df=df,
        piso=piso,
        df_logs=df_logs,
    )

    return {
        "csv": caminho_csv,
        "xlsx": caminho_xlsx,
    }
