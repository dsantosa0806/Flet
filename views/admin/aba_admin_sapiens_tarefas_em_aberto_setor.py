# ==========================================================
# ABA ADMIN - SUPER SAPIENS
# TAREFAS EM ABERTO EM UM SETOR
# ==========================================================
import os
import threading
import traceback
from datetime import datetime

import pandas as pd

import config

from utils.popups import mostrar_alerta
from navegador.login_super_sapiens import obter_token

from requests_data.requisicao_tarefas_em_aberto_setor import (
    SETOR_ID_PADRAO,
    SETOR_NOME_PADRAO,
    executar_fluxo_tarefas_em_aberto_setor,
)


def aba_admin_sapiens_tarefas_em_aberto_setor(
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

    txt_saida = ft.Text(
        f"📁 Saída padrão: {pasta_base_saida}",
        size=DEFAULT_FONT_SIZE,
        color=ft.Colors.GREY_600,
        selectable=True
    )

    txt_setor = ft.Text(
        f"Setor padrão: {SETOR_NOME_PADRAO} ({SETOR_ID_PADRAO})",
        size=DEFAULT_FONT_SIZE,
        color=ft.Colors.GREY_600,
        selectable=True
    )

    btn_executar = ft.ElevatedButton(
        "Gerar Relatórios",
        icon=ft.Icons.PLAY_ARROW,
        bgcolor="green",
        color="white"
    )

    btn_abrir_relatorio = ft.ElevatedButton(
        "Abrir relatório gerado",
        icon=ft.Icons.OPEN_IN_NEW,
        visible=False
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
        label="📝 Logs de execução",
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

    pasta_saida_atual = {
        "path": None
    }

    arquivo_relatorio_atual = {
        "path": None
    }

    registros_logs = []

    # ======================================================
    # FUNÇÕES AUXILIARES
    # ======================================================
    def adicionar_log(
        mensagem: str,
        nivel: str = "INFO"
    ):
        try:
            agora = datetime.now()

            horario = agora.strftime(
                "%H:%M:%S"
            )

            data_hora = agora.strftime(
                "%Y-%m-%d %H:%M:%S"
            )

            mensagem = str(
                mensagem
            )

            log_execucao.value += (
                f"[{horario}] {mensagem}\n"
            )

            registros_logs.append({
                "DataHora": data_hora,
                "Nivel": nivel,
                "Mensagem": mensagem
            })

            status.value = mensagem
            status.visible = True

            page.update()

        except Exception:
            pass

    def registrar_arquivo(
        label: str,
        caminho: str
    ):
        arquivos_gerados.controls.append(
            ft.Text(
                f"✅ {label}: {caminho}",
                size=DEFAULT_FONT_SIZE,
                selectable=True
            )
        )

        arquivos_gerados.visible = True

    def salvar_logs_xlsx(
        pasta_saida: str
    ) -> str:
        os.makedirs(
            pasta_saida,
            exist_ok=True
        )

        caminho_logs = os.path.join(
            pasta_saida,
            "Logs_Tarefas_Em_Aberto_Setor.xlsx"
        )

        df_logs = pd.DataFrame(
            registros_logs
        )

        if df_logs.empty:
            df_logs = pd.DataFrame([
                {
                    "DataHora": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "Nivel": "INFO",
                    "Mensagem": "Nenhum log registrado."
                }
            ])

        with pd.ExcelWriter(
            caminho_logs,
            engine="openpyxl"
        ) as writer:
            df_logs.to_excel(
                writer,
                sheet_name="Logs",
                index=False
            )

        return caminho_logs

    def abrir_arquivo_relatorio(caminho: str):
        try:
            if not caminho or not os.path.exists(caminho):
                raise FileNotFoundError(
                    "Arquivo do relatório não encontrado."
                )

            os.startfile(
                os.path.normpath(caminho)
            )

            adicionar_log(
                f"📂 Relatório aberto: {caminho}"
            )

        except Exception as ex:
            adicionar_log(
                f"⚠️ Não foi possível abrir o relatório automaticamente: {ex}",
                nivel="ERRO"
            )

            mostrar_alerta(
                ft,
                page,
                "Abrir relatório",
                f"Não foi possível abrir o arquivo automaticamente.\n\n{ex}",
                tipo="warning"
            )

    def abrir_relatorio_click(e):
        caminho = arquivo_relatorio_atual.get(
            "path"
        )

        abrir_arquivo_relatorio(
            caminho
        )

    btn_abrir_relatorio.on_click = abrir_relatorio_click

    # ======================================================
    # EXECUÇÃO PRINCIPAL
    # ======================================================
    def executar(e):
        btn_executar.disabled = True
        btn_executar.text = "Executando..."

        progress.visible = True
        progress.value = None

        status.visible = True
        status.value = "Preparando geração do relatório..."

        log_execucao.value = ""
        registros_logs.clear()

        arquivos_gerados.controls.clear()
        arquivos_gerados.visible = False

        arquivo_relatorio_atual["path"] = None
        btn_abrir_relatorio.visible = False

        page.update()

        def task():
            pasta_saida = None

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
                    f"Sapiens_Tarefas_Em_Aberto_Setor_{ts}"
                )

                pasta_downloads = os.path.join(
                    pasta_saida,
                    "downloads"
                )

                os.makedirs(
                    pasta_downloads,
                    exist_ok=True
                )

                pasta_saida_atual["path"] = pasta_saida

                adicionar_log(
                    "🔐 Obtendo token de autenticação do Super Sapiens..."
                )

                token = obter_token()

                if not token:
                    raise RuntimeError(
                        "Não foi possível obter token válido do Super Sapiens."
                    )

                adicionar_log(
                    "✅ Token obtido com sucesso."
                )

                adicionar_log(
                    f"🏢 Setor: {SETOR_NOME_PADRAO} ({SETOR_ID_PADRAO})"
                )

                adicionar_log(
                    f"📁 Pasta de saída: {pasta_saida}"
                )

                adicionar_log(
                    "\n🚀 Iniciando geração e download do relatório..."
                )

                resultado = executar_fluxo_tarefas_em_aberto_setor(
                    token=token,
                    diretorio_downloads=pasta_downloads,
                    setor_id=SETOR_ID_PADRAO,
                    log=adicionar_log
                )

                arquivo_relatorio = resultado.get(
                    "arquivo"
                )

                if arquivo_relatorio:
                    arquivo_relatorio_atual["path"] = arquivo_relatorio

                    registrar_arquivo(
                        "Relatório XLSX",
                        arquivo_relatorio
                    )

                    btn_abrir_relatorio.visible = True

                    adicionar_log(
                        "📂 Abrindo relatório gerado..."
                    )

                    abrir_arquivo_relatorio(
                        arquivo_relatorio
                    )

                adicionar_log(
                    f"📄 Relatório ID: {resultado.get('id_relatorio')}"
                )

                adicionar_log(
                    f"📎 Documento ID: {resultado.get('id_documento')}"
                )

                adicionar_log(
                    f"🧩 Componente digital ID: {resultado.get('id_componente')}"
                )

                adicionar_log(
                    "\n🧾 Salvando logs em XLSX..."
                )

                caminho_logs = salvar_logs_xlsx(
                    pasta_saida
                )

                registrar_arquivo(
                    "Logs XLSX",
                    caminho_logs
                )

                adicionar_log(
                    f"✅ Logs salvos em: {caminho_logs}"
                )

                adicionar_log(
                    "\n🎉 Processo concluído com sucesso."
                )

                mostrar_alerta(
                    ft,
                    page,
                    "Relatório concluído",
                    f"✅ Arquivos gerados em:\n{pasta_saida}",
                    tipo="success"
                )

            except Exception as ex:
                adicionar_log(
                    f"❌ Erro durante a execução: {ex}",
                    nivel="ERRO"
                )

                adicionar_log(
                    traceback.format_exc(),
                    nivel="ERRO"
                )

                try:
                    if pasta_saida:
                        caminho_logs = salvar_logs_xlsx(
                            pasta_saida
                        )

                        registrar_arquivo(
                            "Logs XLSX",
                            caminho_logs
                        )

                        adicionar_log(
                            f"🧾 Logs de erro salvos em: {caminho_logs}"
                        )

                except Exception as ex_logs:
                    adicionar_log(
                        f"⚠️ Falha ao salvar XLSX dos logs: {ex_logs}",
                        nivel="ERRO"
                    )

                mostrar_alerta(
                    ft,
                    page,
                    "Erro na geração do relatório",
                    str(ex),
                    tipo="error"
                )

            finally:
                btn_executar.disabled = False
                btn_executar.text = "Gerar Relatórios"

                progress.visible = False

                desbloquear()
                page.update()

        threading.Thread(
            target=task,
            daemon=True
        ).start()

    btn_executar.on_click = executar

    # ======================================================
    # RETURN
    # ======================================================
    return ft.Column(
        controls=[
            ft.Row(
                [
                    ft.Text(
                        "Admin > Super Sapiens > Tarefas em Aberto no Setor",
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
                            "⚙️ Tarefas em Aberto no Setor - Super Sapiens",
                            size=HEADING_FONT_SIZE,
                            weight="bold"
                        ),

                        ft.Text(
                            (
                                "Este módulo gera o relatório "
                                "'TAREFAS EM ABERTO EM UM SETOR ATUALMENTE (DETALHADO)', "
                                "baixa o XLSX disponibilizado pelo Super Sapiens "
                                "e gera uma planilha XLSX com os logs da execução."
                            ),
                            size=DEFAULT_FONT_SIZE
                        ),

                        ft.Row(
                            controls=[
                                btn_executar,
                                btn_abrir_relatorio
                            ],
                            vertical_alignment=ft.CrossAxisAlignment.END,
                            wrap=True
                        ),

                        txt_setor,
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