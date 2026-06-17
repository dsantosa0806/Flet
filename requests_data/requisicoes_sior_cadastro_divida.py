import pandas as pd
from bs4 import BeautifulSoup, NavigableString
from datetime import datetime


URL_SUPERVISAO = (
    "https://servicos.dnit.gov.br/sior/"
    "Cobranca/SupervisaoSapiensAcompanhamento"
)


def _log(log, mensagem: str):
    print(mensagem)

    if callable(log):
        try:
            log(mensagem)
        except Exception:
            pass


def enviar_requisicao_get(
    s,
    codigos_equipes=None,
    log=None
):
    inicio = datetime.now()

    if codigos_equipes is None:
        codigos_equipes = [1, 2, 3, 4, 5]

    headers = {
        "Accept": "*/*",
        "Accept-Encoding": "gzip, deflate, br, zstd",
        "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
        "Referer": URL_SUPERVISAO,
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "same-origin",
        "X-Lt-Session-Guid": "",
        "X-Requested-With": "XMLHttpRequest",
        "sec-ch-ua": '"Chromium";v="134", "Not:A-Brand";v="24", "Google Chrome";v="134"',
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": '"Windows"'
    }

    s.headers.update(headers)

    todos_dados = []

    for codigo in codigos_equipes:
        url = (
            "https://servicos.dnit.gov.br/sior/"
            "Cobranca/SupervisaoSapiensAcompanhamento/List"
            f"?sort=&page=1&pageSize=10000&group=&filter="
            f"&equipeselecionada={codigo}"
            "&faseselecionada=37"
            "&bind=true"
            "&calledfromapi=true"
            "&calledFromApi=true&"
        )

        try:
            _log(
                log,
                f"📡 Consultando painel da equipe {codigo}..."
            )

            response = s.get(
                url,
                timeout=120
            )

            if response.status_code != 200:
                _log(
                    log,
                    f"❌ Equipe {codigo}: erro HTTP {response.status_code}"
                )
                continue

            json_result = response.json()

            if (
                "Data" not in json_result
                or not isinstance(json_result["Data"], list)
            ):
                _log(
                    log,
                    f"⚠ Equipe {codigo}: retorno inválido ou sem dados."
                )
                continue

            dados = json_result["Data"]

            for item in dados:
                item["EquipeSelecionada"] = codigo

            todos_dados.extend(dados)

            _log(
                log,
                f"✅ Equipe {codigo}: {len(dados)} registros encontrados."
            )

        except Exception as ex:
            _log(
                log,
                f"❌ Equipe {codigo}: erro na requisição: {ex}"
            )

    df = pd.DataFrame(todos_dados)

    if df.empty:
        _log(
            log,
            "⚠ Nenhum registro retornado na varredura do painel."
        )
        return df

    colunas_data = [
        "DataDistribuicaoEquipe",
        "DataDistribuicaoAnalise",
        "DataAnalise",
        "DataDistribuicaoConferencia",
        "DataConferencia"
    ]

    for col in colunas_data:
        if col in df.columns:
            df[col] = (
                pd.to_datetime(
                    df[col],
                    errors="coerce"
                )
                .dt.strftime("%d/%m/%Y")
            )

    fim = datetime.now()
    duracao = str(fim - inicio).split(".")[0]

    _log(
        log,
        f"✅ Painel concluído em {duracao}. Total: {len(df)} registros."
    )

    return df


def extrair_valor_label(label, nome_campo):
    """
    Extrai o valor de um label do SIOR mantendo a lógica mais próxima
    do código original.

    Evita usar find_next(string=True) de forma ampla, pois isso pode
    capturar o próprio nome do campo como valor.
    """

    if (
        "Número do Auto" in nome_campo
        and label.find_next_sibling("a")
    ):
        return (
            label.find_next_sibling("a")
            .get_text(strip=True)
        )

    textarea = label.find_next_sibling("textarea")

    if textarea:
        return textarea.get_text(strip=True)

    input_el = label.find_next_sibling("input")

    if input_el:
        return str(
            input_el.get("value", "")
        ).strip()

    select_el = label.find_next_sibling("select")

    if select_el:
        selecionado = select_el.find(
            "option",
            selected=True
        )

        if selecionado:
            return selecionado.get_text(strip=True)

        return select_el.get_text(" ", strip=True)

    # Mantém o comportamento mais próximo do original:
    # pega texto irmão imediato, sem buscar profundamente no HTML.
    valor_texto = label.find_next_sibling(
        string=True
    )

    if valor_texto:
        return valor_texto.strip()

    # Fallback seguro: percorre irmãos até o próximo label.
    for sibling in label.next_siblings:
        if isinstance(sibling, NavigableString):
            texto = sibling.strip()

            if texto:
                return texto

        nome_tag = getattr(
            sibling,
            "name",
            None
        )

        if nome_tag == "label":
            break

        if nome_tag in {
            "span",
            "div",
            "p",
            "strong",
            "a",
            "td"
        }:
            texto = sibling.get_text(
                " ",
                strip=True
            )

            if texto and texto != label.get_text(strip=True):
                return texto

    return ""


