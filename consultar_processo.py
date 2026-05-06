"""
Consulta sob demanda — TRF3
Tenta Datajud primeiro (rápido). Se falhar, usa Selenium (TRF3 direto).
Processo: 5044070-33.2025.4.03.6301 (Sueli Batista da Silva)
"""

import os
import time
import requests
from datetime import datetime

# ─── CONFIGURAÇÕES ───────────────────────────────────────────

NUMERO_PROCESSO   = "5044070-33.2025.4.03.6301"
NOME_PARTE        = "Sueli Batista da Silva"
DATA_CORTE        = datetime.strptime("01/04/2026", "%d/%m/%Y")

ZAPI_INSTANCE     = os.environ.get("ZAPI_INSTANCE", "")
ZAPI_TOKEN        = os.environ.get("ZAPI_TOKEN", "")
ZAPI_CLIENT_TOKEN = os.environ.get("ZAPI_CLIENT_TOKEN", "")
NUMEROS_WHATSAPP  = [
    os.environ.get("NUMERO_WHATSAPP", ""),
    "5511949543288",
]

DATAJUD_URL = "https://api-publica.datajud.cnj.jus.br/api_publica_trf3/_search"
DATAJUD_KEY = "APIKey " + os.environ.get("DATAJUD_KEY", "")
TRF3_URL    = "https://pje1g.trf3.jus.br/pje/ConsultaPublica/listView.seam"


# ─── FONTE 1: DATAJUD (rápido) ───────────────────────────────

def buscar_datajud():
    print("  [1/2] Tentando Datajud...")
    query = {"query": {"match": {"numeroProcesso": NUMERO_PROCESSO.replace("-","").replace(".","") }}}
    for tentativa in range(1, 4):
        try:
            resp = requests.post(
                DATAJUD_URL,
                json=query,
                headers={"Authorization": DATAJUD_KEY, "Content-Type": "application/json"},
                timeout=15,
            )
            resp.raise_for_status()
            hits = resp.json().get("hits", {}).get("hits", [])
            if not hits:
                return []
            movimentos = hits[0].get("_source", {}).get("movimentos", [])
            movs = []
            for m in movimentos:
                data_raw = m.get("dataHora", "")[:10]
                try:
                    data_dt = datetime.strptime(data_raw, "%Y-%m-%d")
                    if data_dt < DATA_CORTE:
                        continue
                    movs.append({
                        "data": data_dt.strftime("%d/%m/%Y"),
                        "data_dt": data_dt,
                        "descricao": m.get("nome", ""),
                    })
                except Exception:
                    continue
            movs.sort(key=lambda x: x["data_dt"], reverse=True)
            print(f"  ✓ Datajud OK — {len(movs)} movimentação(ões)")
            return movs
        except Exception as e:
            print(f"  Datajud tentativa {tentativa}/3: {e}")
            if tentativa < 3:
                time.sleep(5)
    return None  # None = falhou, tentar fallback


# ─── FONTE 2: TRF3 via Selenium (fallback) ───────────────────

def buscar_selenium():
    print("  [2/2] Datajud indisponível — usando TRF3 direto...")
    from selenium import webdriver
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.chrome.service import Service
    from webdriver_manager.chrome import ChromeDriverManager

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

    driver = webdriver.Chrome(
        service=Service(ChromeDriverManager().install()),
        options=opts
    )
    movs = []
    try:
        driver.get(TRF3_URL)
        time.sleep(3)

        campo = WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.XPATH,
                "//input[contains(@id,'numProcesso') or contains(@name,'numProcesso')]"
            ))
        )
        campo.clear()
        campo.send_keys(NUMERO_PROCESSO.replace("-","").replace(".",""))
        time.sleep(1)

        btn = driver.find_element(By.XPATH,
            "//input[@value='Pesquisar'] | //button[contains(text(),'Pesquisar')]"
        )
        btn.click()
        time.sleep(4)

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

        for linha in driver.find_elements(By.XPATH, "//table//tr[td]"):
            cols = linha.find_elements(By.TAG_NAME, "td")
            if len(cols) >= 2:
                data_txt = cols[0].text.strip()[:10]
                desc_txt = cols[-1].text.strip()
                try:
                    data_dt = datetime.strptime(data_txt, "%d/%m/%Y")
                    if data_dt >= DATA_CORTE:
                        movs.append({"data": data_txt, "data_dt": data_dt, "descricao": desc_txt})
                except Exception:
                    pass

        movs.sort(key=lambda x: x["data_dt"], reverse=True)
        print(f"  ✓ TRF3 OK — {len(movs)} movimentação(ões)")
    finally:
        driver.quit()

    return movs


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
    print(f"Consulta sob demanda — {NUMERO_PROCESSO}...")

    movs = buscar_datajud()

    if movs is None:
        try:
            movs = buscar_selenium()
        except Exception as e:
            enviar_whatsapp(f"⚠️ Erro ao consultar o processo:\n{e}")
            raise SystemExit(0)

    if not movs:
        mensagem = (
            f"⚖️ *Consulta — TRF3*\n"
            f"Processo: {NUMERO_PROCESSO}\n"
            f"Parte: {NOME_PARTE}\n\n"
            f"Nenhuma movimentação encontrada após 01/04/2026. 📭"
        )
    else:
        linhas = [
            "⚖️ *Consulta — TRF3*",
            f"Processo: {NUMERO_PROCESSO}",
            f"Parte: {NOME_PARTE}",
            "",
            "*Movimentações a partir de 01/04/2026:*",
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
