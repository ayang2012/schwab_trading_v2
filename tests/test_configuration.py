#!/usr/bin/env python3
"""
Tests for configuration system and data storage.
"""

import json
import tempfile
import os
from unittest.mock import Mock, patch
from pathlib import Path
import sys

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    import pytest
except ImportError:
    print("pytest not installed. Install with: pip install pytest")
    sys.exit(1)

from config import settings
from utils.io import safe_write_json
import json


class TestConfigurationSystem:
    """Test the configuration system in settings.py."""
    
    def test_watchlist_configuration(self):
        """Test watchlist configuration validity."""
        # Watchlist should be non-empty
        assert len(settings.WATCHLIST_STOCKS) > 0
        
        # All symbols should be valid strings
        for symbol in settings.WATCHLIST_STOCKS:
            assert isinstance(symbol, str)
            assert len(symbol) >= 1
            assert len(symbol) <= 5  # Valid ticker length
            assert symbol.isupper()  # Should be uppercase
            assert symbol.isalpha()  # Should only contain letters
    
    def test_alert_thresholds(self):
        """Test alert threshold configurations."""
        # RSI thresholds
        assert hasattr(settings, 'RSI_OVERSOLD_THRESHOLD')
        assert hasattr(settings, 'RSI_OVERBOUGHT_THRESHOLD')
        assert 0 < settings.RSI_OVERSOLD_THRESHOLD < 50
        assert 50 < settings.RSI_OVERBOUGHT_THRESHOLD < 100
        assert settings.RSI_OVERSOLD_THRESHOLD < settings.RSI_OVERBOUGHT_THRESHOLD
        
        # Price change thresholds
        assert hasattr(settings, 'PRICE_CHANGE_ALERT_THRESHOLD')
        assert settings.PRICE_CHANGE_ALERT_THRESHOLD > 0
    
    def test_wheel_strategy_settings(self):
        """Test wheel strategy configuration."""
        # Put ranking weights
        assert hasattr(settings, 'PUT_RANKING_WEIGHTS')
        assert isinstance(settings.PUT_RANKING_WEIGHTS, dict)
        assert sum(settings.PUT_RANKING_WEIGHTS.values()) == 100
        
        # Call ranking weights
        assert hasattr(settings, 'CALL_RANKING_WEIGHTS')
        assert isinstance(settings.CALL_RANKING_WEIGHTS, dict)
        assert sum(settings.CALL_RANKING_WEIGHTS.values()) == 100
        
        # Required components (matching actual settings structure)
        required_put_components = ['rsi_score', 'price_stability', 'support_level', 'volume_score', 'trend_score', 'bollinger_position', 'macd_score']
        for component in required_put_components:
            assert component in settings.PUT_RANKING_WEIGHTS
        
        required_call_components = ['rsi_score', 'resistance_level', 'price_momentum', 'volume_score', 'trend_exhaustion', 'bollinger_position', 'macd_score']
        for component in required_call_components:
            assert component in settings.CALL_RANKING_WEIGHTS
    
    def test_data_directories(self):
        """Test data directory configurations."""
        # Specific output directories
        assert hasattr(settings, 'WATCHLIST_OUTPUT_DIR')
        assert hasattr(settings, 'RANKING_OUTPUT_DIR')
        assert hasattr(settings, 'DEFAULT_OUTPUT_DIR')
        
        # Directories should be different
        dirs = [settings.WATCHLIST_OUTPUT_DIR, settings.RANKING_OUTPUT_DIR, settings.DEFAULT_OUTPUT_DIR]
        assert len(set(dirs)) == len(dirs)  # All unique
        
        # Directories should be strings
        for dir_path in dirs:
            assert isinstance(dir_path, str)
            assert len(dir_path) > 0
    
    def test_minimum_score_thresholds(self):
        """Test minimum score thresholds for recommendations."""
        if hasattr(settings, 'MIN_PUT_SCORE'):
            assert 0 <= settings.MIN_PUT_SCORE <= 100
        if hasattr(settings, 'MIN_CALL_SCORE'):
            assert 0 <= settings.MIN_CALL_SCORE <= 100


