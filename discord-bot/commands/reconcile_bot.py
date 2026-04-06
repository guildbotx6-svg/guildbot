"""Free Fire guild reconciliation commands cog"""

import os
import sys
import sqlite3, json, io
import discord
from discord import app_commands
from discord.ext import commands
import discord.ui
from datetime import datetime, timezone, timedelta

# Ensure root folder is importable so helpers can be located from cogs
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from helpers import log_action, is_globally_banned

DB_PATH = "guild.db"
IST = timezone(timedelta(hours=5, minutes=30))

class GuildHistoryView(discord.ui.View):
    def __init__(self, rows, per_page=3):
        super().__init__(timeout=300)
        self.rows = rows
        self.page = 0
        self.per_page = per_page
        self.total_pages = (len(rows) + per_page - 1) // per_page
        self.update_buttons()

    def update_buttons(self):
        self.clear_items()
        if self.page > 0:
            prev_button = discord.ui.Button(label="Previous", style=discord.ButtonStyle.primary)
            prev_button.callback = self.prev_page
            self.add_item(prev_button)
        if self.page < self.total_pages - 1:
            next_button = discord.ui.Button(label="Next", style=discord.ButtonStyle.primary)
            next_button.callback = self.next_page
            self.add_item(next_button)

    async def prev_page(self, interaction: discord.Interaction):
        self.page -= 1
        self.update_buttons()
        await self.update_message(interaction)

    async def next_page(self, interaction: discord.Interaction):
        self.page += 1
        self.update_buttons()
        await self.update_message(interaction)

    def get_page_csv(self):
        lines = ["Timestamp,Action,Name,UID"]
        start = self.page * self.per_page
        end = start + self.per_page
        page_rows = self.rows[start:end]

        for timestamp, joined_json, left_json in page_rows:
            joined = json.loads(joined_json) if joined_json else []
            left = json.loads(left_json) if left_json else []

            for name, uid in joined:
                lines.append(f"{timestamp},Joined,{name},{uid}")
            for name, uid in left:
                lines.append(f"{timestamp},Left,{name},{uid}")

        return "\n".join(lines)

    async def update_message(self, interaction: discord.Interaction):
        csv_data = self.get_page_csv()
        prefix = f"Guild Change History (Page {self.page + 1}/{self.total_pages})\n"
        content = f"{prefix}```csv\n{csv_data}\n```"

        if len(content) > 1900:
            file = discord.File(io.BytesIO(csv_data.encode("utf-8")), filename=f"guild_history_page_{self.page + 1}.csv")
            await interaction.response.send_message("Guild history page too big; file attached.", file=file, view=self)
        else:
            await interaction.response.edit_message(content=content, view=self)

