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
    sincronizar_cookies_navegador_para_session
)

from requests_data.requisicoes_sior_cadastro_divida import (
    enviar_requisicao_get,
    get_data_sior
)

from utils.analisys import etl_data
from utils.open_dir_downloads import abrir_pasta_exportacao
from utils.popups import mostrar_alerta


def aba_admin_varredura_sior(
    ft,
    DEFAULT_FONT_SIZE,
    HEADING_FONT_SIZE,
    page,
    bloquear,
    desbloquear
):
    alerta_dialogo = ft.AlertDialog(
        modal=True,
        title=ft.Text(""),
        content=ft.Text(""),
        actions=[],
        open=False
    )

    page.dialog = alerta_dialogo

    pasta_base_saida = getattr(
        config,
        "PASTA_EXPORT_ADMIN",
        r"C:\Downloads"
    )

    input_equipes = ft.TextField(
        label="Equipes para varredura",
        value="1,2,3,4,5",
        width=300,
        hint_text="Ex: 1,2,3,4,5",
        label_style=ft.TextStyle(
            size=DEFAULT_FONT_SIZE
        ),
        text_style=ft.TextStyle(
            size=DEFAULT_FONT_SIZE
        )
    )

    txt_saida = ft.Text(
        f"📁 Saída padrão: {pasta_base_saida}",
        size=DEFAULT_FONT_SIZE,
        color=ft.Colors.GREY_600,
        selectable=True
    )

    btn_executar = ft.ElevatedButton(
        "Iniciar Varredura SIOR",
        icon=ft.Icons.PLAY_ARROW,
        bgcolor="green",
        color="white"
    )

    btn_limpar_logs = ft.ElevatedButton(
        "Limpar logs",
        icon=ft.Icons.CLEANING_SERVICES
    )

    progress = ft.ProgressBar(
        width=500,
        visible=False
    )

    status = ft.Text(
        "",
        size=DEFAULT_FONT_SIZE,
        color="blue",
        visible=False
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
        )
    )

    arquivos_gerados = ft.Column(
        controls=[],
        spacing=5,
        visible=False
    )

    def adicionar_log(mensagem: str):
        try:
            horario = datetime.now().strftime(
                "%H:%M:%S"
            )

            log_execucao.value += (
                f"[{horario}] {mensagem}\n"
            )

            status.value = mensagem
            status.visible = True

            page.update()

        except Exception:
            pass

    def limpar_logs(e):
        log_execucao.value = ""
        arquivos_gerados.controls.clear()
        arquivos_gerados.visible = False
        status.value = ""
        page.update()

    def parse_equipes():
        equipes = []

        partes = [
            p.strip()
            for p in str(input_equipes.value or "").split(",")
            if p.strip()
        ]

        if not partes:
            raise ValueError(
                "Informe ao menos uma equipe para varredura."
            )

        for parte in partes:
            if not parte.isdigit():
                raise ValueError(
                    f"Equipe inválida: {parte}. Use apenas números separados por vírgula."
                )

            equipes.append(
                int(parte)
            )

        return equipes

    def registrar_arquivo(label: str, caminho: str):
        arquivos_gerados.controls.append(
            ft.Text(
                f"✅ {label}: {caminho}",
                size=DEFAULT_FONT_SIZE,
                selectable=True
            )
        )

        arquivos_gerados.visible = True

    def executar_varredura(e):
        try:
            equipes = parse_equipes()

        except Exception as ex:
            mostrar_alerta(
                ft,
                page,
                "Validação",
                str(ex),
                tipo="error"
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

        page.update()

        def task():
            navegador = None

            try:
                bloquear()

                os.makedirs(
                    pasta_base_saida,
                    exist_ok=True
                )

                ts = datetime.now().strftime(
                    "%Y-%m-%d_%H-%M-%S"
                )

                pasta_saida = os.path.join(
                    pasta_base_saida,
                    f"Varredura_SIOR_Cadastro_Divida_{ts}"
                )

                os.makedirs(
                    pasta_saida,
                    exist_ok=True
                )

                adicionar_log(
                    "🔐 Iniciando sessão SIOR..."
                )

                navegador, session = iniciar_sessao_sior(
                    log=adicionar_log
                )

                URL_SUPERVISAO = (
                    "https://servicos.dnit.gov.br/sior/"
                    "Cobranca/SupervisaoSapiensAcompanhamento"
                )

                adicionar_log(
                    "🌐 Acessando tela de Supervisão/Acompanhamento antes da varredura..."
                )

                sucesso_supervisao = safe_get(
                    navegador=navegador,
                    url=URL_SUPERVISAO,
                    elemento_validacao=(By.TAG_NAME, "body"),
                    tentativas=3,
                    timeout_get=20,
                    timeout_elemento=10,
                    tempo_estabilizacao=1
                )

                if not sucesso_supervisao:
                    raise RuntimeError(
                        "Não foi possível acessar a tela de Supervisão/Acompanhamento do SIOR."
                    )

                sincronizar_cookies_navegador_para_session(
                    navegador,
                    session
                )

                session.headers.update({
                    "Referer": URL_SUPERVISAO,
                    "Origin": "https://servicos.dnit.gov.br",
                    "Host": "servicos.dnit.gov.br",
                    "X-Requested-With": "XMLHttpRequest"
                })

                adicionar_log(
                    "✅ Tela de Supervisão/Acompanhamento acessada e sessão sincronizada."
                )

                if navegador is None or session is None:
                    raise RuntimeError(
                        "Não foi possível iniciar a sessão SIOR."
                    )

                adicionar_log(
                    "✅ Sessão SIOR iniciada com sucesso."
                )

                # ==================================================
                # 1/4 - PAINEL DAS EQUIPES
                # ==================================================
                adicionar_log(
                    "🔍 [1/4] Iniciando varredura de dados do painel das equipes..."
                )

                resultado = enviar_requisicao_get(
                    session,
                    codigos_equipes=equipes,
                    log=adicionar_log
                )

                caminho_dados = os.path.join(
                    pasta_saida,
                    "dados.xlsx"
                )

                resultado.to_excel(
                    caminho_dados,
                    index=False
                )

                registrar_arquivo(
                    "Dados do painel",
                    caminho_dados
                )

                adicionar_log(
                    f"✅ [1/4] dados.xlsx gerado com {len(resultado)} registros."
                )

                if resultado.empty:
                    raise RuntimeError(
                        "A varredura do painel não retornou registros."
                    )

                # ==================================================
                # 2/4 - DETALHAMENTO
                # ==================================================
                adicionar_log(
                    "📄 [2/4] Iniciando varredura detalhada dos AITs localizados..."
                )

                resultado_varredura = get_data_sior(
                    session,
                    resultado,
                    log=adicionar_log
                )

                caminho_dados_finais = os.path.join(
                    pasta_saida,
                    "dados_finais.xlsx"
                )

                resultado_varredura.to_excel(
                    caminho_dados_finais,
                    index=False
                )

                registrar_arquivo(
                    "Dados finais detalhados",
                    caminho_dados_finais
                )

                adicionar_log(
                    f"✅ [2/4] dados_finais.xlsx gerado com {len(resultado_varredura)} registros."
                )

                if resultado_varredura.empty:
                    raise RuntimeError(
                        "A varredura detalhada não retornou registros."
                    )

                # ==================================================
                # 3/4 - ETL
                # ==================================================
                adicionar_log(
                    "🛠️ [3/4] Iniciando tratamento e estruturação dos dados finais..."
                )

                resultado_tratamento = etl_data(
                    resultado,
                    resultado_varredura
                )

                caminho_cadastro = os.path.join(
                    pasta_saida,
                    "dados_cadastro_SD.xlsx"
                )

                resultado_tratamento.to_excel(
                    caminho_cadastro,
                    index=False
                )

                registrar_arquivo(
                    "Dados tratados para cadastro",
                    caminho_cadastro
                )

                adicionar_log(
                    f"✅ [3/4] dados_cadastro_SD.xlsx gerado com {len(resultado_tratamento)} registros."
                )

                # ==================================================
                # 4/4 - EDITAIS
                # ==================================================
                adicionar_log(
                    "🛠️ [4/4] Gerando planilha de dados Editais..."
                )

                colunas_editais = [
                    "Número do Auto - Auto de Infração",
                    "Data de Publicação no DOU - Notificação de Autuação [2]",
                    "Data de Vencimento do Edital - Notificação de Autuação [2]",
                    "Data de Publicação no DOU - Notificação de Penalidade [2]",
                    "Data de Vencimento do Edital - Notificação de Penalidade [2]"
                ]

                colunas_existentes = [
                    col
                    for col in colunas_editais
                    if col in resultado_varredura.columns
                ]

                colunas_ausentes = [
                    col
                    for col in colunas_editais
                    if col not in resultado_varredura.columns
                ]

                if colunas_ausentes:
                    adicionar_log(
                        "⚠ Colunas ausentes na planilha de editais: "
                        + "; ".join(colunas_ausentes)
                    )

                if colunas_existentes:
                    df_editais = resultado_varredura[
                        colunas_existentes
                    ].copy()
                else:
                    df_editais = pd.DataFrame(
                        columns=colunas_editais
                    )

                caminho_editais = os.path.join(
                    pasta_saida,
                    "editais_analisar.xlsx"
                )

                df_editais.to_excel(
                    caminho_editais,
                    index=False
                )

                registrar_arquivo(
                    "Editais para análise",
                    caminho_editais
                )

                adicionar_log(
                    f"✅ [4/4] editais_analisar.xlsx gerado com {len(df_editais)} registros."
                )

                adicionar_log(
                    "🎉 Varredura SIOR concluída com sucesso."
                )

                mostrar_alerta(
                    ft,
                    page,
                    "Varredura concluída",
                    f"✅ Arquivos gerados em:\n{pasta_saida}",
                    tipo="success"
                )

                try:
                    abrir_pasta_exportacao(
                        pasta_saida
                    )
                except Exception:
                    pass

            except Exception as ex:
                adicionar_log(
                    f"❌ Erro durante a varredura: {ex}"
                )

                adicionar_log(
                    traceback.format_exc()
                )

                mostrar_alerta(
                    ft,
                    page,
                    "Erro na varredura",
                    str(ex),
                    tipo="error"
                )

            finally:
                try:
                    if navegador:
                        encerrar_navegador_sior(
                            navegador,
                            log=adicionar_log
                        )
                except Exception:
                    pass

                btn_executar.disabled = False
                btn_executar.text = "Iniciar Varredura SIOR"
                progress.visible = False

                desbloquear()
                page.update()

        threading.Thread(
            target=task,
            daemon=True
        ).start()

    btn_executar.on_click = executar_varredura
    btn_limpar_logs.on_click = limpar_logs

    return ft.Column(
        controls=[
            ft.Row(
                [
                    ft.Text(
                        "Admin > SIOR > Varredura Cadastro Dívida",
                        size=10,
                        weight="bold"
                    )
                ],
                alignment="center"
            ),

            ft.Divider(),

            ft.Container(
                content=ft.Column(
                    controls=[
                        ft.Text(
                            "⚙️ Varredura SIOR para Cadastro em Dívida",
                            size=HEADING_FONT_SIZE,
                            weight="bold"
                        ),

                        ft.Text(
                            "Este módulo realiza a varredura do painel das equipes, "
                            "detalha os AITs localizados, executa o tratamento dos dados "
                            "e gera as planilhas de saída para análise/cadastro.",
                            size=DEFAULT_FONT_SIZE
                        ),

                        ft.Row(
                            controls=[
                                input_equipes,
                                btn_executar,
                                btn_limpar_logs
                            ],
                            vertical_alignment=ft.CrossAxisAlignment.END
                        ),

                        txt_saida,
                    ],
                    spacing=10
                ),
                padding=15,
                border_radius=10,
                border=ft.border.all(
                    1,
                    ft.Colors.GREY_600
                ),
                bgcolor=ft.Colors.with_opacity(
                    0.05,
                    ft.Colors.ON_SURFACE
                )
            ),

            status,
            progress,

            ft.Container(
                content=ft.Column(
                    controls=[
                        ft.Text(
                            "📋 Acompanhamento da execução",
                            size=DEFAULT_FONT_SIZE + 1,
                            weight="bold"
                        ),
                        log_execucao
                    ],
                    spacing=10
                ),
                padding=10,
                border_radius=10,
                border=ft.border.all(
                    1,
                    ft.Colors.GREY_600
                ),
                bgcolor=ft.Colors.with_opacity(
                    0.05,
                    ft.Colors.ON_SURFACE
                )
            ),

            arquivos_gerados,

            alerta_dialogo
        ],
        expand=True,
        spacing=10,
        scroll=ft.ScrollMode.AUTO
    )