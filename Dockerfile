FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    openssh-client \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY kubepulse/ ./kubepulse/
COPY templates/ ./templates/
COPY run.py .

EXPOSE 7890

CMD ["python", "run.py", "--host", "0.0.0.0", "--port", "7890", "--no-browser"]
