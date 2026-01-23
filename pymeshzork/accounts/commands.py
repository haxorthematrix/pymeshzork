"""In-game commands for account and team management."""

from typing import Optional, Callable
from dataclasses import dataclass, field

from pymeshzork.accounts.manager import (
    AccountManager,
    TeamManager,
    AccountError,
    TeamError,
)
from pymeshzork.accounts.models import Account, Team, TeamRole, JoinPolicy


@dataclass
class CommandResult:
    """Result of a command execution."""

    success: bool
    message: str
    data: Optional[dict] = None


@dataclass
class GameSession:
    """Represents an active game session."""

    account: Optional[Account] = None
    team: Optional[Team] = None


class AccountCommands:
    """Handles ACCOUNT subcommands."""

    def __init__(
        self,
        account_manager: AccountManager,
        team_manager: TeamManager,
    ) -> None:
        self.accounts = account_manager
        self.teams = team_manager
        self.subcommands: dict[str, Callable] = {
            "create": self.cmd_create,
            "login": self.cmd_login,
            "logout": self.cmd_logout,
            "delete": self.cmd_delete,
            "info": self.cmd_info,
            "list": self.cmd_list,
            "stats": self.cmd_stats,
        }

    def execute(
        self, session: GameSession, subcommand: str, args: list[str]
    ) -> CommandResult:
        """Execute an ACCOUNT subcommand."""
        subcommand = subcommand.lower()
        handler = self.subcommands.get(subcommand)

        if not handler:
            valid = ", ".join(sorted(self.subcommands.keys()))
            return CommandResult(
                False, f"Unknown ACCOUNT subcommand. Valid: {valid}"
            )

        return handler(session, args)

    def cmd_create(self, session: GameSession, args: list[str]) -> CommandResult:
        """Create a new account: ACCOUNT CREATE <username> [display_name]"""
        if session.account:
            return CommandResult(False, "You are already logged in. Use ACCOUNT LOGOUT first.")

        if not args:
            return CommandResult(False, "Usage: ACCOUNT CREATE <username> [display_name]")

        username = args[0]
        display_name = " ".join(args[1:]) if len(args) > 1 else ""

        try:
            account = self.accounts.create_account(username, display_name)
            session.account = account
            return CommandResult(
                True,
                f"Account '{account.username}' created and logged in.",
                {"account_id": account.id},
            )
        except AccountError as e:
            return CommandResult(False, str(e))

    def cmd_login(self, session: GameSession, args: list[str]) -> CommandResult:
        """Login to an account: ACCOUNT LOGIN <username>"""
        if session.account:
            return CommandResult(
                False, f"Already logged in as {session.account.username}. Use ACCOUNT LOGOUT first."
            )

        if not args:
            return CommandResult(False, "Usage: ACCOUNT LOGIN <username>")

        username = args[0]
        account = self.accounts.get_account_by_username(username)

        if not account:
            return CommandResult(False, f"Account '{username}' not found.")

        session.account = account
        self.accounts.update_last_played(account)

        # Load team if member of one
        if account.team_id:
            session.team = self.teams.get_team(account.team_id)

        team_msg = ""
        if session.team:
            team_msg = f" Team: {session.team.name}"

        return CommandResult(
            True,
            f"Welcome back, {account.display_name}!{team_msg}",
            {"account_id": account.id},
        )

    def cmd_logout(self, session: GameSession, args: list[str]) -> CommandResult:
        """Logout from current account: ACCOUNT LOGOUT"""
        if not session.account:
            return CommandResult(False, "You are not logged in.")

        username = session.account.username
        session.account = None
        session.team = None

        return CommandResult(True, f"Logged out from {username}.")

    def cmd_delete(self, session: GameSession, args: list[str]) -> CommandResult:
        """Delete current account: ACCOUNT DELETE CONFIRM"""
        if not session.account:
            return CommandResult(False, "You must be logged in to delete your account.")

        if not args or args[0].upper() != "CONFIRM":
            return CommandResult(
                False,
                "WARNING: This will permanently delete your account and all saves!\n"
                "Type ACCOUNT DELETE CONFIRM to proceed.",
            )

        try:
            account_id = session.account.id
            username = session.account.username
            self.accounts.delete_account(account_id)
            session.account = None
            session.team = None
            return CommandResult(True, f"Account '{username}' has been deleted.")
        except AccountError as e:
            return CommandResult(False, str(e))

    def cmd_info(self, session: GameSession, args: list[str]) -> CommandResult:
        """Show account info: ACCOUNT INFO [username]"""
        if args:
            # Lookup another account
            account = self.accounts.get_account_by_username(args[0])
            if not account:
                return CommandResult(False, f"Account '{args[0]}' not found.")
        else:
            # Show own account
            if not session.account:
                return CommandResult(False, "You must be logged in. Use ACCOUNT INFO <username> to view others.")
            account = session.account

        team_info = "None"
        if account.team_id:
            team = self.teams.get_team(account.team_id)
            if team:
                role = account.team_role.value if account.team_role else "member"
                team_info = f"{team.name} [{team.tag}] ({role})" if team.tag else f"{team.name} ({role})"

        lines = [
            f"=== Account: {account.username} ===",
            f"Display Name: {account.display_name}",
            f"Team: {team_info}",
            f"Created: {account.created.strftime('%Y-%m-%d')}",
            f"Last Played: {account.last_played.strftime('%Y-%m-%d %H:%M')}",
        ]

        return CommandResult(True, "\n".join(lines), {"account": account.to_dict()})

    def cmd_list(self, session: GameSession, args: list[str]) -> CommandResult:
        """List all accounts: ACCOUNT LIST"""
        accounts = self.accounts.list_accounts()

        if not accounts:
            return CommandResult(True, "No accounts found.")

        lines = ["=== Accounts ==="]
        for acc in accounts:
            team_tag = ""
            if acc.team_id:
                team = self.teams.get_team(acc.team_id)
                if team and team.tag:
                    team_tag = f" [{team.tag}]"
            lines.append(f"  {acc.username}{team_tag}")

        lines.append(f"\nTotal: {len(accounts)} accounts")
        return CommandResult(True, "\n".join(lines))

    def cmd_stats(self, session: GameSession, args: list[str]) -> CommandResult:
        """Show account statistics: ACCOUNT STATS [username]"""
        if args:
            account = self.accounts.get_account_by_username(args[0])
            if not account:
                return CommandResult(False, f"Account '{args[0]}' not found.")
        else:
            if not session.account:
                return CommandResult(False, "You must be logged in.")
            account = session.account

        lines = [
            f"=== Stats for {account.username} ===",
            f"Games Played: {account.games_played}",
            f"Total Score: {account.total_score}",
            f"Total Moves: {account.total_moves}",
            f"Total Deaths: {account.total_deaths}",
            f"Worlds Completed: {len(account.worlds_completed)}",
            f"Achievements: {len(account.achievements)}",
        ]

        if account.achievements:
            lines.append("\nAchievements:")
            for ach in account.achievements[:10]:  # Show first 10
                lines.append(f"  - {ach}")
            if len(account.achievements) > 10:
                lines.append(f"  ... and {len(account.achievements) - 10} more")

        return CommandResult(True, "\n".join(lines))


