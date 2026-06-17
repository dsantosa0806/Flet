import threading
import flet as ft


def mostrar_alerta(ft, page, titulo, mensagem, tipo="info", duracao=5000):
    """
    Exibe alerta visual compatível com execução normal e PyInstaller.

    Tenta primeiro SnackBar.
    Se não funcionar, usa AlertDialog como fallback.
    """

    cores = {
        "success": ft.Colors.GREEN,
        "error": ft.Colors.RED,
        "warning": ft.Colors.ORANGE,
        "info": ft.Colors.BLUE,
    }

    icones = {
        "success": "✅",
        "error": "❌",
        "warning": "⚠️",
        "info": "ℹ️",
    }

    cor = cores.get(tipo, ft.Colors.BLUE)
    icone = icones.get(tipo, "ℹ️")

    texto = f"{icone} {titulo}\n{mensagem}"

    # =====================================================
    # 1. TENTATIVA PRINCIPAL: page.open(SnackBar)
    # =====================================================
    try:
        snack = ft.SnackBar(
            content=ft.Text(
                texto,
                color=ft.Colors.WHITE,
                selectable=True
            ),
            bgcolor=cor,
            duration=duracao,
            show_close_icon=True
        )

        page.open(snack)
        page.update()
        return True

    except Exception as ex:
        print(f"Falha ao abrir SnackBar via page.open: {ex}")

    # =====================================================
    # 2. FALLBACK: page.snack_bar tradicional
    # =====================================================
    try:
        page.snack_bar = ft.SnackBar(
            content=ft.Text(
                texto,
                color=ft.Colors.WHITE,
                selectable=True
            ),
            bgcolor=cor,
            duration=duracao,
            show_close_icon=True
        )

        page.snack_bar.open = True
        page.update()
        return True

    except Exception as ex:
        print(f"Falha ao abrir SnackBar via page.snack_bar: {ex}")

    # =====================================================
    # 3. FALLBACK FINAL: AlertDialog
    # =====================================================
    try:
        dialog = None

        def fechar(e=None):
            try:
                if dialog:
                    dialog.open = False
                    page.update()
            except Exception:
                pass

        dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text(f"{icone} {titulo}"),
            content=ft.Container(
                width=520,
                content=ft.Text(
                    str(mensagem),
                    selectable=True
                )
            ),
            actions=[
                ft.TextButton(
                    "Fechar",
                    on_click=fechar
                )
            ],
            actions_alignment=ft.MainAxisAlignment.END
        )

        try:
            page.open(dialog)
        except Exception:
            page.dialog = dialog
            dialog.open = True

        page.update()
        return True

    except Exception as ex:
        print(f"Falha ao abrir AlertDialog fallback: {ex}")
        return False


def fechar_dialogo(page):
    if page.dialog and page.dialog.open:
        page.dialog.open = False
        page.update()
