# ==========================================================
# ABA ADMIN - SIOR REATIVAÇÃO DE COBRANÇA
# ==========================================================
import os
import re
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

from requests_data.requisicoes_sior_reativacao import (
    URL_ANULAR_PAGE,
    LIMITE_AUTOS_POR_REQUISICAO,
    executar_reativacoes_por_motivo,
    preparar_headers_reativacao,
    inicializar_tela_reativacao,
)

from utils.open_dir_downloads import abrir_pasta_exportacao
from utils.popups import mostrar_alerta


# ==========================================================
# CONSTANTES
# ==========================================================
TEXTO_PADRAO_OBSERVACAO = (
    "Reativação do Auto de Infração de Trânsito "
    "em razão da realização da baixa por pagamento capturada via sistema SAPIENS Dívida (AGU)."
)


COLUNAS_LOG = [
    "DataHora",
    "Lote",
    "AUTO",
    "MOTIVO",
    "Status",
    "Mensagem",
    "InfracaoCodigoProcesso",
    "NUPSapiensSei",
    "Devedor",
    "TipoRecuperacaoCredito",
    "DataConstituicaoDefinitiva",
    "ValorOriginal",
    "Enquadramento",
    "Id",
]


# ==========================================================
# HELPERS DE PLANILHA / VALIDAÇÃO
# ==========================================================
def normalizar_nome_coluna(coluna: str) -> str:
    return (
        str(coluna or "")
        .strip()
        .upper()
        .replace(" ", "_")
        .replace("-", "_")
        .replace(".", "")
        .replace("Ç", "C")
        .replace("Ã", "A")
        .replace("Á", "A")
        .replace("À", "A")
        .replace("Â", "A")
        .replace("É", "E")
        .replace("Ê", "E")
        .replace("Í", "I")
        .replace("Ó", "O")
        .replace("Ô", "O")
        .replace("Õ", "O")
        .replace("Ú", "U")
    )


def validar_aits(codigos):
    erros = []

    if not codigos:
        erros.append(
            "⚠ É necessário inserir ao menos um código AIT."
        )

    if len(set(codigos)) < len(codigos):
        duplicados = sorted(
            {
                c
                for c in codigos
                if codigos.count(c) > 1
            }
        )

        erros.append(
            "⚠ Existem Número de AITs duplicados: "
            + ", ".join(duplicados[:20])
        )

    if len(codigos) > 2000:
        erros.append(
            "⚠ Limite máximo de 2000 AITs por vez."
        )

    if any(" " in c for c in codigos):
        erros.append(
            "⚠ Os Número de AIT não podem conter espaços."
        )

    invalidos = [
        c
        for c in codigos
        if not re.match(r"^[A-Za-z][0-9]{9}$", c)
    ]

    if invalidos:
        erros.append(
            "⚠ Todos os Número de AITs devem ter o formato: Letra + 9 dígitos. "
            "Inválidos: " + ", ".join(invalidos[:20])
        )

    return erros


def ler_planilha_molde(
    caminho_arquivo: str,
    motivo_padrao: str,
) -> pd.DataFrame:
    if not caminho_arquivo or not os.path.exists(caminho_arquivo):
        raise FileNotFoundError(
            "Selecione uma planilha válida para execução."
        )

    df = pd.read_excel(
        caminho_arquivo,
        dtype=str,
    )

    if df.empty:
        raise ValueError(
            "A planilha selecionada está vazia."
        )

    mapa_colunas = {
        normalizar_nome_coluna(c): c
        for c in df.columns
    }

    if "AUTO" not in mapa_colunas:
        raise ValueError(
            "A planilha deve conter a coluna obrigatória AUTO."
        )

    if "MOTIVO" not in mapa_colunas:
        raise ValueError(
            "A planilha deve conter a coluna obrigatória MOTIVO."
        )

    df = df[
        [
            mapa_colunas["AUTO"],
            mapa_colunas["MOTIVO"],
        ]
    ].copy()

    df.columns = [
        "AUTO",
        "MOTIVO",
    ]

    df["AUTO"] = (
        df["AUTO"]
        .fillna("")
        .astype(str)
        .str.strip()
        .str.upper()
    )

    df["MOTIVO"] = (
        df["MOTIVO"]
        .fillna("")
        .astype(str)
        .str.strip()
    )

    df = df[
        df["AUTO"] != ""
    ].copy()

    motivo_padrao = str(
        motivo_padrao or ""
    ).strip()

    df.loc[
        df["MOTIVO"] == "",
        "MOTIVO",
    ] = motivo_padrao

    if df.empty:
        raise ValueError(
            "A planilha não possui AITs válidos na coluna AUTO."
        )

    if (
        df["MOTIVO"]
        .astype(str)
        .str.strip()
        .eq("")
        .any()
    ):
        raise ValueError(
            "Existem linhas sem MOTIVO e o campo Motivo padrão também está vazio."
        )

    erros = validar_aits(
        df["AUTO"].tolist()
    )

    if erros:
        raise ValueError(
            "\n".join(erros)
        )

    return df


