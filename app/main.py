import json
import random
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
    }

game_state = create_initial_state()
available_characters = list(PLAYER_CHARACTERS.keys())

clients: set[WebSocket] = set()


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

                case "UPDATE":
                    game_state = msg["state"]

                case "RESET":
                    game_state = reset_game()
                
                case "RESHUFFLE_USED":
                    if game_state["usedPile"]:
                        game_state["deck"].extend(game_state["usedPile"])
                        game_state["usedPile"] = []
                        game_state["deck"] = shuffle(game_state["deck"])

            await broadcast()

    except WebSocketDisconnect:
        clients.discard(ws)


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
