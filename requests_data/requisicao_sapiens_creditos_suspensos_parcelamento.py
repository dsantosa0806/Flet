# ==========================================================
# REQUISIÇÕES - SUPER SAPIENS
# CRÉDITOS SUSPENSOS POR PARCELAMENTO ATUALMENTE
# ==========================================================
import os
import re
import json
import time
import base64
import unicodedata
from datetime import datetime
from typing import Optional, Callable, Dict, Any, List

import pandas as pd
import requests
from openpyxl import load_workbook


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


# ==========================================================
# TRATAMENTO DO RELATÓRIO / MONITORIA
# ==========================================================
CAMINHO_MONITORIA_SUSPENSAO = os.getenv(
    "SS_MONITORIA_SUSPENSAO",
    r"C:\Monitoria-Suspensao\monitoria-suspensos.xlsx"
)

CREDOR_DNIT = (
    "DEPARTAMENTO NACIONAL DE INFRA-ESTRUTURA DE TRANSPORTES - DNIT"
)

ESPECIES_CREDITO_DNIT = [
    "DNIT - DEMAIS MULTAS DE TRANSITO",
    "DNIT - MULTA INFRAÇÃO ADMINISTRATIVA EXCESSO DE VELOCIDADE",
    "DNIT - MULTA INFRAÇÃO ADMINISTRATIVA EXCESSO PESO",
    "DNIT - MULTA POR AVANÇO DE SINAL VERMELHO",
]

LogFn = Optional[Callable[[str], None]]


# ==========================================================
# HELPERS GERAIS
# ==========================================================
def _log(log: LogFn, mensagem: str) -> None:
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


def criar_pasta_downloads(diretorio_downloads: str) -> None:
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


def _extrair_usuario_id_do_token(token: str) -> Optional[int]:
    payload = _extrair_payload_token(
        token
    )

    usuario_id = payload.get("id")

    try:
        if usuario_id:
            return int(usuario_id)
    except Exception:
        pass

    return None


def _filename_content_disposition(content_disposition: str) -> Optional[str]:
    """
    Tenta extrair filename do header Content-Disposition, quando existir.
    """

    if not content_disposition:
        return None

    match = re.search(
        r'filename\*?=(?:UTF-8\'\')?"?([^";]+)"?',
        content_disposition,
        flags=re.IGNORECASE
    )

    if not match:
        return None

    nome = match.group(1).strip()

    if not nome:
        return None

    return _sanitizar_nome_arquivo(
        nome
    )


def _identificar_extensao_por_content_type(content_type: str) -> str:
    content_type = str(
        content_type or ""
    ).lower()

    if "spreadsheetml" in content_type or "excel" in content_type:
        return ".xlsx"

    if "pdf" in content_type:
        return ".pdf"

    if "csv" in content_type:
        return ".csv"

    if "zip" in content_type:
        return ".zip"

    return ".xlsx"


def _extrair_id_componente_de_lista(componentes: Any) -> Optional[int]:
    if not isinstance(componentes, list):
        return None

    for comp in componentes:
        if not isinstance(comp, dict):
            continue

        comp_id = comp.get("id")

        if comp_id:
            try:
                return int(comp_id)
            except Exception:
                return comp_id

    return None


def _procurar_componente_digital_recursivo(obj: Any) -> Optional[int]:
    """
    Fallback defensivo: procura recursivamente um dict que pareça ComponenteDigital.
    """

    if isinstance(obj, dict):
        tipo = str(
            obj.get("@type") or ""
        )

        at_id = str(
            obj.get("@id") or ""
        )

        if (
            tipo == "ComponenteDigital"
            or "/v1/administrativo/componente_digital/" in at_id
        ):
            comp_id = obj.get("id")

            if comp_id:
                try:
                    return int(comp_id)
                except Exception:
                    return comp_id

        for valor in obj.values():
            encontrado = _procurar_componente_digital_recursivo(
                valor
            )

            if encontrado:
                return encontrado

    if isinstance(obj, list):
        for item in obj:
            encontrado = _procurar_componente_digital_recursivo(
                item
            )

            if encontrado:
                return encontrado

    return None


