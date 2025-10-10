import flet as ft
from flet import Icons, Colors
import pandas as pd
import time

from requests_data.requisicoes_cadin import consultar_cadin

DEFAULT_FONT_SIZE = 13
HEADING_FONT_SIZE = 18

CAMPOS_TABELA = [
    "cpfCnpj",
    "nome",
    "numeroTransacao",
    "numeroReferencia",
    "complementoReferencia",
    "dataComunicacao",
    "dataInadimplencia",
    "nomeInstituicao",
]


def aba_consulta_cadin(ft, DEFAULT_FONT_SIZE, HEADING_FONT_SIZE, page):
    resultados = []
    paginador_atual = 1
    registros_por_pagina = 3

    # ---------- ELEMENTOS DE INTERFACE ----------
    titulo = ft.Text(
        "🔎 Consulta CADIN",
        size=HEADING_FONT_SIZE,
        weight=ft.FontWeight.BOLD,
        color=Colors.BLUE_300,
    )

    campo_token = ft.TextField(
        label="TOKEN_JWT (manual)",
        hint_text="Cole aqui o TOKEN_JWT obtido após login no CADIN",
        multiline=False,
        border_color=Colors.BLUE_200,
        border_radius=8,
        color=Colors.WHITE,
        cursor_color=Colors.BLUE_200,
        text_size=DEFAULT_FONT_SIZE,
        expand=True,
        password=True,
        can_reveal_password=True,
    )

    campo_documentos = ft.TextField(
        label="CPF(s) ou CNPJ(s) para consulta",
        hint_text="Informe até 10 CPFs ou CNPJs (um por linha ou separados por vírgula)",
        multiline=True,
        min_lines=3,
        max_lines=6,
        border_color=Colors.BLUE_200,
        border_radius=8,
        color=Colors.WHITE,
        cursor_color=Colors.BLUE_200,
        text_size=DEFAULT_FONT_SIZE,
        expand=True,
    )

    tabela = ft.DataTable(
        columns=[ft.DataColumn(ft.Text(col)) for col in CAMPOS_TABELA],
        rows=[],
        border=ft.border.all(0.5, Colors.with_opacity(0.3, Colors.WHITE)),
        horizontal_lines=ft.border.BorderSide(0.3, Colors.with_opacity(0.2, Colors.WHITE)),
        vertical_lines=ft.border.BorderSide(0.3, Colors.with_opacity(0.2, Colors.WHITE)),
    )

    paginador_info = ft.Text("Página 1 de 1", size=DEFAULT_FONT_SIZE)
    btn_anterior = ft.IconButton(icon=Icons.ARROW_BACK)
    btn_proximo = ft.IconButton(icon=Icons.ARROW_FORWARD)
    btn_consultar = ft.ElevatedButton("Consultar", icon=Icons.SEARCH)
    btn_exportar = ft.ElevatedButton("Exportar Excel", icon=Icons.DOWNLOAD)
    progresso = ft.ProgressRing(width=40, height=40, visible=False)

    # ---------- FUNÇÕES AUXILIARES ----------

    def atualizar_tabela():
        """Atualiza exibição da tabela conforme a página atual."""
        tabela.rows.clear()
        inicio = (paginador_atual - 1) * registros_por_pagina
        fim = inicio + registros_por_pagina

        for linha in resultados[inicio:fim]:
            tabela.rows.append(ft.DataRow(cells=[
                ft.DataCell(ft.Text(str(linha.get(c, "")))) for c in CAMPOS_TABELA
            ]))

        total_paginas = max(1, (len(resultados) + registros_por_pagina - 1) // registros_por_pagina)
        paginador_info.value = f"Página {paginador_atual} de {total_paginas}"
        page.update()

    def exportar_excel(e):
        """Exporta resultados para Excel."""
        if not resultados:
            page.snack_bar = ft.SnackBar(ft.Text("Nenhum dado para exportar."), bgcolor=Colors.RED)
            page.snack_bar.open = True
            page.update()
            return

        df = pd.DataFrame(resultados)
        nome_arquivo = f"Consulta_CADIN_{time.strftime('%Y%m%d_%H%M%S')}.xlsx"
        df.to_excel(nome_arquivo, index=False)
        page.snack_bar = ft.SnackBar(ft.Text(f"Arquivo salvo: {nome_arquivo}"), bgcolor=Colors.GREEN)
        page.snack_bar.open = True
        page.update()

    def anterior(e):
        nonlocal paginador_atual
        if paginador_atual > 1:
            paginador_atual -= 1
            atualizar_tabela()

    def proximo(e):
        nonlocal paginador_atual
        if paginador_atual * registros_por_pagina < len(resultados):
            paginador_atual += 1
            atualizar_tabela()

    def consultar(e):
        """Executa a consulta CADIN usando o TOKEN_JWT manual."""
        nonlocal resultados, paginador_atual

        token = campo_token.value.strip()
        entrada = campo_documentos.value.strip()

        if not token:
            page.snack_bar = ft.SnackBar(ft.Text("Informe o TOKEN_JWT para prosseguir."), bgcolor=Colors.RED)
            page.snack_bar.open = True
            page.update()
            return

        if not entrada:
            page.snack_bar = ft.SnackBar(ft.Text("Informe ao menos um CPF ou CNPJ."), bgcolor=Colors.RED)
            page.snack_bar.open = True
            page.update()
            return

        # 🔹 Limpa máscaras e separa documentos
        documentos = [
            "".join(ch for ch in d if ch.isdigit())
            for d in entrada.replace(",", "\n").split("\n")
            if d.strip()
        ]

        if len(documentos) > 10:
            page.snack_bar = ft.SnackBar(ft.Text("Limite máximo: 10 documentos."), bgcolor=Colors.RED)
            page.snack_bar.open = True
            page.update()
            return

        progresso.visible = True
        page.update()

        try:
            resultados = consultar_cadin(token, documentos)

        except Exception as ex:
            page.snack_bar = ft.SnackBar(ft.Text(f"Erro: {ex}"), bgcolor=Colors.RED)
            page.snack_bar.open = True

        finally:
            progresso.visible = False

        if not resultados:
            page.snack_bar = ft.SnackBar(ft.Text("Nenhum dado encontrado."), bgcolor=Colors.RED)
            page.snack_bar.open = True
        else:
            paginador_atual = 1
            atualizar_tabela()
            page.snack_bar = ft.SnackBar(ft.Text(f"{len(resultados)} registros retornados."), bgcolor=Colors.GREEN)
            page.snack_bar.open = True

        page.update()

    # ---------- EVENTOS ----------
    btn_consultar.on_click = consultar
    btn_exportar.on_click = exportar_excel
    btn_anterior.on_click = anterior
    btn_proximo.on_click = proximo

    # ---------- LAYOUT ----------
    conteudo = ft.Column(
        [
            titulo,
            campo_token,
            campo_documentos,
            ft.Row([btn_consultar, btn_exportar, progresso], spacing=15),
            ft.Divider(height=1, color=Colors.with_opacity(0.2, Colors.WHITE)),
            tabela,
            ft.Row(
                [btn_anterior, paginador_info, btn_proximo],
                alignment=ft.MainAxisAlignment.CENTER,
                spacing=10,
            ),
        ],
        expand=True,
        scroll=ft.ScrollMode.AUTO,
    )

    return conteudo
