# ==========================================================
# CORE - LICENCIAMENTO SIMPLES / RENOVAÇÃO BIMESTRAL
# ==========================================================
import getpass
import hashlib
import hmac
import json
import os
import platform
import socket
import uuid
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any, Dict, Optional

import requests

import config


@dataclass
class LicencaResultado:
    liberado: bool
    requer_senha: bool = False
    titulo: str = ""
    mensagem: str = ""
    origem: str = "online"
    politica: Dict[str, Any] = field(default_factory=dict)
    machine_id: str = ""
    mes_referencia: str = ""
    valido_ate: str = ""


def _hoje() -> date:
    return date.today()


def _agora_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _parse_data_iso(valor: str) -> Optional[date]:
    try:
        return datetime.strptime(str(valor), "%Y-%m-%d").date()
    except Exception:
        return None


def _sha256(texto: str) -> str:
    return hashlib.sha256(
        texto.encode("utf-8")
    ).hexdigest()


def _ler_json_local(caminho: str) -> Dict[str, Any]:
    if not caminho or not os.path.exists(caminho):
        return {}

    try:
        with open(caminho, "r", encoding="utf-8") as arquivo:
            dados = json.load(arquivo)

        return dados if isinstance(dados, dict) else {}

    except Exception:
        return {}


def _salvar_json_local(caminho: str, dados: Dict[str, Any]) -> None:
    pasta = os.path.dirname(caminho)

    if pasta:
        os.makedirs(pasta, exist_ok=True)

    with open(caminho, "w", encoding="utf-8") as arquivo:
        json.dump(
            dados,
            arquivo,
            ensure_ascii=False,
            indent=4
        )


# ==========================================================
# IDENTIFICAÇÃO DA MÁQUINA
# ==========================================================
def obter_identidade_maquina() -> Dict[str, str]:
    try:
        hostname = platform.node() or socket.gethostname() or ""
    except Exception:
        hostname = ""

    try:
        usuario = getpass.getuser() or ""
    except Exception:
        usuario = ""

    try:
        mac = str(uuid.getnode())
    except Exception:
        mac = ""

    try:
        sistema = platform.system()
        release = platform.release()
        machine = platform.machine()
    except Exception:
        sistema = ""
        release = ""
        machine = ""

    base = "|".join(
        [
            hostname,
            usuario,
            mac,
            sistema,
            release,
            machine,
            str(getattr(config, "APP_PROFILE", "")),
            str(getattr(config, "LICENCA_SALT", "")),
        ]
    )

    machine_id = _sha256(base)

    return {
        "machine_id": machine_id,
        "hostname": hostname,
        "usuario": usuario,
        "sistema": sistema,
        "release": release,
        "machine": machine,
    }


# ==========================================================
# HASH DA SENHA SIMPLES
# ==========================================================
def gerar_hash_senha(
    senha: str,
    perfil: Optional[str] = None,
) -> str:
    perfil = str(
        perfil or getattr(config, "APP_PROFILE", "")
    ).upper().strip()

    texto = "|".join(
        [
            str(getattr(config, "LICENCA_SALT", "")),
            perfil,
            str(senha or "").strip(),
        ]
    )

    return _sha256(texto)


def _obter_hash_esperado(politica: Dict[str, Any]) -> Optional[str]:
    """
    Lê o hash da senha no formato simples.

    Formato recomendado:
    {
      "senha_hash_sha256": "hash..."
    }
    """

    valor = (
        politica.get("senha_hash_sha256")
        or politica.get("hash_senha_sha256")
        or politica.get("password_hash_sha256")
    )

    if valor:
        return str(valor).strip().lower()

    return None


# ==========================================================
# POLÍTICA REMOTA
# ==========================================================
def baixar_politica_licenca(timeout: int = 8) -> Dict[str, Any]:
    url = getattr(config, "URL_LICENCA", "")

    if not url:
        raise RuntimeError("URL_LICENCA não configurada no config.py.")

    response = requests.get(
        url,
        params={
            "_": int(datetime.now().timestamp())
        },
        timeout=timeout,
        headers={
            "Accept": "application/json",
            "Cache-Control": "no-cache",
            "Pragma": "no-cache",
        },
    )

    response.raise_for_status()

    dados = response.json()

    if not isinstance(dados, dict):
        raise RuntimeError("JSON de licença inválido.")

    return dados


def _hash_politica(politica: Dict[str, Any]) -> str:
    texto = json.dumps(
        politica,
        ensure_ascii=False,
        sort_keys=True
    )

    return _sha256(texto)


def _assinatura_cache(
    machine_id: str,
    perfil: str,
    periodo_referencia: str,
    valido_ate: str,
    hash_politica: str,
) -> str:
    texto = "|".join(
        [
            str(getattr(config, "LICENCA_SALT", "")),
            machine_id,
            perfil,
            periodo_referencia,
            valido_ate,
            hash_politica,
        ]
    )

    return _sha256(texto)


