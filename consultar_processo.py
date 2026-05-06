"""
Consulta sob demanda — TRF3
Tenta Datajud primeiro. Se falhar, usa Selenium no TRF3 direto.
Processo: 5044070-33.2025.4.03.6301 (Sueli Batista da Silva)
"""

import os, time, requests
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options

NUMERO_PROCESSO   = "5044070-33.2025.4.03.6301"
NOME_PARTE        = "Sueli Batista da Silva"
DATA_CORTE        = datetime.strptime("01/04/2026", "%d/%m/%Y")

ZAPI_INSTANCE     = os.environ.get("ZAPI_INSTANCE", "")
ZAPI_TOKEN        = os.environ.get("ZAPI_TOKEN", "")
ZAPI_CLIENT_TOKEN = os.environ.get("ZAPI_CLIENT_TOKEN", "")
NUMEROS_WHATSAPP  = [os.environ.get("NUMERO_WHATSAPP", ""), "5511949543288"]

DATAJUD_URL = "https://api-publica.datajud.cnj.jus.br/api_publica_trf3/_search"
DATAJUD_KEY = "APIKey " + os.environ.get("DATAJUD_KEY", "")
TRF3_URL    = "https://pje1g.trf3.jus.br/pje/ConsultaPublica/listView.seam"


# ─── FONTE 1: DATAJUD ────────────────────────────────────────

def buscar_datajud():
    print("  Tentando Datajud...")
    query = {"query": {"match": {"numeroProcesso": NUMERO_PROCESSO.replace("-","").replace(".","")}}}
    for i in range(3):
        try:
            resp = requests.post(DATAJUD_URL, json=query,
                headers={"Authorization": DATAJUD_KEY, "Content-Type": "application/json"},
                timeout=20)
            resp.raise_for_status()
            hits = resp.json().get("hits",{}).get("hits",[])
            if not hits:
                return []
            movimentos = hits[0].get("_source",{}).get("movimentos",[])
            print(f"  Datajud OK — {len(movimentos)} movimentos no total")
            movs = []
            for m in movimentos:
                raw = m.get("dataHora","")
                try:
                    dt = datetime.fromisoformat(raw[:19]) if "T" in raw else datetime.strptime(raw[:10], "%Y-%m-%d")
                    if dt >= DATA_CORTE:
                        movs.append({"data": dt.strftime("%d/%m/%Y"), "data_dt": dt, "descricao": m.get("nome","")})
                except:
                    pass
            movs.sort(key=lambda x: x["data_dt"], reverse=True)
            print(f"  Após filtro ({DATA_CORTE.strftime('%d/%m/%Y')}): {len(movs)} movimentos")
            return movs
        except Exception as e:
            print(f"  Datajud tentativa {i+1}/3 falhou: {e}")
            time.sleep(5)
    return None  # Sinaliza falha total


# ─── FONTE 2: SELENIUM (TRF3 direto) ─────────────────────────

def buscar_selenium():
    print("  Datajud indisponível — usando TRF3 via navegador...")
    opts = Options()
    opts.add_argument("--headless")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--disable-gpu")
    opts.add_argument("--window-size=1920,1080")
    opts.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36")

    driver = webdriver.Chrome(options=opts)
    movs = []
    try:
        driver.get(TRF3_URL)
        time.sleep(4)

        campo = WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.XPATH,
                "//input[contains(@id,'numProcesso') or contains(@name,'numProcesso')]")))
        campo.clear()
        campo.send_keys(NUMERO_PROCESSO.replace("-","").replace(".",""))
        time.sleep(1)

        btn = driver.find_element(By.XPATH,
            "//input[@value='Pesquisar'] | //button[contains(text(),'Pesquisar')]")
        btn.click()
        time.sleep(5)

        try:
            link = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.XPATH,
                    "//a[contains(@id,'processo') or contains(@href,'processo')]")))
            link.click()
            time.sleep(3)
        except:
            pass

        for linha in driver.find_elements(By.XPATH, "//table//tr[td]"):
            cols = linha.find_elements(By.TAG_NAME, "td")
            if len(cols) >= 2:
                data_txt = cols[0].text.strip()[:10]
                desc_txt = cols[-1].text.strip()
                try:
                    dt = datetime.strptime(data_txt, "%d/%m/%Y")
                    if dt >= DATA_CORTE:
                        movs.append({"data": data_txt, "data_dt": dt, "descricao": desc_txt})
                except:
                    pass

        movs.sort(key=lambda x: x["data_dt"], reverse=True)
        print(f"  TRF3 Selenium OK — {len(movs)} movimentos após filtro")
    finally:
        driver.quit()
    return movs


# ─── WHATSAPP ────────────────────────────────────────────────

def enviar_whatsapp(mensagem):
    url = f"https://api.z-api.io/instances/{ZAPI_INSTANCE}/token/{ZAPI_TOKEN}/send-text"
    for numero in NUMEROS_WHATSAPP:
        if not numero:
            continue
        try:
            requests.post(url,
                json={"phone": numero, "message": mensagem},
                headers={"Content-Type": "application/json", "Client-Token": ZAPI_CLIENT_TOKEN},
                timeout=15).raise_for_status()
            print(f"  ✓ WhatsApp enviado para {numero}")
        except Exception as e:
            print(f"  ✗ Erro para {numero}: {e}")


# ─── MAIN ────────────────────────────────────────────────────

def main():
    print(f"Consulta — {NUMERO_PROCESSO} | Corte: {DATA_CORTE.strftime('%d/%m/%Y')}")

    movs = buscar_datajud()

    if movs is None:
        try:
            movs = buscar_selenium()
        except Exception as e:
            enviar_whatsapp(f"⚠️ Ambas as fontes falharam:\n{e}")
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
            f"Parte: {NOME_PARTE}", "",
            "*Movimentações a partir de 01/04/2026:*", "",
        ]
        for i, m in enumerate(movs, 1):
            linhas += [f"{i}. 📌 *{m['data']}*", f"   {m['descricao']}", ""]
        linhas.append("🔗 https://pje1g.trf3.jus.br/pje/ConsultaPublica/listView.seam")
        mensagem = "\n".join(linhas)

    enviar_whatsapp(mensagem)
    print("Concluído.")


if __name__ == "__main__":
    main()
