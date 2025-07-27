import flet as ft
from views.aba_consulta_sapiens_divida import aba_consulta_sapiens
from views.aba_consulta_sior import aba_consulta
from views.aba_download import aba_download
from views.aba_sobre import aba_sobre
from config import DEFAULT_FONT_SIZE, HEADING_FONT_SIZE, WINDOW_WIDTH, WINDOW_HEIGHT, APP_TITLE


def construir_cabecalho(toggle_switch):
    return ft.Row([
        ft.Text(APP_TITLE, size=HEADING_FONT_SIZE, weight="bold"),
        toggle_switch
    ])


def construir_abas(page):
    return ft.Tabs(
        selected_index=0,
        animation_duration=200,
        tabs=[
            ft.Tab(text="Consulta AIT", content=aba_consulta(ft, DEFAULT_FONT_SIZE, HEADING_FONT_SIZE,
                                                             page)),
            ft.Tab(text="Download de Relatórios", content=aba_download(ft, DEFAULT_FONT_SIZE, HEADING_FONT_SIZE,
                                                                       page)),
            ft.Tab(text="Consulta Crédito Sapiens", content=aba_consulta_sapiens(ft, DEFAULT_FONT_SIZE,
                                                                                 HEADING_FONT_SIZE, page)),
            ft.Tab(text="Sobre", content=aba_sobre(ft, HEADING_FONT_SIZE, DEFAULT_FONT_SIZE)),
        ],
        expand=1
    )


def main(page: ft.Page):
    page.title = APP_TITLE
    page.window_width = WINDOW_WIDTH
    page.window_height = WINDOW_HEIGHT
    page.scroll = "AUTO"
    page.padding = 25
    page.theme_mode = "dark"
    page.window_resizable = True

    def toggle_theme(e):
        page.theme_mode = "dark" if page.theme_mode == "light" else "light"
        toggle_switch.label = "🌙 Modo Escuro" if page.theme_mode == "light" else "🌞 Modo Claro"
        page.update()

    toggle_switch = ft.Switch(
        label="🌙 Modo Escuro",
        value=False,
        on_change=toggle_theme,
        tooltip="Alternar claro/escuro"
    )

    # dentro do seu main():
    conteudo_limitado = ft.Container(
        content=ft.Column([
            construir_cabecalho(toggle_switch),
            construir_abas(page)
        ], expand=True),
        height=800,  # 👈 limita a altura
        expand=False,

    )
    # Dialogo global para exibir alertas
    dialogo_global = ft.AlertDialog(
        modal=True,
        title=ft.Text(""),
        content=ft.Text(""),
        actions=[ft.TextButton("OK")],
        actions_alignment="end"
    )

    page.dialog = dialogo_global

    page.add(conteudo_limitado)
    page.add(dialogo_global)


if __name__ == "__main__":
    ft.app(target=main)
