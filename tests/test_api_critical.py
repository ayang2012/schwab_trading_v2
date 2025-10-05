"""Critical API Integration Tests for Put Selection.

These tests specifically validate the Schwab API integration issues that were
discovered and fixed, including:
- Options chain API parameter validation
- fromDate/toDate parameter rejection handling
- Minimal API call success validation
"""

import pytest
from unittest.mock import Mock, patch
from datetime import datetime, timedelta
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from strategies.put_selection import PutSelectionEngine


class MockResponse:
    """Mock HTTP response for API calls."""
    
    def __init__(self, json_data, status_code=200):
        self.json_data = json_data
        self.status_code = status_code
    
    def json(self):
        return self.json_data


class TestSchwabAPIIntegration:
    """Test critical Schwab API integration points."""
    
    @pytest.fixture
    def mock_client_success(self):
        """Mock client that returns successful API responses."""
        client = Mock()
        raw_client = Mock()
        client.client = raw_client
        
        # Mock successful options chain response
        options_data = {
            'underlyingPrice': 101.5,
            'putExpDateMap': {
                '2025-01-17:8': {
                    '100.0': [{
                        'strikePrice': 100.0,
                        'bid': 4.75,
                        'ask': 4.90,
                        'mark': 4.82,
                        'openInterest': 1200,
                        'delta': -0.45,
                        'daysToExpiration': 8,
                        'expirationDate': 1737158400000
                    }]
                }
            }
        }
        raw_client.option_chains.return_value = MockResponse(options_data)
        return client
    
    @pytest.fixture
    def mock_client_400_error(self):
        """Mock client that returns 400 Bad Request errors."""
        client = Mock()
        raw_client = Mock()
        client.client = raw_client
        
        # Mock 400 error response (like we were getting)
        raw_client.option_chains.return_value = MockResponse(
            {'error': 'Check Param Values', 'message': 'Invalid Parameter/Value'}, 
            400
        )
        return client
    
    def test_options_chain_correct_parameters(self, mock_client_success):
        """Test that options chain API is called with ONLY contractType parameter."""
        engine = PutSelectionEngine(mock_client_success)
        
        # Call the method
        result = engine._get_put_options_chain('AAPL')
        
        # Verify API was called with ONLY contractType='PUT' (no date parameters)
        mock_client_success.client.option_chains.assert_called_once_with(
            symbol='AAPL',
            contractType='PUT'
        )
        
        # Verify we got a successful result
        assert result is not None
        assert 'underlyingPrice' in result
    
    def test_options_chain_400_error_handling(self, mock_client_400_error):
        """Test graceful handling of 400 Bad Request errors."""
        engine = PutSelectionEngine(mock_client_400_error)
        
        # Call the method - should handle 400 error gracefully
        result = engine._get_put_options_chain('AAPL')
        
        # Should return None on API failure
        assert result is None
    
    def test_options_chain_no_invalid_parameters(self, mock_client_success):
        """Test that we never pass fromDate/toDate parameters that cause 400 errors."""
        engine = PutSelectionEngine(mock_client_success)
        
        # Call the method
        engine._get_put_options_chain('AAPL')
        
        # Get the actual call arguments
        call_args = mock_client_success.client.option_chains.call_args
        args, kwargs = call_args
        
        # Verify that NO date parameters are passed
        forbidden_params = ['fromDate', 'toDate', 'startDate', 'endDate']
        for param in forbidden_params:
            assert param not in kwargs, f"Found forbidden parameter: {param}"
        
        # Verify only allowed parameters are passed
        allowed_params = ['symbol', 'contractType']
        for key in kwargs.keys():
            assert key in allowed_params, f"Found unexpected parameter: {key}"
    
    @patch('strategies.put_selection.datetime')
    def test_api_call_timing_independence(self, mock_datetime, mock_client_success):
        """Test that API calls work regardless of current date/time."""
        # Mock different dates to ensure API call doesn't depend on timing
        test_dates = [
            datetime(2025, 1, 1),   # New Year
            datetime(2025, 6, 15),  # Mid year
            datetime(2025, 12, 31)  # End of year
        ]
        
        engine = PutSelectionEngine(mock_client_success)
        
        for test_date in test_dates:
            mock_datetime.now.return_value = test_date
            mock_client_success.client.option_chains.reset_mock()
            
            # API call should work regardless of date
            result = engine._get_put_options_chain('AAPL')
            
            assert result is not None
            # Verify same call signature regardless of date
            mock_client_success.client.option_chains.assert_called_once_with(
                symbol='AAPL',
                contractType='PUT'
            )
    
    def test_multiple_symbols_api_calls(self, mock_client_success):
        """Test API calls work for multiple symbols."""
        engine = PutSelectionEngine(mock_client_success)
        
        symbols = ['AAPL', 'MSFT', 'GOOGL']
        
        for symbol in symbols:
            mock_client_success.client.option_chains.reset_mock()
            
            result = engine._get_put_options_chain(symbol)
            
            # Each call should succeed with correct parameters
            assert result is not None
            mock_client_success.client.option_chains.assert_called_once_with(
                symbol=symbol,
                contractType='PUT'
            )
    
    def test_api_call_robustness(self, mock_client_success):
        """Test that API calls are robust and don't add extra parameters."""
        engine = PutSelectionEngine(mock_client_success)
        
        # Call the method multiple times
        for _ in range(3):
            result = engine._get_put_options_chain('AAPL')
            assert result is not None
        
        # Verify all calls used the same minimal parameter set
        assert mock_client_success.client.option_chains.call_count == 3
        
        # Check that all calls were identical
        calls = mock_client_success.client.option_chains.call_args_list
        for call in calls:
            args, kwargs = call
            assert kwargs == {'symbol': 'AAPL', 'contractType': 'PUT'}


