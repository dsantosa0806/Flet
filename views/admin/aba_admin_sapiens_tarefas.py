# ==========================================================
# ABA ADMIN - SUPER SAPIENS - RELATÓRIOS DE TAREFAS
# ==========================================================
import os
import re
import threading
import traceback
from datetime import datetime

import pandas as pd

import config

from utils.open_dir_downloads import abrir_pasta_exportacao
from utils.popups import mostrar_alerta

from requests_data.requisicao_sapiens_tarefas import (
    USUARIOS_NOMES,
    gerar_relatorios,
    baixar_relatorios,
    extrair_relatorios_downloads
)

from navegador.login_super_sapiens import obter_token


def aba_admin_sapiens_tarefas(
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

    data_hoje = datetime.now().strftime(
        "%Y-%m-%d"
    )

    usuarios_padrao = ", ".join(
        str(codigo)
        for codigo in USUARIOS_NOMES.keys()
    )

    # ======================================================
    # COMPONENTES DE INPUT
    # ======================================================
    input_data_ref = ft.TextField(
        label="Data de referência",
        value=data_hoje,
        width=180,
        hint_text="AAAA-MM-DD",
        label_style=ft.TextStyle(
            size=DEFAULT_FONT_SIZE
        ),
        text_style=ft.TextStyle(
            size=DEFAULT_FONT_SIZE
        )
    )

    input_usuarios = ft.TextField(
        label="Usuários",
        value=usuarios_padrao,
        multiline=True,
        min_lines=3,
        max_lines=5,
        width=520,
        hint_text="Ex: 324199, 61554, 551246, 324236, 313836",
        label_style=ft.TextStyle(
            size=DEFAULT_FONT_SIZE
        ),
        text_style=ft.TextStyle(
            size=DEFAULT_FONT_SIZE
        )
    )

    txt_mapeamento = ft.Text(
        " | ".join(
            f"{codigo} = {nome}"
            for codigo, nome in USUARIOS_NOMES.items()
        ),
        size=DEFAULT_FONT_SIZE,
        color=ft.Colors.GREY_600,
        selectable=True
    )

    txt_saida = ft.Text(
        f"📁 Saída padrão: {pasta_base_saida}",
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
        "Abrir pasta de saída",
        icon=ft.Icons.FOLDER_OPEN,
        visible=False
    )

    # ======================================================
    # STATUS / PROGRESSO / LOGS
    # ======================================================
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
        label="📝 Logs da geração dos relatórios",
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

    # ======================================================
    # FUNÇÕES AUXILIARES DA ABA
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

    def limpar_logs(e):
        log_execucao.value = ""
        arquivos_gerados.controls.clear()
        arquivos_gerados.visible = False
        status.value = ""
        btn_abrir_pasta.visible = False
        pasta_saida_atual["path"] = None
        page.update()

    def abrir_pasta(e):
        caminho = pasta_saida_atual.get("path")

        if caminho and os.path.exists(caminho):
            abrir_pasta_exportacao(caminho)
        else:
            mostrar_alerta(
                ft,
                page,
                "Pasta não encontrada",
                "Nenhuma pasta de saída válida foi encontrada para abrir.",
                tipo="error"
            )

        page.update()

    def validar_data_ref(data_ref: str):
        data_ref = str(data_ref or "").strip()

        if not data_ref:
            raise ValueError(
                "Informe a data de referência."
            )

        if not re.match(r"^\d{4}-\d{2}-\d{2}$", data_ref):
            raise ValueError(
                "A data de referência deve estar no formato AAAA-MM-DD. Exemplo: 2026-06-16."
            )

        try:
            datetime.strptime(
                data_ref,
                "%Y-%m-%d"
            )
        except Exception:
            raise ValueError(
                "Data de referência inválida."
            )

        return data_ref

    def parse_usuarios():
        texto = str(input_usuarios.value or "")

        partes = [
            p.strip()
            for p in re.split(r"[,\n;\s]+", texto)
            if p.strip()
        ]

        if not partes:
            raise ValueError(
                "Informe ao menos um usuário."
            )

        usuarios = []

        for parte in partes:
            if not parte.isdigit():
                raise ValueError(
                    f"Usuário inválido: {parte}. Use apenas códigos numéricos."
                )

            codigo = int(parte)

            if codigo not in USUARIOS_NOMES:
                raise ValueError(
                    (
                        f"Usuário {codigo} não está no mapeamento. "
                        f"Atualize USUARIOS_NOMES em requests_data/requisicao_sapiens_tarefas.py."
                    )
                )

            usuarios.append(codigo)

        # remove duplicados mantendo a ordem
        usuarios_sem_duplicidade = list(
            dict.fromkeys(usuarios)
        )

        return usuarios_sem_duplicidade

    # ======================================================
    # EXECUÇÃO PRINCIPAL
    # ======================================================
    def executar(e):
        try:
            data_ref = validar_data_ref(
                input_data_ref.value
            )

            usuarios = parse_usuarios()

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
        status.value = "Preparando geração dos relatórios..."

        log_execucao.value = ""

        arquivos_gerados.controls.clear()
        arquivos_gerados.visible = False

        page.update()

        def task():
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
                    f"Sapiens_Tarefas_{data_ref}_{ts}"
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

                nomes = [
                    f"{USUARIOS_NOMES.get(u, str(u))} ({u})"
                    for u in usuarios
                ]

                adicionar_log(
                    f"📅 Data de referência: {data_ref}"
                )

                adicionar_log(
                    "👥 Usuários selecionados: " + ", ".join(nomes)
                )

                adicionar_log(
                    "\n🚀 Iniciando geração dos relatórios..."
                )

                relatorios = gerar_relatorios(
                    token=token,
                    data_referencia=data_ref,
                    usuarios=usuarios,
                    log=adicionar_log
                )

                adicionar_log(
                    f"\n✅ Total de relatórios solicitados com sucesso: {len(relatorios)}"
                )

                if not relatorios:
                    raise RuntimeError(
                        "Nenhum relatório foi gerado. Verifique os logs acima."
                    )

                adicionar_log(
                    "\n📦 Iniciando download dos relatórios..."
                )

                arquivos = baixar_relatorios(
                    token=token,
                    relatorios=relatorios,
                    diretorio_downloads=pasta_downloads,
                    log=adicionar_log
                )

                adicionar_log(
                    f"\n✅ Total de arquivos baixados: {len(arquivos)}"
                )

                for arquivo in arquivos:
                    registrar_arquivo(
                        "Relatório XLSX",
                        arquivo
                    )

                if not arquivos:
                    raise RuntimeError(
                        "Nenhum arquivo foi baixado. Verifique os logs acima."
                    )

                adicionar_log(
                    "\n🧾 Iniciando consolidação dos relatórios baixados..."
                )

                caminho_csv = os.path.join(
                    pasta_saida,
                    "Relatorios_Consolidados.csv"
                )

                df_final = extrair_relatorios_downloads(
                    diretorio_downloads=pasta_downloads,
                    caminho_saida_csv=caminho_csv,
                    log=adicionar_log
                )

                registrar_arquivo(
                    "CSV consolidado",
                    caminho_csv
                )

                # Opcional: também gera XLSX consolidado
                caminho_xlsx = os.path.join(
                    pasta_saida,
                    "Relatorios_Consolidados.xlsx"
                )

                try:
                    with pd.ExcelWriter(
                        caminho_xlsx,
                        engine="openpyxl"
                    ) as writer:
                        df_final.to_excel(
                            writer,
                            sheet_name="Consolidado",
                            index=False
                        )

                    registrar_arquivo(
                        "XLSX consolidado",
                        caminho_xlsx
                    )

                    adicionar_log(
                        f"📁 XLSX consolidado salvo em: {caminho_xlsx}"
                    )

                except Exception as ex_xlsx:
                    adicionar_log(
                        f"⚠️ CSV gerado, mas houve falha ao gerar XLSX consolidado: {ex_xlsx}"
                    )

                adicionar_log(
                    "\n🎉 Processo concluído com sucesso."
                )

                btn_abrir_pasta.visible = True

                mostrar_alerta(
                    ft,
                    page,
                    "Relatórios concluídos",
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
                    f"❌ Erro durante a execução: {ex}"
                )

                adicionar_log(
                    traceback.format_exc()
                )

                mostrar_alerta(
                    ft,
                    page,
                    "Erro na geração dos relatórios",
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

    # ======================================================
    # EVENTOS
    # ======================================================
    btn_executar.on_click = executar
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
                        "Admin > Super Sapiens > Relatórios de Tarefas",
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
                            "⚙️ Relatórios de Tarefas - Super Sapiens",
                            size=HEADING_FONT_SIZE,
                            weight="bold"
                        ),

                        ft.Text(
                            (
                                "Este módulo gera os relatórios de tarefas por usuário, "
                                "baixa os arquivos XLSX do Super Sapiens e cria um consolidado CSV/XLSX."
                            ),
                            size=DEFAULT_FONT_SIZE
                        ),

                        ft.Row(
                            controls=[
                                input_data_ref,
                                btn_executar,
                                btn_limpar_logs,
                                btn_abrir_pasta
                            ],
                            vertical_alignment=ft.CrossAxisAlignment.END,
                            wrap=True
                        ),

                        input_usuarios,

                        ft.Text(
                            "Mapeamento de usuários:",
                            size=DEFAULT_FONT_SIZE,
                            weight="bold"
                        ),

                        txt_mapeamento,

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