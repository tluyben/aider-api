FROM python:3.9-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    git \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .
# Install requirements with --upgrade to ensure latest aider-chat
RUN pip install --no-cache-dir --upgrade -r requirements.txt

# Upgrade aider-chat again separately to ensure latest version
RUN pip install --no-cache-dir --upgrade aider-chat

# Copy application code
COPY . .

# Expose the application port
EXPOSE 8000

# Run the application
CMD ["uvicorn", "aider_api:app", "--host", "0.0.0.0", "--port", "8000"]
