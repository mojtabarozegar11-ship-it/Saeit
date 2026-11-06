"""Living Cities server-authoritative multiplayer-ready SOLO gameplay.

All player mutations are server-side and idempotent. No client-supplied state,
clock, rewards, balance, battle outcome or ownership value is accepted.
This module never initiates cryptocurrency transfers.
"""
import hashlib
import json
import math
import re
from datetime import timedelta

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone

from .models import PlayerWorld, WorldActionReceipt

KINDS = ("wood", "food", "stone", "crystal")
BIOMES = ("MEADOW", "COAST", "DESERT", "FOREST", "HIGHLAND", "TUNDRA")
NAMES = ("Aurora Vale", "The Azure Reach", "Saffron Meridian", "Emerald Canopy", "Crown of Clouds", "Northstar Haven")
BUILDINGS = {
    "farm": {"cost": {"wood": 32, "stone": 14}, "yield": {"food": 1.3}, "people": 10},
    "grove": {"cost": {"wood": 20, "stone": 22}, "yield": {"wood": 1.0}, "people": 5},
    "quarry": {"cost": {"wood": 48, "food": 25}, "yield": {"stone": .8}, "people": 4},
    "observatory": {"cost": {"wood": 65, "stone": 75, "crystal": 8}, "yield": {"crystal": .08}, "people": 3},
    "habitat": {"cost": {"wood": 45, "stone": 38, "food": 30}, "yield": {}, "people": 24},
    "market": {"cost": {"wood": 55, "stone": 45, "food": 24}, "yield": {"food": .32, "wood": .32}, "people": 8},
}
HERO_POWER = {"lyra": 12, "orin": 14, "sera": 10}
COUNTER = {"GUARD": "CHARGE", "CHARGE": "FLANK", "FLANK": "GUARD"}
ENEMY_TACTICS = ("CHARGE", "FLANK", "GUARD", "CHARGE", "GUARD", "FLANK")
EXPLORATION_COST = {"wood": 120, "food": 90, "stone": 70, "crystal": 10}
MAX_CARAVANS = 1000  # Match the standalone browser world's verification limit.
MAX_SAFE_JS_ID = 9007199254740991


def _require(ok, reason):
    if not ok:
        raise ValidationError(reason)


def _city(number, biome, seed, name, starter=False):
    buildings = [
        {"id": 1, "type": "habitat", "x": 4, "z": 4},
    ]
    if starter:
        buildings += [
            {"id": 2, "type": "farm", "x": 3, "z": 4},
            {"id": 3, "type": "grove", "x": 5, "z": 4},
            {"id": 4, "type": "quarry", "x": 4, "z": 5},
            {"id": 5, "type": "market", "x": 4, "z": 3},
        ]
    return {
        "id": number, "name": name, "biome": biome, "seed": seed, "level": 1,
        "population": 100, "growthSeconds": 0, "famineSeconds": 0, "resources": {"wood": 240, "food": 210, "stone": 190, "crystal": 30}
        if starter else {"wood": 35, "food": 50, "stone": 32, "crystal": 3},
        "buildings": buildings, "nextBuildingId": 6 if starter else 2, "discoveredAt": 0,
    }


def _initial():
    return {
        "version": 2, "clock": 0, "activeCityId": 1,
        "cities": [_city(1, "MEADOW", 7, "Aurora Vale", True)],
        "heroRoles": {"lyra": "explorer", "orin": "commander", "sera": "steward"},
        "caravans": [], "combat": None, "victories": 0, "events": [],
        "achievements": ["founder"], "chapters": 1, "log": ["Your first living city has awakened."],
        "nextCaravanId": 1,
    }


def _find(w, city_id=None):
    cid = w["activeCityId"] if city_id is None else city_id
    _require(type(cid) is int, "invalid_city_id")
    city = next((c for c in w["cities"] if c["id"] == cid), None)
    _require(city is not None, "city_not_owned")
    return city


def _note(w, text):
    w["log"] = [text] + w["log"][:15]


