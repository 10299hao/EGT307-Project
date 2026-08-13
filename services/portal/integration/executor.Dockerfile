# Ethan's source is copied unchanged; this Portal-owned wrapper fixes the
# case-sensitive Requirements.txt path in his uploaded Dockerfile.
FROM python:3.11-slim
WORKDIR /app
COPY executor/Requirements.txt ./Requirements.txt
RUN pip install --no-cache-dir -r Requirements.txt
COPY executor/src ./src
CMD ["python", "-u", "src/main.py"]
