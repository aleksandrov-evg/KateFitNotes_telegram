FROM ghcr.io/astral-sh/uv:python3.14-bookworm-slim
WORKDIR /usr/src/bot
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project
COPY bot.py sql.py ./
COPY src/ ./src/
ENV PATH="/usr/src/bot/.venv/bin:$PATH"
CMD ["python3", "bot.py"]
