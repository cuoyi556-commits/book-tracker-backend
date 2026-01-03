# Zeabur 优化的 Dockerfile（轻量级，无需 Chrome）
FROM python:3.11-slim

# 设置工作目录
WORKDIR /app

# 复制依赖文件
COPY requirements.txt .

# 安装 Python 依赖
RUN pip install --no-cache-dir -r requirements.txt

# 复制应用代码
COPY app.py .

# 设置环境变量
ENV PYTHONUNBUFFERED=1
ENV PORT=8080

# 暴露端口
EXPOSE 8080

# 启动命令
CMD ["gunicorn", "app:app", "--bind", "0.0.0.0:8080", "--workers", "2", "--threads", "4", "--timeout", "60"]
