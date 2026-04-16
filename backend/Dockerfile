FROM python:3.11-slim

WORKDIR /app

# Instala dependências do sistema (necessárias para alguns pacotes Python)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copia e instala dependências Python primeiro (cache de Docker layer)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copia o código da aplicação
COPY . .

# Porta da API
EXPOSE 8000

# Comando padrão: roda o servidor FastAPI
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
