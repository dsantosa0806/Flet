# ==========================================================
# REQUISIÇÕES SIOR - VARREDURA ENCAMINHAMENTO
# ==========================================================
from datetime import datetime
from typing import Callable, Optional, List
from urllib.parse import urlencode

import pandas as pd
import requests


# ==========================================================
# CONSTANTES
# ==========================================================
BASE_HOST = "https://servicos.dnit.gov.br"
BASE_SIOR = f"{BASE_HOST}/sior"

URL_ENCAMINHAMENTO_PAGE = (
    f"{BASE_SIOR}/Cobranca/CCOBEEncaminhamento"
)

URL_ENCAMINHAMENTO_LIST = (
    f"{BASE_SIOR}/Cobranca/CCOBEEncaminhamento/List"
)

EQUIPES_DISPONIVEIS = [2, 1, 3, 4, 5, 6, 7, 8]
DEFAULT_EQUIPES = [2, 1, 3, 4, 5]
DEFAULT_PAGE_SIZE = 10000

COLUNAS_PRIORIDADE = [
    "DevedorIdentificacao",
    "QtdeAutos",
    "ValorTotal",
    "EquipeNome",
]

COLUNAS_LOG = [
    "DataHora",
    "Mensagem",
]

LogFn = Optional[Callable[[str], None]]


# ==========================================================
# HELPERS
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
        or "gov.br" in texto and "login" in texto.lower()
    )


def normalizar_equipes(
    codigos_equipes: Optional[List[int]] = None,
) -> List[int]:
    """
    Normaliza a lista de equipes.

    Mantém por padrão as equipes 2, 1, 3, 4 e 5.
    Não trava a lista em 1..5, permitindo acrescentar outras equipes futuramente.
    """

    if not codigos_equipes:
        return list(DEFAULT_EQUIPES)

    equipes = []

    for item in codigos_equipes:
        try:
            equipe = int(item)
        except Exception:
            raise ValueError(
                f"Equipe inválida: {item}"
            )

        if equipe <= 0:
            raise ValueError(
                f"Equipe inválida: {equipe}. Use apenas números positivos."
            )

        if equipe not in equipes:
            equipes.append(equipe)

    if not equipes:
        raise ValueError(
            "Selecione ao menos uma equipe para executar a varredura."
        )

    return equipes


def url_tela_encaminhamento(
    codigos_equipes: Optional[List[int]] = None,
    page_size: int = DEFAULT_PAGE_SIZE,
) -> str:
    equipes = normalizar_equipes(
        codigos_equipes
    )

    params = []

    for equipe in equipes:
        params.append(
            (
                "EquipeSelecionada",
                str(equipe),
            )
        )

    params.extend(
        [
            (
                "Bind",
                "true",
            ),
            (
                "Page",
                "1",
            ),
            (
                "PageSize",
                str(page_size),
            ),
        ]
    )

    return (
        f"{URL_ENCAMINHAMENTO_PAGE}?"
        f"{urlencode(params)}"
    )


def preparar_headers_encaminhamento(
    session: requests.Session,
    codigos_equipes: Optional[List[int]] = None,
) -> None:
    referer = url_tela_encaminhamento(
        codigos_equipes
    )

    session.headers.update(
        {
            "Accept": "*/*",
            "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
            "Origin": BASE_HOST,
            "Referer": referer,
            "Host": "servicos.dnit.gov.br",
            "X-Lt-Session-Guid": "",
            "X-Requested-With": "XMLHttpRequest",
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "same-origin",
        }
    )


