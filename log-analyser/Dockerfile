# 1. Use an official, lightweight Python image
FROM python:3.10-slim

# 2. Set the working directory inside the container
WORKDIR /app
ENV PYTHONUNBUFFERED=1
# 3. Copy the requirements file and install the libraries
# We do this BEFORE copying the rest of the code to save build time!
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 4. Copy the entire log-analyser folder into the container
# This automatically includes the src/ folder and the models/ folder
COPY . .

# 5. Tell the container what script to run when it wakes up
CMD ["python", "src/main.py"]