import os


def abrir_pasta_exportacao(caminho_arquivo):
    """
    Abre no Windows Explorer a pasta onde o arquivo exportado foi salvo.
    """

    try:
        pasta = os.path.dirname(caminho_arquivo)

        if not os.path.exists(pasta):
            os.makedirs(pasta, exist_ok=True)

        os.startfile(pasta)

    except Exception as ex:
        print(f"⚠ Não foi possível abrir a pasta de exportação: {ex}")