def inicializar_tela_encaminhamento(
    session: requests.Session,
    codigos_equipes: Optional[List[int]] = None,
    log: LogFn = None,
    timeout: int = 60,
) -> None:
    """
    Valida a sessão requests na tela real de Encaminhamento.

    A tela é aberta via Selenium no fluxo da aba, mas também fazemos
    esta validação via requests.Session para garantir que os cookies
    foram sincronizados corretamente.
    """

    equipes = normalizar_equipes(
        codigos_equipes
    )

    url = url_tela_encaminhamento(
        equipes
    )

    _log(
        log,
        "🌐 Validando sessão requests na tela de Encaminhamento SIOR..."
    )

    headers_html = {
        "Accept": (
            "text/html,application/xhtml+xml,"
            "application/xml;q=0.9,*/*;q=0.8"
        ),
        "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
        "Referer": f"{BASE_SIOR}/",
        "Host": "servicos.dnit.gov.br",
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
    }

    resp = session.get(
        url,
        headers=headers_html,
        timeout=timeout,
        allow_redirects=True,
    )

    if resp.status_code not in (200, 201, 204):
        raise RuntimeError(
            "Falha ao validar tela de Encaminhamento SIOR. "
            f"HTTP {resp.status_code}: {resp.text[:500]}"
        )

    if _sessao_expirada_texto(
        resp.text or ""
    ):
        raise RuntimeError(
            "A validação da tela de Encaminhamento retornou login/sessão expirada. "
            "Os cookies do navegador não foram sincronizados corretamente para a Session."
        )

    preparar_headers_encaminhamento(
        session,
        equipes,
    )

    _log(
        log,
        "✅ Sessão requests validada na tela de Encaminhamento."
    )


def _montar_params_listagem(
    codigos_equipes: List[int],
    page_size: int,
) -> dict:
    params = {
        "sort": "",
        "page": 1,
        "pageSize": page_size,
        "group": "",
        "filter": "",
    }

    for idx, equipe in enumerate(
        codigos_equipes
    ):
        params[
            f"equipeselecionada[{idx}]"
        ] = equipe

    params.update(
        {
            "bind": "true",
            "calledfromapi": "true",
            "calledFromApi": "true",
        }
    )

    return params


def enviar_requisicao_get(
    session: requests.Session,
    codigos_equipes: Optional[List[int]] = None,
    page_size: int = DEFAULT_PAGE_SIZE,
    log: LogFn = None,
    timeout: int = 120,
) -> pd.DataFrame:
    """
    Executa a varredura do painel de Encaminhamento SIOR.

    Retorna DataFrame com os dados combinados do endpoint:
    /sior/Cobranca/CCOBEEncaminhamento/List
    """

    inicio = datetime.now()

    equipes = normalizar_equipes(
        codigos_equipes
    )

    preparar_headers_encaminhamento(
        session,
        equipes,
    )

    _log(
        log,
        (
            "🔎 Consultando painel de Encaminhamento "
            f"para equipes: {', '.join(map(str, equipes))}..."
        )
    )

    params = _montar_params_listagem(
        codigos_equipes=equipes,
        page_size=page_size,
    )

    try:
        response = session.get(
            URL_ENCAMINHAMENTO_LIST,
            params=params,
            timeout=timeout,
        )

        if response.status_code != 200:
            raise RuntimeError(
                "Erro na requisição de Encaminhamento SIOR. "
                f"HTTP {response.status_code}: {response.text[:1000]}"
            )

        texto = response.text or ""

        if _sessao_expirada_texto(
            texto
        ):
            raise RuntimeError(
                "Sessão expirada ao consultar a listagem de Encaminhamento."
            )

        try:
            json_result = response.json()
        except Exception as ex:
            raise RuntimeError(
                f"Resposta inválida do SIOR. Não foi possível converter para JSON: {ex}"
            )

        if "Data" not in json_result:
            _log(
                log,
                "⚠ Chave 'Data' não encontrada na resposta do SIOR."
            )
            return pd.DataFrame()

        dados = []

        for bloco in json_result.get(
            "Data",
            [],
        ):
            if isinstance(
                bloco,
                list,
            ):
                dados.extend(
                    bloco
                )

            elif isinstance(
                bloco,
                dict,
            ):
                dados.append(
                    bloco
                )

        df = pd.DataFrame(
            dados
        )

        if df.empty:
            _log(
                log,
                "⚠ A varredura de Encaminhamento não retornou registros."
            )
            return df

        colunas = df.columns.tolist()

        prioridade_existente = [
            c
            for c in COLUNAS_PRIORIDADE
            if c in colunas
        ]

        outras_colunas = [
            c
            for c in colunas
            if c not in prioridade_existente
        ]

        df = df[
            prioridade_existente + outras_colunas
        ]

        duracao = (
            datetime.now() - inicio
        )

        _log(
            log,
            (
                f"✅ Varredura concluída com {len(df)} registro(s). "
                f"Tempo: {str(duracao).split('.')[0]}"
            )
        )

        return df

    except Exception as ex:
        _log(
            log,
            f"❌ Erro ao realizar a requisição de Encaminhamento: {ex}"
        )

        raise


