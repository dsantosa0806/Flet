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
    SIOR_DISTRIBUICAO_SUPERVISOR = "SIOR_Distribuicao_Processos"

    SIOR_VARREDURA_DIVIDA = "ADMIN_Varredura_SIOR"
    SAPIENS_TAREFAS = "ADMIN_Sapiens_Tarefas"
    SAPIENS_EXTINTOS = "ADMIN_Sapiens_Extintos_Pagamento"
    ADMIN_SIOR_Suspensao = "ADMIN_SIOR_Suspensao"
    ADMIN_SIOR_Reativacao = "ADMIN_SIOR_Reativacao"
    ADMIN_SIOR_Registro_Pagamento = "ADMIN_SIOR_Registro_Pagamento"
    ADMIN_SIOR_Encaminhamento_Varredura = "ADMIN_SIOR_Varredura_Encaminhamento"

    SAPIENS_CONSULTA = "Sapiens_Consulta"
    CADIN_CONSULTA = "CADIN_Consulta"
    ADMIN_Sapiens_Tarefas_Em_Aberto_Setor = "ADMIN_Sapiens_Tarefas_Em_Aberto_Setor"
    ADMIN_Sapiens_Creditos_Suspensos_Parcelamento = "ADMIN_Sapiens_Creditos_Suspensos_Parcelamento"

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
        Recurso.SIOR_VARREDURA_DIVIDA,
        Recurso.SAPIENS_TAREFAS,
        Recurso.SAPIENS_EXTINTOS,
        Recurso.SIOR_PAINEL_SUPERVISOR,
        Recurso.ADMIN_SIOR_Suspensao,
        Recurso.ADMIN_SIOR_Reativacao,
        Recurso.ADMIN_SIOR_Registro_Pagamento,
        Recurso.ADMIN_SIOR_Encaminhamento_Varredura,
        Recurso.ADMIN_Sapiens_Tarefas_Em_Aberto_Setor,
        Recurso.ADMIN_Sapiens_Creditos_Suspensos_Parcelamento,
        Recurso.SIOR_DISTRIBUICAO_SUPERVISOR

    },

    Perfil.ADMIN: set(Recurso),
}


def tem_permissao(perfil: Perfil, recurso: Recurso) -> bool:
    return recurso in PERMISSOES.get(perfil, set())