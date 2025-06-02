# GitBridgev1

GitBridge is a Human-AI Collaboration System for managing and verifying the lifecycle of AI-generated tasks using a Modular Agent System (MAS). It includes task consensus tracking, error logging, task delegation, real-time UI, and smart agent routing.

## Features

- ✅ MAS Logging System (MAS Lite Protocol v2.1)
- ✅ Task Chain Generation + Summarization
- ✅ Full Pytest Coverage (unit, integration, performance)
- ✅ Web UI Dashboard (real-time updates, filters, analytics)
- ✅ Agent Framework with Dynamic Routing and Delegation
- ✅ CLI Support + API Integration Ready

## Directory Structure

```
/GitBridgev1
├── agent/                  # Delegation engine & logic
│   └── framework/         # Core agent framework components
├── mas_core/              # Logging, status, consensus tools
├── tests/                 # All test suites
│   ├── unit/             # Unit tests
│   ├── integration/      # Integration tests
│   └── performance/      # Performance benchmarks
├── webui/                 # Flask-based UI components
│   ├── templates/        # Jinja2 templates
│   └── static/           # CSS, JS, and assets
├── docs/                  # Protocol and API documentation
├── archive/              # Deprecated or v0.x scripts
├── outputs/              # Task outputs and artifacts
├── logbook/              # System event logs
├── app.py                # Flask app entrypoint
├── requirements.txt      # Python dependencies
└── pytest.ini           # Test configuration
```

## Requirements

- Python 3.13.3+
- Flask 3.0.2
- See requirements.txt for full dependency list

## Quick Start

1. Create and activate a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Run the application:
   ```bash
   python app.py
   ```

4. Visit http://localhost:5000 in your browser

## Testing

Run the test suite:
```bash
pytest
```

For specific test categories:
```bash
pytest -m unit          # Unit tests only
pytest -m integration   # Integration tests
pytest -m performance   # Performance tests
```

## License

Copyright © 2025 