import os

from player_value import calc_fantasy_value, to_float
import yahoo_fantasy_api as yfa
from yahoo_oauth import OAuth2


def load_dotenv(path=None):
    dotenv_path = path or os.path.join(os.path.dirname(__file__), ".env")
    if not os.path.exists(dotenv_path):
        return

    with open(dotenv_path, "r", encoding="utf-8") as file_handle:
        for raw_line in file_handle:
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            env_key = key.strip()
            env_value = value.strip().strip('"').strip("'")
            existing = os.environ.get(env_key)
            if existing is None or str(existing).strip() == "":
                os.environ[env_key] = env_value


def resolve_local_path(path_value):
    if not path_value:
        return path_value
    if os.path.isabs(path_value):
        return path_value
    return os.path.join(os.path.dirname(__file__), path_value)


def league_prefix_env():
    load_dotenv()
    return os.getenv("YAHOO_LEAGUE_INFO") or os.getenv("YAHOO_LEAGUE_KEY")


def build_context(league_key=None, team_key=None):
    load_dotenv()

    game_code = os.getenv("YAHOO_GAME_CODE", "nba")
    oauth_file = resolve_local_path(os.getenv("YAHOO_OAUTH_FILE", "oauth2.json"))
    final_league_key = league_key or league_prefix_env()
    if not final_league_key:
        raise ValueError()
    final_team_key = team_key or f"{final_league_key}.t.1"

    oauth = OAuth2(None, None, from_file=oauth_file)
    game = yfa.Game(oauth, game_code)
    league = game.to_league(final_league_key)
    return league, final_team_key


def get_league_teams(league):
    raw = league.teams() if callable(getattr(league, "teams", None)) else getattr(league, "teams", {})

    def extract_name(value):
        if isinstance(value, str):
            return value.strip()
        if isinstance(value, dict):
            if isinstance(value.get("name"), str):
                return value.get("name", "").strip()
            if isinstance(value.get("team_name"), str):
                return value.get("team_name", "").strip()
            for nested in value.values():
                result = extract_name(nested)
                if result:
                    return result
            return ""
        if isinstance(value, list):
            for nested in value:
                result = extract_name(nested)
                if result:
                    return result
            return ""
        return ""

    teams = []
    if isinstance(raw, dict):
        for team_key, team_data in raw.items():
            parsed_team_key = team_key
            if isinstance(team_data, dict) and team_data.get("team_key"):
                parsed_team_key = str(team_data.get("team_key"))
            parsed_name = extract_name(team_data)
            if not parsed_name:
                parsed_name = "Team"
            teams.append({"team_key": str(parsed_team_key), "name": parsed_name})
    elif isinstance(raw, list):
        for item in raw:
            if isinstance(item, dict):
                team_key = item.get("team_key") or item.get("team_id")
                name = extract_name(item) or str(team_key or "")
                if team_key:
                    teams.append({"team_key": str(team_key), "name": str(name)})
    return teams


def fetch_team_players_with_stats(league, team_key):
    team = league.to_team(team_key)
    roster = team.roster()
    player_ids = [player["player_id"] for player in roster if player.get("player_id")]
    stat_lines = league.player_stats(player_ids, "season") if player_ids else []
    stat_by_id = {line.get("player_id"): line for line in stat_lines}

    players = []
    for player in roster:
        player_id = player.get("player_id")
        stats = stat_by_id.get(player_id, {})
        players.append(
            {
                "player_id": player_id,
                "name": player.get("name", "Unknown"),
                "fantasy_value": calc_fantasy_value(stats),
            }
        )
    return players


def _normalize_name(value):
    return " ".join(str(value or "").strip().lower().split())


def _parse_names(values):
    if isinstance(values, str):
        parts = values.split(",")
    elif isinstance(values, list):
        parts = values
    else:
        parts = []
    return [str(item).strip() for item in parts if str(item).strip()]


def _build_player_value_index(league_key=None, team_key=None):
    league, _ = build_context(league_key=league_key, team_key=team_key)
    teams = get_league_teams(league)
    index = {}

    for team_meta in teams:
        current_team_key = team_meta.get("team_key")
        if not current_team_key:
            continue
        players = fetch_team_players_with_stats(league, current_team_key)
        for player in players:
            name = player.get("name")
            if not name:
                continue
            index[_normalize_name(name)] = {
                "name": name,
                "fantasy_value": round(to_float(player.get("fantasy_value")), 2),
            }
    return index


def compare_trade_values(trade_away_names, receive_names, league_key=None, team_key=None):
    away_names = _parse_names(trade_away_names)
    receive_names = _parse_names(receive_names)
    value_index = _build_player_value_index(league_key=league_key, team_key=team_key)

    def resolve(names):
        found = []
        missing = []
        total = 0.0
        for raw_name in names:
            item = value_index.get(_normalize_name(raw_name))
            if not item:
                missing.append(raw_name)
                continue
            found.append(item)
            total += to_float(item.get("fantasy_value"))
        return {"players": found, "missing": missing, "total": round(total, 2)}

    away = resolve(away_names)
    receive = resolve(receive_names)
    delta = round(receive["total"] - away["total"], 2)
    winner = "even"
    if delta > 0:
        winner = "your_side"
    if delta < 0:
        winner = "other_side"

    return {
        "trade_away": away,
        "trade_for": receive,
        "delta": delta,
        "winner": winner,
    }
