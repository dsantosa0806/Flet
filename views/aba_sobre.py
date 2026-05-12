def aba_sobre(ft, HEADING_FONT_SIZE, DEFAULT_FONT_SIZE):
    texto_ajuda = ft.Text(
        "ℹ️ COMO UTILIZAR A APLICAÇÃO\n",
        size=HEADING_FONT_SIZE,
        weight="bold"
    )

    descricao_geral = ft.Text(
        "Esta aplicação foi desenvolvida para facilitar a consulta e o download de informações "
        "relacionadas aos Autos de Infração e Créditos no SAPIENS, de forma simples e automatizada.",
        size=DEFAULT_FONT_SIZE
    )

    titulo_consulta_ait = ft.Text("📋 Aba 'Consulta AIT'", weight="bold", size=DEFAULT_FONT_SIZE)
    conteudo_consulta_ait = ft.Text(
        "- Informe um ou mais números de AITs no campo de entrada (formato válido: Letra + 9 dígitos).\n"
        "- Clique em 'Iniciar Consulta'. Os dados serão exibidos em uma tabela paginada.\n"
        "- Use os filtros para refinar sua busca por situação ou número.\n"
        "- Você pode exportar os dados para Excel clicando em '📤 Exportar XLSX'.",
        size=DEFAULT_FONT_SIZE
    )

    titulo_download = ft.Text("⬇️ Aba 'Download de Relatórios'", weight="bold", size=DEFAULT_FONT_SIZE)
    conteudo_download = ft.Text(
        "- Insira os códigos de AIT desejados (um por linha).\n"
        "- Selecione os tipos de relatório que deseja baixar (Financeiro e/ou Resumido).\n"
        "- Clique em 'Iniciar Processo'. Os relatórios serão baixados automaticamente na pasta de Downloads.\n"
        "- O log mostrará o andamento e possíveis falhas de download.",
        size=DEFAULT_FONT_SIZE
    )

    titulo_sapiens = ft.Text("🔍 Aba 'Consulta Crédito Sapiens'", weight="bold", size=DEFAULT_FONT_SIZE)
    conteudo_sapiens = ft.Text(
        "- Informe o CPF ou CNPJ do devedor.\n"
        "- Preencha suas credenciais do SAPIENS (serão salvas localmente com segurança).\n"
        "- Clique em 'Consultar'. Os créditos serão exibidos em tabela.\n"
        "- Você pode exportar todos os dados para Excel com o botão '📤 Exportar XLSX'.",
        size=DEFAULT_FONT_SIZE
    )

    titulo_painel_supervisor = ft.Text("📊 Aba 'Painel Supervisor'", weight="bold", size=DEFAULT_FONT_SIZE)
    conteudo_painel_supervisor = ft.Text(
        "- Selecione a equipe desejada na lista suspensa.\n"
        "- Clique em 'Consultar' para extrair os dados relacionados à equipe no sistema SIOR.\n"
        "- Serão exibidos cartões com o total por Situação Fase e indicadores organizados em abas.\n"
        "- Utilize o botão 'Exportar Excel' para gerar um arquivo contendo:\n"
        "    • Todos os dados extraídos;\n"
        "    • Resumo por técnico, fase, e datas de análise/conferência;\n"
        "    • Distribuição por devedor (quantidade e valor);\n"
        "    • Cruzamento entre Técnico e Situação Fase;\n"
        "- Os dados podem ser utilizados para acompanhamento e tomada de decisão da equipe.",
        size=DEFAULT_FONT_SIZE
    )

    titulo_cadin = ft.Text("🔍 Aba 'CADIN'", weight="bold", size=DEFAULT_FONT_SIZE)
    conteudo_cadin = ft.Text(
        "- Informe o TOKEN JWT após login manual no https://cadin.pgfn.gov.br/#/home.\n"
        "- Informe o CPF ou CNPJ do devedor.\n"
        "- Clique em 'Consultar CADIN'. Os registros serão exibidos em tabela.\n"
        "- Você pode exportar todos os dados para Excel com o botão '📤 Exportar XLSX'.",
        size=DEFAULT_FONT_SIZE
    )

    titulo_erros = ft.Text("⚠️ Em caso de erros ou problemas", weight="bold", size=DEFAULT_FONT_SIZE)
    conteudo_erros = ft.Text(
        "- O Chrome deverá sempre estar atualizado para o correto funcionamento da aplicação.\n"
        "- Verifique se o número do AIT ou CPF/CNPJ está no formato correto.\n"
        "- Certifique-se de que o login e senha do SAPIENS estão atualizados e corretos.\n"
        "- Caso o navegador não inicie ou o sistema retorne erro de login, feche o programa e tente novamente.\n"
        "- Confira a conexão com a internet e evite interações manuais enquanto os processos estiverem executando.\n"
        "- Utilize o log disponível nas abas para verificar o que ocorreu e, se necessário, envie para suporte.",
        size=DEFAULT_FONT_SIZE
    )

    return ft.Column([
        ft.Row([ft.Text("Ajuda > Sobre", size=10, weight="bold")], alignment="center"),
        ft.Divider(),
        texto_ajuda,
        descricao_geral,
        ft.Divider(),
        titulo_consulta_ait,
        conteudo_consulta_ait,
        ft.Divider(),
        titulo_download,
        conteudo_download,
        ft.Divider(),
        titulo_sapiens,
        conteudo_sapiens,
        ft.Divider(),
        titulo_painel_supervisor,
        conteudo_painel_supervisor,
        ft.Divider(),
        titulo_cadin,
        conteudo_cadin,
        ft.Divider(),
        titulo_erros,
        conteudo_erros,
    ], expand=True, scroll=ft.ScrollMode.AUTO)
