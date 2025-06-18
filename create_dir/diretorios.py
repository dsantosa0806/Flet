import os
import shutil
import time
from fnmatch import fnmatch
import config
import subprocess

diretorio = config.diretorio
pasta_arquivos = config.pasta_arquivos
pasta_autos = config.pasta_autos
caminho_padrao = config.caminho_padrao
caminho_destino_padrao = config.caminho_destino_padrao


def clean_diretorio_autos_pass():
    os.chdir(caminho_padrao)  # Muda para o diretório especificado
    try:
        for arquivo in os.listdir():
            caminho_completo = os.path.join(caminho_padrao, arquivo)  # Obter o caminho completo do arquivo/diretório

            # Alterar permissões antes de tentar remover
            os.chmod(caminho_completo, 0o644)

            # Verifica se é um arquivo e remove
            if os.path.isfile(caminho_completo):
                os.remove(caminho_completo)
            # Verifica se é um diretório e remove recursivamente
            elif os.path.isdir(caminho_completo):
                shutil.rmtree(caminho_completo, ignore_errors=True)
    except Exception as e:
        print(f"Ocorreu um erro: {e}")
        return 1


def clean_diretorio_arquivos_pass():
    os.chdir(caminho_destino_padrao)
    try:
        for arquivo in os.listdir():
            os.chmod(caminho_destino_padrao, 0o644)
            shutil.rmtree(arquivo, ignore_errors=True)
    except:
        return 1


def diretorios_exec(processo):
    file = processo.replace('/', '-')
    os.chdir(caminho_padrao)
    try:
        if not os.path.exists(file):
            os.mkdir(file)  # Cria a pasta AIT do Loop

    except:
        shutil.rmtree(processo, ignore_errors=True)
        print('Erro', 'A Pasta já existe e será deletada. Tente novamente!')
        return 1

    try:
        err = True
        while err:
            for arquivo in os.listdir():
                file_path = os.path.join(caminho_padrao, arquivo)
                if os.access(file_path, os.W_OK):
                    err = False
                else:
                    print(f"{arquivo} is not writable")
                    return 1
    except:
        return 1

    try:
        for arquivo in os.listdir():
            if arquivo != file:
                os.chmod(arquivo, 0o644)
                shutil.move(arquivo, file)  # move todos arquivos baixados para a pasta do ait do Loop
    except:
        print('erro', f'Erro ao mover os arquivos para a pasta final{ValueError}')
        return 1

    try:
        time.sleep(2)
        if os.path.exists(caminho_destino_padrao + '\\' + file):
            shutil.rmtree(caminho_destino_padrao + '\\' + file, ignore_errors=True)
            if os.access(caminho_padrao + '\\' + file, os.W_OK):
                os.chmod(caminho_padrao, 0o644)
                shutil.move(caminho_padrao + '\\' + file, caminho_destino_padrao)
            else:
                print('Erro', f'Permissão negada. Auto {file}')
                return 1
        else:
            os.chmod(caminho_padrao, 0o644)
            shutil.move(caminho_padrao + '\\' + file, caminho_destino_padrao)


    except:
        return 1

    # Conta a quantidade de registros na pasta
    try:
        quantidade_arquivos = len([arquivo for arquivo in os.listdir(caminho_destino_padrao + '\\' + file) if
                                   os.path.isfile(os.path.join(caminho_destino_padrao + '\\' + file, arquivo))])

        return quantidade_arquivos

    except:
        print('Erro na contagem de arquivos')
        return 1


def verify_downloads(qtde):
    contador = 40
    while True:
        if contador == 0:
            return 1
        else:
            if len(os.listdir(caminho_padrao)) < qtde or\
                    '.crdownload' in str(os.listdir(caminho_padrao)) or\
                    '.tmp' in str(os.listdir(caminho_padrao)):  # Não conta o True de criar pasta
                time.sleep(1)
                contador -= 1
            else:
                pdf_files = [file for file in os.listdir(caminho_padrao) if fnmatch(file, '*.pdf')]
                num_pdf_files = len(pdf_files)
                if qtde == num_pdf_files:
                    break


def open_dir_arquivos():
    subprocess.run(["explorer", diretorio + pasta_arquivos])