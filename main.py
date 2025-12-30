from fastapi import FastAPI, WebSocket, WebSocketDisconnect
import uvicorn
import random
import json

app = FastAPI()

# =======================
# HELPERS
# =======================

def shuffle(array):
    arr = array[:]
    random.shuffle(arr)
    return arr

# =======================
# DATA
# =======================

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

# =======================
# GAME STATE
# =======================

def create_initial_state():
    return {
        "deck": shuffle(CARD_FILES),
        "board": [],
        "players": {},
        "cardIdCounter": 0,
    }

game_state = create_initial_state()
available_characters = list(PLAYER_CHARACTERS.keys())

def get_random_character():
    global available_characters
    if not available_characters:
        available_characters = list(PLAYER_CHARACTERS.keys())

    key = random.choice(available_characters)
    available_characters.remove(key)
    return {"name": key, **PLAYER_CHARACTERS[key]}

# =======================
# CONNECTION MANAGER
# =======================

class ConnectionManager:
    def __init__(self):
        self.connections: list[WebSocket] = []

    async def connect(self, ws: WebSocket):
        await ws.accept()
        self.connections.append(ws)

    def disconnect(self, ws: WebSocket):
        self.connections.remove(ws)

    async def broadcast(self):
        message = json.dumps({
            "type": "STATE",
            "state": game_state
        })
        for ws in self.connections:
            await ws.send_text(message)

manager = ConnectionManager()

# =======================
# WEBSOCKET ENDPOINT
# =======================

@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    global game_state, available_characters

    await manager.connect(ws)
    await ws.send_text(json.dumps({
        "type": "STATE",
        "state": game_state
    }))

    try:
        while True:
            data = json.loads(await ws.receive_text())

            match data["type"]:
                case "JOIN":
                    player = data["player"]
                    if player not in game_state["players"]:
                        game_state["players"][player] = {
                            "health": 30,
                            "maxHealth": 30,
                            "hand": [],
                            "character": get_random_character()
                        }

                case "UPDATE":
                    game_state = data["state"]

                case "RESET":
                    game_state = create_initial_state()
                    available_characters = list(PLAYER_CHARACTERS.keys())

            await manager.broadcast()

    except WebSocketDisconnect:
        manager.disconnect(ws)
        await manager.broadcast()

# =======================
# ROUTES
# =======================

@app.get("/")
def root():
    return {
        "status": "ok",
        "service": "Battleground Lanka",
        "ws": "/ws"
    }


@app.get("/health")
def health_check():
    return {"status": "healthy"}