import numpy as np
import pandas as pd
from nba_api.stats.endpoints import playergamelog
from nba_api.stats.static import players as nba_players
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline


DEFAULT_SEASONS = ["2022-23", "2023-24", "2024-25", "2025-26"]
MIN_ROWS_TO_TRAIN = 25
DEFAULT_RISK = 0.2
_PLAYER_ID_CACHE = {}
_PLAYER_LOG_CACHE = {}


def _to_float(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _minute_to_float(value):
    if value is None:
        return 0.0
    as_text = str(value)
    if ":" in as_text:
        parts = as_text.split(":", 1)
        return _to_float(parts[0]) + (_to_float(parts[1]) / 60.0)
    return _to_float(value)


def _player_name_candidates(full_name):
    text = " ".join(str(full_name).split())
    if not text:
        return []
    candidates = [text]
    normalized = text.replace(".", "")
    if normalized != text:
        candidates.append(normalized)
    return candidates


def resolve_nba_player_id(player_name):
    if not player_name:
        return None
    if player_name in _PLAYER_ID_CACHE:
        return _PLAYER_ID_CACHE[player_name]

    candidates = _player_name_candidates(player_name)
    for name in candidates:
        matches = nba_players.find_players_by_full_name(name)
        exact = [m for m in matches if m.get("full_name", "").lower() == name.lower()]
        if exact:
            _PLAYER_ID_CACHE[player_name] = int(exact[0]["id"])
            return _PLAYER_ID_CACHE[player_name]
        if matches:
            _PLAYER_ID_CACHE[player_name] = int(matches[0]["id"])
            return _PLAYER_ID_CACHE[player_name]
    _PLAYER_ID_CACHE[player_name] = None
    return None


def fetch_player_log(player_id, season):
    cache_key = f"{player_id}:{season}"
    if cache_key in _PLAYER_LOG_CACHE:
        return _PLAYER_LOG_CACHE[cache_key]

    try:
        endpoint = playergamelog.PlayerGameLog(player_id=player_id, season=season, timeout=15)
        data_frames = endpoint.get_data_frames()
        if not data_frames:
            _PLAYER_LOG_CACHE[cache_key] = pd.DataFrame()
            return _PLAYER_LOG_CACHE[cache_key]
        frame = data_frames[0].copy()
        if frame.empty:
            _PLAYER_LOG_CACHE[cache_key] = frame
            return _PLAYER_LOG_CACHE[cache_key]

        frame["GAME_DATE"] = pd.to_datetime(frame["GAME_DATE"], errors="coerce")
        frame = frame.dropna(subset=["GAME_DATE"]).sort_values("GAME_DATE").reset_index(drop=True)
        frame["MIN_FLOAT"] = frame["MIN"].apply(_minute_to_float)
        _PLAYER_LOG_CACHE[cache_key] = frame
        return _PLAYER_LOG_CACHE[cache_key]
    except Exception:
        _PLAYER_LOG_CACHE[cache_key] = pd.DataFrame()
        return _PLAYER_LOG_CACHE[cache_key]


def build_training_rows(game_log, sample_weight=1.0):
    if game_log is None or game_log.empty or len(game_log) < 8:
        return [], None

    rows = []
    latest_features = None

    for index in range(1, len(game_log)):
        prev_slice = game_log.iloc[:index]
        current = game_log.iloc[index]
        prev_game = game_log.iloc[index - 1]

        prev_date = prev_game["GAME_DATE"]
        current_date = current["GAME_DATE"]
        days_rest = float(max((current_date - prev_date).days - 1, 0))
        is_back_to_back = 1.0 if days_rest == 0 else 0.0

        window_14 = prev_slice[prev_slice["GAME_DATE"] >= (current_date - pd.Timedelta(days=14))]
        games_last_14d = float(len(window_14))
        minutes_last_14d = float(window_14["MIN_FLOAT"].sum())
        avg_minutes_5 = float(prev_slice.tail(5)["MIN_FLOAT"].mean()) if len(prev_slice) else 0.0
        minutes_last_game = _to_float(prev_game["MIN_FLOAT"])
        season_minutes = float(prev_slice["MIN_FLOAT"].sum())
        season_games = float(len(prev_slice))

        if index < len(game_log) - 1:
            next_game = game_log.iloc[index + 1]
            next_gap_days = float((next_game["GAME_DATE"] - current_date).days)
            # Proxy label: a long gap to the next team game often reflects unavailability.
            miss_next_game = 1.0 if next_gap_days >= 4 else 0.0
        else:
            miss_next_game = 0.0

        row = {
            "minutes_last_game": minutes_last_game,
            "days_rest": days_rest,
            "is_back_to_back": is_back_to_back,
            "games_last_14d": games_last_14d,
            "minutes_last_14d": minutes_last_14d,
            "avg_minutes_last_5": avg_minutes_5,
            "season_minutes": season_minutes,
            "season_games_played": season_games,
            "target_miss_next": miss_next_game,
            "sample_weight": sample_weight,
        }
        rows.append(row)

        latest_features = {
            "minutes_last_game": minutes_last_game,
            "days_rest": days_rest,
            "is_back_to_back": is_back_to_back,
            "games_last_14d": games_last_14d,
            "minutes_last_14d": minutes_last_14d,
            "avg_minutes_last_5": avg_minutes_5,
            "season_minutes": season_minutes,
            "season_games_played": season_games,
        }

    return rows, latest_features


def _status_default_risk(status):
    status_text = (status or "").upper()
    if any(marker in status_text for marker in ("INJ", "IL", "O", "DTD")):
        return 0.55
    return DEFAULT_RISK


def _normalize_seasons(seasons):
    if seasons is None:
        return list(DEFAULT_SEASONS)
    if isinstance(seasons, str):
        return [seasons]
    values = [str(item) for item in seasons if item]
    return values if values else list(DEFAULT_SEASONS)


def _season_weights(seasons):
    total = len(seasons)
    weights = {}
    for idx, season in enumerate(seasons):
        # Older seasons get smaller weight, latest gets highest.
        weights[season] = 1.0 + (idx / max(total - 1, 1))
    return weights


def predict_injury_risk_for_players(players, seasons=None):
    seasons = _normalize_seasons(seasons)
    season_weight = _season_weights(seasons)

    feature_columns = [
        "minutes_last_game",
        "days_rest",
        "is_back_to_back",
        "games_last_14d",
        "minutes_last_14d",
        "avg_minutes_last_5",
        "season_minutes",
        "season_games_played",
    ]

    train_rows = []
    latest_feature_rows = {}
    default_risk = {}

    for player in players:
        name = player.get("name", "Unknown")
        default_risk[name] = _status_default_risk(player.get("status", ""))
        nba_player_id = resolve_nba_player_id(name)
        if not nba_player_id:
            continue

        chosen_latest = None
        for season in seasons:
            game_log = fetch_player_log(nba_player_id, season=season)
            rows, latest = build_training_rows(game_log, sample_weight=season_weight.get(season, 1.0))
            if rows:
                train_rows.extend(rows)
            if latest:
                chosen_latest = latest
        if chosen_latest:
            latest_feature_rows[name] = chosen_latest

    output = {}
    for player in players:
        name = player.get("name", "Unknown")
        output[name] = {
            "injury_risk_probability": round(default_risk.get(name, DEFAULT_RISK), 4),
            "availability_probability": round(1.0 - default_risk.get(name, DEFAULT_RISK), 4),
            "source": "default",
        }

    if len(train_rows) < MIN_ROWS_TO_TRAIN:
        return {
            "risk_by_player_name": output,
            "trained": False,
            "model_rows": len(train_rows),
            "note": "",
        }

    train_frame = pd.DataFrame(train_rows)
    x_train = train_frame[feature_columns]
    y_train = train_frame["target_miss_next"].astype(int)
    sample_weight = train_frame["sample_weight"].astype(float).values

    if y_train.nunique() < 2:
        return {
            "risk_by_player_name": output,
            "trained": False,
            "model_rows": len(train_rows),
            "note": "",
        }

    model = Pipeline(
        [
            ("imputer", SimpleImputer(strategy="median")),
            (
                "rf",
                RandomForestClassifier(
                    n_estimators=350,
                    max_depth=10,
                    min_samples_leaf=3,
                    random_state=42,
                    n_jobs=-1,
                ),
            ),
        ]
    )
    model.fit(x_train, y_train, rf__sample_weight=sample_weight)

    for name, row in latest_feature_rows.items():
        input_frame = pd.DataFrame([row], columns=feature_columns)
        prob = float(model.predict_proba(input_frame)[0][1])
        prob = float(np.clip(prob, 0.02, 0.95))
        output[name] = {
            "injury_risk_probability": round(prob, 4),
            "availability_probability": round(1.0 - prob, 4),
            "source": "random_forest",
        }

    return {
        "risk_by_player_name": output,
        "trained": True,
        "model_rows": len(train_rows),
        "note": f"Model trained using seasons {', '.join(seasons)} with recency weighting.",
    }
