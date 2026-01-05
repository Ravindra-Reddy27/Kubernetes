# Use Alpine for a lightweight image 
FROM python:3.9-alpine

# Install system dependencies for psycopg2 (Postgres adapter)
RUN apk add --no-cache postgresql-libs && \
    apk add --no-cache --virtual .build-deps gcc musl-dev postgresql-dev

# Set work directory
WORKDIR /app

# Copy requirements and install dependencies
COPY src/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt && \
    apk del .build-deps

# Copy application source code [cite: 13]
COPY src/ .

# Expose the port the app runs on
EXPOSE 5000

# Command to run the application
CMD ["python", "app.py"]