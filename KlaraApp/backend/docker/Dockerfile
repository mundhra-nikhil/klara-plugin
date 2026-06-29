FROM python:3.12-slim

WORKDIR /app

# Install system dependencies.
# libreoffice-writer (headless) + poppler-utils render .docx → PDF → page images
# so the vision model can evaluate rendered-layout rules (margins, line numbers,
# page numbering, widows/orphans, footnote flow). fonts-liberation gives Times-
# equivalent metrics so rendered pleadings look right.
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libpq-dev libreoffice-writer poppler-utils fonts-liberation && \
    rm -rf /var/lib/apt/lists/*

COPY docker/docker-requirements.txt requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
