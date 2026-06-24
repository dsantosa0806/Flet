# ==========================================================
# ABA ADMIN - SIOR ENCAMINHAR DEVEDORES
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

from requests_data.requisicoes_sior_encaminhar_devedores import (
    URL_TELA_ENCAMINHAMENTO,
    COLUNAS_LOG,
    COLUNAS_DETALHE,
    executar_encaminhamento_devedores,
    inicializar_tela_encaminhar_devedores,
    preparar_headers_encaminhar_devedores,
    normalizar_devedor_numero,
    EQUIPE_COD_NOME,
    nome_equipe_por_codigo,
    descricao_equipe_por_codigo,
    codigo_equipe_por_nome,
)

from utils.open_dir_downloads import abrir_pasta_exportacao
from utils.popups import mostrar_alerta


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


def _parse_int(valor, nome_campo: str, linha_excel: int) -> int:
    texto = str(valor or "").strip()

    if texto == "":
        raise ValueError(
            f"Linha {linha_excel}: campo {nome_campo} vazio."
        )

    texto = texto.replace(".0", "") if re.match(r"^\d+\.0$", texto) else texto

    if not re.match(r"^\d+$", texto):
        raise ValueError(
            f"Linha {linha_excel}: campo {nome_campo} deve ser numérico inteiro. Valor: {valor}"
        )

    numero = int(texto)

    if numero <= 0:
        raise ValueError(
            f"Linha {linha_excel}: campo {nome_campo} deve ser maior que zero."
        )

    return numero


def _parse_equipe_cod(valor, linha_excel: int) -> int:
    """
    Aceita tanto o código numérico quanto o nome da equipe.

    Correlação oficial:
    - Equipe Cobrança 1 -> código 2
    - Equipe Cobrança 2 -> código 1
    - Equipe Cobrança 3 -> código 3
    - Equipe Cobrança 4 -> código 4
    - Equipe Cobrança 5 -> código 5
    """
    codigo = codigo_equipe_por_nome(valor)

    if not codigo:
        raise ValueError(
            f"Linha {linha_excel}: EquipeCod inválido. Valor: {valor}. "
            "Use 1, 2, 3, 4 ou 5 conforme a correlação oficial."
        )

    if codigo not in EQUIPE_COD_NOME:
        raise ValueError(
            f"Linha {linha_excel}: EquipeCod {codigo} não está mapeado. "
            "Códigos válidos: 2=Equipe Cobrança 1, 1=Equipe Cobrança 2, "
            "3=Equipe Cobrança 3, 4=Equipe Cobrança 4, 5=Equipe Cobrança 5."
        )

    return int(codigo)


