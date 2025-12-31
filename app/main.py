import json
import random
from copy import deepcopy
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path
import uvicorn

app = FastAPI(title="Battleground Lanka")

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

cards = {
    "Action": {
        "brahma": {"img": "Action/brahma.jpg", "count": 2},
        "garuda": {"img": "Action/garuda.jpg", "count": 2},
        "kaikeyi": {"img": "Action/kaikeyi.jpg", "count": 2},
        "mareecha": {"img": "Action/mareecha.jpg", "count": 2},
        "vimana": {"img": "Action/vimana.jpg", "count": 2},
        "vishnu": {"img": "Action/vishnu.jpg", "count": 2},
    },
    "Damage": {
        "agniastra": {"img": "Damage/agniastra.jpg", "count": 3},
        "brahmastra": {"img": "Damage/brahmastra.jpg", "count": 3},
        "gatiastra": {"img": "Damage/gatiastra.jpg", "count": 3},
        "nagastra": {"img": "Damage/nagastra.jpg", "count": 3},
        "shakti": {"img": "Damage/shakti.jpg", "count": 3},
        "vanar sena": {"img": "Damage/vanar sena.jpg", "count": 3},
        "vayuastra": {"img": "Damage/vayuastra.jpg", "count": 3},
    },
    "Defence": {
        "aaina": {"img": "Defence/aaina.jpg", "count": 3},
        "jatayu": {"img": "Defence/jatayu.jpg", "count": 3},
    },
    "Health": {
        "sanjeevani": {"img": "Health/sanjeevani.jpg", "count": 2},
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

def create_initial_state():
    return {
        "deck": shuffle(CARD_FILES),
        "usedPile": [],
        "board": [],
        "players": {},
        "cardIdCounter": 0,
        "transfer":None,
    }

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
    available_characters = list(PLAYER_CHARACTERS.keys())
    game_state["deck"] = shuffle(CARD_FILES.copy())
    game_state["board"] = []
    game_state["cardIdCounter"] = 0

    for player in game_state["players"].values():
        player["health"] = 30
        player["maxHealth"] = 30
        player["hand"] = []
        player["character"] = get_random_character()
    
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


# ======================
# WEBSOCKET
# ======================

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

                    if player not in game_state["players"]:
                        game_state["players"][player] = {
                            "health": 30,
                            "maxHealth": 30,
                            "hand": [],
                            "character": get_random_character(),
                        }
                        
                    ws_to_player[ws] = player

                case "DRAW_CARD":
                    player = ws_to_player.get(ws)
                    if not player:
                        return

                    if not game_state["deck"]:
                        return

                    card_file = game_state["deck"].pop(0)
                    card_id = f"card-{game_state['cardIdCounter']}"
                    game_state["cardIdCounter"] += 1

                    card = {
                        "id": card_id,
                        "owner": player,
                        "cardFile": card_file,
                        "image": f"/cards/{card_file}",
                        "position": None,
                        "inHand": True,
                    }

                    game_state["board"].append(card)
                    game_state["players"][player]["hand"].append(card_id)
                    
                case "MOVE_CARD":
                    card_id = msg["cardId"]
                    pos = msg["position"]
                    for card in game_state["board"]:
                        if card["id"] == card_id:
                            card["position"] = pos
                            card["inHand"] = False
                            break
                
                case "RETURN_TO_HAND":
                    card_id = msg["cardId"]
                    for card in game_state["board"]:
                        if card["id"] == card_id:
                            card["position"] = None
                            card["inHand"] = True
                            break
                        
                case "DISCARD_CARD":
                    card_id = msg["cardId"]
                    card = next((c for c in game_state["board"] if c["id"] == card_id), None)
                    if not card:
                        return

                    owner = card["owner"]

                    game_state["board"] = [c for c in game_state["board"] if c["id"] != card_id]
                    game_state["usedPile"].append(card["cardFile"])
                    game_state["players"][owner]["hand"].remove(card_id)

                
                case "RESET":
                    game_state = reset_game()
                
                case "UPDATE_HEALTH":
                    player = msg["player"]
                    delta = msg["delta"]

                    p = game_state["players"][player]
                    p["health"] = max(0, min(p["maxHealth"], p["health"] + delta))
                
                case "RESHUFFLE_USED":
                    if game_state["usedPile"]:
                        game_state["deck"].extend(game_state["usedPile"])
                        game_state["usedPile"] = []
                        game_state["deck"] = shuffle(game_state["deck"])
                
                case "TRANSFER_START":
                    initiator = msg["from"]
                    target = msg["to"]

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

                    a, b = t["from"], t["to"]

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
                
                case "TRANSFER_SELECT_CARDS":
                    t = game_state["transfer"]
                    from_p, to_p = t["from"], t["to"]

                    for cid in msg["cardIds"]:
                        if cid in game_state["players"][from_p]["hand"]:
                            game_state["players"][from_p]["hand"].remove(cid)
                            game_state["players"][to_p]["hand"].append(cid)

                            for card in game_state["board"]:
                                if card["id"] == cid:
                                    card["owner"] = to_p

                    game_state["transfer"] = None
                    
                case "TRANSFER_DISCARD_CARDS":
                    t = game_state["transfer"]
                    from_p = t["from"]

                    for cid in msg["cardIds"]:
                        card = next(c for c in game_state["board"] if c["id"] == cid)
                        game_state["players"][from_p]["hand"].remove(cid)
                        game_state["usedPile"].append(card["cardFile"])
                        game_state["board"].remove(card)

                    game_state["transfer"] = None
                    
                case "TRANSFER_CANCEL":
                    game_state["transfer"] = None
                
            await broadcast()

    except WebSocketDisconnect:
        pass
    finally:
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
