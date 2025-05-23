# Use an official Python runtime as a parent image
FROM python:3.9-slim

# Set the working directory in the container
WORKDIR /app

# Copy the current directory contents into the container
COPY . /app

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Run tests (fail the build if any test fails)
RUN pytest --maxfail=1 --disable-warnings

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV TRANSLATION_API_KEY="e95db18b-6bd6-411e-b95c-b3699b12cad3"

# Expose the API port
EXPOSE 5090

# Command to run the Flask app
CMD ["python", "app.py"]
