import sys
import os

# Add the project directory to the Python path
path = '/home/syedzeewaqarhussain/crypto_hft_tool'
if path not in sys.path:
    sys.path.append(path)

# Set environment variables
os.environ['PYTHONPATH'] = path

# Import the FastAPI app
from src.crypto_hft_tool.main import app

# For WSGI servers that don't support ASGI
from fastapi.middleware.wsgi import WSGIMiddleware
application = WSGIMiddleware(app) 