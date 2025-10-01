# Documentation Index

This directory contains detailed documentation for the Schwab Trading v2 system.

## Setup & Configuration
- **[SCHWAB_SETUP.md](SCHWAB_SETUP.md)** - Schwab API setup, authentication, and credential configuration

## Development & Testing  
- **[DEVELOPMENT.md](DEVELOPMENT.md)** - Development workflow, commands, and architecture notes
- **[TESTING.md](TESTING.md)** - Test suite documentation and validation procedures

## Features
- **[ASSIGNMENT_TRACKING.md](ASSIGNMENT_TRACKING.md)** - Complete assignment detection system documentation

## Quick Reference

### First Time Setup
1. Follow [SCHWAB_SETUP.md](SCHWAB_SETUP.md) to configure API credentials
2. Run `python scripts/setup_tokens.py` to authenticate
3. Run `python main.py` to start the application

### Development
1. Read [DEVELOPMENT.md](DEVELOPMENT.md) for workflow
2. Run `pytest` to validate changes
3. Use [TESTING.md](TESTING.md) for testing procedures

### Assignment Tracking
1. See [ASSIGNMENT_TRACKING.md](ASSIGNMENT_TRACKING.md) for system details
2. Run `python scripts/manage_assignments.py status` to view assignments
3. Use `python tools/test_real_assignments.py` to test detection