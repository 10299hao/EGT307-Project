FROM python:3.12-slim
WORKDIR /app
RUN pip install --no-cache-dir redis==6.2.0
COPY bridge.py ./bridge.py
USER 65534
CMD ["python", "bridge.py"]