def _deduct(city, costs):
    _require(all(city["resources"][k] >= n for k, n in costs.items()), "insufficient_resources")
    for key, number in costs.items():
        city["resources"][key] -= number


def _terrain(x, z, seed, biome):
    edge = x in (0, 8) or z in (0, 8)
    h = (math.sin((x + seed * 3) * 2.37 + (z + 1) * 1.8) +
         math.cos((z + seed) * 1.19 + x * .92)) * .5
    if edge and biome == "COAST" and h < .35:
        return "water"
    if edge and biome == "TUNDRA" and h < -.25:
        return "ice"
    if h > .65:
        return "dune" if biome == "DESERT" else "hill"
    if h < -.72:
        return "pond"
    return "plain"


def _advance(w, seconds):
    seconds = min(14400, max(0., seconds))
    w["clock"] += seconds
    for city in w["cities"]:
        gains = dict.fromkeys(KINDS, 0.)
        for building in city["buildings"]:
            for kind, rate in BUILDINGS[building["type"]]["yield"].items():
                gains[kind] += rate
        for kind in KINDS:
            amount = city["resources"][kind] + gains[kind] * seconds / 60
            city["resources"][kind] = min(9999., max(0., amount))
        # Match the browser's civic economy: food and housing constrain growth.
        # The server, never client time, determines authoritative population.
        demand = city["population"] * seconds / 9000
        food_before_demand = city["resources"]["food"]
        city["resources"]["food"] = max(0., food_before_demand - demand)
        housing_capacity = 100 + sum(40 for b in city["buildings"] if b["type"] == "habitat")
        # Preserve partial civic time across frequent server snapshots.
        if seconds > 0 and food_before_demand >= demand * 1.5 and city["population"] < housing_capacity:
            elapsed = city.get("growthSeconds", 0) + seconds
            arrivals = math.floor(elapsed / 1200)
            city["population"] = min(housing_capacity, city["population"] + arrivals)
            city["growthSeconds"] = 0 if city["population"] >= housing_capacity else elapsed - arrivals * 1200
            city["famineSeconds"] = 0
        elif seconds > 0 and food_before_demand < demand:
            elapsed = city.get("famineSeconds", 0) + seconds
            losses = math.floor(elapsed / 900)
            city["population"] = max(0, city["population"] - losses)
            city["famineSeconds"] = 0 if city["population"] == 0 else elapsed - losses * 900
            city["growthSeconds"] = 0
        elif seconds > 0:
            city["growthSeconds"] = 0
            city["famineSeconds"] = 0
    underway = []
    for caravan in w["caravans"]:
        if caravan["arriveAt"] <= w["clock"]:
            receiver = _find(w, caravan["to"])
            kind = caravan["kind"]
            receiver["resources"][kind] = min(9999., receiver["resources"][kind] + caravan["amount"])
            _note(w, str(caravan["amount"]) + " " + kind + " arrived at " + receiver["name"] + ".")
        else:
            underway.append(caravan)
    w["caravans"] = underway


def _tactic(w):
    return ENEMY_TACTICS[(w["victories"] + w["combat"]["round"]) % len(ENEMY_TACTICS)]


