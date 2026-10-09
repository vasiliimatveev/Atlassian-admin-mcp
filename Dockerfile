FROM python:3.13-slim AS build
COPY --from=ghcr.io/astral-sh/uv:0.12.18 /uv /usr/local/bin/uv
WORKDIR /app
COPY pyproject.toml uv.lock README.md LICENSE ./
COPY src ./src
RUN uv build --wheel --out-dir /dist

FROM python:3.13-slim
COPY --from=build /dist/*.whl /tmp/
RUN pip install --no-cache-dir /tmp/*.whl && rm /tmp/*.whl \
    && useradd --create-home --uid 10001 mcp
USER mcp
ENTRYPOINT ["atlassian-admin-mcp"]
