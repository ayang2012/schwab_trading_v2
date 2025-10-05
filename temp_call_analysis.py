# Temporary file for call analysis implementation
def _analyze_call_strikes_with_criteria(self, position: StockPosition, grade: str, 
                                       stock_data: Dict, options_data: Dict, criteria: Dict) -> List[Dict]:
    """Analyze call strikes using grade-based criteria and enhanced filtering."""
    calls = []
    current_price = stock_data.get('current_price', float(position.market_price))
    
    # Extract call option data from the response
    try:
        call_exp_date_map = options_data.get('callExpDateMap', {})
    except (AttributeError, KeyError):
        self.logger.warning(f"No call option data found for {position.symbol}")
        return []
    
    # Get preferred DTE range for this grade
    dte_range = criteria.get('preferred_dte_range', (1, 21))
    min_dte, max_dte = dte_range
    
    for exp_date_str, strike_map in call_exp_date_map.items():
        # Parse expiration date to calculate days to expiry
        try:
            # Format: "2025-10-03:1"
            exp_date = datetime.strptime(exp_date_str.split(':')[0], '%Y-%m-%d').date()
            days_to_expiry = (exp_date - datetime.now().date()).days
        except (ValueError, IndexError):
            continue
            
        # Filter by DTE range
        if not (min_dte <= days_to_expiry <= max_dte):
            continue
            
        for strike_str, option_list in strike_map.items():
            strike_price = float(strike_str)
            
            # Only consider strikes at or above current price (out-of-the-money or at-the-money)
            if strike_price < current_price * 0.95:  # Allow slight in-the-money for flexibility
                continue
                
            # Take the first option (should be the most liquid)
            if not option_list:
                continue
                
            option_data = option_list[0]
            
            # Calculate call metrics with grade-specific criteria
            call_metrics = self._calculate_call_metrics_with_criteria(
                position, grade, current_price, strike_price, option_data, 
                days_to_expiry, criteria
            )
            
            if call_metrics:
                calls.append(call_metrics)
    
    # Sort by attractiveness score (highest first)
    calls.sort(key=lambda x: x.get('attractiveness_score', 0), reverse=True)
    
    # Apply minimum score filter
    min_score = 30.0  # Minimum attractiveness score
    filtered_calls = [call for call in calls if call.get('attractiveness_score', 0) >= min_score]
    
    self.logger.debug(f"Found {len(calls)} call opportunities for {position.symbol}, {len(filtered_calls)} above minimum score")
    
    return filtered_calls[:10]  # Return top 10 opportunities

def _calculate_call_metrics_with_criteria(self, position: StockPosition, grade: str, current_price: float,
                                        strike_price: float, option_data: Dict, days_to_expiry: int, 
                                        criteria: Dict) -> Optional[Dict]:
    """Calculate call metrics with grade-specific filtering."""
    try:
        # Extract option data
        bid = option_data.get('bid', 0)
        ask = option_data.get('ask', 0)
        mark = option_data.get('mark', 0)
        open_interest = option_data.get('openInterest', 0)
        
        # Check bid-ask spread filtering
        if bid > 0 and ask > 0:
            spread_pct = ((ask - bid) / ((ask + bid) / 2)) * 100
            max_spread = criteria.get('max_bid_ask_spread_pct', 20.0)
            if spread_pct > max_spread:
                self.logger.debug(f"Skipping {position.symbol} ${strike_price} CALL: bid-ask spread {spread_pct:.1f}% > {max_spread}%")
                return None
        
        # Check minimum open interest requirement
        min_oi = criteria.get('min_open_interest', 0)
        if open_interest < min_oi:
            self.logger.debug(f"Skipping {position.symbol} ${strike_price} CALL: open interest {open_interest} < {min_oi}")
            return None
        
        # Use mark price, fallback to mid-point of bid/ask
        premium = mark if mark > 0 else (bid + ask) / 2
        if premium <= 0:
            return None
            
        # Check minimum premium percentage
        premium_pct = (premium / current_price) * 100
        min_premium_pct = criteria.get('min_premium_pct', 0.5)
        if premium_pct < min_premium_pct:
            return None
            
        # Calculate key metrics
        max_contracts = position.qty // 100
        premium_per_contract = premium * 100
        total_premium_income = premium_per_contract * max_contracts
        
        # Calculate returns
        annualized_return = (premium / current_price) * (365 / days_to_expiry) * 100
        
        # Check minimum annualized return
        min_annual_return = criteria.get('min_annualized_return', 15.0)
        if annualized_return < min_annual_return:
            return None
        
        # Calculate profit scenarios
        if strike_price > position.avg_cost:
            # Profit if assigned (selling above cost basis)
            capital_gains_per_share = strike_price - position.avg_cost
            total_profit_if_assigned = (premium + capital_gains_per_share) * (max_contracts * 100)
            max_profit_pct = ((premium + capital_gains_per_share) / position.avg_cost) * 100
        else:
            # Loss if assigned (selling below cost basis) but still collect premium
            capital_loss_per_share = position.avg_cost - strike_price
            total_profit_if_assigned = (premium - capital_loss_per_share) * (max_contracts * 100)
            max_profit_pct = ((premium - capital_loss_per_share) / position.avg_cost) * 100
        
        # Estimate assignment probability
        assignment_probability = self._estimate_assignment_probability(
            current_price, strike_price, days_to_expiry, option_type='CALL'
        )
        
        # Check maximum assignment probability
        max_assignment_prob = criteria.get('max_assignment_prob', 70.0)
        if assignment_probability > max_assignment_prob:
            return None
        
        # Calculate attractiveness score with grade-based adjustments
        attractiveness_score = self._calculate_call_attractiveness_score(
            premium_pct, annualized_return, days_to_expiry, assignment_probability, 
            grade, criteria, open_interest, spread_pct if bid > 0 and ask > 0 else 0
        )
        
        # Calculate bid-ask spread percentage for output
        bid_ask_spread_pct = 0
        if bid > 0 and ask > 0:
            bid_ask_spread_pct = ((ask - bid) / ((ask + bid) / 2)) * 100
        
        return {
            'symbol': position.symbol,
            'grade': grade,
            'strike_price': strike_price,
            'premium': premium,
            'bid': bid,
            'ask': ask,
            'mark': mark,
            'bid_ask_spread_pct': round(bid_ask_spread_pct, 1),
            'days_to_expiry': days_to_expiry,
            'expiration_date': option_data.get('expirationDate', ''),
            'premium_per_contract': premium_per_contract,
            'max_contracts': max_contracts,
            'total_premium_income': total_premium_income,
            'premium_pct': round(premium_pct, 2),
            'annualized_return_pct': round(annualized_return, 2),
            'assignment_probability_pct': round(assignment_probability, 1),
            'total_profit_if_assigned': round(total_profit_if_assigned, 2),
            'max_profit_pct': round(max_profit_pct, 2),
            'attractiveness_score': round(attractiveness_score, 1),
            'open_interest': open_interest,
            'volume': option_data.get('totalVolume', 0),
            'delta': option_data.get('delta', 0),
            'theta': option_data.get('theta', 0),
            'implied_volatility': option_data.get('volatility', 0),
            'criteria_applied': criteria
        }
        
    except Exception as e:
        self.logger.error(f"Error calculating call metrics for {position.symbol} {strike_price}: {e}")
        return None

