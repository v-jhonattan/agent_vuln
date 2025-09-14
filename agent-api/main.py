import os, json, base64, time
import traceback
from pathlib import Path
from typing import List, Dict, Optional

from dotenv import load_dotenv
from fastapi import FastAPI, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

# LLMs (cliente único para Azure/OpenAI v1)
from openai import OpenAI, AzureOpenAI

# ===== bootstrap .env =====
env_path = (Path(__file__).resolve().parent / ".env")
if env_path.exists():
    load_dotenv(dotenv_path=env_path)

MODE = os.getenv("MODE", "unsafe").lower()
ALLOWED_ORIGINS = [o.strip() for o in os.getenv("ALLOWED_ORIGINS", "").split(",") if o.strip()]

# Azure OpenAI
AZURE_OPENAI_API_KEY = os.getenv("AZURE_OPENAI_API_KEY")
AZURE_OPENAI_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT")
AZURE_OPENAI_API_VERSION = os.getenv("AZURE_OPENAI_API_VERSION", "2024-05-01-preview")
AZURE_OPENAI_DEPLOYMENT_NAME = os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME")

# OpenAI “puro”
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

# ===== instancia cliente LLM disponível =====
llm_provider = "none"
client = None
model_name = None

if AZURE_OPENAI_ENDPOINT and AZURE_OPENAI_API_KEY:
    client = AzureOpenAI(
        api_key=AZURE_OPENAI_API_KEY,
        azure_endpoint=AZURE_OPENAI_ENDPOINT,
        api_version=AZURE_OPENAI_API_VERSION
    )
    model_name = AZURE_OPENAI_DEPLOYMENT_NAME
    llm_provider = "azure"
elif OPENAI_API_KEY:
    client = OpenAI(api_key=OPENAI_API_KEY)
    model_name = OPENAI_MODEL
    llm_provider = "openai"

# ===== app + CORS =====
app = FastAPI(title="Agente STRIDE — Análise de Arquiteturas")

origins = ALLOWED_ORIGINS or ["http://localhost:5173", "http://127.0.0.1:5173"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,   # ok se não usar '*'
    allow_methods=["*"],
    allow_headers=["*"],
)


# ===== helpers =====
def b64_of_upload(file: UploadFile) -> Optional[str]:
    if not file:
        return None
    data = file.file.read()
    file.file.seek(0)
    return base64.b64encode(data).decode("utf-8")

MITIGATIONS = {
    "Spoofing": [
        "MFA e política de senha", "Sessão segura (SameSite/HttpOnly/Secure)",
        "Assinatura/rotação de tokens", "mTLS/Device binding"
    ],
    "Tampering": [
        "Validação de entrada", "Assinatura/HMAC de payloads",
        "Integridade no CI/CD", "WAF/IDS"
    ],
    "Repudiation": [
        "Logs imutáveis/assinados", "Auditoria completa",
        "Correlação com identidade", "Sincronismo NTP"
    ],
    "Information Disclosure": [
        "TLS 1.2+ em trânsito", "Criptografia em repouso (KMS)",
        "Mascaramento/Tokenização de PII", "CORS restrito"
    ],
    "Denial of Service": [
        "Rate limit/cotas", "Timeouts/backpressure",
        "Circuit breaker", "Autoscaling + proteção upstream"
    ],
    "Elevation of Privilege": [
        "Menor privilégio (RBAC/IAM)", "Segregação de funções",
        "Revisão periódica de acessos", "Vault de segredos + rotação"
    ],
}

SYSTEM_MSG = (
    "Você é um engenheiro de segurança. Analise a arquitetura a partir do texto e da imagem "
    "usando STRIDE. Responda rigorosamente em JSON com os campos:\n"
    "{ 'ameacas': [ {'categoria':'Spoofing|Tampering|Repudiation|Information Disclosure|Denial of Service|Elevation of Privilege',"
    "  'titulo': str, 'descricao': str, 'ativos_afetados': [str]} ], 'observacoes': str }"
)

def analyze_with_llm(payload_text: str, img_b64: Optional[str]) -> Dict:
    if client is None:
        raise RuntimeError("LLM não configurado")

    user_content = [{"type": "text", "text": payload_text}]
    if img_b64:
        user_content.append({
            "type": "image_url",
            "image_url": {"url": f"data:image/png;base64,{img_b64}"}
        })

    resp = client.chat.completions.create(
        model=model_name,
        messages=[
            {"role": "system", "content": SYSTEM_MSG},
            {"role": "user",   "content": user_content},
        ],
        response_format={"type": "json_object"},
        temperature=0.2,
        max_tokens=900
    )
    return json.loads(resp.choices[0].message.content)