# ==========================================================
# VALIDAÇÕES DA POLÍTICA
# ==========================================================
def _validar_regras_politica(
    politica: Dict[str, Any],
    machine_id: str,
) -> LicencaResultado:
    perfil = str(
        getattr(config, "APP_PROFILE", "")
    ).upper().strip()

    periodo_referencia = str(
        politica.get("periodo_referencia")
        or politica.get("mes_referencia")
        or ""
    ).strip()

    valido_ate = str(
        politica.get("valido_ate") or ""
    ).strip()

    if not politica.get("ativo", True):
        return LicencaResultado(
            liberado=False,
            requer_senha=False,
            titulo="Aplicação bloqueada",
            mensagem=politica.get(
                "mensagem_bloqueio",
                "A aplicação está desativada temporariamente."
            ),
            politica=politica,
            machine_id=machine_id,
            mes_referencia=periodo_referencia,
            valido_ate=valido_ate,
        )

    perfil_json = str(
        politica.get("perfil") or perfil
    ).upper().strip()

    if perfil_json and perfil_json != perfil:
        return LicencaResultado(
            liberado=False,
            requer_senha=False,
            titulo="Perfil incompatível",
            mensagem=(
                f"O JSON de licença é do perfil {perfil_json}, "
                f"mas esta aplicação está no perfil {perfil}."
            ),
            politica=politica,
            machine_id=machine_id,
            mes_referencia=periodo_referencia,
            valido_ate=valido_ate,
        )

    perfil_cfg = (
        politica.get("perfis", {})
        .get(perfil, {})
    )

    if perfil_cfg and not perfil_cfg.get("ativo", True):
        return LicencaResultado(
            liberado=False,
            requer_senha=False,
            titulo="Perfil bloqueado",
            mensagem=f"O perfil {perfil} está desativado na política de licença.",
            politica=politica,
            machine_id=machine_id,
            mes_referencia=periodo_referencia,
            valido_ate=valido_ate,
        )

    maquinas_bloqueadas = set(
        str(x).strip()
        for x in politica.get("maquinas_bloqueadas", [])
        if str(x).strip()
    )

    if machine_id in maquinas_bloqueadas:
        return LicencaResultado(
            liberado=False,
            requer_senha=False,
            titulo="Computador bloqueado",
            mensagem="Este computador está bloqueado para uso da aplicação.",
            politica=politica,
            machine_id=machine_id,
            mes_referencia=periodo_referencia,
            valido_ate=valido_ate,
        )

    controlar_maquinas = bool(
        politica.get("controlar_maquinas", False)
    )

    maquinas_liberadas = set(
        str(x).strip()
        for x in politica.get("maquinas_liberadas", [])
        if str(x).strip()
    )

    if controlar_maquinas and maquinas_liberadas and machine_id not in maquinas_liberadas:
        return LicencaResultado(
            liberado=False,
            requer_senha=False,
            titulo="Computador não autorizado",
            mensagem=(
                "Este computador ainda não está na lista de máquinas autorizadas.\n\n"
                f"Machine ID: {machine_id}"
            ),
            politica=politica,
            machine_id=machine_id,
            mes_referencia=periodo_referencia,
            valido_ate=valido_ate,
        )

    data_validade = _parse_data_iso(valido_ate)

    if not data_validade:
        return LicencaResultado(
            liberado=False,
            requer_senha=False,
            titulo="Licença mal configurada",
            mensagem="O JSON de licença não possui valido_ate em formato YYYY-MM-DD.",
            politica=politica,
            machine_id=machine_id,
            mes_referencia=periodo_referencia,
            valido_ate=valido_ate,
        )

    if _hoje() > data_validade:
        return LicencaResultado(
            liberado=False,
            requer_senha=False,
            titulo="Licença vencida",
            mensagem=(
                f"A licença venceu em {valido_ate}. "
                "Atualize o JSON no GitHub Pages com uma nova senha e uma nova validade."
            ),
            politica=politica,
            machine_id=machine_id,
            mes_referencia=periodo_referencia,
            valido_ate=valido_ate,
        )

    hash_esperado = _obter_hash_esperado(politica)

    if not hash_esperado:
        return LicencaResultado(
            liberado=False,
            requer_senha=False,
            titulo="Licença mal configurada",
            mensagem=(
                "O JSON de licença não possui senha_hash_sha256.\n\n"
                "Gere o hash da senha bimestral e publique no JSON."
            ),
            politica=politica,
            machine_id=machine_id,
            mes_referencia=periodo_referencia,
            valido_ate=valido_ate,
        )

    return LicencaResultado(
        liberado=True,
        requer_senha=False,
        titulo="Política válida",
        mensagem="Política remota validada.",
        politica=politica,
        machine_id=machine_id,
        mes_referencia=periodo_referencia,
        valido_ate=valido_ate,
    )