class TestAPIParameterValidation:
    """Test validation of API parameters to prevent 400 errors."""
    
    def test_no_date_parameters_in_options_chain(self):
        """Test that our options chain calls never include date parameters."""
        # This test validates the fix we implemented
        client = Mock()
        raw_client = Mock()
        client.client = raw_client
        
        engine = PutSelectionEngine(client)
        
        # Mock a successful response
        raw_client.option_chains.return_value = MockResponse({
            'underlyingPrice': 100.0,
            'putExpDateMap': {}
        })
        
        # Call the method
        engine._get_put_options_chain('TEST')
        
        # Inspect the actual API call
        call_args = raw_client.option_chains.call_args
        args, kwargs = call_args
        
        # Critical test: ensure no date-related parameters
        date_params = [
            'fromDate', 'toDate', 'startDate', 'endDate',
            'expMonth', 'expYear', 'expirationDate'
        ]
        
        for param in date_params:
            assert param not in kwargs, f"API call included forbidden date parameter: {param}"
        
        # Ensure we only have the essential parameters
        assert 'symbol' in kwargs
        assert 'contractType' in kwargs
        assert kwargs['contractType'] == 'PUT'
        
        # Ensure no extra parameters
        assert len(kwargs) == 2, f"Too many parameters in API call: {kwargs.keys()}"


class TestAPIErrorRecovery:
    """Test recovery from various API error conditions."""
    
    def test_temporary_api_failure_recovery(self):
        """Test handling of temporary API failures."""
        client = Mock()
        raw_client = Mock()
        client.client = raw_client
        
        # First call fails, second succeeds
        raw_client.option_chains.side_effect = [
            MockResponse({'error': 'Temporary failure'}, 500),
            MockResponse({'underlyingPrice': 100.0, 'putExpDateMap': {}}, 200)
        ]
        
        engine = PutSelectionEngine(client)
        
        # First call should return None
        result1 = engine._get_put_options_chain('AAPL')
        assert result1 is None
        
        # Second call should succeed
        result2 = engine._get_put_options_chain('AAPL')
        assert result2 is not None
    
    def test_malformed_response_handling(self):
        """Test handling of malformed API responses."""
        client = Mock()
        raw_client = Mock()
        client.client = raw_client
        
        # Mock malformed JSON response
        raw_client.option_chains.return_value = MockResponse(
            {'unexpected': 'structure'}, 200
        )
        
        engine = PutSelectionEngine(client)
        
        # Should handle gracefully (not crash)
        result = engine._get_put_options_chain('AAPL')
        assert result is not None  # Returns the response even if malformed
        assert 'unexpected' in result
    
    def test_network_timeout_simulation(self):
        """Test handling of network timeouts."""
        client = Mock()
        raw_client = Mock()
        client.client = raw_client
        
        # Simulate network timeout
        raw_client.option_chains.side_effect = Exception("Connection timeout")
        
        engine = PutSelectionEngine(client)
        
        # Should handle exception gracefully
        result = engine._get_put_options_chain('AAPL')
        assert result is None


if __name__ == "__main__":
    # Run tests focused on API integration
    pytest.main([__file__, "-v", "-k", "test_options_chain"])