import os
from datetime import datetime, timezone

from flask import Flask, jsonify, request
from flask_cors import CORS
import injury_prediction
from player_value import apply_availability_adjustment, calc_fantasy_value, to_float
import trades as team_trades
import yahoo_fantasy_api as yfa
from yahoo_oauth import OAuth2


def load_dotenv(path=None):
    dotenv_path = path or os.path.join(os.path.dirname(__file__), ".env")
    if not os.path.exists(dotenv_path):
        return

    with open(dotenv_path, "r", encoding="utf-8") as f:
        for raw_line in f:
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            existing = os.environ.get(key)
            if existing is None or str(existing).strip() == "":
                os.environ[key] = value


def required_env(name):
    value = os.getenv(name)
    if not value:
        raise ValueError()
    return value


def resolve_local_path(path_value):
    if not path_value:
        return path_value
    if os.path.isabs(path_value):
        return path_value
    return os.path.join(os.path.dirname(__file__), path_value)


def league_prefix_env():
    return os.getenv("YAHOO_LEAGUE_INFO") or os.getenv("YAHOO_LEAGUE_KEY")


def split_league_prefix(league_key):
    parts = str(league_key).split(".")
    if len(parts) >= 2:
        return f"{parts[0]}.{parts[1]}"
    return str(league_key)


def format_league_key(league_id=None):
    env_league_key = league_prefix_env()
    if not env_league_key:
        raise ValueError()
    if not league_id:
        return env_league_key
    prefix = split_league_prefix(env_league_key)
    return f"{prefix}.{league_id}"


def format_team_key(league_key, team_number=None):
    if not team_number:
        return f"{league_key}.t.1"
    return f"{league_key}.t.{team_number}"


def resolve_context_args(league_id=None, team_number=None):
    load_dotenv()
    league_key = format_league_key(league_id=league_id)
    team_key = format_team_key(league_key=league_key, team_number=team_number)
    return league_key, team_key


def build_context(league_id=None, team_number=None, include_team=True):
    load_dotenv()

    game_code = os.getenv("YAHOO_GAME_CODE", "nba")
    oauth_file = resolve_local_path(os.getenv("YAHOO_OAUTH_FILE", "oauth2.json"))
    league_key, team_key = resolve_context_args(league_id=league_id, team_number=team_number)

    sc = OAuth2(None, None, from_file=oauth_file)
    gm = yfa.Game(sc, game_code)
    league = gm.to_league(league_key)
    if include_team:
        team = league.to_team(team_key)
        return gm, league, team
    return gm, league, None


def get_team_roster(league_id=None, team_number=None):
    _, _, team = build_context(league_id=league_id, team_number=team_number)
    return team.roster()


def build_player_value_payload(player, stats, risk_payload):
    fantasy_value = calc_fantasy_value(stats)
    risk_fields = apply_availability_adjustment(fantasy_value, risk_payload)

    return {
        "player_id": player.get("player_id"),
        "name": player.get("name", "Unknown"),
        "eligible_positions": player.get("eligible_positions", []),
        "status": player.get("status", ""),
        "fantasy_value": fantasy_value,
        "injury_risk_probability": risk_fields["injury_risk_probability"],
        "availability_probability": risk_fields["availability_probability"],
        "injury_risk_source": risk_fields["injury_risk_source"],
        "risk_adjusted_fantasy_value": risk_fields["risk_adjusted_fantasy_value"],
        "stats": {
            "FG%": to_float(stats.get("FG%")),
            "FT%": to_float(stats.get("FT%")),
            "3PTM": to_float(stats.get("3PTM")),
            "PTS": to_float(stats.get("PTS")),
            "REB": to_float(stats.get("REB")),
            "AST": to_float(stats.get("AST")),
            "ST": to_float(stats.get("ST")),
            "BLK": to_float(stats.get("BLK")),
            "TO": to_float(stats.get("TO")),
        },
    }


