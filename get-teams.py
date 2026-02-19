import os

import pandas as pd
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


load_dotenv()

game_code = os.getenv("YAHOO_GAME_CODE", "nba")
oauth_file = os.getenv("YAHOO_OAUTH_FILE", "oauth2.json")
league_key = required_env("YAHOO_LEAGUE_KEY")
team_key = required_env("YAHOO_TEAM_KEY")

sc = OAuth2(None, None, from_file=oauth_file)
gm = yfa.Game(sc, game_code)
league = gm.to_league(league_key)
team = league.to_team(team_key)

roster = team.roster()
df_roster = pd.DataFrame(roster)

columns = ["name", "eligible_positions"]
available = [col for col in columns if col in df_roster.columns]
print(df_roster[available] if available else df_roster)
