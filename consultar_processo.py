"""
Consulta sob demanda — TRF3
Acessa o site, tira print da página e envia o PDF via WhatsApp.
Processo: 5044070-33.2025.4.03.6301 (Sueli Batista da Silva)
"""

import os, time, base64, requests, json
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options

# ─── CONFIGURAÇÕES ───────────────────────────────────────────

NUMERO_PROCESSO   = "5044070-33.2025.4.03.6301"
NOME_PARTE        = "Sueli Batista da Silva"

ZAPI_INSTANCE     = os.environ.get("ZAPI_INSTANCE", "")
ZAPI_TOKEN        = os.environ.get("ZAPI_TOKEN", "")
ZAPI_CLIENT_TOKEN = os.environ.get("ZAPI_CLIENT_TOKEN", "")
NUMEROS_WHATSAPP  = [os.environ.get("NUMERO_WHATSAPP", ""), "5511949543288"]

DATAJUD_URL = "https://api-publica.datajud.cnj.jus.br/api_publica_trf3/_search"
DATAJUD_KEY = "APIKey " + os.environ.get("DATAJUD_KEY", "")
TRF3_URL    = "https://pje1g.trf3.jus.br/pje/ConsultaPublica/listView.seam"


# ─── SELENIUM ────────────────────────────────────────────────

def criar_driver():
    opts = Options()
    opts.add_argument("--headless")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--disable-gpu")
    opts.add_argument("--window-size=1200,900")
    opts.add_argument(
        "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    )
    return webdriver.Chrome(options=opts)


def gerar_pdf_trf3():
    """Acessa o TRF3, navega até o processo e exporta a página como PDF."""
    driver = criar_driver()
    pdf_path = "/tmp/processo.pdf"

    try:
        print("  Abrindo TRF3...")
        driver.get(TRF3_URL)
        time.sleep(4)

        # Preenche o número do processo
        campo = WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.XPATH,
                "//input[contains(@id,'numProcesso') or contains(@name,'numProcesso')]"
            ))
        )
        campo.clear()
        campo.send_keys(NUMERO_PROCESSO.replace("-", "").replace(".", ""))
        time.sleep(1)

        # Clica em Pesquisar
        btn = driver.find_element(By.XPATH,
            "//input[@value='Pesquisar'] | //button[contains(text(),'Pesquisar')]"
        )
        btn.click()
        time.sleep(5)

        # Clica no link do processo
        try:
            link = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.XPATH,
                    "//a[contains(@id,'processo') or contains(@href,'processo') or contains(text(),'5044070')]"
                ))
            )
            link.click()
            time.sleep(4)
        except Exception as e:
            print(f"  Aviso ao clicar no processo: {e}")

        # Expande a página inteira para capturar todas as movimentações
        altura_total = driver.execute_script("return document.body.scrollHeight")
        driver.set_window_size(1200, altura_total + 200)
        time.sleep(2)

        print("  Gerando PDF da página...")

        # Usa o Chrome para imprimir como PDF
        result = driver.execute_cdp_cmd("Page.printToPDF", {
            "printBackground": True,
            "paperWidth": 8.27,   # A4 em polegadas
            "paperHeight": 11.69,
            "marginTop": 0.5,
            "marginBottom": 0.5,
            "marginLeft": 0.5,
            "marginRight": 0.5,
            "scale": 0.85,
            "displayHeaderFooter": True,
            "headerTemplate": f"""
                <div style="font-size:9px; width:100%; text-align:center; color:#555;">
                    Processo: {NUMERO_PROCESSO} — {NOME_PARTE}
                </div>
            """,
            "footerTemplate": f"""
                <div style="font-size:9px; width:100%; text-align:center; color:#555;">
                    Gerado em {datetime.now().strftime('%d/%m/%Y %H:%M')} —
                    Página <span class="pageNumber"></span> de <span class="totalPages"></span>
                </div>
            """,
        })

        with open(pdf_path, "wb") as f:
            f.write(base64.b64decode(result["data"]))

        print(f"  PDF gerado: {pdf_path}")
        return pdf_path

    finally:
        driver.quit()


# ─── WHATSAPP ────────────────────────────────────────────────

def enviar_mensagem_texto(mensagem):
    url = f"https://api.z-api.io/instances/{ZAPI_INSTANCE}/token/{ZAPI_TOKEN}/send-text"
    for numero in NUMEROS_WHATSAPP:
        if not numero:
            continue
        try:
            requests.post(url,
                json={"phone": numero, "message": mensagem},
                headers={"Content-Type": "application/json", "Client-Token": ZAPI_CLIENT_TOKEN},
                timeout=15).raise_for_status()
            print(f"  ✓ Mensagem enviada para {numero}")
        except Exception as e:
            print(f"  ✗ Erro mensagem para {numero}: {e}")


def enviar_pdf(pdf_path):
    """Envia o PDF via Z-API como documento."""
    url = f"https://api.z-api.io/instances/{ZAPI_INSTANCE}/token/{ZAPI_TOKEN}/send-document/pdf"

    with open(pdf_path, "rb") as f:
        pdf_b64 = base64.b64encode(f.read()).decode()

    nome_arquivo = f"processo_{datetime.now().strftime('%d-%m-%Y')}.pdf"

    for numero in NUMEROS_WHATSAPP:
        if not numero:
            continue
        try:
            resp = requests.post(url,
                json={
                    "phone": numero,
                    "document": f"data:application/pdf;base64,{pdf_b64}",
                    "fileName": nome_arquivo,
                    "caption": f"📄 Detalhe do processo {NUMERO_PROCESSO}\n{NOME_PARTE}",
                },
                headers={"Content-Type": "application/json", "Client-Token": ZAPI_CLIENT_TOKEN},
                timeout=60,
            )
            resp.raise_for_status()
            print(f"  ✓ PDF enviado para {numero}")
        except Exception as e:
            print(f"  ✗ Erro PDF para {numero}: {e}")


# ─── MAIN ────────────────────────────────────────────────────

def main():
    print(f"Consulta — {NUMERO_PROCESSO}")
    agora = datetime.now().strftime("%d/%m/%Y às %H:%M")

    # Avisa que está consultando
    enviar_mensagem_texto(
        f"⚖️ *Consultando processo no TRF3...*\n"
        f"Processo: {NUMERO_PROCESSO}\n"
        f"Parte: {NOME_PARTE}\n\n"
        f"🔄 Aguarde, estou gerando o PDF com as movimentações..."
    )

    try:
        pdf_path = gerar_pdf_trf3()
        enviar_pdf(pdf_path)
        print("Concluído.")
    except Exception as e:
        print(f"Erro: {e}")
        enviar_mensagem_texto(f"⚠️ Erro ao gerar PDF do processo:\n{e}")


if __name__ == "__main__":
    main()