# ==========================================================
# PAYLOAD
# ==========================================================
def montar_payload_creditos_suspensos_parcelamento() -> dict:
    """
    Monta payload equivalente à request capturada no navegador.

    Atenção:
    Este relatório 809 NÃO recebe numeroDocumentoPrincipal.
    Na request funcional, o campo parametros é enviado literalmente como string "null".
    """

    return {
        "formato": "xlsx",
        "nomeRelatorio": None,
        "documento": None,
        "observacao": None,
        "tipoRelatorio": TIPO_RELATORIO_CREDITOS_SUSPENSOS_PARCELAMENTO,
        "parametros": "null",
        "status": None,
        "generoRelatorio": {
            "nome": "OPERACIONAL",
            "descricao": "OPERACIONAL",
            "especiesRelatorios": None,
            "@type": "GeneroRelatorio",
            "@id": "/v1/administrativo/genero_relatorio/3",
            "@context": "/api/doc/#model-GeneroRelatorio",
            "ativo": True,
            "criadoEm": "2013-10-18T15:00:17",
            "atualizadoEm": "2013-10-18T15:00:17",
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
            "criadoEm": "2016-09-16T18:34:08",
            "atualizadoEm": "2023-06-20T16:19:59",
        },
    }


# ==========================================================
# GERAÇÃO DO RELATÓRIO
# ==========================================================
def gerar_relatorio_creditos_suspensos_parcelamento(
    token: str,
    log: LogFn = None
) -> Dict[str, Any]:
    payload = montar_payload_creditos_suspensos_parcelamento()

    _log(
        log,
        f"📤 Solicitando relatório: {NOME_RELATORIO}..."
    )

    _log(
        log,
        "🔎 Enviando payload com parametros='null', conforme request capturada."
    )

    resp = requests.post(
        URL_RELATORIO,
        headers=_headers(
            token,
            content_type="text/plain"
        ),
        data=json.dumps(
            payload,
            ensure_ascii=False
        ).encode("utf-8"),
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
    )

    params = {
        "populate": json.dumps([
            "documento",
            "tipoRelatorio",
            "vinculacoesEtiquetas",
            "vinculacoesEtiquetas.etiqueta",
        ]),
        "context": "{}",
        "order": "{}",
    }

    try:
        resp = requests.get(
            url,
            headers=_headers(token),
            params=params,
            timeout=TIMEOUT_REQUEST
        )

    except Exception as ex:
        _log(
            log,
            f"⚠️ Erro de conexão ao consultar relatório {id_relatorio}: {ex}"
        )
        return None

    if resp.status_code != 200:
        _log(
            log,
            f"⚠️ Falha ao consultar relatório {id_relatorio}. HTTP {resp.status_code}"
        )
        return None

    try:
        return resp.json()

    except Exception as ex:
        _log(
            log,
            f"⚠️ Erro ao ler JSON do relatório {id_relatorio}: {ex}"
        )
        return None


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

    try:
        resp = requests.get(
            url,
            headers=_headers(token),
            params=params,
            timeout=TIMEOUT_REQUEST
        )

    except Exception as ex:
        _log(
            log,
            f"⚠️ Erro de conexão ao listar relatórios recentes: {ex}"
        )
        return []

    if resp.status_code != 200:
        _log(
            log,
            f"⚠️ Falha ao listar relatórios recentes. HTTP {resp.status_code}"
        )
        return []

    try:
        dados = resp.json()

    except Exception as ex:
        _log(
            log,
            f"⚠️ Erro ao ler JSON da listagem de relatórios: {ex}"
        )
        return []

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
            status_relatorio = dados.get("status")
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
                        f"Status relatório: {status_relatorio}. "
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
                try:
                    mesmo_relatorio = int(item.get("id", 0)) == int(id_relatorio)
                except Exception:
                    mesmo_relatorio = False

                if not mesmo_relatorio:
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
def consultar_componentes_por_documento(
    token: str,
    id_documento: int,
    log: LogFn = None
) -> Optional[int]:
    """
    Fallback: consulta diretamente a coleção de componente_digital filtrando pelo documento.
    """

    url = f"{BACKEND}/v1/administrativo/componente_digital"

    filtros_possiveis = [
        {
            "documento.id": f"eq:{id_documento}"
        },
        {
            "documento": f"eq:{id_documento}"
        },
    ]

    for filtro in filtros_possiveis:
        params = {
            "where": json.dumps(filtro),
            "limit": 10,
            "offset": 0,
            "order": json.dumps({
                "id": "DESC"
            }),
            "populate": json.dumps([]),
            "context": "{}",
        }

        try:
            resp = requests.get(
                url,
                headers=_headers(token),
                params=params,
                timeout=TIMEOUT_REQUEST
            )

        except Exception as ex:
            _log(
                log,
                f"⚠️ Erro ao consultar componente_digital por documento: {ex}"
            )
            continue

        if resp.status_code != 200:
            _log(
                log,
                (
                    f"⚠️ Consulta direta de componente_digital retornou "
                    f"HTTP {resp.status_code} para filtro {filtro}."
                )
            )
            continue

        try:
            dados = resp.json()

        except Exception as ex:
            _log(
                log,
                f"⚠️ Erro ao ler JSON de componente_digital: {ex}"
            )
            continue

        entidades = dados.get("entities")

        comp_id = _extrair_id_componente_de_lista(
            entidades
        )

        if comp_id:
            return comp_id

        comp_id = _procurar_componente_digital_recursivo(
            dados
        )

        if comp_id:
            return comp_id

    return None


