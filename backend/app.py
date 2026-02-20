import os
from datetime import datetime, timezone

from flask import Flask, jsonify
from flask_cors import CORS
import yahoo_fantasy_api as yfa
from yahoo_oauth import OAuth2


def load_dotenv(path=".env"):
    if not os.path.exists(path):
        return

    with open(path, "r", encoding="utf-8") as f:
        for raw_line in f:
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            os.environ.setdefault(key, value)


def required_env(name):
    value = os.getenv(name)
    if not value:
        raise ValueError(f"Missing required environment variable: {name}")
    return value


def build_context():
    load_dotenv()

    game_code = os.getenv("YAHOO_GAME_CODE", "nba")
    oauth_file = os.getenv("YAHOO_OAUTH_FILE", "oauth2.json")
    league_key = required_env("YAHOO_LEAGUE_KEY")
    team_key = required_env("YAHOO_TEAM_KEY")

    sc = OAuth2(None, None, from_file=oauth_file)
    gm = yfa.Game(sc, game_code)
    league = gm.to_league(league_key)
    team = league.to_team(team_key)
    return gm, league, team


def get_team_roster():
    _, _, team = build_context()
    return team.roster()


def to_float(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def calc_fantasy_value(stat_line):
    # Weighted score for 9-cat style value ranking.
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


def get_roster_with_values():
    _, league, team = build_context()
    roster = team.roster()
    ids = [p["player_id"] for p in roster if p.get("player_id")]
    stat_lines = league.player_stats(ids, "season") if ids else []
    stat_by_id = {s.get("player_id"): s for s in stat_lines}

    players = []
    for p in roster:
        pid = p.get("player_id")
        stats = stat_by_id.get(pid, {})
        value = calc_fantasy_value(stats)
        players.append(
            {
                "player_id": pid,
                "name": p.get("name", "Unknown"),
                "eligible_positions": p.get("eligible_positions", []),
                "status": p.get("status", ""),
                "fantasy_value": value,
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
        )

    players.sort(key=lambda x: x["fantasy_value"], reverse=True)
    return players


def get_trade_ideas():
    _, league, _ = build_context()
    roster_players = get_roster_with_values()
    roster_ids = {p["player_id"] for p in roster_players if p.get("player_id")}
    weakest = sorted(roster_players, key=lambda x: x["fantasy_value"])[:4]

    core_positions = ["PG", "SG", "SF", "PF", "C"]
    free_agents = []
    seen = set()
    for pos in core_positions:
        for player in league.free_agents(pos)[:12]:
            pid = player.get("player_id")
            if not pid or pid in seen or pid in roster_ids:
                continue
            seen.add(pid)
            free_agents.append(player)

    if not free_agents:
        return []

    fa_ids = [p["player_id"] for p in free_agents]
    fa_stat_lines = league.player_stats(fa_ids, "season")
    fa_stats_by_id = {s.get("player_id"): s for s in fa_stat_lines}

    fa_ranked = []
    for p in free_agents:
        pid = p.get("player_id")
        stats = fa_stats_by_id.get(pid, {})
        fa_ranked.append(
            {
                "player_id": pid,
                "name": p.get("name", "Unknown"),
                "eligible_positions": p.get("eligible_positions", []),
                "percent_owned": to_float(p.get("percent_owned")),
                "fantasy_value": calc_fantasy_value(stats),
            }
        )
    fa_ranked.sort(key=lambda x: x["fantasy_value"], reverse=True)

    ideas = []
    used_adds = set()
    for drop in weakest:
        drop_positions = set(drop.get("eligible_positions", []))
        best_add = None
        for add in fa_ranked:
            if add["player_id"] in used_adds:
                continue
            shared = drop_positions.intersection(set(add.get("eligible_positions", [])))
            if not shared:
                continue
            if add["fantasy_value"] <= drop["fantasy_value"]:
                continue
            best_add = (add, sorted(shared))
            break

        if best_add:
            add, shared_positions = best_add
            used_adds.add(add["player_id"])
            ideas.append(
                {
                    "drop_player": drop["name"],
                    "drop_value": drop["fantasy_value"],
                    "add_player": add["name"],
                    "add_value": add["fantasy_value"],
                    "improvement": round(add["fantasy_value"] - drop["fantasy_value"], 2),
                    "shared_positions": shared_positions,
                    "ownership_percent": add["percent_owned"],
                }
            )

    ideas.sort(key=lambda x: x["improvement"], reverse=True)
    return ideas[:6]


app = Flask(__name__)
CORS(app, resources={r"/api/*": {"origins": "*"}})


@app.get("/api/team")
def team():
    try:
        roster = get_team_roster()
        return jsonify({"team": roster}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.get("/api/team/value-stats")
def team_value_stats():
    try:
        players = get_roster_with_values()
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
                    },
                    "players": players,
                }
            ),
            200,
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.get("/api/team/trade-ideas")
def trade_ideas():
    try:
        ideas = get_trade_ideas()
        return (
            jsonify(
                {
                    "generated_at": datetime.now(timezone.utc).isoformat(),
                    "trade_ideas": ideas,
                }
            ),
            200,
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
