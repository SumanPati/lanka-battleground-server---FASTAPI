import json
import random
import copy
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path
import uvicorn
from pydantic import BaseModel

app = FastAPI(title="Battleground Lanka")

# app.add_middleware(
#     CORSMiddleware,
#     allow_origins=[
#         "http://localhost:5173",  # Vite dev
#         "http://127.0.0.1:5173",
#         "http://192.168.1.5:5173",
#     ],
#     allow_credentials=True,
#     allow_methods=["*"],
#     allow_headers=["*"],
# )

# ---------- PATHS ----------
BASE_DIR = Path(__file__).resolve().parent.parent
FRONTEND_DIR = BASE_DIR / "frontend" / "dist"

# ---------- STATIC FILES ----------
app.mount(
    "/assets",
    StaticFiles(directory=FRONTEND_DIR / "assets"),
    name="assets"
)

app.mount(
    "/cards",
    StaticFiles(directory=FRONTEND_DIR / "cards"),
    name="cards"
)

app.mount(
    "/rules",
    StaticFiles(directory=FRONTEND_DIR / "rules"),
    name="rules"
)



# ======================
# HELPERS
# ======================

def shuffle(array):
    shuffled = array[:]
    for i in range(len(shuffled) - 1, 0, -1):
        j = random.randint(0, i)
        shuffled[i], shuffled[j] = shuffled[j], shuffled[i]
    return shuffled


# ======================
# DATA
# ======================

PLAYER_CHARACTERS = {
    "hanuman": {"img": "Character/hanuman.jpg"},
    "kumbhakarna": {"img": "Character/kumbhakarna.jpg"},
    "lakshmana": {"img": "Character/lakshmana.jpg"},
    "manthara": {"img": "Character/manthara.jpg"},
    "meghanad": {"img": "Character/meghanad.jpg"},
    "rama": {"img": "Character/rama.jpg"},
    "ravana": {"img": "Character/ravana.jpg"},
    "sita": {"img": "Character/sita.jpg"},
    "vibhishana": {"img": "Character/vibhishana.jpg"},
}

RULES = [
    "/rules/1.jpg",
    "/rules/2.jpg",
    "/rules/3.jpg",
    "/rules/4.jpg",
    "/rules/5.jpg",
    "/rules/6.jpg",
    "/rules/7.jpg",
    "/rules/8.jpg"
]

cards = {
    "Action": {
        "brahma": {"img": "Action/brahma.jpg", "count": 3},
        "garuda": {"img": "Action/garuda.jpg", "count": 5},
        "kaikeyi": {"img": "Action/kaikeyi.jpg", "count": 3},
        "mareecha": {"img": "Action/mareecha.jpg", "count": 7},
        "vimana": {"img": "Action/vimana.jpg", "count": 4},
        "vishnu": {"img": "Action/vishnu.jpg", "count": 4},
    },
    "Damage": {
        "agniastra": {"img": "Damage/agniastra.jpg", "count": 5},
        "brahmastra": {"img": "Damage/brahmastra.jpg", "count": 3},
        "gatiastra": {"img": "Damage/gatiastra.jpg", "count": 5},
        "nagastra": {"img": "Damage/nagastra.jpg", "count": 4},
        "shakti": {"img": "Damage/shakti.jpg", "count": 1},
        "vanar sena": {"img": "Damage/vanar sena.jpg", "count": 4},
        "vayuastra": {"img": "Damage/vayuastra.jpg", "count": 4},
    },
    "Defence": {
        "aaina": {"img": "Defence/aaina.jpg", "count": 3},
        "jatayu": {"img": "Defence/jatayu.jpg", "count": 10},
    },
    "Health": {
        "sanjeevani": {"img": "Health/sanjeevani.jpg", "count": 6},
        "shabari": {"img": "Health/shabari.jpg", "count": 2},
    },
    "Stat": {
        "lakshman rekha": {"img": "Stat/lakshman rekha.jpg", "count": 2},
        "vanvas": {"img": "Stat/vanvas.jpg", "count": 2},
    },
}

CARD_FILES = [
    card["img"]
    for category in cards.values()
    for card in category.values()
    for _ in range(card["count"])
]


# ======================
# GAME STATE
# ======================

GAME_STATE_HIST = []

def build_deck():
    deck = []
    for category in cards.values():
        for name, card in category.items():
            deck.extend([{"name": name, "img": card["img"]}] * card["count"])
    return shuffle(deck)

def create_initial_state():
    return {
        "deck": build_deck(),
        "usedPile": [],
        "board": [],
        "players": {},
        "cardIdCounter": 0,
        "transfer":None,
        "log": [],
        "currentTurn": None,
    }

def add_log(entry: str):
    game_state["log"].append(entry)