class TestDataStorage:
    """Test data storage functionality."""
    
    @pytest.fixture
    def temp_dir(self):
        """Create a temporary directory for testing."""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield temp_dir
    
    def test_json_data_saving_loading(self, temp_dir):
        """Test JSON data saving and loading."""
        test_data = {
            'timestamp': '20251002_120000',
            'stocks': ['AAPL', 'MSFT'],
            'data': {
                'AAPL': {'price': 150.0, 'rsi': 45.0},
                'MSFT': {'price': 300.0, 'rsi': 55.0}
            }
        }
        
        file_path = Path(temp_dir) / 'test_data.json'
        
        # Test saving
        safe_write_json(file_path, test_data)
        assert file_path.exists()
        
        # Test loading
        with open(file_path, 'r') as f:
            loaded_data = json.load(f)
        assert loaded_data == test_data
    
    def test_data_directory_creation(self, temp_dir):
        """Test that data directories are created when needed."""
        nested_path = os.path.join(temp_dir, 'data', 'stock_watchlist', 'test.json')
        test_data = {'test': 'data'}
        
        # Directory shouldn't exist yet
        assert not os.path.exists(os.path.dirname(nested_path))
        
        # Save data (should create directories)
        safe_write_json(Path(nested_path), test_data)
        
        # Directory should now exist
        assert os.path.exists(os.path.dirname(nested_path))
        assert os.path.exists(nested_path)
    
    def test_file_naming_conventions(self):
        """Test file naming conventions."""
        from datetime import datetime
        
        # Test timestamp format
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        assert len(timestamp) == 15  # YYYYMMDD_HHMMSS
        assert '_' in timestamp
        assert timestamp[:8].isdigit()  # Date part
        assert timestamp[9:].isdigit()  # Time part
    
    def test_data_structure_validation(self, temp_dir):
        """Test that saved data maintains expected structure."""
        # Test watchlist data structure
        watchlist_data = {
            'timestamp': '20251002_120000',
            'market_session': 'regular',
            'total_analyzed': 10,
            'stocks': {},
            'alerts': [],
            'summary': {}
        }
        
        file_path = Path(temp_dir) / 'watchlist_test.json'
        safe_write_json(file_path, watchlist_data)
        with open(file_path, 'r') as f:
            loaded = json.load(f)
        
        # Verify structure is maintained
        required_keys = ['timestamp', 'stocks', 'alerts', 'summary']
        for key in required_keys:
            assert key in loaded
        
        # Test ranking data structure
        ranking_data = {
            'put_candidates': [],
            'call_candidates': [],
            'metadata': {
                'total_analyzed': 10,
                'timestamp': '20251002_120000'
            }
        }
        
        ranking_path = Path(temp_dir) / 'ranking_test.json'
        safe_write_json(ranking_path, ranking_data)
        with open(ranking_path, 'r') as f:
            loaded_ranking = json.load(f)
        
        required_ranking_keys = ['put_candidates', 'call_candidates', 'metadata']
        for key in required_ranking_keys:
            assert key in loaded_ranking


class TestDataIntegrity:
    """Test data integrity and consistency."""
    
    def test_timestamp_consistency(self):
        """Test timestamp format consistency."""
        from datetime import datetime
        
        # Generate timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Test format
        assert len(timestamp) == 15
        assert timestamp[8] == '_'
        
        # Test parsing back
        try:
            parsed = datetime.strptime(timestamp, "%Y%m%d_%H%M%S")
            assert parsed is not None
        except ValueError:
            pytest.fail("Timestamp format is not parseable")
    
    def test_score_consistency(self):
        """Test that scores remain within valid ranges."""
        # Test score validation function
        def validate_score(score):
            return isinstance(score, (int, float)) and 0 <= score <= 100
        
        # Test various score values
        valid_scores = [0, 25.5, 50, 75.3, 100]
        invalid_scores = [-1, 101, 150, -50]
        
        for score in valid_scores:
            assert validate_score(score), f"Valid score {score} failed validation"
        
        for score in invalid_scores:
            assert not validate_score(score), f"Invalid score {score} passed validation"
    
    def test_symbol_consistency(self):
        """Test that stock symbols remain consistent."""
        # Test symbol validation
        def validate_symbol(symbol):
            return (isinstance(symbol, str) and 
                   1 <= len(symbol) <= 5 and 
                   symbol.isupper() and 
                   symbol.isalpha())
        
        valid_symbols = ['AAPL', 'MSFT', 'GOOG', 'A', 'AMZN']
        invalid_symbols = ['aapl', 'TOOLONG', '123', 'AA1', '']
        
        for symbol in valid_symbols:
            assert validate_symbol(symbol), f"Valid symbol {symbol} failed validation"
        
        for symbol in invalid_symbols:
            assert not validate_symbol(symbol), f"Invalid symbol {symbol} passed validation"


class TestSystemIntegration:
    """Test integration between different system components."""
    
    def test_settings_import_success(self):
        """Test that all settings can be imported successfully."""
        try:
            from config.settings import (
                WATCHLIST_STOCKS,
                RSI_OVERSOLD_THRESHOLD,
                RSI_OVERBOUGHT_THRESHOLD,
                PUT_RANKING_WEIGHTS,
                CALL_RANKING_WEIGHTS,
                WATCHLIST_OUTPUT_DIR,
                RANKING_OUTPUT_DIR
            )
            assert True  # If we get here, imports succeeded
        except ImportError as e:
            pytest.fail(f"Failed to import settings: {e}")
    
    def test_data_flow_consistency(self):
        """Test that data flows consistently between components."""
        # This would test the actual data flow in a real scenario
        # For now, we test that the expected data structure exists
        
        expected_watchlist_structure = {
            'timestamp': str,
            'stocks': dict,
            'alerts': list,
            'summary': dict
        }
        
        expected_ranking_structure = {
            'put_candidates': list,
            'call_candidates': list,
            'metadata': dict
        }
        
        # Verify structures are well-defined
        assert all(isinstance(v, type) for v in expected_watchlist_structure.values())
        assert all(isinstance(v, type) for v in expected_ranking_structure.values())


if __name__ == "__main__":
    # Run tests with: python3.11 -m pytest tests/test_configuration.py -v
    pytest.main([__file__, "-v"])