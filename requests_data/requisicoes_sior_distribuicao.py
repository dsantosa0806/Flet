# ==========================================================
# REQUISIÇÕES SIOR - DISTRIBUIÇÃO AUTOMÁTICA DE PROCESSOS
# ==========================================================
import math
import re
import time
from datetime import datetime
from typing import Callable, Optional, List, Dict, Any

import pandas as pd
import requests


# ==========================================================
# CONSTANTES
# ==========================================================
BASE_HOST = "https://servicos.dnit.gov.br"
BASE_SIOR = f"{BASE_HOST}/sior"

URL_DISTRIBUICAO_PAGE = (
    f"{BASE_SIOR}/Cobranca/SupervisaoSapiensDistribuicao"
    "?EquipeSelecionada={equipe_id}"
)

URL_LISTA_TECNICOS = (
    f"{BASE_SIOR}/Cobranca/SupervisaoSapiensDistribuicao/ListaTecnicos"
)

URL_LIST_DISTRIBUICAO = (
    f"{BASE_SIOR}/Cobranca/SupervisaoSapiensDistribuicao/List"
)

URL_DISTRIBUIR = (
    f"{BASE_SIOR}/Cobranca/SupervisaoSapiensDistribuicao/Distribuir"
)

CODIGO_FASE_APTA_DISTRIBUICAO = 32
FASE_APTA_DISTRIBUICAO = "Equipe Cadastro Sapiens"

FASE_ANALISE = "Análise Sapiens"
FASE_CONFERENCIA = "Conferência Sapiens"

TAMANHO_LOTE_DISTRIBUICAO = 1

LogFn = Optional[Callable[[str], None]]


COLUNAS_PLANO = [
    "OrdemTecnico",
    "AnalisadorId",
    "AnalisadorNome",
    "ConferidorId",
    "ConferidorNome",

    "MetaPainel",
    "AtualPainelAnalisador",
    "AtualPainelConferidor",
    "AtualPainelConsiderado",
    "QuantidadeDistribuirTecnico",

    "NumeroAuto",
    "DataConstituicao",
    "DataConstituicaoOrdenacaoDevedor",
    "ValorOriginal",
    "DevedorNumeroInscricao",
    "DevedorIdentificacao",
    "Fase",
    "CodigoFase",
    "CobrancaCodigoProcesso",
    "CodigoInfracao",
    "KeyDistribuicao",
    "RowVersionDistribuicao",
    "QuebraDevedor",
    "DevedorDistribuidoMaisDeUmTecnico",
    "QtdAutosDevedorNoPlano",
    "QtdAutosDevedorPorTecnico",
    "ObservacaoDistribuicao",
    "StatusPlanejamento",
    "PodeExecutar",
]


COLUNAS_LOG_REQUEST = [
    "DataHora",
    "Lote",
    "NumeroAuto",
    "DevedorNumeroInscricao",
    "DevedorIdentificacao",
    "ValorOriginal",
    "AnalisadorId",
    "AnalisadorNome",
    "ConferidorId",
    "ConferidorNome",
    "KeyDistribuicao",
    "RowVersionDistribuicao",
    "Status",
    "Mensagem",
    "HTTPStatus",
]


# ==========================================================
# HELPERS
# ==========================================================
def _log(log: LogFn, mensagem: str) -> None:
    if log:
        log(mensagem)


def _normalizar_texto(valor: Any) -> str:
    return str(valor or "").strip()


def _normalizar_comparacao(valor: Any) -> str:
    return (
        str(valor or "")
        .strip()
        .upper()
        .replace("Á", "A")
        .replace("À", "A")
        .replace("Â", "A")
        .replace("Ã", "A")
        .replace("É", "E")
        .replace("Ê", "E")
        .replace("Í", "I")
        .replace("Ó", "O")
        .replace("Ô", "O")
        .replace("Õ", "O")
        .replace("Ú", "U")
        .replace("Ç", "C")
    )


def _to_str_id(valor: Any) -> str:
    if valor is None:
        return ""

    try:
        if pd.isna(valor):
            return ""
    except Exception:
        pass

    texto = str(valor).strip()

    if re.fullmatch(r"\d+\.0", texto):
        texto = texto[:-2]

    return texto


def _to_int(valor: Any, default: int = 0) -> int:
    try:
        if valor is None:
            return default

        if pd.isna(valor):
            return default
    except Exception:
        pass

    try:
        return int(float(str(valor).strip()))
    except Exception:
        return default


def _primeiro_campo(row: Dict[str, Any], campos: List[str]) -> str:
    for campo in campos:
        if campo in row:
            valor = row.get(campo)

            try:
                if pd.isna(valor):
                    continue
            except Exception:
                pass

            texto = _to_str_id(valor)

            if texto:
                return texto

    return ""


def _sessao_expirada_texto(texto: str) -> bool:
    texto = texto or ""

    return (
        "A sua sessão expirou" in texto
        or "Account/Login" in texto
        or "/Account/Login" in texto
        or "Entrar com gov.br" in texto
    )


def _chunks(lista: List[Dict[str, Any]], tamanho: int):
    for i in range(0, len(lista), tamanho):
        yield lista[i:i + tamanho]


def _extrair_data(valor: Any) -> str:
    if isinstance(valor, dict):
        return valor.get("DateString", "")

    return valor or ""


def _obter_data_constituicao(row: Dict[str, Any]) -> Any:
    """
    Garante uma leitura única da DataConstituicao, mesmo quando o SIOR
    retorna o mesmo dado com nomes/formatações diferentes.
    """
    if not isinstance(row, dict):
        return ""

    campos_possiveis = [
        "DataConstituicao",
        "DataConstituicaoDefinitiva",
        "DataConstituicaoCredito",
        "DataConstituicaoFormatada",
        "DataConstituicaoString",
        "DataConstituicaoStr",
        "Constituicao",
        "DataConstituicaoDefinitivaFormatada",
    ]

    for campo in campos_possiveis:
        if campo not in row:
            continue

        valor = row.get(campo)

        try:
            if pd.isna(valor):
                continue
        except Exception:
            pass

        texto = str(_extrair_data(valor) or "").strip()

        if texto:
            return texto

    return ""


def _obter_valor_original(row: Dict[str, Any]) -> Any:
    """
    Lê o valor original do auto retornado pela grid do SIOR, aceitando
    possíveis nomes equivalentes usados em diferentes telas/responses.
    """
    if not isinstance(row, dict):
        return ""

    campos_possiveis = [
        "ValorOriginal",
        "ValorOriginalFormatado",
        "ValorMulta",
        "ValorMultaFormatado",
        "Valor",
        "ValorFormatado",
    ]

    for campo in campos_possiveis:
        if campo not in row:
            continue

        valor = row.get(campo)

        try:
            if pd.isna(valor):
                continue
        except Exception:
            pass

        texto = str(valor or "").strip()

        if texto:
            return texto

    return ""


