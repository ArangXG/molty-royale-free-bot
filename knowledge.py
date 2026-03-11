import json
import os
import pandas as pd

DATA_DIR = "data"
COMBAT_HISTORY_FILE = f"{DATA_DIR}/combat_history.csv"
ENEMY_PROFILES_FILE = f"{DATA_DIR}/enemy_profiles.json"

def init_data():
    if not os.path.exists(DATA_DIR):
        os.makedirs(DATA_DIR)
        
    if not os.path.exists(COMBAT_HISTORY_FILE):
        # Create empty CSV with headers
        df = pd.DataFrame(columns=[
            "turn", "my_hp", "my_atk", "my_def", 
            "enemy_hp", "enemy_atk", "enemy_def", "enemy_kills", 
            "result_won"
        ])
        df.to_csv(COMBAT_HISTORY_FILE, index=False)
        
    if not os.path.exists(ENEMY_PROFILES_FILE):
        with open(ENEMY_PROFILES_FILE, 'w') as f:
            json.dump({}, f)

def load_enemy_profiles():
    if os.path.exists(ENEMY_PROFILES_FILE):
        with open(ENEMY_PROFILES_FILE, 'r') as f:
            return json.load(f)
    return {}

def save_enemy_profiles(profiles):
    with open(ENEMY_PROFILES_FILE, 'w') as f:
        json.dump(profiles, f, indent=4)

def update_enemy_profile(enemy_id: str, name: str, kills: int):
    profiles = load_enemy_profiles()
    if enemy_id not in profiles:
        profiles[enemy_id] = {"name": name, "max_kills_seen": kills, "encounters": 1}
    else:
        profiles[enemy_id]["encounters"] += 1
        if kills > profiles[enemy_id]["max_kills_seen"]:
            profiles[enemy_id]["max_kills_seen"] = kills
    save_enemy_profiles(profiles)

def log_combat_result(turn: int, my_stats: dict, enemy_stats: dict, enemy_kills: int, won: bool):
    new_row = pd.DataFrame([{
        "turn": turn,
        "my_hp": my_stats.get("hp", 100),
        "my_atk": my_stats.get("atk", 10),
        "my_def": my_stats.get("def", 5),
        "enemy_hp": enemy_stats.get("hp", 100),
        "enemy_atk": enemy_stats.get("atk", 10),
        "enemy_def": enemy_stats.get("def", 5),
        "enemy_kills": enemy_kills,
        "result_won": int(won)
    }])
    
    new_row.to_csv(COMBAT_HISTORY_FILE, mode='a', header=not os.path.exists(COMBAT_HISTORY_FILE), index=False)

def get_combat_history_df():
    if os.path.exists(COMBAT_HISTORY_FILE):
        return pd.read_csv(COMBAT_HISTORY_FILE)
    return pd.DataFrame()
