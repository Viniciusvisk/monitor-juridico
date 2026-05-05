"""
Consulta sob demanda — TRF3 via Selenium (navegador real)
Processo: 5044070-33.2025.4.03.6301 (Sueli Batista da Silva)
"""

import os
import time
import json
import requests
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options

# ─── CONFIGURAÇÕES ───────────────────────────────────────────

NUMERO_PROCESSO   = "5044070-33.2025.4.03.6301"
NOME_PARTE        = "Sueli Batista da Silva"
DATA_CORTE        = datetime.strptime("13/04/2026", "%d/%m/%Y")

ZAPI_INSTANCE     = os.environ.get("ZAPI_INSTANCE", "")
ZAPI_TOKEN        = os.environ.get("ZAPI_TOKEN", "")
ZAPI_CLIENT_TOKEN = os.environ.get("ZAPI_CLIENT_TOKEN", "")
NUMEROS_WHATSAPP  = [
    os.environ.get("NUMERO_WHATSAPP", ""),
    "5511949543288",
]

URL = "https://pje1g.trf3.jus.br/pje/ConsultaPublica/listView.seam"


# ─── SELENIUM ────────────────────────────────────────────────

def criar_driver():
    opts = Options()
    opts.add_argument("--headless")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--disable-gpu")
    opts.add_argument("--window-size=1920,1080")
    opts.add_argument(
        "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    )
    return webdriver.Chrome(options=opts)


def buscar_movimentacoes():
    driver = criar_driver()
    movimentacoes = []

    try:
        print("  Abrindo site do TRF3...")
        driver.get(URL)
        time.sleep(3)

        # Preenche número do processo
        campo = WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.XPATH,
                "//input[contains(@id,'numProcesso') or contains(@name,'numProcesso')]"
            ))
        )
        num_limpo = NUMERO_PROCESSO.replace("-", "").replace(".", "")
        campo.clear()
        campo.send_keys(num_limpo)
        time.sleep(1)

        # Clica em Pesquisar
        btn = driver.find_element(By.XPATH,
            "//input[@value='Pesquisar' or @value='pesquisar'] | //button[contains(text(),'Pesquisar')]"
        )
        btn.click()
        time.sleep(4)

        # Clica no processo encontrado
        try:
            link = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.XPATH,
                    "//a[contains(@id,'processo') or contains(@href,'processo')]"
                ))
            )
            link.click()
            time.sleep(3)
        except Exception:
            pass

        # Extrai movimentações da tabela
        linhas = driver.find_elements(By.XPATH, "//table//tr[td]")
        for linha in linhas:
            cols = linha.find_elements(By.TAG_NAME, "td")
            if len(cols) >= 2:
                data_txt = cols[0].text.strip()
                desc_txt = cols[-1].text.strip()
                if data_txt and desc_txt and len(data_txt) >= 8:
                    try:
                        data_dt = datetime.strptime(data_txt[:10], "%d/%m/%Y")
                        if data_dt >= DATA_CORTE:
                            movimentacoes.append({
                                "data": data_txt[:10],
                                "data_dt": data_dt,
                                "descricao": desc_txt,
                            })
                    except Exception:
                        pass

        movimentacoes.sort(key=lambda x: x["data_dt"], reverse=True)

    finally:
        driver.quit()

    return movimentacoes


# ─── WHATSAPP ────────────────────────────────────────────────

def enviar_whatsapp(mensagem: str):
    url = f"https://api.z-api.io/instances/{ZAPI_INSTANCE}/token/{ZAPI_TOKEN}/send-text"
    for numero in NUMEROS_WHATSAPP:
        if not numero:
            continue
        try:
            requests.post(
                url,
                json={"phone": numero, "message": mensagem},
                headers={"Content-Type": "application/json", "Client-Token": ZAPI_CLIENT_TOKEN},
                timeout=15,
            ).raise_for_status()
            print(f"  ✓ WhatsApp enviado para {numero}")
        except Exception as e:
            print(f"  ✗ Erro ao enviar para {numero}: {e}")


# ─── MAIN ────────────────────────────────────────────────────

def main():
    print(f"Consulta sob demanda — {NUMERO_PROCESSO} via TRF3...")

    try:
        movs = buscar_movimentacoes()
    except Exception as e:
        enviar_whatsapp(f"⚠️ Erro ao consultar o processo: {e}")
        raise SystemExit(0)

    if not movs:
        mensagem = (
            f"⚖️ *Consulta — TRF3*\n"
            f"Processo: {NUMERO_PROCESSO}\n"
            f"Parte: {NOME_PARTE}\n\n"
            f"Nenhuma movimentação encontrada após 13/04/2026. 📭"
        )
    else:
        linhas = [
            "⚖️ *Consulta — TRF3*",
            f"Processo: {NUMERO_PROCESSO}",
            f"Parte: {NOME_PARTE}",
            "",
            "*Movimentações a partir de 13/04/2026:*",
            "",
        ]
        for i, m in enumerate(movs, 1):
            linhas += [f"{i}. 📌 *{m['data']}*", f"   {m['descricao']}", ""]
        linhas.append("🔗 https://pje1g.trf3.jus.br/pje/ConsultaPublica/listView.seam")
        mensagem = "\n".join(linhas)

    enviar_whatsapp(mensagem)
    print("Concluído.")


if __name__ == "__main__":
    main()
