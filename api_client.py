import requests
import time

BASE_URL = "https://cdn.moltyroyale.com/api"

class ApiClient:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.headers = {
            "Content-Type": "application/json",
            "X-API-Key": self.api_key
        }

    def get_account(self):
        res = requests.get(f"{BASE_URL}/accounts/me", headers=self.headers)
        if res.status_code == 200:
            return res.json().get("data", {})
        return None

    def update_wallet(self, wallet_address: str):
        res = requests.put(f"{BASE_URL}/accounts/wallet", headers=self.headers, json={"wallet_address": wallet_address})
        return res.status_code == 200

    def find_waiting_games(self, entry_type: str = "free"):
        res = requests.get(f"{BASE_URL}/games?status=waiting")
        if res.status_code == 200:
            games = res.json().get("data", [])
            # Filter by matching entryType
            return [g for g in games if g.get("entryType", "free") == entry_type]
        return []

    def create_game(self, host_name: str, entry_type: str = "free"):
        """Creates a new game room. Returns (data, err_code)"""
        payload = {
            "hostName": host_name,
            "entryType": entry_type
        }
        res = requests.post(f"{BASE_URL}/games", headers=self.headers, json=payload)
        res_json = res.json()
        
        if res.status_code == 200 and res_json.get("success"):
            return res_json.get("data", {}), None
        
        err_code = res_json.get("error", {}).get("code", "UNKNOWN_ERROR")
        print(f"Failed to create game from API: {res.status_code} - {res_json}")
        return None, err_code

    def register_agent_free(self, game_id: str, agent_name: str):
        res = requests.post(f"{BASE_URL}/games/{game_id}/agents/register", headers=self.headers, json={"name": agent_name})
        if res.status_code == 200:
            return res.json().get("data", {})
        print(f"Failed to register agent: {res.text}")
        return None


    def get_agent_state(self, game_id: str, agent_id: str):
        res = requests.get(f"{BASE_URL}/games/{game_id}/agents/{agent_id}/state")
        if res.status_code == 200:
            return res.json().get("data", {})
        return None

    def send_action(self, game_id: str, agent_id: str, action: dict, thought: dict = None):
        payload = {"action": action}
        if thought:
            payload["thought"] = thought
        
        # Action endpoints are entirely public (no auth required) as specified in API documentation
        res = requests.post(
            f"{BASE_URL}/games/{game_id}/agents/{agent_id}/action",
            json=payload
        )
        return res.status_code == 202
