# Use Python slim image
FROM python:3.11

# Set working directory
WORKDIR /app

# Install system packages needed to build Python packages
RUN apt-get update && apt-get install -y \
    build-essential \
    gcc \
    libffi-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and upgrade pip
COPY requirements.txt .
RUN python -m pip install --upgrade pip setuptools wheel
RUN pip install --no-cache-dir flask==3.0.3
RUN pip install --no-cache-dir prometheus_client

# Copy the rest of the app
COPY . .

# Expose Flask port
EXPOSE 5000

# Run Flask app
CMD ["python", "app.py"]