from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
import time

def obtener_comando_hta(url):
    options = Options()
    options.add_argument('--headless')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--ignore-certificate-errors')
    options.add_argument('--allow-insecure-localhost')
    driver = webdriver.Chrome(options=options)
    try:
        driver.get(url)
        time.sleep(5)
        # Login automático si aparece formulario
        try:
            user_input = driver.find_element(By.XPATH, "//input[contains(@type, 'email') or contains(@type, 'text') and contains(@name, 'user') or contains(@id, 'user')]")
            pass_input = driver.find_element(By.XPATH, "//input[contains(@type, 'password')]")
            login_btn = driver.find_element(By.XPATH, "//button[contains(text(), 'Sign in') or contains(text(), 'Login') or contains(@type, 'submit')]")
            user_input.clear()
            user_input.send_keys("jesus.diaz-campos@hpe.com")
            pass_input.clear()
            pass_input.send_keys("Liam.dan.ric-28")
            login_btn.click()
            time.sleep(5)
        except Exception:
            pass  # Si no hay login, continuar
        comando = None
        pres = driver.find_elements(By.TAG_NAME, "pre")
        for pre in pres:
            if pre.text.strip():
                comando = pre.text.strip()
                break
        if not comando:
            textareas = driver.find_elements(By.TAG_NAME, "textarea")
            for ta in textareas:
                if ta.text.strip():
                    comando = ta.text.strip()
                    break
        if not comando:
            try:
                rerun_section = driver.find_element(By.XPATH, "//*[contains(text(), 'Re-run commands')]")
                sibling = rerun_section.find_element(By.XPATH, "following-sibling::*[1]")
                if sibling.text.strip():
                    comando = sibling.text.strip()
            except Exception:
                pass
        if not comando:
            comando = driver.find_element(By.TAG_NAME, "body").text
        return comando
    finally:
        driver.quit()

if __name__ == "__main__":
    url = "https://hta.rose.rdlabs.hpecorp.net/triage_assistant/row/260279350/"
    comando = obtener_comando_hta(url)
    print("Comando original:")
    print(comando)
