FROM python:3.10-slim

WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application
COPY . .

# Set environment variables
ENV PYTHONUNBUFFERED=1

# Make sure the startup script is executable
RUN chmod +x /app/startup.sh

# Run the startup script
CMD ["/app/startup.sh"]
