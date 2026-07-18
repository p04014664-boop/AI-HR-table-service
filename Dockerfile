FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY *.py ./
RUN mkdir -p data

# 密钥不进镜像，运行时用 --env-file .env 传入
CMD ["python", "main.py"]
