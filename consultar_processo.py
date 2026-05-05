"""
Consulta sob demanda — responde no WhatsApp quando acionado via Pipedream
Processo: 5044070-33.2025.4.03.6301 (Sueli Batista da Silva)
"""

import requests
import json
import os
from datetime import datetime

NUMERO_PROCESSO   = "5044070-33.2025.4.03.6301"
NOME_PARTE        = "Sueli Batista da Silva"

ZAPI_INSTANCE     = os.environ.get("ZAPI_INSTANCE", "")
ZAPI_TOKEN        = os.environ.get("ZAPI_TOKEN", "")
ZAPI_CLIENT_TOKEN = os.environ.get("ZAPI_CLIENT_TOKEN", "")
NUMERO_WHATSAPP   = os.environ.get("NUMERO_WHATSAPP", "")
DATAJUD_KEY       = "APIKey " + os.environ.get("DATAJUD_KEY", "")

DATAJUD_URL = "https://api-publica.datajud.cnj.jus.br/api_publica_trf3/_search"
DATA_CORTE  = datetime.strptime("13/04/2026", "%d/%m/%Y")


def buscar_movimentacoes():
    query = {
        "query": {
            "match": {
                "numeroProcesso": NUMERO_PROCESSO.replace("-", "").replace(".", "")
            }
        }
    }
    resp = requests.post(
        DATAJUD_URL,
        json=query,
        headers={"Authorization": DATAJUD_KEY, "Content-Type": "application/json"},
        timeout=30,
    )
    resp.raise_for_status()
    hits = resp.json().get("hits", {}).get("hits", [])
    if not hits:
        return []

    movimentos = hits[0].get("_source", {}).get("movimentos", [])
    movimentacoes = []
    for m in movimentos:
        data_raw = m.get("dataHora", "")[:10]
        try:
            data_dt  = datetime.strptime(data_raw, "%Y-%m-%d")
            data_fmt = data_dt.strftime("%d/%m/%Y")
        except Exception:
            continue
        if data_dt < DATA_CORTE:
            continue
        nome = m.get("nome", "") or ""
        movimentacoes.append({"data": data_fmt, "data_dt": data_dt, "descricao": nome})

    movimentacoes.sort(key=lambda x: x["data_dt"], reverse=True)
    return movimentacoes


def enviar_whatsapp(mensagem: str):
    url = f"https://api.z-api.io/instances/{ZAPI_INSTANCE}/token/{ZAPI_TOKEN}/send-text"
    requests.post(
        url,
        json={"phone": NUMERO_WHATSAPP, "message": mensagem},
        headers={"Content-Type": "application/json", "Client-Token": ZAPI_CLIENT_TOKEN},
        timeout=15,
    ).raise_for_status()


def main():
    print("Consulta sob demanda iniciada...")
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
            f"*Últimas movimentações (a partir de 13/04/2026):*",
            "",
        ]
        for i, m in enumerate(movs, 1):
            linhas += [f"{i}. 📌 *{m['data']}*", f"   {m['descricao']}", ""]
        linhas.append("🔗 https://pje1g.trf3.jus.br/pje/ConsultaPublica/listView.seam")
        mensagem = "\n".join(linhas)

    enviar_whatsapp(mensagem)
    print(f"✓ Resposta enviada para {NUMERO_WHATSAPP}")


if __name__ == "__main__":
    main()
