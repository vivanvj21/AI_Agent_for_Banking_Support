FROM python:3.12-slim

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p db knowledge_base/chroma_store logs

EXPOSE 8501

# Default to the Streamlit UI; runtime startup validation initializes SQLite
# and Chroma idempotently, including when db/ and chroma_store/ are mounted.
CMD ["streamlit", "run", "app_streamlit.py", "--server.port=8501", "--server.address=0.0.0.0"]
