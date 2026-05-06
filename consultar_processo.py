"""
Consulta sob demanda — TRF3
Acessa o site, navega até o detalhe do processo e exporta como PDF.
Processo: 5044070-33.2025.4.03.6301 (Sueli Batista da Silva)
"""

import os, time, base64, requests
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options

NUMERO_PROCESSO   = "5044070-33.2025.4.03.6301"
NOME_PARTE        = "Sueli Batista da Silva"
# Número sem formatação para digitar no campo
NUM_LIMPO         = "50440703320254036301"

ZAPI_INSTANCE     = os.environ.get("ZAPI_INSTANCE", "")
ZAPI_TOKEN        = os.environ.get("ZAPI_TOKEN", "")
ZAPI_CLIENT_TOKEN = os.environ.get("ZAPI_CLIENT_TOKEN", "")
NUMEROS_WHATSAPP  = [os.environ.get("NUMERO_WHATSAPP", ""), "5511949543288"]

TRF3_URL = "https://pje1g.trf3.jus.br/pje/ConsultaPublica/listView.seam"


def criar_driver():
    opts = Options()
    opts.add_argument("--headless")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--disable-gpu")
    opts.add_argument("--window-size=1280,900")
    opts.add_argument(
        "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    )
    return webdriver.Chrome(options=opts)


def gerar_pdf_trf3():
    driver = criar_driver()
    pdf_path = "/tmp/processo.pdf"

    try:
        print("  Abrindo TRF3...")
        driver.get(TRF3_URL)
        time.sleep(4)

        # ── Passo 1: preenche o número no campo correto ──
        print("  Preenchendo número do processo...")
        campo = WebDriverWait(driver, 20).until(
            EC.presence_of_element_located((By.XPATH,
                "//input[contains(@id,'Processo') or contains(@id,'processo') or contains(@name,'processo')]"
            ))
        )
        campo.clear()
        # Digita devagar para o campo aceitar corretamente
        for c in NUM_LIMPO:
            campo.send_keys(c)
            time.sleep(0.05)
        time.sleep(1)
        print(f"  Campo preenchido com: {campo.get_attribute('value')}")

        # ── Passo 2: clica em Pesquisar ──
        print("  Clicando em Pesquisar...")
        btn = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.XPATH,
                "//input[@type='submit'] | //button[@type='submit'] | "
                "//input[contains(@value,'esquis')] | //button[contains(text(),'esquis')]"
            ))
        )
        btn.click()
        time.sleep(6)

        print(f"  URL após pesquisa: {driver.current_url}")
        print(f"  Título da página: {driver.title}")

        # ── Passo 3: clica no link do processo na lista ──
        print("  Procurando link do processo na lista...")
        try:
            link = WebDriverWait(driver, 15).until(
                EC.element_to_be_clickable((By.XPATH,
                    "//*[contains(text(),'5044070') or contains(@href,'5044070') or "
                    "contains(@onclick,'5044070')]"
                ))
            )
            print(f"  Link encontrado: {link.text or link.get_attribute('href')}")
            link.click()
            time.sleep(6)
        except Exception as e:
            print(f"  Não encontrou link clicável: {e}")
            # Tira screenshot para debug
            driver.save_screenshot("/tmp/debug.png")

        print(f"  URL final: {driver.current_url}")
        print(f"  Título final: {driver.title}")

        # ── Passo 4: expande página para capturar tudo ──
        altura = driver.execute_script("return document.body.scrollHeight")
        driver.set_window_size(1280, min(altura + 300, 15000))
        time.sleep(2)

        # ── Passo 5: gera PDF via Chrome ──
        print("  Gerando PDF...")
        result = driver.execute_cdp_cmd("Page.printToPDF", {
            "printBackground": True,
            "paperWidth": 8.27,
            "paperHeight": 11.69,
            "marginTop": 0.6,
            "marginBottom": 0.6,
            "marginLeft": 0.5,
            "marginRight": 0.5,
            "scale": 0.85,
            "displayHeaderFooter": True,
            "headerTemplate": (
                f'<div style="font-size:9px;width:100%;text-align:center;color:#444;">'
                f'Processo: {NUMERO_PROCESSO} — {NOME_PARTE}</div>'
            ),
            "footerTemplate": (
                f'<div style="font-size:9px;width:100%;text-align:center;color:#444;">'
                f'Gerado em {datetime.now().strftime("%d/%m/%Y %H:%M")} — '
                f'Página <span class="pageNumber"></span> de <span class="totalPages"></span></div>'
            ),
        })

        with open(pdf_path, "wb") as f:
            f.write(base64.b64decode(result["data"]))

        print(f"  PDF salvo em {pdf_path}")
        return pdf_path

    finally:
        driver.quit()


def enviar_mensagem(mensagem):
    url = f"https://api.z-api.io/instances/{ZAPI_INSTANCE}/token/{ZAPI_TOKEN}/send-text"
    for numero in NUMEROS_WHATSAPP:
        if not numero:
            continue
        try:
            requests.post(url,
                json={"phone": numero, "message": mensagem},
                headers={"Content-Type": "application/json", "Client-Token": ZAPI_CLIENT_TOKEN},
                timeout=15).raise_for_status()
            print(f"  ✓ Mensagem para {numero}")
        except Exception as e:
            print(f"  ✗ Erro para {numero}: {e}")


def enviar_pdf(pdf_path):
    url = f"https://api.z-api.io/instances/{ZAPI_INSTANCE}/token/{ZAPI_TOKEN}/send-document/pdf"
    with open(pdf_path, "rb") as f:
        pdf_b64 = base64.b64encode(f.read()).decode()
    nome = f"processo_{datetime.now().strftime('%d-%m-%Y')}.pdf"
    for numero in NUMEROS_WHATSAPP:
        if not numero:
            continue
        try:
            requests.post(url,
                json={
                    "phone": numero,
                    "document": f"data:application/pdf;base64,{pdf_b64}",
                    "fileName": nome,
                    "caption": f"📄 {NUMERO_PROCESSO}\n{NOME_PARTE}",
                },
                headers={"Content-Type": "application/json", "Client-Token": ZAPI_CLIENT_TOKEN},
                timeout=60).raise_for_status()
            print(f"  ✓ PDF para {numero}")
        except Exception as e:
            print(f"  ✗ Erro PDF para {numero}: {e}")


def main():
    print(f"Consulta — {NUMERO_PROCESSO}")

    enviar_mensagem(
        f"⚖️ *Consultando TRF3...*\n"
        f"Processo: {NUMERO_PROCESSO}\n"
        f"🔄 Gerando PDF, aguarde..."
    )

    try:
        pdf_path = gerar_pdf_trf3()
        enviar_pdf(pdf_path)
        print("Concluído.")
    except Exception as e:
        print(f"Erro: {e}")
        enviar_mensagem(f"⚠️ Erro ao gerar PDF:\n{e}")


if __name__ == "__main__":
    main()
