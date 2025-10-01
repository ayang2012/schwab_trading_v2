"""Environment configuration to prevent accidental production data modification."""

import os
from pathlib import Path
from typing import Optional


class EnvironmentConfig:
    """Configuration to manage test vs production environments."""
    
    @staticmethod
    def is_test_environment() -> bool:
        """Check if we're in a test environment."""
        # Check for pytest running
        if 'pytest' in os.environ.get('_', ''):
            return True
            
        # Check for test environment variable
        if os.environ.get('SCHWAB_TEST_MODE', '').lower() in ('1', 'true', 'yes'):
            return True
            
        # Check if called from test files
        import inspect
        frame = inspect.currentframe()
        while frame:
            filename = frame.f_code.co_filename
            if 'test_' in Path(filename).name or '/tests/' in filename:
                return True
            frame = frame.f_back
            
        return False
    
    @staticmethod
    def get_safe_db_path(requested_path: str) -> str:
        """Get a safe database path that prevents production data modification."""
        if EnvironmentConfig.is_test_environment():
            # In test environment, always use temp databases
            if 'assignments.db' in requested_path and not requested_path.startswith('/tmp'):
                return f"/tmp/test_{Path(requested_path).name}"
        
        return requested_path
    
    @staticmethod
    def require_test_environment(operation: str):
        """Require test environment for potentially dangerous operations."""
        if not EnvironmentConfig.is_test_environment():
            raise RuntimeError(
                f"Operation '{operation}' requires test environment. "
                f"Set SCHWAB_TEST_MODE=1 or run via pytest."
            )
    
    @staticmethod
    def get_production_db_path() -> str:
        """Get the production database path."""
        return "data/assignments.db"
    
    @staticmethod
    def warn_if_production():
        """Warn if we're in production environment."""
        if not EnvironmentConfig.is_test_environment():
            print("⚠️  WARNING: Running in PRODUCTION mode!")
            print("   Your real assignment data may be affected.")
            print("   Set SCHWAB_TEST_MODE=1 for safe testing.")
    
    @staticmethod
    def confirm_production_operation(operation: str) -> bool:
        """Ask for confirmation before production operations."""
        if EnvironmentConfig.is_test_environment():
            return True
            
        print(f"🚨 PRODUCTION OPERATION: {operation}")
        print("   This will modify your real assignment data!")
        response = input("   Type 'yes' to continue: ").lower()
        return response == 'yes'


def safe_db_operation(func):
    """Decorator to make database operations safer."""
    def wrapper(*args, **kwargs):
        # Check if we're about to modify production data
        if hasattr(args[0], 'db_path') and 'assignments.db' in str(args[0].db_path):
            if not EnvironmentConfig.is_test_environment():
                operation = func.__name__
                if not EnvironmentConfig.confirm_production_operation(operation):
                    print("❌ Operation cancelled for safety.")
                    return None
        
        return func(*args, **kwargs)
    return wrapper


if __name__ == "__main__":
    # Test the environment detection
    print("🔍 Environment Detection Test")
    print("=" * 40)
    print(f"Is test environment: {EnvironmentConfig.is_test_environment()}")
    print(f"Safe DB path: {EnvironmentConfig.get_safe_db_path('data/assignments.db')}")
    
    EnvironmentConfig.warn_if_production()
    
    # Test production confirmation
    if EnvironmentConfig.confirm_production_operation("test operation"):
        print("✅ Operation would proceed")
    else:
        print("❌ Operation cancelled")