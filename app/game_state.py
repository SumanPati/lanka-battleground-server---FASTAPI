import random

clients = set()

PLAYER_CHARACTERS = {
    "hanuman": {"img": "Character/hanuman.jpg"},
    "kumbhakarna": {"img": "Character/kumbhakarna.jpg"},
    "lakshmana": {"img": "Character/lakshmana.jpg"},
    "rama": {"img": "Character/rama.jpg"},
    "ravana": {"img": "Character/ravana.jpg"},
    "sita": {"img": "Character/sita.jpg"},
}

available_characters = list(PLAYER_CHARACTERS.keys())

def get_random_character():
    global available_characters
    if not available_characters:
        available_characters = list(PLAYER_CHARACTERS.keys())

    key = random.choice(available_characters)
    available_characters.remove(key)
    return {"name": key, **PLAYER_CHARACTERS[key]}


game_state = {
    "deck": [],
    "board": [],
    "players": {},
    "cardIdCounter": 0,
}


async def broadcast_state():
    payload = {"type": "STATE", "state": game_state}
    for ws in clients:
        await ws.send_json(payload)


def handle_join(ws, player):
    clients.add(ws)

    if player not in game_state["players"]:
        game_state["players"][player] = {
            "health": 30,
            "maxHealth": 30,
            "hand": [],
            "character": get_random_character(),
        }


def handle_update(state):
    global game_state
    game_state = state


def handle_reset():
    game_state["board"] = []
    game_state["cardIdCounter"] = 0

    for p in game_state["players"].values():
        p["health"] = 30
        p["hand"] = []
