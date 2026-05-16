# ==========================================================
# IMPORTS
# ==========================================================
import os
import re
import time
import threading
from datetime import datetime

import pandas as pd

from navegador.sior_selenium_execution import iniciar_sessao_sior

from requests_data.requisicoes_sior import (
    get_dados_auto_cobranca,
    get_valor_corrigido
)

from utils.popups import mostrar_alerta


# ==========================================================
# REQUEST - DEVEDOR
# ==========================================================
def get_dados_devedor_cobranca(
    devedor,
    s,
    page=1,
    page_size=100
):

    try:

        timestamp = int(time.time() * 1000)

        url = (
            "https://servicos.dnit.gov.br/"
            "sior/Cobranca/CobrancaConsulta/List"
        )

        params = {

            "sort": "",
            "page": page,
            "pageSize": page_size,
            "group": "",
            "filter": "",
            "devedornome": devedor,
            "bind": "true",
            "calledfromapi": "true",
            "calledFromApi": "true",
            "_": timestamp
        }

        headers = {

            "Accept": "*/*",

            "Referer":
                "https://servicos.dnit.gov.br/"
                "sior/Cobranca/CobrancaConsulta",

            "X-Requested-With":
                "XMLHttpRequest",

            "User-Agent":
                "Mozilla/5.0 "
                "(Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 "
                "(KHTML, like Gecko) "
                "Chrome/148.0.0.0 Safari/537.36"
        }

        response = s.get(
            url,
            params=params,
            headers=headers,
            timeout=60
        )

        if response.status_code != 200:

            print(
                f"❌ Erro consulta devedor: "
                f"{response.status_code}"
            )

            return {
                "Data": []
            }

        return response.json()

    except Exception as ex:

        print(
            f"❌ Erro consulta devedor: {ex}"
        )

        return {
            "Data": []
        }


# ==========================================================
# PLACEHOLDER - NUP
# ==========================================================
def get_dados_nup_cobranca(
    nup,
    s
):

    print(
        f"⚠ Consulta NUP ainda não implementada: {nup}"
    )

    return {
        "Data": []
    }


