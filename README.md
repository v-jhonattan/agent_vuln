# Agente STRIDE — Análise de Arquiteturas (FastAPI + Cytoscape)

Assistente que analisa arquiteturas (com ou sem imagem do diagrama) e gera:

- Lista de ameaças STRIDE com mitigações sugeridas.

- Grafo interativo (Cytoscape) ligando Ativos ⇄ Ameaças ⇄ Categorias.


# ✨ Funcionalidades

- Entrada textual (tipo de app, autenticação, dados sensíveis etc.)

- Entrada de imagem (diagrama/arquitetura)

- Modo Heurístico (sem LLM) — funciona offline.

- Modo LLM (OpenAI ou Azure OpenAI) — raciocínio mais rico.

- Frontend estático (HTML/JS) com Cytoscape.

# 🧱 Stack

- FastAPI (backend, /analisar_ameacas/, /healthz)

- Cytoscape.js (grafo)

- HTML + fetch (frontend simples)

# ⚙️ Requisitos

- Python 3.10+

- Navegador recente (Firefox/Chrome)

- (Opcional) Chave OpenAI ou Azure OpenAI para modo LLM

# 🚀 Como rodar (dev)

Backend

    cd agent-api
    python -m venv .venv && source .venv/bin/activate
    pip install -r requirements.txt

    cp .env.example .env
    
    # ajuste CORS do front
    echo 'ALLOWED_ORIGINS=http://localhost:5173,http://127.0.0.1:5173' >> .env

    uvicorn main:app --reload --port 8000

Frontend

    cd frontend
    python -m http.server 5173
    # abra http://localhost:5173


Verificação

    curl http://127.0.0.1:8000/healthz
    # esperado (modo heurístico): {"mode":"unsafe","llm":"none","model":null}


# 🤖 (Opcional) Ativar LLM

## OpenAI

Adicione no agent-api/.env:

    OPENAI_API_KEY=sk-xxxx
    OPENAI_MODEL=gpt-4o-mini

Reinicie o backend e confira:

    curl http://127.0.0.1:8000/healthz
    # {"mode":"unsafe","llm":"openai","model":"gpt-4o-mini"}

# Azure OpenAI

    AZURE_OPENAI_API_KEY=...
    AZURE_OPENAI_ENDPOINT=https://SEU-RECURSO.openai.azure.com/
    AZURE_OPENAI_API_VERSION=2024-05-01-preview
    AZURE_OPENAI_DEPLOYMENT_NAME=gpt-4o-mini

# 📡 API
## GET /healthz

Status e provedor LLM.

    curl http://127.0.0.1:8000/healthz


POST /analisar_ameacas/

- Form fields:
tipo_aplicacao, autenticacao, acesso_internet, dados_sensiveis, descricao_aplicacao, imagem (opcional)

Exemplo (sem imagem)

    curl -s -X POST http://127.0.0.1:8000/analisar_ameacas/ \
      -F 'tipo_aplicacao=Web' \
      -F 'autenticacao=Entra ID' \
      -F 'acesso_internet=Sim' \
      -F 'dados_sensiveis=Sim' \
      -F 'descricao_aplicacao=App para salvar contratos em SQL' | jq .

Exemplo (com imagem)

    curl -s -X POST http://127.0.0.1:8000/analisar_ameacas/ \
      -F 'imagem=@images/exemplo-diagrama.png' \
      -F 'tipo_aplicacao=Web' \
      -F 'autenticacao=Entra ID' \
      -F 'acesso_internet=Sim' \
      -F 'dados_sensiveis=Sim' \
      -F 'descricao_aplicacao=App jurídica SQL' | jq .

# 🌐 CORS (se der erro no navegador)

No .env do backend:

    ALLOWED_ORIGINS=http://localhost:5173,http://127.0.0.1:5173


Teste:

    curl -i -H "Origin: http://localhost:5173" http://127.0.0.1:8000/healthz | grep -i access-control-allow-origin
    curl -i -X OPTIONS http://127.0.0.1:8000/analisar_ameacas/ \
      -H "Origin: http://localhost:5173" \
      -H "Access-Control-Request-Method: POST" | grep -Ei "allow-(origin|methods|headers)"


## 📸 Demonstração rápida

| Formulário | Grafo |
| --- | --- |
| ![Form](imagens/01-front-form.png) | ![Graph](imagens/02-front-graph.png) |

| CORS OK | cURL (heurístico) |
| --- | --- |
| ![CORS](imagens/05-network-ok.png) | ![cURL](imagens/06-curl-sem-imagem.png) |


# 🖼️ Frontend (uso)

1. Abra http://localhost:5173

2. Preencha o formulário (opcional: envie imagem do diagrama)

3. Clique Analisar → veja o JSON e o grafo STRIDE


# 📁 Estrutura

    vuln-arch-agent/
    ├─ agent-api/
    │  ├─ main.py
    │  ├─ requirements.txt
    │  ├─ .env.example  → copie para .env
    │  └─ ...
    ├─ frontend/
    │  └─ index.html
    ├─ images/
    │  ├─ 01-front-form.png
    │  ├─ 02-front-graph.png
    │  ├─ 03-healthz-heuristico.png
    │  ├─ 04-healthz-llm.png
    │  ├─ 06-curl-sem-imagem.png
    │  ├─ 07-curl-com-imagem.png
    │  └─ 08-cors-ok.png
    └─ README.md

# 🔐 Aviso/Ética

- Projeto educacional. Não use para avaliar sistemas de terceiros sem autorização.

- Dados sensíveis: proteja chaves .env e não faça commit de segredos.