def ler_planilha_molde(caminho_arquivo: str) -> pd.DataFrame:
    if not caminho_arquivo or not os.path.exists(caminho_arquivo):
        raise FileNotFoundError(
            "Selecione uma planilha válida para execução."
        )

    df_original = pd.read_excel(
        caminho_arquivo,
        dtype=str,
    )

    if df_original.empty:
        raise ValueError(
            "A planilha selecionada está vazia."
        )

    mapa_colunas = {
        normalizar_nome_coluna(c): c
        for c in df_original.columns
    }

    obrigatorias = [
        "DEVEDOR",
        "QTDE",
        "EQUIPECOD",
    ]

    ausentes = [
        coluna
        for coluna in obrigatorias
        if coluna not in mapa_colunas
    ]

    if ausentes:
        raise ValueError(
            "A planilha deve conter exatamente as colunas obrigatórias: "
            "Devedor, Qtde, EquipeCod. Ausentes: " + ", ".join(ausentes)
        )

    df = df_original[
        [
            mapa_colunas["DEVEDOR"],
            mapa_colunas["QTDE"],
            mapa_colunas["EQUIPECOD"],
        ]
    ].copy()

    df.columns = [
        "Devedor",
        "Qtde",
        "EquipeCod",
    ]

    df["Devedor"] = (
        df["Devedor"]
        .fillna("")
        .astype(str)
        .str.strip()
    )

    df = df[
        df["Devedor"] != ""
    ].copy()

    if df.empty:
        raise ValueError(
            "A planilha não possui devedores válidos na coluna Devedor."
        )

    registros = []
    erros = []

    for idx, row in df.reset_index(drop=True).iterrows():
        linha_excel = idx + 2
        devedor = str(row.get("Devedor", "")).strip()
        devedor_numero = normalizar_devedor_numero(devedor)

        if len(devedor_numero) not in (11, 14):
            erros.append(
                f"Linha {linha_excel}: Devedor deve ser CPF/CNPJ com 11 ou 14 dígitos. Valor: {devedor}"
            )
            continue

        try:
            qtde = _parse_int(row.get("Qtde"), "Qtde", linha_excel)
            equipe_cod = _parse_equipe_cod(row.get("EquipeCod"), linha_excel)
        except Exception as ex:
            erros.append(str(ex))
            continue

        registros.append(
            {
                "Devedor": devedor,
                "DevedorNumero": devedor_numero,
                "Qtde": qtde,
                "EquipeCod": equipe_cod,
                "EquipeNome": nome_equipe_por_codigo(equipe_cod),
                "EquipeDestino": descricao_equipe_por_codigo(equipe_cod),
            }
        )

    if erros:
        raise ValueError(
            "Foram encontradas inconsistências na planilha:\n"
            + "\n".join(erros[:30])
        )

    df_validado = pd.DataFrame(registros)

    # Evita executar duas vezes a mesma combinação Devedor + Equipe.
    # Se existir duplicidade, soma a quantidade esperada.
    df_agrupado = (
        df_validado
        .groupby(
            ["DevedorNumero", "EquipeCod"],
            as_index=False,
            sort=False,
        )
        .agg(
            Devedor=("Devedor", "first"),
            Qtde=("Qtde", "sum"),
        )
    )

    df_agrupado["EquipeNome"] = df_agrupado["EquipeCod"].apply(nome_equipe_por_codigo)
    df_agrupado["EquipeDestino"] = df_agrupado["EquipeCod"].apply(descricao_equipe_por_codigo)

    df_agrupado = df_agrupado[
        [
            "Devedor",
            "DevedorNumero",
            "Qtde",
            "EquipeCod",
            "EquipeNome",
            "EquipeDestino",
        ]
    ].copy()

    return df_agrupado


