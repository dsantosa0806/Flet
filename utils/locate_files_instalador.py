import os
import sys


def caminho_recurso(caminho_relativo):
    """
    Retorna o caminho correto do recurso tanto no Python normal
    quanto no executável gerado pelo PyInstaller.
    """
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")

    return os.path.join(base_path, caminho_relativo)