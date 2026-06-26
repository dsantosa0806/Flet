import os
from core.permissoes import Perfil


def obter_perfil_aplicacao() -> Perfil:
    perfil = os.getenv(
        "SIOR_APP_PROFILE",
        "TECNICO"
    ).upper().strip()

    # Compatibilidade com versão antiga
    if perfil == "USUARIO":
        perfil = "SUPERVISAO"

    if perfil == "ADMIN":
        return Perfil.ADMIN

    if perfil == "SUPERVISAO":
        return Perfil.SUPERVISAO

    return Perfil.TECNICO