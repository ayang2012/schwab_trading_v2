"""Production Schwab API client for real trading account data.

This module provides the production interface to retrieve live account
information and positions from Schwab's API.
"""
from datetime import datetime, timedelta
from decimal import Decimal

try:
    # Try relative imports first (when run as module from parent)
    from ..core.models import AccountSnapshot, StockPosition, OptionPosition, MutualFundPosition
    from ..utils.logging import get_logger
except ImportError:
    # Fall back to direct imports (when run from within directory)
    from core.models import AccountSnapshot, StockPosition, OptionPosition, MutualFundPosition
    from utils.logging import get_logger


class RealBrokerClient:
    """Real broker client for Schwab API integration using schwabdev library.
    
    To use this client:
    1. Install the Schwab library: pip install schwabdev
    2. Set up your Schwab API credentials (app key, app secret)
    3. Configure OAuth2 authentication
    """

    def __init__(self, app_key: str | None = None, app_secret: str | None = None, 
                 redirect_uri: str | None = None, token_path: str | None = None):
        """Initialize the Schwab client.
        
        Args:
            app_key: Your Schwab API app key
            app_secret: Your Schwab API app secret  
            redirect_uri: OAuth redirect URI (e.g., 'https://127.0.0.1')
            token_path: Path to store OAuth tokens
        """
        self.app_key = app_key
        self.app_secret = app_secret
        self.redirect_uri = redirect_uri or "https://127.0.0.1"
        self.token_path = token_path or "tokens.json"
        self.client = None
        self.logger = get_logger()
        
        # Initialize Schwab client
        if app_key and app_secret:
            try:
                import schwabdev
                self.client = schwabdev.Client(
                    app_key=self.app_key,
                    app_secret=self.app_secret,
                    callback_url=self.redirect_uri,
                    tokens_file=self.token_path
                )
                self.logger.info("✓ Schwab client initialized successfully")
            except ImportError:
                raise ImportError("schwabdev package is required. Install with: pip install schwabdev")
            except Exception as e:
                self.logger.warning(f"Could not initialize Schwab client: {e}")
                self.logger.info("This is normal on first run - authentication will be required.")

    def _handle_token_refresh(self):
        """Handle automatic token refresh when authentication fails."""
        try:
            self.logger.info("🔄 Re-initializing Schwab client with fresh authentication...")
            import schwabdev
            
            # Re-create the client - this will trigger the OAuth flow if needed
            self.client = schwabdev.Client(
                app_key=self.app_key,
                app_secret=self.app_secret,
                callback_url=self.redirect_uri,
                tokens_file=self.token_path
            )
            self.logger.info("✓ Token refresh completed successfully")
            
        except Exception as e:
            self.logger.error(f"Failed to refresh tokens: {e}")
            
            # If refresh fails, try deleting the token file and starting fresh
            try:
                import os
                if os.path.exists(self.token_path):
                    self.logger.info(f"🗑️  Deleting invalid token file: {self.token_path}")
                    os.remove(self.token_path)
                    
                    self.logger.info("🔐 Starting fresh authentication...")
                    import schwabdev
                    self.client = schwabdev.Client(
                        app_key=self.app_key,
                        app_secret=self.app_secret,
                        callback_url=self.redirect_uri,
                        tokens_file=self.token_path
                    )
                    self.logger.info("✓ Fresh authentication completed successfully")
                else:
                    raise RuntimeError("Token file not found")
                    
            except Exception as refresh_error:
                self.logger.error(f"Fresh authentication also failed: {refresh_error}")
                self.logger.info("Manual intervention required:")
                self.logger.info(f"1. Ensure {self.token_path} directory exists")
                self.logger.info("2. Check your app_key and app_secret are correct")
                self.logger.info("3. Ensure your callback_url matches your Schwab app configuration")
                raise RuntimeError("Automatic token refresh failed - manual setup required")

    def get_account_snapshot(self) -> AccountSnapshot:
        """Fetch real account data from Schwab API using schwabdev."""
        if self.client is None:
            raise RuntimeError("Schwab client not initialized. Please set up API credentials.")
        
        try:
            self.logger.debug("Fetching account numbers...")
            accounts_response = self.client.account_linked()
            accounts_data = accounts_response.json()
            self.logger.debug(f"Raw accounts data: {accounts_data}")
            
            # Check for authentication errors and handle automatically
            if isinstance(accounts_data, dict) and 'errors' in accounts_data:
                errors = accounts_data['errors']
                for error in errors:
                    if error.get('status') == 401 or 'Unauthorized' in error.get('title', ''):
                        self.logger.warning("Authentication failed - tokens may be expired")
                        self.logger.info("Attempting to re-authenticate...")
                        self._handle_token_refresh()
                        # Retry the request after re-authentication
                        accounts_response = self.client.account_linked()
                        accounts_data = accounts_response.json()
                        break
            
            self.logger.debug(f"Found {len(accounts_data)} accounts")
            
            if not accounts_data:
                raise RuntimeError("No accounts found")
            
            # Use the first account - handle both list and dict formats
            if isinstance(accounts_data, list):
                first_account = accounts_data[0]
            else:
                # If it's a dict, get the first value
                first_account = list(accounts_data.values())[0] if accounts_data else {}
            
            account_hash = first_account['hashValue']
            account_number = first_account.get('accountNumber', 'Unknown')
            self.logger.debug(f"Using account: {account_number} (hash: {account_hash[:8]}...)")
            
            # Get detailed account info with positions
            self.logger.debug("Fetching account details and positions...")
            account_response = self.client.account_details(account_hash, fields="positions")
            account_data = account_response.json()
            
            # Debug: Log the structure to understand the data
            self.logger.debug("Account data structure:")
            if self.logger.isEnabledFor(10):  # DEBUG level
                self._print_json_structure(account_data)
            
            securities_account = account_data.get('securitiesAccount', {})
            
            # Parse balances
            balances = securities_account.get('currentBalances', {})
            cash = Decimal(str(balances.get('cashBalance', 0)))
            buying_power = Decimal(str(balances.get('buyingPower', 0)))
            liquidation_value = Decimal(str(balances.get('liquidationValue', 0)))
            
            self.logger.debug(f"Cash: ${cash}")
            self.logger.debug(f"Buying Power: ${buying_power}")
            self.logger.debug(f"Schwab Liquidation Value: ${liquidation_value}")
            
            # Parse positions
            stocks = []
            options = []
            mutual_funds = []
            positions = securities_account.get('positions', [])
            
            self.logger.debug(f"Found {len(positions)} positions")
            
            for i, position in enumerate(positions):
                self.logger.debug(f"\nPosition {i+1}:")
                self.logger.debug(f"  Raw position data: {position}")
                
                instrument = position.get('instrument', {})
                long_qty = float(position.get('longQuantity', 0))
                short_qty = float(position.get('shortQuantity', 0))
                qty = long_qty - short_qty
                
                if qty == 0:
                    continue
                
                asset_type = instrument.get('assetType', '')
                symbol = instrument.get('symbol', '')
                
                avg_cost = Decimal(str(position.get('averagePrice', 0)))
                market_value = Decimal(str(position.get('marketValue', 0)))
                # For options, market_value is the total value for all contracts
                # Options are quoted per share, but contracts represent 100 shares
                # So we need to divide market_value by (quantity * 100) to get per-share price
                if asset_type == 'OPTION':
                    market_price = Decimal(str(abs(float(market_value)) / (abs(float(qty)) * 100) if qty != 0 else 0))
                else:
                    market_price = Decimal(str(abs(float(market_value)) / abs(float(qty)) if qty != 0 else 0))
                
                self.logger.debug(f"  Symbol: {symbol}")
                self.logger.debug(f"  Asset Type: {asset_type}")
                self.logger.debug(f"  Quantity: {qty}")
                self.logger.debug(f"  Avg Cost: ${avg_cost}")
                self.logger.debug(f"  Market Price: ${market_price}")
                self.logger.debug(f"  Market Value: ${market_value}")
                
                if asset_type == 'EQUITY':
                    stocks.append(StockPosition(
                        symbol=symbol,
                        qty=int(qty),
                        avg_cost=avg_cost,
                        market_price=market_price
                    ))
                elif asset_type == 'OPTION':
                    # Parse option details
                    underlying_symbol = instrument.get('underlyingSymbol', symbol.split('_')[0] if '_' in symbol else symbol)
                    strike_price = Decimal(str(instrument.get('strikePrice', 0)))
                    
                    # If strike price is 0, try to parse from contract symbol
                    if strike_price == 0 and len(symbol) >= 15:
                        try:
                            # Contract format: SYMBOL YYMMDDCPPPPPPPPP where P is strike * 1000
                            # Example: "ACHR  251003P00009500" -> strike = 9.5
                            strike_part = symbol[-8:]  # Last 8 characters
                            strike_price = Decimal(str(int(strike_part) / 1000.0))
                            self.logger.debug(f"  Parsed strike from contract symbol: {strike_price}")
                        except (ValueError, IndexError):
                            self.logger.warning(f"  Could not parse strike price from symbol: {symbol}")
                            strike_price = Decimal('0')
                    
                    expiry_date = instrument.get('expirationDate', '')
                    put_call = instrument.get('putCall', 'C')
                    
                    # If put_call is empty, try to parse from contract symbol
                    if not put_call and len(symbol) >= 15:
                        try:
                            # Put/Call is the character before the strike price (position -9)
                            put_call = symbol[-9].upper()
                            self.logger.debug(f"  Parsed put/call from contract symbol: {put_call}")
                        except IndexError:
                            put_call = 'C'  # Default to Call
                    
                    try:
                        if expiry_date:
                            # Handle different date formats from API
                            if 'T' in expiry_date:
                                expiry = datetime.fromisoformat(expiry_date.replace('Z', '+00:00'))
                            else:
                                # Assume it's a date string like "2024-01-19"
                                expiry = datetime.strptime(expiry_date, "%Y-%m-%d")
                        else:
                            # No expiry date from API, parse from contract symbol
                            # Contract format: SYMBOL  YYMMDDCXXXXXXXX or SYMBOL  YYMMDDPXXXXXXXX
                            # Date is in positions 6-11 (YYMMDD)
                            if len(symbol) >= 12:
                                date_part = symbol[6:12]
                                expiry = datetime.strptime(date_part, '%y%m%d')
                                self.logger.debug(f"  Parsed expiry from contract symbol: {expiry.strftime('%Y-%m-%d')}")
                            else:
                                raise ValueError("Contract symbol too short to parse expiry")
                    except (ValueError, TypeError) as e:
                        self.logger.warning(f"  Could not parse expiry date: {e}")
                        expiry = datetime.utcnow() + timedelta(days=30)  # Default fallback
                    
                    options.append(OptionPosition(
                        symbol=underlying_symbol,
                        contract_symbol=symbol,
                        qty=int(qty),
                        avg_cost=avg_cost,
                        market_price=market_price,
                        strike=strike_price,
                        expiry=expiry,
                        put_call=put_call
                    ))
                elif asset_type == 'MUTUAL_FUND':
                    # Handle mutual funds (like money market funds)
                    description = instrument.get('description', '')
                    mutual_funds.append(MutualFundPosition(
                        symbol=symbol,
                        qty=int(qty),
                        avg_cost=avg_cost,
                        market_price=market_price,
                        description=description
                    ))
            
            self.logger.info(f"Processed {len(stocks)} stock positions, {len(options)} option positions, and {len(mutual_funds)} mutual fund positions")
            
            return AccountSnapshot(
                generated_at=datetime.utcnow(),
                cash=cash,
                buying_power=buying_power,
                stocks=stocks,
                options=options,
                mutual_funds=mutual_funds,
                official_liquidation_value=liquidation_value
            )
            
        except Exception as e:
            self.logger.error(f"Error fetching account data: {e}")
            self.logger.debug(f"Error type: {type(e)}")
            import traceback
            self.logger.debug(traceback.format_exc())
            raise
    
    def _print_json_structure(self, obj, indent=0, max_depth=3):
        """Helper to log JSON structure for debugging."""
        if indent > max_depth:
            self.logger.debug("  " * indent + "...")
            return
            
        if isinstance(obj, dict):
            for key, value in obj.items():
                if isinstance(value, (dict, list)):
                    self.logger.debug("  " * indent + f"{key}: {type(value).__name__}")
                    self._print_json_structure(value, indent + 1, max_depth)
                else:
                    self.logger.debug("  " * indent + f"{key}: {value}")
        elif isinstance(obj, list):
            self.logger.debug("  " * indent + f"List with {len(obj)} items")
            if obj and indent < max_depth:
                self.logger.debug("  " * indent + "First item:")
                self._print_json_structure(obj[0], indent + 1, max_depth)
