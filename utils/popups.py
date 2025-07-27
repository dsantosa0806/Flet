import threading


def mostrar_alerta(ft, page, titulo: str, mensagem: str, tipo="info", duracao=3):
    """
    Exibe um alerta modal (popup) por até X segundos.

    :param page: instância da página Flet
    :param titulo: título do alerta
    :param mensagem: texto do corpo
    :param tipo: tipo do alerta ("info", "success", "error", "warning")
    :param duracao: tempo em segundos para fechamento automático
    """
    cores = {
        "info": ("ℹ️", "blue"),
        "success": ("✅", "green"),
        "error": ("❌", "red"),
        "warning": ("⚠️", "orange"),
    }

    icone, cor = cores.get(tipo, ("ℹ️", "blue"))

    page.dialog.title = ft.Text(f"{icone} {titulo}", color=cor, weight="bold")
    page.dialog.content = ft.Text(mensagem)
    page.dialog.actions = [
        ft.TextButton("OK", on_click=lambda e: fechar_dialogo(page))
    ]
    page.dialog.actions_alignment = "end"
    page.dialog.open = True
    page.update()

    # Fecha automaticamente após o tempo definido
    def fechar_auto():
        if page.dialog.open:
            page.dialog.open = False
            page.update()

    threading.Timer(duracao, fechar_auto).start()


def fechar_dialogo(page):
    if page.dialog.open:
        page.dialog.open = False
        page.update()
