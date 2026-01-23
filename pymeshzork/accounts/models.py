"""Data models for accounts and teams."""

import secrets
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Optional


class TeamRole(Enum):
    """Team member roles."""

    OWNER = "owner"
    OFFICER = "officer"
    MEMBER = "member"


class JoinPolicy(Enum):
    """Team join policies."""

    OPEN = "open"  # Anyone can join
    PASSWORD = "password"  # Requires password
    INVITE_ONLY = "invite_only"  # Requires invite code
    CLOSED = "closed"  # No new members


@dataclass
class Account:
    """Player account."""

    id: str  # UUID
    username: str
    display_name: str = ""
    created: datetime = field(default_factory=datetime.utcnow)
    last_played: datetime = field(default_factory=datetime.utcnow)
    team_id: Optional[str] = None
    team_role: TeamRole = TeamRole.MEMBER

    # Statistics
    total_score: int = 0
    total_moves: int = 0
    total_deaths: int = 0
    games_played: int = 0
    worlds_completed: list[str] = field(default_factory=list)
    achievements: list[str] = field(default_factory=list)

    @classmethod
    def create(cls, username: str, display_name: str = "") -> "Account":
        """Create a new account."""
        return cls(
            id=str(uuid.uuid4()),
            username=username,
            display_name=display_name or username,
        )

    def to_dict(self) -> dict:
        """Serialize to dictionary."""
        return {
            "id": self.id,
            "username": self.username,
            "display_name": self.display_name,
            "created": self.created.isoformat(),
            "last_played": self.last_played.isoformat(),
            "team_id": self.team_id,
            "team_role": self.team_role.value if self.team_role else None,
            "total_score": self.total_score,
            "total_moves": self.total_moves,
            "total_deaths": self.total_deaths,
            "games_played": self.games_played,
            "worlds_completed": self.worlds_completed,
            "achievements": self.achievements,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Account":
        """Deserialize from dictionary."""
        return cls(
            id=data["id"],
            username=data["username"],
            display_name=data.get("display_name", ""),
            created=datetime.fromisoformat(data["created"]),
            last_played=datetime.fromisoformat(data["last_played"]),
            team_id=data.get("team_id"),
            team_role=TeamRole(data["team_role"]) if data.get("team_role") else TeamRole.MEMBER,
            total_score=data.get("total_score", 0),
            total_moves=data.get("total_moves", 0),
            total_deaths=data.get("total_deaths", 0),
            games_played=data.get("games_played", 0),
            worlds_completed=data.get("worlds_completed", []),
            achievements=data.get("achievements", []),
        )


@dataclass
class TeamMember:
    """Team membership record."""

    player_id: str
    username: str
    role: TeamRole
    joined: datetime = field(default_factory=datetime.utcnow)
    last_active: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> dict:
        """Serialize to dictionary."""
        return {
            "player_id": self.player_id,
            "username": self.username,
            "role": self.role.value,
            "joined": self.joined.isoformat(),
            "last_active": self.last_active.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "TeamMember":
        """Deserialize from dictionary."""
        return cls(
            player_id=data["player_id"],
            username=data["username"],
            role=TeamRole(data["role"]),
            joined=datetime.fromisoformat(data["joined"]),
            last_active=datetime.fromisoformat(data["last_active"]),
        )


@dataclass
class TeamInvite:
    """Team invite."""

    id: str  # UUID
    team_id: str
    inviter_id: str
    invitee_id: Optional[str] = None  # Specific player or None for generic
    code: str = ""  # Invite code
    created: datetime = field(default_factory=datetime.utcnow)
    expires: datetime = field(default_factory=lambda: datetime.utcnow() + timedelta(days=7))
    max_uses: int = 1
    uses: int = 0

    @classmethod
    def create(
        cls,
        team_id: str,
        inviter_id: str,
        invitee_id: Optional[str] = None,
        max_uses: int = 1,
        expires_days: int = 7,
    ) -> "TeamInvite":
        """Create a new invite."""
        return cls(
            id=str(uuid.uuid4()),
            team_id=team_id,
            inviter_id=inviter_id,
            invitee_id=invitee_id,
            code=cls._generate_code(),
            expires=datetime.utcnow() + timedelta(days=expires_days),
            max_uses=max_uses,
        )

    @staticmethod
    def _generate_code() -> str:
        """Generate a secure invite code."""
        # 6 character alphanumeric code
        return secrets.token_urlsafe(4)[:6].upper()

    def is_valid(self) -> bool:
        """Check if invite is still valid."""
        if self.uses >= self.max_uses:
            return False
        if datetime.utcnow() > self.expires:
            return False
        return True

    def can_use(self, player_id: str) -> bool:
        """Check if a specific player can use this invite."""
        if not self.is_valid():
            return False
        if self.invitee_id and self.invitee_id != player_id:
            return False
        return True

    def to_dict(self) -> dict:
        """Serialize to dictionary."""
        return {
            "id": self.id,
            "team_id": self.team_id,
            "inviter_id": self.inviter_id,
            "invitee_id": self.invitee_id,
            "code": self.code,
            "created": self.created.isoformat(),
            "expires": self.expires.isoformat(),
            "max_uses": self.max_uses,
            "uses": self.uses,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "TeamInvite":
        """Deserialize from dictionary."""
        return cls(
            id=data["id"],
            team_id=data["team_id"],
            inviter_id=data["inviter_id"],
            invitee_id=data.get("invitee_id"),
            code=data["code"],
            created=datetime.fromisoformat(data["created"]),
            expires=datetime.fromisoformat(data["expires"]),
            max_uses=data.get("max_uses", 1),
            uses=data.get("uses", 0),
        )


@dataclass
class TeamSettings:
    """Team settings."""

    max_players: int = 8  # 1-50
    join_policy: JoinPolicy = JoinPolicy.INVITE_ONLY
    password_hash: Optional[str] = None  # bcrypt hash
    allow_friendly_fire: bool = False
    shared_discoveries: bool = True

    def to_dict(self) -> dict:
        """Serialize to dictionary."""
        return {
            "max_players": self.max_players,
            "join_policy": self.join_policy.value,
            "password_hash": self.password_hash,
            "allow_friendly_fire": self.allow_friendly_fire,
            "shared_discoveries": self.shared_discoveries,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "TeamSettings":
        """Deserialize from dictionary."""
        return cls(
            max_players=data.get("max_players", 8),
            join_policy=JoinPolicy(data.get("join_policy", "invite_only")),
            password_hash=data.get("password_hash"),
            allow_friendly_fire=data.get("allow_friendly_fire", False),
            shared_discoveries=data.get("shared_discoveries", True),
        )


@dataclass
class TeamStats:
    """Team statistics."""

    total_score: int = 0
    total_treasures: int = 0
    total_deaths: int = 0
    worlds_completed: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        """Serialize to dictionary."""
        return {
            "total_score": self.total_score,
            "total_treasures": self.total_treasures,
            "total_deaths": self.total_deaths,
            "worlds_completed": self.worlds_completed,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "TeamStats":
        """Deserialize from dictionary."""
        return cls(
            total_score=data.get("total_score", 0),
            total_treasures=data.get("total_treasures", 0),
            total_deaths=data.get("total_deaths", 0),
            worlds_completed=data.get("worlds_completed", []),
        )


@dataclass
class Team:
    """Team/guild."""

    id: str  # UUID
    name: str
    tag: str = ""  # 2-4 character tag
    created: datetime = field(default_factory=datetime.utcnow)
    owner_id: str = ""
    settings: TeamSettings = field(default_factory=TeamSettings)
    members: list[TeamMember] = field(default_factory=list)
    invites: list[TeamInvite] = field(default_factory=list)
    stats: TeamStats = field(default_factory=TeamStats)

    @classmethod
    def create(
        cls,
        name: str,
        owner: Account,
        tag: str = "",
        max_players: int = 8,
    ) -> "Team":
        """Create a new team."""
        team = cls(
            id=str(uuid.uuid4()),
            name=name,
            tag=tag[:4].upper() if tag else "",
            owner_id=owner.id,
            settings=TeamSettings(max_players=max_players),
        )
        # Add owner as first member
        team.members.append(
            TeamMember(
                player_id=owner.id,
                username=owner.username,
                role=TeamRole.OWNER,
            )
        )
        return team

    @property
    def member_count(self) -> int:
        """Get current member count."""
        return len(self.members)

    @property
    def is_full(self) -> bool:
        """Check if team is at capacity."""
        return self.member_count >= self.settings.max_players

    @property
    def capacity_percent(self) -> float:
        """Get capacity percentage."""
        if self.settings.max_players == 0:
            return 100.0
        return (self.member_count / self.settings.max_players) * 100

    def get_member(self, player_id: str) -> Optional[TeamMember]:
        """Get a member by player ID."""
        for member in self.members:
            if member.player_id == player_id:
                return member
        return None

    def get_member_by_username(self, username: str) -> Optional[TeamMember]:
        """Get a member by username."""
        username_lower = username.lower()
        for member in self.members:
            if member.username.lower() == username_lower:
                return member
        return None

    def has_permission(self, player_id: str, required_role: TeamRole) -> bool:
        """Check if player has required role or higher."""
        member = self.get_member(player_id)
        if not member:
            return False

        role_hierarchy = {
            TeamRole.OWNER: 3,
            TeamRole.OFFICER: 2,
            TeamRole.MEMBER: 1,
        }
        return role_hierarchy.get(member.role, 0) >= role_hierarchy.get(required_role, 0)

    def add_member(self, account: Account, role: TeamRole = TeamRole.MEMBER) -> bool:
        """Add a member to the team."""
        if self.is_full:
            return False
        if self.get_member(account.id):
            return False  # Already a member

        self.members.append(
            TeamMember(
                player_id=account.id,
                username=account.username,
                role=role,
            )
        )
        return True

    def remove_member(self, player_id: str) -> bool:
        """Remove a member from the team."""
        for i, member in enumerate(self.members):
            if member.player_id == player_id:
                if member.role == TeamRole.OWNER:
                    return False  # Can't remove owner
                del self.members[i]
                return True
        return False

    def promote_member(self, player_id: str) -> bool:
        """Promote a member to officer."""
        member = self.get_member(player_id)
        if not member or member.role != TeamRole.MEMBER:
            return False
        member.role = TeamRole.OFFICER
        return True

    def demote_member(self, player_id: str) -> bool:
        """Demote an officer to member."""
        member = self.get_member(player_id)
        if not member or member.role != TeamRole.OFFICER:
            return False
        member.role = TeamRole.MEMBER
        return True

    def transfer_ownership(self, new_owner_id: str) -> bool:
        """Transfer ownership to another member."""
        new_owner = self.get_member(new_owner_id)
        if not new_owner:
            return False

        # Demote current owner to officer
        current_owner = self.get_member(self.owner_id)
        if current_owner:
            current_owner.role = TeamRole.OFFICER

        # Promote new owner
        new_owner.role = TeamRole.OWNER
        self.owner_id = new_owner_id
        return True

    def get_invite_by_code(self, code: str) -> Optional[TeamInvite]:
        """Get an invite by code."""
        code_upper = code.upper()
        for invite in self.invites:
            if invite.code == code_upper:
                return invite
        return None

    def cleanup_expired_invites(self) -> int:
        """Remove expired invites. Returns count removed."""
        initial_count = len(self.invites)
        self.invites = [i for i in self.invites if i.is_valid()]
        return initial_count - len(self.invites)

    def to_dict(self) -> dict:
        """Serialize to dictionary."""
        return {
            "id": self.id,
            "name": self.name,
            "tag": self.tag,
            "created": self.created.isoformat(),
            "owner_id": self.owner_id,
            "settings": self.settings.to_dict(),
            "members": [m.to_dict() for m in self.members],
            "invites": [i.to_dict() for i in self.invites],
            "stats": self.stats.to_dict(),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Team":
        """Deserialize from dictionary."""
        return cls(
            id=data["id"],
            name=data["name"],
            tag=data.get("tag", ""),
            created=datetime.fromisoformat(data["created"]),
            owner_id=data["owner_id"],
            settings=TeamSettings.from_dict(data.get("settings", {})),
            members=[TeamMember.from_dict(m) for m in data.get("members", [])],
            invites=[TeamInvite.from_dict(i) for i in data.get("invites", [])],
            stats=TeamStats.from_dict(data.get("stats", {})),
        )
