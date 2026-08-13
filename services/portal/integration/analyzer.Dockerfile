FROM python:3.12-slim
WORKDIR /app
RUN pip install --no-cache-dir scikit-learn==1.8.0 pandas==2.3.3 numpy==2.3.5 redis==5.0.0 joblib==1.5.2
COPY log-analyser/requirements.txt ./original-requirements.txt
COPY log-analyser/src ./src
COPY log-analyser/models ./models
CMD ["python", "-u", "src/main.py"]
