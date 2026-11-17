"""
Vercel Serverless Function Entry Point for Groww Facts Assistant.
Routes all web and API traffic through StandaloneUIHandler.
"""

import sys
from pathlib import Path

# Ensure project root is in sys.path
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ui.server import StandaloneUIHandler

class handler(StandaloneUIHandler):
    """Vercel Python runtime handler."""
    pass