def gerar_planilha_molde(
    caminho_saida: str,
) -> None:
    df = pd.DataFrame(
        [
            {
                "AUTO": "S014267241",
                "MOTIVO": TEXTO_PADRAO_OBSERVACAO,
            },
            {
                "AUTO": "S014270673",
                "MOTIVO": (
                    "Processo SEI n.º 00000.000000/0000-00. "
                    "Reativação do Auto de Infração de Trânsito "
                    "em razão da rescisão do parcelamento."
                ),
            },
        ]
    )

    with pd.ExcelWriter(
        caminho_saida,
        engine="openpyxl",
    ) as writer:
        df.to_excel(
            writer,
            sheet_name="Molde",
            index=False,
        )

        ws = writer.sheets[
            "Molde"
        ]

        ws.column_dimensions[
            "A"
        ].width = 18

        ws.column_dimensions[
            "B"
        ].width = 120

        for cell in ws[1]:
            cell.style = "Headline 3"


def exportar_logs_excel(
    caminho_saida: str,
    df_molde: pd.DataFrame,
    df_logs: pd.DataFrame,
):
    with pd.ExcelWriter(
        caminho_saida,
        engine="openpyxl",
    ) as writer:

        df_logs.to_excel(
            writer,
            sheet_name="Logs",
            index=False,
        )

        df_molde.to_excel(
            writer,
            sheet_name="Molde Processado",
            index=False,
        )

        if not df_logs.empty and "Status" in df_logs.columns:
            resumo = (
                df_logs.groupby("Status")
                .size()
                .reset_index(name="Quantidade")
                .sort_values("Status")
            )
        else:
            resumo = pd.DataFrame(
                columns=[
                    "Status",
                    "Quantidade",
                ]
            )

        resumo.to_excel(
            writer,
            sheet_name="Resumo",
            index=False,
        )

        for sheet in writer.sheets.values():
            for column_cells in sheet.columns:
                max_length = 0
                column_letter = column_cells[0].column_letter

                for cell in column_cells:
                    try:
                        max_length = max(
                            max_length,
                            len(str(cell.value or "")),
                        )
                    except Exception:
                        pass

                sheet.column_dimensions[
                    column_letter
                ].width = min(
                    max_length + 2,
                    80,
                )


