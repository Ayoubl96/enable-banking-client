"""Enable Banking Python Client

A comprehensive Python client for Enable Banking API that provides:
- JWT token generation using PEM private key
- Session management without database (in-memory)
- Support for multiple bank connections simultaneously
- FastAPI wrapper for external consumption
"""

__version__ = "0.1.0"
__author__ = "Enable Banking Client Team"
__email__ = "support@enablebanking.com"

from enable_banking.config.logging import setup_logging, get_logger

__all__ = ["setup_logging", "get_logger", "__version__"]