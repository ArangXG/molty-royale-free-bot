import random
from knowledge import load_enemy_profiles, update_enemy_profile

class Strategy:
    def __init__(self, brain):
        self.brain = brain

    def _getWeaponBonus(self, item):
        if not item or item.get("category") != "weapon":
            return 0
        return item.get("atkBonus", 0)

    def decide_action(self, state):
        """
        Reads the full state from the API and decides the next action.
        Returns a dict: {"action": {...}, "thought": {...}}
        """
        self_state = state.get("self", {})
        region = state.get("currentRegion", {})
        visible_agents = state.get("visibleAgents", [])
        visible_monsters = state.get("visibleMonsters", [])
        pending_deathzones = state.get("pendingDeathzones", [])
        turn_info = 1 # We can guess turn based on time/messages, or default it to 30. Better logic exists in main loop.

        # ----------------------------------------------------
        # PRIORITY 1: Death Zone Avoidance
        # ----------------------------------------------------
        is_in_deathzone = region.get("isDeathZone", False)
        
        # Determine if we are in a pending death zone
        is_pending_deathzone = False
        for pdz in pending_deathzones:
            if pdz.get("id") == region.get("id"):
                is_pending_deathzone = True
                break
                
        if is_in_deathzone or is_pending_deathzone:
            safe_connections = []
            connections = region.get("connections", [])
            
            # Find a connection that is NOT pending a deathzone
            for conn_id in connections:
                is_safe = True
                for pdz in pending_deathzones:
                    if pdz.get("id") == conn_id:
                        is_safe = False
                        break
                if is_safe:
                    safe_connections.append(conn_id)

            if safe_connections:
                # Move to the first safe region
                target = random.choice(safe_connections)
                return {
                    "action": {"type": "move", "regionId": target},
                    "thought": {"reasoning": "Escaping current or pending Death Zone.", "plannedAction": "move"}
                }
            elif connections:
                # If all connections are pending, just move anywhere to get out of active death zone
                return {
                    "action": {"type": "move", "regionId": connections[0]},
                    "thought": {"reasoning": "Death Zone imminent everywhere, moving randomly.", "plannedAction": "move"}
                }

        # ----------------------------------------------------
        # PRIORITY 2: Heals (Resource Management)
        # ----------------------------------------------------
        if self_state.get("hp", 100) < 40:
            for item in self_state.get("inventory", []):
                if item.get("category") == "recovery" and "hp" not in item.get("name", "").lower(): # Usually "Bandage" or "Medkit"
                    return {
                        "action": {"type": "use_item", "itemId": item["id"]},
                        "thought": {"reasoning": f"HP is {self_state.get('hp')}, consuming healing item.", "plannedAction": "use_item"}
                    }

        # ----------------------------------------------------
        # PRIORITY 3: Rest if EP is too low to attack
        # ----------------------------------------------------
        if self_state.get("ep", 10) < 2:
            return {
                "action": {"type": "rest"},
                "thought": {"reasoning": "EP is too low for combat or movement. Resting.", "plannedAction": "rest"}
            }

        # ----------------------------------------------------
        # PRIORITY 4: Combat (Machine Learning Driven)
        # ----------------------------------------------------
        current_kills = self_state.get("kills", 0)
        # We need a rough turn estimate (or we can pass it from main)
        # Let's say we pass the real turn into strategy, but since we didn't, we will assume Mid Game.
        current_turn = 30 
        
        # Check Agents First
        best_target = None
        best_win_prob = 0.0
        
        for agent in visible_agents:
            if agent.get("regionId") == self_state.get("regionId") and agent.get("isAlive"):
                # Profile enemy and predict win probabilty
                agent_id = agent["id"]
                agent_name = agent.get("name", "Unknown")
                enemy_kills = agent.get("kills", 0) 
                
                # Update knowledge graph silently
                update_enemy_profile(agent_id, agent_name, enemy_kills)
                
                win_prob = self.brain.predict_win_probability(current_turn, self_state, agent, enemy_kills)
                
                if win_prob > best_win_prob:
                    best_win_prob = win_prob
                    best_target = {"id": agent["id"], "type": "agent", "name": agent.get("name")}

        # Check Monsters Second
        for monster in visible_monsters:
            if monster.get("regionId") == self_state.get("regionId"):
                win_prob = self.brain.predict_win_probability(current_turn, self_state, monster, 0) # Monsters have 0 kills
                if win_prob > best_win_prob:
                    best_win_prob = win_prob
                    best_target = {"id": monster["id"], "type": "monster", "name": monster.get("name")}

        # Decide if we attack based on Dynamic Threshold
        threshold = self.brain.get_dynamic_threshold(current_turn, current_kills)
        
        if best_target and best_win_prob >= threshold:
            return {
                "action": {"type": "attack", "targetId": best_target["id"], "targetType": best_target["type"]},
                "thought": {"reasoning": f"Target {best_target['name']} yields {best_win_prob*100:.1f}% win probability (Threshold: {threshold*100:.1f}%).", "plannedAction": "attack"}
            }
        elif best_target and best_win_prob < threshold:
             # We see an enemy but our win prob is too low. Retreat.
             connections = region.get("connections", [])
             if connections:
                 return {
                     "action": {"type": "move", "regionId": random.choice(connections)},
                     "thought": {"reasoning": f"Enemy too strong (P(Win)={best_win_prob*100:.1f}% < {threshold*100:.1f}%). Retreating.", "plannedAction": "move"}
                 }

        # ----------------------------------------------------
        # PRIORITY 5: Explore & Loot
        # ----------------------------------------------------
        # If no imminent danger or better targets, just explore region to uncover loot
        return {
            "action": {"type": "explore"},
            "thought": {"reasoning": "Area secure. Exploring for items and Moltz.", "plannedAction": "explore"}
        }

    def process_free_actions(self, state, api_client, game_id, agent_id):
        """
        Executes free actions simultaneously (Pickup, Equip, Talk) since they cost 0 EP.
        """
        self_state = state.get("self", {})
        
        # 1. Equip Best Weapon
        weapons = [item for item in self_state.get("inventory", []) if item.get("category") == "weapon"]
        if weapons:
            best_weapon = max(weapons, key=lambda w: w.get("atkBonus", 0))
            current_weapon = self_state.get("equippedWeapon")
            
            # If current weapon is none, or existing weapon is weaker, equip best weapon
            if not current_weapon or best_weapon.get("atkBonus", 0) > current_weapon.get("atkBonus", 0):
                api_client.send_action(game_id, agent_id, {"type": "equip", "itemId": best_weapon["id"]})
                print(f"[FREE] Equipped better weapon: {best_weapon.get('name')}")
        
        # 2. Pickup all visible items in the current region
        # If inventory is not full
        if len(self_state.get("inventory", [])) < 10:
            visible_items = state.get("visibleItems", [])
            for item_entry in visible_items:
                if item_entry.get("regionId") == self_state.get("regionId"):
                    api_client.send_action(game_id, agent_id, {"type": "pickup", "itemId": item_entry.get("item", {}).get("id")})
                    print(f"[FREE] Picked up item: {item_entry.get('item', {}).get('name')}")
                    # A small delay isn't needed by API, but we break after picking 1 item to let the state update next turn mostly.
                    break
        
        # 3. Whisper / Talk Logic (manipulation)
        # Example: if low HP, send a friendly message to deter attacks
        recent_messages = state.get("recentMessages", [])
        for msg in recent_messages:
            if msg.get("senderId") != agent_id and msg.get("type") == "private":
                # Automatically reply to whispers
                api_client.send_action(game_id, agent_id, {
                    "type": "whisper", 
                    "targetId": msg.get("senderId"), 
                    "message": "I come in peace. Let's focus on looting."
                })
