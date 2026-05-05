"""
Monitor de Processo Jurídico — TRF3
Usa a API pública do Datajud (CNJ) — sem scraping, sem bloqueios
Processo: 5044070-33.2025.4.03.6301 (Sueli Batista da Silva)
"""

import requests
import hashlib
import json
import os
from datetime import datetime

# ─── CONFIGURAÇÕES ───────────────────────────────────────────

NUMERO_PROCESSO   = "5044070-33.2025.4.03.6301"
NOME_PARTE        = "Sueli Batista da Silva"

ZAPI_INSTANCE     = os.environ.get("ZAPI_INSTANCE", "")
ZAPI_TOKEN        = os.environ.get("ZAPI_TOKEN", "")
ZAPI_CLIENT_TOKEN = os.environ.get("ZAPI_CLIENT_TOKEN", "")
NUMERO_WHATSAPP   = os.environ.get("NUMERO_WHATSAPP", "")

ARQUIVO_ESTADO    = "estado_processo.json"

# ─── DATAJUD (API oficial do CNJ) ────────────────────────────

DATAJUD_URL = "https://api-publica.datajud.cnj.jus.br/api_publica_trf3/_search"
DATAJUD_KEY = "APIKey " + os.environ.get("DATAJUD_KEY", "")  # chave pública oficial do CNJ


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
        headers={
            "Authorization": DATAJUD_KEY,
            "Content-Type": "application/json",
        },
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()

    hits = data.get("hits", {}).get("hits", [])
    if not hits:
        print("  Nenhum resultado encontrado no Datajud para esse processo.")
        return []

    processo = hits[0].get("_source", {})
    movimentos = processo.get("movimentos", [])

    movimentacoes = []
    for m in movimentos:
        data_mov = m.get("dataHora", "")[:10]  # pega só a data YYYY-MM-DD
        # Converte para DD/MM/YYYY
        try:
            data_fmt = datetime.strptime(data_mov, "%Y-%m-%d").strftime("%d/%m/%Y")
        except Exception:
            data_fmt = data_mov

        nome = m.get("nome", "") or m.get("complementosTabelados", [{}])[0].get("descricao", "")
        movimentacoes.append({"data": data_fmt, "descricao": nome})

    # Ordena do mais recente para o mais antigo
    movimentacoes.sort(key=lambda x: x["data"], reverse=True)
    return movimentacoes


# ─── ESTADO ──────────────────────────────────────────────────

def carregar_estado():
    if os.path.exists(ARQUIVO_ESTADO):
        try:
            with open(ARQUIVO_ESTADO, "r", encoding="utf-8") as f:
                conteudo = f.read().strip()
                if conteudo:
                    return json.loads(conteudo)
        except (json.JSONDecodeError, ValueError):
            pass
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
    print(f"Verificando processo {NUMERO_PROCESSO} via Datajud/CNJ ...")

    try:
        movs = buscar_movimentacoes()
    except Exception as e:
        print(f"✗ Erro ao consultar Datajud: {e}")
        raise SystemExit(0)

    print(f"  {len(movs)} movimentação(ões) encontrada(s).")

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
