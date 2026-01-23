"""SQLite database layer for accounts and teams."""

import json
import sqlite3
from pathlib import Path
from typing import Optional

from pymeshzork.accounts.models import Account, Team


class AccountDatabase:
    """SQLite database for accounts and teams."""

    def __init__(self, db_path: Path) -> None:
        """Initialize database connection."""
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._connection: Optional[sqlite3.Connection] = None
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        """Get or create database connection."""
        if self._connection is None:
            self._connection = sqlite3.connect(str(self.db_path))
            self._connection.row_factory = sqlite3.Row
        return self._connection

    def _init_db(self) -> None:
        """Initialize database schema."""
        conn = self._get_connection()
        cursor = conn.cursor()

        # Accounts table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS accounts (
                id TEXT PRIMARY KEY,
                username TEXT UNIQUE NOT NULL,
                display_name TEXT,
                created TEXT NOT NULL,
                last_played TEXT NOT NULL,
                team_id TEXT,
                team_role TEXT,
                data TEXT NOT NULL
            )
        """)

        # Teams table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS teams (
                id TEXT PRIMARY KEY,
                name TEXT UNIQUE NOT NULL,
                tag TEXT,
                owner_id TEXT NOT NULL,
                created TEXT NOT NULL,
                data TEXT NOT NULL
            )
        """)

        # Save slots table (per-account game saves)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS saves (
                id TEXT PRIMARY KEY,
                account_id TEXT NOT NULL,
                slot_name TEXT NOT NULL,
                world_id TEXT NOT NULL,
                created TEXT NOT NULL,
                updated TEXT NOT NULL,
                room_id TEXT,
                score INTEGER DEFAULT 0,
                moves INTEGER DEFAULT 0,
                data TEXT NOT NULL,
                FOREIGN KEY (account_id) REFERENCES accounts(id),
                UNIQUE(account_id, slot_name)
            )
        """)

        # Indexes
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_accounts_username ON accounts(username)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_accounts_team ON accounts(team_id)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_teams_name ON teams(name)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_saves_account ON saves(account_id)
        """)

        conn.commit()

    def close(self) -> None:
        """Close database connection."""
        if self._connection:
            self._connection.close()
            self._connection = None

    # === Account Operations ===

    def save_account(self, account: Account) -> None:
        """Save or update an account."""
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute(
            """
            INSERT OR REPLACE INTO accounts
            (id, username, display_name, created, last_played, team_id, team_role, data)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                account.id,
                account.username,
                account.display_name,
                account.created.isoformat(),
                account.last_played.isoformat(),
                account.team_id,
                account.team_role.value if account.team_role else None,
                json.dumps(account.to_dict()),
            ),
        )
        conn.commit()

    def get_account(self, account_id: str) -> Optional[Account]:
        """Get an account by ID."""
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT data FROM accounts WHERE id = ?", (account_id,))
        row = cursor.fetchone()
        if row:
            return Account.from_dict(json.loads(row["data"]))
        return None

    def get_account_by_username(self, username: str) -> Optional[Account]:
        """Get an account by username."""
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute(
            "SELECT data FROM accounts WHERE LOWER(username) = LOWER(?)",
            (username,),
        )
        row = cursor.fetchone()
        if row:
            return Account.from_dict(json.loads(row["data"]))
        return None

    def delete_account(self, account_id: str) -> bool:
        """Delete an account and its saves."""
        conn = self._get_connection()
        cursor = conn.cursor()

        # Delete saves first
        cursor.execute("DELETE FROM saves WHERE account_id = ?", (account_id,))
        # Delete account
        cursor.execute("DELETE FROM accounts WHERE id = ?", (account_id,))
        conn.commit()
        return cursor.rowcount > 0

    def list_accounts(self) -> list[Account]:
        """List all accounts."""
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT data FROM accounts ORDER BY username")
        return [Account.from_dict(json.loads(row["data"])) for row in cursor.fetchall()]

    def username_exists(self, username: str) -> bool:
        """Check if a username is already taken."""
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute(
            "SELECT 1 FROM accounts WHERE LOWER(username) = LOWER(?)",
            (username,),
        )
        return cursor.fetchone() is not None

    # === Team Operations ===

    def save_team(self, team: Team) -> None:
        """Save or update a team."""
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute(
            """
            INSERT OR REPLACE INTO teams
            (id, name, tag, owner_id, created, data)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                team.id,
                team.name,
                team.tag,
                team.owner_id,
                team.created.isoformat(),
                json.dumps(team.to_dict()),
            ),
        )
        conn.commit()

    def get_team(self, team_id: str) -> Optional[Team]:
        """Get a team by ID."""
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT data FROM teams WHERE id = ?", (team_id,))
        row = cursor.fetchone()
        if row:
            return Team.from_dict(json.loads(row["data"]))
        return None

    def get_team_by_name(self, name: str) -> Optional[Team]:
        """Get a team by name."""
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute(
            "SELECT data FROM teams WHERE LOWER(name) = LOWER(?)",
            (name,),
        )
        row = cursor.fetchone()
        if row:
            return Team.from_dict(json.loads(row["data"]))
        return None

    def delete_team(self, team_id: str) -> bool:
        """Delete a team."""
        conn = self._get_connection()
        cursor = conn.cursor()

        # Update accounts to remove team membership
        cursor.execute(
            "UPDATE accounts SET team_id = NULL, team_role = NULL WHERE team_id = ?",
            (team_id,),
        )
        # Delete team
        cursor.execute("DELETE FROM teams WHERE id = ?", (team_id,))
        conn.commit()
        return cursor.rowcount > 0

    def list_teams(self) -> list[Team]:
        """List all teams."""
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT data FROM teams ORDER BY name")
        return [Team.from_dict(json.loads(row["data"])) for row in cursor.fetchall()]

    def team_name_exists(self, name: str) -> bool:
        """Check if a team name is already taken."""
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute(
            "SELECT 1 FROM teams WHERE LOWER(name) = LOWER(?)",
            (name,),
        )
        return cursor.fetchone() is not None

    def find_team_by_invite_code(self, code: str) -> Optional[Team]:
        """Find a team that has a matching invite code."""
        # This requires searching through all teams
        # In a larger system, we'd have a separate invites table
        for team in self.list_teams():
            if team.get_invite_by_code(code):
                return team
        return None

    # === Save Slot Operations ===

    def save_game_slot(
        self,
        account_id: str,
        slot_name: str,
        world_id: str,
        room_id: str,
        score: int,
        moves: int,
        data: dict,
    ) -> str:
        """Save a game to a slot. Returns save ID."""
        import uuid
        from datetime import datetime

        conn = self._get_connection()
        cursor = conn.cursor()

        now = datetime.utcnow().isoformat()
        save_id = str(uuid.uuid4())

        cursor.execute(
            """
            INSERT OR REPLACE INTO saves
            (id, account_id, slot_name, world_id, created, updated, room_id, score, moves, data)
            VALUES (
                COALESCE(
                    (SELECT id FROM saves WHERE account_id = ? AND slot_name = ?),
                    ?
                ),
                ?, ?, ?,
                COALESCE(
                    (SELECT created FROM saves WHERE account_id = ? AND slot_name = ?),
                    ?
                ),
                ?, ?, ?, ?, ?
            )
            """,
            (
                account_id, slot_name, save_id,  # id selection
                account_id, slot_name, world_id,  # main values
                account_id, slot_name, now,  # created selection
                now, room_id, score, moves, json.dumps(data),  # remaining values
            ),
        )
        conn.commit()

        # Get the actual ID
        cursor.execute(
            "SELECT id FROM saves WHERE account_id = ? AND slot_name = ?",
            (account_id, slot_name),
        )
        row = cursor.fetchone()
        return row["id"] if row else save_id

    def load_game_slot(self, account_id: str, slot_name: str) -> Optional[dict]:
        """Load a game from a slot."""
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute(
            "SELECT data FROM saves WHERE account_id = ? AND slot_name = ?",
            (account_id, slot_name),
        )
        row = cursor.fetchone()
        if row:
            return json.loads(row["data"])
        return None

    def delete_game_slot(self, account_id: str, slot_name: str) -> bool:
        """Delete a save slot."""
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute(
            "DELETE FROM saves WHERE account_id = ? AND slot_name = ?",
            (account_id, slot_name),
        )
        conn.commit()
        return cursor.rowcount > 0

    def list_game_slots(self, account_id: str) -> list[dict]:
        """List all save slots for an account."""
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT slot_name, world_id, created, updated, room_id, score, moves
            FROM saves
            WHERE account_id = ?
            ORDER BY updated DESC
            """,
            (account_id,),
        )

        return [
            {
                "slot_name": row["slot_name"],
                "world_id": row["world_id"],
                "created": row["created"],
                "updated": row["updated"],
                "room_id": row["room_id"],
                "score": row["score"],
                "moves": row["moves"],
            }
            for row in cursor.fetchall()
        ]
