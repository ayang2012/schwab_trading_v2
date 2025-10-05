"""Option trading strategies package.

This package provides specialized modules for different option strategies:
- put_selection: Cash secured put selection and analysis

Each module focuses on the specific requirements and analysis for that option type.
"""

from .put_selection import PutSelectionEngine

__all__ = ['PutSelectionEngine']