class GuildUpdateModal(discord.ui.Modal, title="Update Guild Members"):
    def __init__(self, cog):
        super().__init__()
        self.cog = cog

    guild_data = discord.ui.TextInput(
        label="Guild Member Data",
        placeholder="Paste lines like Name,UID (e.g. Player1,123456789)",
        style=discord.TextStyle.paragraph,
        required=True,
        max_length=4000
    )

    async def on_submit(self, interaction: discord.Interaction):
        text = self.guild_data.value
        current_members, invalid = self.cog.parse_member_lines(text)

        # Check for globally banned players
        banned_players = []
        for uid in current_members.keys():
            if is_globally_banned(uid):
                player_name = current_members[uid]
                banned_players.append(f"{player_name} ({uid})")

        self.cog.cursor.execute("SELECT members FROM guild_state WHERE channel_id=?", (interaction.channel_id,))
        row = self.cog.cursor.fetchone()

        joined, left = [], []
        name_changes = []
        if row:
            old_members = {int(uid): name for uid, name in json.loads(row[0]).items()}
            joined = [(name, uid) for uid, name in current_members.items() if uid not in old_members]
            left = [(name, uid) for uid, name in old_members.items() if uid not in current_members]
            # Check for name changes
            for uid in set(current_members.keys()) & set(old_members.keys()):
                if current_members[uid] != old_members[uid]:
                    name_changes.append((old_members[uid], current_members[uid], uid))

        # Save/update current state
        self.cog.cursor.execute(
            "REPLACE INTO guild_state (channel_id, members) VALUES (?, ?)",
            (interaction.channel_id, json.dumps(current_members))
        )

        # Log to history if there are changes
        if joined or left:
            self.cog.cursor.execute(
                "INSERT INTO guild_history (channel_id, timestamp, joined, left) VALUES (?, ?, ?, ?)",
                (interaction.channel_id, datetime.now(IST).isoformat(), json.dumps(joined), json.dumps(left))
            )

        self.cog.conn.commit()

        # Build message content
        msg = "**Guild Updates**\n"
        msg += f"📋 Current Members: {len(current_members)}\n\n"

        # Prepare CSV content
        joined_csv = "Name,UID\n" + "\n".join([f"{name},{uid}" for name, uid in joined]) if joined else ""
        left_csv = "Name,UID\n" + "\n".join([f"{name},{uid}" for name, uid in left]) if left else ""
        name_change_list = "\n".join([f"{old_name} -> {new_name} ({uid})" for old_name, new_name, uid in name_changes]) if name_changes else ""

        # Estimate total message length
        estimated_length = len(msg) + len(joined_csv) + len(left_csv) + len(name_change_list) + 200  # padding for formatting

        if estimated_length > 1800 or len(joined) > 20 or len(left) > 20:  # Use file if too long or too many changes
            # Create summary message and attach CSV file
            summary_msg = "**Guild Updates**\n"
            summary_msg += f"📋 Current Members: {len(current_members)}\n"
            summary_msg += f"✅ Joined: {len(joined)}\n"
            summary_msg += f"❌ Left: {len(left)}\n"
            summary_msg += f"🔄 Name Changes: {len(name_changes)}\n"

            if invalid:
                summary_msg += f"⚠️ Skipped invalid UIDs: {len(invalid)}\n"

            if banned_players:
                summary_msg += f"🚫 **Globally Banned Players Detected:** {len(banned_players)}\n"
                summary_msg += "\n".join([f"• {player}" for player in banned_players[:5]])  # Show first 5
                if len(banned_players) > 5:
                    summary_msg += f"\n... and {len(banned_players) - 5} more"
                summary_msg += "\n\n"

            # Create CSV file with all changes
            import io
            import csv
            buf = io.StringIO()
            writer = csv.writer(buf)

            writer.writerow(["Action", "Name", "UID"])
            for name, uid in joined:
                writer.writerow(["Joined", name, uid])
            for name, uid in left:
                writer.writerow(["Left", name, uid])
            for old_name, new_name, uid in name_changes:
                writer.writerow(["Name Change", f"{old_name} -> {new_name}", str(uid)])

            file = discord.File(io.BytesIO(buf.getvalue().encode("utf-8")), filename="guild_changes.csv")
            await interaction.response.send_message(summary_msg, file=file)
        else:
            # Use normal message format
            if joined:
                msg += f"✅ **Joined:**\n```csv\n{joined_csv}\n```\n"

            if left:
                msg += f"❌ **Left:**\n```csv\n{left_csv}\n```\n"

            if name_changes:
                msg += f"🔄 **Name Changes:**\n{name_change_list}\n\n"

            if not joined and not left and not name_changes:
                msg += "No changes since last update."

            if banned_players:
                msg += f"\n🚫 **Globally Banned Players Detected:**\n"
                msg += "\n".join([f"• {player}" for player in banned_players[:10]])  # Show first 10
                if len(banned_players) > 10:
                    msg += f"\n... and {len(banned_players) - 10} more"
                msg += "\n\n"

            if invalid:
                msg += f"⚠️ Skipped invalid UIDs: {', '.join([f'{name} ({uid})' for name, uid in invalid])}"

            await interaction.response.send_message(msg)

        await log_action(interaction, "Guild Updates", f"Updated guild: {len(joined)} joined, {len(left)} left, {len(name_changes)} name changes.")

    async def on_error(self, interaction: discord.Interaction, error: Exception):
        await interaction.response.send_message("An error occurred while processing your guild data.", ephemeral=True)
        print(f"Modal error: {error}")


