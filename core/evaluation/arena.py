"""
Blinded Multi-Model Comparative Elo Arena & Automated Leaderboard.

Provides:
- ArenaMatch: Representation of an evaluation battle between two models.
- ModelEloRating: Tracks Elo score, match count, wins, losses, and ties.
- ComparativeEloArena: Manages blinded A/B comparisons and computes dynamic Elo ratings.
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class ModelEloRating:
    model_name: str
    elo: float = 1200.0
    matches_played: int = 0
    wins: int = 0
    losses: int = 0
    ties: int = 0

    @property
    def win_rate(self) -> float:
        if self.matches_played == 0:
            return 0.0
        return round(self.wins / self.matches_played, 3)


@dataclass
class ArenaMatch:
    match_id: str
    prompt: str
    model_a: str
    model_b: str
    response_a: str
    response_b: str
    winner: str  # 'model_a', 'model_b', or 'tie'
    rationale: str = ""
    domain: str = "general"


class ComparativeEloArena:
    """Orchestrates head-to-head model matches and maintains an Elo leaderboard."""

    def __init__(self, k_factor: float = 32.0, default_elo: float = 1200.0):
        self.k_factor = k_factor
        self.default_elo = default_elo
        self.ratings: Dict[str, ModelEloRating] = {}
        self.match_history: List[ArenaMatch] = []

    def _get_or_create_rating(self, model_name: str) -> ModelEloRating:
        if model_name not in self.ratings:
            self.ratings[model_name] = ModelEloRating(model_name=model_name, elo=self.default_elo)
        return self.ratings[model_name]

    def record_match(
        self,
        match_id: str,
        prompt: str,
        model_a: str,
        model_b: str,
        winner: str,
        response_a: str = "",
        response_b: str = "",
        rationale: str = "",
        domain: str = "general",
    ) -> Tuple[float, float]:
        """
        Record match outcome and update Elo ratings for model_a and model_b.
        winner: 'model_a', 'model_b', or 'tie'.
        Returns (new_elo_a, new_elo_b).
        """
        r_a = self._get_or_create_rating(model_a)
        r_b = self._get_or_create_rating(model_b)

        # Expected score
        exp_a = 1.0 / (1.0 + math.pow(10, (r_b.elo - r_a.elo) / 400.0))
        exp_b = 1.0 - exp_a

        # Actual score S_A, S_B
        if winner == "model_a":
            s_a, s_b = 1.0, 0.0
            r_a.wins += 1
            r_b.losses += 1
        elif winner == "model_b":
            s_a, s_b = 0.0, 1.0
            r_b.wins += 1
            r_a.losses += 1
        else:
            s_a, s_b = 0.5, 0.5
            r_a.ties += 1
            r_b.ties += 1

        r_a.matches_played += 1
        r_b.matches_played += 1

        # Apply Elo delta
        r_a.elo = round(r_a.elo + self.k_factor * (s_a - exp_a), 1)
        r_b.elo = round(r_b.elo + self.k_factor * (s_b - exp_b), 1)

        match = ArenaMatch(
            match_id=match_id,
            prompt=prompt,
            model_a=model_a,
            model_b=model_b,
            response_a=response_a,
            response_b=response_b,
            winner=winner,
            rationale=rationale,
            domain=domain,
        )
        self.match_history.append(match)

        return r_a.elo, r_b.elo

    def get_leaderboard(self) -> List[Dict[str, Any]]:
        """Return sorted leaderboard ranked by Elo rating descending."""
        sorted_models = sorted(self.ratings.values(), key=lambda r: r.elo, reverse=True)
        return [
            {
                "rank": idx + 1,
                "model_name": r.model_name,
                "elo": r.elo,
                "win_rate": r.win_rate,
                "matches": r.matches_played,
                "record": f"{r.wins}W-{r.losses}L-{r.ties}T",
            }
            for idx, r in enumerate(sorted_models)
        ]