# ==========================================================
# CACHE LOCAL
# ==========================================================
def _cache_local_valido(
    cache: Dict[str, Any],
    machine_id: str,
    politica: Optional[Dict[str, Any]] = None,
    permitir_offline: bool = False,
) -> bool:
    if not cache:
        return False

    perfil = str(
        getattr(config, "APP_PROFILE", "")
    ).upper().strip()

    if cache.get("machine_id") != machine_id:
        return False

    if str(cache.get("perfil", "")).upper() != perfil:
        return False

    periodo_referencia = str(
        cache.get("periodo_referencia")
        or cache.get("mes_referencia")
        or ""
    ).strip()

    valido_ate = str(
        cache.get("valido_ate") or ""
    ).strip()

    hash_politica = str(
        cache.get("hash_politica") or ""
    ).strip()

    data_validade = _parse_data_iso(valido_ate)

    if not data_validade:
        return False

    if _hoje() > data_validade:
        return False

    if politica is not None:
        hash_politica_atual = _hash_politica(politica)

        if hash_politica != hash_politica_atual:
            return False

    assinatura_esperada = _assinatura_cache(
        machine_id=machine_id,
        perfil=perfil,
        periodo_referencia=periodo_referencia,
        valido_ate=valido_ate,
        hash_politica=hash_politica,
    )

    assinatura_cache = str(
        cache.get("assinatura") or ""
    ).strip()

    if not hmac.compare_digest(
        assinatura_cache,
        assinatura_esperada,
    ):
        return False

    if permitir_offline:
        try:
            validado_em = datetime.fromisoformat(
                str(cache.get("validado_em"))
            ).date()

            dias_offline = (_hoje() - validado_em).days

            limite = int(
                getattr(config, "LICENCA_TOLERANCIA_OFFLINE_DIAS", 3)
            )

            if dias_offline > limite:
                return False

        except Exception:
            return False

    return True


def salvar_cache_licenca(
    politica: Dict[str, Any],
    machine_id: str,
) -> None:
    perfil = str(
        getattr(config, "APP_PROFILE", "")
    ).upper().strip()

    periodo_referencia = str(
        politica.get("periodo_referencia")
        or politica.get("mes_referencia")
        or ""
    ).strip()

    valido_ate = str(
        politica.get("valido_ate") or ""
    ).strip()

    hash_politica = _hash_politica(politica)

    cache = {
        "app": getattr(config, "APP_TITLE_BASE", "RPA Search Data"),
        "perfil": perfil,
        "machine_id": machine_id,
        "periodo_referencia": periodo_referencia,
        "valido_ate": valido_ate,
        "hash_politica": hash_politica,
        "validado_em": _agora_iso(),
        "assinatura": _assinatura_cache(
            machine_id=machine_id,
            perfil=perfil,
            periodo_referencia=periodo_referencia,
            valido_ate=valido_ate,
            hash_politica=hash_politica,
        ),
    }

    _salvar_json_local(
        config.LICENCA_CACHE_PATH,
        cache,
    )


# ==========================================================
# REGISTRO OPCIONAL DA MÁQUINA
# ==========================================================
def registrar_maquina_se_configurado(
    politica: Dict[str, Any],
    identidade: Dict[str, str],
) -> None:
    url = getattr(config, "URL_REGISTRO_MAQUINA", "") or ""

    if not url:
        return

    periodo_referencia = str(
        politica.get("periodo_referencia")
        or politica.get("mes_referencia")
        or ""
    ).strip()

    machine_id = identidade.get("machine_id", "")
    perfil = str(
        getattr(config, "APP_PROFILE", "")
    ).upper().strip()

    cache_registro = _ler_json_local(
        config.LICENCA_REGISTRO_CACHE_PATH
    )

    chave_atual = f"{machine_id}|{perfil}|{periodo_referencia}|{url}"

    if cache_registro.get("ultima_chave") == chave_atual:
        return

    payload = {
        "secret": getattr(config, "REGISTRO_MAQUINA_SECRET", ""),
        "app": getattr(config, "APP_TITLE_BASE", "RPA Search Data"),
        "perfil": perfil,
        "versao": getattr(config, "current_version", ""),
        "periodo_referencia": periodo_referencia,
        "machine_id": machine_id,
        "hostname": identidade.get("hostname", ""),
        "usuario": identidade.get("usuario", ""),
        "sistema": identidade.get("sistema", ""),
        "release": identidade.get("release", ""),
        "machine": identidade.get("machine", ""),
        "registrado_em": _agora_iso(),
    }

    try:
        response = requests.post(
            url,
            json=payload,
            timeout=6,
        )

        if response.status_code in (200, 201, 204):
            _salvar_json_local(
                config.LICENCA_REGISTRO_CACHE_PATH,
                {
                    "ultima_chave": chave_atual,
                    "machine_id": machine_id,
                    "perfil": perfil,
                    "periodo_referencia": periodo_referencia,
                    "registrado_em": _agora_iso(),
                },
            )

    except Exception:
        pass