# ==========================================================
# EXPORTAÇÃO XLSX
# ==========================================================
def _moeda_para_float(valor):
    try:
        texto = str(
            valor or ""
        )

        texto = (
            texto
            .replace("R$", "")
            .replace(" ", "")
        )

        texto = (
            texto
            .replace(".", "")
            .replace(",", ".")
        )

        return float(
            texto
        )

    except Exception:
        return 0.0


def exportar_resultado_excel(
    caminho_saida: str,
    df_resultado: pd.DataFrame,
    df_logs: pd.DataFrame,
    codigos_equipes: Optional[List[int]] = None,
) -> None:
    equipes = normalizar_equipes(
        codigos_equipes
    )

    df_resultado = (
        df_resultado.copy()
        if df_resultado is not None
        else pd.DataFrame()
    )

    df_logs = (
        df_logs.copy()
        if df_logs is not None
        else pd.DataFrame(columns=COLUNAS_LOG)
    )

    resumo_execucao = pd.DataFrame(
        [
            {
                "Campo": "Data/Hora da exportação",
                "Valor": datetime.now().strftime(
                    "%d/%m/%Y %H:%M:%S"
                ),
            },
            {
                "Campo": "Equipes",
                "Valor": ", ".join(
                    map(str, equipes)
                ),
            },
            {
                "Campo": "Total de registros",
                "Valor": len(
                    df_resultado
                ),
            },
        ]
    )

    with pd.ExcelWriter(
        caminho_saida,
        engine="openpyxl",
    ) as writer:

        resumo_execucao.to_excel(
            writer,
            sheet_name="Resumo",
            index=False,
        )

        df_resultado.to_excel(
            writer,
            sheet_name="Dados",
            index=False,
        )

        if not df_resultado.empty and "EquipeNome" in df_resultado.columns:
            df_resumo_equipe = df_resultado.copy()

            if "QtdeAutos" in df_resumo_equipe.columns:
                df_resumo_equipe["QtdeAutos"] = pd.to_numeric(
                    df_resumo_equipe["QtdeAutos"],
                    errors="coerce",
                ).fillna(0)

            if "ValorTotal" in df_resumo_equipe.columns:
                df_resumo_equipe["ValorTotal"] = (
                    df_resumo_equipe["ValorTotal"]
                    .apply(_moeda_para_float)
                )

            agg_dict = {}

            if "QtdeAutos" in df_resumo_equipe.columns:
                agg_dict["QtdeAutos"] = "sum"

            if "ValorTotal" in df_resumo_equipe.columns:
                agg_dict["ValorTotal"] = "sum"

            if agg_dict:
                resumo_equipe = (
                    df_resumo_equipe
                    .groupby("EquipeNome", dropna=False)
                    .agg(agg_dict)
                    .reset_index()
                )

                resumo_equipe.to_excel(
                    writer,
                    sheet_name="Resumo por Equipe",
                    index=False,
                )

        df_logs.to_excel(
            writer,
            sheet_name="Logs",
            index=False,
        )

        for sheet in writer.sheets.values():
            for column_cells in sheet.columns:
                max_length = 0
                column_letter = column_cells[0].column_letter

                for cell in column_cells:
                    try:
                        max_length = max(
                            max_length,
                            len(str(cell.value or "")),
                        )
                    except Exception:
                        pass

                sheet.column_dimensions[
                    column_letter
                ].width = min(
                    max_length + 2,
                    80,
                )

