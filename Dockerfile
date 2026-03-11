# Use an official Python runtime as a parent image, slim version for faster builds
FROM python:3.11-slim

# Set the working directory in the container
WORKDIR /app

# Copy just the requirements.txt first to leverage Docker cache
COPY requirements.txt .

# Install dependencies (no-cache-dir reduces image size)
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code
COPY . .

# Run main.py when the container launches
CMD ["python", "main.py"]
