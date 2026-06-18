# ==========================================================
# ABA ADMIN - VARREDURA SIOR ENCAMINHAMENTO
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

from requests_data.requisicao_sior_varredura_encaminhamento_request import (
    EQUIPES_DISPONIVEIS,
    DEFAULT_EQUIPES,
    url_tela_encaminhamento,
    preparar_headers_encaminhamento,
    inicializar_tela_encaminhamento,
    enviar_requisicao_get,
    exportar_resultado_excel,
)

from utils.open_dir_downloads import abrir_pasta_exportacao
from utils.popups import mostrar_alerta


def aba_admin_sior_varredura_encaminhamento(
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
        "df_resultado": pd.DataFrame(),
        "logs": [],
        "caminho_xlsx": None,
        "pasta_saida": None,
    }

    equipes_selecionadas = set(
        DEFAULT_EQUIPES
    )

    checkboxes_equipes = {}

    # ======================================================
    # HELPERS - EQUIPES
    # ======================================================
    def texto_equipes_selecionadas():
        equipes = [
            equipe
            for equipe in EQUIPES_DISPONIVEIS
            if equipe in equipes_selecionadas
        ]

        if not equipes:
            return "Nenhuma equipe selecionada"

        return (
            "Equipes selecionadas: "
            + ", ".join(
                map(str, equipes)
            )
        )

    txt_equipes_selecionadas = ft.Text(
        texto_equipes_selecionadas(),
        size=DEFAULT_FONT_SIZE,
        color=ft.Colors.GREY_700,
        selectable=True,
    )

    def atualizar_texto_equipes():
        txt_equipes_selecionadas.value = texto_equipes_selecionadas()
        page.update()

    def alterar_equipe(e, equipe: int):
        if e.control.value:
            equipes_selecionadas.add(
                equipe
            )
        else:
            equipes_selecionadas.discard(
                equipe
            )

        atualizar_texto_equipes()

    def marcar_todas_equipes(e=None):
        equipes_selecionadas.clear()

        for equipe in EQUIPES_DISPONIVEIS:
            equipes_selecionadas.add(
                equipe
            )

            if equipe in checkboxes_equipes:
                checkboxes_equipes[equipe].value = True

        atualizar_texto_equipes()

    def limpar_equipes(e=None):
        equipes_selecionadas.clear()

        for checkbox in checkboxes_equipes.values():
            checkbox.value = False

        atualizar_texto_equipes()

    def obter_equipes_para_execucao():
        equipes = [
            equipe
            for equipe in EQUIPES_DISPONIVEIS
            if equipe in equipes_selecionadas
        ]

        if not equipes:
            raise ValueError(
                "Selecione ao menos uma equipe para executar a varredura."
            )

        return equipes

    lista_checkboxes_equipes = []

    for equipe in EQUIPES_DISPONIVEIS:
        checkbox = ft.Checkbox(
            label=f"Equipe {equipe}",
            value=equipe in DEFAULT_EQUIPES,
            on_change=lambda e, equipe=equipe: alterar_equipe(
                e,
                equipe,
            ),
        )

        checkboxes_equipes[equipe] = checkbox
        lista_checkboxes_equipes.append(
            checkbox
        )

    seletor_equipes = ft.ExpansionTile(
        title=ft.Text(
            "Selecionar equipes da varredura",
            size=DEFAULT_FONT_SIZE,
            weight="bold",
        ),
        subtitle=txt_equipes_selecionadas,
        initially_expanded=False,
        controls=[
            ft.Container(
                content=ft.Column(
                    controls=[
                        ft.Row(
                            controls=[
                                ft.ElevatedButton(
                                    "Marcar todas",
                                    icon=ft.Icons.CHECK_BOX,
                                    on_click=marcar_todas_equipes,
                                ),
                                ft.ElevatedButton(
                                    "Limpar seleção",
                                    icon=ft.Icons.CHECK_BOX_OUTLINE_BLANK,
                                    on_click=limpar_equipes,
                                ),
                            ],
                            spacing=10,
                            wrap=True,
                        ),
                        ft.Column(
                            controls=lista_checkboxes_equipes,
                            spacing=0,
                        ),
                    ],
                    spacing=8,
                ),
                padding=10,
            )
        ],
    )

    # ======================================================
    # CONTROLES
    # ======================================================
    txt_saida = ft.Text(
        f"📁 Saída padrão: {pasta_base_saida}",
        size=DEFAULT_FONT_SIZE,
        color=ft.Colors.GREY_600,
        selectable=True,
    )

    txt_info = ft.Text(
        (
            "Selecione quais equipes deverão ser consideradas na varredura. "
            "Por padrão, as equipes 2, 1, 3, 4 e 5 já vêm marcadas."
        ),
        size=DEFAULT_FONT_SIZE,
        color=ft.Colors.GREY_700,
        selectable=True,
    )

    btn_executar = ft.ElevatedButton(
        "Iniciar Varredura",
        icon=ft.Icons.PLAY_ARROW,
        bgcolor="green",
        color="white",
    )

    btn_abrir_xlsx = ft.ElevatedButton(
        "Abrir XLSX gerado com logs",
        icon=ft.Icons.TABLE_VIEW,
        visible=False,
    )

    btn_limpar_logs = ft.ElevatedButton(
        "Limpar logs",
        icon=ft.Icons.CLEANING_SERVICES,
    )

    progress = ft.ProgressBar(
        width=500,
        visible=False,
    )

    status = ft.Text(
        "",
        size=DEFAULT_FONT_SIZE,
        color="blue",
        visible=False,
        selectable=True,
    )

    log_execucao = ft.TextField(
        label="📝 Logs da Varredura",
        multiline=True,
        read_only=True,
        expand=True,
        min_lines=18,
        max_lines=18,
        label_style=ft.TextStyle(
            size=DEFAULT_FONT_SIZE
        ),
        text_style=ft.TextStyle(
            size=DEFAULT_FONT_SIZE
        ),
    )

    arquivos_gerados = ft.Column(
        controls=[],
        spacing=5,
        visible=False,
    )

    container_logs = ft.Container(
        content=ft.Column(
            controls=[
                ft.Text(
                    "📋 Logs da Execução",
                    size=DEFAULT_FONT_SIZE + 1,
                    weight="bold",
                ),
                log_execucao,
            ],
            spacing=10,
            scroll=ft.ScrollMode.AUTO,
        ),
        height=360,
        padding=10,
        border_radius=10,
        border=ft.border.all(
            1,
            ft.Colors.GREY_600,
        ),
        bgcolor=ft.Colors.with_opacity(
            0.05,
            ft.Colors.ON_SURFACE,
        ),
    )

    # ======================================================
    # HELPERS UI
    # ======================================================
    def adicionar_log(
        mensagem: str,
    ):
        try:
            horario = datetime.now().strftime(
                "%H:%M:%S"
            )

            data_hora = datetime.now().strftime(
                "%d/%m/%Y %H:%M:%S"
            )

            estado["logs"].append(
                {
                    "DataHora": data_hora,
                    "Mensagem": mensagem,
                }
            )

            log_execucao.value += (
                f"[{horario}] {mensagem}\n"
            )

            status.value = mensagem
            status.visible = True

            page.update()

        except Exception:
            pass

    def registrar_arquivo(
        label: str,
        caminho: str,
    ):
        arquivos_gerados.controls.append(
            ft.Text(
                f"✅ {label}: {caminho}",
                size=DEFAULT_FONT_SIZE,
                selectable=True,
            )
        )

        arquivos_gerados.visible = True

    def limpar_logs(e=None):
        log_execucao.value = ""

        arquivos_gerados.controls.clear()
        arquivos_gerados.visible = False

        status.value = ""
        status.visible = False

        estado["df_resultado"] = pd.DataFrame()
        estado["logs"] = []
        estado["caminho_xlsx"] = None
        estado["pasta_saida"] = None

        btn_abrir_xlsx.visible = False

        page.update()

    def abrir_xlsx(e=None):
        caminho = estado.get(
            "caminho_xlsx"
        )

        if caminho and os.path.exists(
            caminho
        ):
            abrir_pasta_exportacao(
                caminho
            )

        else:
            mostrar_alerta(
                ft,
                page,
                "Arquivo não encontrado",
                "O XLSX ainda não foi gerado ou não está disponível.",
                tipo="warning",
            )

            page.update()

    def exportar_xlsx_logs_em_erro():
        """
        Gera XLSX mesmo quando a execução falha antes de concluir a varredura.
        Assim os logs sempre ficam disponíveis em arquivo.
        """

        try:
            pasta_saida = estado.get(
                "pasta_saida"
            )

            if not pasta_saida:
                ts_pasta = datetime.now().strftime(
                    "%Y-%m-%d_%H-%M-%S"
                )

                pasta_saida = os.path.join(
                    pasta_base_saida,
                    f"Varredura_SIOR_Encaminhamento_ERRO_{ts_pasta}",
                )

                os.makedirs(
                    pasta_saida,
                    exist_ok=True,
                )

                estado["pasta_saida"] = pasta_saida

            ts_erro = datetime.now().strftime(
                "%Y-%m-%d_%H-%M-%S"
            )

            caminho_xlsx = os.path.join(
                pasta_saida,
                f"logs_varredura_sior_encaminhamento_erro_{ts_erro}.xlsx",
            )

            exportar_resultado_excel(
                caminho_saida=caminho_xlsx,
                df_resultado=estado.get(
                    "df_resultado",
                    pd.DataFrame(),
                ),
                df_logs=pd.DataFrame(
                    estado["logs"]
                ),
                codigos_equipes=list(
                    equipes_selecionadas
                ),
            )

            estado["caminho_xlsx"] = caminho_xlsx

            registrar_arquivo(
                "XLSX de logs da execução com erro",
                caminho_xlsx,
            )

            btn_abrir_xlsx.visible = True

        except Exception as ex:
            try:
                log_execucao.value += (
                    f"Falha ao exportar XLSX de logs do erro: {ex}\n"
                )
            except Exception:
                pass

    # ======================================================
    # EXECUÇÃO
    # ======================================================
    def executar_varredura(e):
        try:
            equipes_execucao = obter_equipes_para_execucao()

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

        btn_executar.disabled = True
        btn_executar.text = "Executando..."

        progress.visible = True
        progress.value = None

        status.visible = True
        status.value = "Preparando varredura..."

        log_execucao.value = ""

        arquivos_gerados.controls.clear()
        arquivos_gerados.visible = False

        btn_abrir_xlsx.visible = False

        estado["df_resultado"] = pd.DataFrame()
        estado["logs"] = []
        estado["caminho_xlsx"] = None
        estado["pasta_saida"] = None

        page.update()

        def task():
            navegador = None

            try:
                bloquear()

                ts = datetime.now().strftime(
                    "%Y-%m-%d_%H-%M-%S"
                )

                pasta_saida = os.path.join(
                    pasta_base_saida,
                    f"Varredura_SIOR_Encaminhamento_{ts}",
                )

                os.makedirs(
                    pasta_saida,
                    exist_ok=True,
                )

                estado["pasta_saida"] = pasta_saida

                adicionar_log(
                    "👥 Equipes selecionadas para execução: "
                    + ", ".join(
                        map(str, equipes_execucao)
                    )
                )

                adicionar_log(
                    "🔐 Iniciando sessão SIOR..."
                )

                navegador, session = iniciar_sessao_sior(
                    log=adicionar_log
                )

                if navegador is None or session is None:
                    raise RuntimeError(
                        "Não foi possível iniciar a sessão SIOR."
                    )

                adicionar_log(
                    "✅ Sessão SIOR iniciada com sucesso."
                )

                url_tela = url_tela_encaminhamento(
                    equipes_execucao
                )

                adicionar_log(
                    "🌐 Acessando tela de Encaminhamento SIOR antes da varredura..."
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
                        "Não foi possível acessar a tela de Encaminhamento do SIOR."
                    )

                total_cookies = sincronizar_cookies_navegador_para_session(
                    navegador,
                    session,
                )

                preparar_headers_encaminhamento(
                    session,
                    equipes_execucao,
                )

                adicionar_log(
                    f"🍪 Cookies sincronizados navegador → requests: {total_cookies}."
                )

                inicializar_tela_encaminhamento(
                    session=session,
                    codigos_equipes=equipes_execucao,
                    log=adicionar_log,
                )

                adicionar_log(
                    "🚀 Iniciando varredura do painel de Encaminhamento..."
                )

                df_resultado = enviar_requisicao_get(
                    session=session,
                    codigos_equipes=equipes_execucao,
                    page_size=10000,
                    log=adicionar_log,
                )

                estado["df_resultado"] = df_resultado

                adicionar_log(
                    f"📊 Total de registros retornados: {len(df_resultado)}."
                )

                caminho_xlsx = os.path.join(
                    pasta_saida,
                    f"varredura_sior_encaminhamento_{ts}.xlsx",
                )

                adicionar_log(
                    "💾 Gerando XLSX da varredura com aba de logs..."
                )

                exportar_resultado_excel(
                    caminho_saida=caminho_xlsx,
                    df_resultado=df_resultado,
                    df_logs=pd.DataFrame(
                        estado["logs"]
                    ),
                    codigos_equipes=equipes_execucao,
                )

                estado["caminho_xlsx"] = caminho_xlsx

                adicionar_log(
                    "✅ XLSX da varredura gerado com sucesso contendo a aba Logs."
                )

                # Atualiza novamente o XLSX para incluir o log final de sucesso.
                exportar_resultado_excel(
                    caminho_saida=caminho_xlsx,
                    df_resultado=df_resultado,
                    df_logs=pd.DataFrame(
                        estado["logs"]
                    ),
                    codigos_equipes=equipes_execucao,
                )

                registrar_arquivo(
                    "XLSX da varredura com logs",
                    caminho_xlsx,
                )

                btn_abrir_xlsx.visible = True

                tipo_alerta = (
                    "success"
                    if len(df_resultado) > 0
                    else "warning"
                )

                mostrar_alerta(
                    ft,
                    page,
                    "Varredura finalizada",
                    (
                        "✅ Varredura de Encaminhamento concluída.\n\n"
                        f"Registros encontrados: {len(df_resultado)}\n\n"
                        "Os logs foram exportados dentro do próprio XLSX, "
                        "na aba Logs.\n\n"
                        f"Arquivo:\n{caminho_xlsx}"
                    ),
                    tipo=tipo_alerta,
                )

                try:
                    abrir_pasta_exportacao(
                        caminho_xlsx
                    )
                except Exception:
                    pass

            except Exception as ex:
                adicionar_log(
                    f"❌ Erro durante execução: {ex}"
                )

                adicionar_log(
                    traceback.format_exc()
                )

                exportar_xlsx_logs_em_erro()

                mostrar_alerta(
                    ft,
                    page,
                    "Erro na Varredura de Encaminhamento",
                    (
                        f"{ex}\n\n"
                        "Os logs da falha foram exportados em XLSX."
                    ),
                    tipo="error",
                )

            finally:
                try:
                    if navegador:
                        encerrar_navegador_sior(
                            navegador,
                            log=adicionar_log,
                        )
                except Exception:
                    pass

                btn_executar.disabled = False
                btn_executar.text = "Iniciar Varredura"

                progress.visible = False

                desbloquear()

                page.update()

        threading.Thread(
            target=task,
            daemon=True,
        ).start()

    # ======================================================
    # EVENTOS
    # ======================================================
    btn_executar.on_click = executar_varredura
    btn_abrir_xlsx.on_click = abrir_xlsx
    btn_limpar_logs.on_click = limpar_logs

    # ======================================================
    # LAYOUT
    # ======================================================
    return ft.Column(
        controls=[
            ft.Text(
                "Varredura SIOR - Encaminhamento",
                size=HEADING_FONT_SIZE,
                weight="bold",
            ),

            ft.Text(
                (
                    "Executa a varredura do painel de Encaminhamento SIOR, "
                    "gera planilha XLSX com os dados retornados e exporta "
                    "os logs da execução dentro do próprio XLSX."
                ),
                size=DEFAULT_FONT_SIZE,
                selectable=True,
            ),

            txt_saida,

            txt_info,

            seletor_equipes,

            ft.Row(
                controls=[
                    btn_executar,
                    btn_abrir_xlsx,
                    btn_limpar_logs,
                ],
                spacing=10,
                wrap=True,
            ),

            progress,

            status,

            arquivos_gerados,

            container_logs,
        ],
        spacing=12,
        expand=True,
        scroll=ft.ScrollMode.AUTO,
    )