def analyze_with_rules(payload_text: str) -> Dict:
    t = payload_text.lower()
    a = []

    def add(cat, title, desc, assets):
        a.append({"categoria": cat, "titulo": title, "descricao": desc, "ativos_afetados": assets})

    if "web" in t or "http" in t:
        add("Spoofing", "Impersonação de usuário", "Risco de credenciais fracas/reutilizadas.", ["Frontend","App"])
        add("Repudiation", "Ação não rastreável", "Trilha de auditoria insuficiente.", ["App"])

    if "sql" in t or "dados" in t or "base" in t:
        add("Tampering", "Manipulação de dados", "Entrada sem validação pode alterar registros.", ["DB"])
        add("Information Disclosure", "Vazamento de PII", "Falta de criptografia/mascaramento.", ["DB","Relatórios"])

    if "internet" in t or "exposta" in t:
        add("Denial of Service", "Sobrecarga de requisições", "Falta de rate limit e proteção anti-bot.", ["Edge","App"])
        add("Elevation of Privilege", "Permissões amplas", "Papéis largos permitem abuso lateral.", ["IAM","App"])

    return {"ameacas": a, "observacoes": "Resultado heurístico (sem LLM)."}

def to_cytoscape(ameacas: List[Dict]) -> Dict:
    nodes, edges = [], []
    cats = sorted(set(a["categoria"] for a in ameacas))
    for c in cats:
        nodes.append({"data": {"id": f"cat::{c}", "label": c, "kind": "categoria"}})

    for i, a in enumerate(ameacas, 1):
        nid = f"threat::{i}"
        nodes.append({"data": {"id": nid, "label": a["titulo"], "categoria": a["categoria"], "kind": "ameaca"}})
        edges.append({"data": {"id": f"e::{nid}->{a['categoria']}", "source": nid, "target": f"cat::{a['categoria']}"}})
        for at in a.get("ativos_afetados", [])[:5]:
            aid = f"asset::{at}"
            if not any(n["data"]["id"] == aid for n in nodes):
                nodes.append({"data": {"id": aid, "label": at, "kind": "ativo"}})
            edges.append({"data": {"id": f"e::{aid}->{nid}", "source": aid, "target": nid}})
    return {"nodes": nodes, "edges": edges}

def attach_mitigations(ameacas: List[Dict]) -> List[Dict]:
    out = []
    for a in ameacas:
        a2 = dict(a)
        a2["mitigacoes"] = MITIGATIONS.get(a["categoria"], [])[:4]
        out.append(a2)
    return out

# ===== endpoints =====
@app.get("/healthz")
def healthz():
    return {"mode": MODE, "llm": llm_provider, "model": model_name}


@app.post("/analisar_ameacas/")
async def analisar_ameacas(
    imagem: UploadFile = File(None, description="PNG/JPG do diagrama"),
    tipo_aplicacao: str = Form(...),
    autenticacao: str = Form(...),
    acesso_internet: str = Form(...),
    dados_sensiveis: str = Form(...),
    descricao_aplicacao: str = Form(...),
    force_llm: Optional[str] = Form(None),   # <--- NOVO
):
    img_b64 = b64_of_upload(imagem) if imagem else None
    payload_text = (
        f"Tipo de aplicação: {tipo_aplicacao}\n"
        f"Autenticação: {autenticacao}\n"
        f"Exposição na Internet: {acesso_internet}\n"
        f"Dados sensíveis: {dados_sensiveis}\n"
        f"Descrição: {descricao_aplicacao}\n"
        f"(Se houver imagem, ela está anexada em base64.)"
    )

    use_llm = (client is not None) and (force_llm is not None or img_b64)

    try:
        if use_llm:
            raw = analyze_with_llm(payload_text, img_b64)
            provider = llm_provider
            obs = "LLM OK"
        else:
            raw = analyze_with_rules(payload_text)
            provider = "heuristico"
            obs = "Resultado heurístico (sem LLM)."
    except Exception as e:
        print("LLM ERROR:", e)
        print(traceback.format_exc())
        raw = analyze_with_rules(payload_text)
        provider = "heuristico"
        obs = "Falha no LLM, usando heurística."

    ameacas = attach_mitigations(raw.get("ameacas", []))
    graph = to_cytoscape(ameacas)

    return JSONResponse({
        "provider": provider,
        "observacoes": obs,
        "entrada": {
            "tipo_aplicacao": tipo_aplicacao,
            "autenticacao": autenticacao,
            "acesso_internet": acesso_internet,
            "dados_sensiveis": dados_sensiveis,
            "descricao_aplicacao": descricao_aplicacao,
            "imagem": bool(img_b64),
        },
        "resultado": {
            "ameacas": ameacas,
            "graph": graph
        }
    })
