"""Live trading monitor configuration."""

# ========================================
# WATCHLIST CONFIGURATION
# ========================================

# Main watchlist - stocks to monitor for technical analysis
WATCHLIST_STOCKS = ["AAL","GOOG","AMZN","UBER","AMD","MU","INTC","QCOM","BAC","WFC","COP","OXY","SOFI","ACHR"]

# ========================================
# ALERT THRESHOLDS
# ========================================

# RSI thresholds for alerts
RSI_OVERSOLD_THRESHOLD = 30
RSI_OVERBOUGHT_THRESHOLD = 70

# Price change percentage thresholds for alerts
PRICE_CHANGE_ALERT_THRESHOLD = 3.0  # Alert if stock moves more than 3%

# Volume spike threshold (multiplier of average volume)
VOLUME_SPIKE_THRESHOLD = 2.0  # Alert if volume is 2x average

# ========================================
# TECHNICAL ANALYSIS SETTINGS
# ========================================

# Moving average periods
SMA_SHORT_PERIOD = 20
SMA_LONG_PERIOD = 50

# MACD settings
MACD_FAST = 12
MACD_SLOW = 26
MACD_SIGNAL = 9

# Bollinger Bands settings
BB_PERIOD = 20
BB_STD_DEV = 2

# ========================================
# MONITORING SETTINGS
# ========================================

# Market hours (in 24-hour format)
MARKET_OPEN_HOUR = 6   # 6:30 AM (adjusted for your preference)
MARKET_OPEN_MINUTE = 30
MARKET_CLOSE_HOUR = 13  # 1:00 PM (adjusted for your preference)  
MARKET_CLOSE_MINUTE = 0

# Default monitoring interval (seconds)
DEFAULT_MONITORING_INTERVAL = 20

# Maximum number of alerts to display per cycle
MAX_ALERTS_DISPLAY = 5

# ========================================
# DATA STORAGE SETTINGS
# ========================================

# Default output directories
DEFAULT_OUTPUT_DIR = "data/account"          # Account snapshots and tracking
WATCHLIST_OUTPUT_DIR = "data/stock_watchlist"  # Watchlist technical analysis
RANKING_OUTPUT_DIR = "data/stock_ranking"      # Wheel strategy rankings

# Watchlist analysis filename pattern
WATCHLIST_ANALYSIS_PATTERN = "watchlist_analysis_{timestamp}.json"

# Data storage strategy for wheel trading
STORE_EVERY_ITERATION = False  # Set to True only for debugging
STORE_END_OF_DAY_ONLY = True   # Store comprehensive data at market close
STORE_ALERTS_ONLY = True       # Store when significant alerts trigger
STORE_WEEKLY_SUMMARY = True    # Store weekly technical summaries

# Storage intervals
STORE_INTERVAL_MINUTES = 60    # Store every 60 minutes during market hours
CLEANUP_OLD_DATA_DAYS = 3      # Keep detailed data for 3 days

# Wheel strategy specific settings
WHEEL_TARGET_DELTA = 0.30      # Target delta for cash-secured puts
WHEEL_MIN_PREMIUM = 0.50       # Minimum premium per contract ($50)
WHEEL_MAX_DTE = 10             # Maximum days to expiration
WHEEL_MIN_DTE = 1              # Minimum days to expiration

# Technical conditions for wheel entry
WHEEL_RSI_MAX = 60             # Don't sell puts if RSI > 60 (too bullish)
WHEEL_RSI_MIN = 25             # Don't sell puts if RSI < 25 (falling knife)
WHEEL_SUPPORT_DISTANCE = 0.05  # Strike should be 5% below support level

# ========================================
# WHEEL STRATEGY RANKING SYSTEM
# ========================================

# Scoring weights for put selling opportunities (total = 100 points)
PUT_RANKING_WEIGHTS = {
    'rsi_score': 25,           # RSI in optimal range (30-50 ideal)
    'price_stability': 20,     # Low volatility/stable price action
    'support_level': 15,       # Distance from support levels
    'volume_score': 10,        # Adequate volume for liquidity
    'trend_score': 15,         # Overall trend direction
    'bollinger_position': 10,  # Position within Bollinger Bands
    'macd_score': 5           # MACD momentum indicators
}

# Scoring weights for call selling opportunities (total = 100 points)
CALL_RANKING_WEIGHTS = {
    'rsi_score': 25,           # RSI overbought (60-80 ideal)
    'resistance_level': 20,    # Near resistance levels
    'price_momentum': 15,      # Recent upward momentum
    'volume_score': 10,        # Volume supporting move
    'trend_exhaustion': 15,    # Signs of trend exhaustion
    'bollinger_position': 10,  # Upper Bollinger Band proximity
    'macd_score': 5           # MACD divergence signals
}

# RSI ranges for put selling (ideal conditions)
PUT_RSI_EXCELLENT = (30, 45)    # Sweet spot for selling puts
PUT_RSI_GOOD = (25, 55)         # Acceptable range
PUT_RSI_FAIR = (20, 60)         # Marginal but workable
PUT_RSI_AVOID = (0, 20, 65, 100) # Too extreme (falling knife or too bullish)

# RSI ranges for call selling (ideal conditions) 
CALL_RSI_EXCELLENT = (65, 75)   # Sweet spot for selling calls
CALL_RSI_GOOD = (60, 80)        # Acceptable range  
CALL_RSI_FAIR = (55, 85)        # Marginal but workable
CALL_RSI_AVOID = (0, 50, 90, 100) # Too low or extremely overbought

# Price stability thresholds (daily price change %)
STABILITY_EXCELLENT = 1.0       # < 1% change = very stable
STABILITY_GOOD = 2.0            # < 2% change = stable
STABILITY_FAIR = 3.5            # < 3.5% change = acceptable
STABILITY_POOR = 5.0            # > 5% change = too volatile

# Volume ratio thresholds (current vs average)
VOLUME_EXCELLENT = (0.8, 2.0)   # Good liquidity range
VOLUME_GOOD = (0.5, 3.0)        # Acceptable range
VOLUME_FAIR = (0.3, 4.0)        # Marginal liquidity
VOLUME_POOR = (0.0, 0.3, 4.0, 10.0)  # Too low or too high

# Ranking display settings
MAX_PUT_RANKINGS = 5            # Show top 5 put candidates
MAX_CALL_RANKINGS = 5           # Show top 5 call candidates
SHOW_RANKING_BREAKDOWN = True   # Show detailed score breakdown
MIN_RANKING_SCORE = 35          # Minimum score to show in rankings

# Grade thresholds
RANK_EXCELLENT = 80    # 80+ points = Excellent opportunity
RANK_GOOD = 65        # 65-79 points = Good opportunity  
RANK_FAIR = 50        # 50-64 points = Fair opportunity
RANK_POOR = 35        # 35-49 points = Poor opportunity
                      # <35 points = Avoid (don't show)

# ========================================
# ALERT CATEGORIES
# ========================================

# Define which types of alerts to enable
ENABLE_RSI_ALERTS = True
ENABLE_PRICE_CHANGE_ALERTS = True
ENABLE_VOLUME_ALERTS = True
ENABLE_TECHNICAL_BREAKOUT_ALERTS = True



# You can switch which watchlist to use by changing this
ACTIVE_WATCHLIST = WATCHLIST_STOCKS  # Change to GROWTH_STOCKS, VALUE_STOCKS, etc.