def _normalizar_registro_valor_original(row: Dict[str, Any]) -> Dict[str, Any]:
    """
    Mantém o campo ValorOriginal presente no registro, quando a response
    retornar o valor com outro nome equivalente.
    """
    if not isinstance(row, dict):
        return row

    if not str(row.get("ValorOriginal", "") or "").strip():
        row["ValorOriginal"] = _obter_valor_original(row)

    return row


def _normalizar_registro_data_constituicao(row: Dict[str, Any]) -> Dict[str, Any]:
    """
    Mantém o campo DataConstituicao presente no registro retornado pela request.
    Isso facilita a ordenação posterior por devedor e também a auditoria no XLSX.
    """
    if not isinstance(row, dict):
        return row

    if not str(_extrair_data(row.get("DataConstituicao", "")) or "").strip():
        row["DataConstituicao"] = _obter_data_constituicao(row)
    else:
        row["DataConstituicao"] = _extrair_data(row.get("DataConstituicao"))

    return row


def _parse_data_constituicao_para_ordenacao(valor: Any) -> pd.Timestamp:
    """
    Converte a DataConstituicao para ordenação sem gerar warning do pandas.

    Regra:
    - formatos brasileiros são lidos com formato explícito;
    - formatos ISO/SQL são lidos com dayfirst=False;
    - datas inválidas/ausentes vão para o final da fila.
    """
    texto = str(_extrair_data(valor) or "").strip()

    if not texto:
        return pd.Timestamp.max

    texto = (
        texto.replace("T", " ")
        .replace("Z", "")
        .strip()
    )

    # Remove frações de segundo comuns em respostas ISO.
    texto = re.sub(r"\.\d+$", "", texto)

    formatos = [
        "%d/%m/%Y %H:%M:%S",
        "%d/%m/%Y %H:%M",
        "%d/%m/%Y",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M",
        "%Y-%m-%d",
        "%d-%m-%Y %H:%M:%S",
        "%d-%m-%Y %H:%M",
        "%d-%m-%Y",
        "%Y/%m/%d %H:%M:%S",
        "%Y/%m/%d %H:%M",
        "%Y/%m/%d",
    ]

    for formato in formatos:
        try:
            data = pd.to_datetime(
                texto,
                format=formato,
                errors="coerce",
            )

            if not pd.isna(data):
                return data

        except Exception:
            continue

    try:
        data = pd.to_datetime(
            texto,
            errors="coerce",
        )

        if not pd.isna(data):
            return data

    except Exception:
        pass

    return pd.Timestamp.max


def _formatar_data_ordenacao(valor: Any) -> str:
    """
    Formata timestamps usados na ordenação para auditoria no XLSX.
    """
    try:
        data = _parse_data_constituicao_para_ordenacao(valor)

        if pd.isna(data) or data == pd.Timestamp.max:
            return ""

        return data.strftime("%d/%m/%Y")

    except Exception:
        return ""


# ==========================================================
# HEADERS / INICIALIZAÇÃO
# ==========================================================
def preparar_headers_distribuicao(
    session: requests.Session,
    equipe_id: str,
) -> None:
    referer = URL_DISTRIBUICAO_PAGE.format(
        equipe_id=equipe_id
    )

    session.headers.update(
        {
            "Accept": "*/*",
            "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
            "Origin": BASE_HOST,
            "Referer": referer,
            "Host": "servicos.dnit.gov.br",
            "X-Requested-With": "XMLHttpRequest",
            "X-Lt-Session-Guid": "",
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "same-origin",
        }
    )


def inicializar_tela_distribuicao(
    session: requests.Session,
    equipe_id: str,
    log: LogFn = None,
    timeout: int = 60,
) -> None:
    preparar_headers_distribuicao(
        session,
        equipe_id,
    )

    url = URL_DISTRIBUICAO_PAGE.format(
        equipe_id=equipe_id
    )

    _log(
        log,
        f"🌐 Inicializando tela de Distribuição SIOR para equipe {equipe_id}..."
    )

    resp = session.get(
        url,
        timeout=timeout,
        allow_redirects=True,
    )

    if resp.status_code not in (200, 201, 204):
        raise RuntimeError(
            f"Falha ao inicializar tela de distribuição. "
            f"HTTP {resp.status_code}: {resp.text[:500]}"
        )

    if _sessao_expirada_texto(resp.text or ""):
        raise RuntimeError(
            "Sessão SIOR expirada ao inicializar a tela de distribuição."
        )

    preparar_headers_distribuicao(
        session,
        equipe_id,
    )

    _log(
        log,
        "✅ Tela de Distribuição inicializada."
    )


# ==========================================================
# REQUESTS BASE
# ==========================================================
def listar_tecnicos_distribuicao(
    equipe_id: str,
    session: requests.Session,
    log: LogFn = None,
    timeout: int = 60,
) -> List[Dict[str, Any]]:
    preparar_headers_distribuicao(
        session,
        equipe_id,
    )

    params = {
        "equipeID": equipe_id,
        "_": int(time.time() * 1000),
    }

    _log(
        log,
        "👥 Consultando técnicos da equipe..."
    )

    resp = session.get(
        URL_LISTA_TECNICOS,
        params=params,
        timeout=timeout,
    )

    if resp.status_code != 200:
        raise RuntimeError(
            f"Falha ao consultar técnicos. "
            f"HTTP {resp.status_code}: {resp.text[:500]}"
        )

    if _sessao_expirada_texto(resp.text or ""):
        raise RuntimeError(
            "Sessão SIOR expirada ao consultar técnicos."
        )

    dados = resp.json()

    tecnicos = [
        item
        for item in dados
        if not item.get("Disabled", False)
    ]

    _log(
        log,
        f"✅ Técnicos localizados: {len(tecnicos)}."
    )

    return tecnicos


