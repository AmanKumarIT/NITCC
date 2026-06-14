"""
NITCC Shared Backend Library
Installed as an editable package by all agent microservices.
"""

from setuptools import setup, find_packages

setup(
    name="nitcc-shared",
    version="1.0.0",
    packages=find_packages(),
    install_requires=[
        "fastapi>=0.109.0",
        "uvicorn[standard]>=0.27.0",
        "pydantic>=2.5.0",
        "pydantic-settings>=2.1.0",
        "motor>=3.3.0",          # Async MongoDB driver
        "redis[hiredis]>=5.0.0", # Async Redis
        "aiokafka>=0.10.0",      # Async Kafka client
        "confluent-kafka>=2.3.0",# Confluent Kafka (Avro support)
        "fastavro>=1.9.0",       # Avro serialization
        "requests-cache>=1.1.0",
        "httpx>=0.26.0",
        "python-jose[cryptography]>=3.3.0",  # JWT
        "passlib[bcrypt]>=1.7.4",
        "pyotp>=2.9.0",          # TOTP MFA
        "python-multipart>=0.0.7",
        "structlog>=24.1.0",     # Structured logging
        "prometheus-client>=0.19.0",
        "opentelemetry-api>=1.22.0",
        "opentelemetry-sdk>=1.22.0",
        "opentelemetry-exporter-otlp>=1.22.0",
        "slowapi>=0.1.9",        # Rate limiting
        "python-dotenv>=1.0.0",
    ],
)
