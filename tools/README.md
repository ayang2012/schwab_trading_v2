# Development Tools

This directory contains utility scripts and tools used during development and testing.

## Scripts

### Assignment Testing & Population
- `test_real_assignments.py` - Test script to validate assignment detection against real Schwab account data
- `add_assignments.py` - Quick script to manually populate assignment database with sample data
- `populate_assignments.py` - Script to fetch and populate assignments from Schwab API (work in progress)
- `view_assignments.py` - Simple database viewer for assignment data

## Usage

### View Assignments
```bash
# Quick view of all assignments
python3.11 tools/view_assignments.py

# Use the full CLI tool for more features
python3.11 scripts/manage_assignments.py status
```

### Test Assignment Detection
```bash
# Test against real account data (requires Schwab API access)
python3.11 tools/test_real_assignments.py
```

### Populate Database
```bash
# Add sample assignments to database
python3.11 tools/add_assignments.py
```

## Note

These are development/testing tools. For production assignment management, use:
- `scripts/manage_assignments.py` - Main assignment management CLI
- `main.py` - Main application (will integrate assignments in the future)