def get_acompanhamento_distribuicao_sior(
    equipe_id: str,
    session: requests.Session,
    fase: int | None = None,
    page_size: int = 1000,
    log: LogFn = None,
    timeout: int = 60,
) -> List[Dict[str, Any]]:
    """
    Consulta a própria grid de distribuição:

    /Cobranca/SupervisaoSapiensDistribuicao/List

    Esta request retorna:
    - RowVersionConverted
    - CobrancaCodigoProcesso
    - CodigoInfracao
    - CodigoFase
    - Fase
    - TecnicoAtualAnalise
    - CodigoTecnicoAtualAnalise
    - TecnicoAtualConferencia
    - CodigoTecnicoAtualConferencia
    - DataConstituicao
    - ValorOriginal

    Observação:
    - O campo DataConstituicao é normalizado em todos os registros retornados.
    - Caso o SIOR retorne a data com outro nome equivalente, a função converte para DataConstituicao.
    - Caso o SIOR retorne o valor com outro nome equivalente, a função converte para ValorOriginal.
    """

    preparar_headers_distribuicao(
        session,
        equipe_id,
    )

    page = 1
    todos = []

    descricao_fase = (
        f"fase {fase}"
        if fase is not None
        else "todas as fases"
    )

    _log(
        log,
        f"📥 Consultando grid de distribuição ({descricao_fase})..."
    )

    while True:
        params = {
            "sort": "",
            "page": page,
            "pageSize": page_size,
            "group": "",
            "filter": "",
            "equipeselecionada": equipe_id,
            "calledfromapi": "true",
            "calledFromApi": "true",
            "_": int(time.time() * 1000),
        }

        if fase is not None:
            params["fase"] = fase

        resp = session.get(
            URL_LIST_DISTRIBUICAO,
            params=params,
            timeout=timeout,
        )

        if resp.status_code != 200:
            raise RuntimeError(
                f"Falha ao consultar grid de distribuição. "
                f"Página {page}. HTTP {resp.status_code}: {resp.text[:500]}"
            )

        if _sessao_expirada_texto(resp.text or ""):
            raise RuntimeError(
                "Sessão SIOR expirada ao consultar grid de distribuição."
            )

        dados_json = resp.json()
        dados = dados_json.get("Data", [])

        dados = [
            _normalizar_registro_valor_original(
                _normalizar_registro_data_constituicao(item)
            )
            for item in dados
        ]

        todos.extend(dados)

        total = dados_json.get(
            "Total",
            len(todos),
        )

        _log(
            log,
            f"   Página {page}: {len(dados)} registro(s). Total acumulado: {len(todos)}/{total}."
        )

        if len(todos) >= total:
            break

        page += 1

    _log(
        log,
        f"✅ Grid de distribuição carregada: {len(todos)} registro(s)."
    )

    return todos


def listar_processos_aptos_distribuicao(
    equipe_id: str,
    session: requests.Session,
    log: LogFn = None,
) -> List[Dict[str, Any]]:
    """
    Consulta diretamente a fase 32, que é a fase apta para distribuição:
    Equipe Cadastro Sapiens.
    """

    return get_acompanhamento_distribuicao_sior(
        equipe_id=equipe_id,
        session=session,
        fase=CODIGO_FASE_APTA_DISTRIBUICAO,
        page_size=1000,
        log=log,
    )


# ==========================================================
# NORMALIZAÇÃO DO PAINEL
# ==========================================================
def normalizar_dataframe_painel(
    dados: List[Dict[str, Any]],
) -> pd.DataFrame:
    df = pd.DataFrame(
        dados or []
    )

    if df.empty:
        return pd.DataFrame()

    if "DataConstituicao" not in df.columns:
        df["DataConstituicao"] = ""

    df["DataConstituicao"] = df.apply(
        lambda row: _obter_data_constituicao(row.to_dict()),
        axis=1,
    )

    df["DataConstituicaoFormatada"] = df["DataConstituicao"].apply(
        _extrair_data
    )

    for coluna in [
        "RowVersionConverted",
        "CodigoInfracao",
        "CodigoFase",
        "EquipeCodigoProcesso",
        "CobrancaCodigoProcesso",
        "CodigoTecnicoAtualAnalise",
        "CodigoTecnicoAtualConferencia",
    ]:
        if coluna in df.columns:
            df[coluna] = df[coluna].apply(
                _to_str_id
            )

    return df


