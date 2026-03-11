import time
import sys
import os
import argparse
from api_client import ApiClient
from brain import MLBrain
from strategy import Strategy
from knowledge import init_data, log_combat_result

def get_args():
    parser = argparse.ArgumentParser(description="Molty Royale ML Agent")
    parser.add_argument("--api-key", required=True, help="Your mr_live_ API Key")
    parser.add_argument("--room-type", choices=["free", "paid"], default="free", help="Type of room to join")
    return parser.parse_args()

def main():
    parser = argparse.ArgumentParser(description="Molty Royale ML Agent")
    parser.add_argument("--api-key", help="Your mr_live_ API Key (Overrides MR_API_KEY env var)")
    args = parser.parse_args()

    api_key = args.api_key or os.environ.get("MR_API_KEY")
    if not api_key:
        print("Error: API Key is required. Set MR_API_KEY environment variable or pass --api-key.")
        sys.exit(1)

    room_type = "free" # Hardcoded for free games
    wallet_address = os.environ.get("MR_WALLET_ADDRESS")

    print(f"Initializing AI Bot. Room Type: {room_type}")

    # Initialize Local Datastore
    init_data()

    # Initialize Components
    client = ApiClient(api_key)
    brain = MLBrain()
    brain.train_from_history() # Load any existing knowledge
    strategy = Strategy(brain)

    # 1. Check Account
    account = client.get_account()
    if not account:
        print("Failed to authenticate with provided API Key. Exiting.")
        sys.exit(1)

    print(f"Authenticated as: {account.get('name')}")
    
    # Wallet Requirement Check for Rewards (Non-blocking)
    if "walletAddress" not in account or not account["walletAddress"]:
        if wallet_address and wallet_address.startswith("0x"):
            print(f"Updating EVM Wallet Address from MR_WALLET_ADDRESS: {wallet_address}")
            if client.update_wallet(wallet_address):
                print("Wallet address updated successfully.")
            else:
                print("Failed to update wallet address.")
        else:
            print("WARNING: No EVM Wallet Address set on this account. Rewards will not be paid. Set MR_WALLET_ADDRESS to receive rewards.")

    # 2. Main Loop
    turn_counter = 0 # Track local turns 
    last_creation_attempt = 0 # Rate limit auto-create
    
    while True:
        account = client.get_account()
        if not account:
            print("Failed to fetch account info (API error or rate limit). Retrying in 3 seconds...")
            time.sleep(3)
            continue
            
        current_games = account.get("currentGames", [])
        active_game = next((g for g in current_games if g.get("entryType") == room_type), None)
        game_id = None
        agent_id = None

        if active_game:
            game_id = active_game.get("gameId")
            agent_id = active_game.get("agentId")
        else:
            # Find waiting game
            print(f"Looking for waiting {room_type} game...")
            games = client.find_waiting_games(room_type)
            if not games:
                current_time = time.time()
                # Create a game if we haven't tried in the last 120 seconds
                if current_time - last_creation_attempt > 120:
                    print(f"No waiting {room_type} games found. Attempting to create one automatically...")
                    new_room_name = account.get("name", "Auto") + "_Room_" + str(int(current_time % 1000))
                    new_game, err_code = client.create_game(host_name=new_room_name, entry_type=room_type)
                    last_creation_attempt = current_time

                    if new_game:
                        print(f"Game room '{new_room_name}' created successfully. Joining...")
                        game_id = new_game["id"]
                    elif err_code == "WAITING_GAME_EXISTS":
                        print("API reported a waiting game already exists! Fetching it now...")
                        # In this scenario, we just skip waiting, let the loop fetch it on next tick (or fetch directly)
                        # We will force a re-fetch immediately
                        print("Re-fetching games list...")
                        continue
                    else:
                        print(f"Failed to auto-create game (Code: {err_code}). Retrying search in 3 seconds...")
                        time.sleep(3)
                    continue
                else:
                    print(f"No waiting {room_type} games found. Waiting 3 seconds before next search...")
                    time.sleep(3)
                    continue
            
            game_id = games[0]["id"]
            print(f"Found waiting game: {games[0].get('name')} (ID: {game_id})")

            if room_type == "free":
                agent = client.register_agent_free(game_id, account.get("name") + "_Bot")
                if not agent:
                    print("Failed to register. Retrying in 3s...")
                    time.sleep(3)
                    continue
                agent_id = agent["id"]
                print(f"Registered successfully! Agent ID: {agent_id}")

        # 3. Game State Loop
        state = client.get_agent_state(game_id, agent_id)
        if not state:
            print("Failed to fetch state. Retrying in 5 seconds...")
            time.sleep(5)
            continue

        game_status = state.get("gameStatus")
        self_state = state.get("self", {})

        if game_status == "waiting":
            print(f"Game Status: WAITING. Max Agents: {state.get('maxAgents')} Agents Registered. Waiting for Start...")
            time.sleep(10)
            continue

        if game_status == "finished" or not self_state.get("isAlive", True):
            print("\n!!! GAME OVER !!!")
            result = state.get("result", {})
            print(f"Won: {result.get('isWinner')}, Final Rank: {result.get('finalRank')}, Rewards: {result.get('rewards')} Moltz")
            
            # Extract final stats for history tracking
            kills = self_state.get("kills", 0)
            won = result.get("isWinner", False)
            log_combat_result(turn_counter, self_state, {}, kills, won) # Generalized logging of match end
            
            # Retrain model after every game ends!
            brain.train_from_history()
            
            print("Bot session ended. Looking for next game...")
            turn_counter = 0
            time.sleep(10)
            continue

        turn_counter += 1
        print(f"\n--- Turn ~{turn_counter} / HP: {self_state.get('hp')} / EP: {self_state.get('ep')} / Kills: {self_state.get('kills')} ---")
        
        # Free actions
        strategy.process_free_actions(state, client, game_id, agent_id)

        # Decide Action
        decision = strategy.decide_action(state)
        action_payload = decision["action"]
        thought_payload = decision.get("thought")

        print(f"Action: {action_payload.get('type')}")
        if thought_payload:
            print(f"Thought: {thought_payload.get('reasoning')}")

        # Execute Action
        success = client.send_action(game_id, agent_id, action_payload, thought_payload)
        if not success:
            print("Action failed or rejected by server.")

        # Wait 60s for next Turn (Real Time equivalence for 6 Game Hours)
        print("Waiting 60s for next turn...")
        time.sleep(60)

if __name__ == "__main__":
    main()
