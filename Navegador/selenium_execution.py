import sys
import time
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoSuchElementException
import re
from selenium.webdriver.common.keys import Keys
from create_dir.diretorios import verify_downloads


# Oh Lord, forgive me for what I'm about to Code !
def acessa_sior(navegador):
    try:
        # Acesso a tela de login
        url_login = 'http://servicos.dnit.gov.br/sior/Account/Login/?ReturnUrl=%2Fsior%2F'
        navegador.get(url_login)
    except:
        print('Erro', 'O SIOR apresentou instabilidade, '
                      'por favor reinicie a aplicação e tente novamente T:acessa_sior ')
        sys.exit()


def login(navegador):
    path_btn_entrar_gov = '//*[@id="placeholder"]/div[1]/div/div/div/div/div/div/form/div[2]/button'
    qr_code_path = '//*[@id="login-cpf"]/div[5]/a'
    logado = '//*[@id="center-pane"]/div/div/div[1]/div[2]'

    try:
        WebDriverWait(navegador, 120).until(
            EC.presence_of_element_located(
                (By.XPATH, path_btn_entrar_gov))).click()
        WebDriverWait(navegador, 120).until(
            EC.presence_of_element_located(
                (By.XPATH, qr_code_path))).click()
        WebDriverWait(navegador, 120).until(
            EC.presence_of_element_located(
                (By.XPATH, logado))).is_displayed()
    except:
        return 1


def elemento_existe(navegador, by, value):
    try:
        elemento = navegador.find_element(by, value)
        if elemento.is_displayed():
            return True
    except NoSuchElementException:
        return False
    return False


def acessa_tela_incial_auto(navegador):
    # Acessa a tela da notificação da autuação
    url_base = 'https://servicos.dnit.gov.br/sior/Infracao/ConsultaAutoInfracao/?SituacoesInfracaoSelecionadas=0'
    try:
        navegador.get(url_base)
    except:
        return 1


def download_relatorio_financeiro(navegador, ait):
    path_id_relatorio_financeiro = 'btnExportarRelatorioFinanceiro'
    path_menu_relat = '//*[@id="menu_relatorio"]/li/span'

    try:
        WebDriverWait(navegador, 15).until(
            EC.element_to_be_clickable((By.XPATH, path_menu_relat))).click()
    except:
        print('Erro - ao clicar no menu relatório')
        return 1

    # CLIQUE PARA BAIXAR RELATÓRIO RESUMIDO
    try:
        WebDriverWait(navegador, 15).until(
            EC.element_to_be_clickable(
                (By.ID, path_id_relatorio_financeiro))).click()
        while True:
            janelas = navegador.window_handles
            if len(janelas) == 1:
                navegador.switch_to.window(janelas[0])
                break
    except:
        print('Erro - ao clicar em baixar e aguardar janela relatório')
        return 1


def download_relatorio(navegador, auto):
    for ait in auto:
        acessa_tela_incial_auto(navegador)
        input_ait = ait
        path_auto = '//*[@id="NumeroAuto"]'
        path_btn_closefilter = '//*[@id="SituacoesInfracaoSelecionadas_taglist"]/div/span[2]/span'
        path_btn_consultar = '//*[@id="placeholder"]/div[1]/div/div[1]/button'
        path_details = '//*[@id="gridInfracao"]/table/tbody/tr/td[1]/a'
        path_auto_empty = '//*[@id="gridInfracao"]/div[1]'

        try:
            WebDriverWait(navegador, 30).until(
                EC.element_to_be_clickable((By.XPATH, path_auto))).clear()
        except:
            print('Erro - ao limpar campo AIT')
            return 1

        # INPUT AIT
        try:
            WebDriverWait(navegador, 15).until(
                EC.element_to_be_clickable((By.XPATH, path_auto))).send_keys(input_ait)
        except:
            print('Erro - Input AIT')
            return 1

        # REALIZA A CONSULTA
        try:
            WebDriverWait(navegador, 15).until(
                EC.element_to_be_clickable((By.XPATH, path_btn_consultar))).click()
        except:
            print('Erro - ao realizar a consulta')
            return 1

        # detalhes
        try:
            WebDriverWait(navegador, 15).until(
                EC.element_to_be_clickable((By.XPATH, path_details))).click()

        except:
            print('Erro - clicar em details do AIT')
            return 1

        if download_relatorio_financeiro(navegador, ait) == 1:
            print(f'Erro ao baixar o Auto {ait}')
            continue
        time.sleep(3)
        if acessa_tela_incial_auto(navegador) == 1:
            print(f'Erro ao tentar acessar a tela inicial do auto no fim do loop')
            continue
        time.sleep(3)
    verify_downloads(len(auto))



