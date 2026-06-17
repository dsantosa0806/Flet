import os
import sys
import threading
import traceback
from datetime import datetime

import config

from navegador.login_super_sapiens import obter_token

from requests_data.requisicao_sapiens_extintos_pagamento import (
    gerar_relatorios,
    baixar_relatorios,
    extrair_relatorios_downloads,
    DOWNLOAD_DIR,
    PASTA_MODULO,
    ARQUIVO_CONSOLIDADO
)

from utils.open_dir_downloads import abrir_pasta_exportacao
from utils.popups import mostrar_alerta


# ==========================================================
# CAPTURA DE PRINTS PARA O LOG DO FLET
# ==========================================================
class FletLogWriter:
    def __init__(self, callback):
        self.callback = callback
        self.buffer = ""

    def write(self, texto):
        if not texto:
            return

        self.buffer += texto

        while "\n" in self.buffer:
            linha, self.buffer = self.buffer.split("\n", 1)

            linha = linha.strip()

            if linha:
                self.callback(linha)

    def flush(self):
        if self.buffer.strip():
            self.callback(self.buffer.strip())
            self.buffer = ""


# ==========================================================
# ABA ADMIN - EXTINTOS POR PAGAMENTO
# ==========================================================
def aba_admin_sapiens_extintos_pagamento(
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

    # ======================================================
    # INPUTS
    # ======================================================
    input_data_inicio = ft.TextField(
        label="Data início",
        hint_text="Ex: 2026-06-08",
        width=180,
        value="",
        label_style=ft.TextStyle(
            size=DEFAULT_FONT_SIZE
        ),
        text_style=ft.TextStyle(
            size=DEFAULT_FONT_SIZE
        )
    )

    input_data_fim = ft.TextField(
        label="Data fim",
        hint_text="Ex: 2026-06-14",
        width=180,
        value="",
        label_style=ft.TextStyle(
            size=DEFAULT_FONT_SIZE
        ),
        text_style=ft.TextStyle(
            size=DEFAULT_FONT_SIZE
        )
    )

    txt_saida = ft.Text(
        f"📁 Saída esperada: {pasta_base_saida}",
        size=DEFAULT_FONT_SIZE,
        color=ft.Colors.GREY_600,
        selectable=True
    )

    # ======================================================
    # BOTÕES
    # ======================================================
    btn_executar = ft.ElevatedButton(
        "Gerar Relatórios",
        icon=ft.Icons.PLAY_ARROW,
        bgcolor="green",
        color="white"
    )

    btn_limpar_logs = ft.ElevatedButton(
        "Limpar logs",
        icon=ft.Icons.CLEANING_SERVICES
    )

    btn_abrir_pasta = ft.ElevatedButton(
        "Abrir pasta",
        icon=ft.Icons.FOLDER_OPEN,
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
        label="📝 Logs da Execução",
        multiline=True,
        read_only=True,
        expand=True,
        min_lines=20,
        max_lines=20,
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

    ultima_pasta_saida = {
        "path": pasta_base_saida
    }

    # ======================================================
    # HELPERS
    # ======================================================
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

    def registrar_arquivo(label: str, caminho: str):
        arquivos_gerados.controls.append(
            ft.Text(
                f"✅ {label}: {caminho}",
                size=DEFAULT_FONT_SIZE,
                selectable=True
            )
        )

        arquivos_gerados.visible = True

        try:
            if caminho and os.path.exists(caminho):
                ultima_pasta_saida["path"] = (
                    caminho
                    if os.path.isdir(caminho)
                    else os.path.dirname(caminho)
                )
        except Exception:
            pass

        page.update()

    def limpar_logs(e):
        log_execucao.value = ""
        arquivos_gerados.controls.clear()
        arquivos_gerados.visible = False
        status.value = ""
        status.visible = False
        btn_abrir_pasta.visible = False
        page.update()

    def abrir_pasta(e):
        try:
            caminho = ultima_pasta_saida.get(
                "path",
                pasta_base_saida
            )

            if caminho:
                abrir_pasta_exportacao(caminho)

        except Exception as ex:
            mostrar_alerta(
                ft,
                page,
                "Erro ao abrir pasta",
                str(ex),
                tipo="error"
            )

            page.update()

    def validar_periodo():
        data_inicio = str(
            input_data_inicio.value or ""
        ).strip()

        data_fim = str(
            input_data_fim.value or ""
        ).strip()

        if not data_inicio:
            raise ValueError(
                "Informe a data início."
            )

        if not data_fim:
            raise ValueError(
                "Informe a data fim."
            )

        try:
            dt_inicio = datetime.strptime(
                data_inicio,
                "%Y-%m-%d"
            )

            dt_fim = datetime.strptime(
                data_fim,
                "%Y-%m-%d"
            )

        except ValueError:
            raise ValueError(
                "As datas devem estar no formato AAAA-MM-DD. Exemplo: 2026-06-08."
            )

        if dt_fim < dt_inicio:
            raise ValueError(
                "A data fim não pode ser menor que a data início."
            )

        return data_inicio, data_fim

    def localizar_arquivo_consolidado():
        """
        Tenta localizar o arquivo final esperado pelo pipeline antigo.
        Mantém compatibilidade caso a função extrair_relatorios_downloads()
        não retorne caminho.
        """

        nomes_possiveis = [
            "Relatorios_Consolidados.csv",
            "Relatorios_Consolidados.xlsx"
        ]

        pastas_possiveis = [
            os.getcwd(),
            pasta_base_saida,
            os.path.expanduser("~"),
            os.path.join(
                os.path.expanduser("~"),
                "Downloads"
            )
        ]

        for pasta in pastas_possiveis:
            for nome in nomes_possiveis:
                caminho = os.path.join(
                    pasta,
                    nome
                )

                if os.path.exists(caminho):
                    return caminho

        return None

    # ======================================================
    # EXECUÇÃO
    # ======================================================
    def executar_relatorios(e):
        try:
            data_inicio, data_fim = validar_periodo()

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
        btn_abrir_pasta.visible = False

        progress.visible = True
        progress.value = None

        status.visible = True
        status.value = "Preparando execução..."

        log_execucao.value = ""
        arquivos_gerados.controls.clear()
        arquivos_gerados.visible = False

        page.update()

        def task():
            stdout_original = sys.stdout
            stderr_original = sys.stderr

            try:
                bloquear()

                os.makedirs(
                    pasta_base_saida,
                    exist_ok=True
                )

                writer = FletLogWriter(
                    adicionar_log
                )

                sys.stdout = writer
                sys.stderr = writer

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
                    f"📅 Período de referência: {data_inicio} → {data_fim}"
                )

                adicionar_log(
                    "🚀 Iniciando geração de relatórios diários..."
                )

                # ==================================================
                # 1 - GERAR RELATÓRIOS
                # ==================================================
                relatorios = gerar_relatorios(
                    token,
                    data_inicio,
                    data_fim
                )

                if not relatorios:
                    adicionar_log(
                        "⚠️ Nenhum relatório foi gerado. Encerrando execução."
                    )

                    mostrar_alerta(
                        ft,
                        page,
                        "Sem relatórios",
                        "Nenhum relatório foi gerado para o período informado.",
                        tipo="warning"
                    )

                    return

                adicionar_log(
                    f"✅ {len(relatorios)} relatório(s) solicitado(s)/gerado(s)."
                )

                # ==================================================
                # 2 - DOWNLOAD
                # ==================================================
                adicionar_log(
                    "📦 Iniciando download dos relatórios gerados..."
                )

                arquivos = baixar_relatorios(
                    token,
                    relatorios
                )

                if not arquivos:
                    adicionar_log(
                        "⚠️ Nenhum arquivo foi baixado. Verifique logs e permissões."
                    )

                    mostrar_alerta(
                        ft,
                        page,
                        "Sem downloads",
                        "Nenhum arquivo foi baixado. Verifique logs e permissões.",
                        tipo="warning"
                    )

                    return

                adicionar_log(
                    "🧾 Relatórios baixados:"
                )

                for arquivo in arquivos:
                    adicionar_log(
                        f"📂 {arquivo}"
                    )

                    registrar_arquivo(
                        "Relatório baixado",
                        str(arquivo)
                    )

                # ==================================================
                # 3 - CONSOLIDAÇÃO
                # ==================================================
                adicionar_log(
                    "📊 Iniciando consolidação dos relatórios extraídos..."
                )

                resultado_consolidacao = extrair_relatorios_downloads()

                # Caso sua função retorne um caminho ou lista de caminhos
                if resultado_consolidacao:
                    if isinstance(
                        resultado_consolidacao,
                        (list, tuple, set)
                    ):
                        for item in resultado_consolidacao:
                            registrar_arquivo(
                                "Arquivo consolidado",
                                str(item)
                            )
                    else:
                        registrar_arquivo(
                            "Arquivo consolidado",
                            str(resultado_consolidacao)
                        )

                # Caso sua função antiga não retorne nada
                else:
                    consolidado = localizar_arquivo_consolidado()

                    if consolidado:
                        registrar_arquivo(
                            "Arquivo consolidado",
                            consolidado
                        )
                    else:
                        adicionar_log(
                            "⚠️ Consolidação finalizada, mas não consegui localizar automaticamente o arquivo Relatorios_Consolidados."
                        )

                adicionar_log(
                    "✅ Processo concluído com sucesso!"
                )

                adicionar_log(
                    "📁 Arquivo final esperado: Relatorios_Consolidados.csv na raiz do projeto."
                )

                btn_abrir_pasta.visible = True

                mostrar_alerta(
                    ft,
                    page,
                    "Processo concluído",
                    "✅ Relatórios gerados, baixados e consolidados com sucesso.",
                    tipo="success"
                )

                try:
                    abrir_pasta_exportacao(
                        ultima_pasta_saida.get(
                            "path",
                            pasta_base_saida
                        )
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

                mostrar_alerta(
                    ft,
                    page,
                    "Erro na execução",
                    str(ex),
                    tipo="error"
                )

            finally:
                try:
                    sys.stdout = stdout_original
                    sys.stderr = stderr_original
                except Exception:
                    pass

                btn_executar.disabled = False
                btn_executar.text = "Gerar Relatórios"
                progress.visible = False

                desbloquear()
                page.update()

        threading.Thread(
            target=task,
            daemon=True
        ).start()

    # ======================================================
    # EVENTS
    # ======================================================
    btn_executar.on_click = executar_relatorios
    btn_limpar_logs.on_click = limpar_logs
    btn_abrir_pasta.on_click = abrir_pasta

    # ======================================================
    # RETURN
    # ======================================================
    return ft.Column(
        controls=[
            ft.Row(
                [
                    ft.Text(
                        "Admin > Super Sapiens > Extintos por Pagamento",
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
                            "⚙️ Relatórios Super Sapiens - Extintos por Pagamento",
                            size=HEADING_FONT_SIZE,
                            weight="bold"
                        ),

                        ft.Text(
                            "Este módulo gera um relatório diário para cada dia do período informado, "
                            "baixa os arquivos gerados e executa a consolidação final.",
                            size=DEFAULT_FONT_SIZE
                        ),

                        ft.Row(
                            controls=[
                                input_data_inicio,
                                input_data_fim,
                                btn_executar,
                                btn_limpar_logs,
                                btn_abrir_pasta
                            ],
                            vertical_alignment=ft.CrossAxisAlignment.END,
                            wrap=True
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