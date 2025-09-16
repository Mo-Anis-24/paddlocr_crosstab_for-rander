#!/usr/bin/env python3
"""
Startup script for Invoice OCR API
"""

import os
import sys
from app import create_app

def main():
    """Main entry point for the API server."""
    # Set default environment
    if not os.environ.get('FLASK_ENV'):
        os.environ['FLASK_ENV'] = 'development'
    
    # Create application
    app = create_app()
    
    # Get configuration
    port = int(os.environ.get('PORT', 5000))
    host = os.environ.get('HOST', '0.0.0.0')
    debug = os.environ.get('FLASK_DEBUG', '1') == '1'
    
    print(f"Starting Invoice OCR API on {host}:{port}")
    print(f"Environment: {os.environ.get('FLASK_ENV', 'development')}")
    print(f"Debug mode: {debug}")
    print(f"API Documentation: http://{host}:{port}/apidocs")
    print(f"Health Check: http://{host}:{port}/api/v1/health")
    
    # Run application
    app.run(host=host, port=port, debug=debug)

if __name__ == '__main__':
    main()
