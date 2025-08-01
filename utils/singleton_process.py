import psutil
import os


def ja_esta_rodando(prefixo_nome="RPA"):
    current_pid = os.getpid()
    for proc in psutil.process_iter(attrs=['pid', 'name']):
        try:
            info = proc.as_dict(attrs=['pid', 'name'])
            nome = info['name']
            pid = info['pid']
            if nome and nome.startswith(prefixo_nome) and pid != current_pid:
                return True
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            continue
    return False
