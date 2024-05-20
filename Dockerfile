FROM --platform=linux/amd64 python:3.12-slim

WORKDIR /app

COPY requirements.txt /app

RUN pip install --no-cache-dir -r requirements.txt

COPY . /app

CMD ["python3", "-u", "main.py"]