# Zeabur 优化的 Dockerfile
# 使用更轻量的基础镜像和简化的 Chrome 安装

FROM python:3.11-slim

# 设置工作目录
WORKDIR /app

# 安装系统依赖和 Chrome（使用官方脚本）
RUN apt-get update && apt-get install -y \
    wget \
    gnupg \
    ca-certificates \
    fonts-liberation \
    libappindicator3-1 \
    libasound2 \
    libatk-bridge2.0-0 \
    libatk1.0-0 \
    libcups2 \
    libdbus-1-3 \
    libdrm2 \
    libgbm1 \
    libgtk-3-0 \
    libnspr4 \
    libnss3 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxkbcommon0 \
    libxrandr2 \
    xdg-utils \
    fonts-wqy-zenhei \
    && rm -rf /var/lib/apt/lists/*

# 使用 Google 的官方安装脚本安装 Chrome
RUN wget -q -O - https://dl-ssl.google.com/linux/linux_signing_key.pub | gpg --dearmor -o /usr/share/keyrings/googlechrome-linux-keyring.gpg \
    && sh -c 'echo "deb [arch=amd64 signed-by=/usr/share/keyrings/googlechrome-linux-keyring.gpg] http://dl.google.com/linux/chrome/deb/ stable main" >> /etc/apt/sources.list.d/google-chrome.list' \
    && apt-get update \
    && apt-get install -y google-chrome-stable \
    && rm -rf /var/lib/apt/lists/* /etc/apt/sources.list.d/google-chrome.list

# 复制依赖文件
COPY requirements.txt .

# 安装 Python 依赖
RUN pip install --no-cache-dir -r requirements.txt

# 复制应用代码
COPY app.py .

# 设置环境变量
ENV PYTHONUNBUFFERED=1
ENV PORT=5000

# 暴露端口
EXPOSE 5000

# 启动命令 - 使用更少的 worker 和更多超时时间
CMD ["gunicorn", "app:app", "--bind", "0.0.0.0:5000", "--workers", "1", "--threads", "1", "--timeout", "180", "--graceful-timeout", "30", "--keepalive", "5"]
