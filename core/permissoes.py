from enum import Enum


class Perfil(str, Enum):
    USUARIO = "USUARIO"
    ADMIN = "ADMIN"


class Recurso(str, Enum):
    INICIO = "Inicio"
    SOBRE = "Sobre"

    SIOR_CONSULTA = "SIOR_Consulta"
    SIOR_PROPRIETARIO = "SIOR_Proprietario"
    SIOR_PLACA = "SIOR_Placa"
    SIOR_DOWNLOAD = "SIOR_Download"
    SIOR_LOGIN_MANUAL = "Login Manual SIOR"
    SIOR_COBRANCA = "SIOR_Consulta_Cobranca"
    SIOR_COBRANCA_DEVEDOR = "SIOR_Consulta_Cobranca_Devedor"
    SIOR_PAINEL_SUPERVISOR = "SIOR_Consulta_Painel_Super"

    SAPIENS_CONSULTA = "Sapiens_Consulta"
    CADIN_CONSULTA = "CADIN_Consulta"

    ADMIN_USUARIOS = "ADMIN_Usuarios"
    ADMIN_CONFIGURACOES = "ADMIN_Configuracoes"
    ADMIN_LOGS = "ADMIN_Logs"


PERMISSOES = {
    Perfil.USUARIO: {
        Recurso.INICIO,
        Recurso.SOBRE,
        Recurso.SIOR_CONSULTA,
        Recurso.SIOR_PROPRIETARIO,
        Recurso.SIOR_PLACA,
        Recurso.SIOR_DOWNLOAD,
        Recurso.SIOR_LOGIN_MANUAL,
        Recurso.SIOR_COBRANCA,
        Recurso.SIOR_COBRANCA_DEVEDOR,
        Recurso.SAPIENS_CONSULTA,
        Recurso.CADIN_CONSULTA,
    },

    Perfil.ADMIN: set(Recurso),
}


def tem_permissao(perfil: Perfil, recurso: Recurso) -> bool:
    return recurso in PERMISSOES.get(perfil, set())