"""
Consulta sob demanda — TRF3
Processo: 5044070-33.2025.4.03.6301 (Sueli Batista da Silva)
"""

import os
import time
import requests
from datetime import datetime

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


def buscar_datajud():
    query = {"query": {"match": {"numeroProcesso": NUMERO_PROCESSO.replace("-","").replace(".","")}}}
    resp = requests.post(
        DATAJUD_URL,
        json=query,
        headers={"Authorization": DATAJUD_KEY, "Content-Type": "application/json"},
        timeout=30,
    )
    resp.raise_for_status()

    hits = resp.json().get("hits", {}).get("hits", [])
    if not hits:
        print("  Nenhum resultado no Datajud")
        return []

    movimentos = hits[0].get("_source", {}).get("movimentos", [])
    print(f"  Total de movimentações no Datajud: {len(movimentos)}")

    # Mostra as 5 mais recentes para debug
    movimentos_sorted = sorted(movimentos, key=lambda x: x.get("dataHora",""), reverse=True)
    print("  Últimas 5 datas no Datajud:")
    for m in movimentos_sorted[:5]:
        print(f"    dataHora={m.get('dataHora','')} | nome={m.get('nome','')}")

    movs = []
    for m in movimentos:
        data_raw = m.get("dataHora", "")
        print(f"  Processando: dataHora={data_raw!r}")
        # Tenta diferentes formatos de data
        data_dt = None
        for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d", "%d/%m/%Y"):
            try:
                data_dt = datetime.strptime(data_raw[:len(fmt.replace('%Y','0000').replace('%m','00').replace('%d','00').replace('%H','00').replace('%M','00').replace('%S','00'))], fmt)
                break
            except Exception:
                continue

        if data_dt is None:
            try:
                data_dt = datetime.fromisoformat(data_raw[:19])
            except Exception:
                print(f"    ✗ Não conseguiu parsear a data: {data_raw!r}")
                continue

        print(f"    data_dt={data_dt} | corte={DATA_CORTE} | passa={data_dt >= DATA_CORTE}")
        if data_dt >= DATA_CORTE:
            movs.append({
                "data": data_dt.strftime("%d/%m/%Y"),
                "data_dt": data_dt,
                "descricao": m.get("nome", ""),
            })

    movs.sort(key=lambda x: x["data_dt"], reverse=True)
    print(f"  Movimentações após {DATA_CORTE.strftime('%d/%m/%Y')}: {len(movs)}")
    return movs


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


def main():
    print(f"Consulta — {NUMERO_PROCESSO}")
    print(f"Data de corte: {DATA_CORTE.strftime('%d/%m/%Y')}")

    try:
        movs = buscar_datajud()
    except Exception as e:
        print(f"Erro: {e}")
        enviar_whatsapp(f"⚠️ Erro ao consultar: {e}")
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
