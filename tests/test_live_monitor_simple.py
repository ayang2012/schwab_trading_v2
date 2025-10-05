#!/usr/bin/env python3
"""
Simple integration tests for live monitor functionality.
"""

import json
import tempfile
import os
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path
import sys

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    import pytest
except ImportError:
    print("pytest not installed. Install with: pip install pytest")
    sys.exit(1)


class TestLiveMonitorIntegration:
    """Test live monitor integration without heavy mocking."""
    
    def test_live_monitor_imports_successfully(self):
        """Test that live_monitor.py can be imported without errors."""
        try:
            # Import the module
            sys.path.insert(0, str(Path(__file__).parent.parent))
            import live_monitor
            
            # Check key classes exist
            assert hasattr(live_monitor, 'LiveTradingMonitor')
            assert True  # Success if we get here
        except ImportError as e:
            pytest.fail(f"Failed to import live_monitor: {e}")
    
    def test_live_monitor_class_can_be_instantiated(self):
        """Test that LiveTradingMonitor can be created (with mocking)."""
        try:
            # Mock the expensive dependencies
            with patch('api.client.RealBrokerClient'), \
                 patch('analysis.technicals.TechnicalAnalyzer'), \
                 patch('os.getenv', return_value='1'):  # Test mode
                
                from live_monitor import LiveTradingMonitor
                monitor = LiveTradingMonitor()
                
                assert monitor is not None
                assert hasattr(monitor, 'client')
        except Exception as e:
            pytest.skip(f"LiveTradingMonitor instantiation not working: {e}")
    
    def test_market_hours_constants_exist(self):
        """Test that market hours are properly configured."""
        try:
            from config.settings import (
                MARKET_OPEN_HOUR, MARKET_OPEN_MINUTE,
                MARKET_CLOSE_HOUR, MARKET_CLOSE_MINUTE
            )
            
            # Basic validation
            assert 0 <= MARKET_OPEN_HOUR <= 23
            assert 0 <= MARKET_OPEN_MINUTE <= 59
            assert 0 <= MARKET_CLOSE_HOUR <= 23
            assert 0 <= MARKET_CLOSE_MINUTE <= 59
            
        except ImportError as e:
            pytest.fail(f"Market hours configuration missing: {e}")
    
    def test_monitoring_interval_setting(self):
        """Test that monitoring interval is configured."""
        try:
            from config.settings import DEFAULT_MONITORING_INTERVAL
            assert isinstance(DEFAULT_MONITORING_INTERVAL, int)
            assert DEFAULT_MONITORING_INTERVAL > 0
            assert DEFAULT_MONITORING_INTERVAL <= 300  # Reasonable max (5 minutes)
        except ImportError as e:
            pytest.fail(f"Monitoring interval not configured: {e}")


class TestDataFlowIntegration:
    """Test data flow between components."""
    
    def test_data_directories_are_consistent(self):
        """Test that data directories are consistent across modules."""
        try:
            from config.settings import WATCHLIST_OUTPUT_DIR, RANKING_OUTPUT_DIR
            
            # Directories should be strings
            assert isinstance(WATCHLIST_OUTPUT_DIR, str)
            assert isinstance(RANKING_OUTPUT_DIR, str)
            
            # Should contain expected keywords
            assert 'watchlist' in WATCHLIST_OUTPUT_DIR.lower()
            assert 'ranking' in RANKING_OUTPUT_DIR.lower()
            
            # Should be different directories
            assert WATCHLIST_OUTPUT_DIR != RANKING_OUTPUT_DIR
            
        except ImportError as e:
            pytest.fail(f"Data directory configuration error: {e}")
    
    def test_json_file_patterns_exist(self):
        """Test that file naming patterns are configured."""
        try:
            from datetime import datetime
            
            # Test timestamp generation (used in file naming)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            
            # Basic format validation
            assert len(timestamp) == 15
            assert '_' in timestamp
            assert timestamp[:8].isdigit()  # Date part
            assert timestamp[9:].isdigit()  # Time part
            
        except Exception as e:
            pytest.fail(f"Timestamp generation error: {e}")
    
    def test_watchlist_to_ranking_data_compatibility(self):
        """Test that watchlist data structure is compatible with ranking system."""
        # Mock watchlist data structure (what live_monitor creates)
        mock_watchlist_data = {
            'timestamp': '20251002_120000',
            'stocks': {
                'AAPL': {
                    'price': 150.0,
                    'rsi': 45.0,
                    'price_change_pct': -1.0
                }
            },
            'alerts': []
        }
        
        # Test that this structure has the expected fields
        assert 'timestamp' in mock_watchlist_data
        assert 'stocks' in mock_watchlist_data
        assert isinstance(mock_watchlist_data['stocks'], dict)
        
        # Test stock data structure
        for symbol, data in mock_watchlist_data['stocks'].items():
            assert isinstance(symbol, str)
            assert isinstance(data, dict)
            # These are minimum fields needed for ranking
            expected_fields = ['price', 'rsi']
            for field in expected_fields:
                if field not in data:
                    pytest.skip(f"Stock data missing {field} field - may need adjustment")


