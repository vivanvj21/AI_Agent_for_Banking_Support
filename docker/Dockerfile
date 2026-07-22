FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Seed the demo database and FAQ vector index at build time so the container
# is immediately usable without a separate init step.
RUN python db/seed_synthetic_data.py && \
    python -c "from tools.faq_search import build_index; build_index()"

EXPOSE 8501

# Default to the Streamlit UI; override CMD to run cli.py for console mode.
CMD ["streamlit", "run", "app_streamlit.py", "--server.port=8501", "--server.address=0.0.0.0"]