# ==========================================================
# ABA
# ==========================================================
def aba_admin_sior_reativacao(
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
        "arquivo_molde": None,
        "df_molde": pd.DataFrame(
            columns=[
                "AUTO",
                "MOTIVO",
            ]
        ),
        "df_logs": pd.DataFrame(
            columns=COLUNAS_LOG
        ),
        "caminho_saida": None,
    }

    # ======================================================
    # CONTROLES
    # ======================================================
    input_motivo_padrao = ft.TextField(
        label="Motivo padrão da reativação / observação",
        value=TEXTO_PADRAO_OBSERVACAO,
        multiline=True,
        min_lines=3,
        max_lines=5,
        expand=True,
        label_style=ft.TextStyle(
            size=DEFAULT_FONT_SIZE
        ),
        text_style=ft.TextStyle(
            size=DEFAULT_FONT_SIZE
        ),
    )

    txt_arquivo = ft.Text(
        "Nenhuma planilha selecionada.",
        size=DEFAULT_FONT_SIZE,
        color=ft.Colors.GREY_600,
        selectable=True,
    )

    txt_saida = ft.Text(
        f"📁 Saída padrão: {pasta_base_saida}",
        size=DEFAULT_FONT_SIZE,
        color=ft.Colors.GREY_600,
        selectable=True,
    )

    btn_baixar_molde = ft.ElevatedButton(
        "Gerar planilha molde",
        icon=ft.Icons.DOWNLOAD,
    )

    btn_selecionar = ft.ElevatedButton(
        "Selecionar planilha",
        icon=ft.Icons.UPLOAD_FILE,
    )

    btn_executar = ft.ElevatedButton(
        "Iniciar Reativação",
        icon=ft.Icons.PLAY_ARROW,
        bgcolor="green",
        color="white",
        disabled=True,
    )

    btn_exportar_logs = ft.ElevatedButton(
        "Abrir XLSX de logs",
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
    )

    log_execucao = ft.TextField(
        label="📝 Logs da Reativação",
        multiline=True,
        read_only=True,
        expand=True,
        min_lines=16,
        max_lines=16,
        label_style=ft.TextStyle(
            size=DEFAULT_FONT_SIZE
        ),
        text_style=ft.TextStyle(
            size=DEFAULT_FONT_SIZE
        ),
    )

    resumo_planilha = ft.Text(
        "",
        size=DEFAULT_FONT_SIZE,
        visible=False,
        selectable=True,
    )

    arquivos_gerados = ft.Column(
        controls=[],
        spacing=5,
        visible=False,
    )

    tabela_preview = ft.DataTable(
        columns=[
            ft.DataColumn(
                ft.Text(
                    "AUTO",
                    size=DEFAULT_FONT_SIZE,
                )
            ),
            ft.DataColumn(
                ft.Text(
                    "MOTIVO",
                    size=DEFAULT_FONT_SIZE,
                )
            ),
        ],
        rows=[],
        visible=False,
        data_text_style=ft.TextStyle(
            size=DEFAULT_FONT_SIZE
        ),
    )

    container_preview = ft.Container(
        content=tabela_preview,
        height=220,
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
        visible=False,
    )

    file_picker = ft.FilePicker()
    page.overlay.append(file_picker)

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

    def atualizar_preview():
        tabela_preview.rows.clear()

        df = estado[
            "df_molde"
        ]

        for _, row in df.head(5).iterrows():
            tabela_preview.rows.append(
                ft.DataRow(
                    cells=[
                        ft.DataCell(
                            ft.Text(
                                str(row.get("AUTO", "")),
                                size=DEFAULT_FONT_SIZE,
                            )
                        ),
                        ft.DataCell(
                            ft.Text(
                                str(row.get("MOTIVO", ""))[:180],
                                size=DEFAULT_FONT_SIZE,
                            )
                        ),
                    ]
                )
            )

        total = len(df)

        motivos = (
            df["MOTIVO"].nunique()
            if not df.empty
            else 0
        )

        resumo_planilha.value = (
            f"📄 Planilha carregada: {total} AIT(s) | "
            f"{motivos} motivo(s) distinto(s)."
        )

        resumo_planilha.visible = True
        tabela_preview.visible = total > 0
        container_preview.visible = total > 0
        btn_executar.disabled = total == 0

        page.update()

    def limpar_logs(e=None):
        log_execucao.value = ""

        arquivos_gerados.controls.clear()
        arquivos_gerados.visible = False

        status.value = ""

        btn_exportar_logs.visible = False

        estado["df_logs"] = pd.DataFrame(
            columns=COLUNAS_LOG
        )

        estado["caminho_saida"] = None

        page.update()

    # ======================================================
    # AÇÕES PLANILHA
    # ======================================================
    def baixar_molde(e):
        try:
            ts = datetime.now().strftime(
                "%Y-%m-%d_%H-%M-%S"
            )

            caminho = os.path.join(
                pasta_base_saida,
                f"molde_sior_reativacao_{ts}.xlsx",
            )

            gerar_planilha_molde(
                caminho
            )

            mostrar_alerta(
                ft,
                page,
                "Molde gerado",
                f"✅ Planilha molde de reativação gerada em:\n{caminho}",
                tipo="success",
            )

            abrir_pasta_exportacao(
                caminho
            )

        except Exception as ex:
            mostrar_alerta(
                ft,
                page,
                "Erro ao gerar molde",
                str(ex),
                tipo="error",
            )

        finally:
            page.update()

    def selecionar_planilha(e):
        file_picker.pick_files(
            allow_multiple=False,
            allowed_extensions=[
                "xlsx",
                "xls",
            ],
        )

    def on_file_picked(e):
        try:
            if not e.files:
                return

            caminho = e.files[0].path

            estado[
                "arquivo_molde"
            ] = caminho

            txt_arquivo.value = (
                f"📄 Planilha selecionada: {caminho}"
            )

            df = ler_planilha_molde(
                caminho,
                input_motivo_padrao.value,
            )

            estado[
                "df_molde"
            ] = df

            atualizar_preview()

            mostrar_alerta(
                ft,
                page,
                "Planilha carregada",
                f"✅ {len(df)} AIT(s) carregado(s) para reativação.",
                tipo="success",
            )

        except Exception as ex:
            estado["df_molde"] = pd.DataFrame(
                columns=[
                    "AUTO",
                    "MOTIVO",
                ]
            )

            btn_executar.disabled = True
            container_preview.visible = False
            resumo_planilha.visible = False

            mostrar_alerta(
                ft,
                page,
                "Validação da planilha",
                str(ex),
                tipo="error",
            )

        finally:
            page.update()

    def abrir_logs(e=None):
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
                "O XLSX de logs ainda não foi gerado ou não está disponível.",
                tipo="warning",
            )

            page.update()

    # ======================================================
    # EXECUÇÃO
    # ======================================================
    def executar_reativacao(e):
        try:
            df_molde = estado[
                "df_molde"
            ].copy()

            if df_molde.empty:
                raise ValueError(
                    "Selecione e valide uma planilha antes de iniciar."
                )

            # Revalida no momento da execução.
            if estado.get("arquivo_molde"):
                df_molde = ler_planilha_molde(
                    estado["arquivo_molde"],
                    input_motivo_padrao.value,
                )

                estado[
                    "df_molde"
                ] = df_molde

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

        btn_selecionar.disabled = True
        btn_baixar_molde.disabled = True

        progress.visible = True
        progress.value = None

        status.visible = True
        status.value = "Preparando execução..."

        log_execucao.value = ""

        arquivos_gerados.controls.clear()
        arquivos_gerados.visible = False

        btn_exportar_logs.visible = False

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
                    f"Reativacao_SIOR_{ts}",
                )

                os.makedirs(
                    pasta_saida,
                    exist_ok=True,
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
                    "🌐 Acessando tela de Reativação/Anulação de Suspensão..."
                )

                sucesso_tela = safe_get(
                    navegador=navegador,
                    url=URL_ANULAR_PAGE,
                    elemento_validacao=(By.TAG_NAME, "body"),
                    tentativas=3,
                    timeout_get=20,
                    timeout_elemento=10,
                    tempo_estabilizacao=1,
                )

                if not sucesso_tela:
                    raise RuntimeError(
                        "Não foi possível acessar a tela de Reativação do SIOR."
                    )

                total_cookies = sincronizar_cookies_navegador_para_session(
                    navegador,
                    session,
                )

                preparar_headers_reativacao(
                    session
                )

                adicionar_log(
                    f"🍪 Cookies sincronizados navegador → requests: {total_cookies}."
                )

                inicializar_tela_reativacao(
                    session=session,
                    log=adicionar_log,
                    renovar_guid=True,
                )

                adicionar_log(
                    "✅ Tela acessada e sessão requests validada."
                )

                adicionar_log(
                    "🚀 Iniciando processamento dos lotes por motivo..."
                )

                df_logs = executar_reativacoes_por_motivo(
                    session=session,
                    df_molde=df_molde,
                    log=adicionar_log,
                    tamanho_lote=LIMITE_AUTOS_POR_REQUISICAO,
                    pausa_entre_lotes=1.0,
                )

                if df_logs.empty:
                    df_logs = pd.DataFrame(
                        columns=COLUNAS_LOG
                    )

                estado[
                    "df_logs"
                ] = df_logs

                caminho_logs = os.path.join(
                    pasta_saida,
                    f"logs_reativacao_sior_{ts}.xlsx",
                )

                exportar_logs_excel(
                    caminho_logs,
                    df_molde=df_molde,
                    df_logs=df_logs,
                )

                estado[
                    "caminho_saida"
                ] = caminho_logs

                registrar_arquivo(
                    "XLSX de logs",
                    caminho_logs,
                )

                total_sucesso = (
                    int((df_logs["Status"] == "SUCESSO").sum())
                    if "Status" in df_logs
                    else 0
                )

                total_erro = (
                    int((df_logs["Status"] == "ERRO").sum())
                    if "Status" in df_logs
                    else 0
                )

                adicionar_log(
                    f"🎉 Execução finalizada. Sucessos: {total_sucesso} | Erros: {total_erro}."
                )

                btn_exportar_logs.visible = True

                mostrar_alerta(
                    ft,
                    page,
                    "Reativação finalizada",
                    (
                        f"✅ Execução concluída.\n"
                        f"Sucessos: {total_sucesso}\n"
                        f"Erros: {total_erro}\n\n"
                        f"Logs em:\n{caminho_logs}"
                    ),
                    tipo="success" if total_erro == 0 else "warning",
                )

                try:
                    abrir_pasta_exportacao(
                        caminho_logs
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
                    "Erro na reativação",
                    str(ex),
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

                btn_executar.disabled = estado[
                    "df_molde"
                ].empty

                btn_executar.text = "Iniciar Reativação"

                btn_selecionar.disabled = False
                btn_baixar_molde.disabled = False

                progress.visible = False

                desbloquear()

                page.update()

        threading.Thread(
            target=task,
            daemon=True,
        ).start()

    # ======================================================
    # EVENTS
    # ======================================================
    file_picker.on_result = on_file_picked
    btn_baixar_molde.on_click = baixar_molde
    btn_selecionar.on_click = selecionar_planilha
    btn_executar.on_click = executar_reativacao
    btn_exportar_logs.on_click = abrir_logs
    btn_limpar_logs.on_click = limpar_logs

    # ======================================================
    # RETURN
    # ======================================================
    return ft.Column(
        controls=[
            ft.Row(
                [
                    ft.Text(
                        "Admin > SIOR > Reativação de Cobrança",
                        size=10,
                        weight="bold",
                    )
                ],
                alignment="center",
            ),

            ft.Divider(),

            ft.Container(
                content=ft.Column(
                    controls=[
                        ft.Text(
                            "⚙️ Reativação de Cobrança por Requisição",
                            size=HEADING_FONT_SIZE,
                            weight="bold",
                        ),

                        ft.Text(
                            "Carregue uma planilha com as colunas AUTO e MOTIVO. "
                            "A execução agrupa os AITs por motivo, processa os autos em lotes de até "
                            f"{LIMITE_AUTOS_POR_REQUISICAO} registros por limitação do SIOR, "
                            "confirma a reativação e gera XLSX de logs com sucessos e erros.",
                            size=DEFAULT_FONT_SIZE,
                        ),

                        input_motivo_padrao,

                        ft.Row(
                            controls=[
                                btn_baixar_molde,
                                btn_selecionar,
                                btn_executar,
                                btn_exportar_logs,
                                btn_limpar_logs,
                            ],
                            vertical_alignment=ft.CrossAxisAlignment.END,
                            wrap=True,
                        ),

                        txt_arquivo,
                        txt_saida,
                        resumo_planilha,
                    ],
                    spacing=10,
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

            container_preview,

            status,

            progress,

            ft.Container(
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
                ),
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
            ),

            arquivos_gerados,

            alerta_dialogo,
        ],
        expand=True,
        spacing=10,
        scroll=ft.ScrollMode.AUTO,
    )