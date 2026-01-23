"""Save/load persistence for PyMeshZork."""

import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from pymeshzork.engine.state import GameState


@dataclass
class SaveMetadata:
    """Metadata for a save file."""

    save_id: str
    player_id: str
    created: datetime
    modified: datetime
    room_name: str
    score: int
    moves: int
    world_id: str
    slot_name: str = "Quick Save"


@dataclass
class PlayerAccount:
    """Player account information."""

    player_id: str
    username: str
    created: datetime
    last_played: datetime
    total_play_time: int = 0  # seconds
    saves: list[str] = field(default_factory=list)


class SaveManager:
    """Manages save files and player accounts."""

    SAVE_VERSION = 1

    def __init__(self, save_dir: Path | None = None) -> None:
        """Initialize save manager."""
        self.save_dir = save_dir or (Path.home() / ".pymeshzork" / "saves")
        self.accounts_file = self.save_dir / "accounts.json"

    def ensure_dirs(self) -> None:
        """Ensure save directories exist."""
        self.save_dir.mkdir(parents=True, exist_ok=True)

    def create_account(self, username: str) -> PlayerAccount:
        """Create a new player account."""
        self.ensure_dirs()

        account = PlayerAccount(
            player_id=str(uuid.uuid4()),
            username=username,
            created=datetime.now(),
            last_played=datetime.now(),
        )

        self._save_account(account)
        return account

    def get_account(self, player_id: str) -> PlayerAccount | None:
        """Get a player account by ID."""
        accounts = self._load_accounts()
        for acc in accounts:
            if acc.player_id == player_id:
                return acc
        return None

    def list_accounts(self) -> list[PlayerAccount]:
        """List all player accounts."""
        return self._load_accounts()

    def save_game(
        self,
        state: GameState,
        player_id: str,
        world_id: str = "classic_zork",
        slot_name: str = "Quick Save",
        room_name: str = "",
    ) -> str:
        """Save a game state. Returns save ID."""
        self.ensure_dirs()

        save_id = str(uuid.uuid4())
        now = datetime.now()

        # Create save data
        save_data = {
            "version": self.SAVE_VERSION,
            "save_id": save_id,
            "player_id": player_id,
            "world_id": world_id,
            "created": now.isoformat(),
            "modified": now.isoformat(),
            "slot_name": slot_name,
            "room_name": room_name,
            "score": state.score,
            "moves": state.moves,
            "state": state.to_dict(),
        }

        # Write save file
        save_file = self.save_dir / f"{save_id}.json"
        with open(save_file, "w") as f:
            json.dump(save_data, f, indent=2)

        # Update account
        account = self.get_account(player_id)
        if account:
            if save_id not in account.saves:
                account.saves.append(save_id)
            account.last_played = now
            self._save_account(account)

        return save_id

    def load_game(self, save_id: str) -> tuple[GameState | None, dict | None]:
        """Load a game state. Returns (state, metadata) or (None, None)."""
        save_file = self.save_dir / f"{save_id}.json"

        if not save_file.exists():
            return None, None

        try:
            with open(save_file) as f:
                save_data = json.load(f)

            state = GameState.from_dict(save_data["state"])
            metadata = {
                "save_id": save_data["save_id"],
                "player_id": save_data["player_id"],
                "world_id": save_data["world_id"],
                "slot_name": save_data["slot_name"],
                "room_name": save_data["room_name"],
                "score": save_data["score"],
                "moves": save_data["moves"],
                "created": save_data["created"],
                "modified": save_data["modified"],
            }

            return state, metadata

        except (json.JSONDecodeError, KeyError):
            return None, None

    def list_saves(self, player_id: str | None = None) -> list[dict]:
        """List all saves, optionally filtered by player."""
        saves = []

        for save_file in self.save_dir.glob("*.json"):
            if save_file.name == "accounts.json":
                continue

            try:
                with open(save_file) as f:
                    save_data = json.load(f)

                if player_id and save_data.get("player_id") != player_id:
                    continue

                saves.append({
                    "save_id": save_data["save_id"],
                    "player_id": save_data["player_id"],
                    "slot_name": save_data["slot_name"],
                    "room_name": save_data["room_name"],
                    "score": save_data["score"],
                    "moves": save_data["moves"],
                    "modified": save_data["modified"],
                })
            except (json.JSONDecodeError, KeyError):
                continue

        # Sort by modified date, newest first
        saves.sort(key=lambda s: s["modified"], reverse=True)
        return saves

    def delete_save(self, save_id: str) -> bool:
        """Delete a save file."""
        save_file = self.save_dir / f"{save_id}.json"

        if save_file.exists():
            save_file.unlink()
            return True
        return False

    def _load_accounts(self) -> list[PlayerAccount]:
        """Load all accounts from file."""
        if not self.accounts_file.exists():
            return []

        try:
            with open(self.accounts_file) as f:
                data = json.load(f)

            accounts = []
            for acc_data in data.get("accounts", []):
                accounts.append(PlayerAccount(
                    player_id=acc_data["player_id"],
                    username=acc_data["username"],
                    created=datetime.fromisoformat(acc_data["created"]),
                    last_played=datetime.fromisoformat(acc_data["last_played"]),
                    total_play_time=acc_data.get("total_play_time", 0),
                    saves=acc_data.get("saves", []),
                ))
            return accounts

        except (json.JSONDecodeError, KeyError):
            return []

    def _save_account(self, account: PlayerAccount) -> None:
        """Save an account to file."""
        accounts = self._load_accounts()

        # Update or add account
        found = False
        for i, acc in enumerate(accounts):
            if acc.player_id == account.player_id:
                accounts[i] = account
                found = True
                break

        if not found:
            accounts.append(account)

        # Write to file
        data = {
            "accounts": [
                {
                    "player_id": acc.player_id,
                    "username": acc.username,
                    "created": acc.created.isoformat(),
                    "last_played": acc.last_played.isoformat(),
                    "total_play_time": acc.total_play_time,
                    "saves": acc.saves,
                }
                for acc in accounts
            ]
        }

        self.ensure_dirs()
        with open(self.accounts_file, "w") as f:
            json.dump(data, f, indent=2)
