#!/usr/bin/env python3
"""
GitBridgev1 - Main Application Entry Point.

This module serves as the main entry point for the GitBridge application,
implementing the MAS Lite Protocol v2.1 for agent collaboration and task management.
"""

import os
import logging
from pathlib import Path
from flask import Flask, render_template
from flask_socketio import SocketIO
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/gitbridge.log'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__, 
    template_folder='webui/templates',
    static_folder='webui/static'
)
app.config['SECRET_KEY'] = os.environ.get('FLASK_SECRET_KEY', 'dev_key_replace_in_prod')
socketio = SocketIO(app)

# Create required directories
Path('logs').mkdir(exist_ok=True)
Path('messages').mkdir(exist_ok=True)

# Import routes after app initialization
from webui.routes import *
from agent.routes import *
from mas_core.routes import *

@app.route('/')
def index():
    """Render main dashboard."""
    return render_template('dashboard.html')

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    socketio.run(app, host='0.0.0.0', port=port, debug=False) 