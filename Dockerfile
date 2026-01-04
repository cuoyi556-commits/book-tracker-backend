# Zeabur 优化的 Dockerfile（超轻量级）
# 版本: 2.1 - 添加图片代理功能
FROM python:3.12-alpine

# 设置工作目录
WORKDIR /app

# 复制依赖文件
COPY requirements.txt .

# 安装 Python 依赖（使用 Alpine 的包管理器安装依赖）
RUN apk add --no-cache gcc musl-dev libffi-dev openssl-dev && \
    pip install --no-cache-dir --break-system-packages -r requirements.txt && \
    apk del gcc musl-dev libffi-dev openssl-dev

# 复制应用代码
COPY app.py .

# 设置环境变量
ENV PYTHONUNBUFFERED=1
ENV PORT=8080

# 暴露端口
EXPOSE 8080

# 启动命令（减少 worker 数量以节省内存）
CMD ["gunicorn", "app:app", "--bind", "0.0.0.0:8080", "--workers", "1", "--threads", "2", "--timeout", "60"]
