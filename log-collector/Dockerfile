FROM python:3.12-slim

WORKDIR /app

COPY log-collector/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY log-collector/src ./src

COPY data/EVENTID_MEANING.csv ./data/EVENTID_MEANING.csv

ENV MEANING_PATH=/app/data/EVENTID_MEANING.csv

EXPOSE 8080

CMD ["python", "src/main.py"]