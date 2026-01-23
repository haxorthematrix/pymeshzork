"""Tests for the account and team system."""

import pytest
import tempfile
from pathlib import Path

from pymeshzork.accounts import (
    Account,
    Team,
    TeamRole,
    JoinPolicy,
    AccountManager,
    TeamManager,
    AccountError,
    TeamError,
    AccountDatabase,
    AccountCommands,
    TeamCommands,
    GameSession,
    create_managers,
)


@pytest.fixture
def db_path():
    """Create a temporary database file."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        yield Path(f.name)


@pytest.fixture
def managers(db_path):
    """Create account and team managers."""
    return create_managers(db_path)


@pytest.fixture
def account_manager(managers):
    """Get account manager."""
    return managers[0]


@pytest.fixture
def team_manager(managers):
    """Get team manager."""
    return managers[1]


class TestAccountModel:
    """Test Account model."""

    def test_create_account(self):
        """Test creating an account."""
        account = Account.create("testuser", "Test User")
        assert account.username == "testuser"
        assert account.display_name == "Test User"
        assert account.id  # Should have a UUID
        assert account.team_id is None

    def test_account_serialization(self):
        """Test account to_dict/from_dict."""
        account = Account.create("testuser", "Test User")
        account.total_score = 100
        account.achievements = ["first_blood"]

        data = account.to_dict()
        restored = Account.from_dict(data)

        assert restored.username == account.username
        assert restored.display_name == account.display_name
        assert restored.total_score == 100
        assert "first_blood" in restored.achievements


class TestTeamModel:
    """Test Team model."""

    def test_create_team(self):
        """Test creating a team."""
        owner = Account.create("owner", "Team Owner")
        team = Team.create("Test Team", owner, "TEST", max_players=10)

        assert team.name == "Test Team"
        assert team.tag == "TEST"
        assert team.owner_id == owner.id
        assert team.member_count == 1
        assert team.settings.max_players == 10

    def test_team_capacity(self):
        """Test team capacity."""
        owner = Account.create("owner", "Owner")
        team = Team.create("Small Team", owner, max_players=2)

        assert not team.is_full

        # Add another member
        member = Account.create("member", "Member")
        assert team.add_member(member)
        assert team.is_full

        # Can't add more
        another = Account.create("another", "Another")
        assert not team.add_member(another)

    def test_team_roles(self):
        """Test team role hierarchy."""
        owner = Account.create("owner", "Owner")
        team = Team.create("Test", owner)

        member = Account.create("member", "Member")
        team.add_member(member)

        # Owner has all permissions
        assert team.has_permission(owner.id, TeamRole.OWNER)
        assert team.has_permission(owner.id, TeamRole.OFFICER)
        assert team.has_permission(owner.id, TeamRole.MEMBER)

        # Member only has member permission
        assert team.has_permission(member.id, TeamRole.MEMBER)
        assert not team.has_permission(member.id, TeamRole.OFFICER)

        # Promote to officer
        team.promote_member(member.id)
        assert team.has_permission(member.id, TeamRole.OFFICER)

    def test_team_serialization(self):
        """Test team to_dict/from_dict."""
        owner = Account.create("owner", "Owner")
        team = Team.create("Test Team", owner, "TST")
        team.stats.total_score = 500

        data = team.to_dict()
        restored = Team.from_dict(data)

        assert restored.name == team.name
        assert restored.tag == team.tag
        assert restored.member_count == 1
        assert restored.stats.total_score == 500


class TestAccountManager:
    """Test AccountManager."""

    def test_create_account(self, account_manager):
        """Test creating accounts."""
        account = account_manager.create_account("alice", "Alice")
        assert account.username == "alice"

        # Can retrieve
        retrieved = account_manager.get_account_by_username("alice")
        assert retrieved.id == account.id

    def test_username_validation(self, account_manager):
        """Test username validation."""
        # Too short
        with pytest.raises(AccountError):
            account_manager.create_account("ab")

        # Too long
        with pytest.raises(AccountError):
            account_manager.create_account("a" * 21)

        # Invalid characters
        with pytest.raises(AccountError):
            account_manager.create_account("user@name")

    def test_duplicate_username(self, account_manager):
        """Test duplicate username prevention."""
        account_manager.create_account("alice")

        with pytest.raises(AccountError):
            account_manager.create_account("Alice")  # Case-insensitive

    def test_delete_account(self, account_manager):
        """Test account deletion."""
        account = account_manager.create_account("deleteme")
        assert account_manager.delete_account(account.id)
        assert account_manager.get_account(account.id) is None


class TestTeamManager:
    """Test TeamManager."""

    def test_create_team(self, account_manager, team_manager):
        """Test creating a team."""
        owner = account_manager.create_account("owner")
        team = team_manager.create_team("Test Team", owner, "TST")

        assert team.name == "Test Team"
        assert owner.team_id == team.id
        assert owner.team_role == TeamRole.OWNER

    def test_join_open_team(self, account_manager, team_manager):
        """Test joining an open team."""
        owner = account_manager.create_account("owner")
        team = team_manager.create_team("Open Team", owner)
        team_manager.set_join_policy(team, owner.id, JoinPolicy.OPEN)

        member = account_manager.create_account("member")
        team_manager.join_team(member, team)

        assert member.team_id == team.id
        assert team.member_count == 2

    def test_join_password_team(self, account_manager, team_manager):
        """Test joining a password-protected team."""
        owner = account_manager.create_account("owner")
        team = team_manager.create_team("Secure Team", owner)
        team_manager.set_join_policy(team, owner.id, JoinPolicy.PASSWORD, "secret123")

        member = account_manager.create_account("member")

        # Wrong password
        with pytest.raises(TeamError):
            team_manager.join_team(member, team, password="wrong")

        # Correct password
        team_manager.join_team(member, team, password="secret123")
        assert member.team_id == team.id

    def test_join_invite_only_team(self, account_manager, team_manager):
        """Test joining an invite-only team."""
        owner = account_manager.create_account("owner")
        team = team_manager.create_team("Private Team", owner)
        # Default policy is invite-only

        member = account_manager.create_account("member")

        # Can't join without invite
        with pytest.raises(TeamError):
            team_manager.join_team(member, team)

        # Create invite and join
        invite = team_manager.create_invite(team, owner.id, max_uses=5)
        team_manager.join_team(member, team, invite_code=invite.code)
        assert member.team_id == team.id

    def test_leave_team(self, account_manager, team_manager):
        """Test leaving a team."""
        owner = account_manager.create_account("owner")
        team = team_manager.create_team("Test", owner)
        team_manager.set_join_policy(team, owner.id, JoinPolicy.OPEN)

        member = account_manager.create_account("member")
        team_manager.join_team(member, team)

        team_manager.leave_team(member)
        assert member.team_id is None

        # Owner can't leave
        with pytest.raises(TeamError):
            team_manager.leave_team(owner)

    def test_kick_member(self, account_manager, team_manager):
        """Test kicking a member."""
        owner = account_manager.create_account("owner")
        team = team_manager.create_team("Test", owner)
        team_manager.set_join_policy(team, owner.id, JoinPolicy.OPEN)

        member = account_manager.create_account("member")
        team_manager.join_team(member, team)

        team_manager.kick_member(team, owner.id, member.id)
        # Refresh member from database to see updated state
        member = account_manager.get_account(member.id)
        assert member.team_id is None

    def test_transfer_ownership(self, account_manager, team_manager):
        """Test ownership transfer."""
        owner = account_manager.create_account("owner")
        team = team_manager.create_team("Test", owner)
        team_manager.set_join_policy(team, owner.id, JoinPolicy.OPEN)

        new_owner = account_manager.create_account("new_owner")
        team_manager.join_team(new_owner, team)

        team_manager.transfer_ownership(team, owner.id, new_owner.id)

        # Refresh accounts
        owner = account_manager.get_account(owner.id)
        new_owner = account_manager.get_account(new_owner.id)

        assert new_owner.team_role == TeamRole.OWNER
        assert owner.team_role == TeamRole.OFFICER


class TestAccountCommands:
    """Test ACCOUNT commands."""

    def test_create_and_login(self, managers):
        """Test account create and login commands."""
        account_mgr, team_mgr = managers
        cmds = AccountCommands(account_mgr, team_mgr)
        session = GameSession()

        # Create account
        result = cmds.execute(session, "create", ["alice", "Alice", "Smith"])
        assert result.success
        assert session.account is not None
        assert session.account.username == "alice"

        # Logout
        result = cmds.execute(session, "logout", [])
        assert result.success
        assert session.account is None

        # Login
        result = cmds.execute(session, "login", ["alice"])
        assert result.success
        assert session.account.username == "alice"

    def test_account_info(self, managers):
        """Test account info command."""
        account_mgr, team_mgr = managers
        cmds = AccountCommands(account_mgr, team_mgr)
        session = GameSession()

        cmds.execute(session, "create", ["bob"])
        result = cmds.execute(session, "info", [])
        assert result.success
        assert "bob" in result.message


class TestTeamCommands:
    """Test TEAM commands."""

    def test_create_team(self, managers):
        """Test team create command."""
        account_mgr, team_mgr = managers
        account_cmds = AccountCommands(account_mgr, team_mgr)
        team_cmds = TeamCommands(account_mgr, team_mgr)
        session = GameSession()

        # Must be logged in
        result = team_cmds.execute(session, "create", ["MyTeam"])
        assert not result.success

        # Login and create
        account_cmds.execute(session, "create", ["owner"])
        result = team_cmds.execute(session, "create", ["MyTeam", "MT"])
        assert result.success
        assert session.team is not None
        assert session.team.name == "MyTeam"
        assert session.team.tag == "MT"

    def test_team_invite_flow(self, managers):
        """Test team invite workflow."""
        account_mgr, team_mgr = managers
        account_cmds = AccountCommands(account_mgr, team_mgr)
        team_cmds = TeamCommands(account_mgr, team_mgr)

        # Create owner and team
        owner_session = GameSession()
        account_cmds.execute(owner_session, "create", ["owner"])
        team_cmds.execute(owner_session, "create", ["Private"])

        # Create invite
        result = team_cmds.execute(owner_session, "invite", ["5", "7"])
        assert result.success
        invite_code = result.data["code"]

        # Create member and join with invite
        member_session = GameSession()
        account_cmds.execute(member_session, "create", ["member"])
        result = team_cmds.execute(member_session, "join", [invite_code])
        assert result.success
        assert member_session.team.name == "Private"

    def test_team_management(self, managers):
        """Test team management commands."""
        account_mgr, team_mgr = managers
        account_cmds = AccountCommands(account_mgr, team_mgr)
        team_cmds = TeamCommands(account_mgr, team_mgr)

        # Setup
        owner_session = GameSession()
        account_cmds.execute(owner_session, "create", ["owner"])
        team_cmds.execute(owner_session, "create", ["Test"])
        team_cmds.execute(owner_session, "settings", ["join_policy", "open"])

        member_session = GameSession()
        account_cmds.execute(member_session, "create", ["member"])
        team_cmds.execute(member_session, "join", ["Test"])

        # Refresh owner's team view to see the new member
        owner_session.team = team_mgr.get_team(owner_session.team.id)

        # Promote
        result = team_cmds.execute(owner_session, "promote", ["member"])
        assert result.success

        # List members
        result = team_cmds.execute(owner_session, "members", [])
        assert result.success
        assert "member" in result.message
        assert "Officer" in result.message

        # Demote
        result = team_cmds.execute(owner_session, "demote", ["member"])
        assert result.success

        # Kick
        result = team_cmds.execute(owner_session, "kick", ["member"])
        assert result.success
        assert account_mgr.get_account(member_session.account.id).team_id is None


class TestDatabasePersistence:
    """Test database persistence."""

    def test_account_persistence(self, db_path):
        """Test that accounts persist across manager instances."""
        # Create account
        mgr1, _ = create_managers(db_path)
        account = mgr1.create_account("persistent", "Persistent User")
        account_id = account.id

        # New manager should find it
        db = AccountDatabase(db_path)
        mgr2 = AccountManager(db)
        restored = mgr2.get_account(account_id)

        assert restored is not None
        assert restored.username == "persistent"

    def test_team_persistence(self, db_path):
        """Test that teams persist across manager instances."""
        # Create team
        account_mgr1, team_mgr1 = create_managers(db_path)
        owner = account_mgr1.create_account("owner")
        team = team_mgr1.create_team("Persistent Team", owner, "PT")
        team_id = team.id

        # New manager should find it
        db = AccountDatabase(db_path)
        team_mgr2 = TeamManager(db)
        restored = team_mgr2.get_team(team_id)

        assert restored is not None
        assert restored.name == "Persistent Team"
        assert restored.member_count == 1
