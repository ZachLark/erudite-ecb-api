#!/bin/bash

# Set PYTHONPATH to include project root
export PYTHONPATH=$(pwd)

# Activate virtual environment if it exists
if [ -d "venv" ]; then
    source venv/bin/activate
fi

# Run tests with tox
tox -e py3

# Run integration tests separately
pytest tests/integration -v --cov=scripts/redis_queue --cov-report=html 