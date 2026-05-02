# 1. Use a lightweight Python base image
FROM python:3.11-slim

# 2. Set the working directory inside the container
WORKDIR /app

# 3. Install necessary Linux build tools for ML libraries
RUN apt-get update && apt-get install -y \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# 4. Copy the requirements file first (for Docker caching)
COPY requirements.txt .

# 5. Upgrade pip and Install dependencies with a massive timeout limit
RUN pip install --upgrade pip && \
    pip install --default-timeout=2000 --no-cache-dir -r requirements.txt

# 6. Copy the rest of your application code into the container
COPY . .

# 7. Expose Port 8501 for the Streamlit web interface
EXPOSE 8501

# 8. Command to run the application
CMD ["streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0"]