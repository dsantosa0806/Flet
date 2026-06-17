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
from requests_data.requisicoes_sior import get_dados_placa_sior
from utils.open_dir_downloads import abrir_pasta_exportacao
from utils.popups import mostrar_alerta


# ==========================================================
# ABA - CONSULTA SIOR PLACA
# ==========================================================
def aba_consulta_sior_placa(
    ft,
    DEFAULT_FONT_SIZE,
    HEADING_FONT_SIZE,
    page,
    bloquear,
    desbloquear
):

    tabela_resultados = []

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
    # INPUT PLACA
    # ==========================================================
    input_placa = ft.TextField(
        label="Placa do veículo (uma por linha)",
        multiline=True,
        min_lines=5,
        max_lines=10,
        height=150,
        visible=True,
        hint_text="Ex: HYQ0602 ou ABC1D23",
        label_style=ft.TextStyle(
            size=DEFAULT_FONT_SIZE
        ),
        text_style=ft.TextStyle(
            size=DEFAULT_FONT_SIZE
        )
    )

    # ==========================================================
    # EXPANDER
    # ==========================================================
    expander_input = ft.ExpansionTile(
        title=ft.Text(
            "📥 Inserir Placas para Consulta"
        ),
        initially_expanded=True,
        controls=[
            input_placa
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

    filtro_situacao_fase = ft.Dropdown(
        label="Filtrar por Situação Fase",
        options=[],
        width=250,
        visible=False
    )

    filtro_situacao_debito = ft.Dropdown(
        label="Filtrar por Situação Débito",
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
        "PlacaPesquisada",
        "NumeroAuto",
        "DataInfracao",
        "Proprietario",
        "Veiculo",
        "SituacaoFase",
        "SituacaoDebito",
        "ValorMultaFormatado",
        "ValorMulta",
        "VencimentoNP",
        "Enquadramento",
        "Municipio",
        "Local",
        "EquipamentoAfericao",
        "RegistroRENAINF",
        "CodigoRegistroRenainf",
        "MultaDesvinculada",
        "CodigoInfracao"
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
    # HELPERS
    # ==========================================================
    def extrair_valor_campo(valor):
        """
        Trata campos comuns da response do SIOR.

        Exemplo:
        DataInfracao e VencimentoNP retornam dicionário com DateString.
        """

        if (
            isinstance(valor, dict)
            and "DateString" in valor
        ):
            return valor.get(
                "DateString",
                ""
            )

        return valor

    def normalizar_placa(placa):
        """
        Remove caracteres especiais e padroniza a placa em maiúsculo.
        Exemplos:
        - hyq-0602 -> HYQ0602
        - abc1d23 -> ABC1D23
        """

        return re.sub(
            r"[^A-Za-z0-9]",
            "",
            str(placa or "")
        ).upper()

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
            filtro_situacao_fase,
            filtro_situacao_debito,
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

            if filtro_situacao_fase.value:

                filtro_ativo[
                    "SituacaoFase"
                ] = filtro_situacao_fase.value

            if filtro_situacao_debito.value:

                filtro_ativo[
                    "SituacaoDebito"
                ] = filtro_situacao_debito.value

            atualizar_tabela()

            loading_filtro.visible = False
            table.visible = True

            page.update()

        threading.Thread(
            target=task
        ).start()

    # ==========================================================
    # LIMPAR FILTROS
    # ==========================================================
    def limpar_filtros(e):

        nonlocal pagina_atual
        nonlocal filtro_ativo

        pagina_atual = 1

        filtro_ativo.clear()

        filtro_numero.value = ""

        filtro_situacao_fase.value = None

        filtro_situacao_debito.value = None

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
                f"Consulta_SIOR_Placa_{ts}.xlsx"
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

                df.to_excel(
                    writer,
                    sheet_name="Consulta Placa",
                    index=False
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
                "✅ Disponível na pasta Downloads. Abrindo local do arquivo...",
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
    # VALIDA PLACAS
    # ==========================================================
    def validar_placas(lista_placas):

        erros = []

        # ======================================
        # LIMITE
        # ======================================
        if len(lista_placas) > 100:
            erros.append(
                "Limite máximo de 100 placas por consulta."
            )

        # ======================================
        # CAMPO VAZIO
        # ======================================
        if len(lista_placas) == 0:
            erros.append(
                "Informe ao menos uma placa para consulta."
            )

        if len(set(lista_placas)) < len(lista_placas):
            erros.append("⚠ Existem Números duplicados.")

        # ======================================
        # PADRÕES ACEITOS
        # ======================================
        padrao_antigo = re.compile(
            r"^[A-Z]{3}[0-9]{4}$"
        )

        padrao_mercosul = re.compile(
            r"^[A-Z]{3}[0-9][A-Z][0-9]{2}$"
        )

        placas_normalizadas = []

        for idx, item in enumerate(lista_placas, 1):

            placa = normalizar_placa(item)

            if (
                padrao_antigo.match(placa)
                or padrao_mercosul.match(placa)
            ):
                placas_normalizadas.append(placa)

            else:
                erros.append(
                    f"Linha {idx}: "
                    f"Placa inválida ({item}). "
                    f"Use o padrão HYQ0602 ou ABC1D23."
                )

        return erros, placas_normalizadas

    # ==========================================================
    # CONSULTA
    # ==========================================================
    def run_consulta(e):

        nonlocal tabela_resultados
        nonlocal pagina_atual

        placas_informadas = [
            c.strip()
            for c in input_placa.value.splitlines()
            if c.strip()
        ]

        # ======================================
        # VALIDAÇÃO PLACAS
        # ======================================
        erros_validacao, placas = validar_placas(
            placas_informadas
        )

        if erros_validacao:

            page.dialog = alerta_dialogo

            mostrar_alerta(
                ft,
                page,
                "Validação de Placa",
                "\n".join(erros_validacao),
                tipo="error"
            )

            page.update()
            return

        tabela_resultados.clear()

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

                total_placas = len(placas)

                for idx_placa, placa in enumerate(
                    placas,
                    1
                ):

                    status.value = (
                        f"Consultando placa "
                        f"{idx_placa}/{total_placas}: {placa}"
                    )

                    if total_placas > 0:
                        progress.value = idx_placa / total_placas

                    page.update()

                    resposta = get_dados_placa_sior(
                        placa,
                        session
                    )

                    dados_response = resposta.get(
                        "Data",
                        []
                    )

                    total_response = resposta.get(
                        "Total",
                        len(dados_response)
                    )

                    log.value += (
                        f"📄 {placa} | "
                        f"{len(dados_response)} de {total_response} registros retornados.\n"
                    )

                    page.update()

                    for item in dados_response:

                        linha = {
                            "PlacaPesquisada": placa
                        }

                        for k in cols:

                            if k == "PlacaPesquisada":
                                continue

                            valor = item.get(k, "")

                            linha[k] = extrair_valor_campo(
                                valor
                            )

                        tabela_resultados.append(
                            linha
                        )

                filtro_situacao_fase.options = [
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

                filtro_situacao_debito.options = [
                    ft.dropdown.Option(
                        key=f,
                        text=f
                    )
                    for f in sorted({
                        r.get(
                            "SituacaoDebito",
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
                "SIOR > Consulta > Placa",
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

            filtro_situacao_fase,

            filtro_situacao_debito,

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