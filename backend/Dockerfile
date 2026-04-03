# syntax=docker/dockerfile:1
FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends git openssh-client && rm -rf /var/lib/apt/lists/*

WORKDIR /app

ARG GH_TOKEN=""
RUN if [ -n "$GH_TOKEN" ]; then \
        git config --global url."https://x-access-token:${GH_TOKEN}@github.com/".insteadOf "https://github.com/"; \
    fi

COPY pyproject.toml ./

# Install deps — uses GH_TOKEN (HTTPS) when set, otherwise SSH mount for deploy key
RUN --mount=type=ssh \
    if [ -z "$GH_TOKEN" ]; then \
        mkdir -p ~/.ssh && ssh-keyscan github.com >> ~/.ssh/known_hosts 2>/dev/null && \
        git config --global url."git@github.com:".insteadOf "https://github.com/"; \
    fi && \
    pip install --no-cache-dir -e "."

COPY . .

EXPOSE 8001

CMD ["uvicorn", "src.local_server:app", "--host", "0.0.0.0", "--port", "8001"]
