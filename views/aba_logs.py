import os
from datetime import datetime


def exportar_logs(ft, HEADING_FONT_SIZE, page, log_download, log_consulta):
    try:
        ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        path = os.path.join(os.path.expanduser("~"), "Downloads", f"Logs_{ts}.txt")
        with open(path, "w", encoding="utf-8") as f:
            f.write("-- Log Download --\n" + (log_download.value or "Nenhum log de download."))
            f.write("\n\n-- Log Consulta --\n" + (log_consulta.value or "Nenhum log de consulta."))
        page.snack_bar = ft.SnackBar(ft.Text("Logs exportados com sucesso!"))
        page.snack_bar.open = True
        page.update()
    except Exception as ex:
        page.snack_bar = ft.SnackBar(ft.Text(f"❌ Erro ao exportar logs: {ex}"))
        page.snack_bar.open = True
        page.update()

    aba_logs = ft.Column([
        ft.Text("🧾 LOGS", size=HEADING_FONT_SIZE, weight="bold"),
        ft.Row([ft.ElevatedButton("Exportar Logs",
                                  icon=ft.Icons.DOWNLOAD,
                                  on_click=exportar_logs)],
               alignment="center")
    ], expand=True)