class TeamCommands:
    """Handles TEAM subcommands."""

    def __init__(
        self,
        account_manager: AccountManager,
        team_manager: TeamManager,
    ) -> None:
        self.accounts = account_manager
        self.teams = team_manager
        self.subcommands: dict[str, Callable] = {
            "create": self.cmd_create,
            "join": self.cmd_join,
            "leave": self.cmd_leave,
            "info": self.cmd_info,
            "list": self.cmd_list,
            "members": self.cmd_members,
            "invite": self.cmd_invite,
            "kick": self.cmd_kick,
            "promote": self.cmd_promote,
            "demote": self.cmd_demote,
            "transfer": self.cmd_transfer,
            "disband": self.cmd_disband,
            "settings": self.cmd_settings,
        }

    def execute(
        self, session: GameSession, subcommand: str, args: list[str]
    ) -> CommandResult:
        """Execute a TEAM subcommand."""
        subcommand = subcommand.lower()
        handler = self.subcommands.get(subcommand)

        if not handler:
            valid = ", ".join(sorted(self.subcommands.keys()))
            return CommandResult(
                False, f"Unknown TEAM subcommand. Valid: {valid}"
            )

        return handler(session, args)

    def _require_login(self, session: GameSession) -> Optional[CommandResult]:
        """Check if logged in, return error if not."""
        if not session.account:
            return CommandResult(False, "You must be logged in to use team commands.")
        return None

    def _require_team(self, session: GameSession) -> Optional[CommandResult]:
        """Check if in a team, return error if not."""
        error = self._require_login(session)
        if error:
            return error
        if not session.team:
            return CommandResult(False, "You are not in a team.")
        return None

    def cmd_create(self, session: GameSession, args: list[str]) -> CommandResult:
        """Create a team: TEAM CREATE <name> [tag]"""
        error = self._require_login(session)
        if error:
            return error

        if not args:
            return CommandResult(False, "Usage: TEAM CREATE <name> [tag]")

        name = args[0]
        tag = args[1] if len(args) > 1 else ""

        try:
            team = self.teams.create_team(name, session.account, tag)
            session.team = team
            tag_msg = f" [{team.tag}]" if team.tag else ""
            return CommandResult(
                True,
                f"Team '{team.name}'{tag_msg} created! You are the owner.",
                {"team_id": team.id},
            )
        except TeamError as e:
            return CommandResult(False, str(e))

    def cmd_join(self, session: GameSession, args: list[str]) -> CommandResult:
        """Join a team: TEAM JOIN <name|code> [password]"""
        error = self._require_login(session)
        if error:
            return error

        if not args:
            return CommandResult(False, "Usage: TEAM JOIN <team_name|invite_code> [password]")

        name_or_code = args[0]
        password = args[1] if len(args) > 1 else None

        try:
            # Try as invite code first (6 chars, alphanumeric)
            if len(name_or_code) == 6 and name_or_code.isalnum():
                team = self.teams.use_invite_code(session.account, name_or_code)
            else:
                # Try as team name
                team = self.teams.get_team_by_name(name_or_code)
                if not team:
                    return CommandResult(False, f"Team '{name_or_code}' not found.")
                self.teams.join_team(session.account, team, password=password)

            session.team = team
            return CommandResult(
                True,
                f"You have joined {team.name}!",
                {"team_id": team.id},
            )
        except TeamError as e:
            return CommandResult(False, str(e))

    def cmd_leave(self, session: GameSession, args: list[str]) -> CommandResult:
        """Leave current team: TEAM LEAVE"""
        error = self._require_team(session)
        if error:
            return error

        team_name = session.team.name

        try:
            self.teams.leave_team(session.account)
            session.team = None
            return CommandResult(True, f"You have left {team_name}.")
        except TeamError as e:
            return CommandResult(False, str(e))

    def cmd_info(self, session: GameSession, args: list[str]) -> CommandResult:
        """Show team info: TEAM INFO [name]"""
        if args:
            team = self.teams.get_team_by_name(args[0])
            if not team:
                return CommandResult(False, f"Team '{args[0]}' not found.")
        else:
            error = self._require_team(session)
            if error:
                return error
            team = session.team

        policy_names = {
            JoinPolicy.OPEN: "Open",
            JoinPolicy.PASSWORD: "Password Required",
            JoinPolicy.INVITE_ONLY: "Invite Only",
            JoinPolicy.CLOSED: "Closed",
        }

        lines = [
            f"=== Team: {team.name} ===",
        ]
        if team.tag:
            lines.append(f"Tag: [{team.tag}]")
        lines.extend([
            f"Members: {team.member_count}/{team.settings.max_players}",
            f"Join Policy: {policy_names.get(team.settings.join_policy, 'Unknown')}",
            f"Created: {team.created.strftime('%Y-%m-%d')}",
            "",
            "Stats:",
            f"  Total Score: {team.stats.total_score}",
            f"  Treasures Found: {team.stats.total_treasures}",
            f"  Worlds Completed: {len(team.stats.worlds_completed)}",
        ])

        return CommandResult(True, "\n".join(lines), {"team": team.to_dict()})

    def cmd_list(self, session: GameSession, args: list[str]) -> CommandResult:
        """List all teams: TEAM LIST"""
        teams = self.teams.list_teams()

        if not teams:
            return CommandResult(True, "No teams found. Create one with TEAM CREATE!")

        lines = ["=== Teams ==="]
        for team in teams:
            tag = f"[{team.tag}] " if team.tag else ""
            policy = ""
            if team.settings.join_policy == JoinPolicy.OPEN:
                policy = " (Open)"
            elif team.settings.join_policy == JoinPolicy.CLOSED:
                policy = " (Closed)"
            lines.append(
                f"  {tag}{team.name} - {team.member_count}/{team.settings.max_players}{policy}"
            )

        lines.append(f"\nTotal: {len(teams)} teams")
        return CommandResult(True, "\n".join(lines))

    def cmd_members(self, session: GameSession, args: list[str]) -> CommandResult:
        """List team members: TEAM MEMBERS [name]"""
        if args:
            team = self.teams.get_team_by_name(args[0])
            if not team:
                return CommandResult(False, f"Team '{args[0]}' not found.")
        else:
            error = self._require_team(session)
            if error:
                return error
            team = session.team

        lines = [f"=== Members of {team.name} ==="]

        role_order = {TeamRole.OWNER: 0, TeamRole.OFFICER: 1, TeamRole.MEMBER: 2}
        sorted_members = sorted(team.members, key=lambda m: role_order.get(m.role, 3))

        for member in sorted_members:
            role_badge = ""
            if member.role == TeamRole.OWNER:
                role_badge = " [Owner]"
            elif member.role == TeamRole.OFFICER:
                role_badge = " [Officer]"
            lines.append(f"  {member.username}{role_badge}")

        lines.append(f"\nTotal: {len(team.members)} members")
        return CommandResult(True, "\n".join(lines))

    def cmd_invite(self, session: GameSession, args: list[str]) -> CommandResult:
        """Create an invite: TEAM INVITE [uses] [days]"""
        error = self._require_team(session)
        if error:
            return error

        max_uses = 1
        expires_days = 7

        if args:
            try:
                max_uses = int(args[0])
            except ValueError:
                pass
        if len(args) > 1:
            try:
                expires_days = int(args[1])
            except ValueError:
                pass

        try:
            invite = self.teams.create_invite(
                session.team,
                session.account.id,
                max_uses=max_uses,
                expires_days=expires_days,
            )
            return CommandResult(
                True,
                f"Invite code: {invite.code}\n"
                f"Uses: {max_uses}, Expires in {expires_days} days\n"
                f"Share this code with: TEAM JOIN {invite.code}",
                {"code": invite.code},
            )
        except TeamError as e:
            return CommandResult(False, str(e))

    def cmd_kick(self, session: GameSession, args: list[str]) -> CommandResult:
        """Kick a member: TEAM KICK <username>"""
        error = self._require_team(session)
        if error:
            return error

        if not args:
            return CommandResult(False, "Usage: TEAM KICK <username>")

        target = session.team.get_member_by_username(args[0])
        if not target:
            return CommandResult(False, f"Member '{args[0]}' not found in team.")

        try:
            self.teams.kick_member(session.team, session.account.id, target.player_id)
            return CommandResult(True, f"{target.username} has been kicked from the team.")
        except TeamError as e:
            return CommandResult(False, str(e))

    def cmd_promote(self, session: GameSession, args: list[str]) -> CommandResult:
        """Promote a member to officer: TEAM PROMOTE <username>"""
        error = self._require_team(session)
        if error:
            return error

        if not args:
            return CommandResult(False, "Usage: TEAM PROMOTE <username>")

        target = session.team.get_member_by_username(args[0])
        if not target:
            return CommandResult(False, f"Member '{args[0]}' not found in team.")

        try:
            self.teams.promote_member(session.team, session.account.id, target.player_id)
            return CommandResult(True, f"{target.username} has been promoted to Officer.")
        except TeamError as e:
            return CommandResult(False, str(e))

    def cmd_demote(self, session: GameSession, args: list[str]) -> CommandResult:
        """Demote an officer to member: TEAM DEMOTE <username>"""
        error = self._require_team(session)
        if error:
            return error

        if not args:
            return CommandResult(False, "Usage: TEAM DEMOTE <username>")

        target = session.team.get_member_by_username(args[0])
        if not target:
            return CommandResult(False, f"Member '{args[0]}' not found in team.")

        try:
            self.teams.demote_member(session.team, session.account.id, target.player_id)
            return CommandResult(True, f"{target.username} has been demoted to Member.")
        except TeamError as e:
            return CommandResult(False, str(e))

    def cmd_transfer(self, session: GameSession, args: list[str]) -> CommandResult:
        """Transfer ownership: TEAM TRANSFER <username> CONFIRM"""
        error = self._require_team(session)
        if error:
            return error

        if len(args) < 2 or args[1].upper() != "CONFIRM":
            return CommandResult(
                False,
                "Usage: TEAM TRANSFER <username> CONFIRM\n"
                "WARNING: This will transfer team ownership permanently!",
            )

        target = session.team.get_member_by_username(args[0])
        if not target:
            return CommandResult(False, f"Member '{args[0]}' not found in team.")

        try:
            self.teams.transfer_ownership(
                session.team, session.account.id, target.player_id
            )
            # Refresh session account
            session.account = self.accounts.get_account(session.account.id)
            return CommandResult(
                True, f"Ownership transferred to {target.username}. You are now an Officer."
            )
        except TeamError as e:
            return CommandResult(False, str(e))

    def cmd_disband(self, session: GameSession, args: list[str]) -> CommandResult:
        """Disband the team: TEAM DISBAND CONFIRM"""
        error = self._require_team(session)
        if error:
            return error

        if not args or args[0].upper() != "CONFIRM":
            return CommandResult(
                False,
                "WARNING: This will permanently disband the team!\n"
                "Type TEAM DISBAND CONFIRM to proceed.",
            )

        team_name = session.team.name

        try:
            self.teams.delete_team(session.team.id, session.account.id)
            session.team = None
            session.account.team_id = None
            session.account.team_role = TeamRole.MEMBER
            return CommandResult(True, f"Team '{team_name}' has been disbanded.")
        except TeamError as e:
            return CommandResult(False, str(e))

    def cmd_settings(self, session: GameSession, args: list[str]) -> CommandResult:
        """Modify team settings: TEAM SETTINGS <setting> <value>"""
        error = self._require_team(session)
        if error:
            return error

        if not args:
            # Show current settings
            team = session.team
            policy_names = {
                JoinPolicy.OPEN: "open",
                JoinPolicy.PASSWORD: "password",
                JoinPolicy.INVITE_ONLY: "invite",
                JoinPolicy.CLOSED: "closed",
            }
            lines = [
                "=== Team Settings ===",
                f"max_players: {team.settings.max_players}",
                f"join_policy: {policy_names.get(team.settings.join_policy, 'unknown')}",
                f"friendly_fire: {team.settings.allow_friendly_fire}",
                f"shared_discoveries: {team.settings.shared_discoveries}",
                "",
                "To change: TEAM SETTINGS <setting> <value>",
                "  TEAM SETTINGS max_players 20",
                "  TEAM SETTINGS join_policy open|password|invite|closed",
                "  TEAM SETTINGS password <password>  (sets policy to password)",
            ]
            return CommandResult(True, "\n".join(lines))

        setting = args[0].lower()
        value = args[1] if len(args) > 1 else None

        try:
            if setting == "max_players":
                if not value:
                    return CommandResult(False, "Usage: TEAM SETTINGS max_players <1-50>")
                self.teams.set_max_players(
                    session.team, session.account.id, int(value)
                )
                return CommandResult(True, f"Max players set to {value}.")

            elif setting == "join_policy":
                if not value:
                    return CommandResult(
                        False, "Usage: TEAM SETTINGS join_policy <open|password|invite|closed>"
                    )
                policy_map = {
                    "open": JoinPolicy.OPEN,
                    "password": JoinPolicy.PASSWORD,
                    "invite": JoinPolicy.INVITE_ONLY,
                    "closed": JoinPolicy.CLOSED,
                }
                policy = policy_map.get(value.lower())
                if not policy:
                    return CommandResult(False, "Valid policies: open, password, invite, closed")
                if policy == JoinPolicy.PASSWORD:
                    return CommandResult(
                        False, "Use TEAM SETTINGS password <password> to set password policy"
                    )
                self.teams.set_join_policy(session.team, session.account.id, policy)
                return CommandResult(True, f"Join policy set to {value}.")

            elif setting == "password":
                if not value:
                    return CommandResult(False, "Usage: TEAM SETTINGS password <password>")
                self.teams.set_join_policy(
                    session.team, session.account.id, JoinPolicy.PASSWORD, value
                )
                return CommandResult(True, "Password set. Join policy is now 'password'.")

            else:
                return CommandResult(False, f"Unknown setting: {setting}")

        except (TeamError, ValueError) as e:
            return CommandResult(False, str(e))