def _command(w, payload):
    kind = payload.get("type")
    _require(isinstance(kind, str) and len(kind) <= 32, "invalid_action")
    city = _find(w)
    if kind == "construct":
        structure, x, z = payload.get("kind"), payload.get("x"), payload.get("z")
        _require(isinstance(structure, str) and structure in BUILDINGS, "unknown_building")
        _require(type(x) is int and type(z) is int and 1 <= x <= 7 and 1 <= z <= 7, "invalid_tile")
        _require(_terrain(x, z, city["seed"], city["biome"]) == "plain", "unbuildable_terrain")
        _require(all(b["x"] != x or b["z"] != z for b in city["buildings"]), "occupied_tile")
        b = BUILDINGS[structure]
        _deduct(city, b["cost"])
        city["buildings"].append({"id": city["nextBuildingId"], "type": structure, "x": x, "z": z})
        city["nextBuildingId"] += 1
        city["population"] += b["people"]
        _note(w, structure + " rises in " + city["name"] + ".")
    elif kind == "explore":
        name = payload.get("name", "")
        _require(isinstance(name, str) and len(name) <= 32, "invalid_city_name")
        _deduct(city, EXPLORATION_COST)
        _require(len(w["cities"]) < 60, "city_limit_reached")
        new_id = max(c["id"] for c in w["cities"]) + 1
        biome = BIOMES[(new_id - 1) % len(BIOMES)]
        candidate = name.strip() if len(name.strip()) >= 3 else NAMES[(new_id - 1) % len(NAMES)]
        destination = _city(new_id, biome, new_id * 11 + 7, candidate)
        destination["discoveredAt"] = w["clock"]
        w["cities"].append(destination)
        w["chapters"] = max(w["chapters"], len(w["cities"]))
        _note(w, candidate + " discovered. Its future is yours to choose.")
    elif kind == "migrate":
        _require(w["combat"] is None, "battle_in_progress")
        dest = payload.get("destination_id")
        target = _find(w, dest)
        _require(target["id"] != city["id"], "already_in_city")
        w["activeCityId"] = target["id"]
        _note(w, "Welcome to " + target["name"] + ". All your former cities remain yours.")
    elif kind == "dispatch":
        dest, cargo, amount = payload.get("destination_id"), payload.get("kind"), payload.get("amount")
        receiver = _find(w, dest)
        _require(receiver["id"] != city["id"], "invalid_destination")
        _require(cargo in KINDS, "invalid_cargo")
        _require(type(amount) is int and 1 <= amount <= 1000, "invalid_amount")
        # Browser verify() rejects >1000 caravans and non-safe IDs. Refuse
        # before charging stock so authoritative saves remain playable.
        _require(len(w["caravans"]) < MAX_CARAVANS, "caravan_limit_reached")
        _require(type(w["nextCaravanId"]) is int and 1 <= w["nextCaravanId"] < MAX_SAFE_JS_ID,
                 "caravan_id_limit_reached")
        _deduct(city, {cargo: amount})
        w["caravans"].append({
            "id": w["nextCaravanId"], "from": city["id"], "to": receiver["id"],
            "kind": cargo, "amount": amount, "arriveAt": w["clock"] + 75 + abs(city["id"] - receiver["id"]) * 35,
        })
        w["nextCaravanId"] += 1
        _note(w, "Trade convoy on its way to " + receiver["name"] + ".")
    elif kind == "hero":
        _require(w["combat"] is None, "battle_in_progress")
        hero, role = payload.get("id"), payload.get("role")
        _require(isinstance(hero, str) and hero in HERO_POWER, "unknown_hero")
        _require(role in ("commander", "steward", "explorer", "rest"), "invalid_role")
        _require(w["heroRoles"][hero] != role, "role_already_assigned")
        w["heroRoles"][hero] = role
        _note(w, hero + " assigned to " + role + ".")
    elif kind == "battle_start":
        _require(w["combat"] is None, "battle_already_in_progress")
        commander = sum(power for key, power in HERO_POWER.items() if w["heroRoles"][key] == "commander")
        _require(commander > 0, "no_commander")
        w["combat"] = {
            "round": 0, "hp": 65 + commander * 2,
            "enemyHp": 100 + w["victories"] * 6,
            "enemyName": ("The Ashbound", "Rift Marauders", "Thunder Court")[w["victories"] % 3],
            "telegraph": None, "journal": [], "won": False,
        }
        w["combat"]["telegraph"] = _tactic(w)
        _note(w, "A tactical frontier encounter begins.")
    elif kind == "battle_turn":
        tactic = payload.get("tactic")
        _require(isinstance(tactic, str) and tactic in COUNTER, "invalid_tactic")
        b = w["combat"]
        _require(b is not None and b["hp"] > 0 and b["enemyHp"] > 0, "no_active_battle")
        enemy = b["telegraph"]
        power = sum(v for h, v in HERO_POWER.items() if w["heroRoles"][h] == "commander")
        advantage = COUNTER[tactic] == enemy
        penalty = COUNTER[enemy] == tactic
        damage = max(5, math.floor(10 + power * .85 + (15 if advantage else 0) - (6 if penalty else 0) + .5))
        taken = max(4, 14 + (12 if penalty else 0) - (9 if advantage else 0))
        b["enemyHp"] = max(0, b["enemyHp"] - damage)
        if b["enemyHp"] > 0:
            b["hp"] = max(0, b["hp"] - taken)
        b["journal"].append({"tactic": tactic, "enemy": enemy, "damage": damage,
                             "taken": taken if b["enemyHp"] > 0 else 0})
        b["round"] += 1
        if b["enemyHp"] == 0:
            w["victories"] += 1
            city["resources"]["crystal"] = min(9999, city["resources"]["crystal"] + 7)
            city["resources"]["stone"] = min(9999, city["resources"]["stone"] + 48)
            b["won"] = True
            _note(w, "Frontier secured: +7 crystal and +48 stone.")
        elif b["hp"] == 0:
            _note(w, "Your heroes withdrew. All cities remain safe.")
        else:
            b["telegraph"] = _tactic(w)
    elif kind == "battle_close":
        b = w["combat"]
        _require(b is not None and (b["hp"] == 0 or b["enemyHp"] == 0), "battle_not_finished")
        w["combat"] = None
    else:
        raise ValidationError("unknown_action")


