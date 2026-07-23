FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libpq-dev curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Pre-download ML models at build time so workers start instantly
RUN python -c "\
from sentence_transformers import SentenceTransformer; \
SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2'); \
print('Embedding model cached.')"

RUN python -c "\
from transformers import pipeline; \
pipeline('sentiment-analysis', model='cardiffnlp/twitter-xlm-roberta-base-sentiment', truncation=True, max_length=512); \
print('Sentiment model cached.')"

COPY . .
RUN chmod +x start.sh

CMD ["./start.sh"]