# ==========================================================
# ABA
# ==========================================================
def aba_consulta_auto_cobranca(
    ft,
    DEFAULT_FONT_SIZE,
    HEADING_FONT_SIZE,
    page,
    bloquear,
    desbloquear
):

    tabela_resultados = []
    tabela_financeiro = []

    pagina_atual = 1
    itens_por_pagina = 3

    filtro_ativo = {}

    alerta_dialogo = ft.AlertDialog(
        modal=True,
        title=ft.Text(""),
        content=ft.Text(""),
        actions=[],
        open=False
    )

    # ==========================================================
    # TABS PESQUISA
    # ==========================================================
    tipo_pesquisa = ft.Tabs(
        selected_index=0,
        tabs=[

            ft.Tab(
                text="Pesquisa AIT"
            ),

            ft.Tab(
                text="Pesquisa Devedor"
            ),

            # ft.Tab(
            #     text="Pesquisa NUP"
            # )
        ]
    )

    # ==========================================================
    # INPUTS
    # ==========================================================
    input_consulta = ft.TextField(
        label="Número do AIT (um por linha)",
        multiline=True,
        min_lines=5,
        max_lines=10,
        height=150,
        visible=True,
        label_style=ft.TextStyle(
            size=DEFAULT_FONT_SIZE
        ),
        text_style=ft.TextStyle(
            size=DEFAULT_FONT_SIZE
        )
    )

    input_devedor = ft.TextField(
        label="CPF/CNPJ (um por linha)",
        multiline=True,
        min_lines=5,
        max_lines=10,
        height=150,
        visible=False,
        label_style=ft.TextStyle(
            size=DEFAULT_FONT_SIZE
        ),
        text_style=ft.TextStyle(
            size=DEFAULT_FONT_SIZE
        )
    )

    input_nup = ft.TextField(
        label="NUP (um por linha)",
        multiline=True,
        min_lines=5,
        max_lines=10,
        height=150,
        visible=False,
        label_style=ft.TextStyle(
            size=DEFAULT_FONT_SIZE
        ),
        text_style=ft.TextStyle(
            size=DEFAULT_FONT_SIZE
        )
    )

    # ==========================================================
    # TOGGLE FINANCEIRO
    # ==========================================================
    toggle_financeiro = ft.Switch(
        label="Buscar Valor Débito Atualizado?",
        value=False,
        visible=True
    )

    # ==========================================================
    # ALTERA INPUTS
    # ==========================================================
    def alterar_tipo_pesquisa(e):

        idx = tipo_pesquisa.selected_index

        # ======================================
        # INPUTS
        # ======================================
        input_consulta.visible = idx == 0
        input_devedor.visible = idx == 1
        input_nup.visible = idx == 2

        # ======================================
        # TOGGLE FINANCEIRO
        # SOMENTE PESQUISA AIT
        # ======================================
        toggle_financeiro.visible = idx == 0

        # ======================================
        # SE TROCAR DE ABA
        # DESMARCA AUTOMATICAMENTE
        # ======================================
        if idx != 0:
            toggle_financeiro.value = False

        page.update()

    tipo_pesquisa.on_change = alterar_tipo_pesquisa

    # ==========================================================
    # EXPANDER
    # ==========================================================
    expander_input = ft.ExpansionTile(
        title=ft.Text(
            "📥 Inserir Dados de Consulta"
        ),
        initially_expanded=True,
        controls=[

            tipo_pesquisa,

            input_consulta,

            input_devedor,

            input_nup,

            ft.Container(height=10),

            toggle_financeiro
        ],
    )

    # ==========================================================
    # BOTÕES
    # ==========================================================
    btn_consultar = ft.ElevatedButton(
        "Iniciar Consulta",
        icon=ft.Icons.SEARCH,
        bgcolor="green",
        color="white"
    )

    progress = ft.ProgressBar(
        width=400,
        visible=False
    )

    status = ft.Text(
        "",
        size=DEFAULT_FONT_SIZE,
        color="blue",
        visible=False
    )

    log = ft.TextField(
        label="📝 Log",
        multiline=True,
        read_only=True,
        expand=True,
        height=200,
        label_style=ft.TextStyle(
            size=DEFAULT_FONT_SIZE
        ),
        text_style=ft.TextStyle(
            size=DEFAULT_FONT_SIZE
        )
    )

    # ==========================================================
    # FILTROS
    # ==========================================================
    filtro_numero = ft.TextField(
        label="Filtrar por Número",
        visible=False,
        width=200
    )

    filtro_tipo = ft.Dropdown(
        label="Filtrar por Tipo Recuperação",
        options=[],
        width=250,
        visible=False
    )

    filtro_situacao = ft.Dropdown(
        label="Filtrar por Situação Fase",
        options=[],
        width=250,
        visible=False
    )

    btn_filtrar = ft.ElevatedButton(
        "🔍 Filtrar Tabela",
        visible=False
    )

    btn_limpar = ft.ElevatedButton(
        "Limpar Filtros",
        visible=False
    )

    loading_filtro = ft.Row(
        [ft.ProgressRing()],
        alignment="center",
        visible=False
    )

    # ==========================================================
    # PAGINAÇÃO
    # ==========================================================
    total_text = ft.Text(
        "Total de registros: 0",
        size=DEFAULT_FONT_SIZE
    )

    paginador_text = ft.Text(
        size=DEFAULT_FONT_SIZE
    )

    btn_anterior = ft.ElevatedButton(
        "⬅ Anterior",
        visible=False
    )

    btn_proximo = ft.ElevatedButton(
        "Próxima ➡",
        visible=False
    )

    btn_export = ft.ElevatedButton(
        "📤 Exportar XLSX",
        icon=ft.Icons.SAVE,
        visible=False
    )

    msg_export = ft.Text(
        "",
        color="green",
        size=DEFAULT_FONT_SIZE,
        visible=False
    )

    # ==========================================================
    # COLUNAS
    # ==========================================================
    cols = [

        "NumeroAuto",
        "Devedor",
        "TipoRecuperacaoCredito",
        "NUPFormatado",
        "DataConstituicaoDefinitiva",
        "ValorOriginal",
        "Enquadramento",
        "SituacaoFase"
    ]

    table = ft.DataTable(

        columns=[

            ft.DataColumn(
                ft.Text(
                    c,
                    size=DEFAULT_FONT_SIZE
                )
            )

            for c in cols
        ],

        rows=[],

        expand=True,

        visible=False,

        data_text_style=ft.TextStyle(
            size=DEFAULT_FONT_SIZE
        )
    )

    # ==========================================================
    # TABELA
    # ==========================================================
    def atualizar_tabela():

        table.rows.clear()

        dados = tabela_resultados

        for chave, valor in filtro_ativo.items():

            dados = [

                d for d in dados

                if valor.lower()
                in str(
                    d.get(chave, "")
                ).lower()
            ]

        total = len(dados)

        total_text.value = (
            f"Total de registros: {total}"
        )

        total_paginas = max(
            1,
            (
                total + itens_por_pagina - 1
            ) // itens_por_pagina
        )

        nonlocal pagina_atual

        pagina_atual = max(
            1,
            min(
                pagina_atual,
                total_paginas
            )
        )

        inicio = (
            pagina_atual - 1
        ) * itens_por_pagina

        fim = inicio + itens_por_pagina

        for row in dados[inicio:fim]:

            table.rows.append(

                ft.DataRow(
                    cells=[

                        ft.DataCell(
                            ft.Text(
                                str(
                                    row.get(k, "")
                                ),
                                size=DEFAULT_FONT_SIZE
                            )
                        )

                        for k in cols
                    ]
                )
            )

        for w in [

            filtro_numero,
            filtro_tipo,
            filtro_situacao,
            btn_filtrar,
            btn_limpar
        ]:
            w.visible = True

        vis = total > 0

        for w in [

            table,
            total_text,
            paginador_text,
            btn_anterior,
            btn_proximo,
            btn_export,
            container_tabela
        ]:
            w.visible = vis

        btn_anterior.disabled = (
            pagina_atual == 1
        )

        btn_proximo.disabled = (
            pagina_atual == total_paginas
        )

        paginador_text.value = (
            f"{pagina_atual}/{total_paginas}"
        )

        page.update()

    # ==========================================================
    # FILTROS
    # ==========================================================
    def aplicar_filtro(e):

        def task():

            nonlocal pagina_atual

            loading_filtro.visible = True
            table.visible = False

            page.update()

            pagina_atual = 1

            filtro_ativo.clear()

            if filtro_numero.value.strip():

                filtro_ativo[
                    "NumeroAuto"
                ] = filtro_numero.value.strip()

            if filtro_tipo.value:

                filtro_ativo[
                    "TipoRecuperacaoCredito"
                ] = filtro_tipo.value

            if filtro_situacao.value:

                filtro_ativo[
                    "SituacaoFase"
                ] = filtro_situacao.value

            atualizar_tabela()

            loading_filtro.visible = False
            table.visible = True

            page.update()

        threading.Thread(
            target=task
        ).start()

    # ==========================================================
    # LIMPAR
    # ==========================================================
    def limpar_filtros(e):

        nonlocal pagina_atual
        nonlocal filtro_ativo

        pagina_atual = 1

        filtro_ativo.clear()

        filtro_numero.value = ""

        filtro_tipo.value = None

        filtro_situacao.value = None

        atualizar_tabela()

    # ==========================================================
    # PAGINAÇÃO
    # ==========================================================
    def pagina_anterior(e):

        nonlocal pagina_atual

        pagina_atual = max(
            1,
            pagina_atual - 1
        )

        atualizar_tabela()

    def pagina_proxima(e):

        nonlocal pagina_atual

        pagina_atual += 1

        atualizar_tabela()

    # ==========================================================
    # EXPORTAR
    # ==========================================================
    def exportar_xlsx(e):

        try:

            dados_filtrados = tabela_resultados

            for chave, valor in filtro_ativo.items():

                dados_filtrados = [

                    d for d in dados_filtrados

                    if valor.lower()
                    in str(
                        d.get(chave, '')
                    ).lower()
                ]

            df = pd.DataFrame(
                dados_filtrados
            )

            ts = datetime.now().strftime(
                "%Y-%m-%d_%H-%M-%S"
            )

            nome_arquivo = (
                f"Consulta_AIT_Cobranca{ts}.xlsx"
            )

            path = os.path.join(
                os.path.expanduser("~"),
                "Downloads",
                nome_arquivo
            )

            with pd.ExcelWriter(
                path,
                engine="openpyxl"
            ) as writer:

                # ======================================
                # ABA PRINCIPAL
                # ======================================
                df.to_excel(
                    writer,
                    sheet_name="Consulta Cobranca",
                    index=False
                )

                # ======================================
                # FINANCEIRO
                # ======================================
                if toggle_financeiro.value:

                    df_financeiro = pd.DataFrame(
                        tabela_financeiro
                    )

                    def moeda_para_float(valor):

                        try:

                            valor = str(valor)

                            valor = re.sub(
                                r"[^\d,.-]",
                                "",
                                valor
                            )

                            valor = (
                                valor
                                .replace(".", "")
                                .replace(",", ".")
                            )

                            return float(valor)

                        except:
                            return 0.0

                    if (
                        "ValorOriginal"
                        in df_financeiro.columns
                    ):

                        df_financeiro[
                            "ValorOriginal"
                        ] = (

                            df_financeiro[
                                "ValorOriginal"
                            ].apply(
                                moeda_para_float
                            )
                        )

                    if (
                        "ValorCorrigido"
                        in df_financeiro.columns
                    ):

                        df_financeiro[
                            "ValorCorrigido"
                        ] = (

                            df_financeiro[
                                "ValorCorrigido"
                            ].apply(
                                moeda_para_float
                            )
                        )

                    df_financeiro.to_excel(
                        writer,
                        sheet_name="Financeiro",
                        index=False
                    )

                    workbook = writer.book

                    worksheet = writer.sheets[
                        "Financeiro"
                    ]

                    moeda_format = (
                        'R$ #,##0.00'
                    )

                    for cell in worksheet["C"][1:]:

                        cell.number_format = (
                            moeda_format
                        )

                    for cell in worksheet["D"][1:]:

                        cell.number_format = (
                            moeda_format
                        )

                    for cell in worksheet["E"][1:]:

                        cell.number_format = (
                            '0.0000'
                        )

            page.dialog = alerta_dialogo

            msg_export.value = (
                "📤 Exportação concluída "
                "com sucesso!"
            )

            mostrar_alerta(

                ft,
                page,

                "Exportado com sucesso",

                "✅ Disponível em "
                "C:\\Downloads",

                tipo="success"
            )

            msg_export.color = "green"

            msg_export.visible = True

            page.update()

        except Exception as ex:

            msg_export.value = (
                f"❌ Falha ao exportar: {ex}"
            )

            msg_export.color = "red"

            msg_export.visible = True

            page.update()

    # ==========================================================
    # VALIDA CPF/CNPJ
    # ==========================================================
    def validar_devedores(lista_devedores):

        erros = []

        # ======================================
        # LIMITE
        # ======================================
        if len(lista_devedores) > 100:
            erros.append(
                "Limite máximo de 100 CPF/CNPJ por consulta."
            )

        # ======================================
        # VALIDAÇÕES
        # ======================================
        for idx, item in enumerate(lista_devedores, 1):

            documento = re.sub(
                r"\D",
                "",
                item
            )

            # CPF
            if len(documento) == 11:
                continue

            # CNPJ
            elif len(documento) == 14:
                continue

            else:

                erros.append(
                    f"Linha {idx}: "
                    f"CPF/CNPJ inválido ({item})"
                )

        return erros

    # ==========================================================
    # CONSULTA
    # ==========================================================
    def run_consulta(e):

        nonlocal tabela_resultados
        nonlocal tabela_financeiro
        nonlocal pagina_atual

        idx_tab = tipo_pesquisa.selected_index

        # ======================================
        # AIT
        # ======================================
        if idx_tab == 0:

            codigos = [

                c.strip()

                for c in input_consulta.value.splitlines()

                if c.strip()
            ]

        # ======================================
        # DEVEDOR
        # ======================================
        elif idx_tab == 1:

            codigos = [

                c.strip()

                for c in input_devedor.value.splitlines()

                if c.strip()
            ]

            # ======================================
            # VALIDAÇÃO CPF/CNPJ
            # ======================================
            erros_validacao = validar_devedores(
                codigos
            )

            if erros_validacao:
                mostrar_alerta(

                    ft,
                    page,

                    "Validação de CPF/CNPJ",

                    "\n".join(erros_validacao),

                    tipo="error"
                )

                return

        # ======================================
        # NUP
        # ======================================
        else:

            codigos = [

                c.strip()

                for c in input_nup.value.splitlines()

                if c.strip()
            ]

        tabela_resultados.clear()
        tabela_financeiro.clear()

        pagina_atual = 1

        status.visible = True
        status.value = "Iniciando..."

        progress.visible = True
        progress.value = 0

        btn_consultar.disabled = True
        btn_consultar.text = "Consultando..."

        table.visible = False

        log.value = ""

        page.update()

        def task():

            navegador = None

            try:

                bloquear()

                log.value += (
                    "🔐 Iniciando sessão SIOR...\n"
                )

                status.value = (
                    "🔐 Iniciando sessão SIOR..."
                )

                page.update()

                def adicionar_log(mensagem):

                    log.value += (
                        f"{mensagem}\n"
                    )

                    status.value = mensagem

                    page.update()

                navegador, session = iniciar_sessao_sior(
                    log=adicionar_log
                )

                log.value += (
                    "✅ Sessão iniciada com sucesso.\n"
                )

                page.update()

                total = len(codigos)

                for idx, codigo in enumerate(
                    codigos,
                    1
                ):

                    status.value = (
                        f"Consultando "
                        f"{idx}/{total}: {codigo}"
                    )

                    progress.value = idx / total

                    page.update()

                    # ==================================
                    # AIT
                    # ==================================
                    if idx_tab == 0:

                        resposta = (
                            get_dados_auto_cobranca(
                                codigo,
                                session
                            )
                        )

                    # ==================================
                    # DEVEDOR
                    # ==================================
                    elif idx_tab == 1:

                        resposta = (
                            get_dados_devedor_cobranca(
                                codigo,
                                session
                            )
                        )

                    # ==================================
                    # NUP
                    # ==================================
                    else:

                        resposta = (
                            get_dados_nup_cobranca(
                                codigo,
                                session
                            )
                        )

                    for item in resposta.get(
                        "Data",
                        []
                    ):

                        linha = {}

                        for k in cols:

                            valor = item.get(k, "")

                            if (
                                isinstance(valor, dict)
                                and "DateString" in valor
                            ):

                                linha[k] = valor[
                                    "DateString"
                                ]

                            else:

                                linha[k] = valor

                        tabela_resultados.append(
                            linha
                        )

                    # ==================================
                    # FINANCEIRO
                    # ==================================
                    if toggle_financeiro.value:

                        try:

                            numero_auto = None

                            if idx_tab == 0:

                                numero_auto = codigo

                            else:

                                dados = resposta.get(
                                    "Data",
                                    []
                                )

                                if dados:

                                    numero_auto = (
                                        dados[0].get(
                                            "NumeroAuto"
                                        )
                                    )

                            if numero_auto:

                                financeiro = (
                                    get_valor_corrigido(
                                        numero_auto,
                                        session
                                    )
                                )

                                if financeiro:

                                    tabela_financeiro.append({

                                        "NumeroAuto":
                                            financeiro.get(
                                                "NumeroAuto",
                                                ""
                                            ),

                                        "DevedorNumero":
                                            financeiro.get(
                                                "DevedorNumero",
                                                ""
                                            ),

                                        "ValorOriginal":
                                            financeiro.get(
                                                "ValorOriginal",
                                                ""
                                            ),

                                        "ValorCorrigido":
                                            financeiro.get(
                                                "ValorCorrigido",
                                                ""
                                            ),

                                        "FatorMultiplicador":
                                            financeiro.get(
                                                "FatorMultiplicador",
                                                ""
                                            )
                                    })

                        except Exception as ex:

                            log.value += (
                                f"❌ Erro financeiro: "
                                f"{ex}\n"
                            )

                            page.update()

                filtro_tipo.options = [

                    ft.dropdown.Option(
                        key=f,
                        text=f
                    )

                    for f in sorted({

                        r.get(
                            "TipoRecuperacaoCredito",
                            ""
                        )

                        for r in tabela_resultados

                    })

                    if f
                ]

                filtro_situacao.options = [

                    ft.dropdown.Option(
                        key=f,
                        text=f
                    )

                    for f in sorted({

                        r.get(
                            "SituacaoFase",
                            ""
                        )

                        for r in tabela_resultados

                    })

                    if f
                ]

                atualizar_tabela()

                status.value = (
                    "✅ Consulta concluída"
                )

                page.update()

            except Exception as ex:

                log.value += (
                    f"\n❌ Erro durante execução: "
                    f"{ex}\n"
                )

                status.value = (
                    "❌ Erro durante execução"
                )

                page.update()

            finally:

                if navegador:

                    try:

                        navegador.quit()

                    except:
                        pass

                btn_consultar.disabled = False

                btn_consultar.text = (
                    "Nova Consulta"
                )

                progress.visible = False

                expander_input.initially_expanded = False
                expander_input.expanded = False

                desbloquear()

                page.update()

        threading.Thread(
            target=task
        ).start()

    # ==========================================================
    # EVENTS
    # ==========================================================
    btn_consultar.on_click = run_consulta
    btn_filtrar.on_click = aplicar_filtro
    btn_limpar.on_click = limpar_filtros
    btn_anterior.on_click = pagina_anterior
    btn_proximo.on_click = pagina_proxima
    btn_export.on_click = exportar_xlsx

    # ==========================================================
    # CONTAINER
    # ==========================================================
    container_tabela = ft.Container(

        content=table,

        height=250,

        padding=10,

        border_radius=10,

        border=ft.border.all(
            1,
            ft.Colors.GREY_600
        ),

        bgcolor=ft.Colors.with_opacity(
            0.05,
            ft.Colors.ON_SURFACE
        ),

        visible=False
    )

    # ==========================================================
    # RETURN
    # ==========================================================
    return ft.Column([

        ft.Row([

            ft.Text(

                "SIOR > Consultar Auto de "
                "Infração Cobrança",

                size=10,

                weight="bold"
            )

        ], alignment="center"),

        ft.Divider(),

        expander_input,

        ft.Row(
            [btn_consultar],
            alignment="center"
        ),

        status,

        progress,

        ft.Row([

            filtro_numero,

            filtro_tipo,

            filtro_situacao,

            btn_filtrar,

            btn_limpar,

            btn_export

        ], alignment="center"),

        loading_filtro,

        container_tabela,

        ft.Row([

            btn_anterior,

            paginador_text,

            btn_proximo,

            total_text

        ], alignment="center"),

        msg_export,

        log,

        alerta_dialogo

    ], expand=True)