# ==========================================================
# FUNÇÕES PÚBLICAS
# ==========================================================
def verificar_acesso_aplicacao() -> LicencaResultado:
    identidade = obter_identidade_maquina()
    machine_id = identidade["machine_id"]

    cache = _ler_json_local(
        config.LICENCA_CACHE_PATH
    )

    try:
        politica = baixar_politica_licenca()

    except Exception as ex:
        if _cache_local_valido(
            cache=cache,
            machine_id=machine_id,
            politica=None,
            permitir_offline=True,
        ):
            return LicencaResultado(
                liberado=True,
                requer_senha=False,
                titulo="Licença local válida",
                mensagem=(
                    "Não foi possível consultar a licença online, "
                    "mas o cache local ainda está dentro da tolerância offline."
                ),
                origem="cache_offline",
                politica={},
                machine_id=machine_id,
                mes_referencia=str(
                    cache.get("periodo_referencia")
                    or cache.get("mes_referencia")
                    or ""
                ),
                valido_ate=str(cache.get("valido_ate") or ""),
            )

        return LicencaResultado(
            liberado=False,
            requer_senha=False,
            titulo="Falha ao consultar licença",
            mensagem=(
                "Não foi possível consultar a licença online e não há cache local válido.\n\n"
                f"Detalhe: {ex}"
            ),
            origem="erro_online",
            politica={},
            machine_id=machine_id,
        )

    regras = _validar_regras_politica(
        politica=politica,
        machine_id=machine_id,
    )

    if not regras.liberado:
        return regras

    if _cache_local_valido(
        cache=cache,
        machine_id=machine_id,
        politica=politica,
        permitir_offline=False,
    ):
        return LicencaResultado(
            liberado=True,
            requer_senha=False,
            titulo="Licença válida",
            mensagem="Licença local validada com a política online atual.",
            origem="cache_online",
            politica=politica,
            machine_id=machine_id,
            mes_referencia=regras.mes_referencia,
            valido_ate=regras.valido_ate,
        )

    return LicencaResultado(
        liberado=False,
        requer_senha=True,
        titulo="Renovação necessária",
        mensagem=(
            f"Informe a senha vigente da aplicação.\n\n"
            f"Período: {regras.mes_referencia or 'não informado'}\n"
            f"Validade: {regras.valido_ate}"
        ),
        origem="senha_necessaria",
        politica=politica,
        machine_id=machine_id,
        mes_referencia=regras.mes_referencia,
        valido_ate=regras.valido_ate,
    )


def validar_senha_renovacao(
    senha: str,
    politica: Optional[Dict[str, Any]] = None,
) -> LicencaResultado:
    identidade = obter_identidade_maquina()
    machine_id = identidade["machine_id"]

    if politica is None:
        try:
            politica = baixar_politica_licenca()
        except Exception as ex:
            return LicencaResultado(
                liberado=False,
                requer_senha=True,
                titulo="Falha ao consultar licença",
                mensagem=f"Não foi possível consultar o JSON de licença: {ex}",
                origem="erro_online",
                politica={},
                machine_id=machine_id,
            )

    regras = _validar_regras_politica(
        politica=politica,
        machine_id=machine_id,
    )

    if not regras.liberado:
        return regras

    hash_esperado = _obter_hash_esperado(politica)

    hash_informado = gerar_hash_senha(
        senha=senha,
        perfil=getattr(config, "APP_PROFILE", ""),
    )

    if not hmac.compare_digest(
        str(hash_informado).lower(),
        str(hash_esperado).lower(),
    ):
        return LicencaResultado(
            liberado=False,
            requer_senha=True,
            titulo="Senha inválida",
            mensagem="A senha informada não corresponde à senha vigente da aplicação.",
            origem="senha_invalida",
            politica=politica,
            machine_id=machine_id,
            mes_referencia=regras.mes_referencia,
            valido_ate=regras.valido_ate,
        )

    salvar_cache_licenca(
        politica=politica,
        machine_id=machine_id,
    )

    registrar_maquina_se_configurado(
        politica=politica,
        identidade=identidade,
    )

    return LicencaResultado(
        liberado=True,
        requer_senha=False,
        titulo="Licença renovada",
        mensagem="Licença renovada com sucesso.",
        origem="senha_validada",
        politica=politica,
        machine_id=machine_id,
        mes_referencia=regras.mes_referencia,
        valido_ate=regras.valido_ate,
    )