# ==========================================================
# ABA - SIOR DISTRIBUIÇÃO AUTOMÁTICA DE PROCESSOS
# Disponível para todos os usuários
# ==========================================================
import os
import threading
import traceback
from datetime import datetime

import pandas as pd

import config
from selenium.webdriver.common.by import By

from navegador.sior_selenium_execution import (
    iniciar_sessao_sior,
    encerrar_navegador_sior,
    safe_get,
    sincronizar_cookies_navegador_para_session,
)

from requests_data.requisicoes_sior_distribuicao import (
    URL_DISTRIBUICAO_PAGE,
    FASE_APTA_DISTRIBUICAO,
    preparar_headers_distribuicao,
    inicializar_tela_distribuicao,
    listar_tecnicos_distribuicao,
    get_acompanhamento_distribuicao_sior,
    listar_processos_aptos_distribuicao,
    montar_df_quantitativos,
    montar_comparativo_quantitativos,
    gerar_plano_distribuicao,
    executar_distribuicao_por_plano,
    montar_insights_distribuicao,
    exportar_distribuicao_completa_excel,
)

from utils.open_dir_downloads import abrir_pasta_exportacao
from utils.popups import mostrar_alerta


# ==========================================================
# ABA
# ==========================================================
def aba_sior_distribuicao_processos(
    ft,
    DEFAULT_FONT_SIZE,
    HEADING_FONT_SIZE,
    page,
    bloquear,
    desbloquear,
):
    alerta_dialogo = ft.AlertDialog(
        modal=True,
        title=ft.Text(""),
        content=ft.Text(""),
        actions=[],
        open=False,
    )

    page.dialog = alerta_dialogo

    pasta_base_saida = getattr(
        config,
        "PASTA_EXPORT_ADMIN",
        r"C:\Downloads",
    )

    os.makedirs(
        pasta_base_saida,
        exist_ok=True,
    )

    estado = {
        "session": None,
        "equipe_id": None,
        "tecnicos": [],
        "dados_painel_antes": [],
        "dados_painel_depois": [],
        "dados_processos_aptos": [],
        "df_quant_antes": pd.DataFrame(),
        "df_quant_depois": pd.DataFrame(),
        "df_comparativo": pd.DataFrame(),
        "df_plano": pd.DataFrame(),
        "df_logs_request": pd.DataFrame(),
        "logs_interface": [],
        "caminho_saida": None,
        "execucao_concluida": False,
    }

    linhas_tecnicos_estado = []

    # ======================================================
    # UX COMPACTA
    # ======================================================
    # Mantém a fonte normal da página e reduz apenas os dados
    # dos cards de distribuição por técnico.
    UI_FONT = DEFAULT_FONT_SIZE
    UI_FONT_SMALL = max(DEFAULT_FONT_SIZE - 1, 10)
    UI_FONT_TINY = max(DEFAULT_FONT_SIZE - 2, 9)

    CARD_FONT = max(DEFAULT_FONT_SIZE - 3, 8)
    CARD_FONT_SMALL = max(DEFAULT_FONT_SIZE - 4, 8)
    CARD_FONT_TINY = max(DEFAULT_FONT_SIZE - 5, 7)

    # Fonte específica da tabela de distribuição.
    # Mantém a página compacta, mas deixa a tabela no mesmo padrão visual dos botões.
    TABELA_FONT = UI_FONT
    TABELA_FONT_SMALL = UI_FONT

    # ======================================================
    # CONTROLES PRINCIPAIS
    # ======================================================
    dropdown_equipes = ft.Dropdown(
        label="Equipe do supervisor",
        options=[
            ft.dropdown.Option(key="2", text="Equipe Cobrança 1"),
            ft.dropdown.Option(key="1", text="Equipe Cobrança 2"),
            ft.dropdown.Option(key="3", text="Equipe Cobrança 3"),
            ft.dropdown.Option(key="4", text="Equipe Cobrança 4"),
            ft.dropdown.Option(key="5", text="Equipe Cobrança 5"),
            ft.dropdown.Option(key="6", text="Equipe Cobrança 6"),
        ],
        width=260,
        value="2",
        label_style=ft.TextStyle(
            size=UI_FONT,
        ),
        text_style=ft.TextStyle(
            size=UI_FONT,
        ),
    )

    input_meta_padrao = ft.TextField(
        label="Quantidade a distribuir",
        value="50",
        width=230,
        height=42,
        hint_text="1 a 200 por técnico",
        label_style=ft.TextStyle(
            size=UI_FONT,
        ),
        text_style=ft.TextStyle(
            size=UI_FONT,
        ),
        content_padding=ft.padding.symmetric(horizontal=10, vertical=6),
    )

    txt_saida = ft.Text(
        f"📁 Saída padrão: {pasta_base_saida}",
        size=UI_FONT_SMALL,
        color=ft.Colors.GREY_600,
        selectable=True,
    )

    txt_resumo_carga = ft.Text(
        "",
        size=UI_FONT_SMALL,
        visible=False,
        selectable=True,
    )

    txt_resumo_final = ft.Text(
        "",
        size=UI_FONT_SMALL,
        visible=False,
        selectable=True,
    )

    btn_entenda_mais = ft.ElevatedButton(
        "Entenda mais",
        icon=ft.Icons.HELP_OUTLINE,
        bgcolor=ft.Colors.INDIGO_600,
        color="white",
        height=34,
        tooltip="Entenda como funciona a distribuição automática",
    )

    btn_carregar = ft.ElevatedButton(
        "Carregar equipe",
        icon=ft.Icons.DOWNLOAD,
        bgcolor="blue",
        color="white",
        height=34,
    )

    # O plano agora é gerado automaticamente dentro do botão Executar distribuição.
    # Mantemos a referência apenas para evitar impacto em fluxos internos antigos,
    # mas o botão não é exibido ao usuário.
    btn_gerar_plano = ft.ElevatedButton(
        "Gerar plano de distribuição",
        icon=ft.Icons.ACCOUNT_TREE_OUTLINED,
        bgcolor="green",
        color="white",
        disabled=True,
        visible=False,
    )

    btn_executar = ft.ElevatedButton(
        "Executar distribuição",
        icon=ft.Icons.PLAY_ARROW,
        bgcolor=ft.Colors.RED_600,
        color="white",
        height=34,
        disabled=True,
        visible=False,
    )

    btn_abrir_logs = ft.ElevatedButton(
        "Abrir XLSX gerado",
        icon=ft.Icons.TABLE_VIEW,
        visible=False,
        height=34,
    )

    btn_limpar = ft.ElevatedButton(
        "Limpar",
        icon=ft.Icons.CLEANING_SERVICES,
        height=34,
    )

    btn_marcar_todos = ft.ElevatedButton(
        "Selecionar todos",
        icon=ft.Icons.SELECT_ALL,
        visible=False,
        height=34,
    )

    btn_desmarcar_todos = ft.ElevatedButton(
        "Desmarcar todos",
        icon=ft.Icons.DESELECT,
        visible=False,
        height=34,
    )

    progress = ft.ProgressBar(
        width=420,
        visible=False,
    )

    status = ft.Text(
        "",
        size=UI_FONT_SMALL,
        color="blue",
        visible=False,
    )

    log_execucao = ft.TextField(
        label="Detalhes da execução",
        multiline=True,
        read_only=True,
        expand=True,
        min_lines=9,
        max_lines=9,
        label_style=ft.TextStyle(
            size=UI_FONT,
        ),
        text_style=ft.TextStyle(
            size=UI_FONT_SMALL,
        ),
    )

    linhas_tecnicos = ft.Column(
        controls=[],
        spacing=3,
        visible=False,
        tight=True,
    )

    txt_qtd_aptos = ft.Text(
        "0",
        size=UI_FONT + 6,
        weight="bold",
        color=ft.Colors.WHITE,
    )

    txt_desc_aptos = ft.Text(
        "processos aptos à distribuição",
        size=UI_FONT_SMALL,
        color=ft.Colors.WHITE,
    )

    card_aptos = ft.Container(
        content=ft.Row(
            [
                ft.Icon(
                    ft.Icons.INVENTORY_2_OUTLINED,
                    color=ft.Colors.WHITE,
                    size=26,
                ),
                ft.Column(
                    [
                        ft.Text(
                            "Aptos",
                            size=UI_FONT_SMALL,
                            weight="bold",
                            color=ft.Colors.WHITE,
                        ),
                        txt_qtd_aptos,
                        txt_desc_aptos,
                    ],
                    spacing=0,
                ),
            ],
            spacing=10,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        ),
        width=260,
        padding=ft.padding.symmetric(horizontal=12, vertical=8),
        border_radius=12,
        bgcolor=ft.Colors.BLUE_600,
        visible=False,
    )

    cabecalho_tecnicos = ft.Container(
        content=ft.Row(
            [
                ft.Container(width=34, content=ft.Text("Sel.", size=TABELA_FONT_SMALL, weight="bold")),
                ft.Container(width=235, content=ft.Text("Analisador", size=TABELA_FONT_SMALL, weight="bold")),
                ft.Container(width=235, content=ft.Text("Conferidor", size=TABELA_FONT_SMALL, weight="bold")),
                ft.Container(width=82, content=ft.Text("Análise painel", size=TABELA_FONT_SMALL, weight="bold")),
                ft.Container(width=92, content=ft.Text("Conferência painel", size=TABELA_FONT_SMALL, weight="bold")),
                ft.Container(width=70, content=ft.Text("Total painel", size=TABELA_FONT_SMALL, weight="bold")),
                ft.Container(width=92, content=ft.Text("Total após distrib.", size=TABELA_FONT_SMALL, weight="bold")),
                ft.Container(width=92, content=ft.Text("Status", size=TABELA_FONT_SMALL, weight="bold")),
                ft.Container(width=112, content=ft.Text("Quantidade a distribuir", size=TABELA_FONT_SMALL, weight="bold")),
            ],
            spacing=6,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        ),
        padding=ft.padding.symmetric(horizontal=6, vertical=3),
        border_radius=6,
        bgcolor=ft.Colors.with_opacity(0.04, ft.Colors.ON_SURFACE),
        visible=False,
    )

    container_tecnicos = ft.Column(
        [
            ft.Text(
                "👥 Distribuição por analisador/conferidor",
                size=UI_FONT,
                weight="bold",
            ),
            ft.Text(
                "Informe de 1 a 200 autos por linha. Por padrão, analisador = conferidor, mas é editável.",
                size=UI_FONT_TINY,
                color=ft.Colors.GREY_600,
            ),
            card_aptos,
            ft.Row(
                [
                    btn_marcar_todos,
                    btn_desmarcar_todos,
                ],
                wrap=True,
                spacing=8,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                tight=True,
            ),
            cabecalho_tecnicos,
            linhas_tecnicos,
        ],
        spacing=4,
        tight=True,
        visible=False,
    )

    tabela_resumo_plano = ft.DataTable(
        columns=[
            ft.DataColumn(ft.Text("Analisador", size=UI_FONT_SMALL)),
            ft.DataColumn(ft.Text("Conferidor", size=UI_FONT_SMALL)),
            ft.DataColumn(ft.Text("Qtd informada", size=UI_FONT_SMALL)),
            ft.DataColumn(ft.Text("Atual", size=UI_FONT_SMALL)),
            ft.DataColumn(ft.Text("A distribuir", size=UI_FONT_SMALL)),
            ft.DataColumn(ft.Text("Planejado", size=UI_FONT_SMALL)),
            ft.DataColumn(ft.Text("Devedores", size=UI_FONT_SMALL)),
            ft.DataColumn(ft.Text("Quebras", size=UI_FONT_SMALL)),
        ],
        rows=[],
        visible=False,
        data_text_style=ft.TextStyle(
            size=UI_FONT_SMALL,
        ),
    )

    container_resumo_plano = ft.Container(
        content=ft.Column(
            [
                ft.Text(
                    "📌 Resumo da distribuição automática",
                    size=UI_FONT,
                    weight="bold",
                ),
                tabela_resumo_plano,
            ],
            spacing=10,
            scroll=ft.ScrollMode.AUTO,
        ),
        padding=6,
        border_radius=10,
        border=ft.border.all(
            1,
            ft.Colors.GREY_600,
        ),
        bgcolor=None,
        visible=False,
    )

    tabela_painel_final = ft.DataTable(
        columns=[
            ft.DataColumn(ft.Text("Técnico", size=DEFAULT_FONT_SIZE)),
            ft.DataColumn(ft.Text("Análise antes", size=DEFAULT_FONT_SIZE)),
            ft.DataColumn(ft.Text("Análise depois", size=DEFAULT_FONT_SIZE)),
            ft.DataColumn(ft.Text("Δ Análise", size=DEFAULT_FONT_SIZE)),
            ft.DataColumn(ft.Text("Conf. antes", size=DEFAULT_FONT_SIZE)),
            ft.DataColumn(ft.Text("Conf. depois", size=DEFAULT_FONT_SIZE)),
            ft.DataColumn(ft.Text("Δ Conf.", size=DEFAULT_FONT_SIZE)),
            ft.DataColumn(ft.Text("Δ Total", size=DEFAULT_FONT_SIZE)),
        ],
        rows=[],
        visible=False,
        data_text_style=ft.TextStyle(
            size=UI_FONT_SMALL,
        ),
    )

    container_painel_final = ft.Container(
        content=ft.Column(
            [
                ft.Text(
                    "📊 Painel atualizado após distribuição",
                    size=UI_FONT,
                    weight="bold",
                ),
                tabela_painel_final,
            ],
            spacing=10,
            scroll=ft.ScrollMode.AUTO,
        ),
        padding=6,
        border_radius=10,
        border=ft.border.all(
            1,
            ft.Colors.GREY_600,
        ),
        bgcolor=None,
        visible=False,
    )

    # ======================================================
    # HELPERS UI
    # ======================================================
    def adicionar_log(mensagem: str):
        try:
            horario = datetime.now().strftime(
                "%H:%M:%S"
            )

            log_execucao.value += (
                f"[{horario}] {mensagem}\n"
            )

            estado["logs_interface"].append(
                {
                    "DataHora": datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
                    "Mensagem": mensagem,
                }
            )

            status.value = mensagem
            status.visible = True

            page.update()

        except Exception:
            pass

    def set_processando(processando: bool, texto_status: str = None):
        btn_carregar.disabled = processando
        btn_gerar_plano.disabled = True
        btn_executar.disabled = (
            processando
            or not estado["dados_processos_aptos"]
            or estado.get("execucao_concluida", False)
        )

        progress.visible = processando
        progress.value = None if processando else 0

        if texto_status:
            status.value = texto_status
            status.visible = True

        page.update()

    def limpar(e=None):
        estado["session"] = None
        estado["equipe_id"] = None
        estado["tecnicos"] = []
        estado["dados_painel_antes"] = []
        estado["dados_painel_depois"] = []
        estado["dados_processos_aptos"] = []
        estado["df_quant_antes"] = pd.DataFrame()
        estado["df_quant_depois"] = pd.DataFrame()
        estado["df_comparativo"] = pd.DataFrame()
        estado["df_plano"] = pd.DataFrame()
        estado["df_logs_request"] = pd.DataFrame()
        estado["logs_interface"] = []
        estado["caminho_saida"] = None
        estado["execucao_concluida"] = False

        linhas_tecnicos_estado.clear()
        linhas_tecnicos.controls.clear()
        linhas_tecnicos.visible = False
        container_tecnicos.visible = False

        tabela_resumo_plano.rows.clear()
        tabela_resumo_plano.visible = False
        container_resumo_plano.visible = False

        tabela_painel_final.rows.clear()
        tabela_painel_final.visible = False
        container_painel_final.visible = False

        txt_resumo_carga.value = ""
        txt_resumo_carga.visible = False

        txt_resumo_final.value = ""
        txt_resumo_final.visible = False

        log_execucao.value = ""
        status.value = ""
        status.visible = False
        progress.visible = False

        btn_gerar_plano.disabled = True
        btn_executar.disabled = True
        btn_executar.visible = False
        btn_marcar_todos.visible = False
        btn_desmarcar_todos.visible = False
        btn_abrir_logs.visible = False
        txt_qtd_aptos.value = "0"
        card_aptos.visible = False

        page.update()

    def abrir_logs(e):
        caminho = estado.get(
            "caminho_saida"
        )

        if caminho and os.path.exists(caminho):
            abrir_pasta_exportacao(
                caminho
            )
        else:
            mostrar_alerta(
                ft,
                page,
                "Arquivo não encontrado",
                "Nenhum XLSX gerado foi localizado.",
                tipo="error",
            )

        page.update()

    def abrir_dialogo_modal(dialogo):
        """
        Abre AlertDialog de forma compatível com versões diferentes do Flet.

        Algumas versões antigas aceitam page.dialog + dialog.open.
        Versões novas preferem page.open(dialog).
        Este helper tenta as duas estratégias para evitar o clique sem efeito.
        """
        try:
            if hasattr(page, "open") and callable(getattr(page, "open")):
                page.open(dialogo)
                return
        except Exception:
            pass

        try:
            if hasattr(page, "overlay") and dialogo not in page.overlay:
                page.overlay.append(dialogo)
        except Exception:
            pass

        try:
            page.dialog = dialogo
        except Exception:
            pass

        try:
            dialogo.open = True
        except Exception:
            pass

        page.update()

    def fechar_dialogo_modal(dialogo):
        """Fecha AlertDialog com fallback para diferentes versões do Flet."""
        try:
            if hasattr(page, "close") and callable(getattr(page, "close")):
                page.close(dialogo)
                return
        except Exception:
            pass

        try:
            dialogo.open = False
        except Exception:
            pass

        page.update()

    def abrir_entenda_mais(e=None):
        """Abre uma explicação didática sobre o módulo de distribuição."""

        def card_info(numero: str, titulo: str, texto: str, cor):
            return ft.Container(
                content=ft.Row(
                    [
                        ft.Container(
                            content=ft.Text(
                                numero,
                                size=UI_FONT_SMALL,
                                weight="bold",
                                color="white",
                            ),
                            width=30,
                            height=30,
                            alignment=ft.alignment.center,
                            border_radius=15,
                            bgcolor=cor,
                        ),
                        ft.Container(
                            content=ft.Column(
                                [
                                    ft.Text(
                                        titulo,
                                        size=UI_FONT,
                                        weight="bold",
                                    ),
                                    ft.Text(
                                        texto,
                                        size=UI_FONT_SMALL,
                                        color=ft.Colors.GREY_700,
                                    ),
                                ],
                                spacing=2,
                                tight=True,
                            ),
                            expand=True,
                        ),
                    ],
                    spacing=10,
                    vertical_alignment=ft.CrossAxisAlignment.START,
                ),
                padding=ft.padding.symmetric(horizontal=10, vertical=8),
                border_radius=10,
                border=ft.border.all(
                    1,
                    ft.Colors.with_opacity(0.12, ft.Colors.ON_SURFACE),
                ),
                bgcolor=ft.Colors.with_opacity(0.025, ft.Colors.ON_SURFACE),
            )

        def legenda_cor(cor, titulo, texto):
            return ft.Container(
                content=ft.Row(
                    [
                        ft.Container(
                            width=14,
                            height=14,
                            border_radius=7,
                            bgcolor=cor,
                        ),
                        ft.Text(
                            titulo,
                            size=UI_FONT_SMALL,
                            weight="bold",
                        ),
                        ft.Text(
                            texto,
                            size=UI_FONT_TINY,
                            color=ft.Colors.GREY_700,
                        ),
                    ],
                    spacing=6,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    wrap=True,
                ),
                padding=ft.padding.symmetric(horizontal=8, vertical=4),
            )

        def fechar(e=None):
            fechar_dialogo_modal(dialogo_ajuda)

        dialogo_ajuda = ft.AlertDialog(
            modal=True,
            title=ft.Text(
                "Entenda a Distribuição Automática SIOR",
                weight="bold",
            ),
            content=ft.Container(
                width=820,
                height=620,
                content=ft.Column(
                    [
                        ft.Container(
                            content=ft.Column(
                                [
                                    ft.Text(
                                        "Objetivo do módulo",
                                        size=UI_FONT + 1,
                                        weight="bold",
                                        color=ft.Colors.INDIGO_700,
                                    ),
                                    ft.Text(
                                        (
                                            "Este módulo distribui automaticamente os processos aptos do painel SIOR para "
                                            "analisador e conferidor. Primeiro, prioriza os devedores com autos de "
                                            "DataConstituicao mais antiga; depois, mantém a regra principal: sempre que possível, "
                                            "autos do mesmo devedor ficam com o mesmo analisador/conferidor."
                                        ),
                                        size=UI_FONT_SMALL,
                                        color=ft.Colors.GREY_700,
                                    ),
                                ],
                                spacing=4,
                                tight=True,
                            ),
                            padding=ft.padding.symmetric(horizontal=12, vertical=10),
                            border_radius=12,
                            bgcolor=ft.Colors.with_opacity(0.08, ft.Colors.INDIGO),
                        ),
                        card_info(
                            "1",
                            "Escolha a equipe do supervisor",
                            "Selecione a equipe que será carregada. A tela irá buscar os técnicos da equipe, o painel atual e os processos aptos à distribuição.",
                            ft.Colors.BLUE_600,
                        ),
                        card_info(
                            "2",
                            "Clique em Carregar equipe",
                            "Após carregar, será exibido o card Aptos, que mostra quantos processos estão disponíveis para distribuir no momento.",
                            ft.Colors.BLUE_600,
                        ),
                        card_info(
                            "3",
                            "Revise a tabela de distribuição",
                            "Cada linha permite escolher se aquele técnico participará, quem será o analisador, quem será o conferidor e quantos autos serão distribuídos para essa linha.",
                            ft.Colors.GREEN_600,
                        ),
                        card_info(
                            "4",
                            "Analisador e conferidor",
                            "Por padrão, o analisador também será o conferidor. Mesmo assim, os campos são editáveis para casos específicos em que você precise alterar a dupla.",
                            ft.Colors.GREEN_600,
                        ),
                        card_info(
                            "5",
                            "Quantidade a distribuir",
                            "Informe a quantidade de autos que deseja enviar para cada analisador/conferidor. O limite por linha é de 1 a 200 autos.",
                            ft.Colors.ORANGE_600,
                        ),
                        card_info(
                            "6",
                            "Prioridade pela data mais antiga",
                            "Antes de distribuir, a aplicação identifica a menor DataConstituicao de cada devedor. O devedor com auto mais antigo entra primeiro na fila de distribuição.",
                            ft.Colors.RED_600,
                        ),
                        card_info(
                            "7",
                            "Regra por devedor",
                            "A distribuição agrupa os autos por devedor. Se um devedor tiver muitos autos e a quantidade da linha acabar, o restante poderá seguir para a próxima linha selecionada.",
                            ft.Colors.PURPLE_600,
                        ),
                        ft.Container(
                            content=ft.Column(
                                [
                                    ft.Text(
                                        "Como interpretar as cores da tabela",
                                        size=UI_FONT,
                                        weight="bold",
                                    ),
                                    legenda_cor(
                                        ft.Colors.RED_50,
                                        "Vermelho claro:",
                                        "Total painel menor que 50. O técnico está abaixo da referência visual.",
                                    ),
                                    legenda_cor(
                                        ft.Colors.GREEN_50,
                                        "Verde claro:",
                                        "Total painel igual a 50. O técnico está exatamente na referência visual.",
                                    ),
                                    legenda_cor(
                                        ft.Colors.BLUE_50,
                                        "Azul claro:",
                                        "Total painel maior que 50. O técnico está acima da referência visual.",
                                    ),
                                    legenda_cor(
                                        ft.Colors.GREY_100,
                                        "Cinza:",
                                        "Linha desmarcada ou ignorada na distribuição.",
                                    ),
                                ],
                                spacing=2,
                                tight=True,
                            ),
                            padding=ft.padding.symmetric(horizontal=10, vertical=8),
                            border_radius=10,
                            border=ft.border.all(1, ft.Colors.GREY_300),
                        ),
                        card_info(
                            "7",
                            "Executar distribuição",
                            "Ao clicar em Executar distribuição, uma confirmação será aberta com o total selecionado. Se confirmar, a automação distribui e gera um XLSX com as ações realizadas.",
                            ft.Colors.RED_600,
                        ),
                        card_info(
                            "8",
                            "Arquivo final",
                            "Ao final, o XLSX registra o plano executado, logs, painel antes/depois e eventuais quebras de devedor. Depois disso, a equipe é recarregada automaticamente para mostrar a tabela atualizada na tela.",
                            ft.Colors.TEAL_600,
                        ),
                    ],
                    spacing=8,
                    scroll=ft.ScrollMode.AUTO,
                ),
            ),
            actions=[
                ft.ElevatedButton(
                    "Entendi",
                    icon=ft.Icons.CHECK_CIRCLE_OUTLINE,
                    bgcolor=ft.Colors.GREEN_700,
                    color="white",
                    on_click=fechar,
                )
            ],
        )

        abrir_dialogo_modal(dialogo_ajuda)

    def validar_equipe() -> str:
        equipe_id = str(
            dropdown_equipes.value or ""
        ).strip()

        if not equipe_id:
            raise ValueError(
                "Selecione a equipe do supervisor."
            )

        if not equipe_id.isdigit():
            raise ValueError(
                "Equipe inválida."
            )

        return equipe_id

    def validar_meta_padrao() -> int:
        try:
            meta = int(
                str(input_meta_padrao.value or "0").strip()
            )
        except Exception:
            meta = 0

        if meta <= 0:
            raise ValueError(
                "A quantidade a distribuir deve ser maior que zero."
            )

        if meta > 200:
            raise ValueError(
                "A quantidade a distribuir por analisador/conferidor deve ser de no máximo 200."
            )

        return meta

    def opcoes_tecnicos():
        return [
            ft.dropdown.Option(
                key=str(t.get("Value")),
                text=str(t.get("Text")),
            )
            for t in estado["tecnicos"]
        ]

    def nome_tecnico_por_id(tecnico_id: str) -> str:
        tecnico_id = str(
            tecnico_id or ""
        )

        for tecnico in estado["tecnicos"]:
            if str(tecnico.get("Value")) == tecnico_id:
                return str(
                    tecnico.get("Text")
                )

        return tecnico_id

    def obter_total_painel_tecnico(nome_tecnico: str) -> dict:
        df_quant = estado["df_quant_antes"]

        if df_quant is None or df_quant.empty:
            return {
                "analise": 0,
                "conferencia": 0,
                "total": 0,
            }

        filtro = (
                df_quant["Tecnico"]
                .astype(str)
                .str.strip()
                == str(nome_tecnico or "").strip()
        )

        if not filtro.any():
            return {
                "analise": 0,
                "conferencia": 0,
                "total": 0,
            }

        row = df_quant[filtro].iloc[0]

        analise = int(
            row.get(
                "QtdAnaliseSapiens",
                0,
            )
        )

        conferencia = int(
            row.get(
                "QtdConferenciaSapiens",
                0,
            )
        )

        return {
            "analise": analise,
            "conferencia": conferencia,
            "total": analise + conferencia,
        }

    def calcular_necessidade_distribuicao(
            analisador_id: str,
            conferidor_id: str,
            meta_painel: int,
    ) -> dict:
        analisador_nome = nome_tecnico_por_id(
            analisador_id
        )

        conferidor_nome = nome_tecnico_por_id(
            conferidor_id
        )

        qtd_analisador = obter_total_painel_tecnico(
            analisador_nome
        )

        qtd_conferidor = obter_total_painel_tecnico(
            conferidor_nome
        )

        atual_analisador = qtd_analisador["total"]
        atual_conferidor = qtd_conferidor["total"]

        necessidade_analisador = max(
            meta_painel - atual_analisador,
            0,
        )

        necessidade_conferidor = max(
            meta_painel - atual_conferidor,
            0,
        )

        if str(analisador_id) == str(conferidor_id):
            quantidade_distribuir = necessidade_analisador
            atual_considerado = atual_analisador

        else:
            quantidade_distribuir = min(
                necessidade_analisador,
                necessidade_conferidor,
            )

            atual_considerado = max(
                atual_analisador,
                atual_conferidor,
            )

        return {
            "analisador_nome": analisador_nome,
            "conferidor_nome": conferidor_nome,
            "atual_analisador": atual_analisador,
            "atual_conferidor": atual_conferidor,
            "atual_considerado": atual_considerado,
            "necessidade_analisador": necessidade_analisador,
            "necessidade_conferidor": necessidade_conferidor,
            "quantidade_distribuir": quantidade_distribuir,
        }

    def criar_linhas_tecnicos():
        linhas_tecnicos.controls.clear()
        linhas_tecnicos_estado.clear()

        qtd_padrao = validar_meta_padrao()

        def linha_dropdown_tecnicos(valor_inicial: str):
            return ft.Dropdown(
                options=opcoes_tecnicos(),
                value=valor_inicial,
                width=235,
                label_style=ft.TextStyle(size=TABELA_FONT_SMALL),
                text_style=ft.TextStyle(size=TABELA_FONT_SMALL),
            )

        for tecnico in estado["tecnicos"]:
            tecnico_id = str(
                tecnico.get("Value")
            )

            chk = ft.Checkbox(
                value=True,
                width=34,
                tooltip="Selecionar técnico para distribuição",
            )

            dd_analisador = linha_dropdown_tecnicos(
                tecnico_id
            )

            dd_conferidor = linha_dropdown_tecnicos(
                tecnico_id
            )
            dd_conferidor.data = "auto"

            input_qtd = ft.TextField(
                value=str(qtd_padrao),
                width=96,
                height=34,
                text_align=ft.TextAlign.CENTER,
                content_padding=ft.padding.symmetric(horizontal=4, vertical=4),
                text_style=ft.TextStyle(
                    size=TABELA_FONT,
                    weight="bold",
                ),
            )

            txt_atual_analise = ft.Text(
                "0",
                size=TABELA_FONT_SMALL,
                color=ft.Colors.GREY_700,
                selectable=True,
            )

            txt_atual_conferencia = ft.Text(
                "0",
                size=TABELA_FONT_SMALL,
                color=ft.Colors.GREY_700,
                selectable=True,
            )

            txt_atual_total = ft.Text(
                "0",
                size=TABELA_FONT_SMALL,
                weight="bold",
                color=ft.Colors.GREY_800,
                selectable=True,
            )

            txt_total_apos = ft.Text(
                "0",
                size=TABELA_FONT,
                weight="bold",
                color=ft.Colors.BLUE_800,
                selectable=True,
            )

            txt_status_linha = ft.Text(
                "Selecionado",
                size=TABELA_FONT_SMALL,
                weight="bold",
                color=ft.Colors.BLUE_700,
            )

            linha_container = ft.Container(
                height=50,
                padding=ft.padding.symmetric(horizontal=6, vertical=3),
                border_radius=7,
                border=ft.border.all(
                    1,
                    ft.Colors.BLUE_300,
                ),
                bgcolor=ft.Colors.with_opacity(0.06, ft.Colors.BLUE),
            )

            def atualizar_texto_linha(
                dd_a=dd_analisador,
                dd_c=dd_conferidor,
                input_quantidade=input_qtd,
                txt_atual_analise_linha=txt_atual_analise,
                txt_atual_conferencia_linha=txt_atual_conferencia,
                txt_atual_total_linha=txt_atual_total,
                txt_total_apos_linha=txt_total_apos,
                txt_status=txt_status_linha,
                linha=linha_container,
                chk_item=chk,
            ):
                try:
                    quantidade = int(
                        str(input_quantidade.value or "0").strip()
                    )
                except Exception:
                    quantidade = 0

                analisador_nome = nome_tecnico_por_id(
                    dd_a.value
                )
                conferidor_nome = nome_tecnico_por_id(
                    dd_c.value
                )

                qtd_analisador = obter_total_painel_tecnico(
                    analisador_nome
                )
                qtd_conferidor = obter_total_painel_tecnico(
                    conferidor_nome
                )

                atual_analisador = int(qtd_analisador.get("total", 0))
                atual_conferidor = int(qtd_conferidor.get("total", 0))

                if str(dd_a.value) == str(dd_c.value):
                    atual_considerado = atual_analisador
                else:
                    atual_considerado = max(
                        atual_analisador,
                        atual_conferidor,
                    )

                txt_atual_analise_linha.value = str(atual_analisador)
                txt_atual_conferencia_linha.value = str(atual_conferidor)
                txt_atual_total_linha.value = str(atual_considerado)

                # Total após distribuição = Total painel + Quantidade a distribuir.
                # Para quantidade negativa/inválida, mantém apenas o total atual do painel.
                quantidade_para_total = quantidade if quantidade > 0 else 0
                total_apos_distribuicao = atual_considerado + quantidade_para_total
                txt_total_apos_linha.value = str(total_apos_distribuicao)

                if quantidade <= 0:
                    txt_status.value = "Qtd inválida"
                    txt_status.color = ft.Colors.RED_700
                    linha.border = ft.border.all(1, ft.Colors.RED_400)
                    linha.bgcolor = ft.Colors.with_opacity(0.06, ft.Colors.RED)
                    return

                if quantidade > 200:
                    txt_status.value = "Máx. 200"
                    txt_status.color = ft.Colors.RED_700
                    linha.border = ft.border.all(1, ft.Colors.RED_400)
                    linha.bgcolor = ft.Colors.with_opacity(0.06, ft.Colors.RED)
                    return

                if not chk_item.value:
                    txt_status.value = "Ignorado"
                    txt_status.color = ft.Colors.GREY_600
                    linha.border = ft.border.all(1, ft.Colors.GREY_400)
                    linha.bgcolor = None
                    return

                # ==================================================
                # CORES POR TOTAL NO PAINEL
                # ==================================================
                # Regra de UX solicitada:
                # - Total painel < 50  -> vermelho claro
                # - Total painel == 50 -> verde claro
                # - Total painel > 50  -> azul claro
                if atual_considerado < 50:
                    txt_status.value = "Abaixo de 50"
                    txt_status.color = ft.Colors.RED_700
                    linha.border = ft.border.all(1, ft.Colors.RED_300)
                    linha.bgcolor = ft.Colors.with_opacity(0.07, ft.Colors.RED)

                elif atual_considerado == 50:
                    txt_status.value = "Igual a 50"
                    txt_status.color = ft.Colors.GREEN_700
                    linha.border = ft.border.all(1, ft.Colors.GREEN_400)
                    linha.bgcolor = ft.Colors.with_opacity(0.08, ft.Colors.GREEN)

                else:
                    txt_status.value = "Acima de 50"
                    txt_status.color = ft.Colors.BLUE_700
                    linha.border = ft.border.all(1, ft.Colors.BLUE_300)
                    linha.bgcolor = ft.Colors.with_opacity(0.07, ft.Colors.BLUE)

            def on_change_analisador(e, dd_a=dd_analisador, dd_c=dd_conferidor):
                if getattr(dd_c, "data", "auto") == "auto":
                    dd_c.value = dd_a.value

                for item in linhas_tecnicos_estado:
                    if item["dd_analisador"] == dd_a:
                        item["atualizar"]()
                        break

                page.update()

            def on_change_conferidor(e, dd_a=dd_analisador, dd_c=dd_conferidor):
                if str(dd_c.value) == str(dd_a.value):
                    dd_c.data = "auto"
                else:
                    dd_c.data = "manual"

                for item in linhas_tecnicos_estado:
                    if item["dd_conferidor"] == dd_c:
                        item["atualizar"]()
                        break

                page.update()

            def on_change_quantidade(e, input_quantidade=input_qtd):
                for item in linhas_tecnicos_estado:
                    if item["input_qtd"] == input_quantidade:
                        item["atualizar"]()
                        break

                page.update()

            def on_change_chk(e, chk_item=chk):
                for item in linhas_tecnicos_estado:
                    if item["chk"] == chk_item:
                        item["atualizar"]()
                        break

                page.update()

            chk.on_change = on_change_chk
            dd_analisador.on_change = on_change_analisador
            dd_conferidor.on_change = on_change_conferidor
            input_qtd.on_change = on_change_quantidade

            linha_container.content = ft.Row(
                [
                    ft.Container(width=34, content=chk),
                    ft.Container(width=235, content=dd_analisador),
                    ft.Container(width=235, content=dd_conferidor),
                    ft.Container(width=82, content=txt_atual_analise, alignment=ft.alignment.center),
                    ft.Container(width=92, content=txt_atual_conferencia, alignment=ft.alignment.center),
                    ft.Container(width=70, content=txt_atual_total, alignment=ft.alignment.center),
                    ft.Container(width=92, content=txt_total_apos, alignment=ft.alignment.center),
                    ft.Container(width=92, content=txt_status_linha),
                    ft.Container(width=112, content=input_qtd),
                ],
                spacing=6,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            )

            linhas_tecnicos.controls.append(
                linha_container
            )

            item_estado = {
                "chk": chk,
                "dd_analisador": dd_analisador,
                "dd_conferidor": dd_conferidor,
                "input_qtd": input_qtd,
                "atualizar": atualizar_texto_linha,
            }

            linhas_tecnicos_estado.append(
                item_estado
            )

            atualizar_texto_linha()

        linhas_tecnicos.visible = True
        cabecalho_tecnicos.visible = True
        container_tecnicos.visible = True
        btn_marcar_todos.visible = True
        btn_desmarcar_todos.visible = True
        card_aptos.visible = True

        page.update()

    def parse_metas_tecnicos():
        metas = []

        for item in linhas_tecnicos_estado:
            chk = item["chk"]

            if not chk.value:
                continue

            analisador_id = str(
                item["dd_analisador"].value or ""
            ).strip()

            conferidor_id = str(
                item["dd_conferidor"].value or ""
            ).strip()

            try:
                quantidade_distribuir = int(
                    str(item["input_qtd"].value or "0").strip()
                )
            except Exception:
                quantidade_distribuir = 0

            if quantidade_distribuir <= 0:
                raise ValueError(
                    "A quantidade a distribuir dos técnicos selecionados deve ser maior que zero."
                )

            if quantidade_distribuir > 200:
                nome_tecnico = nome_tecnico_por_id(analisador_id) or analisador_id
                raise ValueError(
                    f"A quantidade a distribuir para {nome_tecnico} está acima do limite máximo de 200."
                )

            if not analisador_id or not conferidor_id:
                continue

            analisador_nome = nome_tecnico_por_id(
                analisador_id
            )

            conferidor_nome = nome_tecnico_por_id(
                conferidor_id
            )

            qtd_analisador = obter_total_painel_tecnico(
                analisador_nome
            )

            qtd_conferidor = obter_total_painel_tecnico(
                conferidor_nome
            )

            atual_analisador = int(
                qtd_analisador.get("total", 0)
            )

            atual_conferidor = int(
                qtd_conferidor.get("total", 0)
            )

            if str(analisador_id) == str(conferidor_id):
                atual_considerado = atual_analisador
            else:
                atual_considerado = max(
                    atual_analisador,
                    atual_conferidor,
                )

            metas.append(
                {
                    "analisador_id": analisador_id,
                    "analisador_nome": analisador_nome,
                    "conferidor_id": conferidor_id,
                    "conferidor_nome": conferidor_nome,

                    # Neste fluxo, o campo informado pelo usuário é a quantidade que será disponibilizada
                    # para o par analisador/conferidor, e não a meta final do painel.
                    "meta_painel": quantidade_distribuir,
                    "atual_painel_analisador": atual_analisador,
                    "atual_painel_conferidor": atual_conferidor,
                    "atual_painel_considerado": atual_considerado,
                    "total_apos_distribuicao": atual_considerado + quantidade_distribuir,
                    "quantidade_distribuir": quantidade_distribuir,

                    # Compatibilidade com a função de planejamento
                    "quantidade": quantidade_distribuir,
                }
            )

        if not metas:
            raise ValueError(
                (
                    "Nenhum técnico foi selecionado com quantidade a distribuir. "
                    "Marque ao menos uma linha e informe uma quantidade entre 1 e 200."
                )
            )

        return metas

    def atualizar_resumo_plano():
        tabela_resumo_plano.rows.clear()

        df = estado["df_plano"]

        if df.empty:
            tabela_resumo_plano.visible = False
            container_resumo_plano.visible = False
            btn_executar.disabled = True
            page.update()
            return

        df_exec = df[
            df["PodeExecutar"] == True
        ].copy()

        if df_exec.empty:
            tabela_resumo_plano.visible = False
            container_resumo_plano.visible = False
            btn_executar.disabled = True
            page.update()
            return

        resumo = (
            df_exec
            .groupby(
                [
                    "AnalisadorNome",
                    "ConferidorNome",
                    "MetaPainel",
                    "AtualPainelConsiderado",
                    "QuantidadeDistribuirTecnico",
                ],
                dropna=False,
            )
            .agg(
                Planejado=("NumeroAuto", "count"),
                Devedores=("DevedorIdentificacao", "nunique"),
                Quebras=("QuebraDevedor", lambda s: int((s == "Sim").sum())),
            )
            .reset_index()
        )

        for _, row in resumo.iterrows():
            tabela_resumo_plano.rows.append(
                ft.DataRow(
                    cells=[
                        ft.DataCell(ft.Text(str(row["AnalisadorNome"]), size=DEFAULT_FONT_SIZE)),
                        ft.DataCell(ft.Text(str(row["ConferidorNome"]), size=DEFAULT_FONT_SIZE)),
                        ft.DataCell(ft.Text(str(row["MetaPainel"]), size=DEFAULT_FONT_SIZE)),
                        ft.DataCell(ft.Text(str(row["AtualPainelConsiderado"]), size=DEFAULT_FONT_SIZE)),
                        ft.DataCell(ft.Text(str(row["QuantidadeDistribuirTecnico"]), size=DEFAULT_FONT_SIZE)),
                        ft.DataCell(ft.Text(str(row["Planejado"]), size=DEFAULT_FONT_SIZE)),
                        ft.DataCell(ft.Text(str(row["Devedores"]), size=DEFAULT_FONT_SIZE)),
                        ft.DataCell(ft.Text(str(row["Quebras"]), size=DEFAULT_FONT_SIZE)),
                    ]
                )
            )

        tabela_resumo_plano.visible = True
        container_resumo_plano.visible = True
        btn_executar.disabled = False

        page.update()

    def atualizar_painel_final():
        tabela_painel_final.rows.clear()

        df = estado["df_comparativo"]

        if df.empty:
            tabela_painel_final.visible = False
            container_painel_final.visible = False
            page.update()
            return

        df_view = df.copy()

        for _, row in df_view.iterrows():
            tabela_painel_final.rows.append(
                ft.DataRow(
                    cells=[
                        ft.DataCell(ft.Text(str(row.get("Tecnico", "")), size=DEFAULT_FONT_SIZE)),
                        ft.DataCell(ft.Text(str(row.get("AnaliseAntes", 0)), size=DEFAULT_FONT_SIZE)),
                        ft.DataCell(ft.Text(str(row.get("AnaliseDepois", 0)), size=DEFAULT_FONT_SIZE)),
                        ft.DataCell(ft.Text(str(row.get("DeltaAnalise", 0)), size=DEFAULT_FONT_SIZE)),
                        ft.DataCell(ft.Text(str(row.get("ConferenciaAntes", 0)), size=DEFAULT_FONT_SIZE)),
                        ft.DataCell(ft.Text(str(row.get("ConferenciaDepois", 0)), size=DEFAULT_FONT_SIZE)),
                        ft.DataCell(ft.Text(str(row.get("DeltaConferencia", 0)), size=DEFAULT_FONT_SIZE)),
                        ft.DataCell(ft.Text(str(row.get("DeltaTotal", 0)), size=DEFAULT_FONT_SIZE)),
                    ]
                )
            )

        tabela_painel_final.visible = True
        container_painel_final.visible = True

        page.update()

    def exportar_execucao(caminho_saida: str):
        df_logs_interface = pd.DataFrame(
            estado["logs_interface"]
        )

        if df_logs_interface.empty:
            df_logs_interface = pd.DataFrame(
                columns=[
                    "DataHora",
                    "Mensagem",
                ]
            )

        df_insights = montar_insights_distribuicao(
            df_plano=estado["df_plano"],
            df_logs_request=estado["df_logs_request"],
            df_quant_antes=estado["df_quant_antes"],
            df_quant_depois=estado["df_quant_depois"],
            dados_painel_antes=estado["dados_painel_antes"],
            dados_painel_depois=estado["dados_painel_depois"],
        )

        exportar_distribuicao_completa_excel(
            caminho_saida=caminho_saida,
            df_logs_interface=df_logs_interface,
            df_plano=estado["df_plano"],
            df_logs_request=estado["df_logs_request"],
            dados_painel_antes=estado["dados_painel_antes"],
            dados_painel_depois=estado["dados_painel_depois"],
            df_quant_antes=estado["df_quant_antes"],
            df_quant_depois=estado["df_quant_depois"],
            df_comparativo=estado["df_comparativo"],
            df_insights=df_insights,
        )

        estado["caminho_saida"] = caminho_saida

    # ======================================================
    # CARREGAR DADOS
    # ======================================================
    def carregar_dados(e):
        try:
            equipe_id = validar_equipe()
            validar_meta_padrao()

        except Exception as ex:
            mostrar_alerta(
                ft,
                page,
                "Validação",
                str(ex),
                tipo="error",
            )
            page.update()
            return

        limpar()

        dropdown_equipes.value = equipe_id

        set_processando(
            True,
            "Preparando carregamento da equipe...",
        )

        def task():
            navegador = None

            try:
                bloquear()

                adicionar_log(
                    "🔐 Iniciando sessão SIOR..."
                )

                navegador, session = iniciar_sessao_sior(
                    log=adicionar_log,
                )

                if navegador is None or session is None:
                    raise RuntimeError(
                        "Não foi possível iniciar a sessão SIOR."
                    )

                url_tela = URL_DISTRIBUICAO_PAGE.format(
                    equipe_id=equipe_id,
                )

                adicionar_log(
                    f"🌐 Acessando tela de Distribuição da equipe {equipe_id}..."
                )

                sucesso_tela = safe_get(
                    navegador=navegador,
                    url=url_tela,
                    elemento_validacao=(By.TAG_NAME, "body"),
                    tentativas=3,
                    timeout_get=20,
                    timeout_elemento=10,
                    tempo_estabilizacao=1,
                )

                if not sucesso_tela:
                    raise RuntimeError(
                        "Não foi possível acessar a tela de Distribuição do SIOR."
                    )

                total_cookies = sincronizar_cookies_navegador_para_session(
                    navegador,
                    session,
                )

                preparar_headers_distribuicao(
                    session,
                    equipe_id,
                )

                adicionar_log(
                    f"🍪 Cookies sincronizados navegador → requests: {total_cookies}."
                )

                inicializar_tela_distribuicao(
                    session=session,
                    equipe_id=equipe_id,
                    log=adicionar_log,
                )

                tecnicos = listar_tecnicos_distribuicao(
                    equipe_id=equipe_id,
                    session=session,
                    log=adicionar_log,
                )

                dados_painel_antes = get_acompanhamento_distribuicao_sior(
                    equipe_id=equipe_id,
                    session=session,
                    fase=None,
                    page_size=1000,
                    log=adicionar_log,
                )

                dados_processos_aptos = listar_processos_aptos_distribuicao(
                    equipe_id=equipe_id,
                    session=session,
                    log=adicionar_log,
                )

                df_quant_antes = montar_df_quantitativos(
                    dados_painel=dados_painel_antes,
                    tecnicos=tecnicos,
                )

                estado["session"] = session
                estado["equipe_id"] = equipe_id
                estado["tecnicos"] = tecnicos
                estado["dados_painel_antes"] = dados_painel_antes
                estado["dados_processos_aptos"] = dados_processos_aptos
                estado["df_quant_antes"] = df_quant_antes
                estado["execucao_concluida"] = False

                criar_linhas_tecnicos()

                total_fase_apta = len(
                    dados_processos_aptos
                )

                txt_qtd_aptos.value = str(total_fase_apta)
                txt_desc_aptos.value = "processo apto à distribuição" if total_fase_apta == 1 else "processos aptos à distribuição"
                card_aptos.bgcolor = ft.Colors.GREEN_600 if total_fase_apta > 0 else ft.Colors.GREY_600
                card_aptos.visible = True

                total_analise = (
                    int(df_quant_antes["QtdAnaliseSapiens"].sum())
                    if not df_quant_antes.empty
                    else 0
                )

                total_conferencia = (
                    int(df_quant_antes["QtdConferenciaSapiens"].sum())
                    if not df_quant_antes.empty
                    else 0
                )

                txt_resumo_carga.value = (
                    f"✅ Equipe {equipe_id} | "
                    f"Técnicos {len(tecnicos)} | "
                    f"Painel {len(dados_painel_antes)} | "
                    f"Aptos {total_fase_apta} | "
                    f"Análise {total_analise} | "
                    f"Conferência {total_conferencia}"
                )

                txt_resumo_carga.visible = True

                btn_gerar_plano.disabled = True
                btn_executar.visible = True
                btn_executar.disabled = False

                adicionar_log(
                    "✅ Carregamento finalizado. Ajuste as quantidades e clique em Executar distribuição."
                )

            except Exception as ex:
                adicionar_log(
                    f"❌ Erro ao carregar dados: {ex}"
                )

                adicionar_log(
                    traceback.format_exc()
                )

                mostrar_alerta(
                    ft,
                    page,
                    "Erro no carregamento",
                    str(ex),
                    tipo="error",
                )

            finally:
                try:
                    if navegador is not None:
                        encerrar_navegador_sior(
                            navegador,
                            log=adicionar_log,
                        )
                except Exception:
                    pass

                set_processando(
                    False,
                )

                desbloquear()
                page.update()

        threading.Thread(
            target=task,
            daemon=True,
        ).start()

    # ======================================================
    # GERAR PLANO AUTOMÁTICO (uso interno)
    # ======================================================
    def gerar_plano(e):
        try:
            if not estado["dados_processos_aptos"]:
                raise ValueError(
                    "Carregue a equipe antes de gerar o plano."
                )

            metas = parse_metas_tecnicos()

            adicionar_log(
                "🧮 Gerando distribuição por devedor..."
            )

            df_plano = gerar_plano_distribuicao(
                dados_processos_aptos=estado["dados_processos_aptos"],
                metas_tecnicos=metas,
                log=adicionar_log,
            )

            estado["df_plano"] = df_plano

            total = len(df_plano)

            executaveis = (
                int((df_plano["PodeExecutar"] == True).sum())
                if not df_plano.empty and "PodeExecutar" in df_plano.columns
                else 0
            )

            sem_capacidade = (
                int((df_plano["StatusPlanejamento"] == "SEM_CAPACIDADE").sum())
                if not df_plano.empty and "StatusPlanejamento" in df_plano.columns
                else 0
            )

            sem_key = (
                int((df_plano["StatusPlanejamento"] == "SEM_KEY_OU_ROWVERSION").sum())
                if not df_plano.empty and "StatusPlanejamento" in df_plano.columns
                else 0
            )

            adicionar_log(
                (
                    f"✅ Plano gerado: {total} registro(s) | "
                    f"Executáveis: {executaveis} | "
                    f"Sem capacidade: {sem_capacidade} | "
                    f"Sem Key/RowVersion: {sem_key}."
                )
            )

            atualizar_resumo_plano()

            if executaveis == 0:
                mostrar_alerta(
                    ft,
                    page,
                    "Plano sem itens executáveis",
                    (
                        "O plano foi gerado, mas nenhum item possui KeyDistribuicao "
                        "e RowVersionDistribuicao. Verifique se a request de distribuição "
                        "retornou CobrancaCodigoProcesso e RowVersionConverted."
                    ),
                    tipo="error",
                )

            page.update()

        except Exception as ex:
            adicionar_log(
                f"❌ Erro ao gerar plano: {ex}"
            )

            mostrar_alerta(
                ft,
                page,
                "Erro ao gerar plano",
                str(ex),
                tipo="error",
            )

            page.update()

    # ======================================================
    # CONFIRMAÇÃO / EXECUTAR DISTRIBUIÇÃO
    # ======================================================
    def montar_resumo_confirmacao(metas: list[dict]) -> dict:
        """
        Monta o resumo exibido antes da execução.

        Importante:
        - A quantidade selecionada é o somatório dos campos
          "Quantidade a distribuir" das linhas marcadas.
        - A execução real ainda respeita os processos aptos carregados
          e a regra de agrupamento por devedor.
        """
        total_solicitado = sum(
            int(m.get("quantidade_distribuir", 0) or 0)
            for m in metas
        )

        total_aptos = len(
            estado.get("dados_processos_aptos", []) or []
        )

        linhas = []

        for idx, meta in enumerate(metas, start=1):
            analisador = str(
                meta.get("analisador_nome")
                or meta.get("analisador_id")
                or ""
            )

            conferidor = str(
                meta.get("conferidor_nome")
                or meta.get("conferidor_id")
                or ""
            )

            quantidade = int(
                meta.get("quantidade_distribuir", 0) or 0
            )

            linhas.append(
                {
                    "ordem": idx,
                    "analisador": analisador,
                    "conferidor": conferidor,
                    "quantidade": quantidade,
                    "analise_painel": int(meta.get("atual_painel_analisador", 0) or 0),
                    "conferencia_painel": int(meta.get("atual_painel_conferidor", 0) or 0),
                    "total_painel": int(meta.get("atual_painel_considerado", 0) or 0),
                    "total_apos_distribuicao": int(meta.get("total_apos_distribuicao", 0) or 0),
                }
            )

        return {
            "total_solicitado": total_solicitado,
            "total_aptos": total_aptos,
            "linhas": linhas,
        }

    def abrir_confirmacao_distribuicao(equipe_id: str, metas: list[dict]):
        resumo = montar_resumo_confirmacao(
            metas
        )

        total_solicitado = int(
            resumo.get("total_solicitado", 0) or 0
        )

        total_aptos = int(
            resumo.get("total_aptos", 0) or 0
        )

        linhas_resumo = []

        for item in resumo.get("linhas", []):
            linhas_resumo.append(
                ft.Container(
                    content=ft.Row(
                        [
                            ft.Container(
                                width=28,
                                content=ft.Text(
                                    str(item.get("ordem", "")),
                                    size=UI_FONT_SMALL,
                                    weight="bold",
                                ),
                            ),
                            ft.Container(
                                width=210,
                                content=ft.Text(
                                    str(item.get("analisador", "")),
                                    size=UI_FONT_SMALL,
                                    no_wrap=True,
                                ),
                            ),
                            ft.Container(
                                width=210,
                                content=ft.Text(
                                    str(item.get("conferidor", "")),
                                    size=UI_FONT_SMALL,
                                    no_wrap=True,
                                ),
                            ),
                            ft.Container(
                                width=72,
                                alignment=ft.alignment.center,
                                content=ft.Text(
                                    str(item.get("total_painel", 0)),
                                    size=UI_FONT_SMALL,
                                    weight="bold",
                                ),
                            ),
                            ft.Container(
                                width=82,
                                alignment=ft.alignment.center,
                                content=ft.Text(
                                    str(item.get("total_apos_distribuicao", 0)),
                                    size=UI_FONT_SMALL,
                                    weight="bold",
                                    color=ft.Colors.GREEN_700,
                                ),
                            ),
                            ft.Container(
                                width=82,
                                alignment=ft.alignment.center,
                                content=ft.Text(
                                    str(item.get("quantidade", 0)),
                                    size=UI_FONT_SMALL,
                                    weight="bold",
                                    color=ft.Colors.BLUE_700,
                                ),
                            ),
                        ],
                        spacing=6,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    padding=ft.padding.symmetric(horizontal=6, vertical=4),
                    border_radius=6,
                    bgcolor=ft.Colors.with_opacity(
                        0.035,
                        ft.Colors.ON_SURFACE,
                    ),
                )
            )

        if not linhas_resumo:
            linhas_resumo.append(
                ft.Text(
                    "Nenhuma linha selecionada.",
                    size=UI_FONT_SMALL,
                    color=ft.Colors.RED_600,
                )
            )

        def fechar_dialogo(e=None):
            fechar_dialogo_modal(dialogo_confirmacao)

        def confirmar_execucao(e=None):
            fechar_dialogo()
            iniciar_distribuicao_confirmada(
                equipe_id=equipe_id,
                metas_confirmadas=metas,
            )

        dialogo_confirmacao = ft.AlertDialog(
            modal=True,
            title=ft.Text(
                "Confirmar distribuição",
                weight="bold",
            ),
            content=ft.Container(
                width=820,
                content=ft.Column(
                    [
                        ft.Text(
                            (
                                "Deseja prosseguir com a distribuição dos processos "
                                "conforme as quantidades selecionadas abaixo?"
                            ),
                            size=UI_FONT,
                        ),
                        ft.Row(
                            [
                                ft.Container(
                                    content=ft.Column(
                                        [
                                            ft.Text(
                                                "Aptos no painel",
                                                size=UI_FONT_TINY,
                                                color=ft.Colors.WHITE,
                                            ),
                                            ft.Text(
                                                str(total_aptos),
                                                size=UI_FONT + 8,
                                                weight="bold",
                                                color=ft.Colors.WHITE,
                                            ),
                                        ],
                                        spacing=0,
                                    ),
                                    width=165,
                                    padding=ft.padding.symmetric(horizontal=12, vertical=8),
                                    border_radius=10,
                                    bgcolor=ft.Colors.GREEN_600,
                                ),
                                ft.Container(
                                    content=ft.Column(
                                        [
                                            ft.Text(
                                                "Quantidade selecionada",
                                                size=UI_FONT_TINY,
                                                color=ft.Colors.WHITE,
                                            ),
                                            ft.Text(
                                                str(total_solicitado),
                                                size=UI_FONT + 8,
                                                weight="bold",
                                                color=ft.Colors.WHITE,
                                            ),
                                        ],
                                        spacing=0,
                                    ),
                                    width=205,
                                    padding=ft.padding.symmetric(horizontal=12, vertical=8),
                                    border_radius=10,
                                    bgcolor=ft.Colors.BLUE_600,
                                ),
                            ],
                            spacing=10,
                            wrap=True,
                        ),
                        ft.Text(
                            (
                                "A distribuição continuará agrupando autos do mesmo devedor "
                                "para o mesmo analisador/conferidor sempre que houver quantidade disponível. "
                                "Se acabar a quantidade da linha, os autos remanescentes do devedor seguirão para a próxima linha selecionada."
                            ),
                            size=UI_FONT_SMALL,
                            color=ft.Colors.GREY_700,
                        ),
                        ft.Container(
                            content=ft.Row(
                                [
                                    ft.Container(width=28, content=ft.Text("#", size=UI_FONT_TINY, weight="bold")),
                                    ft.Container(width=210, content=ft.Text("Analisador", size=UI_FONT_TINY, weight="bold")),
                                    ft.Container(width=210, content=ft.Text("Conferidor", size=UI_FONT_TINY, weight="bold")),
                                    ft.Container(width=72, alignment=ft.alignment.center, content=ft.Text("Painel", size=UI_FONT_TINY, weight="bold")),
                                    ft.Container(width=82, alignment=ft.alignment.center, content=ft.Text("Após distrib.", size=UI_FONT_TINY, weight="bold")),
                                    ft.Container(width=82, alignment=ft.alignment.center, content=ft.Text("Distribuir", size=UI_FONT_TINY, weight="bold")),
                                ],
                                spacing=6,
                                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                            ),
                            padding=ft.padding.symmetric(horizontal=6, vertical=3),
                            border_radius=6,
                            bgcolor=ft.Colors.with_opacity(
                                0.08,
                                ft.Colors.ON_SURFACE,
                            ),
                        ),
                        ft.Container(
                            content=ft.Column(
                                linhas_resumo,
                                spacing=3,
                                            scroll=ft.ScrollMode.AUTO,
                            ),
                            height=230,
                            padding=ft.padding.only(right=4),
                        ),
                    ],
                    spacing=10,
                ),
            ),
            actions=[
                ft.TextButton(
                    "Não, ajustar",
                    on_click=fechar_dialogo,
                ),
                ft.ElevatedButton(
                    "Sim, executar distribuição",
                    icon=ft.Icons.PLAY_ARROW,
                    bgcolor=ft.Colors.GREEN_700,
                    color="white",
                    on_click=confirmar_execucao,
                ),
            ],
        )

        adicionar_log(
            "🧾 Janela de confirmação aberta. Confirme para iniciar a distribuição."
        )

        abrir_dialogo_modal(
            dialogo_confirmacao
        )

    def executar_distribuicao(e):
        try:
            if estado["session"] is None:
                raise ValueError(
                    "Sessão não carregada. Clique em Carregar equipe novamente."
                )

            if not estado["dados_processos_aptos"]:
                raise ValueError(
                    "Carregue a equipe antes de executar a distribuição."
                )

            # Valida as quantidades aqui e exibe a janela de confirmação
            # antes de iniciar qualquer request de distribuição.
            metas = parse_metas_tecnicos()
            equipe_id = estado["equipe_id"]

            total_solicitado = sum(
                int(m.get("quantidade_distribuir", 0) or 0)
                for m in metas
            )

            total_aptos = len(
                estado.get("dados_processos_aptos", []) or []
            )

            if total_solicitado > total_aptos:
                mostrar_alerta(
                    ft,
                    page,
                    "Quantidade indisponível",
                    (
                        f"Você selecionou {total_solicitado} processo(s) para distribuição, "
                        f"mas existem apenas {total_aptos} processo(s) apto(s) no painel.\n\n"
                        "Ajuste a Quantidade a distribuir na tela anterior para continuar."
                    ),
                    tipo="error",
                )
                page.update()
                return

        except Exception as ex:
            mostrar_alerta(
                ft,
                page,
                "Validação",
                str(ex),
                tipo="error",
            )
            page.update()
            return

        try:
            abrir_confirmacao_distribuicao(
                equipe_id=equipe_id,
                metas=metas,
            )
        except Exception as ex:
            adicionar_log(
                f"❌ Erro ao abrir confirmação da distribuição: {ex}"
            )
            adicionar_log(
                traceback.format_exc()
            )
            mostrar_alerta(
                ft,
                page,
                "Erro ao abrir confirmação",
                str(ex),
                tipo="error",
            )
            page.update()

    def iniciar_distribuicao_confirmada(equipe_id: str, metas_confirmadas: list[dict]):
        btn_executar.disabled = True
        btn_gerar_plano.disabled = True
        btn_carregar.disabled = True
        btn_abrir_logs.visible = False

        progress.visible = True
        progress.value = None

        status.visible = True
        status.value = "Gerando distribuição automática e executando..."

        page.update()

        def task():
            try:
                bloquear()

                ts = datetime.now().strftime(
                    "%Y-%m-%d_%H-%M-%S"
                )

                pasta_saida = os.path.join(
                    pasta_base_saida,
                    f"Distribuicao_SIOR_Equipe_{equipe_id}_{ts}",
                )

                os.makedirs(
                    pasta_saida,
                    exist_ok=True,
                )

                caminho_saida = os.path.join(
                    pasta_saida,
                    f"logs_distribuicao_sior_{ts}.xlsx",
                )

                adicionar_log(
                    "🧮 Gerando distribuição automática por devedor..."
                )

                df_plano = gerar_plano_distribuicao(
                    dados_processos_aptos=estado["dados_processos_aptos"],
                    metas_tecnicos=metas_confirmadas,
                    log=adicionar_log,
                )

                estado["df_plano"] = df_plano

                total = len(df_plano)
                executaveis = (
                    int((df_plano["PodeExecutar"] == True).sum())
                    if not df_plano.empty and "PodeExecutar" in df_plano.columns
                    else 0
                )

                sem_capacidade = (
                    int((df_plano["StatusPlanejamento"] == "SEM_CAPACIDADE").sum())
                    if not df_plano.empty and "StatusPlanejamento" in df_plano.columns
                    else 0
                )

                sem_key = (
                    int((df_plano["StatusPlanejamento"] == "SEM_KEY_OU_ROWVERSION").sum())
                    if not df_plano.empty and "StatusPlanejamento" in df_plano.columns
                    else 0
                )

                adicionar_log(
                    (
                        f"✅ Distribuição calculada: {total} registro(s) | "
                        f"Executáveis: {executaveis} | "
                        f"Sem capacidade: {sem_capacidade} | "
                        f"Sem Key/RowVersion: {sem_key}."
                    )
                )

                atualizar_resumo_plano()

                if executaveis <= 0:
                    raise RuntimeError(
                        "Nenhum item executável foi encontrado para distribuição. "
                        "Verifique se há processos aptos, KeyDistribuicao e RowVersionDistribuicao."
                    )

                adicionar_log(
                    "🚀 Iniciando execução da distribuição..."
                )

                df_logs_request = executar_distribuicao_por_plano(
                    session=estado["session"],
                    equipe_id=equipe_id,
                    df_plano=estado["df_plano"],
                    log=adicionar_log,
                    tamanho_lote=100,
                    pausa_entre_lotes=0.8,
                )

                estado["df_logs_request"] = df_logs_request

                adicionar_log(
                    "🔄 Reconsultando painel atualizado após a distribuição..."
                )

                dados_painel_depois = get_acompanhamento_distribuicao_sior(
                    equipe_id=equipe_id,
                    session=estado["session"],
                    fase=None,
                    page_size=1000,
                    log=adicionar_log,
                )

                estado["dados_painel_depois"] = dados_painel_depois

                df_quant_depois = montar_df_quantitativos(
                    dados_painel=dados_painel_depois,
                    tecnicos=estado["tecnicos"],
                )

                estado["df_quant_depois"] = df_quant_depois

                df_comparativo = montar_comparativo_quantitativos(
                    df_antes=estado["df_quant_antes"],
                    df_depois=df_quant_depois,
                )

                estado["df_comparativo"] = df_comparativo

                total_sucesso = (
                    int((df_logs_request["Status"] == "SUCESSO").sum())
                    if not df_logs_request.empty and "Status" in df_logs_request.columns
                    else 0
                )

                total_erro = (
                    int((df_logs_request["Status"] == "ERRO").sum())
                    if not df_logs_request.empty and "Status" in df_logs_request.columns
                    else 0
                )

                total_analise_depois = (
                    int(df_quant_depois["QtdAnaliseSapiens"].sum())
                    if not df_quant_depois.empty
                    else 0
                )

                total_conferencia_depois = (
                    int(df_quant_depois["QtdConferenciaSapiens"].sum())
                    if not df_quant_depois.empty
                    else 0
                )

                txt_resumo_final.value = (
                    f"✅ Painel atualizado | "
                    f"Sucesso request: {total_sucesso} | "
                    f"Erros request: {total_erro} | "
                    f"Em análise agora: {total_analise_depois} | "
                    f"Em conferência agora: {total_conferencia_depois}"
                )

                txt_resumo_final.visible = True

                atualizar_painel_final()

                exportar_execucao(
                    caminho_saida
                )

                adicionar_log(
                    f"📄 XLSX completo gerado: {caminho_saida}"
                )

                # ==================================================
                # RECARREGAMENTO AUTOMÁTICO DA EQUIPE APÓS EXECUÇÃO
                # ==================================================
                # Após gerar o XLSX, atualizamos a própria tabela principal
                # com os dados mais recentes do painel. Assim o usuário vê,
                # na mesma tela, como ficaram os quantitativos após todas as
                # ações de distribuição executadas.
                adicionar_log(
                    "🔁 Recarregando automaticamente a equipe para atualizar a tabela principal..."
                )

                dados_processos_aptos_atualizados = listar_processos_aptos_distribuicao(
                    equipe_id=equipe_id,
                    session=estado["session"],
                    log=adicionar_log,
                )

                # A tabela principal usa estes campos como referência atual.
                # Por isso, após a execução, o 'antes' passa a representar o
                # painel atual reconsultado.
                estado["dados_painel_antes"] = dados_painel_depois
                estado["df_quant_antes"] = df_quant_depois
                estado["dados_processos_aptos"] = dados_processos_aptos_atualizados

                total_fase_apta_atualizado = len(
                    dados_processos_aptos_atualizados
                )

                txt_qtd_aptos.value = str(
                    total_fase_apta_atualizado
                )

                txt_desc_aptos.value = (
                    "processo apto à distribuição"
                    if total_fase_apta_atualizado == 1
                    else "processos aptos à distribuição"
                )

                card_aptos.bgcolor = (
                    ft.Colors.GREEN_600
                    if total_fase_apta_atualizado > 0
                    else ft.Colors.GREY_600
                )

                card_aptos.visible = True

                txt_resumo_carga.value = (
                    f"✅ Equipe {equipe_id} atualizada após distribuição | "
                    f"Técnicos {len(estado['tecnicos'])} | "
                    f"Painel {len(dados_painel_depois)} | "
                    f"Aptos restantes {total_fase_apta_atualizado} | "
                    f"Análise {total_analise_depois} | "
                    f"Conferência {total_conferencia_depois}"
                )

                txt_resumo_carga.visible = True

                criar_linhas_tecnicos()

                adicionar_log(
                    "✅ Tabela principal atualizada com os quantitativos atuais do painel."
                )

                estado["execucao_concluida"] = True

                adicionar_log(
                    (
                        f"✅ Execução finalizada. "
                        f"Sucesso: {total_sucesso} | Erro: {total_erro}."
                    )
                )

                btn_abrir_logs.visible = True

                mostrar_alerta(
                    ft,
                    page,
                    "Distribuição finalizada",
                    (
                        f"Sucesso: {total_sucesso}\n"
                        f"Erro: {total_erro}\n\n"
                        "O painel foi reconsultado e o XLSX completo foi gerado."
                    ),
                    tipo="success" if total_erro == 0 else "warning",
                )

            except Exception as ex:
                adicionar_log(
                    f"❌ Erro na execução: {ex}"
                )

                adicionar_log(
                    traceback.format_exc()
                )

                try:
                    ts_erro = datetime.now().strftime(
                        "%Y-%m-%d_%H-%M-%S"
                    )

                    pasta_saida_erro = os.path.join(
                        pasta_base_saida,
                        f"Distribuicao_SIOR_Equipe_{equipe_id}_ERRO_{ts_erro}",
                    )

                    os.makedirs(
                        pasta_saida_erro,
                        exist_ok=True,
                    )

                    caminho_erro = os.path.join(
                        pasta_saida_erro,
                        f"logs_distribuicao_sior_erro_{ts_erro}.xlsx",
                    )

                    exportar_execucao(
                        caminho_erro
                    )

                    adicionar_log(
                        f"📄 XLSX de erro gerado: {caminho_erro}"
                    )

                    btn_abrir_logs.visible = True

                except Exception as ex_export:
                    adicionar_log(
                        f"⚠️ Não foi possível exportar logs de erro: {ex_export}"
                    )

                mostrar_alerta(
                    ft,
                    page,
                    "Erro na distribuição",
                    str(ex),
                    tipo="error",
                )

            finally:
                progress.visible = False
                btn_carregar.disabled = False
                btn_gerar_plano.disabled = True
                btn_executar.visible = bool(estado["dados_processos_aptos"])
                btn_executar.disabled = (
                    not bool(estado["dados_processos_aptos"])
                    or estado.get("execucao_concluida", False)
                )

                desbloquear()
                page.update()

        threading.Thread(
            target=task,
            daemon=True,
        ).start()

    def marcar_todos(e=None):
        for item in linhas_tecnicos_estado:
            item["chk"].value = True
            try:
                item["atualizar"]()
            except Exception:
                pass

        page.update()

    def desmarcar_todos(e=None):
        for item in linhas_tecnicos_estado:
            item["chk"].value = False
            try:
                item["atualizar"]()
            except Exception:
                pass

        page.update()

    # ======================================================
    # EVENTOS
    # ======================================================
    btn_carregar.on_click = carregar_dados
    btn_entenda_mais.on_click = abrir_entenda_mais
    btn_executar.on_click = executar_distribuicao
    btn_abrir_logs.on_click = abrir_logs
    btn_limpar.on_click = limpar
    btn_marcar_todos.on_click = marcar_todos
    btn_desmarcar_todos.on_click = desmarcar_todos

    # ======================================================
    # LAYOUT
    # ======================================================
    return ft.Column(
        [
            ft.Text(
                "SIOR - Distribuição Automática de Processos",
                size=HEADING_FONT_SIZE - 1,
                weight="bold",
            ),
            ft.Text(
                (
                    "Esta tela distribui processos aptos na fase "
                    f"'{FASE_APTA_DISTRIBUICAO}', agrupando por devedor. "
                    "Clique em Carregar equipe, confirme os técnicos e execute. "
                    "O cálculo da distribuição é automático e o XLSX final registra todos os autos, ações e quebras por devedor."
                ),
                size=CARD_FONT_SMALL,
                color=ft.Colors.GREY_700,
            ),
            ft.Divider(height=8),
            ft.Row(
                [
                    btn_entenda_mais,
                ],
                wrap=True,
                spacing=8,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            ft.Row(
                [
                    dropdown_equipes,
                    btn_carregar,
                    btn_executar,
                    btn_abrir_logs,
                    btn_limpar,
                ],
                wrap=True,
                spacing=8,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            txt_saida,
            txt_resumo_carga,
            txt_resumo_final,
            progress,
            status,
            container_tecnicos,
            container_resumo_plano,
            container_painel_final,
            ft.Divider(height=8),
            ft.ExpansionTile(
                title=ft.Text(
                    "📝 Logs da Distribuição",
                    size=UI_FONT,
                    weight="bold",
                ),
                subtitle=ft.Text(
                    "Clique para visualizar os detalhes da execução.",
                    size=UI_FONT_TINY,
                    color=ft.Colors.GREY_600,
                ),
                initially_expanded=False,
                controls=[
                    ft.Container(
                        content=log_execucao,
                        height=210,
                        padding=6,
                        border_radius=10,
                        border=ft.border.all(
                            1,
                            ft.Colors.GREY_600,
                        ),
                        bgcolor=ft.Colors.with_opacity(
                            0.05,
                            ft.Colors.ON_SURFACE,
                        ),
                    ),
                ],
            ),
        ],
        spacing=8,
        expand=True,
        tight=True,
        scroll=ft.ScrollMode.AUTO,
    )