# ================================
# 阶段一：构建前端
# ================================
FROM node:20-slim AS frontend-builder

WORKDIR /build

# 复制前端依赖文件并安装
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm ci --registry=https://registry.npmmirror.com

# 复制前端代码并构建
COPY frontend/ ./

RUN VITE_API_BASE_URL="" npm run build


# ================================
# 阶段二：构建最终镜像
# ================================
FROM python:3.10-slim

WORKDIR /app

# 安装后端构建与健康检查依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc curl \
    && rm -rf /var/lib/apt/lists/*

# 安装 uv 包管理器
RUN pip install --no-cache-dir uv -i https://mirrors.aliyun.com/pypi/simple/

# 复制后端依赖并使用 uv 安装
COPY backend/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt -i https://mirrors.aliyun.com/pypi/simple/

# 安装 gunicorn + uvicorn worker
RUN uv pip install --system --no-cache gunicorn "uvicorn[standard]" -i https://mirrors.aliyun.com/pypi/simple/

# 复制后端代码
COPY backend/ ./backend/

# 从阶段一复制前端构建产物
COPY --from=frontend-builder /build/dist ./frontend/dist

# 复制启动脚本
COPY start.sh ./start.sh
RUN sed -i 's/\r$//' ./start.sh && chmod +x ./start.sh \
    && useradd --create-home --uid 10001 journeyops \
    && mkdir -p /app/backend/data /app/.cache/uv \
    && chown -R journeyops:journeyops /app

ENV UV_CACHE_DIR=/app/.cache/uv
USER journeyops

# Keep the optional legacy AMap MCP executable available without a root-owned runtime cache.
RUN uvx amap-mcp-server --help >/dev/null 2>&1 || true

# 魔搭创空间要求端口 7860
EXPOSE 7860

CMD ["./start.sh"]
