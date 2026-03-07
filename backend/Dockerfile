FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends git && rm -rf /var/lib/apt/lists/*

WORKDIR /app

ARG GH_TOKEN=""
RUN if [ -n "$GH_TOKEN" ]; then \
        git config --global url."https://x-access-token:${GH_TOKEN}@github.com/".insteadOf "https://github.com/"; \
    fi

COPY pyproject.toml ./
RUN pip install --no-cache-dir -e "."

COPY . .

EXPOSE 8001

CMD ["uvicorn", "src.local_server:app", "--host", "0.0.0.0", "--port", "8001"]
