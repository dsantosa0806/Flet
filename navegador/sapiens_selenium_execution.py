import time
import json
import os
import requests
from selenium import webdriver
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.common.by import By
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.support import expected_conditions as EC
import config

COOKIE_PATH = config.COOKIE_PATH


def acessa_sapiens(navegador):
    try:
        navegador.get('https://sapiens.agu.gov.br')
    except Exception as e:
        print(f'Erro ao acessar o SAPIENS: {e}')


def salvar_cookies(navegador, caminho=COOKIE_PATH):
    os.makedirs(os.path.dirname(caminho), exist_ok=True)
    with open(caminho, "w") as f:
        json.dump(navegador.get_cookies(), f, indent=4)


def carregar_cookies(navegador, caminho=COOKIE_PATH):
    if os.path.exists(caminho):
        with open(caminho, "r") as f:
            cookies = json.load(f)
            for cookie in cookies:
                navegador.add_cookie(cookie)


def options_nav():
    options = webdriver.ChromeOptions()
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--disable-extensions")
    options.add_argument("--start-minimized")
    options.add_argument("--window-size=800,600")

    return options


def login(navegador, usuario, senha):

    try:
        acessa_sapiens(navegador)

        WebDriverWait(navegador, 30).until(
            EC.presence_of_element_located((By.XPATH, '//*[@id="cpffield-1017-inputEl"]'))
        ).send_keys(usuario)

        WebDriverWait(navegador, 30).until(
            EC.presence_of_element_located((By.XPATH, '//*[@id="textfield-1018-inputEl"]'))
        ).send_keys(senha)

        navegador.find_element(By.XPATH, '//*[@id="button-1019-btnInnerEl"]').click()

        # Espera o login ser bem-sucedido ou o erro aparecer
        try:
            WebDriverWait(navegador, 10).until(
                EC.presence_of_element_located((By.XPATH, '//*[@id="painelUsuario_header_hd-textEl"]'))
            )
            print("✅ Login realizado com sucesso")
            time.sleep(2)

            selenium_cookies = navegador.get_cookies()
            cookies_dict = {cookie["name"]: cookie["value"] for cookie in selenium_cookies}
            return navegador, cookies_dict

        except TimeoutException:
            # Verifica se o erro de login apareceu
            try:
                erro_login = navegador.find_element(By.XPATH, '//*[@id="messagebox-1001-displayfield-inputEl"]/b[1]')
                print(f"❌ Erro no login: {erro_login.text}")
            except:
                print("❌ Login falhou, mas não foi possível identificar a mensagem de erro.")
            navegador.quit()
            return None, None

    except Exception as e:
        print(f"❌ Exceção ao tentar logar: {e}")
        navegador.quit()
        return None, None