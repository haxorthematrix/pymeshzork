"""High-level managers for accounts and teams."""

from pathlib import Path
from typing import Optional
import bcrypt

from pymeshzork.accounts.database import AccountDatabase
from pymeshzork.accounts.models import (
    Account,
    Team,
    TeamInvite,
    TeamRole,
    JoinPolicy,
)


class AccountError(Exception):
    """Base exception for account operations."""

    pass


class TeamError(Exception):
    """Base exception for team operations."""

    pass


class AccountManager:
    """High-level account management."""

    def __init__(self, db: AccountDatabase) -> None:
        """Initialize with database."""
        self.db = db

    def create_account(self, username: str, display_name: str = "") -> Account:
        """Create a new account.

        Args:
            username: Unique username (3-20 chars, alphanumeric + underscore)
            display_name: Optional display name

        Returns:
            Created account

        Raises:
            AccountError: If username is invalid or taken
        """
        # Validate username
        username = username.strip()
        if not self._is_valid_username(username):
            raise AccountError(
                "Username must be 3-20 characters, alphanumeric or underscore"
            )

        # Check if taken
        if self.db.username_exists(username):
            raise AccountError(f"Username '{username}' is already taken")

        # Create account
        account = Account.create(username, display_name)
        self.db.save_account(account)
        return account

    def get_account(self, account_id: str) -> Optional[Account]:
        """Get account by ID."""
        return self.db.get_account(account_id)

    def get_account_by_username(self, username: str) -> Optional[Account]:
        """Get account by username (case-insensitive)."""
        return self.db.get_account_by_username(username)

    def update_account(self, account: Account) -> None:
        """Save updated account."""
        self.db.save_account(account)

    def delete_account(self, account_id: str) -> bool:
        """Delete an account and its saves."""
        account = self.db.get_account(account_id)
        if not account:
            return False

        # If account is a team owner, they must transfer ownership first
        if account.team_id:
            team = self.db.get_team(account.team_id)
            if team and team.owner_id == account_id:
                raise AccountError(
                    "Cannot delete account while owning a team. "
                    "Transfer ownership or disband the team first."
                )

        return self.db.delete_account(account_id)

    def list_accounts(self) -> list[Account]:
        """List all accounts."""
        return self.db.list_accounts()

    def update_last_played(self, account: Account) -> None:
        """Update last played timestamp."""
        from datetime import datetime

        account.last_played = datetime.utcnow()
        self.db.save_account(account)

    def add_game_stats(
        self,
        account: Account,
        score: int = 0,
        moves: int = 0,
        deaths: int = 0,
    ) -> None:
        """Add game statistics to account."""
        account.total_score += score
        account.total_moves += moves
        account.total_deaths += deaths
        account.games_played += 1
        self.db.save_account(account)

    def add_achievement(self, account: Account, achievement: str) -> bool:
        """Add an achievement to account. Returns False if already earned."""
        if achievement in account.achievements:
            return False
        account.achievements.append(achievement)
        self.db.save_account(account)
        return True

    def mark_world_completed(self, account: Account, world_id: str) -> bool:
        """Mark a world as completed. Returns False if already completed."""
        if world_id in account.worlds_completed:
            return False
        account.worlds_completed.append(world_id)
        self.db.save_account(account)
        return True

    @staticmethod
    def _is_valid_username(username: str) -> bool:
        """Check if username is valid."""
        if len(username) < 3 or len(username) > 20:
            return False
        return all(c.isalnum() or c == "_" for c in username)


