FROM --platform=linux/amd64 python:3.12-slim

ENV PYTHONUNBUFFERED True

WORKDIR /app

COPY requirements.txt /app

RUN pip install --no-cache-dir --upgrade pip -r requirements.txt

COPY . /app

# CMD exec gunicorn --bind :$PORT --workers 1 --threads 8 --timeout 0 main:app
CMD ["python3", "-u", "main.py"]