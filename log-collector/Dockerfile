FROM python:3.12-slim

WORKDIR /app

COPY log-collector/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY log-collector/src ./src

COPY data/demonstration_traces.csv ./data/demonstration_traces.csv
COPY data/EVENTID_MEANING.csv ./data/EVENTID_MEANING.csv

# Tell main.py where these files actually live inside this image,
# since /app/src + '../../data' would resolve outside /app.
ENV CSV_PATH=/app/data/demonstration_traces.csv
ENV MEANING_PATH=/app/data/EVENTID_MEANING.csv

EXPOSE 8080

CMD ["python", "src/main.py"]