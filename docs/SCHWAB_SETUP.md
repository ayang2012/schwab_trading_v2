# Schwab API Setup Guide

This guide will help you set up the Schwab API integration to get your real account data.

## Prerequisites

1. **Schwab Developer Account**: You need a Schwab brokerage account and developer access
2. **API Application**: Create an application in the Schwab Developer Portal
3. **Python SDK**: Install the unofficial Schwab Python SDK

## Step 1: Get API Credentials

1. Go to the [Schwab Developer Portal](https://developer.schwab.com/)
2. Sign in with your Schwab credentials
3. Create a new application or use an existing one
4. Note down your:
   - **App Key** (Consumer Key)
   - **App Secret** (Consumer Secret)
   - **Redirect URI** (e.g., `https://localhost:8080`)

## Step 2: Install Dependencies

```bash
pip install schwab-py
```

## Step 3: Set Up Environment Variables

Create a `.env` file in your project directory or set environment variables:

```bash
export SCHWAB_APP_KEY="your_app_key_here"
export SCHWAB_APP_SECRET="your_app_secret_here"
export SCHWAB_REDIRECT_URI="https://localhost:8080"  # Optional
export SCHWAB_TOKEN_PATH="./schwab_tokens.json"      # Optional
```

## Step 4: First-Time Authentication

The first time you run the real client, you'll need to complete OAuth authentication:

1. Run the CLI with real API:
   ```bash
   python3 -m schwab_trading_v2.cli --use-real
   ```

2. Follow the OAuth flow:
   - A browser window will open
   - Log in to Schwab
   - Authorize the application
   - You'll be redirected to your redirect URI
   - Copy the full redirect URL and paste it when prompted

3. The authentication tokens will be saved for future use

## Step 5: Run with Real Data

Once authenticated, you can run:

```bash
# Use environment variables
python3 -m schwab_trading_v2.cli --use-real

# Or specify credentials directly
python3 -m schwab_trading_v2.cli --use-real --app-key YOUR_KEY --app-secret YOUR_SECRET
```

## Troubleshooting

### "Module not found" errors
Make sure you're running from the parent directory:
```bash
cd /Users/ayang2012/Desktop/projects/
python3 -m schwab_trading_v2.cli --use-real
```

### Authentication issues
- Check that your app key and secret are correct
- Ensure your redirect URI matches what's registered in the developer portal
- Delete `schwab_tokens.json` and re-authenticate if needed

### API Rate Limits
- Schwab has rate limits on API calls
- The tool makes minimal calls (just account info and positions)
- If you hit limits, wait a few minutes before trying again

## Security Notes

- Never commit your API credentials to version control
- Use environment variables or a secure credential store
- The token file contains sensitive authentication data - keep it secure
- Consider using a service account for production use

## Next Steps

Once you have real data flowing:
1. Test with small positions first
2. Verify P&L calculations match your Schwab interface
3. Set up automated snapshots if needed
4. Add error handling for specific API scenarios