class TeamManager:
    """High-level team management."""

    def __init__(self, db: AccountDatabase) -> None:
        """Initialize with database."""
        self.db = db

    def create_team(
        self,
        name: str,
        owner: Account,
        tag: str = "",
        max_players: int = 8,
    ) -> Team:
        """Create a new team.

        Args:
            name: Team name (3-30 chars)
            owner: Account creating the team
            tag: Optional 2-4 char tag
            max_players: Max team size (1-50)

        Returns:
            Created team

        Raises:
            TeamError: If name is invalid, taken, or owner already in a team
        """
        # Validate name
        name = name.strip()
        if not self._is_valid_team_name(name):
            raise TeamError("Team name must be 3-30 characters")

        # Check if taken
        if self.db.team_name_exists(name):
            raise TeamError(f"Team name '{name}' is already taken")

        # Check if owner is already in a team
        if owner.team_id:
            raise TeamError("You must leave your current team before creating a new one")

        # Validate max_players
        max_players = max(1, min(50, max_players))

        # Create team
        team = Team.create(name, owner, tag, max_players)
        self.db.save_team(team)

        # Update owner's team membership
        owner.team_id = team.id
        owner.team_role = TeamRole.OWNER
        self.db.save_account(owner)

        return team

    def get_team(self, team_id: str) -> Optional[Team]:
        """Get team by ID."""
        return self.db.get_team(team_id)

    def get_team_by_name(self, name: str) -> Optional[Team]:
        """Get team by name (case-insensitive)."""
        return self.db.get_team_by_name(name)

    def update_team(self, team: Team) -> None:
        """Save updated team."""
        self.db.save_team(team)

    def delete_team(self, team_id: str, requester_id: str) -> bool:
        """Delete a team. Only owner can delete.

        Raises:
            TeamError: If requester is not the owner
        """
        team = self.db.get_team(team_id)
        if not team:
            return False

        if team.owner_id != requester_id:
            raise TeamError("Only the team owner can disband the team")

        # Clear team membership from all accounts
        for member in team.members:
            account = self.db.get_account(member.player_id)
            if account:
                account.team_id = None
                account.team_role = TeamRole.MEMBER
                self.db.save_account(account)

        return self.db.delete_team(team_id)

    def list_teams(self) -> list[Team]:
        """List all teams."""
        return self.db.list_teams()

    def join_team(
        self,
        account: Account,
        team: Team,
        password: Optional[str] = None,
        invite_code: Optional[str] = None,
    ) -> bool:
        """Join a team.

        Args:
            account: Account joining
            team: Team to join
            password: Password if required
            invite_code: Invite code if required

        Returns:
            True if joined successfully

        Raises:
            TeamError: If join fails
        """
        # Check if already in a team
        if account.team_id:
            raise TeamError("You must leave your current team first")

        # Check if team is full
        if team.is_full:
            raise TeamError("Team is full")

        # Check join policy
        policy = team.settings.join_policy
        if policy == JoinPolicy.CLOSED:
            raise TeamError("Team is not accepting new members")

        elif policy == JoinPolicy.PASSWORD:
            if not password:
                raise TeamError("Password required to join this team")
            if not self._verify_password(password, team.settings.password_hash):
                raise TeamError("Incorrect password")

        elif policy == JoinPolicy.INVITE_ONLY:
            if not invite_code:
                raise TeamError("Invite code required to join this team")
            invite = team.get_invite_by_code(invite_code)
            if not invite or not invite.can_use(account.id):
                raise TeamError("Invalid or expired invite code")
            # Mark invite as used
            invite.uses += 1
            self.db.save_team(team)

        # Add member
        if not team.add_member(account):
            raise TeamError("Failed to join team")

        # Update account
        account.team_id = team.id
        account.team_role = TeamRole.MEMBER
        self.db.save_account(account)
        self.db.save_team(team)

        return True

    def leave_team(self, account: Account) -> bool:
        """Leave current team.

        Raises:
            TeamError: If account is owner
        """
        if not account.team_id:
            raise TeamError("You are not in a team")

        team = self.db.get_team(account.team_id)
        if not team:
            # Team doesn't exist, clear membership
            account.team_id = None
            account.team_role = TeamRole.MEMBER
            self.db.save_account(account)
            return True

        if team.owner_id == account.id:
            raise TeamError(
                "Owner cannot leave the team. Transfer ownership or disband the team."
            )

        # Remove from team
        team.remove_member(account.id)
        self.db.save_team(team)

        # Update account
        account.team_id = None
        account.team_role = TeamRole.MEMBER
        self.db.save_account(account)

        return True

    def kick_member(
        self, team: Team, kicker_id: str, target_id: str
    ) -> bool:
        """Kick a member from the team.

        Args:
            team: The team
            kicker_id: ID of account doing the kicking
            target_id: ID of account to kick

        Raises:
            TeamError: If kicker lacks permission
        """
        # Check permission (officers can kick members, owner can kick anyone)
        kicker = team.get_member(kicker_id)
        target = team.get_member(target_id)

        if not kicker or not target:
            raise TeamError("Member not found")

        if target.role == TeamRole.OWNER:
            raise TeamError("Cannot kick the team owner")

        if kicker.role == TeamRole.MEMBER:
            raise TeamError("You don't have permission to kick members")

        if kicker.role == TeamRole.OFFICER and target.role == TeamRole.OFFICER:
            raise TeamError("Officers cannot kick other officers")

        # Remove member
        team.remove_member(target_id)
        self.db.save_team(team)

        # Update kicked account
        account = self.db.get_account(target_id)
        if account:
            account.team_id = None
            account.team_role = TeamRole.MEMBER
            self.db.save_account(account)

        return True

    def promote_member(self, team: Team, promoter_id: str, target_id: str) -> bool:
        """Promote a member to officer.

        Raises:
            TeamError: If promoter lacks permission
        """
        if not team.has_permission(promoter_id, TeamRole.OWNER):
            raise TeamError("Only the owner can promote members")

        if not team.promote_member(target_id):
            raise TeamError("Cannot promote this member")

        self.db.save_team(team)

        # Update account
        account = self.db.get_account(target_id)
        if account:
            account.team_role = TeamRole.OFFICER
            self.db.save_account(account)

        return True

    def demote_member(self, team: Team, demoter_id: str, target_id: str) -> bool:
        """Demote an officer to member.

        Raises:
            TeamError: If demoter lacks permission
        """
        if not team.has_permission(demoter_id, TeamRole.OWNER):
            raise TeamError("Only the owner can demote members")

        if not team.demote_member(target_id):
            raise TeamError("Cannot demote this member")

        self.db.save_team(team)

        # Update account
        account = self.db.get_account(target_id)
        if account:
            account.team_role = TeamRole.MEMBER
            self.db.save_account(account)

        return True

    def transfer_ownership(
        self, team: Team, current_owner_id: str, new_owner_id: str
    ) -> bool:
        """Transfer team ownership.

        Raises:
            TeamError: If requester is not owner
        """
        if team.owner_id != current_owner_id:
            raise TeamError("Only the owner can transfer ownership")

        if not team.transfer_ownership(new_owner_id):
            raise TeamError("Failed to transfer ownership")

        self.db.save_team(team)

        # Update accounts
        old_owner = self.db.get_account(current_owner_id)
        if old_owner:
            old_owner.team_role = TeamRole.OFFICER
            self.db.save_account(old_owner)

        new_owner = self.db.get_account(new_owner_id)
        if new_owner:
            new_owner.team_role = TeamRole.OWNER
            self.db.save_account(new_owner)

        return True

    def create_invite(
        self,
        team: Team,
        inviter_id: str,
        invitee_id: Optional[str] = None,
        max_uses: int = 1,
        expires_days: int = 7,
    ) -> TeamInvite:
        """Create a team invite.

        Args:
            team: The team
            inviter_id: Account creating the invite
            invitee_id: Specific account (or None for generic)
            max_uses: Max times invite can be used
            expires_days: Days until expiration

        Returns:
            Created invite

        Raises:
            TeamError: If inviter lacks permission
        """
        if not team.has_permission(inviter_id, TeamRole.OFFICER):
            raise TeamError("You must be an officer or owner to create invites")

        # Clean up expired invites
        team.cleanup_expired_invites()

        # Create invite
        invite = TeamInvite.create(
            team_id=team.id,
            inviter_id=inviter_id,
            invitee_id=invitee_id,
            max_uses=max_uses,
            expires_days=expires_days,
        )
        team.invites.append(invite)
        self.db.save_team(team)

        return invite

    def revoke_invite(self, team: Team, revoker_id: str, invite_code: str) -> bool:
        """Revoke a team invite.

        Raises:
            TeamError: If revoker lacks permission
        """
        if not team.has_permission(revoker_id, TeamRole.OFFICER):
            raise TeamError("You must be an officer or owner to revoke invites")

        invite = team.get_invite_by_code(invite_code)
        if not invite:
            raise TeamError("Invite not found")

        team.invites = [i for i in team.invites if i.code != invite_code.upper()]
        self.db.save_team(team)

        return True

    def use_invite_code(self, account: Account, code: str) -> Team:
        """Join a team using an invite code.

        Returns:
            The team joined

        Raises:
            TeamError: If code is invalid or join fails
        """
        team = self.db.find_team_by_invite_code(code)
        if not team:
            raise TeamError("Invalid invite code")

        # join_team will validate and use the invite
        self.join_team(account, team, invite_code=code)
        return team

    def set_join_policy(
        self,
        team: Team,
        setter_id: str,
        policy: JoinPolicy,
        password: Optional[str] = None,
    ) -> None:
        """Set team join policy.

        Raises:
            TeamError: If setter is not owner
        """
        if team.owner_id != setter_id:
            raise TeamError("Only the owner can change join policy")

        team.settings.join_policy = policy

        if policy == JoinPolicy.PASSWORD:
            if not password:
                raise TeamError("Password required for password-protected teams")
            team.settings.password_hash = self._hash_password(password)
        else:
            team.settings.password_hash = None

        self.db.save_team(team)

    def set_max_players(self, team: Team, setter_id: str, max_players: int) -> None:
        """Set team max players.

        Raises:
            TeamError: If setter is not owner or count too low
        """
        if team.owner_id != setter_id:
            raise TeamError("Only the owner can change team size")

        max_players = max(1, min(50, max_players))

        if max_players < team.member_count:
            raise TeamError(
                f"Cannot set max players below current member count ({team.member_count})"
            )

        team.settings.max_players = max_players
        self.db.save_team(team)

    def get_team_members(self, team: Team) -> list[Account]:
        """Get full Account objects for all team members."""
        accounts = []
        for member in team.members:
            account = self.db.get_account(member.player_id)
            if account:
                accounts.append(account)
        return accounts

    @staticmethod
    def _is_valid_team_name(name: str) -> bool:
        """Check if team name is valid."""
        return 3 <= len(name) <= 30

    @staticmethod
    def _hash_password(password: str) -> str:
        """Hash a password with bcrypt."""
        return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

    @staticmethod
    def _verify_password(password: str, password_hash: Optional[str]) -> bool:
        """Verify a password against a hash."""
        if not password_hash:
            return False
        try:
            return bcrypt.checkpw(password.encode(), password_hash.encode())
        except Exception:
            return False


def create_managers(db_path: Path) -> tuple[AccountManager, TeamManager]:
    """Create account and team managers with shared database.

    Args:
        db_path: Path to SQLite database file

    Returns:
        Tuple of (AccountManager, TeamManager)
    """
    db = AccountDatabase(db_path)
    return AccountManager(db), TeamManager(db)
