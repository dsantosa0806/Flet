import flet as ft
import threading
import re
import os
from datetime import datetime
from main import executar_fluxo_completo

navegador_global = None
historico_logs = []

def main(page: ft.Page):
    global navegador_global, historico_logs

    page.title = "SIOR - Relatórios de AIT"
    page.scroll = "AUTO"
    page.padding = 20
    page.theme_mode = "light"

    def toggle_theme(e):
        page.theme_mode = "dark" if page.theme_mode == "light" else "light"
        toggle_switch.label = "🌙 Modo Escuro" if page.theme_mode == "light" else "🌞 Modo Claro"
        page.update()

    toggle_switch = ft.Switch(
        label="🌙 Modo Escuro",
        value=False,
        on_change=toggle_theme,
        tooltip="Alternar entre tema claro e escuro"
    )

    check_financeiro = ft.Checkbox(label="Relatório Financeiro", value=True)
    check_resumido = ft.Checkbox(label="Relatório Resumido")
    input_codigos = ft.TextField(label="Códigos AIT (um por linha)", multiline=True, min_lines=5, max_lines=10, expand=True)
    log_console = ft.TextField(label="📝 Log de Execução", multiline=True, disabled=True, expand=True, height=200)
    log_historico_view = ft.TextField(value="", multiline=True, read_only=True, expand=True, height=300)
    progress_bar = ft.ProgressBar(value=0, width=400)
    progress_text = ft.Text("Progresso: 0%", visible=False)
    status_msg = ft.Text(value="", size=14, color="green", visible=False)

    btn_iniciar = ft.ElevatedButton(
        "Iniciar Processo",
        icon=ft.Icons.DOWNLOAD,
        on_click=None,
        bgcolor="blue",
        color="white"
    )

    def run_process(e):
        def resetar_botao():
            btn_iniciar.disabled = False
            btn_iniciar.text = "Iniciar Processo"
            btn_iniciar.icon = ft.Icons.DOWNLOAD
            page.update()

        btn_iniciar.text = "Aguarde..."
        btn_iniciar.icon = ft.Icons.HOURGLASS_EMPTY
        btn_iniciar.disabled = True
        status_msg.visible = False
        page.update()

        codigos = [c.strip() for c in input_codigos.value.splitlines() if c.strip()]
        erros = []

        if not codigos:
            erros.append("⚠ É necessário inserir ao menos um código AIT.")
        if len(set(codigos)) < len(codigos):
            erros.append("⚠ Existem códigos duplicados.")
        if len(codigos) > 100:
            erros.append("⚠ Limite máximo de 100 códigos AIT por vez.")
        if any(" " in codigo for codigo in codigos):
            erros.append("⚠ Os códigos AIT não podem conter espaços.")
        if any(not re.match(r"^[A-Za-z]{1}[0-9]{9}$", codigo) for codigo in codigos):
            erros.append("⚠ Todos os códigos devem ter o formato: Letra + 9 dígitos.")
        if not (check_financeiro.value or check_resumido.value):
            erros.append("⚠ Selecione ao menos um tipo de relatório.")

        if erros:
            log_console.value = "\n".join(erros)
            resetar_botao()
            return

        progress_bar.value = 0
        progress_text.visible = True
        progress_text.value = "Progresso: 0%"
        page.update()

        def update_progress(atual, total):
            progress_bar.value = atual / total
            progress_text.value = f"Progresso: {int((atual / total) * 100)}%"
            page.update()

        def resetar_botao():
            btn_iniciar.disabled = False
            btn_iniciar.text = "Iniciar Processo"
            btn_iniciar.icon = ft.Icons.DOWNLOAD
            page.update()

        def task():
            global navegador_global
            try:
                log_console.value = ""
                navegador_global = executar_fluxo_completo(
                    "\n".join(codigos),
                    log=log_console,
                    baixar_financeiro=check_financeiro.value,
                    baixar_resumido=check_resumido.value,
                    atualizar_progresso=update_progress,
                    total=len(codigos)
                )
                progress_bar.value = 1
                progress_text.value = "✅ Concluído"
                historico_logs.append(log_console.value)
                log_historico_view.value = "\n\n".join(historico_logs)
                status_msg.value = "✅ Processo concluído."
                status_msg.visible = True
            finally:
                resetar_botao()

        threading.Thread(target=task).start()

    btn_iniciar.on_click = run_process

    def exportar_logs(e):
        snackbar = ft.SnackBar(ft.Text("Logs exportados com sucesso!"))
        page.snack_bar = snackbar
        try:
            timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            nome_arquivo = os.path.join(os.path.expanduser("~"), "Downloads", f"Logs_{timestamp}.txt")
            with open(nome_arquivo, "w", encoding="utf-8") as f:
                f.write("\n\n".join(historico_logs) or "Nenhum log disponível.")
            page.snack_bar.open = True
            page.update()
        except Exception as ex:
            print(f"❌ Erro ao exportar logs: {ex}")

    aba_download = ft.Column([
        ft.Text("📥 DOWNLOAD DE RELATÓRIOS", size=18, weight="bold"),
        ft.Text("Insira até 100 códigos AIT válidos (ex: B123456789) e selecione os relatórios desejados."),
        ft.Divider(),
        ft.Row([check_financeiro, check_resumido]),
        input_codigos,
        ft.Row([btn_iniciar], alignment="center"),
        status_msg,
        ft.Container(content=ft.Column([progress_bar, progress_text]), alignment=ft.alignment.center),
        log_console
    ])

    aba_logs = ft.Column([
        ft.Text("🧾 LOGS DE EXECUÇÃO", size=18, weight="bold"),
        ft.Text("Aqui você pode revisar e exportar os logs gerados durante os processos executados."),
        ft.Divider(),
        log_historico_view,
        ft.Row([
            ft.ElevatedButton("Exportar Logs", icon=ft.Icons.DOWNLOAD, on_click=exportar_logs)
        ], alignment="center")
    ])

    aba_consulta = ft.Column([
        ft.Text("🔍 CONSULTA AIT", size=18, weight="bold"),
        ft.Text("Funcionalidade em desenvolvimento. Em breve será possível consultar informações detalhadas dos autos."),
    ])

    aba_sobre = ft.Column([
        ft.Text("ℹ️ SOBRE A APLICAÇÃO", size=18, weight="bold"),
        ft.Text("Esta aplicação permite baixar relatórios de Autos de Infração de Trânsito (AIT) diretamente do sistema SIOR."),
        ft.Text("- Insira até 100 códigos AIT no formato: 1 LETRA + 9 DÍGITOS (ex: B123456789)."),
        ft.Text("- Os relatórios serão salvos na pasta Downloads."),
        ft.Text("- É possível escolher entre relatório financeiro, resumido ou ambos."),
        ft.Text("- O navegador abrirá automaticamente para login se necessário."),
    ])

    page.add(
        ft.Column([
            ft.Row([
                ft.Text("SIOR Relatórios", size=20, weight="bold", expand=True),
                toggle_switch
            ], alignment="spaceBetween"),
            ft.Tabs(
                selected_index=0,
                animation_duration=200,
                tabs=[
                    ft.Tab(text="📥 Download de Relatórios", content=aba_download),
                    ft.Tab(text="🧾 Logs", content=aba_logs),
                    ft.Tab(text="🔍 Consulta AIT", content=aba_consulta),
                    ft.Tab(text="ℹ Sobre", content=aba_sobre),
                ],
                expand=1
            )
        ])
    )

ft.app(target=main)