def _load_locked(owner):
    world, _ = PlayerWorld.objects.get_or_create(owner=owner, defaults={"payload": _initial()})
    return PlayerWorld.objects.select_for_update().get(pk=world.pk)


def _advance_persisted(world, now):
    # Server time is authoritative; browser-provided elapsed seconds are ignored.
    elapsed = min(14400., max(0., (now - world.last_simulated_at).total_seconds()))
    payload = world.payload
    if elapsed:
        _advance(payload, elapsed)
    return payload


@transaction.atomic
def snapshot(owner):
    model = _load_locked(owner)
    now = timezone.now()
    state = _advance_persisted(model, now)
    if (now - model.last_simulated_at).total_seconds() >= 60:
        # Polling must not write an entire JSON world every five seconds.
        model.payload = state
        model.last_simulated_at = now
        model.save(update_fields=["payload", "last_simulated_at"])
    return {"state": state, "revision": model.revision, "authority": "server"}


@transaction.atomic
def act(owner, action, key):
    _require(isinstance(action, dict), "invalid_action")
    _require(isinstance(key, str) and re.fullmatch(r"[A-Za-z0-9_-]{16,96}", key), "invalid_action_key")
    canonical = json.dumps(action, sort_keys=True, separators=(",", ":"), allow_nan=False)
    _require(len(canonical) <= 4096, "action_too_large")
    fingerprint = hashlib.sha256(canonical.encode()).hexdigest()
    model = _load_locked(owner)
    record = WorldActionReceipt.objects.filter(owner=owner, action_key=key).first()
    if record is not None:
        _require(record.action_digest == fingerprint, "idempotency_conflict")
        # Small immutable receipt prevents action replay without duplicating an
        # ever-growing world snapshot in the database for every click.
        return {
            "state": _advance_persisted(model, timezone.now()),
            "revision": model.revision, "original_revision": record.revision,
            "authority": "server", "replayed": True,
        }
    now = timezone.now()
    state = _advance_persisted(model, now)
    _command(state, action)
    model.payload = state
    model.revision += 1
    model.last_simulated_at = now
    model.save(update_fields=["payload", "revision", "last_simulated_at"])
    WorldActionReceipt.objects.create(
        owner=owner, action_key=key, action_digest=fingerprint,
        revision=model.revision,
    )
    return {"state": state, "revision": model.revision, "authority": "server", "replayed": False}
