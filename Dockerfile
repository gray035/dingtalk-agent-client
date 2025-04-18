# 使用 Debian 作为基础镜像
FROM debian:bullseye-slim

# 设置工作目录
WORKDIR /app

# 设置环境变量
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple

# 安装 Python 和系统依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 \
    python3-pip \
    python3-dev \
    gcc \
    && rm -rf /var/lib/apt/lists/* \
    && ln -s /usr/bin/python3 /usr/bin/python

# 复制项目文件
COPY requirements.txt .
COPY . .

# 安装 Python 依赖
RUN pip3 install --no-cache-dir -r requirements.txt

# 创建必要的目录
RUN mkdir -p static/resource

# 暴露端口
EXPOSE 8000

# 设置启动命令
CMD ["python", "-m", "app.core.mcp_server"] 