def obter_componente_digital_do_documento(
    token: str,
    id_documento: int,
    log: LogFn = None,
    tentativas: int = TENTATIVAS_DOCUMENTO,
    espera_segundos: int = PAUSA_DOCUMENTO_SEGUNDOS
) -> Optional[int]:
    """
    Consulta o documento até localizar componentesDigitais[0].id.

    Usa também fallback direto na coleção componente_digital.
    """

    url = (
        f"{BACKEND}/v1/administrativo/documento/{id_documento}"
    )

    params = {
        "populate": json.dumps([
            "componentesDigitais"
        ]),
        "context": "{}",
        "order": "{}",
    }

    inicio = time.time()

    for tentativa in range(1, tentativas + 1):
        try:
            resp = requests.get(
                url,
                headers=_headers(token),
                params=params,
                timeout=TIMEOUT_REQUEST
            )

        except Exception as ex:
            _log(
                log,
                f"⚠️ Erro de conexão ao consultar documento {id_documento}: {ex}"
            )

            time.sleep(
                espera_segundos
            )
            continue

        if resp.status_code == 200:
            try:
                dados = resp.json()

                componentes = dados.get("componentesDigitais") or []

                comp_id = _extrair_id_componente_de_lista(
                    componentes
                )

                if not comp_id:
                    comp_id = _procurar_componente_digital_recursivo(
                        dados
                    )

                if comp_id:
                    tempo_total = int(
                        time.time() - inicio
                    )

                    _log(
                        log,
                        (
                            f"✅ Componente digital localizado no documento. "
                            f"ID: {comp_id}. "
                            f"Tempo aguardado nesta etapa: {tempo_total}s."
                        )
                    )

                    return comp_id

            except Exception as ex:
                _log(
                    log,
                    f"⚠️ Erro ao ler JSON do documento {id_documento}: {ex}"
                )

        else:
            _log(
                log,
                f"⚠️ Falha ao consultar documento {id_documento}. HTTP {resp.status_code}"
            )

        # Fallback: consulta direta em componente_digital
        comp_id_fallback = consultar_componentes_por_documento(
            token=token,
            id_documento=id_documento,
            log=log
        )

        if comp_id_fallback:
            tempo_total = int(
                time.time() - inicio
            )

            _log(
                log,
                (
                    f"✅ Componente digital localizado pelo fallback. "
                    f"ID: {comp_id_fallback}. "
                    f"Tempo aguardado nesta etapa: {tempo_total}s."
                )
            )

            return comp_id_fallback

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
    )

    params = {
        "context": "{}",
        "populate": json.dumps([]),
    }

    _log(
        log,
        f"📥 Baixando componente digital {comp_id}..."
    )

    try:
        resp = requests.get(
            url,
            headers=_headers(token),
            params=params,
            timeout=TIMEOUT_DOWNLOAD
        )

    except Exception as ex:
        raise RuntimeError(
            f"Erro de conexão ao baixar componente {comp_id}: {ex}"
        )

    if resp.status_code != 200:
        raise RuntimeError(
            f"Erro ao baixar componente {comp_id}. HTTP {resp.status_code}: {resp.text}"
        )

    content_type = resp.headers.get(
        "Content-Type",
        ""
    ).lower()

    content_disposition = resp.headers.get(
        "Content-Disposition",
        ""
    )

    timestamp = datetime.now().strftime(
        "%Y-%m-%d_%H-%M-%S"
    )

    conteudo_bytes = resp.content or b""
    parece_json = conteudo_bytes.lstrip().startswith(b"{")

    # ======================================================
    # CASO 1: JSON com base64
    # ======================================================
    if "json" in content_type or parece_json:
        try:
            dados = resp.json()

        except Exception as ex:
            raise RuntimeError(
                f"Resposta do componente {comp_id} parece JSON, mas não foi possível ler: {ex}"
            )

        nome_arquivo = dados.get(
            "fileName"
        )

        if not nome_arquivo:
            nome_arquivo = (
                f"Creditos_Suspensos_Parcelamento_{comp_id}_{timestamp}.xlsx"
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
    nome_arquivo = _filename_content_disposition(
        content_disposition
    )

    if not nome_arquivo:
        extensao = _identificar_extensao_por_content_type(
            content_type
        )

        nome_arquivo = (
            f"Creditos_Suspensos_Parcelamento_{comp_id}_{timestamp}{extensao}"
        )

    nome_arquivo = _sanitizar_nome_arquivo(
        nome_arquivo
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
# TRATAMENTO DO XLSX BAIXADO
# ==========================================================
def _remover_acentos(texto: str) -> str:
    texto = str(texto or "")

    return "".join(
        c
        for c in unicodedata.normalize("NFKD", texto)
        if not unicodedata.combining(c)
    )


def _normalizar_nome_campo(valor) -> str:
    texto = _remover_acentos(
        str(valor or "")
    ).strip().upper()

    texto = texto.replace("-", "_")
    texto = texto.replace(".", "")
    texto = texto.replace("/", "_")
    texto = texto.replace("\\", "_")

    texto = re.sub(
        r"\s+",
        "_",
        texto
    )

    texto = re.sub(
        r"_+",
        "_",
        texto
    )

    return texto.strip("_")


def _normalizar_texto_comparacao(valor) -> str:
    if valor is None:
        return ""

    try:
        if pd.isna(valor):
            return ""
    except Exception:
        pass

    texto = _remover_acentos(
        str(valor)
    ).strip().upper()

    texto = re.sub(
        r"\s+",
        " ",
        texto
    )

    return texto.strip()


def _normalizar_ait(valor) -> str:
    if valor is None:
        return ""

    try:
        if pd.isna(valor):
            return ""
    except Exception:
        pass

    texto = str(valor).strip().upper()

    if texto.endswith(".0"):
        texto = texto[:-2]

    texto = re.sub(
        r"[^A-Z0-9]",
        "",
        texto
    )

    return texto


def _montar_mapa_colunas(df: pd.DataFrame) -> dict:
    return {
        _normalizar_nome_campo(coluna): coluna
        for coluna in df.columns
    }


def _localizar_linha_cabecalho_excel(caminho_xlsx: str) -> int:
    """
    Tenta localizar a linha do cabeçalho automaticamente.
    Regra esperada: linha 7, ou seja, índice 6 para o pandas.

    Retorna índice zero-based para usar em pd.read_excel(header=...).
    """

    try:
        preview = pd.read_excel(
            caminho_xlsx,
            header=None,
            nrows=20,
            dtype=str
        )

        campos_obrigatorios = {
            "CREDOR",
            "ESPECIE_CREDITO",
            "NUM_ORIGEM",
        }

        for idx, row in preview.iterrows():
            valores = {
                _normalizar_nome_campo(v)
                for v in row.tolist()
                if str(v or "").strip()
            }

            if campos_obrigatorios.issubset(valores):
                return int(idx)

    except Exception:
        pass

    # Fallback pela regra informada: cabeçalho na linha 7.
    return 6


def _ler_relatorio_creditos_suspensos(
    caminho_xlsx: str
) -> pd.DataFrame:
    linha_header = _localizar_linha_cabecalho_excel(
        caminho_xlsx
    )

    df = pd.read_excel(
        caminho_xlsx,
        header=linha_header,
        dtype=str
    )

    df = df.dropna(
        how="all"
    ).copy()

    return df


def _ajustar_largura_abas_excel(caminho_xlsx: str) -> None:
    try:
        wb = load_workbook(
            caminho_xlsx
        )

        for ws in wb.worksheets:
            ws.freeze_panes = "A2"

            for colunas in ws.columns:
                letra_coluna = colunas[0].column_letter

                maior = 0

                for celula in colunas:
                    try:
                        valor = str(
                            celula.value or ""
                        )
                    except Exception:
                        valor = ""

                    maior = max(
                        maior,
                        len(valor)
                    )

                ws.column_dimensions[letra_coluna].width = min(
                    max(maior + 2, 12),
                    60
                )

            try:
                ws.auto_filter.ref = ws.dimensions
            except Exception:
                pass

        wb.save(
            caminho_xlsx
        )

    except Exception:
        pass


def processar_relatorio_creditos_suspensos_parcelamento(
    caminho_relatorio_original: str,
    diretorio_saida: str,
    caminho_monitoria: str = CAMINHO_MONITORIA_SUSPENSAO,
    log: LogFn = None
) -> Dict[str, Any]:
    """
    Processa o XLSX baixado do Super Sapiens.

    Saída:
    - Aba Filtrado DNIT:
        registros com Credor DNIT e espécies de crédito selecionadas.
    - Aba Consta monitoria:
        registros cujo Num_origem consta em C:\\Monitoria-Suspensao.xlsx.
    - Aba Registrar suspensao:
        registros cujo Num_origem NÃO consta em C:\\Monitoria-Suspensao.xlsx.
    """

    if not caminho_relatorio_original or not os.path.exists(caminho_relatorio_original):
        raise FileNotFoundError(
            f"Relatório original não encontrado: {caminho_relatorio_original}"
        )

    if not caminho_monitoria or not os.path.exists(caminho_monitoria):
        raise FileNotFoundError(
            (
                "Planilha de monitoria não encontrada. "
                f"Arquivo esperado: {caminho_monitoria}"
            )
        )

    os.makedirs(
        diretorio_saida,
        exist_ok=True
    )

    _log(
        log,
        "📊 Iniciando tratamento do relatório baixado..."
    )

    df = _ler_relatorio_creditos_suspensos(
        caminho_relatorio_original
    )

    if df.empty:
        raise RuntimeError(
            "O relatório baixado foi lido, mas não possui registros."
        )

    mapa = _montar_mapa_colunas(
        df
    )

    coluna_credor = mapa.get(
        "CREDOR"
    )

    coluna_especie = (
        mapa.get("ESPECIE_CREDITO")
        or mapa.get("ESPECIE_CREDITO_")
        or mapa.get("ESPECIE_CREDITO_ATIVA")
    )

    coluna_num_origem = (
        mapa.get("NUM_ORIGEM")
        or mapa.get("NUMERO_ORIGEM")
        or mapa.get("NUMERO_ORIGEM_CREDITO")
    )

    if not coluna_credor:
        raise RuntimeError(
            "Não foi possível localizar a coluna 'Credor' no relatório baixado."
        )

    if not coluna_especie:
        raise RuntimeError(
            "Não foi possível localizar a coluna 'Especie_credito' no relatório baixado."
        )

    if not coluna_num_origem:
        raise RuntimeError(
            "Não foi possível localizar a coluna 'Num_origem' no relatório baixado."
        )

    credor_filtro = _normalizar_texto_comparacao(
        CREDOR_DNIT
    )

    especies_filtro = {
        _normalizar_texto_comparacao(especie)
        for especie in ESPECIES_CREDITO_DNIT
    }

    df_filtrado = df[
        (
            df[coluna_credor].apply(_normalizar_texto_comparacao)
            == credor_filtro
        )
        &
        (
            df[coluna_especie].apply(_normalizar_texto_comparacao)
            .isin(especies_filtro)
        )
    ].copy()

    _log(
        log,
        f"✅ Registros após filtro DNIT/especies: {len(df_filtrado)}"
    )

    df_monitoria = pd.read_excel(
        caminho_monitoria,
        dtype=str
    )

    if df_monitoria.empty:
        raise RuntimeError(
            f"A planilha de monitoria está vazia: {caminho_monitoria}"
        )

    mapa_monitoria = _montar_mapa_colunas(
        df_monitoria
    )

    coluna_monitoria_ait = (
        mapa_monitoria.get("NUMERO_AIT")
        or mapa_monitoria.get("AIT")
        or mapa_monitoria.get("NUM_ORIGEM")
    )

    coluna_monitoria_status = mapa_monitoria.get(
        "STATUS"
    )

    coluna_monitoria_situacao = (
        mapa_monitoria.get("SITUACAO_AIT")
        or mapa_monitoria.get("SITUACAO")
    )

    if not coluna_monitoria_ait:
        raise RuntimeError(
            (
                "Não foi possível localizar a coluna 'Numero_AIT' "
                "na planilha C:\\Monitoria-Suspensao.xlsx."
            )
        )

    df_filtrado["_AIT_COMPARACAO"] = df_filtrado[coluna_num_origem].apply(
        _normalizar_ait
    )

    df_monitoria["_AIT_COMPARACAO"] = df_monitoria[coluna_monitoria_ait].apply(
        _normalizar_ait
    )

    df_monitoria = df_monitoria[
        df_monitoria["_AIT_COMPARACAO"] != ""
    ].copy()

    df_monitoria_unica = df_monitoria.drop_duplicates(
        subset=["_AIT_COMPARACAO"],
        keep="first"
    ).copy()

    conjunto_monitoria = set(
        df_monitoria_unica["_AIT_COMPARACAO"].tolist()
    )

    mask_consta = df_filtrado["_AIT_COMPARACAO"].isin(
        conjunto_monitoria
    )

    df_consta_monitoria = df_filtrado[
        mask_consta
    ].copy()

    df_registrar_suspensao = df_filtrado[
        ~mask_consta
    ].copy()

    if not df_monitoria_unica.empty:
        monitoria_indexada = df_monitoria_unica.set_index(
            "_AIT_COMPARACAO"
        )

        if not df_consta_monitoria.empty:
            if coluna_monitoria_status:
                mapa_status = monitoria_indexada[coluna_monitoria_status].to_dict()

                df_consta_monitoria["Monitoria_Status"] = (
                    df_consta_monitoria["_AIT_COMPARACAO"].map(mapa_status)
                )

            if coluna_monitoria_situacao:
                mapa_situacao = monitoria_indexada[coluna_monitoria_situacao].to_dict()

                df_consta_monitoria["Monitoria_Situacao_AIT"] = (
                    df_consta_monitoria["_AIT_COMPARACAO"].map(mapa_situacao)
                )

            mapa_numero_ait = monitoria_indexada[coluna_monitoria_ait].to_dict()

            df_consta_monitoria["Monitoria_Numero_AIT"] = (
                df_consta_monitoria["_AIT_COMPARACAO"].map(mapa_numero_ait)
            )

    for dataframe in [
        df_filtrado,
        df_consta_monitoria,
        df_registrar_suspensao
    ]:
        if "_AIT_COMPARACAO" in dataframe.columns:
            dataframe.drop(
                columns=["_AIT_COMPARACAO"],
                inplace=True
            )

    timestamp = datetime.now().strftime(
        "%Y-%m-%d_%H-%M-%S"
    )

    caminho_tratado = os.path.join(
        diretorio_saida,
        f"Creditos_Suspensos_Parcelamento_TRATADO_{timestamp}.xlsx"
    )

    with pd.ExcelWriter(
        caminho_tratado,
        engine="openpyxl"
    ) as writer:
        df_filtrado.to_excel(
            writer,
            sheet_name="Filtrado DNIT",
            index=False
        )

        df_consta_monitoria.to_excel(
            writer,
            sheet_name="Consta monitoria",
            index=False
        )

        df_registrar_suspensao.to_excel(
            writer,
            sheet_name="Registrar suspensao",
            index=False
        )

    _ajustar_largura_abas_excel(
        caminho_tratado
    )

    _log(
        log,
        f"✅ Aba 'Consta monitoria': {len(df_consta_monitoria)} registro(s)."
    )

    _log(
        log,
        f"✅ Aba 'Registrar suspensao': {len(df_registrar_suspensao)} registro(s)."
    )

    _log(
        log,
        f"📄 Planilha tratada salva em: {caminho_tratado}"
    )

    return {
        "arquivo_tratado": caminho_tratado,
        "total_relatorio_original": len(df),
        "total_filtrado": len(df_filtrado),
        "total_consta_monitoria": len(df_consta_monitoria),
        "total_registrar_suspensao": len(df_registrar_suspensao),
    }


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
    4. Baixa XLSX original;
    5. Filtra DNIT / espécies;
    6. Compara Num_origem com C:\\Monitoria-Suspensao.xlsx;
    7. Gera XLSX tratado.
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

    arquivo_original = baixar_componente_digital(
        token=token,
        comp_id=comp_id,
        diretorio_downloads=diretorio_downloads,
        log=log
    )

    if not arquivo_original:
        raise RuntimeError(
            "Não foi possível baixar o arquivo do relatório."
        )

    # Salva a planilha tratada na pasta principal da execução,
    # e não dentro da subpasta downloads.
    if os.path.basename(os.path.normpath(diretorio_downloads)).lower() == "downloads":
        diretorio_saida_tratada = os.path.dirname(
            os.path.normpath(diretorio_downloads)
        )
    else:
        diretorio_saida_tratada = diretorio_downloads

    resultado_tratamento = processar_relatorio_creditos_suspensos_parcelamento(
        caminho_relatorio_original=arquivo_original,
        diretorio_saida=diretorio_saida_tratada,
        caminho_monitoria=CAMINHO_MONITORIA_SUSPENSAO,
        log=log
    )

    return {
        "id_relatorio": id_relatorio,
        "id_documento": doc_id,
        "id_componente": comp_id,
        "arquivo": arquivo_original,
        "arquivo_tratado": resultado_tratamento.get("arquivo_tratado"),
        "total_relatorio_original": resultado_tratamento.get("total_relatorio_original", 0),
        "total_filtrado": resultado_tratamento.get("total_filtrado", 0),
        "total_consta_monitoria": resultado_tratamento.get("total_consta_monitoria", 0),
        "total_registrar_suspensao": resultado_tratamento.get("total_registrar_suspensao", 0),
    }
