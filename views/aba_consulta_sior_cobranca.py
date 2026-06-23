# ==========================================================
# IMPORTS
# ==========================================================
import os
import re
import threading
from datetime import datetime

import pandas as pd

from navegador.sior_selenium_execution import iniciar_sessao_sior

from requests_data.requisicoes_sior import (
    get_dados_auto_cobranca,
    get_valor_corrigido
)
from utils.open_dir_downloads import abrir_pasta_exportacao

from utils.popups import mostrar_alerta


# ==========================================================
# ABA - CONSULTA AIT COBRANÇA
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
    # INPUT AIT
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

    # === FUNÇÕES AUXILIARES ===
    def validar_codigos(codigos):
        erros = []
        if not codigos:
            erros.append("⚠ É necessário inserir ao menos um código AIT.")
        if len(set(codigos)) < len(codigos):
            erros.append("⚠ Existem Número de AITs duplicados.")
        if len(codigos) > 2000:
            erros.append("⚠ Limite máximo de 2000 AITs por vez.")
        if any(" " in c for c in codigos):
            erros.append("⚠ Os Número de AIT não podem conter espaços.")
        if any(not re.match(r"^[A-Za-z][0-9]{9}$", c) for c in codigos):
            erros.append("⚠ Todos os Número de AITs devem ter o formato: Letra + 9 dígitos.")
        return erros

    # ==========================================================
    # TOGGLE FINANCEIRO
    # ==========================================================
    toggle_financeiro = ft.Switch(
        label="Buscar Valor Débito Atualizado?",
        value=False,
        visible=True
    )

    # ==========================================================
    # EXPANDER
    # ==========================================================
    expander_input = ft.ExpansionTile(
        title=ft.Text(
            "📥 Inserir Dados de Consulta"
        ),
        initially_expanded=True,
        controls=[
            input_consulta,

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
    # CONTAINER TABELA
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
                        d.get(chave, "")
                    ).lower()
                ]

            df = pd.DataFrame(
                dados_filtrados
            )

            ts = datetime.now().strftime(
                "%Y-%m-%d_%H-%M-%S"
            )

            nome_arquivo = (
                f"Consulta_AIT_Cobranca_{ts}.xlsx"
            )

            path = os.path.join(
                os.path.expanduser("~"),
                "Downloads",
                nome_arquivo
            )

            # ==================================================
            # HELPERS
            # ==================================================
            def normalizar_texto(valor):

                try:
                    if pd.isna(valor):
                        return ""
                except Exception:
                    pass

                return str(valor or "").strip()

            def normalizar_auto(valor):

                return (
                    normalizar_texto(valor)
                    .upper()
                )

            def moeda_para_float(valor):

                try:

                    if isinstance(valor, (int, float)):
                        if pd.isna(valor):
                            return 0.0

                        return float(valor)

                    texto = normalizar_texto(valor)

                    if not texto:
                        return 0.0

                    texto = re.sub(
                        r"[^\d,.-]",
                        "",
                        texto
                    )

                    if not texto:
                        return 0.0

                    # Formato brasileiro: 1.234,56
                    if "," in texto:
                        texto = (
                            texto
                            .replace(".", "")
                            .replace(",", ".")
                        )

                    # Formato numérico comum: 1234.56
                    else:
                        texto = texto.replace(",", "")

                    return float(texto)

                except Exception:
                    return 0.0

            def ajustar_planilha(
                worksheet,
                aplicar_moeda_colunas=None,
                aplicar_decimal_colunas=None
            ):

                aplicar_moeda_colunas = aplicar_moeda_colunas or []
                aplicar_decimal_colunas = aplicar_decimal_colunas or []

                moeda_format = "R$ #,##0.00"
                decimal_format = "0.0000"

                try:
                    worksheet.freeze_panes = "A2"
                    worksheet.auto_filter.ref = worksheet.dimensions
                except Exception:
                    pass

                # Cabeçalho
                try:
                    for cell in worksheet[1]:
                        cell.style = "Headline 3"
                except Exception:
                    pass

                # Formatação por nome da coluna
                try:
                    headers = {
                        cell.value: cell.column
                        for cell in worksheet[1]
                    }

                    for nome_coluna in aplicar_moeda_colunas:
                        col_idx = headers.get(nome_coluna)

                        if col_idx:
                            for row in worksheet.iter_rows(
                                min_row=2,
                                min_col=col_idx,
                                max_col=col_idx
                            ):
                                for cell in row:
                                    cell.number_format = moeda_format

                    for nome_coluna in aplicar_decimal_colunas:
                        col_idx = headers.get(nome_coluna)

                        if col_idx:
                            for row in worksheet.iter_rows(
                                min_row=2,
                                min_col=col_idx,
                                max_col=col_idx
                            ):
                                for cell in row:
                                    cell.number_format = decimal_format

                except Exception:
                    pass

                # Ajuste de largura
                try:
                    for column_cells in worksheet.columns:

                        max_length = 0
                        column_letter = column_cells[0].column_letter

                        for cell in column_cells:
                            try:
                                max_length = max(
                                    max_length,
                                    len(str(cell.value or ""))
                                )
                            except Exception:
                                pass

                        worksheet.column_dimensions[
                            column_letter
                        ].width = min(
                            max_length + 2,
                            45
                        )

                except Exception:
                    pass

            def criar_tabela_resumo(
                df_consulta,
                df_financeiro
            ):

                # ==========================================
                # Garante colunas necessárias no financeiro
                # ==========================================
                for coluna in [
                    "NumeroAuto",
                    "DevedorNumero",
                    "ValorOriginal",
                    "ValorCorrigido",
                    "FatorMultiplicador"
                ]:
                    if coluna not in df_financeiro.columns:
                        df_financeiro[coluna] = ""

                df_financeiro = df_financeiro.copy()

                df_financeiro["NumeroAuto"] = (
                    df_financeiro["NumeroAuto"]
                    .apply(normalizar_auto)
                )

                df_financeiro["DevedorNumero"] = (
                    df_financeiro["DevedorNumero"]
                    .apply(normalizar_texto)
                )

                df_financeiro["ValorOriginal"] = (
                    df_financeiro["ValorOriginal"]
                    .apply(moeda_para_float)
                )

                df_financeiro["ValorCorrigido"] = (
                    df_financeiro["ValorCorrigido"]
                    .apply(moeda_para_float)
                )

                # ==========================================
                # Consulta Cobrança: NumeroAuto x SituacaoFase
                # ==========================================
                if (
                    not df_consulta.empty
                    and "NumeroAuto" in df_consulta.columns
                    and "SituacaoFase" in df_consulta.columns
                ):

                    df_fase = df_consulta[
                        [
                            "NumeroAuto",
                            "SituacaoFase"
                        ]
                    ].copy()

                    df_fase["NumeroAuto"] = (
                        df_fase["NumeroAuto"]
                        .apply(normalizar_auto)
                    )

                    df_fase["SituacaoFase"] = (
                        df_fase["SituacaoFase"]
                        .apply(normalizar_texto)
                    )

                    df_fase = df_fase.drop_duplicates(
                        subset=[
                            "NumeroAuto"
                        ],
                        keep="first"
                    )

                else:

                    df_fase = pd.DataFrame(
                        columns=[
                            "NumeroAuto",
                            "SituacaoFase"
                        ]
                    )

                # ==========================================
                # Une Financeiro + Consulta Cobrança
                # Base: NumeroAuto
                # ==========================================
                df_base = pd.merge(
                    df_financeiro,
                    df_fase,
                    on="NumeroAuto",
                    how="left"
                )

                df_base["DevedorNumero"] = (
                    df_base["DevedorNumero"]
                    .replace("", "Não informado")
                    .fillna("Não informado")
                )

                df_base["SituacaoFase"] = (
                    df_base["SituacaoFase"]
                    .replace("", "Não informado")
                    .fillna("Não informado")
                )

                if df_base.empty:

                    return pd.DataFrame(
                        columns=[
                            "DevedorNumero",
                            "Total Geral"
                        ]
                    )

                # ==========================================
                # Pivot:
                # Linhas: DevedorNumero
                # Colunas: SituacaoFase
                # Valores: soma ValorCorrigido
                # ==========================================
                df_tabela = pd.pivot_table(
                    df_base,
                    index="DevedorNumero",
                    columns="SituacaoFase",
                    values="ValorCorrigido",
                    aggfunc="sum",
                    fill_value=0
                )

                df_tabela.columns.name = None

                df_tabela["Total Geral"] = (
                    df_tabela.sum(
                        axis=1
                    )
                )

                df_tabela = df_tabela.sort_values(
                    "Total Geral",
                    ascending=False
                )

                # Linha total por fase
                linha_total = (
                    df_tabela
                    .sum(numeric_only=True)
                    .to_frame()
                    .T
                )

                linha_total.index = [
                    "Total Geral"
                ]

                df_tabela = pd.concat(
                    [
                        df_tabela,
                        linha_total
                    ]
                )

                df_tabela = (
                    df_tabela
                    .reset_index()
                    .rename(
                        columns={
                            "index": "DevedorNumero"
                        }
                    )
                )

                return df_tabela

            with pd.ExcelWriter(
                path,
                engine="openpyxl"
            ) as writer:

                df_financeiro = pd.DataFrame()

                # ======================================
                # FINANCEIRO / TABELA RESUMO
                # A aba Tabela precisa ser criada primeiro
                # para aparecer como primeira aba no XLSX.
                # ======================================
                if toggle_financeiro.value:

                    df_financeiro = pd.DataFrame(
                        tabela_financeiro
                    )

                    df_tabela = criar_tabela_resumo(
                        df,
                        df_financeiro
                    )

                    df_tabela.to_excel(
                        writer,
                        sheet_name="Tabela",
                        index=False
                    )

                    worksheet_tabela = writer.sheets[
                        "Tabela"
                    ]

                    colunas_moeda_tabela = [
                        c
                        for c in df_tabela.columns
                        if c != "DevedorNumero"
                    ]

                    ajustar_planilha(
                        worksheet_tabela,
                        aplicar_moeda_colunas=colunas_moeda_tabela
                    )

                # ======================================
                # ABA PRINCIPAL
                # ======================================
                df.to_excel(
                    writer,
                    sheet_name="Consulta Cobranca",
                    index=False
                )

                ajustar_planilha(
                    writer.sheets[
                        "Consulta Cobranca"
                    ]
                )

                # ======================================
                # ABA FINANCEIRO
                # ======================================
                if toggle_financeiro.value:

                    if df_financeiro.empty:
                        df_financeiro = pd.DataFrame(
                            columns=[
                                "NumeroAuto",
                                "DevedorNumero",
                                "ValorOriginal",
                                "ValorCorrigido",
                                "FatorMultiplicador"
                            ]
                        )

                    for coluna in [
                        "ValorOriginal",
                        "ValorCorrigido"
                    ]:
                        if coluna in df_financeiro.columns:
                            df_financeiro[coluna] = (
                                df_financeiro[coluna]
                                .apply(moeda_para_float)
                            )

                    df_financeiro.to_excel(
                        writer,
                        sheet_name="Financeiro",
                        index=False
                    )

                    worksheet_financeiro = writer.sheets[
                        "Financeiro"
                    ]

                    ajustar_planilha(
                        worksheet_financeiro,
                        aplicar_moeda_colunas=[
                            "ValorOriginal",
                            "ValorCorrigido"
                        ],
                        aplicar_decimal_colunas=[
                            "FatorMultiplicador"
                        ]
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
                "✅ Disponível na pasta Downloads. Abrindo arquivo...",
                tipo="success"
            )

            abrir_pasta_exportacao(path)

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
    # CONSULTA
    # ==========================================================
    def run_consulta(e):

        nonlocal tabela_resultados
        nonlocal tabela_financeiro
        nonlocal pagina_atual

        codigos = [
            c.strip()
            for c in input_consulta.value.splitlines()
            if c.strip()
        ]

        codigos = [c.strip() for c in input_consulta.value.splitlines() if c.strip()]
        erros = validar_codigos(codigos)

        if erros:
            mostrar_alerta(
                ft,
                page,
                "Validação de CPF/CNPJ",
                "\n".join(erros),
                tipo="error"
            )
            page.update()
            return

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

                    if total > 0:
                        progress.value = idx / total

                    page.update()

                    resposta = (
                        get_dados_auto_cobranca(
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
                    # FINANCEIRO - APENAS AIT
                    # ==================================
                    if toggle_financeiro.value:

                        try:

                            financeiro = (
                                get_valor_corrigido(
                                    codigo,
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

                    except Exception:
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
