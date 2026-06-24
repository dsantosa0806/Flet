# ==========================================================
# ABA ADMIN - SIOR ANÁLISE RECUPERAÇÃO CRÉDITOS PFE
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

from requests_data.requisicao_sior_recuperacao_pfe import (
    VALORES_PISO,
    PISO_PADRAO,
    URL_TELA_RECUPERACAO_PFE,
    preparar_headers_recuperacao_pfe,
    inicializar_tela_recuperacao_pfe,
    enviar_requisicao_get,
    exportar_resultados_recuperacao_pfe,
    exportar_xlsx_analise,
)

from utils.open_dir_downloads import abrir_pasta_exportacao
from utils.popups import mostrar_alerta


PAGE_SIZE_RECUPERACAO_PFE = 100000


# ==========================================================
# ABA
# ==========================================================
def aba_admin_sior_recuperacao_pfe(
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
        "caminho_csv": None,
        "caminho_xlsx": None,
        "pasta_saida": None,
        "piso": PISO_PADRAO,
    }

    # ======================================================
    # CONTROLES
    # ======================================================
    dropdown_piso = ft.Dropdown(
        label="Piso para projeção / classificação",
        value=str(PISO_PADRAO),
        width=260,
        options=[
            ft.dropdown.Option(str(valor))
            for valor in VALORES_PISO
        ],
        label_style=ft.TextStyle(
            size=DEFAULT_FONT_SIZE
        ),
        text_style=ft.TextStyle(
            size=DEFAULT_FONT_SIZE
        ),
    )

    txt_saida = ft.Text(
        f"📁 Saída padrão: {pasta_base_saida}",
        size=DEFAULT_FONT_SIZE,
        color=ft.Colors.GREY_600,
        selectable=True,
    )

    txt_info = ft.Text(
        (
            "A varredura consulta o painel Recuperação PFE do SIOR, gera um CSV bruto "
            "com todos os registros retornados e um XLSX apenas com abas analíticas. "
            "A classificação 'Acima do Piso' ou 'Abaixo do Piso' é calculada pelo campo ValorTotal."
        ),
        size=DEFAULT_FONT_SIZE,
        color=ft.Colors.GREY_700,
        selectable=True,
    )

    txt_resumo = ft.Text(
        "",
        size=DEFAULT_FONT_SIZE,
        visible=False,
        selectable=True,
    )

    btn_executar = ft.ElevatedButton(
        "Iniciar Varredura",
        icon=ft.Icons.PLAY_ARROW,
        bgcolor="green",
        color="white",
    )

    btn_abrir_xlsx = ft.ElevatedButton(
        "Abrir XLSX exportado",
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
        label="📝 Logs da Varredura Recuperação PFE",
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
                    "📋 Acompanhamento da execução",
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

        txt_resumo.value = ""
        txt_resumo.visible = False

        estado["df_resultado"] = pd.DataFrame()
        estado["logs"] = []
        estado["caminho_csv"] = None
        estado["caminho_xlsx"] = None
        estado["pasta_saida"] = None
        estado["piso"] = PISO_PADRAO

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

    def obter_piso_selecionado() -> float:
        try:
            piso = float(str(dropdown_piso.value).replace(",", "."))
        except Exception:
            raise ValueError(
                "Selecione um valor de piso válido."
            )

        if int(piso) not in VALORES_PISO:
            raise ValueError(
                "O piso selecionado não está na lista de valores permitidos."
            )

        return piso

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
                    f"Analise_Recuperacao_Creditos_PFE_ERRO_{ts_pasta}",
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
                f"logs_analise_recuperacao_creditos_pfe_erro_{ts_erro}.xlsx",
            )

            exportar_xlsx_analise(
                caminho_xlsx=caminho_xlsx,
                df=estado.get(
                    "df_resultado",
                    pd.DataFrame(),
                ),
                piso=estado.get(
                    "piso",
                    PISO_PADRAO,
                ),
                df_logs=pd.DataFrame(
                    estado["logs"]
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

    def atualizar_resumo_final(df_resultado: pd.DataFrame, piso: float):
        if df_resultado.empty:
            txt_resumo.value = (
                f"📊 Resultado: 0 registro encontrado | Piso: R$ {piso:,.2f}"
            )
            txt_resumo.visible = True
            return

        total_devedores = len(df_resultado)

        if "ClassificacaoPiso" in df_resultado.columns:
            mask_acima = df_resultado["ClassificacaoPiso"].eq("Acima do Piso")
            mask_abaixo = df_resultado["ClassificacaoPiso"].eq("Abaixo do Piso")
        else:
            mask_acima = pd.Series(False, index=df_resultado.index)
            mask_abaixo = pd.Series(False, index=df_resultado.index)

        devedores_acima = int(mask_acima.sum())
        devedores_abaixo = int(mask_abaixo.sum())

        if "QtdeAutosNumerico" in df_resultado.columns:
            qtde_autos = pd.to_numeric(
                df_resultado["QtdeAutosNumerico"],
                errors="coerce",
            ).fillna(0).astype(int)
        else:
            qtde_autos = pd.Series(0, index=df_resultado.index)

        total_autos = int(qtde_autos.sum())
        autos_acima = int(qtde_autos[mask_acima].sum())
        autos_abaixo = int(qtde_autos[mask_abaixo].sum())

        valor_total = (
            float(pd.to_numeric(df_resultado["ValorTotalNumerico"], errors="coerce").fillna(0).sum())
            if "ValorTotalNumerico" in df_resultado.columns
            else 0.0
        )

        percentual_autos_acima = round((autos_acima / total_autos) * 100, 2) if total_autos else 0
        percentual_autos_abaixo = round((autos_abaixo / total_autos) * 100, 2) if total_autos else 0

        txt_resumo.value = (
            f"📊 Devedores: {total_devedores} | Autos disponíveis: {total_autos} | "
            f"Autos acima do piso: {autos_acima} ({percentual_autos_acima}%) | "
            f"Autos abaixo do piso: {autos_abaixo} ({percentual_autos_abaixo}%) | "
            f"Devedores acima: {devedores_acima} | Devedores abaixo: {devedores_abaixo} | "
            f"ValorTotal somado: R$ {valor_total:,.2f} | Piso: R$ {piso:,.2f}"
        )
        txt_resumo.visible = True

    # ======================================================
    # EXECUÇÃO
    # ======================================================
    def executar_varredura(e):
        try:
            piso = obter_piso_selecionado()

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

        estado["piso"] = piso

        btn_executar.disabled = True
        btn_executar.text = "Executando..."

        dropdown_piso.disabled = True

        progress.visible = True
        progress.value = None

        status.visible = True
        status.value = "Preparando varredura..."

        log_execucao.value = ""

        arquivos_gerados.controls.clear()
        arquivos_gerados.visible = False

        txt_resumo.value = ""
        txt_resumo.visible = False

        btn_abrir_xlsx.visible = False

        estado["df_resultado"] = pd.DataFrame()
        estado["logs"] = []
        estado["caminho_csv"] = None
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
                    f"Analise_Recuperacao_Creditos_PFE_{ts}",
                )

                os.makedirs(
                    pasta_saida,
                    exist_ok=True,
                )

                estado["pasta_saida"] = pasta_saida

                adicionar_log(
                    f"💰 Piso selecionado para classificação: R$ {piso:,.2f}."
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

                adicionar_log(
                    "🌐 Acessando tela Recuperação de Créditos PFE antes da varredura..."
                )

                sucesso_tela = safe_get(
                    navegador=navegador,
                    url=URL_TELA_RECUPERACAO_PFE,
                    elemento_validacao=(By.TAG_NAME, "body"),
                    tentativas=3,
                    timeout_get=30,
                    timeout_elemento=12,
                    tempo_estabilizacao=1,
                )

                if not sucesso_tela:
                    raise RuntimeError(
                        "Não foi possível acessar a tela Recuperação de Créditos PFE do SIOR."
                    )

                total_cookies = sincronizar_cookies_navegador_para_session(
                    navegador,
                    session,
                )

                preparar_headers_recuperacao_pfe(
                    session
                )

                adicionar_log(
                    f"🍪 Cookies sincronizados navegador → requests: {total_cookies}."
                )

                inicializar_tela_recuperacao_pfe(
                    session=session,
                    log=adicionar_log,
                )

                adicionar_log(
                    "🚀 Iniciando varredura extensa do painel Recuperação PFE..."
                )

                df_resultado = enviar_requisicao_get(
                    session=session,
                    piso=piso,
                    page_size=PAGE_SIZE_RECUPERACAO_PFE,
                    log=adicionar_log,
                    timeout=120,
                )

                estado["df_resultado"] = df_resultado

                adicionar_log(
                    f"📊 Total de registros retornados: {len(df_resultado)}."
                )

                adicionar_log(
                    "💾 Gerando CSV bruto e XLSX analítico..."
                )

                caminhos = exportar_resultados_recuperacao_pfe(
                    pasta_saida=pasta_saida,
                    df=df_resultado,
                    piso=piso,
                    df_logs=pd.DataFrame(
                        estado["logs"]
                    ),
                )

                estado["caminho_csv"] = caminhos.get(
                    "csv"
                )

                estado["caminho_xlsx"] = caminhos.get(
                    "xlsx"
                )

                adicionar_log(
                    "✅ CSV bruto e XLSX analítico gerados com sucesso."
                )

                # Atualiza o XLSX uma última vez para incluir o log final.
                exportar_xlsx_analise(
                    caminho_xlsx=estado["caminho_xlsx"],
                    df=df_resultado,
                    piso=piso,
                    df_logs=pd.DataFrame(
                        estado["logs"]
                    ),
                )

                registrar_arquivo(
                    "CSV bruto com todos os registros",
                    estado["caminho_csv"],
                )

                registrar_arquivo(
                    "XLSX com análises dos devedores",
                    estado["caminho_xlsx"],
                )

                atualizar_resumo_final(
                    df_resultado,
                    piso,
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
                    "Análise finalizada",
                    (
                        "✅ Varredura de Recuperação PFE concluída.\n\n"
                        f"Registros encontrados: {len(df_resultado)}\n"
                        f"Piso utilizado: R$ {piso:,.2f}\n\n"
                        "Foi gerado um CSV bruto com todos os registros e um XLSX "
                        "com as abas de análise dos devedores.\n\n"
                        f"XLSX:\n{estado['caminho_xlsx']}\n\n"
                        f"CSV:\n{estado['caminho_csv']}"
                    ),
                    tipo=tipo_alerta,
                )

                try:
                    abrir_pasta_exportacao(
                        estado["caminho_xlsx"]
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
                    "Erro na Análise Recuperação PFE",
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

                dropdown_piso.disabled = False

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
                "Admin > SIOR > Análise Recuperação Créditos PFE",
                size=10,
                weight="bold",
            ),

            ft.Divider(),

            ft.Container(
                content=ft.Column(
                    controls=[
                        ft.Text(
                            "⚙️ Análise Recuperação Créditos PFE",
                            size=HEADING_FONT_SIZE,
                            weight="bold",
                        ),

                        txt_info,

                        ft.Row(
                            controls=[
                                dropdown_piso,
                            ],
                            vertical_alignment=ft.CrossAxisAlignment.END,
                            wrap=True,
                        ),

                        txt_saida,

                        ft.Row(
                            controls=[
                                btn_executar,
                                btn_abrir_xlsx,
                                btn_limpar_logs,
                            ],
                            spacing=10,
                            wrap=True,
                        ),

                        txt_resumo,
                    ],
                    spacing=10,
                    tight=True,
                ),
                padding=15,
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

            progress,

            status,

            arquivos_gerados,

            container_logs,

            alerta_dialogo,
        ],
        spacing=12,
        expand=True,
        scroll=ft.ScrollMode.AUTO,
    )
