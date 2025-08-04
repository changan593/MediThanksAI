FROM python:3.10.16-alpine3.20

# 设置工作目录
WORKDIR /app

# 设置环境变量
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1


# 复制项目文件
COPY requirements.txt .
COPY main.py .
COPY prompts.xlsx .
COPY static/ static/
COPY templates/ templates/

# 安装 Python 依赖
RUN pip install --no-cache-dir -r requirements.txt

# 暴露端口
EXPOSE 8000

# 启动命令
CMD ["python", "main.py"]