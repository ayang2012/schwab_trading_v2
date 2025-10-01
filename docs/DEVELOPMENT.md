# Development Guide

## Quick Start Commands

### Main Application
```bash
# Run main trading application
python3.11 main.py

# Run with live monitoring (30 seconds, 10s intervals)
python3.11 scripts/live_monitor.py
```

### Assignment Management
```bash
# Check assignment status
python3.11 scripts/manage_assignments.py status

# View assignments for specific ticker
python3.11 scripts/manage_assignments.py ticker AAL

# Backfill historical assignments
python3.11 scripts/manage_assignments.py backfill --days 30
```

### Development Tools
```bash
# Test assignment detection with real account data
python3.11 tools/test_real_assignments.py

# Quick view of assignment database
python3.11 tools/view_assignments.py

# Populate assignment database manually
python3.11 tools/add_assignments.py
```

### Testing
```bash
# Run all tests
pytest

# Run specific test module
pytest tests/test_assignments.py

# Run with verbose output
pytest -v
```

## Project Components

### Core Features
- **Real-time Position Tracking**: Live stock and option positions with P&L
- **Technical Analysis**: Moving averages, RSI, EMA analysis
- **Assignment Tracking**: Automatic detection and recording of option assignments
- **Account Monitoring**: Cash balance, buying power, account value tracking

### API Integration
- **Schwab API**: Real broker integration using `schwabdev` library
- **Live Data**: Real-time market data and position updates
- **Transaction Processing**: Automatic transaction parsing and assignment detection

### Data Management
- **SQLite Databases**: Local storage for assignments and account history
- **JSON Snapshots**: Account state preservation
- **CSV Export**: Historical account value tracking

## Development Workflow

1. **Setup**: Configure API credentials in `.env`
2. **Test**: Run `tools/test_real_assignments.py` to validate API connection
3. **Develop**: Make changes to core modules
4. **Validate**: Run tests with `pytest`
5. **Deploy**: Run main application with `python3.11 main.py`

## Architecture Notes

- **Modular Design**: Separate API, core logic, and utilities
- **Real vs Sim**: Production client for real data, sim client for testing
- **Assignment System**: Complete detection, normalization, and tracking
- **Extensible**: Easy to add new brokers or features