def _calculate_call_attractiveness_score(self, premium_pct: float, annualized_return: float, 
                                       days_to_expiry: int, assignment_prob: float, grade: str,
                                       criteria: Dict, open_interest: int, bid_ask_spread: float) -> float:
    """Calculate attractiveness score for call options with grade-based adjustments."""
    score = 0.0
    
    # Premium percentage score (0-25 points)
    if premium_pct >= 3.0:
        score += 25
    elif premium_pct >= 2.0:
        score += 20
    elif premium_pct >= 1.5:
        score += 15
    elif premium_pct >= 1.0:
        score += 10
    else:
        score += premium_pct * 5
    
    # Annualized return score (0-30 points)
    if annualized_return >= 100:
        score += 30
    elif annualized_return >= 75:
        score += 25
    elif annualized_return >= 50:
        score += 20
    elif annualized_return >= 25:
        score += 15
    else:
        score += annualized_return * 0.3
    
    # Time to expiration score (0-15 points) - prefer shorter term
    if days_to_expiry <= 7:
        score += 15
    elif days_to_expiry <= 14:
        score += 12
    elif days_to_expiry <= 21:
        score += 8
    else:
        score += max(0, 15 - (days_to_expiry - 21) * 0.2)
    
    # Assignment probability score (0-15 points) - prefer lower assignment risk
    if assignment_prob <= 20:
        score += 15
    elif assignment_prob <= 40:
        score += 12
    elif assignment_prob <= 60:
        score += 8
    else:
        score += max(0, 15 - (assignment_prob - 60) * 0.3)
    
    # Liquidity score (0-10 points)
    if open_interest >= 100:
        score += 5
    elif open_interest >= 50:
        score += 3
    elif open_interest >= 25:
        score += 2
    
    if bid_ask_spread <= 5:
        score += 5
    elif bid_ask_spread <= 10:
        score += 3
    elif bid_ask_spread <= 15:
        score += 1
    
    # Grade-based adjustment (0-5 points)
    grade_bonus = {
        'EXCELLENT': 5,  # Bonus for quality stocks
        'GOOD': 3,
        'FAIR': 1,
        'POOR': 0
    }
    score += grade_bonus.get(grade, 0)
    
    return max(0, min(100, score))

def _estimate_assignment_probability(self, current_price: float, strike_price: float, 
                                   days_to_expiry: int, option_type: str = 'CALL') -> float:
    """Estimate assignment probability for call options."""
    if option_type == 'CALL':
        # For calls, assignment more likely if stock price is above strike
        moneyness = current_price / strike_price
        
        if moneyness >= 1.1:  # 10% or more in the money
            base_prob = 80
        elif moneyness >= 1.05:  # 5-10% in the money
            base_prob = 60
        elif moneyness >= 1.0:  # At the money or slightly in the money
            base_prob = 40
        elif moneyness >= 0.95:  # Slightly out of the money
            base_prob = 20
        else:  # Further out of the money
            base_prob = 5
    else:
        base_prob = 20  # Default for other types
    
    # Adjust for time to expiration
    if days_to_expiry <= 3:
        time_multiplier = 1.5
    elif days_to_expiry <= 7:
        time_multiplier = 1.2
    elif days_to_expiry <= 14:
        time_multiplier = 1.0
    else:
        time_multiplier = 0.8
    
    probability = base_prob * time_multiplier
    return max(0, min(100, probability))