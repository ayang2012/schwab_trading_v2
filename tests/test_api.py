"""Pytest tests for Schwab API client functionality."""
import pytest
import sys
from pathlib import Path

# Add the project to the Python path  
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from utils.config_schwab import SchwabConfig
from api.sim_client import SimBrokerClient
from core.models import AccountSnapshot


@pytest.fixture
def schwab_config():
    """Fixture for Schwab configuration."""
    return SchwabConfig.from_env()


@pytest.fixture  
def sim_client():
    """Fixture for simulated broker client."""
    return SimBrokerClient()





class TestSchwabConfig:
    """Test Schwab configuration loading."""
    
    def test_config_creation(self):
        """Test that config can be created."""
        config = SchwabConfig.from_env()
        assert config is not None
        assert hasattr(config, 'app_key')
        assert hasattr(config, 'app_secret')
        assert hasattr(config, 'redirect_uri')
        assert hasattr(config, 'token_path')


class TestSimBrokerClient:
    """Test simulated broker client."""
    
    def test_sim_client_initialization(self, sim_client):
        """Test that simulated client initializes correctly."""
        assert sim_client is not None

    def test_sim_client_snapshot(self, sim_client):
        """Test that simulated client returns valid snapshot."""
        snapshot = sim_client.get_account_snapshot()
        
        assert isinstance(snapshot, AccountSnapshot)
        assert snapshot.cash is not None
        assert snapshot.buying_power is not None
        assert isinstance(snapshot.stocks, list)
        assert isinstance(snapshot.options, list)
        assert isinstance(snapshot.mutual_funds, list)
        
        # Test that we have some simulated data
        assert len(snapshot.stocks) > 0
        assert len(snapshot.options) > 0



# Legacy main function for backward compatibility
def main():
    """Run tests using pytest programmatically."""
    print("Running API tests with pytest...")
    return pytest.main([__file__, "-v"])


if __name__ == "__main__":
    exit(main())