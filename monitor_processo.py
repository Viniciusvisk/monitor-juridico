"""
Monitor de Processo Jurídico — TRF3
Adaptado para GitHub Actions
Processo: 5044070-33.2025.4.03.6301 (Sueli Batista da Silva)
"""

import requests
import hashlib
import json
import os
import time
import random
from datetime import datetime
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# ─── CONFIGURAÇÕES ───────────────────────────────────────────

NUMERO_PROCESSO   = "5044070-33.2025.4.03.6301"
NOME_PARTE        = "Sueli Batista da Silva"

ZAPI_INSTANCE     = os.environ.get("ZAPI_INSTANCE", "")
ZAPI_TOKEN        = os.environ.get("ZAPI_TOKEN", "")
ZAPI_CLIENT_TOKEN = os.environ.get("ZAPI_CLIENT_TOKEN", "")
NUMERO_WHATSAPP   = os.environ.get("NUMERO_WHATSAPP", "")

ARQUIVO_ESTADO    = "estado_processo.json"

# ─── TRF3 ────────────────────────────────────────────────────

URL_CONSULTA = "https://pje1g.trf3.jus.br/pje/ConsultaPublica/listView.seam"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": (
        "text/html,application/xhtml+xml,application/xml;"
        "q=0.9,image/avif,image/webp,*/*;q=0.8"
    ),
    "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
    "Cache-Control": "max-age=0",
}


def criar_session():
    session = requests.Session()
    retry = Retry(
        total=4,
        backoff_factor=3,
        status_forcelist=[429, 500, 502, 503, 504],
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session


def buscar_movimentacoes():
    session = criar_session()

    pausa = random.uniform(3, 8)
    print(f"  Aguardando {pausa:.1f}s antes de acessar o TRF3...")
    time.sleep(pausa)

    print("  Carregando página inicial do TRF3...")
    resp = session.get(URL_CONSULTA, headers=HEADERS, timeout=60)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    viewstate = ""
    vs = soup.find("input", {"name": "javax.faces.ViewState"})
    if vs:
        viewstate = vs.get("value", "")
    print(f"  ViewState obtido: {'sim' if viewstate else 'não encontrado'}")

    time.sleep(random.uniform(2, 4))

    num_limpo = NUMERO_PROCESSO.replace("-", "").replace(".", "")
    payload = {
        "javax.faces.ViewState": viewstate,
        "fPP:numProcesso-inputNumeroProcesso": num_limpo,
        "fPP:pesquisar": "Pesquisar",
    }

    print("  Enviando consulta do processo...")
    headers_post = {**HEADERS, "Referer": URL_CONSULTA}
    resp2 = session.post(URL_CONSULTA, data=payload, headers=headers_post, timeout=60)
    resp2.raise_for_status()
    soup2 = BeautifulSoup(resp2.text, "html.parser")

    movimentacoes = []
    tabela = soup2.find("table", {"id": lambda x: x and "movimento" in str(x).lower()})

    if not tabela:
        for t in soup2.find_all("table"):
            for linha in t.find_all("tr")[1:]:
                cols = linha.find_all("td")
                if len(cols) >= 2:
                    data = cols[0].get_text(strip=True)
                    desc = cols[-1].get_text(strip=True)
                    if data and desc and len(data) >= 8:
                        movimentacoes.append({"data": data, "descricao": desc})
    else:
        for linha in tabela.find_all("tr")[1:]:
            cols = linha.find_all("td")
            if len(cols) >= 2:
                movimentacoes.append({
                    "data": cols[0].get_text(strip=True),
                    "descricao": cols[-1].get_text(strip=True),
                })

    return movimentacoes


# ─── ESTADO ──────────────────────────────────────────────────

def carregar_estado():
    if os.path.exists(ARQUIVO_ESTADO):
        with open(ARQUIVO_ESTADO, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"hash_ultimo": None, "ultima_verificacao": None, "movimentacoes": []}


def salvar_estado(estado):
    with open(ARQUIVO_ESTADO, "w", encoding="utf-8") as f:
        json.dump(estado, f, ensure_ascii=False, indent=2)


def hash_movs(movs):
    return hashlib.sha256(
        json.dumps(movs, sort_keys=True, ensure_ascii=False).encode()
    ).hexdigest()


# ─── WHATSAPP Z-API ──────────────────────────────────────────

def enviar_whatsapp(mensagem: str):
    url = (
        f"https://api.z-api.io/instances/{ZAPI_INSTANCE}"
        f"/token/{ZAPI_TOKEN}/send-text"
    )
    resp = requests.post(
        url,
        json={"phone": NUMERO_WHATSAPP, "message": mensagem},
        headers={"Content-Type": "application/json", "Client-Token": ZAPI_CLIENT_TOKEN},
        timeout=15,
    )
    resp.raise_for_status()
    print(f"✓ WhatsApp enviado para {NUMERO_WHATSAPP}")


def montar_mensagem(novas):
    linhas = [
        "⚖️ *Nova movimentação — TRF3*",
        f"Processo: {NUMERO_PROCESSO}",
        f"Parte: {NOME_PARTE}",
        "",
    ]
    for m in novas:
        linhas += [f"📌 *{m['data']}*", f"   {m['descricao']}", ""]
    linhas.append("🔗 https://pje1g.trf3.jus.br/pje/ConsultaPublica/listView.seam")
    return "\n".join(linhas)


# ─── MAIN ────────────────────────────────────────────────────

def main():
    print(f"Verificando processo {NUMERO_PROCESSO} ...")

    try:
        movs = buscar_movimentacoes()
    except requests.exceptions.Timeout:
        print("✗ Timeout — TRF3 pode estar fora do ar. Tentando na próxima execução.")
        raise SystemExit(0)
    except Exception as e:
        print(f"✗ Erro ao consultar TRF3: {e}")
        raise SystemExit(0)

    print(f"  {len(movs)} movimentação(ões) encontrada(s) no site.")

    estado    = carregar_estado()
    novo_hash = hash_movs(movs)

    if novo_hash != estado["hash_ultimo"]:
        antigas = {json.dumps(m, sort_keys=True) for m in estado.get("movimentacoes", [])}
        novas   = [m for m in movs if json.dumps(m, sort_keys=True) not in antigas]

        if novas:
            print(f"  → {len(novas)} nova(s) movimentação(ões)!")
            for m in novas:
                print(f"     {m['data']} — {m['descricao']}")
            try:
                enviar_whatsapp(montar_mensagem(novas))
            except Exception as e:
                print(f"  ✗ Erro WhatsApp: {e}")
        else:
            print("  → Conteúdo mudou mas sem movimentações novas identificadas.")

        estado["hash_ultimo"]   = novo_hash
        estado["movimentacoes"] = movs
    else:
        print("  → Sem novidades.")

    estado["ultima_verificacao"] = datetime.now().strftime("%d/%m/%Y %H:%M")
    salvar_estado(estado)
    print("Concluído.")


if __name__ == "__main__":
    main()