def gerar_planilha_molde(caminho_saida: str) -> None:
    df = pd.DataFrame(
        [
            {
                "Devedor": "047.171.314-79",
                "Qtde": 2,
                "EquipeCod": 2,
            },
            {
                "Devedor": "12.345.678/0001-90",
                "Qtde": 5,
                "EquipeCod": 3,
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

        ws = writer.sheets["Molde"]

        ws.column_dimensions["A"].width = 24
        ws.column_dimensions["B"].width = 12
        ws.column_dimensions["C"].width = 14

        for cell in ws[1]:
            cell.style = "Headline 3"


def exportar_logs_excel(
    caminho_saida: str,
    df_molde: pd.DataFrame,
    df_logs: pd.DataFrame,
    df_detalhes: pd.DataFrame,
):
    if df_logs is None or df_logs.empty:
        df_logs = pd.DataFrame(columns=COLUNAS_LOG)

    if df_detalhes is None or df_detalhes.empty:
        df_detalhes = pd.DataFrame(columns=COLUNAS_DETALHE)

    with pd.ExcelWriter(
        caminho_saida,
        engine="openpyxl",
    ) as writer:
        df_logs.to_excel(
            writer,
            sheet_name="Logs",
            index=False,
        )

        df_detalhes.to_excel(
            writer,
            sheet_name="Detalhes Autos",
            index=False,
        )

        df_molde.to_excel(
            writer,
            sheet_name="Molde Processado",
            index=False,
        )

        if not df_logs.empty and "Status" in df_logs.columns:
            resumo_status = (
                df_logs.groupby("Status")
                .size()
                .reset_index(name="Quantidade")
                .sort_values("Status")
            )
        else:
            resumo_status = pd.DataFrame(
                columns=["Status", "Quantidade"]
            )

        resumo_status.to_excel(
            writer,
            sheet_name="Resumo",
            index=False,
            startrow=0,
        )

        if not df_logs.empty:
            resumo_equipe = (
                df_logs.groupby(["EquipeCod", "EquipeNome", "EquipeDestino", "Status"], dropna=False)
                .agg(
                    Devedores=("DevedorNumero", "nunique"),
                    AutosInformados=("QtdeInformada", "sum"),
                    AutosRetornados=("QtdeRetornadaSIOR", "sum"),
                    AutosSelecionados=("QtdeSelecionada", "sum"),
                )
                .reset_index()
                .sort_values(["EquipeCod", "Status"])
            )
        else:
            resumo_equipe = pd.DataFrame(
                columns=[
                    "EquipeCod",
                    "EquipeNome",
                    "EquipeDestino",
                    "Status",
                    "Devedores",
                    "AutosInformados",
                    "AutosRetornados",
                    "AutosSelecionados",
                ]
            )

        resumo_equipe.to_excel(
            writer,
            sheet_name="Resumo por Equipe",
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

                sheet.column_dimensions[column_letter].width = min(
                    max(max_length + 2, 10),
                    80,
                )


# ==========================================================
# ABA
# ==========================================================
def aba_admin_sior_encaminhar_devedores(
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

    dialogo_confirmacao = ft.AlertDialog(
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
                "Devedor",
                "DevedorNumero",
                "Qtde",
                "EquipeCod",
                "EquipeNome",
                "EquipeDestino",
            ]
        ),
        "df_logs": pd.DataFrame(columns=COLUNAS_LOG),
        "df_detalhes": pd.DataFrame(columns=COLUNAS_DETALHE),
        "caminho_saida": None,
        "pasta_saida": None,
    }

    # ======================================================
    # CONTROLES
    # ======================================================
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
        "Iniciar Encaminhamento",
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
        selectable=True,
    )

    log_execucao = ft.TextField(
        label="📝 Logs do Encaminhamento",
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
            ft.DataColumn(ft.Text("Devedor", size=DEFAULT_FONT_SIZE)),
            ft.DataColumn(ft.Text("Qtde", size=DEFAULT_FONT_SIZE)),
            ft.DataColumn(ft.Text("Equipe destino", size=DEFAULT_FONT_SIZE)),
            ft.DataColumn(ft.Text("EquipeCod", size=DEFAULT_FONT_SIZE)),
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
    def adicionar_log(mensagem: str):
        try:
            horario = datetime.now().strftime("%H:%M:%S")
            log_execucao.value += f"[{horario}] {mensagem}\n"
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
                selectable=True,
            )
        )
        arquivos_gerados.visible = True

    def resumo_execucao_df(df: pd.DataFrame) -> dict:
        if df is None or df.empty:
            return {
                "total_devedores": 0,
                "total_combinacoes": 0,
                "total_autos": 0,
                "equipes": pd.DataFrame(),
            }

        resumo_equipes = (
            df.groupby(["EquipeCod", "EquipeNome", "EquipeDestino"], dropna=False)
            .agg(
                Devedores=("DevedorNumero", "nunique"),
                Combinacoes=("DevedorNumero", "count"),
                Autos=("Qtde", "sum"),
            )
            .reset_index()
            .sort_values("EquipeCod")
        )

        return {
            "total_devedores": int(df["DevedorNumero"].nunique()),
            "total_combinacoes": int(len(df)),
            "total_autos": int(df["Qtde"].sum()),
            "equipes": resumo_equipes,
        }

    def atualizar_preview():
        tabela_preview.rows.clear()

        df = estado["df_molde"]

        for _, row in df.head(8).iterrows():
            tabela_preview.rows.append(
                ft.DataRow(
                    cells=[
                        ft.DataCell(ft.Text(str(row.get("Devedor", "")), size=DEFAULT_FONT_SIZE)),
                        ft.DataCell(ft.Text(str(row.get("Qtde", "")), size=DEFAULT_FONT_SIZE)),
                        ft.DataCell(ft.Text(str(row.get("EquipeNome", "")), size=DEFAULT_FONT_SIZE)),
                        ft.DataCell(ft.Text(str(row.get("EquipeCod", "")), size=DEFAULT_FONT_SIZE)),
                    ]
                )
            )

        resumo = resumo_execucao_df(df)

        resumo_planilha.value = (
            f"📄 Planilha carregada: {resumo['total_devedores']} devedor(es) único(s) | "
            f"{resumo['total_combinacoes']} combinação(ões) Devedor/Equipe | "
            f"{resumo['total_autos']} auto(s) informado(s)."
        )

        resumo_planilha.visible = True
        tabela_preview.visible = len(df) > 0
        container_preview.visible = len(df) > 0
        btn_executar.disabled = len(df) == 0

        page.update()

    def limpar_logs(e=None):
        log_execucao.value = ""
        arquivos_gerados.controls.clear()
        arquivos_gerados.visible = False
        status.value = ""
        status.visible = False
        btn_exportar_logs.visible = False

        estado["df_logs"] = pd.DataFrame(columns=COLUNAS_LOG)
        estado["df_detalhes"] = pd.DataFrame(columns=COLUNAS_DETALHE)
        estado["caminho_saida"] = None
        estado["pasta_saida"] = None

        page.update()

    # ======================================================
    # AÇÕES PLANILHA
    # ======================================================
    def baixar_molde(e):
        try:
            ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            caminho = os.path.join(
                pasta_base_saida,
                f"molde_sior_encaminhar_devedores_{ts}.xlsx",
            )

            gerar_planilha_molde(caminho)

            mostrar_alerta(
                ft,
                page,
                "Molde gerado",
                f"✅ Planilha molde gerada em:\n{caminho}",
                tipo="success",
            )

            abrir_pasta_exportacao(caminho)

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
            allowed_extensions=["xlsx", "xls"],
        )

    def on_file_picked(e):
        try:
            if not e.files:
                return

            caminho = e.files[0].path
            estado["arquivo_molde"] = caminho
            txt_arquivo.value = f"📄 Planilha selecionada: {caminho}"

            df = ler_planilha_molde(caminho)
            estado["df_molde"] = df

            atualizar_preview()

            resumo = resumo_execucao_df(df)

            mostrar_alerta(
                ft,
                page,
                "Planilha carregada",
                (
                    f"✅ {resumo['total_devedores']} devedor(es) único(s) carregado(s).\n"
                    f"Autos informados: {resumo['total_autos']}"
                ),
                tipo="success",
            )

        except Exception as ex:
            estado["df_molde"] = pd.DataFrame(
                columns=["Devedor", "DevedorNumero", "Qtde", "EquipeCod", "EquipeNome", "EquipeDestino"]
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
        caminho = estado.get("caminho_saida")

        if caminho and os.path.exists(caminho):
            abrir_pasta_exportacao(caminho)
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
    # CONFIRMAÇÃO
    # ======================================================
    def abrir_confirmacao(e):
        try:
            df_molde = estado["df_molde"].copy()

            if df_molde.empty:
                raise ValueError(
                    "Selecione e valide uma planilha antes de iniciar."
                )

            if estado.get("arquivo_molde"):
                df_molde = ler_planilha_molde(estado["arquivo_molde"])
                estado["df_molde"] = df_molde
                atualizar_preview()

            resumo = resumo_execucao_df(df_molde)
            resumo_equipes = resumo["equipes"]

            linhas_equipes = []
            for _, row in resumo_equipes.iterrows():
                linhas_equipes.append(
                    f"{row['EquipeDestino']}: "
                    f"{int(row['Devedores'])} devedor(es), "
                    f"{int(row['Autos'])} auto(s)."
                )

            texto_equipes = "\n".join(linhas_equipes)

            def cancelar_confirmacao(ev=None):
                dialogo_confirmacao.open = False
                page.update()

            def confirmar(ev=None):
                dialogo_confirmacao.open = False
                page.update()
                executar_encaminhamento_confirmado(df_molde)

            dialogo_confirmacao.title = ft.Text(
                "Confirmar Encaminhamento de Devedores SIOR"
            )

            dialogo_confirmacao.content = ft.Container(
                content=ft.Column(
                    controls=[
                        ft.Text(
                            "Confirme a execução antes de encaminhar os devedores no SIOR.",
                            size=DEFAULT_FONT_SIZE,
                        ),
                        ft.Text(
                            (
                                f"Devedores únicos: {resumo['total_devedores']}\n"
                                f"Combinações Devedor/Equipe: {resumo['total_combinacoes']}\n"
                                f"Autos informados na planilha: {resumo['total_autos']}"
                            ),
                            size=DEFAULT_FONT_SIZE,
                            weight="bold",
                            selectable=True,
                        ),
                        ft.Divider(),
                        ft.Text(
                            texto_equipes,
                            size=DEFAULT_FONT_SIZE,
                            selectable=True,
                        ),
                        ft.Divider(),
                        ft.Text(
                            "Validação de segurança: para cada devedor/equipe, o POST só será enviado "
                            "se a quantidade retornada pelo SIOR for igual à Qtde informada na planilha.",
                            size=DEFAULT_FONT_SIZE,
                            color=ft.Colors.AMBER_800,
                            selectable=True,
                        ),
                    ],
                    tight=True,
                    spacing=8,
                    scroll=ft.ScrollMode.AUTO,
                ),
                width=560,
                height=360,
            )

            dialogo_confirmacao.actions = [
                ft.TextButton(
                    "Cancelar",
                    on_click=cancelar_confirmacao,
                ),
                ft.ElevatedButton(
                    "Confirmar e encaminhar",
                    icon=ft.Icons.CHECK,
                    bgcolor="green",
                    color="white",
                    on_click=confirmar,
                ),
            ]

            page.dialog = dialogo_confirmacao
            dialogo_confirmacao.open = True
            page.update()

        except Exception as ex:
            mostrar_alerta(
                ft,
                page,
                "Validação",
                str(ex),
                tipo="error",
            )
            page.update()

    # ======================================================
    # EXECUÇÃO
    # ======================================================
    def exportar_xlsx_logs_em_erro():
        try:
            pasta_saida = estado.get("pasta_saida")

            if not pasta_saida:
                ts_pasta = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
                pasta_saida = os.path.join(
                    pasta_base_saida,
                    f"Encaminhar_Devedores_SIOR_ERRO_{ts_pasta}",
                )
                os.makedirs(pasta_saida, exist_ok=True)
                estado["pasta_saida"] = pasta_saida

            ts_erro = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            caminho_xlsx = os.path.join(
                pasta_saida,
                f"logs_encaminhar_devedores_sior_erro_{ts_erro}.xlsx",
            )

            exportar_logs_excel(
                caminho_saida=caminho_xlsx,
                df_molde=estado.get("df_molde", pd.DataFrame()),
                df_logs=estado.get("df_logs", pd.DataFrame(columns=COLUNAS_LOG)),
                df_detalhes=estado.get("df_detalhes", pd.DataFrame(columns=COLUNAS_DETALHE)),
            )

            estado["caminho_saida"] = caminho_xlsx
            registrar_arquivo("XLSX de logs da execução com erro", caminho_xlsx)
            btn_exportar_logs.visible = True

        except Exception as ex:
            try:
                log_execucao.value += f"Falha ao exportar XLSX de erro: {ex}\n"
            except Exception:
                pass

    def executar_encaminhamento_confirmado(df_molde: pd.DataFrame):
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

        estado["df_logs"] = pd.DataFrame(columns=COLUNAS_LOG)
        estado["df_detalhes"] = pd.DataFrame(columns=COLUNAS_DETALHE)
        estado["caminho_saida"] = None
        estado["pasta_saida"] = None

        page.update()

        def task():
            navegador = None

            try:
                bloquear()

                ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
                pasta_saida = os.path.join(
                    pasta_base_saida,
                    f"Encaminhar_Devedores_SIOR_{ts}",
                )

                os.makedirs(pasta_saida, exist_ok=True)
                estado["pasta_saida"] = pasta_saida

                adicionar_log("🔐 Iniciando sessão SIOR...")

                navegador, session = iniciar_sessao_sior(
                    log=adicionar_log
                )

                if navegador is None or session is None:
                    raise RuntimeError(
                        "Não foi possível iniciar a sessão SIOR."
                    )

                adicionar_log("🌐 Acessando tela de Encaminhamento SIOR...")

                sucesso_tela = safe_get(
                    navegador=navegador,
                    url=f"{URL_TELA_ENCAMINHAMENTO}?Bind=true",
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

                preparar_headers_encaminhar_devedores(session)

                adicionar_log(
                    f"🍪 Cookies sincronizados navegador → requests: {total_cookies}."
                )

                inicializar_tela_encaminhar_devedores(
                    session=session,
                    log=adicionar_log,
                    renovar_guid=True,
                )

                adicionar_log("✅ Tela acessada e sessão requests validada.")

                resumo = resumo_execucao_df(df_molde)

                adicionar_log(
                    f"🚀 Iniciando encaminhamento: {resumo['total_devedores']} devedor(es), "
                    f"{resumo['total_autos']} auto(s) informado(s)."
                )

                resultado = executar_encaminhamento_devedores(
                    session=session,
                    df_molde=df_molde,
                    log=adicionar_log,
                    validar_qtde_informada=True,
                    pausa_entre_devedores=0.5,
                )

                df_logs = resultado.get("logs", pd.DataFrame(columns=COLUNAS_LOG))
                df_detalhes = resultado.get("detalhes", pd.DataFrame(columns=COLUNAS_DETALHE))

                estado["df_logs"] = df_logs
                estado["df_detalhes"] = df_detalhes

                caminho_logs = os.path.join(
                    pasta_saida,
                    f"logs_encaminhar_devedores_sior_{ts}.xlsx",
                )

                exportar_logs_excel(
                    caminho_saida=caminho_logs,
                    df_molde=df_molde,
                    df_logs=df_logs,
                    df_detalhes=df_detalhes,
                )

                estado["caminho_saida"] = caminho_logs

                registrar_arquivo("XLSX de logs", caminho_logs)

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

                autos_sucesso = (
                    int(
                        df_logs.loc[
                            df_logs["Status"] == "SUCESSO",
                            "QtdeSelecionada",
                        ].fillna(0).astype(int).sum()
                    )
                    if not df_logs.empty and "QtdeSelecionada" in df_logs.columns
                    else 0
                )

                adicionar_log(
                    f"🎉 Execução finalizada. Devedores com sucesso: {total_sucesso} | "
                    f"Erros: {total_erro} | Autos encaminhados: {autos_sucesso}."
                )

                btn_exportar_logs.visible = True

                mostrar_alerta(
                    ft,
                    page,
                    "Encaminhamento finalizado",
                    (
                        f"✅ Execução concluída.\n"
                        f"Devedores com sucesso: {total_sucesso}\n"
                        f"Erros: {total_erro}\n"
                        f"Autos encaminhados: {autos_sucesso}\n\n"
                        f"Logs em:\n{caminho_logs}"
                    ),
                    tipo="success" if total_erro == 0 else "warning",
                )

                try:
                    abrir_pasta_exportacao(caminho_logs)
                except Exception:
                    pass

            except Exception as ex:
                adicionar_log(f"❌ Erro durante execução: {ex}")
                adicionar_log(traceback.format_exc())

                exportar_xlsx_logs_em_erro()

                mostrar_alerta(
                    ft,
                    page,
                    "Erro no encaminhamento",
                    (
                        f"{ex}\n\n"
                        "Os logs da falha foram exportados em XLSX, quando possível."
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

                btn_executar.disabled = estado["df_molde"].empty
                btn_executar.text = "Iniciar Encaminhamento"

                btn_selecionar.disabled = False
                btn_baixar_molde.disabled = False

                progress.visible = False

                desbloquear()

                page.update()

        threading.Thread(target=task, daemon=True).start()

    # ======================================================
    # EVENTS
    # ======================================================
    file_picker.on_result = on_file_picked
    btn_baixar_molde.on_click = baixar_molde
    btn_selecionar.on_click = selecionar_planilha
    btn_executar.on_click = abrir_confirmacao
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
                        "Admin > SIOR > Encaminhar Devedores SIOR",
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
                            "📤 Encaminhar Devedores SIOR",
                            size=HEADING_FONT_SIZE,
                            weight="bold",
                        ),

                        ft.Text(
                            "Carregue uma planilha com as colunas Devedor, Qtde e EquipeCod. "
                            "Correlação: código 2 = Equipe Cobrança 1; código 1 = Equipe Cobrança 2; "
                            "códigos 3, 4 e 5 = Equipes Cobrança 3, 4 e 5. "
                            "Antes da execução, será exibida uma janela de confirmação com o total "
                            "de devedores, autos e equipes. Ao final, será gerado XLSX com logs, "
                            "detalhes dos autos retornados e resumo por equipe.",
                            size=DEFAULT_FONT_SIZE,
                            selectable=True,
                        ),

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
            dialogo_confirmacao,
        ],
        expand=True,
        spacing=10,
        scroll=ft.ScrollMode.AUTO,
    )