def save_state():
    GAME_STATE_HIST.append(copy.deepcopy(game_state))

game_state = create_initial_state()
available_characters = list(PLAYER_CHARACTERS.keys())

clients: set[WebSocket] = set()
ws_to_player: dict[WebSocket, str] = {}

def get_random_character():
    global available_characters

    if not available_characters:
        available_characters = list(PLAYER_CHARACTERS.keys())

    key = random.choice(available_characters)
    available_characters.remove(key)

    return {"name": key, **PLAYER_CHARACTERS[key]}

def reset_game():
    global available_characters,GAME_STATE_HIST
    available_characters = list(PLAYER_CHARACTERS.keys())
    game_state["deck"] = build_deck()
    game_state["board"] = []
    game_state["cardIdCounter"] = 0
    game_state["usedPile"] = []
    game_state["transfer"] = None
    game_state["log"] = []
    GAME_STATE_HIST = []
    
    for player_name, player_data in game_state["players"].items():
        player_data["health"] = 5
        player_data["maxHealth"] = 5
        player_data["hand"] = []
        player_data["applied"] = []
        player_data["character"] = get_random_character()
        draw_cards(player_name, 5)

    p_list = list(game_state["players"].keys())
    game_state["currentTurn"] = p_list[0] if p_list else None
    
    return game_state

# ======================
# BROADCAST
# ======================

async def broadcast():
    payload = json.dumps({"type": "STATE", "state": game_state})
    dead = []

    for ws in clients:
        try:
            await ws.send_text(payload)
        except Exception:
            dead.append(ws)

    for ws in dead:
        clients.discard(ws)
        ws_to_player.pop(ws, None)


# ======================
# ROUTES
# ======================

@app.get("/")
def root():
    return FileResponse(FRONTEND_DIR / "index.html")


@app.get("/health")
def health():
    return {"status": "healthy"}

@app.get("/api/cards")
def get_cards():
    return cards

@app.get("/api/activeplayers")
def get_active_players():
    return list(game_state["players"].keys())

@app.get("/api/rules")
def get_rules():
    return RULES

class CardUpdate(BaseModel):
    category: str
    name: str
    count: int

@app.post("/api/cards")
def update_card(cfg: CardUpdate):
    global game_state
    if cfg.category not in cards:
        return {"error": "Invalid category"}

    if cfg.name not in cards[cfg.category]:
        return {"error": "Invalid card"}

    cards[cfg.category][cfg.name]["count"] = max(0, cfg.count)
    game_state = create_initial_state()
    return {"status": "ok"}

# ======================
# WEBSOCKET
# ======================

def draw_cards(player: str, count: int = 1):
    drawn = 0
    for _ in range(count):
        if not game_state["deck"]:
            break

        card_data = game_state["deck"].pop(0)
        card_id = f"card-{game_state['cardIdCounter']}"
        game_state["cardIdCounter"] += 1

        card = {
            "id": card_id,
            "owner": player,
            "name": card_data["name"],
            "cardFile": card_data,
            "image": f"/cards/{card_data['img']}",
            "position": None,
            "inHand": True,
        }

        game_state["board"].append(card)
        game_state["players"][player]["hand"].append(card_id)
        drawn += 1

    if drawn > 0:
        game_state["players"][player]["hand"].sort(key=lambda cid: int(cid.split("-")[1]))
    
    return drawn

