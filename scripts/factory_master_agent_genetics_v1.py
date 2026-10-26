#!/usr/bin/env python3
"""Bounded genetic policy evolution for the private factory master cycle.

This mutates only two bounded orchestration genes. Each candidate is evaluated
against the actual private-cycle technical outcomes; the champion is retained on
regression. It never edits Python source, product slots, clearances, or release
state. Its fitness is an internal scheduler signal, never a product-quality score.
"""
import hashlib
import json
import os
from pathlib import Path
import tempfile

SCHEMA = "saeit.factory.master-agent-genome.v1"
BASE = {"source_evolution_quota": 2, "quality_return_priority": True}
QUOTA_MIN = 1
QUOTA_MAX = 5
HISTORY_LIMIT = 24


def _path(root):
    return Path(root) / "quality-excellence" / "master-agent-genetics" / "current.json"


def _valid_genome(value):
    return (isinstance(value, dict)
            and type(value.get("source_evolution_quota")) is int
            and QUOTA_MIN <= value["source_evolution_quota"] <= QUOTA_MAX
            and type(value.get("quality_return_priority")) is bool)


def _read(path):
    if path.is_symlink() or not path.is_file() or path.stat().st_size > 200_000:
        raise ValueError("MASTER_GENOME_STATE_UNSAFE")
    state = json.loads(path.read_text(encoding="utf8"))
    if (not isinstance(state, dict) or state.get("schema") != SCHEMA
            or not _valid_genome(state.get("current_genome"))
            or not _valid_genome(state.get("champion_genome"))
            or type(state.get("generation")) is not int or state["generation"] < 0
            or type(state.get("champion_fitness")) is not int
            or not 0 <= state["champion_fitness"] <= 100):
        raise ValueError("MASTER_GENOME_STATE_INVALID")
    return state


def _write(path, state):
    parent = path.parent
    if parent.is_symlink():
        raise ValueError("MASTER_GENOME_DIRECTORY_UNSAFE")
    parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(parent, 0o700)
    if path.is_symlink():
        raise ValueError("MASTER_GENOME_STATE_SYMLINK")
    fd, temporary = tempfile.mkstemp(prefix=".genome-", dir=str(parent))
    try:
        with os.fdopen(fd, "w", encoding="utf8") as stream:
            json.dump(state, stream, sort_keys=True, ensure_ascii=False, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(temporary, 0o600)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def begin_cycle(root):
    """Return the selected genome for this run, creating a safe baseline once."""
    path = _path(root)
    if path.exists():
        state = _read(path)
    else:
        state = {
            "schema": SCHEMA,
            "generation": 0,
            "current_genome": dict(BASE),
            "champion_genome": dict(BASE),
            "champion_fitness": 0,
            "history": [],
            "selection": "baseline",
        }
        _write(path, state)
    genome = dict(state["current_genome"])
    genome["generation"] = state["generation"]
    return genome


def _fitness(outcome):
    """0-100 operational fitness; never represents product certification."""
    score = 0
    if outcome.get("cycle_status") == "ok":
        score += 30
    if outcome.get("artifact_qa_passed") is True:
        score += 50
    attempted = outcome.get("source_evolution_attempted_count", 0)
    evolved = outcome.get("genuinely_evolved_source_count", 0)
    if type(attempted) is not int or attempted < 0:
        attempted = 0
    if type(evolved) is not int or evolved < 0:
        evolved = 0
    if attempted:
        score += round(20 * min(evolved, attempted) / attempted)
    return max(0, min(100, score))


def _mutate(parent, generation, fitness):
    child = dict(parent)
    seed = hashlib.sha256(json.dumps(
        {"parent": parent, "generation": generation, "fitness": fitness},
        sort_keys=True, separators=(",", ":")).encode("utf8")).digest()
    if seed[0] % 2 == 0:
        step = 1 if seed[1] % 2 == 0 else -1
        candidate = child["source_evolution_quota"] + step
        if candidate < QUOTA_MIN or candidate > QUOTA_MAX:
            candidate = child["source_evolution_quota"] - step
        child["source_evolution_quota"] = candidate
        gene = "source_evolution_quota"
    else:
        child["quality_return_priority"] = not child["quality_return_priority"]
        gene = "quality_return_priority"
    return child, gene


def finish_cycle(root, genome, outcome):
    """Score the real cycle, select a champion, mutate its next bounded child."""
    if not _valid_genome({k: genome.get(k) for k in BASE}):
        raise ValueError("MASTER_GENOME_INPUT_INVALID")
    path = _path(root)
    state = _read(path)
    generation = genome.get("generation")
    if type(generation) is not int or generation != state["generation"]:
        raise ValueError("MASTER_GENOME_GENERATION_MISMATCH")
    evaluated = {k: genome[k] for k in BASE}
    fitness = _fitness(outcome)
    champion = dict(state["champion_genome"])
    champion_fitness = state["champion_fitness"]
    if fitness > champion_fitness:
        champion = evaluated
        champion_fitness = fitness
        selection = "candidate_promoted"
    else:
        selection = "champion_retained"
    next_generation = generation + 1
    child, mutated_gene = _mutate(champion, next_generation, max(fitness, champion_fitness))
    history = list(state.get("history", []))
    history.append({
        "generation": generation,
        "genome": evaluated,
        "fitness": fitness,
        "fitness_scope": "private_cycle_reliability_and_source_evolution_only",
        "selection": selection,
        "next_mutated_gene": mutated_gene,
    })
    state = {
        "schema": SCHEMA,
        "generation": next_generation,
        "current_genome": child,
        "champion_genome": champion,
        "champion_fitness": champion_fitness,
        "history": history[-HISTORY_LIMIT:],
        "selection": selection,
        "last_fitness": fitness,
        "product_quality_certification": False,
        "commercial_release": False,
    }
    _write(path, state)
    return {
        "schema": SCHEMA,
        "evaluated_generation": generation,
        "next_generation": next_generation,
        "fitness": fitness,
        "selected": selection,
        "mutated_gene": mutated_gene,
        "current_genome": child,
        "product_quality_certification": False,
        "commercial_release": False,
    }