def compute_players_with_values(league, roster):
    ids = [p["player_id"] for p in roster if p.get("player_id")]
    stat_lines = league.player_stats(ids, "season") if ids else []
    stat_by_id = {s.get("player_id"): s for s in stat_lines}
    risk_result = injury_prediction.predict_injury_risk_for_players(roster)
    risk_map = risk_result.get("risk_by_player_name", {})

    players = []
    for player in roster:
        pid = player.get("player_id")
        stats = stat_by_id.get(pid, {})
        risk_payload = risk_map.get(player.get("name", "Unknown"), {})
        players.append(build_player_value_payload(player, stats, risk_payload))

    players.sort(key=lambda x: x["fantasy_value"], reverse=True)
    return players, risk_result


def get_roster_with_values(league_id=None, team_number=None):
    _, league, team = build_context(league_id=league_id, team_number=team_number)
    roster = team.roster()
    players, risk_result = compute_players_with_values(league, roster)
    return players, risk_result


app = Flask(__name__)
CORS(app, resources={r"/api/*": {"origins": "*"}})


@app.get("/api/team")
def team():
    league_id = request.args.get("league_id")
    team_number = request.args.get("team_number")
    roster = get_team_roster(league_id=league_id, team_number=team_number)
    return jsonify({"team": roster}), 200


@app.get("/api/team/value-stats")
def team_value_stats():
    league_id = request.args.get("league_id")
    team_number = request.args.get("team_number")
    players, risk_result = get_roster_with_values(league_id=league_id, team_number=team_number)
    if not players:
        return jsonify({"players": [], "summary": {}}), 200

    highest = players[0]
    lowest = players[-1]
    average = round(
        sum(player["fantasy_value"] for player in players) / len(players),
        2,
    )
    return (
        jsonify(
            {
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "summary": {
                    "highest_player": highest["name"],
                    "highest_value": highest["fantasy_value"],
                    "lowest_player": lowest["name"],
                    "lowest_value": lowest["fantasy_value"],
                    "average_value": average,
                    "risk_model_trained": risk_result.get("trained", False),
                    "risk_model_rows": risk_result.get("model_rows", 0),
                    "risk_model_note": risk_result.get("note", ""),
                },
                "players": players,
            }
        ),
        200,
    )


@app.post("/api/team/trade-compare")
def trade_compare():
    payload = request.get_json(silent=True) or {}
    trade_away = payload.get("trade_away", [])
    trade_for = payload.get("trade_for", [])
    league_id = payload.get("league_id") or request.args.get("league_id")
    team_number = payload.get("team_number") or request.args.get("team_number")
    league_key, team_key = resolve_context_args(league_id=league_id, team_number=team_number)
    result = team_trades.compare_trade_values(
        trade_away_names=trade_away,
        receive_names=trade_for,
        league_key=league_key,
        team_key=team_key,
    )
    return jsonify({"generated_at": datetime.now(timezone.utc).isoformat(), **result}), 200


@app.get("/api/team/injury-prediction-values")
def team_injury_prediction_values():
    league_id = request.args.get("league_id")
    team_number = request.args.get("team_number")
    players, risk_result = get_roster_with_values(league_id=league_id, team_number=team_number)
    ordered = sorted(players, key=lambda x: x["risk_adjusted_fantasy_value"], reverse=True)
    return (
        jsonify(
            {
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "model": {
                    "trained": risk_result.get("trained", False),
                    "rows": risk_result.get("model_rows", 0),
                    "note": risk_result.get("note", ""),
                },
                "players": ordered,
            }
        ),
        200,
    )


@app.get("/api/league/teams")
def league_teams():
    league_id = request.args.get("league_id")
    league_key, _ = resolve_context_args(league_id=league_id, team_number=None)
    _, league, _ = build_context(league_id=league_id, team_number=None, include_team=False)
    teams = team_trades.get_league_teams(league)
    payload = []
    for team in teams:
        team_key = team.get("team_key", "")
        team_number = ""
        if ".t." in str(team_key):
            team_number = str(team_key).split(".t.")[-1]
        elif str(team_key):
            team_number = str(team_key).split(".")[-1]

        team_name = str(team.get("name", "")).strip()
        payload.append(
            {
                "team_key": team_key,
                "team_name": team_name,
                "team_number": team_number,
            }
        )
    return jsonify({"league_key": league_key, "teams": payload}), 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