def filtrar_aptos_distribuicao(
    dados: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    registros = []

    for row in dados or []:
        codigo_fase = _to_int(
            row.get("CodigoFase"),
            default=-1,
        )

        fase_texto = _normalizar_comparacao(
            row.get("Fase", "")
        )

        apto_por_codigo = (
            codigo_fase == CODIGO_FASE_APTA_DISTRIBUICAO
        )

        apto_por_texto = (
            _normalizar_comparacao(FASE_APTA_DISTRIBUICAO)
            in fase_texto
        )

        if apto_por_codigo or apto_por_texto:
            registros.append(
                row
            )

    return registros


# ==========================================================
# INDICADORES / QUANTITATIVOS
# ==========================================================
def calcular_quantitativos_tecnicos(
    dados_painel: List[Dict[str, Any]],
) -> Dict[str, Dict[str, int]]:
    df = normalizar_dataframe_painel(
        dados_painel
    )

    if df.empty:
        return {}

    resultado = {}

    nomes = set()

    if "TecnicoAtualAnalise" in df.columns:
        nomes.update(
            df["TecnicoAtualAnalise"]
            .dropna()
            .astype(str)
            .str.strip()
            .tolist()
        )

    if "TecnicoAtualConferencia" in df.columns:
        nomes.update(
            df["TecnicoAtualConferencia"]
            .dropna()
            .astype(str)
            .str.strip()
            .tolist()
        )

    for nome in nomes:
        if not nome:
            continue

        qtd_analise = 0
        qtd_conferencia = 0

        if all(c in df.columns for c in ["TecnicoAtualAnalise", "Fase"]):
            qtd_analise = int(
                (
                    (df["TecnicoAtualAnalise"].astype(str).str.strip() == nome)
                    & (
                        df["Fase"]
                        .astype(str)
                        .map(_normalizar_comparacao)
                        .str.contains(_normalizar_comparacao(FASE_ANALISE), na=False)
                    )
                ).sum()
            )

        if all(c in df.columns for c in ["TecnicoAtualConferencia", "Fase"]):
            qtd_conferencia = int(
                (
                    (df["TecnicoAtualConferencia"].astype(str).str.strip() == nome)
                    & (
                        df["Fase"]
                        .astype(str)
                        .map(_normalizar_comparacao)
                        .str.contains(_normalizar_comparacao(FASE_CONFERENCIA), na=False)
                    )
                ).sum()
            )

        resultado[nome] = {
            "analise": qtd_analise,
            "conferencia": qtd_conferencia,
            "total": qtd_analise + qtd_conferencia,
        }

    return resultado


def montar_df_quantitativos(
    dados_painel: List[Dict[str, Any]],
    tecnicos: List[Dict[str, Any]] | None = None,
) -> pd.DataFrame:
    quantitativos = calcular_quantitativos_tecnicos(
        dados_painel
    )

    linhas = []

    tecnicos = tecnicos or []

    nomes_tecnicos_lista = [
        str(t.get("Text", "")).strip()
        for t in tecnicos
        if str(t.get("Text", "")).strip()
    ]

    nomes = sorted(
        set(nomes_tecnicos_lista)
        | set(quantitativos.keys())
    )

    for nome in nomes:
        qtd = quantitativos.get(
            nome,
            {
                "analise": 0,
                "conferencia": 0,
                "total": 0,
            },
        )

        codigo = ""

        for tecnico in tecnicos:
            if str(tecnico.get("Text", "")).strip() == nome:
                codigo = tecnico.get("Value", "")
                break

        linhas.append(
            {
                "CodigoTecnico": codigo,
                "Tecnico": nome,
                "QtdAnaliseSapiens": qtd.get("analise", 0),
                "QtdConferenciaSapiens": qtd.get("conferencia", 0),
                "TotalAnaliseConferencia": qtd.get("total", 0),
            }
        )

    return pd.DataFrame(
        linhas
    )


def montar_comparativo_quantitativos(
    df_antes: pd.DataFrame,
    df_depois: pd.DataFrame,
) -> pd.DataFrame:
    if df_antes is None:
        df_antes = pd.DataFrame()

    if df_depois is None:
        df_depois = pd.DataFrame()

    colunas = [
        "CodigoTecnico",
        "Tecnico",
        "QtdAnaliseSapiens",
        "QtdConferenciaSapiens",
        "TotalAnaliseConferencia",
    ]

    for coluna in colunas:
        if coluna not in df_antes.columns:
            df_antes[coluna] = ""

        if coluna not in df_depois.columns:
            df_depois[coluna] = ""

    antes = df_antes[colunas].copy()
    depois = df_depois[colunas].copy()

    antes.rename(
        columns={
            "QtdAnaliseSapiens": "AnaliseAntes",
            "QtdConferenciaSapiens": "ConferenciaAntes",
            "TotalAnaliseConferencia": "TotalAntes",
        },
        inplace=True,
    )

    depois.rename(
        columns={
            "QtdAnaliseSapiens": "AnaliseDepois",
            "QtdConferenciaSapiens": "ConferenciaDepois",
            "TotalAnaliseConferencia": "TotalDepois",
        },
        inplace=True,
    )

    comparativo = antes.merge(
        depois,
        on=[
            "CodigoTecnico",
            "Tecnico",
        ],
        how="outer",
    ).fillna(0)

    for coluna in [
        "AnaliseAntes",
        "ConferenciaAntes",
        "TotalAntes",
        "AnaliseDepois",
        "ConferenciaDepois",
        "TotalDepois",
    ]:
        comparativo[coluna] = comparativo[coluna].astype(int)

    comparativo["DeltaAnalise"] = (
        comparativo["AnaliseDepois"]
        - comparativo["AnaliseAntes"]
    )

    comparativo["DeltaConferencia"] = (
        comparativo["ConferenciaDepois"]
        - comparativo["ConferenciaAntes"]
    )

    comparativo["DeltaTotal"] = (
        comparativo["TotalDepois"]
        - comparativo["TotalAntes"]
    )

    return comparativo.sort_values(
        "Tecnico"
    )


# ==========================================================
# PLANO DE DISTRIBUIÇÃO
# ==========================================================
def gerar_plano_distribuicao(
    dados_processos_aptos: List[Dict[str, Any]],
    metas_tecnicos: List[Dict[str, Any]],
    log: LogFn = None,
) -> pd.DataFrame:
    """
    Regra de distribuição:

    - O campo quantidade representa a QUANTIDADE QUE O USUÁRIO QUER DISTRIBUIR
      para o par analisador/conferidor, limitada a 200 pela interface.
    - Essa quantidade não é reduzida pelo quantitativo atual do painel.
    - Por padrão, o analisador e o conferidor são o mesmo técnico, mas a tela permite edição.
    - Distribui os autos do mesmo devedor em sequência.
    - Se o devedor possuir mais autos do que a capacidade restante do técnico,
      distribui até a capacidade e envia o restante para o próximo técnico.
    """

    metas_validas = []

    for item in metas_tecnicos or []:
        try:
            meta_painel = int(
                item.get(
                    "meta_painel",
                    item.get("quantidade", 0)
                )
            )
        except Exception:
            meta_painel = 0

        try:
            quantidade_distribuir = int(
                item.get(
                    "quantidade_distribuir",
                    item.get("quantidade", 0)
                )
            )
        except Exception:
            quantidade_distribuir = 0

        if meta_painel <= 0:
            continue

        if quantidade_distribuir <= 0:
            continue

        analisador_id = _to_str_id(
            item.get("analisador_id")
        )

        conferidor_id = _to_str_id(
            item.get("conferidor_id")
        )

        if not analisador_id or not conferidor_id:
            continue

        metas_validas.append(
            {
                "analisador_id": analisador_id,
                "analisador_nome": _normalizar_texto(
                    item.get("analisador_nome")
                ),
                "conferidor_id": conferidor_id,
                "conferidor_nome": _normalizar_texto(
                    item.get("conferidor_nome")
                ),

                "meta_painel": meta_painel,
                "atual_painel_analisador": int(
                    item.get("atual_painel_analisador", 0)
                ),
                "atual_painel_conferidor": int(
                    item.get("atual_painel_conferidor", 0)
                ),
                "atual_painel_considerado": int(
                    item.get("atual_painel_considerado", 0)
                ),
                "quantidade_distribuir": quantidade_distribuir,
            }
        )

    if not metas_validas:
        raise ValueError(
            "Nenhum técnico foi selecionado com quantidade válida para distribuição. "
            "Informe quantidade maior que zero para ao menos um analisador/conferidor."
        )

    registros_aptos = filtrar_aptos_distribuicao(
        dados_processos_aptos
    )

    df_base = pd.DataFrame(
        registros_aptos
    )

    if df_base.empty:
        return pd.DataFrame(
            columns=COLUNAS_PLANO
        )

    registros = []

    for _, row in df_base.iterrows():
        item = row.to_dict()

        key_distribuicao = _primeiro_campo(
            item,
            [
                "CobrancaCodigoProcesso",
                "CodigoInfracao",
                "CodigoProcessoCobranca",
                "CodigoProcesso",
                "Id",
            ],
        )

        row_version = _primeiro_campo(
            item,
            [
                "RowVersionConverted",
                "RowVersion",
                "rowVersion",
                "RowVersionString",
            ],
        )

        devedor_numero = _primeiro_campo(
            item,
            [
                "DevedorNumeroInscricao",
                "DevedorDocumento",
                "CpfCnpj",
            ],
        )

        devedor_identificacao = _normalizar_texto(
            item.get("DevedorIdentificacao")
            or item.get("Devedor")
            or devedor_numero
            or "DEVEDOR NÃO IDENTIFICADO"
        )

        devedor_chave = (
            devedor_numero
            or devedor_identificacao
            or "DEVEDOR NÃO IDENTIFICADO"
        )

        data_constituicao = _obter_data_constituicao(item)
        data_constituicao_ordenacao = _parse_data_constituicao_para_ordenacao(
            data_constituicao
        )

        registros.append(
            {
                **item,
                "DataConstituicao": data_constituicao,
                "_DataConstituicaoDistribuicao": data_constituicao,
                "_DataConstituicaoOrdenacao": data_constituicao_ordenacao,
                "_DevedorChave": devedor_chave,
                "_KeyDistribuicao": key_distribuicao,
                "_RowVersionDistribuicao": row_version,
                "_DevedorNumeroInscricao": devedor_numero,
                "_DevedorIdentificacao": devedor_identificacao,
            }
        )

    df_base = pd.DataFrame(
        registros
    )

    df_base["_QtdDevedor"] = df_base.groupby(
        "_DevedorChave"
    )["_DevedorChave"].transform("size")

    df_base["_DataConstituicaoOrdenacao"] = df_base[
        "_DataConstituicaoOrdenacao"
    ].apply(
        _parse_data_constituicao_para_ordenacao
    )

    # ======================================================
    # REGRA DE NEGÓCIO - PRIORIZAÇÃO POR DATA MAIS ANTIGA
    # ======================================================
    # Antes de aplicar a regra por devedor já existente, identificamos
    # a menor DataConstituicao de cada devedor. O devedor que possuir
    # o auto mais antigo fica primeiro na fila de distribuição.
    # A regra de manter os autos do mesmo devedor juntos permanece igual.
    df_base["_DataConstituicaoDevedorMin"] = df_base.groupby(
        "_DevedorChave"
    )["_DataConstituicaoOrdenacao"].transform("min")

    ordenadores = [
        "_DataConstituicaoDevedorMin",
        "_QtdDevedor",
        "_DevedorChave",
        "_DataConstituicaoOrdenacao",
    ]

    ascendentes = [
        True,
        False,
        True,
        True,
    ]

    if "NumeroAuto" in df_base.columns:
        ordenadores.append(
            "NumeroAuto"
        )

        ascendentes.append(
            True
        )

    df_base = df_base.sort_values(
        ordenadores,
        ascending=ascendentes,
    )

    _log(
        log,
        "📅 Devedores priorizados pela DataConstituicao mais antiga antes da distribuição."
    )

    tecnico_idx = 0
    usado_tecnico = 0
    plano = []

    grupos = df_base.groupby(
        "_DevedorChave",
        sort=False,
    )

    for _, grupo in grupos:
        linhas_devedor = grupo.to_dict(
            orient="records"
        )

        pos = 0
        total_devedor = len(
            linhas_devedor
        )

        while pos < total_devedor:
            if tecnico_idx >= len(metas_validas):
                for row in linhas_devedor[pos:]:
                    plano.append(
                        _montar_linha_plano(
                            row=row,
                            meta=None,
                            ordem_tecnico=None,
                            quebra_devedor="Não",
                            status="SEM_CAPACIDADE",
                            pode_executar=False,
                        )
                    )

                break

            meta = metas_validas[
                tecnico_idx
            ]

            capacidade_restante = (
                meta["quantidade_distribuir"]
                - usado_tecnico
            )

            if capacidade_restante <= 0:
                tecnico_idx += 1
                usado_tecnico = 0
                continue

            qtd_pegar = min(
                capacidade_restante,
                total_devedor - pos,
            )

            houve_quebra = (
                pos > 0
                or qtd_pegar < total_devedor
            )

            for row in linhas_devedor[pos:pos + qtd_pegar]:
                key_ok = bool(
                    row.get("_KeyDistribuicao")
                )

                row_version_ok = bool(
                    row.get("_RowVersionDistribuicao")
                )

                pode_executar = (
                    key_ok
                    and row_version_ok
                )

                status = (
                    "PLANEJADO"
                    if pode_executar
                    else "SEM_KEY_OU_ROWVERSION"
                )

                plano.append(
                    _montar_linha_plano(
                        row=row,
                        meta=meta,
                        ordem_tecnico=tecnico_idx + 1,
                        quebra_devedor="Sim" if houve_quebra else "Não",
                        status=status,
                        pode_executar=pode_executar,
                    )
                )

            pos += qtd_pegar
            usado_tecnico += qtd_pegar

            if usado_tecnico >= meta["quantidade_distribuir"]:
                tecnico_idx += 1
                usado_tecnico = 0

    df_plano = pd.DataFrame(
        plano,
        columns=COLUNAS_PLANO,
    )

    if not df_plano.empty:
        chave_devedor = df_plano["DevedorNumeroInscricao"].astype(str).str.strip()

        chave_devedor = chave_devedor.where(
            chave_devedor != "",
            df_plano["DevedorIdentificacao"].astype(str).str.strip(),
        )

        df_plano["_ChaveDevedorExport"] = chave_devedor

        df_plano["_ParTecnicoExport"] = (
            df_plano["AnalisadorId"].astype(str)
            + "|"
            + df_plano["ConferidorId"].astype(str)
        )

        df_plano["QtdAutosDevedorNoPlano"] = (
            df_plano.groupby("_ChaveDevedorExport")["NumeroAuto"]
            .transform("count")
            .astype(int)
        )

        df_plano["QtdAutosDevedorPorTecnico"] = (
            df_plano.groupby(["_ChaveDevedorExport", "_ParTecnicoExport"])["NumeroAuto"]
            .transform("count")
            .astype(int)
        )

        qtd_pares_por_devedor = (
            df_plano.groupby("_ChaveDevedorExport")["_ParTecnicoExport"]
            .transform("nunique")
            .astype(int)
        )

        df_plano["DevedorDistribuidoMaisDeUmTecnico"] = qtd_pares_por_devedor.map(
            lambda qtd: "Sim" if qtd > 1 else "Não"
        )

        df_plano.loc[
            df_plano["DevedorDistribuidoMaisDeUmTecnico"] == "Sim",
            "QuebraDevedor",
        ] = "Sim"

        df_plano["ObservacaoDistribuicao"] = df_plano.apply(
            lambda row: (
                "Devedor dividido entre técnicos por limite da quantidade informada/capacidade."
                if row.get("DevedorDistribuidoMaisDeUmTecnico") == "Sim"
                else (
                    "Auto mantido no mesmo analisador/conferidor do devedor."
                    if row.get("PodeExecutar") is True or row.get("PodeExecutar") == True
                    else "Auto não executável; verificar status de planejamento."
                )
            ),
            axis=1,
        )

        df_plano.drop(
            columns=["_ChaveDevedorExport", "_ParTecnicoExport"],
            inplace=True,
            errors="ignore",
        )

    _log(
        log,
        f"✅ Distribuição planejada automaticamente: {len(df_plano)} processo(s)."
    )

    return df_plano


def _montar_linha_plano(
    row: Dict[str, Any],
    meta: Optional[Dict[str, Any]],
    ordem_tecnico: Optional[int],
    quebra_devedor: str,
    status: str,
    pode_executar: bool,
) -> Dict[str, Any]:
    return {
        "OrdemTecnico": ordem_tecnico or "",
        "AnalisadorId": meta.get("analisador_id", "") if meta else "",
        "AnalisadorNome": meta.get("analisador_nome", "") if meta else "",
        "ConferidorId": meta.get("conferidor_id", "") if meta else "",
        "ConferidorNome": meta.get("conferidor_nome", "") if meta else "",

        "MetaPainel": meta.get("meta_painel", "") if meta else "",  # compatibilidade: representa a quantidade informada
        "AtualPainelAnalisador": meta.get("atual_painel_analisador", "") if meta else "",
        "AtualPainelConferidor": meta.get("atual_painel_conferidor", "") if meta else "",
        "AtualPainelConsiderado": meta.get("atual_painel_considerado", "") if meta else "",
        "QuantidadeDistribuirTecnico": meta.get("quantidade_distribuir", "") if meta else "",

        "NumeroAuto": row.get("NumeroAuto", ""),
        "DataConstituicao": row.get("_DataConstituicaoDistribuicao", row.get("DataConstituicao", "")),
        "DataConstituicaoOrdenacaoDevedor": _formatar_data_ordenacao(
            row.get("_DataConstituicaoDevedorMin", "")
        ),
        "ValorOriginal": _obter_valor_original(row),
        "DevedorNumeroInscricao": row.get("_DevedorNumeroInscricao", ""),
        "DevedorIdentificacao": row.get("_DevedorIdentificacao", ""),
        "Fase": row.get("Fase", ""),
        "CodigoFase": row.get("CodigoFase", ""),
        "CobrancaCodigoProcesso": row.get("CobrancaCodigoProcesso", ""),
        "CodigoInfracao": row.get("CodigoInfracao", ""),
        "KeyDistribuicao": row.get("_KeyDistribuicao", ""),
        "RowVersionDistribuicao": row.get("_RowVersionDistribuicao", ""),
        "QuebraDevedor": quebra_devedor,
        "DevedorDistribuidoMaisDeUmTecnico": "",
        "QtdAutosDevedorNoPlano": "",
        "QtdAutosDevedorPorTecnico": "",
        "ObservacaoDistribuicao": "",
        "StatusPlanejamento": status,
        "PodeExecutar": bool(pode_executar),
    }


# ==========================================================
# EXECUÇÃO DA DISTRIBUIÇÃO
# ==========================================================
def _extrair_mensagem_response(dados: Dict[str, Any]) -> str:
    mensagens = []

    for action in dados.get("actions", []) or []:
        options = action.get("options", {}) or {}
        mensagem = options.get("message")

        if mensagem:
            mensagens.append(
                str(mensagem)
            )

    return " | ".join(
        mensagens
    )


def _montar_payload_distribuicao(
    registros: List[Dict[str, Any]],
) -> List[tuple]:
    payload = []

    for idx, row in enumerate(registros):
        key = _to_str_id(
            row.get("KeyDistribuicao")
        )

        row_version = _to_str_id(
            row.get("RowVersionDistribuicao")
        )

        analisador = _to_str_id(
            row.get("AnalisadorId")
        )

        conferidor = _to_str_id(
            row.get("ConferidorId")
        )

        payload.append(
            (
                f"listDistribuicao[{idx}][Key]",
                key,
            )
        )

        payload.append(
            (
                f"listDistribuicao[{idx}][Value][]",
                analisador,
            )
        )

        payload.append(
            (
                f"listDistribuicao[{idx}][Value][]",
                conferidor,
            )
        )

        payload.append(
            (
                f"listDistribuicaoRowVersion[{idx}][Key]",
                key,
            )
        )

        payload.append(
            (
                f"listDistribuicaoRowVersion[{idx}][Value]",
                row_version,
            )
        )

    return payload


def executar_distribuicao_por_plano(
    session: requests.Session,
    equipe_id: str,
    df_plano: pd.DataFrame,
    log: LogFn = None,
    tamanho_lote: int = TAMANHO_LOTE_DISTRIBUICAO,
    pausa_entre_lotes: float = 0.8,
) -> pd.DataFrame:
    """
    Executa a distribuição de forma sequencial, auto por auto.

    Observação importante:
    O endpoint /Distribuir do SIOR não lida bem com payloads contendo
    vários pares de analisador/conferidor na mesma chamada. Quando isso
    ocorre, o backend pode retornar HTTP 500 com IndexOutOfRangeException.

    Por isso, mesmo que o plano possua vários analisadores/conferidores,
    cada auto é enviado em uma request individual, sempre usando índice [0]
    no payload. A ordem do plano é preservada, mantendo a regra por devedor.
    """
    if df_plano is None or df_plano.empty:
        raise ValueError(
            "Plano de distribuição vazio."
        )

    df_exec = df_plano[
        df_plano["PodeExecutar"] == True
    ].copy()

    if df_exec.empty:
        raise ValueError(
            "Nenhum item executável no plano."
        )

    preparar_headers_distribuicao(
        session,
        equipe_id,
    )

    logs = []

    registros = df_exec.to_dict(
        orient="records"
    )

    total_processos = len(
        registros
    )

    _log(
        log,
        (
            f"🚀 Iniciando distribuição sequencial de {total_processos} processo(s). "
            "Cada auto será enviado individualmente ao SIOR."
        )
    )

    headers = {
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        "Origin": BASE_HOST,
        "Referer": URL_DISTRIBUICAO_PAGE.format(
            equipe_id=equipe_id
        ),
        "Host": "servicos.dnit.gov.br",
        "X-Lt-Session-Guid": "",
        "X-Requested-With": "XMLHttpRequest",
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "same-origin",
    }

    for numero_execucao, row in enumerate(
        registros,
        start=1,
    ):
        numero_auto = row.get(
            "NumeroAuto",
            "",
        )

        analisador_nome = row.get(
            "AnalisadorNome",
            "",
        )

        conferidor_nome = row.get(
            "ConferidorNome",
            "",
        )

        _log(
            log,
            (
                f"📤 Enviando auto {numero_execucao}/{total_processos}: "
                f"{numero_auto} → {analisador_nome} / {conferidor_nome}"
            )
        )

        # Envia sempre uma única distribuição por request.
        # Assim o payload usa listDistribuicao[0] e evita erro de índice no backend.
        payload = _montar_payload_distribuicao(
            [row]
        )

        try:
            preparar_headers_distribuicao(
                session,
                equipe_id,
            )

            resp = session.post(
                URL_DISTRIBUIR,
                headers=headers,
                data=payload,
                timeout=90,
            )

            http_status = resp.status_code

            if http_status != 200:
                mensagem = (
                    f"HTTP {http_status}: {resp.text[:500]}"
                )

                status_execucao = "ERRO"

            else:
                try:
                    dados = resp.json()
                except Exception:
                    dados = {}

                if dados.get("status") == "ok":
                    mensagem = (
                        _extrair_mensagem_response(dados)
                        or "Distribuição realizada com sucesso."
                    )

                    status_execucao = "SUCESSO"

                else:
                    mensagem = str(dados or resp.text)[:1000]
                    status_execucao = "ERRO"

        except Exception as ex:
            http_status = ""
            mensagem = str(ex)
            status_execucao = "ERRO"

        _log(
            log,
            (
                f"{'✅' if status_execucao == 'SUCESSO' else '❌'} "
                f"Auto {numero_execucao}/{total_processos}: {mensagem}"
            )
        )

        logs.append(
            {
                "DataHora": datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
                "Lote": numero_execucao,
                "NumeroAuto": row.get("NumeroAuto", ""),
                "DevedorNumeroInscricao": row.get("DevedorNumeroInscricao", ""),
                "DevedorIdentificacao": row.get("DevedorIdentificacao", ""),
                "ValorOriginal": row.get("ValorOriginal", ""),
                "AnalisadorId": row.get("AnalisadorId", ""),
                "AnalisadorNome": row.get("AnalisadorNome", ""),
                "ConferidorId": row.get("ConferidorId", ""),
                "ConferidorNome": row.get("ConferidorNome", ""),
                "KeyDistribuicao": row.get("KeyDistribuicao", ""),
                "RowVersionDistribuicao": row.get("RowVersionDistribuicao", ""),
                "Status": status_execucao,
                "Mensagem": mensagem,
                "HTTPStatus": http_status,
            }
        )

        if pausa_entre_lotes:
            time.sleep(
                pausa_entre_lotes
            )

    return pd.DataFrame(
        logs,
        columns=COLUNAS_LOG_REQUEST,
    )


# ==========================================================
# INSIGHTS E EXPORTAÇÃO
# ==========================================================
def montar_insights_distribuicao(
    df_plano: pd.DataFrame,
    df_logs_request: pd.DataFrame,
    df_quant_antes: pd.DataFrame,
    df_quant_depois: pd.DataFrame,
    dados_painel_antes: List[Dict[str, Any]],
    dados_painel_depois: List[Dict[str, Any]],
) -> pd.DataFrame:
    insights = []

    def add(indicador, valor):
        insights.append(
            {
                "Indicador": indicador,
                "Valor": valor,
            }
        )

    total_painel_antes = len(
        dados_painel_antes or []
    )

    total_painel_depois = len(
        dados_painel_depois or []
    )

    aptos_antes = len(
        filtrar_aptos_distribuicao(
            dados_painel_antes
        )
    )

    aptos_depois = len(
        filtrar_aptos_distribuicao(
            dados_painel_depois
        )
    )

    add(
        "Total painel antes",
        total_painel_antes,
    )

    add(
        "Total painel depois",
        total_painel_depois,
    )

    add(
        "Aptos para distribuição antes",
        aptos_antes,
    )

    add(
        "Aptos para distribuição depois",
        aptos_depois,
    )

    add(
        "Redução de aptos",
        aptos_antes - aptos_depois,
    )

    if df_plano is not None and not df_plano.empty:
        add(
            "Total planejado",
            len(df_plano),
        )

        add(
            "Total executável",
            int((df_plano["PodeExecutar"] == True).sum()),
        )

        add(
            "Sem capacidade",
            int((df_plano["StatusPlanejamento"] == "SEM_CAPACIDADE").sum()),
        )

        add(
            "Sem Key/RowVersion",
            int((df_plano["StatusPlanejamento"] == "SEM_KEY_OU_ROWVERSION").sum()),
        )

        add(
            "Devedores únicos planejados",
            df_plano["DevedorNumeroInscricao"].nunique(),
        )

        add(
            "Registros com quebra de devedor",
            int((df_plano["QuebraDevedor"] == "Sim").sum()),
        )

        if "DevedorDistribuidoMaisDeUmTecnico" in df_plano.columns:
            add(
                "Devedores divididos entre técnicos",
                int(
                    df_plano.loc[
                        df_plano["DevedorDistribuidoMaisDeUmTecnico"] == "Sim",
                        "DevedorNumeroInscricao",
                    ].nunique()
                ),
            )

    if df_logs_request is not None and not df_logs_request.empty:
        add(
            "Total enviado na request",
            len(df_logs_request),
        )

        add(
            "Sucessos na request",
            int((df_logs_request["Status"] == "SUCESSO").sum()),
        )

        add(
            "Erros na request",
            int((df_logs_request["Status"] == "ERRO").sum()),
        )

    if df_quant_antes is not None and not df_quant_antes.empty:
        add(
            "Total análise antes",
            int(df_quant_antes["QtdAnaliseSapiens"].sum()),
        )

        add(
            "Total conferência antes",
            int(df_quant_antes["QtdConferenciaSapiens"].sum()),
        )

    if df_quant_depois is not None and not df_quant_depois.empty:
        add(
            "Total análise depois",
            int(df_quant_depois["QtdAnaliseSapiens"].sum()),
        )

        add(
            "Total conferência depois",
            int(df_quant_depois["QtdConferenciaSapiens"].sum()),
        )

    return pd.DataFrame(
        insights
    )



def montar_df_quebras_devedor(
    df_plano: pd.DataFrame,
) -> pd.DataFrame:
    """
    Retorna uma visão específica dos devedores que precisaram ser distribuídos
    para mais de um analisador/conferidor por limite de capacidade/meta.
    """
    if df_plano is None or df_plano.empty:
        return pd.DataFrame(
            columns=[
                "DevedorNumeroInscricao",
                "DevedorIdentificacao",
                "TotalAutosDevedor",
                "QtdTecnicosEnvolvidos",
                "AnalisadorNome",
                "ConferidorNome",
                "QtdAutosNoTecnico",
                "Autos",
            ]
        )

    df = df_plano.copy()

    for coluna in [
        "DevedorNumeroInscricao",
        "DevedorIdentificacao",
        "AnalisadorNome",
        "ConferidorNome",
        "NumeroAuto",
        "DevedorDistribuidoMaisDeUmTecnico",
    ]:
        if coluna not in df.columns:
            df[coluna] = ""

    df["_ChaveDevedor"] = df["DevedorNumeroInscricao"].astype(str).str.strip()
    df["_ChaveDevedor"] = df["_ChaveDevedor"].where(
        df["_ChaveDevedor"] != "",
        df["DevedorIdentificacao"].astype(str).str.strip(),
    )

    if "DevedorDistribuidoMaisDeUmTecnico" in df.columns:
        df = df[df["DevedorDistribuidoMaisDeUmTecnico"] == "Sim"].copy()
    else:
        pares = (
            df["AnalisadorNome"].astype(str)
            + "|"
            + df["ConferidorNome"].astype(str)
        )
        df["_Par"] = pares
        qtd_pares = df.groupby("_ChaveDevedor")["_Par"].transform("nunique")
        df = df[qtd_pares > 1].copy()

    if df.empty:
        return pd.DataFrame(
            columns=[
                "DevedorNumeroInscricao",
                "DevedorIdentificacao",
                "TotalAutosDevedor",
                "QtdTecnicosEnvolvidos",
                "AnalisadorNome",
                "ConferidorNome",
                "QtdAutosNoTecnico",
                "Autos",
            ]
        )

    df["_Par"] = (
        df["AnalisadorNome"].astype(str)
        + "|"
        + df["ConferidorNome"].astype(str)
    )

    total_autos = df.groupby("_ChaveDevedor")["NumeroAuto"].transform("count")
    qtd_tecnicos = df.groupby("_ChaveDevedor")["_Par"].transform("nunique")

    agrupado = (
        df.assign(
            TotalAutosDevedor=total_autos,
            QtdTecnicosEnvolvidos=qtd_tecnicos,
        )
        .groupby(
            [
                "DevedorNumeroInscricao",
                "DevedorIdentificacao",
                "TotalAutosDevedor",
                "QtdTecnicosEnvolvidos",
                "AnalisadorNome",
                "ConferidorNome",
            ],
            dropna=False,
        )
        .agg(
            QtdAutosNoTecnico=("NumeroAuto", "count"),
            Autos=("NumeroAuto", lambda s: ", ".join(s.astype(str).tolist())),
        )
        .reset_index()
        .sort_values(
            [
                "TotalAutosDevedor",
                "DevedorIdentificacao",
                "AnalisadorNome",
            ],
            ascending=[False, True, True],
        )
    )

    return agrupado


def montar_df_controle_distribuidos(
    df_plano: pd.DataFrame,
    df_logs_request: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """
    Monta a aba de controle com uma linha por auto efetivamente distribuído.

    Prioridade:
    - se houver logs de request com status SUCESSO, usa somente esses autos;
    - se não houver logs, usa o plano executável como referência.
    """
    colunas = [
        "Devedor",
        "Auto distribuído",
        "Analisador",
        "Conferidor",
        "Valor do auto de infração",
    ]

    if df_plano is None or df_plano.empty:
        return pd.DataFrame(columns=colunas)

    df_base = df_plano.copy()

    if "PodeExecutar" in df_base.columns:
        df_base = df_base[
            df_base["PodeExecutar"] == True
        ].copy()

    if df_base.empty:
        return pd.DataFrame(columns=colunas)

    if (
        df_logs_request is not None
        and not df_logs_request.empty
        and "Status" in df_logs_request.columns
        and "NumeroAuto" in df_logs_request.columns
    ):
        df_sucesso = df_logs_request[
            df_logs_request["Status"]
            .astype(str)
            .str.upper()
            .eq("SUCESSO")
        ].copy()

        if not df_sucesso.empty:
            autos_sucesso = set(
                df_sucesso["NumeroAuto"]
                .astype(str)
                .str.strip()
                .tolist()
            )

            df_base = df_base[
                df_base["NumeroAuto"]
                .astype(str)
                .str.strip()
                .isin(autos_sucesso)
            ].copy()

    if df_base.empty:
        return pd.DataFrame(columns=colunas)

    df_controle = pd.DataFrame({
        "Devedor": df_base.get(
            "DevedorIdentificacao",
            pd.Series([""] * len(df_base), index=df_base.index),
        ),
        "Auto distribuído": df_base.get(
            "NumeroAuto",
            pd.Series([""] * len(df_base), index=df_base.index),
        ),
        "Analisador": df_base.get(
            "AnalisadorNome",
            pd.Series([""] * len(df_base), index=df_base.index),
        ),
        "Conferidor": df_base.get(
            "ConferidorNome",
            pd.Series([""] * len(df_base), index=df_base.index),
        ),
        "Valor do auto de infração": df_base.get(
            "ValorOriginal",
            pd.Series([""] * len(df_base), index=df_base.index),
        ),
    })

    return df_controle[colunas]


def exportar_distribuicao_completa_excel(
    caminho_saida: str,
    df_logs_interface: pd.DataFrame,
    df_plano: pd.DataFrame,
    df_logs_request: pd.DataFrame,
    dados_painel_antes: List[Dict[str, Any]],
    dados_painel_depois: List[Dict[str, Any]],
    df_quant_antes: pd.DataFrame,
    df_quant_depois: pd.DataFrame,
    df_comparativo: pd.DataFrame,
    df_insights: pd.DataFrame,
) -> None:
    df_painel_antes = normalizar_dataframe_painel(
        dados_painel_antes
    )

    df_painel_depois = normalizar_dataframe_painel(
        dados_painel_depois
    )

    df_quebras = montar_df_quebras_devedor(
        df_plano
    )

    df_controle_distribuidos = montar_df_controle_distribuidos(
        df_plano,
        df_logs_request,
    )

    if df_plano is not None and not df_plano.empty and "MetaPainel" in df_plano.columns:
        df_plano = df_plano.copy()
        df_plano.rename(
            columns={"MetaPainel": "QuantidadeInformada"},
            inplace=True,
        )


    if df_plano is not None and not df_plano.empty and "PodeExecutar" in df_plano.columns:
        df_resumo_tecnico = (
            df_plano[df_plano["PodeExecutar"] == True]
            .groupby(
                [
                    "AnalisadorNome",
                    "ConferidorNome",
                    "QuantidadeInformada",
                    "AtualPainelConsiderado",
                    "QuantidadeDistribuirTecnico",
                ],
                dropna=False,
            )
            .agg(
                QtdAutos=("NumeroAuto", "count"),
                QtdDevedores=("DevedorIdentificacao", "nunique"),
                QtdAutosComQuebra=("QuebraDevedor", lambda s: int((s == "Sim").sum())),
            )
            .reset_index()
        )
    else:
        df_resumo_tecnico = pd.DataFrame()

    with pd.ExcelWriter(
        caminho_saida,
        engine="openpyxl",
    ) as writer:
        df_logs_interface.to_excel(
            writer,
            sheet_name="Logs Interface",
            index=False,
        )

        df_insights.to_excel(
            writer,
            sheet_name="Insights",
            index=False,
        )

        df_controle_distribuidos.to_excel(
            writer,
            sheet_name="Controle distribuídos",
            index=False,
        )

        df_plano.to_excel(
            writer,
            sheet_name="Distribuição Executada",
            index=False,
        )

        df_resumo_tecnico.to_excel(
            writer,
            sheet_name="Resumo por Técnico",
            index=False,
        )

        df_quebras.to_excel(
            writer,
            sheet_name="Quebras de Devedor",
            index=False,
        )

        df_logs_request.to_excel(
            writer,
            sheet_name="Logs Requests",
            index=False,
        )


        df_comparativo.to_excel(
            writer,
            sheet_name="Comparativo",
            index=False,
        )

        df_painel_antes.to_excel(
            writer,
            sheet_name="Painel Antes",
            index=False,
        )

        df_painel_depois.to_excel(
            writer,
            sheet_name="Painel Depois",
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

                sheet.column_dimensions[column_letter].width = min(
                    max_length + 2,
                    80,
                )