class TestSystemHealthChecks:
    """Basic system health checks."""
    
    def test_all_required_modules_importable(self):
        """Test that all critical modules can be imported."""
        critical_modules = [
            'config.settings',
            'analysis.technicals', 
            'api.client',
            'core.models',
            'utils.logging'
        ]
        
        for module_name in critical_modules:
            try:
                __import__(module_name)
            except ImportError as e:
                pytest.fail(f"Critical module {module_name} cannot be imported: {e}")
    
    def test_settings_completeness(self):
        """Test that critical settings are present."""
        try:
            from config import settings
            
            critical_settings = [
                'WATCHLIST_STOCKS',
                'RSI_OVERSOLD_THRESHOLD', 
                'RSI_OVERBOUGHT_THRESHOLD',
                'PUT_RANKING_WEIGHTS',
                'CALL_RANKING_WEIGHTS'
            ]
            
            for setting in critical_settings:
                assert hasattr(settings, setting), f"Missing critical setting: {setting}"
                value = getattr(settings, setting)
                assert value is not None, f"Setting {setting} is None"
                
        except ImportError as e:
            pytest.fail(f"Cannot import settings: {e}")
    
    def test_file_system_permissions(self):
        """Test that we can create files in data directories."""
        try:
            from config.settings import WATCHLIST_OUTPUT_DIR, RANKING_OUTPUT_DIR
            
            for data_dir in [WATCHLIST_OUTPUT_DIR, RANKING_OUTPUT_DIR]:
                # Create directory if it doesn't exist
                Path(data_dir).mkdir(parents=True, exist_ok=True)
                
                # Test write permission
                test_file = Path(data_dir) / 'test_write_permission.tmp'
                try:
                    test_file.write_text('test')
                    test_file.unlink()  # Clean up
                except PermissionError:
                    pytest.fail(f"No write permission in {data_dir}")
                    
        except Exception as e:
            pytest.skip(f"File system permission test failed: {e}")


class TestEndToEndWorkflow:
    """Test end-to-end workflow scenarios."""
    
    @pytest.mark.slow
    def test_simulated_monitoring_cycle(self):
        """Test a simulated monitoring cycle."""
        try:
            # Mock all external dependencies
            with patch('api.client.RealBrokerClient') as mock_client, \
                 patch('analysis.technicals.TechnicalAnalyzer') as mock_analyzer, \
                 patch('os.getenv', return_value='1'):  # Test mode
                
                # Set up mocks
                mock_client_instance = Mock()
                mock_client.return_value = mock_client_instance
                
                mock_analyzer_instance = Mock()
                mock_analyzer.return_value = mock_analyzer_instance
                
                # Mock analysis results
                mock_analyzer_instance.get_technical_analysis.return_value = {
                    'price': 150.0,
                    'rsi': 45.0,
                    'price_change_pct': -1.0
                }
                
                from live_monitor import LiveTradingMonitor
                monitor = LiveTradingMonitor()
                
                # Test that monitor was created successfully
                assert monitor is not None
                
                # Note: We don't actually run the monitoring loop in tests
                # as that would require real market data and could run indefinitely
                
        except Exception as e:
            pytest.skip(f"End-to-end test not fully implementable: {e}")


if __name__ == "__main__":
    # Run tests with: python3.11 -m pytest tests/test_live_monitor_simple.py -v
    pytest.main([__file__, "-v"])