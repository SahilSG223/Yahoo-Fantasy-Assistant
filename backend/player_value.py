def to_float(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def calc_fantasy_value(stat_line):
    return round(
        (to_float(stat_line.get("FG%")) * 15)
        + (to_float(stat_line.get("FT%")) * 12)
        + (to_float(stat_line.get("3PTM")) * 1.2)
        + (to_float(stat_line.get("PTS")) * 0.4)
        + (to_float(stat_line.get("REB")) * 0.7)
        + (to_float(stat_line.get("AST")) * 0.9)
        + (to_float(stat_line.get("ST")) * 2.5)
        + (to_float(stat_line.get("BLK")) * 2.2)
        - (to_float(stat_line.get("TO")) * 1.0),
        2,
    )


def apply_availability_adjustment(fantasy_value, risk_payload):
    injury_risk = to_float((risk_payload or {}).get("injury_risk_probability"))
    limited_minutes_factor = max(0.75, 1.0 - (0.35 * injury_risk))
    adjusted_value = round(fantasy_value * (1.0 - injury_risk) * limited_minutes_factor, 2)
    return {
        "injury_risk_probability": round(injury_risk, 4),
        "availability_probability": round(1.0 - injury_risk, 4),
        "injury_risk_source": (risk_payload or {}).get("source", "default"),
        "risk_adjusted_fantasy_value": adjusted_value,
    }
