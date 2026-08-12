FROM python:3.12-slim

WORKDIR /app

COPY log-collector/requirements.txt /app/log-collector/requirements.txt

RUN pip install --no-cache-dir -r /app/log-collector/requirements.txt

COPY log-collector/src /app/log-collector/src

COPY data /app/data

EXPOSE 8080

CMD ["python", "/app/log-collector/src/main.py"]