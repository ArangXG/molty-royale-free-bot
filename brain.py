import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
import numpy as np
import os
from knowledge import COMBAT_HISTORY_FILE

class MLBrain:
    def __init__(self):
        self.model = LogisticRegression(class_weight='balanced')
        self.scaler = StandardScaler()
        self.is_trained = False
        
        # We start with some dummy data to ensure the model can always predict
        # This gives a baseline where higher stats = win, lower stats = loss.
        self._init_baseline_model()

    def _init_baseline_model(self):
        # Dummy data simulating obvious wins and losses to seed the model
        baseline_X = pd.DataFrame([
            {"turn": 5, "my_hp": 100, "my_atk": 25, "my_def": 10, "enemy_hp": 10, "enemy_atk": 5, "enemy_def": 1, "enemy_kills": 0}, # Definite Win
            {"turn": 50, "my_hp": 10, "my_atk": 10, "my_def": 5, "enemy_hp": 100, "enemy_atk": 30, "enemy_def": 15, "enemy_kills": 5}, # Definite Loss
            {"turn": 20, "my_hp": 80, "my_atk": 15, "my_def": 5, "enemy_hp": 20, "enemy_atk": 10, "enemy_def": 2, "enemy_kills": 1}, # Probable Win
            {"turn": 40, "my_hp": 30, "my_atk": 10, "my_def": 5, "enemy_hp": 90, "enemy_atk": 20, "enemy_def": 5, "enemy_kills": 3}, # Probable Loss
        ])
        baseline_y = np.array([1, 0, 1, 0])
        
        self.scaler.fit(baseline_X)
        X_scaled = self.scaler.transform(baseline_X)
        self.model.fit(X_scaled, baseline_y)
        self.is_trained = True

    def train_from_history(self):
        """Retrains the model using the actual combat history data if enough exists."""
        if not os.path.exists(COMBAT_HISTORY_FILE):
            return
            
        df = pd.read_csv(COMBAT_HISTORY_FILE)
        
        # Need at least a few real samples to retrain effectively, and both classes (win/loss)
        if len(df) > 5 and len(df['result_won'].unique()) > 1:
            X = df.drop(columns=['result_won'])
            y = df['result_won']
            
            # Re-fit scaler and model
            self.scaler.fit(X)
            X_scaled = self.scaler.transform(X)
            self.model.fit(X_scaled, y)
            self.is_trained = True
            print("MLBrain: Successfully retrained model based on historical data.")

    def predict_win_probability(self, turn: int, my_stats: dict, enemy_stats: dict, enemy_kills: int = 0) -> float:
        """
        Predicts the percentage chance of winning against a specific enemy.
        """
        if not self.is_trained:
            return 0.5 # 50% chance if untrained (should never happen due to baseline)

        # We construct a feature vector exactly matching the training data format
        X_current = pd.DataFrame([{
            "turn": turn,
            "my_hp": my_stats.get("hp", 100),
            "my_atk": my_stats.get("atk", 10) + my_stats.get("equippedWeapon", {}).get("atkBonus", 0) if my_stats.get("equippedWeapon") else my_stats.get("atk", 10),
            "my_def": my_stats.get("def", 5),
            "enemy_hp": enemy_stats.get("hp", 100),
            "enemy_atk": enemy_stats.get("atk", 10) + enemy_stats.get("equippedWeapon", {}).get("atkBonus", 0) if enemy_stats.get("equippedWeapon") else enemy_stats.get("atk", 10),
            "enemy_def": enemy_stats.get("def", 5),
            "enemy_kills": enemy_kills
        }])

        X_scaled = self.scaler.transform(X_current)
        
        # predict_proba returns [[P(Loss), P(Win)]]
        probabilities = self.model.predict_proba(X_scaled)
        
        p_win = probabilities[0][1]
        
        # Rule-based heuristics to adjust P(Win) based on Inference:
        # If the enemy has high kills and it's late game (inferring they have high-tier hidden items like medkits)
        # we mathematically reduce P(Win) to make the bot more cautious.
        if enemy_kills >= 3 and turn >= 30:
            p_win -= 0.15 
            
        # Hard limits
        p_win = max(0.0, min(1.0, p_win))

        return p_win

    def get_dynamic_threshold(self, turn: int, current_kills: int) -> float:
        """
        Calculates the required P(Win) threshold to trigger an attack.
        Lowers threshold (becomes more aggressive) as the game reaches the end if kills are low.
        """
        base_threshold = 0.70 # Default 70% confidence required
        
        if turn < 20: 
            # Early Game: Very cautious, prioritize looting. Only attack easy targets.
            return 0.80
        elif 20 <= turn < 40:
            # Mid Game: Standard acceptable risk
            return base_threshold
        else:
            # Late Game (Turn 41-56): Push for kills if we don't have enough to rank high
            if current_kills < 2:
                # Desperate for kills to rank up
                return 0.50 
            elif current_kills < 5:
                return 0.60
            else:
                return base_threshold