class ReconcileCog(commands.Cog):
    """Commands for tracking Free Fire guild member changes"""

    def __init__(self, bot):
        self.bot = bot
        self.conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        self.cursor = self.conn.cursor()
        self._create_tables()

    def _create_tables(self):
        self.cursor.execute("""
        CREATE TABLE IF NOT EXISTS guild_state (
            channel_id INTEGER PRIMARY KEY,
            members TEXT
        )
        """)
        self.cursor.execute("""
        CREATE TABLE IF NOT EXISTS guild_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            channel_id INTEGER,
            timestamp TEXT,
            joined TEXT,
            left TEXT
        )
        """)
        self.conn.commit()

    @staticmethod
    def parse_member_lines(text: str):
        members = {}
        invalid_lines = []
        for line in text.splitlines():
            parts = line.strip().split(",")
            if len(parts) == 2:
                name, uid = parts
                try:
                    members[int(uid.strip())] = name.strip()
                except ValueError:
                    invalid_lines.append((name.strip(), uid.strip()))
        return members, invalid_lines

    @staticmethod
    def has_head_commander(interaction: discord.Interaction) -> bool:
        """Check if user has Head Commander role"""
        if not isinstance(interaction.user, discord.Member):
            return False
        return any(role.name == "head commander" for role in interaction.user.roles)

    @app_commands.command(name="currentmembers", description="Show current guild members")
    async def currentmembers(self, interaction: discord.Interaction):
        self.cursor.execute("SELECT members FROM guild_state WHERE channel_id=?", (interaction.channel_id,))
        row = self.cursor.fetchone()

        if not row or not row[0]:
            await interaction.response.send_message("No guild data stored yet. Use `/guildupdates` first.")
            return

        members = json.loads(row[0])
        if not members:
            await interaction.response.send_message("No members stored.")
            return

        members_csv = "Name,UID\n" + "\n".join([f"{name},{uid}" for uid, name in members.items()])
        msg = f"**Current Guild Members ({len(members)})**\n```csv\n{members_csv}\n```"

        await interaction.response.send_message(msg)
        await log_action(interaction, "Current Members Viewed", f"Displayed {len(members)} guild members.")

    @app_commands.command(name="guildupdates", description="Show Free Fire guild changes (modal)")
    async def guildupdates(self, interaction: discord.Interaction):
        modal = GuildUpdateModal(self)
        await interaction.response.send_modal(modal)

    @app_commands.command(name="clearguild", description="Clear guild data for this channel")
    async def clearguild(self, interaction: discord.Interaction):
        if not self.has_head_commander(interaction):
            await interaction.response.send_message("You need the Head Commander role to use this command.", ephemeral=True)
            return
        self.cursor.execute("DELETE FROM guild_state WHERE channel_id=?", (interaction.channel_id,))
        self.conn.commit()
        await interaction.response.send_message("Guild data cleared for this channel.")
        await log_action(interaction, "Clear Guild", "Cleared all guild data.")

    @app_commands.command(name="editguild", description="Edit guild members (format: Name,UID per line - updates existing or adds new)")
    async def editguild(self, interaction: discord.Interaction, text: str):
        if not self.has_head_commander(interaction):
            await interaction.response.send_message("You need the Head Commander role to use this command.", ephemeral=True)
            return
        members_to_edit, invalid = self.parse_member_lines(text)
        if not members_to_edit:
            await interaction.response.send_message("No valid members to edit. Use: Name,UID per line.")
            return

        self.cursor.execute("SELECT members FROM guild_state WHERE channel_id=?", (interaction.channel_id,))
        row = self.cursor.fetchone()
        current_members = {int(uid): name for uid, name in json.loads(row[0]).items()} if row and row[0] else {}

        current_members.update(members_to_edit)
        self.cursor.execute("REPLACE INTO guild_state (channel_id, members) VALUES (?, ?)", (interaction.channel_id, json.dumps(current_members)))
        self.conn.commit()

        response = f"Guild updated with {len(members_to_edit)} member(s)."
        if invalid:
            response += f"\nSkipped invalid UIDs: {', '.join([f'{name} ({uid})' for name, uid in invalid])}"
        await interaction.response.send_message(response)
        await log_action(interaction, "Edit Guild", f"Edited guild: {len(members_to_edit)} members updated.")

    @app_commands.command(name="guildhistory", description="Show guild change history")
    async def guildhistory(self, interaction: discord.Interaction):
        self.cursor.execute("SELECT timestamp, joined, left FROM guild_history WHERE channel_id=? ORDER BY id DESC", (interaction.channel_id,))
        rows = self.cursor.fetchall()

        if not rows:
            await interaction.response.send_message("No guild change history found.")
            return

        view = GuildHistoryView(rows)
        csv_data = view.get_page_csv()
        prefix = f"Guild Change History (Page 1/{view.total_pages})\n"
        content = f"{prefix}```csv\n{csv_data}\n```"

        if len(content) > 1900:
            file = discord.File(io.BytesIO(csv_data.encode("utf-8")), filename="guild_history_page_1.csv")
            await interaction.response.send_message("Guild history page too big to display; file attached.", file=file, view=view)
        else:
            await interaction.response.send_message(content, view=view)

        await log_action(interaction, "Guild History", f"Viewed guild history: {len(rows)} entries.")

    @app_commands.command(name="resethistory", description="Clear guild change history for this channel")
    async def resethistory(self, interaction: discord.Interaction):
        if not self.has_head_commander(interaction):
            await interaction.response.send_message("You need the Head Commander role to use this command.", ephemeral=True)
            return
        self.cursor.execute("DELETE FROM guild_history WHERE channel_id=?", (interaction.channel_id,))
        self.conn.commit()
        await interaction.response.send_message("Guild history cleared for this channel.")
        await log_action(interaction, "Reset History", "Cleared guild change history.")

    @app_commands.command(name="addheadcommander", description="Add Head Commander role to a user")
    async def addheadcommander(self, interaction: discord.Interaction, user: discord.User):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("You need Administrator permissions to use this command.", ephemeral=True)
            return

        member = await interaction.guild.fetch_member(user.id)
        head_commander_role = discord.utils.get(interaction.guild.roles, name="head commander")

        if not head_commander_role:
            try:
                head_commander_role = await interaction.guild.create_role(name="head commander", color=discord.Color.red())
            except Exception as e:
                await interaction.response.send_message(f"Error creating role: {e}", ephemeral=True)
                return

        if head_commander_role in member.roles:
            await interaction.response.send_message(f"{user.mention} already has the Head Commander role.", ephemeral=True)
            return

        await member.add_roles(head_commander_role)
        await interaction.response.send_message(f"Added Head Commander role to {user.mention}.")
        await log_action(interaction, "Add Head Commander", f"Added Head Commander role to {user.mention}.")

    @app_commands.command(name="removeheadcommander", description="Remove Head Commander role from a user")
    async def removeheadcommander(self, interaction: discord.Interaction, user: discord.User):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("You need Administrator permissions to use this command.", ephemeral=True)
            return

        member = await interaction.guild.fetch_member(user.id)
        head_commander_role = discord.utils.get(interaction.guild.roles, name="head commander")

        if not head_commander_role or head_commander_role not in member.roles:
            await interaction.response.send_message(f"{user.mention} does not have the Head Commander role.", ephemeral=True)
            return

        await member.remove_roles(head_commander_role)
        await interaction.response.send_message(f"Removed Head Commander role from {user.mention}.")
        await log_action(interaction, "Remove Head Commander", f"Removed Head Commander role from {user.mention}.")

    @app_commands.command(name="listheadcommanders", description="List all Head Commanders in this server")
    async def listheadcommanders(self, interaction: discord.Interaction):
        head_commander_role = discord.utils.get(interaction.guild.roles, name="head commander")

        if not head_commander_role or not head_commander_role.members:
            await interaction.response.send_message("No users have the **Head Commander** role.")
            return

        members_list = "\n".join([f"{member.mention} ({member.name})" for member in head_commander_role.members])
        msg = f"**Head Commanders ({len(head_commander_role.members)})**\n{members_list}"
        await interaction.response.send_message(msg)
        await log_action(interaction, "List Head Commanders", f"Listed {len(head_commander_role.members)} Head Commanders.")

    @app_commands.command(name="export", description="Export guild data in various formats")
    @app_commands.describe(
        data_type="What data to export",
        export_format="Export format"
    )
    @app_commands.choices(
        data_type=[
            app_commands.Choice(name="Current Guild Members", value="guild_members"),
            app_commands.Choice(name="Guild Change History", value="guild_history"),
            app_commands.Choice(name="Guild State (JSON)", value="guild_state")
        ],
        export_format=[
            app_commands.Choice(name="CSV", value="csv"),
            app_commands.Choice(name="JSON", value="json"),
            app_commands.Choice(name="Plain Text", value="txt")
        ]
    )
    async def export(
        self,
        interaction: discord.Interaction,
        data_type: str = "guild_members",
        export_format: str = "csv"
    ):
        data_type = data_type or "guild_members"
        export_format = export_format or "csv"

        if data_type == "guild_members":
            self.cursor.execute("SELECT members FROM guild_state WHERE channel_id=?", (interaction.channel_id,))
            row = self.cursor.fetchone()
            if not row or not row[0]:
                await interaction.response.send_message("No guild members found to export.")
                await log_action(interaction, "Export Guild Members", "No data found.")
                return

            members = json.loads(row[0])
            data = [{"name": name, "uid": uid} for uid, name in members.items()]

        elif data_type == "guild_history":
            self.cursor.execute(
                "SELECT timestamp, joined, left FROM guild_history WHERE channel_id=? ORDER BY id DESC",
                (interaction.channel_id,)
            )
            rows = self.cursor.fetchall()
            if not rows:
                await interaction.response.send_message("No guild history found to export.")
                await log_action(interaction, "Export Guild History", "No data found.")
                return

            data = []
            for timestamp, joined_json, left_json in rows:
                entry = {"timestamp": timestamp}
                if joined_json:
                    entry["joined"] = json.loads(joined_json)
                if left_json:
                    entry["left"] = json.loads(left_json)
                data.append(entry)

        elif data_type == "guild_state":
            self.cursor.execute("SELECT members FROM guild_state WHERE channel_id=?", (interaction.channel_id,))
            row = self.cursor.fetchone()
            if not row or not row[0]:
                await interaction.response.send_message("No guild state found to export.")
                await log_action(interaction, "Export Guild State", "No data found.")
                return

            data = json.loads(row[0])

        if export_format == "csv":
            import io
            import csv
            buf = io.StringIO()

            if data_type == "guild_members":
                writer = csv.writer(buf)
                writer.writerow(["Name", "UID"])
                for member in data:
                    writer.writerow([member["name"], member["uid"]])
                filename = "guild_members.csv"

            elif data_type == "guild_history":
                writer = csv.writer(buf)
                writer.writerow(["Timestamp", "Action", "Name", "UID"])
                for entry in data:
                    timestamp = entry["timestamp"]
                    if "joined" in entry:
                        for name, uid in entry["joined"]:
                            writer.writerow([timestamp, "Joined", name, uid])
                    if "left" in entry:
                        for name, uid in entry["left"]:
                            writer.writerow([timestamp, "Left", name, uid])
                filename = "guild_history.csv"

            elif data_type == "guild_state":
                writer = csv.writer(buf)
                writer.writerow(["UID", "Name"])
                for uid, name in data.items():
                    writer.writerow([uid, name])
                filename = "guild_state.csv"

            file = discord.File(io.BytesIO(buf.getvalue().encode("utf-8")), filename=filename)

        elif export_format == "json":
            import io
            json_data = json.dumps(data, indent=2, ensure_ascii=False)
            file = discord.File(io.BytesIO(json_data.encode("utf-8")), filename=f"{data_type}.json")

        elif export_format == "txt":
            import io
            buf = io.StringIO()

            if data_type == "guild_members":
                buf.write("Current Guild Members:\n\n")
                for member in data:
                    buf.write(f"{member['name']},{member['uid']}\n")

            elif data_type == "guild_history":
                buf.write("Guild Change History:\n\n")
                for entry in data:
                    buf.write(f"[{entry['timestamp']}]\n")
                    if "joined" in entry:
                        buf.write("Joined:\n")
                        for name, uid in entry["joined"]:
                            buf.write(f"  {name} ({uid})\n")
                    if "left" in entry:
                        buf.write("Left:\n")
                        for name, uid in entry["left"]:
                            buf.write(f"  {name} ({uid})\n")
                    buf.write("\n")

            elif data_type == "guild_state":
                buf.write("Guild State (UID -> Name):\n\n")
                for uid, name in data.items():
                    buf.write(f"{uid} -> {name}\n")

            file = discord.File(io.BytesIO(buf.getvalue().encode("utf-8")), filename=f"{data_type}.txt")

        await interaction.response.send_message(f"Here's the exported {data_type.replace('_', ' ')} data in {export_format.upper()} format:", file=file)
        await log_action(interaction, "Export Data", f"Exported {data_type} in {export_format} format.")

    @app_commands.command(name="exportall", description="Export all guild data (members + history) as ZIP")
    async def exportall(self, interaction: discord.Interaction):
        import zipfile
        import io

        self.cursor.execute("SELECT members FROM guild_state WHERE channel_id=?", (interaction.channel_id,))
        row = self.cursor.fetchone()
        members_data = json.loads(row[0]) if row and row[0] else {}

        self.cursor.execute(
            "SELECT timestamp, joined, left FROM guild_history WHERE channel_id=? ORDER BY id DESC",
            (interaction.channel_id,)
        )
        history_rows = self.cursor.fetchall()

        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            members_csv = "Name,UID\n"
            for uid, name in members_data.items():
                members_csv += f"{name},{uid}\n"
            zip_file.writestr("guild_members.csv", members_csv)

            history_csv = "Timestamp,Action,Name,UID\n"
            for timestamp, joined_json, left_json in history_rows:
                if joined_json:
                    for name, uid in json.loads(joined_json):
                        history_csv += f"{timestamp},Joined,{name},{uid}\n"
                if left_json:
                    for name, uid in json.loads(left_json):
                        history_csv += f"{timestamp},Left,{name},{uid}\n"
            zip_file.writestr("guild_history.csv", history_csv)

            all_data = {
                "members": members_data,
                "history": [
                    {
                        "timestamp": timestamp,
                        "joined": json.loads(joined_json) if joined_json else [],
                        "left": json.loads(left_json) if left_json else []
                    } for timestamp, joined_json, left_json in history_rows
                ]
            }
            zip_file.writestr("guild_data.json", json.dumps(all_data, indent=2, ensure_ascii=False))

        zip_buffer.seek(0)
        file = discord.File(zip_buffer, filename="guild_export.zip")
        await interaction.response.send_message("Here's a complete export of all guild data:", file=file)
        await log_action(interaction, "Export All Data", "Exported complete guild data as ZIP.")

    @app_commands.command(name="listreconcile", description="List all Reconcile cog commands")
    async def listreconcile(self, interaction: discord.Interaction):
        commands = [
            "currentmembers", "guildupdates", "clearguild", "editguild", "guildhistory",
            "resethistory", "addheadcommander", "removeheadcommander", "listheadcommanders",
            "export", "exportall", "listreconcile"
        ]
        await interaction.response.send_message(f"Reconcile commands: {', '.join(commands)}")


async def setup(bot):
    await bot.add_cog(ReconcileCog(bot))
