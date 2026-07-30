# syntax=docker/dockerfile:1.7
#
# Two-stage Alpine build. The builder installs the dependencies and runs the
# test suite (a build gate that was previously in the single runtime stage);
# the runtime stage receives only the finished virtualenv and the app source,
# so pytest and the compilers never ship.
#
# Python raised 3.9 -> 3.13; 3.9 went end-of-life in October 2025.

# ---- Stage 1: build the virtualenv and gate on the tests ----
FROM python:3.13-alpine AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# build-base/libffi-dev/openssl-dev cover grpcio and the google-auth crypto
# stack in case a musllinux wheel is missing for the resolved version.
RUN apk add --no-cache build-base libffi-dev openssl-dev

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

WORKDIR /build

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Run tests (fail the build if any test fails)
COPY . .
RUN pytest --maxfail=1 --disable-warnings

# ---- Stage 2: runtime ----
FROM python:3.13-alpine

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV TRANSLATION_API_KEY="e95db18b-6bd6-411e-b95c-b3699b12cad3"
ENV PYTHONDONTWRITEBYTECODE=1 \
    PATH="/opt/venv/bin:$PATH"

RUN apk add --no-cache libffi openssl libstdc++

# Set the working directory in the container
WORKDIR /app

COPY --from=builder /opt/venv /opt/venv

# Copy the current directory contents into the container
COPY . /app

RUN addgroup -g 1000 -S appuser \
    && adduser -u 1000 -S -G appuser -H -s /sbin/nologin appuser \
    && mkdir -p /data \
    && chown -R appuser:appuser /app /data

USER 1000:1000

# Expose the API port
EXPOSE 5090

# Command to run the Flask app
CMD ["python", "app.py"]
