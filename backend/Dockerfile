FROM python:3.11-slim

WORKDIR /app

# Install dependencies first (better Docker layer caching -
# this layer only rebuilds when requirements.txt changes, not on every code edit)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Now copy the actual application code
COPY . .

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
