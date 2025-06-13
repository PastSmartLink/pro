from typing import List, Dict, Any, Optional
from itertools import combinations
import logging

logger = logging.getLogger(__name__)

def american_to_decimal(american_odds: Optional[int]) -> Optional[float]:
    if american_odds is None:
        return None
    if not isinstance(american_odds, (int, float)):
        try:
            american_odds = float(american_odds)
        except (ValueError, TypeError):
            logger.warning(f"Invalid american_odds: {american_odds}")
            return None
    
    if american_odds is None:
        logger.warning("american_odds is None")
        return None
    american_odds_float = float(american_odds)
    if american_odds_float == 0:
        logger.warning("Zero odds provided")
        return None
    if american_odds_float > 0:
        return (american_odds_float / 100.0) + 1.0
    else:
        return (100.0 / abs(american_odds_float)) + 1.0

def identify_potential_parlay_legs(
    matches: List[Dict[str, Any]], 
    predictions_map: Dict[str, Dict[str, Any]],
    sentiments_map: Dict[str, Dict[str, Any]], 
    min_confidence_threshold: float = 0.60 
) -> List[Dict[str, Any]]:
    potential_legs = []
    for match in matches:
        game_id = match.get('game_id')
        if not game_id:
            logger.debug(f"Skipping match with missing game_id: {match}")
            continue

        prediction = predictions_map.get(game_id, {})
        if prediction.get('error') or not prediction.get('winner') or prediction.get('confidence_score') is None:
            logger.debug(f"Skipping game_id {game_id}: Invalid prediction {prediction}")
            continue
        
        try:
            confidence = float(prediction.get('confidence_score', 0.0))
        except (ValueError, TypeError):
            logger.debug(f"Skipping game_id {game_id}: Invalid confidence {prediction.get('confidence_score')}")
            continue

        if confidence < min_confidence_threshold:
            logger.debug(f"Skipping game_id {game_id}: Confidence {confidence} below threshold {min_confidence_threshold}")
            continue

        winner = prediction.get('winner')
        home_team = match.get('home_team')
        away_team = match.get('away_team')

        home_odds_decimal = match.get('home_odds')
        away_odds_decimal = match.get('away_odds')
        draw_odds_decimal = match.get('draw_odds')

        selected_odds = None
        selection = None
        
        normalized_winner = str(winner).lower().strip()
        normalized_home_team = str(home_team).lower().strip()
        normalized_away_team = str(away_team).lower().strip()

        if normalized_winner == normalized_home_team and home_odds_decimal and home_odds_decimal >= 1.0:
            selected_odds = home_odds_decimal
            selection = home_team
        elif normalized_winner == normalized_away_team and away_odds_decimal and away_odds_decimal >= 1.0:
            selected_odds = away_odds_decimal
            selection = away_team
        elif normalized_winner == 'draw' and draw_odds_decimal and draw_odds_decimal >= 1.0:
            selected_odds = draw_odds_decimal
            selection = 'Draw'

        if selected_odds and selection:
            potential_legs.append({
                'game_id': game_id,
                'sport': match.get('sport_display', 'Unknown Sport'),
                'match': f"{home_team or 'Home'} vs {away_team or 'Away'}",
                'selection': selection,
                'odds': selected_odds,
                'confidence': confidence
            })
        else:
            logger.debug(f"Skipping game_id {game_id}: No valid odds/selection for winner {winner}")

    if not potential_legs:
        logger.info("No potential parlay legs identified")
    return potential_legs

def generate_parlay_combinations(
    potential_legs: List[Dict[str, Any]], 
    min_legs_count: int = 2, 
    max_legs_count: int = 4,
    max_parlays_per_leg_count: int = 5
) -> Dict[str, List[Dict[str, Any]]]:
    
    if not potential_legs or len(potential_legs) < min_legs_count:
        logger.info(f"Cannot generate parlays: {len(potential_legs)} legs available, minimum {min_legs_count} required")
        return {}
    
    parlay_combinations_by_leg_str: Dict[str, List[Dict[str, Any]]] = {}
    actual_max_legs = min(max_legs_count, len(potential_legs))

    for leg_count in range(min_legs_count, actual_max_legs + 1):
        leg_count_str = f"{leg_count}-Leg"
        current_leg_parlays = []
        
        for combo_tuple in combinations(potential_legs, leg_count):
            combo = list(combo_tuple)
            if len(set(leg['game_id'] for leg in combo)) != leg_count:
                continue

            parlay_odds = 1.0
            valid_combo = True
            for leg in combo:
                leg_odds = leg.get('odds')
                if not isinstance(leg_odds, (int, float)) or leg_odds < 1.0:
                    logger.debug(f"Invalid odds in combo: {leg_odds}")
                    valid_combo = False
                    break
                parlay_odds *= leg_odds
            
            if not valid_combo:
                continue

            total_confidence = sum(float(leg.get('confidence', 0.0)) for leg in combo)
            average_confidence = total_confidence / len(combo) if len(combo) > 0 else 0.0
            
            current_leg_parlays.append({
                'legs': combo,
                'combined_odds': round(parlay_odds, 2),
                'confidence': round(average_confidence, 3)
            })
        
        if current_leg_parlays:
            current_leg_parlays.sort(key=lambda x: (-x['confidence'], -x['combined_odds']))
            parlay_combinations_by_leg_str[leg_count_str] = current_leg_parlays[:max_parlays_per_leg_count]
    
    if not parlay_combinations_by_leg_str:
        logger.info("No parlay combinations generated")
    return parlay_combinations_by_leg_str