@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    global game_state, available_characters

    await ws.accept()
    clients.add(ws)
    
    # Send initial state
    await ws.send_text(json.dumps({"type": "STATE", "state": game_state}))

    try:
        while True:
            raw = await ws.receive_text()
            msg = json.loads(raw)

            match msg.get("type"):
                case "JOIN":
                    player = msg["player"]
                    save_state()
                    add_log(f"{player} joined the game")

                    if player not in game_state["players"]:
                        game_state["players"][player] = {
                            "health": 5,
                            "maxHealth": 5,
                            "hand": [],
                            "applied": [],
                            "character": get_random_character(),
                        }
                        drawn = draw_cards(player, 5)
                        add_log(f"{player} given {drawn} card(s)")
                        
                    ws_to_player[ws] = player

                    if game_state["currentTurn"] is None:
                        game_state["currentTurn"] = player

                case "DRAW_CARD":
                    player = ws_to_player.get(ws)
                    if player:
                        save_state()
                        drawn = draw_cards(player, 1)
                        if drawn > 0:
                            add_log(f"{player} drew {drawn} card(s)")
                    
                    if game_state["usedPile"] and game_state["deck"].__len__() <= 5:
                        game_state["deck"].extend(game_state["usedPile"])
                        game_state["usedPile"] = []
                        game_state["deck"] = shuffle(game_state["deck"])
                
                case "UNDO":
                    game_state = GAME_STATE_HIST.pop() if GAME_STATE_HIST else game_state
                    
                case "MOVE_CARD":
                    player = ws_to_player.get(ws)
                    
                    card_id = msg["cardId"]
                    pos = msg["position"]
                    for card in game_state["board"]:
                        if card["id"] == card_id:
                            save_state()
                            card["position"] = pos
                            card["inHand"] = False
                            add_log(f"{player} played {card['name']}")
                            break
                
                case "RETURN_TO_HAND":
                    player = ws_to_player.get(ws)
                    card_id = msg["cardId"]
                    
                    for card in game_state["board"]:
                        if card["id"] == card_id:
                            save_state()
                            card["position"] = None
                            card["inHand"] = True
                            add_log(f"{player} returned {card['name']}")
                            break
                        
                case "DISCARD_CARD":
                    player = ws_to_player.get(ws)
                    
                    card_id = msg["cardId"]
                    card = next((c for c in game_state["board"] if c["id"] == card_id), None)
                    if not card:
                        return

                    owner = card["owner"]
                    save_state()
                    
                    add_log(f"{player} discarded {card['name']}")
                    
                    game_state["board"] = [c for c in game_state["board"] if c["id"] != card_id]
                    game_state["usedPile"].append(card["cardFile"])
                    game_state["players"][owner]["hand"].remove(card_id)
                    game_state["players"][owner]["hand"].sort(key=lambda cid: int(cid.split("-")[1]))

                case "APPLY":
                    player = ws_to_player.get(ws)
                    card_id = msg["cardId"]
                    target_player = msg["target"]

                    card = next((c for c in game_state["board"] if c["id"] == card_id), None)
                    if card and target_player in game_state["players"]:
                        save_state()
                        owner = card["owner"]
                        if card_id in game_state["players"][owner]["hand"]:
                            game_state["players"][owner]["hand"].remove(card_id)
                            game_state["players"][owner]["hand"].sort(key=lambda cid: int(cid.split("-")[1]))

                        card["inHand"] = False
                        card["position"] = None
                        
                        if "applied" not in game_state["players"][target_player]:
                            game_state["players"][target_player]["applied"] = []
                        
                        game_state["players"][target_player]["applied"].append(card)
                        add_log(f"{player} applied {card['name']} to {target_player}")
                
                case "APPLIED_REMOVE":
                    player = ws_to_player.get(ws)
                    card_id = msg["cardId"]

                    card = next((c for c in game_state["board"] if c["id"] == card_id), None)
                    if card:
                        target_name = None
                        for p_name, p_data in game_state["players"].items():
                            applied_list = p_data.get("applied", [])
                            if any(c["id"] == card_id for c in applied_list):
                                save_state()
                                target_name = p_name
                                p_data["applied"] = [c for c in applied_list if c["id"] != card_id]
                                break
                        
                        if target_name:
                            add_log(f"{player} removed {card['name']} from {target_name}")
                            game_state["usedPile"].append(card["cardFile"])
                            game_state["board"] = [c for c in game_state["board"] if c["id"] != card_id]
                
                case "RESET":
                    game_state = reset_game()
                
                case "UPDATE_HEALTH":
                    player = msg["player"]
                    save_state()
                    delta = msg["delta"]
                                        
                    p = game_state["players"][player]
                    p["health"] = max(0, min(p["maxHealth"], p["health"] + delta))
                
                    if delta > 0:
                        add_log(f"{player} healed {delta} health to {p['health']}")
                    else:
                        add_log(f"{player} lost {abs(delta)} health to {p['health']}")
                
                case "TRANSFER_START":
                    initiator = msg["from"]
                    target = msg["to"]

                    save_state()
                    add_log(f"{initiator} initiated a transfer with {target}")

                    if game_state["transfer"] is not None:
                        return  # only one transfer at a time

                    if initiator not in game_state["players"]:
                        return
                    if target not in game_state["players"]:
                        return

                    game_state["transfer"] = {
                        "from": initiator,
                        "to": target,
                        "mode": "SELECT",
                        "selectedCards": []
                    }
                    
                case "TRANSFER_SWAP_HANDS":
                    t = game_state["transfer"]
                    if not t:
                        return

                    save_state()
                    a, b = t["from"], t["to"]
                    
                    add_log(f"{a} and {b} swapped hands")

                    game_state["players"][a]["hand"], game_state["players"][b]["hand"] = (
                        game_state["players"][b]["hand"],
                        game_state["players"][a]["hand"],
                    )
                    
                    for card in game_state["board"]:
                        if card["id"] in game_state["players"][a]["hand"]:
                            card["owner"] = a
                        elif card["id"] in game_state["players"][b]["hand"]:
                            card["owner"] = b
                    
                    game_state["transfer"] = None
                    
                    game_state["players"][a]["hand"].sort(key=lambda cid: int(cid.split("-")[1]))
                    game_state["players"][b]["hand"].sort(key=lambda cid: int(cid.split("-")[1]))
                    
                
                case "TRANSFER_SELECT_CARDS":
                    t = game_state["transfer"]
                    from_p, to_p = t["from"], t["to"]

                    save_state()
                    for cid in msg["cardIds"]:
                        if cid in game_state["players"][from_p]["hand"]:
                            game_state["players"][from_p]["hand"].remove(cid)
                            game_state["players"][to_p]["hand"].append(cid)

                            for card in game_state["board"]:
                                if card["id"] == cid:
                                    card["owner"] = to_p
                                    
                    add_log(f"{to_p} took {msg['cardIds'].__len__()} card(s) from {from_p}")

                    game_state["players"][from_p]["hand"].sort(key=lambda cid: int(cid.split("-")[1]))
                    game_state["players"][to_p]["hand"].sort(key=lambda cid: int(cid.split("-")[1]))
                    
                    game_state["transfer"] = None
                    
                case "TRANSFER_DISCARD_CARDS":
                    t = game_state.get("transfer")
                    if not t:
                        return

                    save_state()

                    from_p = t.get("from")
                    initiator = t.get("to")
                    
                    if from_p not in game_state["players"]:
                        game_state["transfer"] = None
                        return

                    hand = game_state["players"][from_p]["hand"]

                    for cid in msg.get("cardIds", []):
                        # Safely locate card on board
                        card = next((c for c in game_state["board"] if c["id"] == cid), None)
                        if not card:
                            continue  # already discarded / invalid

                        # Remove from player's hand if present
                        if cid in hand:
                            hand.remove(cid)

                        # Move card to used pile
                        game_state["usedPile"].append(card["cardFile"])

                        # Remove from board
                        game_state["board"].remove(card)

                        add_log(f"{initiator} discarded {card['name']} from {from_p}")
                    
                    # End transfer
                    game_state["transfer"] = None
                    game_state["players"][from_p]["hand"].sort(key=lambda cid: int(cid.split("-")[1]))

                    
                case "TRANSFER_CANCEL":
                    save_state()
                    add_log("Transfer was cancelled")
                    game_state["transfer"] = None

                case "END_TURN":
                    player = ws_to_player.get(ws)
                    if game_state.get("currentTurn") == player:
                        p_list = list(game_state["players"].keys())
                        if p_list:
                            save_state()
                            idx = p_list.index(player)
                            next_p = p_list[(idx + 1) % len(p_list)]
                            game_state["currentTurn"] = next_p
                            add_log(f"Turn passed to {next_p}")
                    
                case "LEAVE":
                    player = ws_to_player.get(ws)
                    if player and player in game_state["players"]:
                        save_state()
                        add_log(f"{player} left the game")

                        # 1️⃣ Return hand cards to deck
                        for cid in game_state["players"][player]["hand"]:
                            card = next((c for c in game_state["board"] if c["id"] == cid), None)
                            if card:
                                game_state["deck"].append(card["cardFile"])
                                game_state["board"].remove(card)

                        # 2️⃣ Safety: remove any stray board cards owned by player
                        stray = [c for c in game_state["board"] if c["owner"] == player]
                        for card in stray:
                            game_state["deck"].append(card["cardFile"])
                            game_state["board"].remove(card)

                        # 3️⃣ Handle turn if active player leaves
                        if game_state.get("currentTurn") == player:
                            p_list = list(game_state["players"].keys())
                            if len(p_list) > 1:
                                idx = p_list.index(player)
                                next_p = p_list[(idx + 1) % len(p_list)]
                                game_state["currentTurn"] = next_p
                                add_log(f"Turn passed to {next_p}")
                            else:
                                game_state["currentTurn"] = None

                        # 4️⃣ Remove player from game
                        del game_state["players"][player]

                        # 5️⃣ Cancel transfer if involved
                        t = game_state.get("transfer")
                        if t and (t["from"] == player or t["to"] == player):
                            game_state["transfer"] = None
                
            await broadcast()

    except WebSocketDisconnect:
        print("WebSocketDisconnect...")
        player = ws_to_player.get(ws)
        if player:
            print(f"{player} disconnected")
    finally:
        player = ws_to_player.get(ws)
        if player:
            add_log(f"{player} disconnected")

        clients.discard(ws)
        ws_to_player.pop(ws, None)


# ======================
# MAIN
# ======================

def main():
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=False,
        log_level="info",
    )


if __name__ == "__main__":
    main()