class SocialCommands:
    """Handles WHO and SAY commands for multiplayer."""

    def __init__(
        self,
        account_manager: AccountManager,
        team_manager: TeamManager,
    ) -> None:
        self.accounts = account_manager
        self.teams = team_manager
        # In a real multiplayer setup, this would track active sessions
        self.active_sessions: dict[str, GameSession] = {}

    def register_session(self, session: GameSession) -> None:
        """Register an active session."""
        if session.account:
            self.active_sessions[session.account.id] = session

    def unregister_session(self, account_id: str) -> None:
        """Unregister a session."""
        self.active_sessions.pop(account_id, None)

    def cmd_who(self, session: GameSession, args: list[str]) -> CommandResult:
        """Show online players: WHO [team]"""
        show_team_only = args and args[0].lower() == "team"

        if show_team_only and not session.team:
            return CommandResult(False, "You are not in a team.")

        online = []
        for acc_id, sess in self.active_sessions.items():
            if sess.account:
                if show_team_only:
                    if sess.team and session.team and sess.team.id == session.team.id:
                        online.append(sess.account)
                else:
                    online.append(sess.account)

        if not online:
            msg = "No players online."
            if show_team_only:
                msg = "No team members online."
            return CommandResult(True, msg)

        lines = ["=== Online Players ==="]
        for acc in online:
            team_tag = ""
            if acc.team_id:
                team = self.teams.get_team(acc.team_id)
                if team and team.tag:
                    team_tag = f" [{team.tag}]"
            lines.append(f"  {acc.display_name}{team_tag}")

        lines.append(f"\nTotal: {len(online)} online")
        return CommandResult(True, "\n".join(lines))

    def cmd_say(
        self, session: GameSession, message: str, team_only: bool = False
    ) -> CommandResult:
        """Send a message: SAY <message> or TEAM SAY <message>"""
        if not session.account:
            return CommandResult(False, "You must be logged in to chat.")

        if not message:
            return CommandResult(False, "Usage: SAY <message>")

        if team_only:
            if not session.team:
                return CommandResult(False, "You are not in a team.")
            # In real implementation, this would broadcast to team members
            tag = f"[{session.team.tag}] " if session.team.tag else "[Team] "
            return CommandResult(
                True,
                f"{tag}{session.account.display_name}: {message}",
                {"type": "team_chat", "sender": session.account.id, "message": message},
            )
        else:
            # Global chat
            return CommandResult(
                True,
                f"{session.account.display_name}: {message}",
                {"type": "global_chat", "sender": session.account.id, "message": message},
            )
