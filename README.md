# Schwab Trading v2

Advanced options trading system with real-time position tracking, technical analysis, and comprehensive assignment monitoring.

## Features

- **Real-time Position Tracking**: Live stock and option positions with P&L calculations
- **Technical Analysis**: RSI, moving averages, EMA analysis with trend detection  
- **Assignment Tracking**: Automatic detection and recording of option assignments
- **Account Monitoring**: Cash balance, buying power, and account value tracking
- **Live Market Data**: Real-time price updates and position monitoring

## Quick Start

### 1. Setup
```bash
pip install -r requirements.txt
python scripts/setup_tokens.py  # Configure Schwab API credentials
```

### 2. Run
```bash
python main.py  # Main trading application
```

### 3. Monitor Assignments
```bash
python scripts/manage_assignments.py status  # View assignment tracking
```

## Documentation

- **[Setup Guide](docs/SCHWAB_SETUP.md)** - Schwab API configuration and authentication
- **[Development Guide](docs/DEVELOPMENT.md)** - Development workflow and commands  
- **[Assignment Tracking](docs/ASSIGNMENT_TRACKING.md)** - Assignment detection system details
- **[Testing Guide](docs/TESTING.md)** - Test suite and validation procedures

## Project Structure

```
schwab_trading_v2/
├── analysis/               # Technical analysis modules
├── api/                    # API clients and interfaces  
├── core/                   # Core business logic and models
├── data/                   # Data storage (databases, snapshots)
├── docs/                   # Documentation
├── scripts/                # Production command-line utilities
├── tests/                  # Test files
├── tools/                  # Development and testing utilities
├── utils/                  # Utility functions and helpers
└── main.py                 # Main application entry point
```

## Key Commands

### Main Application
```bash
python main.py                              # Run main trading dashboard
python scripts/live_monitor.py              # Live monitoring (30s)
```

### Assignment Management  
```bash
python scripts/manage_assignments.py status    # Assignment overview
python scripts/manage_assignments.py ticker AAL # Ticker-specific assignments
python scripts/manage_assignments.py backfill --days 30 # Historical backfill
```

### Development Tools
```bash
python tools/view_assignments.py            # Quick assignment database view
python tools/test_real_assignments.py       # Test with real account data
pytest                                       # Run test suite
```

## Requirements

- Python 3.11+
- Schwab API credentials (app key, app secret)
- Active Schwab brokerage account

## License

This project is for educational and personal use only. Please ensure compliance with your broker's API terms of service.