def get_data_sior(
    s,
    df,
    log=None
):
    inicio = datetime.now()

    if df is None or df.empty:
        raise ValueError(
            "DataFrame do painel está vazio. Não há dados para detalhar."
        )

    if "CodigoProcessoInfracao" not in df.columns:
        raise ValueError(
            "Coluna CodigoProcessoInfracao não encontrada em dados.xlsx."
        )

    dados_extraidos = []

    codigos = (
        df["CodigoProcessoInfracao"]
        .dropna()
        .drop_duplicates()
        .tolist()
    )

    total = len(codigos)

    _log(
        log,
        f"📄 Iniciando detalhamento de {total} processos..."
    )

    for i, cod_infra in enumerate(
        codigos,
        start=1
    ):
        url = (
            "https://servicos.dnit.gov.br/sior/"
            f"Cobranca/CobrancaConsulta/DetailsPFE/{cod_infra}"
        )

        s.headers.update(
            {
                "Referer": url
            }
        )

        try:
            response = s.get(
                url,
                timeout=120
            )

            if response.status_code != 200:
                _log(
                    log,
                    f"❌ [{cod_infra}] Erro HTTP {response.status_code}"
                )
                continue

            soup = BeautifulSoup(
                response.text,
                "html.parser"
            )

            labels = soup.find_all(
                "label",
                class_="lt-label"
            )

            if not labels:
                _log(
                    log,
                    f"⚠ [{cod_infra}] Nenhum label lt-label encontrado. Possível sessão expirada ou HTML diferente."
                )

            dados_item = {
                "CodigoProcessoInfracao": cod_infra
            }

            contador_campos = {}

            for label in labels:
                nome_campo = label.get_text(
                    strip=True
                )

                fieldset = label.find_parent(
                    "fieldset"
                )

                legenda = None

                if (
                    fieldset
                    and fieldset.find("legend")
                ):
                    legenda = fieldset.find(
                        "legend"
                    ).get_text(
                        strip=True
                    )

                if legenda:
                    nome_campo = (
                        f"{nome_campo} - {legenda}"
                    )

                valor = extrair_valor_label(
                    label,
                    nome_campo
                )

                chave_base = nome_campo

                contador_campos.setdefault(
                    chave_base,
                    0
                )

                contador_campos[chave_base] += 1

                if contador_campos[chave_base] > 1:
                    nome_campo = (
                        f"{chave_base} "
                        f"[{contador_campos[chave_base]}]"
                    )

                dados_item[nome_campo] = valor

            dados_extraidos.append(
                dados_item
            )

        except Exception as ex:
            _log(
                log,
                f"❌ [{cod_infra}] Erro na requisição: {ex}"
            )

        if i == 1 or i % 100 == 0 or i == total:
            _log(
                log,
                f"📌 Detalhamento concluído: {i}/{total}"
            )

        if i % 1000 == 0:
            _log(
                log,
                f"✅ {i} requisições concluídas em "
                f"{datetime.now().strftime('%d/%m/%Y %H:%M:%S')}"
            )

    df_resultado = pd.DataFrame(
        dados_extraidos
    )

    if not df_resultado.empty:
        df_resultado = (
            df_resultado
            .groupby("CodigoProcessoInfracao")
            .first()
            .reset_index()
        )

    fim = datetime.now()
    duracao = str(fim - inicio).split(".")[0]

    _log(
        log,
        f"✅ Detalhamento concluído em {duracao}. Total: {len(df_resultado)} registros."
    )

    return df_resultado