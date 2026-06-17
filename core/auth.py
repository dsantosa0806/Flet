import os
from core.permissoes import Perfil


def obter_perfil_aplicacao() -> Perfil:
    perfil = os.getenv("SIOR_APP_PROFILE", "USUARIO").upper()

    if perfil == "ADMIN":
        return Perfil.ADMIN

    return Perfil.USUARIO