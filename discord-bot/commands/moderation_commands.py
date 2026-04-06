"""User Moderation & Discipline Commands"""
import discord
from discord import app_commands
from discord.ext import commands
import io
from datetime import datetime, timezone, timedelta
from helpers import (
    log_action,
    is_commander,
    add_warning,
    get_warnings,
    clear_warnings,
    clear_all_warnings,
    get_member_name_by_uid,
    get_all_warned_members,
    add_ban,
    get_bans,
    get_ban,
    remove_ban,
    clear_bans,
    get_banned_members,
    add_global_ban,
    get_global_bans,
    get_global_ban,
    remove_global_ban,
    clear_global_bans,
    is_globally_banned,
    update_glory,
    get_glory_data,
    set_glory_threshold,
    get_glory_threshold,
    add_glory_exception,
    remove_glory_exception,
    get_glory_exceptions,
    is_glory_exception
)

# IST timezone constant
IST = timezone(timedelta(hours=5, minutes=30))

class WarnUIDModal(discord.ui.Modal, title="Warn Players by UID"):
    def __init__(self, cog):
        super().__init__()
        self.cog = cog

    warn_data = discord.ui.TextInput(
        label="UID and Reason",
        placeholder="Enter warnings in format: UID,Reason (one per line)",
        style=discord.TextStyle.paragraph,
        required=True,
        max_length=4000
    )

    async def on_submit(self, interaction: discord.Interaction):
        text = self.warn_data.value
        warnings_added = []
        invalid_lines = []

        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue

            parts = line.split(",", 1)  # Split on first comma only
            if len(parts) != 2:
                invalid_lines.append(line)
                continue

            uid_str, reason = parts
            uid_str = uid_str.strip()
            reason = reason.strip()

            if not uid_str or not reason:
                invalid_lines.append(line)
                continue

            # Validate UID is an integer
            try:
                uid = int(uid_str)
            except ValueError:
                invalid_lines.append(line)
                continue

            # Add warning
            timestamp = datetime.now(IST).isoformat()
            success = add_warning(interaction.channel_id, uid, reason, str(interaction.user.id), timestamp, guild_id=interaction.guild_id)

            if success:
                player_name = get_member_name_by_uid(interaction.channel_id, str(uid))
                display_target = f"{player_name} ({uid})" if player_name else f"UID {uid}"
                warnings_added.append((uid, reason, display_target))

        # Build response message
        msg = "**Warnings Processed**\n\n"
        if warnings_added:
            msg += f"✅ **Added {len(warnings_added)} warning(s):**\n"
            for uid, reason, display_target in warnings_added:
                msg += f"• {display_target}: {reason}\n"
        
        if invalid_lines:
            msg += f"\n⚠️ **Skipped {len(invalid_lines)} invalid line(s)**\n"

        await interaction.response.send_message(msg)
        
        # Log action
        if warnings_added:
            for uid, reason, display_target in warnings_added:
                await log_action(interaction, "Player Warned", f"{display_target} warned by {interaction.user.mention}. Reason: {reason}")

    async def on_error(self, interaction: discord.Interaction, error: Exception):
        await interaction.response.send_message("An error occurred while processing warnings.", ephemeral=True)
        print(f"Modal error: {error}")


class BanUIDModal(discord.ui.Modal, title="Ban Players by UID"):
    def __init__(self, cog):
        super().__init__()
        self.cog = cog

    ban_data = discord.ui.TextInput(
        label="UID,Player Name,Reason,WhatsApp",
        placeholder="Enter ban records in format: UID,Player Name,Reason,WhatsApp (one per line)",
        style=discord.TextStyle.paragraph,
        required=True,
        max_length=4000
    )

    async def on_submit(self, interaction: discord.Interaction):
        text = self.ban_data.value
        bans_added = []
        invalid_lines = []

        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue

            parts = [p.strip() for p in line.split(",", 3)]
            if len(parts) != 4:
                invalid_lines.append(line)
                continue

            uid_str, player_name, reason, whatsapp = parts
            if not uid_str or not player_name or not reason:
                invalid_lines.append(line)
                continue

            try:
                uid = int(uid_str)
            except ValueError:
                invalid_lines.append(line)
                continue

            timestamp = datetime.now(IST).isoformat()
            success = add_ban(interaction.channel_id, uid, player_name, reason, whatsapp, str(interaction.user.id), timestamp, guild_id=interaction.guild_id)
            if success:
                bans_added.append((uid, player_name, reason, whatsapp))

        msg = "**Ban Entries Processed**\n\n"
        if bans_added:
            msg += f"✅ **Added {len(bans_added)} ban(s):**\n"
            for uid, player_name, reason, whatsapp in bans_added:
                msg += f"• {player_name} ({uid}) - {reason}, WhatsApp: {whatsapp}\n"

        if invalid_lines:
            msg += f"\n⚠️ **Skipped {len(invalid_lines)} invalid line(s)**\n"

        await interaction.response.send_message(msg)

        if bans_added:
            for uid, player_name, reason, whatsapp in bans_added:
                await log_action(interaction, "Player Banned", f"{player_name} ({uid}) banned by {interaction.user.mention}. Reason: {reason}. WhatsApp: {whatsapp}")

    async def on_error(self, interaction: discord.Interaction, error: Exception):
        await interaction.response.send_message("An error occurred while processing ban entries.", ephemeral=True)
        print(f"Ban modal error: {error}")


class GloryCheckModal(discord.ui.Modal, title="Check Glory Levels"):
    def __init__(self, cog):
        super().__init__()
        self.cog = cog

    glory_data = discord.ui.TextInput(
        label="UID and Glory",
        placeholder="Enter glory checks in format: UID,Glory (one per line)",
        style=discord.TextStyle.paragraph,
        required=True,
        max_length=4000
    )

    async def on_submit(self, interaction: discord.Interaction):
        text = self.glory_data.value
        warnings_needed = []
        invalid_lines = []
        no_warning_needed = []

        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue

            parts = line.split(",", 1)
            if len(parts) != 2:
                invalid_lines.append(line)
                continue

            uid_str, glory_str = parts
            uid_str = uid_str.strip()
            glory_str = glory_str.strip()

            if not uid_str or not glory_str:
                invalid_lines.append(line)
                continue

            try:
                uid = int(uid_str)
                glory = int(glory_str)
            except ValueError:
                invalid_lines.append(line)
                continue

            if glory >= 7000:
                no_warning_needed.append((uid, glory))
                continue

            # Get player name from guild data
            player_name = get_member_name_by_uid(interaction.channel_id, str(uid))
            if not player_name:
                invalid_lines.append(f"{uid},{glory} (not found in guild data)")
                continue

            warnings_needed.append((uid, glory, player_name))

        # Build response message
        msg = "**Glory Check Results**\n\n"
        if warnings_needed:
            msg += f"⚠️ **Glory warnings ({len(warnings_needed)}):\n**"
            for uid, glory, player_name in warnings_needed:
                msg += f"• {player_name} (UID: {uid}): Glory {glory}\n"
        
        if no_warning_needed:
            msg += f"\n✅ **Players with sufficient glory ({len(no_warning_needed)})** (glory >= 7000)\n"
        
        if invalid_lines:
            msg += f"\n❌ **Invalid entries ({len(invalid_lines)}):\n**"
            for line in invalid_lines[:10]:  # Limit to first 10 to avoid message too long
                msg += f"• {line}\n"
            if len(invalid_lines) > 10:
                msg += f"... and {len(invalid_lines) - 10} more\n"

        await interaction.response.send_message(msg)
        
        # Log action
        if warnings_needed:
            await log_action(interaction, "Glory Check", f"Checked glory for {len(warnings_needed)} players needing warnings")

    async def on_error(self, interaction: discord.Interaction, error: Exception):
        await interaction.response.send_message("An error occurred while processing glory checks.", ephemeral=True)
        print(f"Glory check modal error: {error}")


class GloryUpdateModal(discord.ui.Modal, title="Update Glory Data"):
    def __init__(self, cog):
        super().__init__()
        self.cog = cog

    glory_data = discord.ui.TextInput(
        label="UID and Glory",
        placeholder="Enter glory updates in format: UID,Glory (one per line)",
        style=discord.TextStyle.paragraph,
        required=True,
        max_length=4000
    )

    async def on_submit(self, interaction: discord.Interaction):
        text = self.glory_data.value
        updated = []
        invalid_lines = []

        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue

            parts = line.split(",", 1)
            if len(parts) != 2:
                invalid_lines.append(line)
                continue

            uid_str, glory_str = parts
            uid_str = uid_str.strip()
            glory_str = glory_str.strip()

            if not uid_str or not glory_str:
                invalid_lines.append(line)
                continue

            try:
                uid = int(uid_str)
                glory = int(glory_str)
            except ValueError:
                invalid_lines.append(line)
                continue

            timestamp = datetime.now(IST).isoformat()
            success = update_glory(interaction.channel_id, uid, glory, str(interaction.user.id), timestamp)
            if success:
                updated.append((uid, glory))
            else:
                invalid_lines.append(f"{uid},{glory} (update failed)")

        # Build response message
        msg = "**Glory Data Updated**\n\n"
        if updated:
            msg += f"✅ **Updated {len(updated)} glory records:**\n"
            for uid, glory in updated[:20]:  # Limit display
                msg += f"• UID {uid}: Glory {glory}\n"
            if len(updated) > 20:
                msg += f"... and {len(updated) - 20} more\n"
        
        if invalid_lines:
            msg += f"\n❌ **Skipped {len(invalid_lines)} invalid line(s)**\n"

        await interaction.response.send_message(msg)
        
        # Log action
        if updated:
            await log_action(interaction, "Glory Updated", f"Updated glory data for {len(updated)} players")

    async def on_error(self, interaction: discord.Interaction, error: Exception):
        await interaction.response.send_message("An error occurred while updating glory data.", ephemeral=True)
        print(f"Glory update modal error: {error}")


class ModerationCommands(commands.Cog):
    """Commands for user moderation and discipline"""
    
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="warnuid", description="Warn players by UID (Commanders only)")
    async def warnuid(self, interaction: discord.Interaction):
        if not is_commander(interaction):
            await interaction.response.send_message("Only Commanders can warn players.")
            await log_action(interaction, "Permission Denied", f"{interaction.user.mention} attempted /warnuid without permission.")
            return

        modal = WarnUIDModal(self)
        await interaction.response.send_modal(modal)

    @app_commands.command(name="warnings", description="View warnings for a UID")
    async def warnings(self, interaction: discord.Interaction, uid: str):
        # Validate UID is an integer
        try:
            uid_int = int(uid)
        except ValueError:
            await interaction.response.send_message(f"Invalid UID. Please provide a valid integer UID.")
            return

        results = get_warnings(interaction.channel_id, uid_int)
        if not results:
            await interaction.response.send_message(f"No warnings found for UID {uid_int}.")
            return

        player_name = get_member_name_by_uid(interaction.channel_id, str(uid_int))
        display_target = f"{player_name} ({uid_int})" if player_name else f"UID {uid_int}"

        lines = [f"ID {row[0]} - {row[2]} at {row[3]}: {row[1]}" for row in results]
        output = "\n".join(lines)

        if len(output) > 1900:
            buf = io.StringIO()
            buf.write(output)
            file = discord.File(io.BytesIO(buf.getvalue().encode('utf-8')), filename=f"warnings_{uid_int}.txt")
            await interaction.response.send_message(f"Warnings for {display_target} are too long; sending as file.", file=file)
        else:
            await interaction.response.send_message(f"Warnings for {display_target}:\n{output}")

        await log_action(interaction, "View Warnings", f"{interaction.user.mention} viewed warnings for {display_target}.")

    @app_commands.command(name="clearwarnings", description="Clear all warnings for a UID (Admins only)")
    async def clearwarnings(self, interaction: discord.Interaction, uid: str):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("Only Admins can clear warnings.", ephemeral=True)
            await log_action(interaction, "Permission Denied", f"{interaction.user.mention} attempted /clearwarnings without permission.")
            return

        # Validate UID is an integer
        try:
            uid_int = int(uid)
        except ValueError:
            await interaction.response.send_message(f"Invalid UID. Please provide a valid integer UID.")
            return

        if clear_warnings(interaction.channel_id, uid_int):
            await interaction.response.send_message(f"Warnings for UID {uid_int} have been cleared.")
            await log_action(interaction, "Warnings Cleared", f"Cleared warnings for UID {uid_int}.")
        else:
            await interaction.response.send_message("Could not clear warnings. Please try again.")

    @app_commands.command(name="clearallwarnings", description="Clear all warnings in this channel (Admins only)")
    async def clearallwarnings(self, interaction: discord.Interaction):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("Only Admins can clear all warnings in this channel.", ephemeral=True)
            await log_action(interaction, "Permission Denied", f"{interaction.user.mention} attempted /clearallwarnings without permission.")
            return

        if clear_all_warnings(interaction.channel_id):
            await interaction.response.send_message("All warnings in this channel have been cleared.")
            await log_action(interaction, "Warnings Cleared", "Cleared all warnings in this channel.")
        else:
            await interaction.response.send_message("Could not clear warnings. Please try again.")

    @app_commands.command(name="listwarnings", description="List all members with warnings")
    async def listwarnings(self, interaction: discord.Interaction):
        warned_members = get_all_warned_members(interaction.channel_id)

        if not warned_members:
            await interaction.response.send_message("No members with warnings in this guild.")
            await log_action(interaction, "List Warnings", "Viewed warned members list - no warnings found.")
            return

        # Build the output
        lines = ["UID,Warning Count,Player Name"]
        for uid, warning_count in warned_members:
            player_name = get_member_name_by_uid(interaction.channel_id, int(uid))
            if player_name:
                lines.append(f"{uid},{warning_count},{player_name}")
            else:
                lines.append(f"{uid},{warning_count},Unknown")

        output = "\n".join(lines)

        # Check if output is too long for Discord message
        if len(output) > 1900:
            # Send as file
            file = discord.File(io.BytesIO(output.encode("utf-8")), filename="warned_members.csv")
            await interaction.response.send_message(f"Warned members list (CSV):", file=file)
        else:
            # Send as message block
            await interaction.response.send_message(f"**Warned Members List:**\n```csv\n{output}\n```")

        await log_action(interaction, "List Warnings", f"Viewed warned members list - {len(warned_members)} members with warnings.")

    @app_commands.command(name="banuid", description="Ban players by UID (Commanders only)")
    async def banuid(self, interaction: discord.Interaction):
        if not is_commander(interaction):
            await interaction.response.send_message("Only Commanders can ban players.")
            await log_action(interaction, "Permission Denied", f"{interaction.user.mention} attempted /banuid without permission.")
            return

        modal = BanUIDModal(self)
        await interaction.response.send_modal(modal)

    @app_commands.command(name="listbans", description="List all banned members in this channel")
    async def listbans(self, interaction: discord.Interaction):
        bans = get_banned_members(interaction.channel_id)

        if not bans:
            await interaction.response.send_message("No banned members in this channel.")
            await log_action(interaction, "List Bans", "Viewed ban list - none found.")
            return

        lines = ["UID,Player Name,Reason,WhatsApp,BannedBy,Timestamp"]
        for uid, player_name, reason, whatsapp, banned_by, timestamp in bans:
            player_name = player_name or "Unknown"
            whatsapp = whatsapp or "N/A"
            lines.append(f"{uid},{player_name},{reason},{whatsapp},{banned_by},{timestamp}")

        output = "\n".join(lines)
        if len(output) > 1900:
            file = discord.File(io.BytesIO(output.encode('utf-8')), filename="banned_members.csv")
            await interaction.response.send_message("Banned members list is long; sending as attachment.", file=file)
        else:
            await interaction.response.send_message(f"**Banned Members:**\n```csv\n{output}\n```")

        await log_action(interaction, "List Bans", f"Viewed ban list with {len(bans)} entries.")

    def _is_owner(self, interaction: discord.Interaction):
        owner_id = self.bot.owner_id
        if owner_id is None:
            return False
        return interaction.user.id == owner_id

    @app_commands.command(name="globalban", description="Add a global ban by UID (Owner only)")
    async def globalban(self, interaction: discord.Interaction, uid: str, player_name: str, reason: str, whatsapp: str):
        if not self._is_owner(interaction):
            await interaction.response.send_message("Only the bot owner can use this command.", ephemeral=True)
            await log_action(interaction, "Permission Denied", f"{interaction.user.mention} attempted /globalban without permission.")
            return

        try:
            uid_int = int(uid)
        except ValueError:
            await interaction.response.send_message("Invalid UID. Please provide a valid integerUID.")
            return

        timestamp = datetime.now(IST).isoformat()
        if add_global_ban(uid_int, player_name, reason, whatsapp, str(interaction.user.id), timestamp, source_guild_id=interaction.guild_id):
            await interaction.response.send_message(f"Global ban added: {player_name} ({uid_int}) - {reason}")
            await log_action(interaction, "Global Ban Added", f"Added global ban for {player_name} ({uid_int}) by {interaction.user.mention}.")
        else:
            await interaction.response.send_message("Could not add global ban. Please try again.")

    @app_commands.command(name="listglobalbans", description="List all global ban entries (Owner only)")
    async def listglobalbans(self, interaction: discord.Interaction):
        if not self._is_owner(interaction):
            await interaction.response.send_message("Only the bot owner can use this command.", ephemeral=True)
            return

        bans = get_global_bans()
        if not bans:
            await interaction.response.send_message("No global bans set.")
            return

        lines = ["UID,Player Name,Reason,WhatsApp,BannedBy,Timestamp,SourceGuild"]
        for uid, player_name, reason, whatsapp, banned_by, timestamp, source_guild_id in bans:
            lines.append(f"{uid},{player_name},{reason},{whatsapp},{banned_by},{timestamp},{source_guild_id or 'N/A'}")

        output = "\n".join(lines)
        if len(output) > 1900:
            file = discord.File(io.BytesIO(output.encode('utf-8')), filename="global_bans.csv")
            await interaction.response.send_message("Global bans list is long; sending as attachment.", file=file)
        else:
            await interaction.response.send_message(f"**Global Bans:**\n```csv\n{output}\n```")

        await log_action(interaction, "List Global Bans", f"Viewed global ban list with {len(bans)} entries.")

    @app_commands.command(name="removeglobalban", description="Remove a global ban by UID (Owner only)")
    async def removeglobalban(self, interaction: discord.Interaction, uid: str):
        if not self._is_owner(interaction):
            await interaction.response.send_message("Only the bot owner can use this command.", ephemeral=True)
            return

        try:
            uid_int = int(uid)
        except ValueError:
            await interaction.response.send_message("Invalid UID. Please provide a valid integer UID.")
            return

        if remove_global_ban(uid_int):
            await interaction.response.send_message(f"Global ban removed for UID {uid_int}.")
            await log_action(interaction, "Global Ban Removed", f"Removed global ban for UID {uid_int}.")
        else:
            await interaction.response.send_message("Could not remove global ban. Please try again.")

    @app_commands.command(name="clearglobalbans", description="Clear all global bans (Owner only)")
    async def clearglobalbans(self, interaction: discord.Interaction):
        if not self._is_owner(interaction):
            await interaction.response.send_message("Only the bot owner can use this command.", ephemeral=True)
            return

        if clear_global_bans():
            await interaction.response.send_message("All global bans have been cleared.")
            await log_action(interaction, "Global Bans Cleared", "Cleared all global bans.")
        else:
            await interaction.response.send_message("Could not clear global bans. Please try again.")

    @app_commands.command(name="checkban", description="Check whether a UID is globally banned")
    async def checkban(self, interaction: discord.Interaction, uid: str):
        try:
            uid_int = int(uid)
        except ValueError:
            await interaction.response.send_message("Invalid UID. Please provide a valid integer UID.")
            return

        if is_globally_banned(uid_int):
            ban_entry = get_global_ban(uid_int)
            if ban_entry:
                _, player_name, reason, whatsapp, banned_by, timestamp, source_guild_id = ban_entry
                await interaction.response.send_message(f"UID {uid_int} is globally banned: {player_name} - {reason} (Whatsapp: {whatsapp})")
                return
        await interaction.response.send_message(f"UID {uid_int} is not globally banned.")

        await log_action(interaction, "Check Global Ban", f"Checked global ban status for UID {uid_int}.")

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        # optional check by Discord user ID against global ban UID values
        if is_globally_banned(member.id):
            try:
                await member.guild.kick(member, reason="Global ban enforcement")
                print(f"Kicked globally banned user {member} on join.")
            except Exception as e:
                print(f"Failed to kick globally banned user {member}: {e}")

    @app_commands.command(name="unbanuid", description="Unban a specific UID (Admins only)")
    async def unbanuid(self, interaction: discord.Interaction, uid: str):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("Only Admins can unban players.", ephemeral=True)
            await log_action(interaction, "Permission Denied", f"{interaction.user.mention} attempted /unbanuid without permission.")
            return

        try:
            uid_int = int(uid)
        except ValueError:
            await interaction.response.send_message("Invalid UID. Must be an integer.")
            return

        if remove_ban(interaction.channel_id, uid_int):
            await interaction.response.send_message(f"UID {uid_int} removed from the ban list.")
            await log_action(interaction, "Unban UID", f"Removed ban for UID {uid_int}.")
        else:
            await interaction.response.send_message("Could not remove ban. Please try again.")

    @app_commands.command(name="clearbans", description="Clear all bans in this channel (Admins only)")
    async def clearbans(self, interaction: discord.Interaction):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("Only Admins can clear bans.", ephemeral=True)
            await log_action(interaction, "Permission Denied", f"{interaction.user.mention} attempted /clearbans without permission.")
            return

        if clear_bans(interaction.channel_id):
            await interaction.response.send_message("All bans in this channel have been cleared.")
            await log_action(interaction, "Clear Bans", "Cleared all bans in this channel.")
        else:
            await interaction.response.send_message("Could not clear bans. Please try again.")

    @app_commands.command(name="mute", description="Mute a user by assigning Muted role (Admins only)")
    async def mute(self, interaction: discord.Interaction, member: discord.Member):
        await interaction.response.defer()
        
        if not interaction.user.guild_permissions.administrator:
            await interaction.followup.send("Only Admins can mute users.", ephemeral=True)
            await log_action(interaction, "Permission Denied", f"{interaction.user.mention} attempted /mute without permission.")
            return
        guild = interaction.guild
        role = discord.utils.get(guild.roles, name="Muted")
        if role is None:
            role = await guild.create_role(name="Muted")
            for channel in guild.channels:
                await channel.set_permissions(role, send_messages=False)
        await member.add_roles(role)
        await interaction.followup.send(f"🔇 {member.display_name} has been muted.")
        await log_action(interaction, "User Muted", f"{member.mention} has been muted.")

    @app_commands.command(name="unmute", description="Unmute a user by removing Muted role (Commanders only)")
    async def unmute(self, interaction: discord.Interaction, member: discord.Member):
        if not is_commander(interaction):
            await interaction.response.send_message("Only Commanders can unmute users.", ephemeral=True)
            await log_action(interaction, "Permission Denied", f"{interaction.user.mention} attempted /unmute without permission.")
            return
        role = discord.utils.get(interaction.guild.roles, name="Muted")
        if role is None or role not in member.roles:
            await interaction.response.send_message(f"{member.display_name} is not muted.", ephemeral=True)
            return
        await member.remove_roles(role)
        await interaction.response.send_message(f"🔊 {member.display_name} has been unmuted.")
        await log_action(interaction, "User Unmuted", f"{member.mention} has been unmuted.")

    @app_commands.command(name="check_glory", description="Check stored glory levels and report players below threshold (Commanders only)")
    async def check_glory(self, interaction: discord.Interaction):
        if not is_commander(interaction):
            await interaction.response.send_message("Only Commanders can check glory.", ephemeral=True)
            await log_action(interaction, "Permission Denied", f"{interaction.user.mention} attempted /check_glory without permission.")
            return

        glory_data = get_glory_data(interaction.channel_id)
        if not glory_data:
            await interaction.response.send_message("No glory data stored for this channel. Use `/update_glory` to add glory data first.")
            return

        threshold = get_glory_threshold(interaction.channel_id)
        warnings_needed = []
        no_warning_needed = []

        for uid, glory in glory_data:
            if glory < threshold:
                player_name = get_member_name_by_uid(interaction.channel_id, str(uid))
                if player_name:
                    warnings_needed.append((uid, glory, player_name))
                else:
                    warnings_needed.append((uid, glory, f"Unknown (UID: {uid})"))
            else:
                no_warning_needed.append((uid, glory))

        # Build response message
        msg = f"**Glory Check Results (Threshold: {threshold})**\n\n"
        if warnings_needed:
            msg += f"⚠️ **Players needing glory warnings ({len(warnings_needed)}):\n**"
            for uid, glory, player_name in warnings_needed[:20]:  # Limit display
                msg += f"• {player_name}: Glory {glory}\n"
            if len(warnings_needed) > 20:
                msg += f"... and {len(warnings_needed) - 20} more\n"
        
        if no_warning_needed:
            msg += f"\n✅ **Players with sufficient glory ({len(no_warning_needed)})** (glory >= {threshold})\n"
        
        if len(msg) > 1900:
            # If too long, send as file
            buf = io.StringIO()
            buf.write(msg)
            file = discord.File(io.BytesIO(buf.getvalue().encode('utf-8')), filename="glory_check.txt")
            await interaction.response.send_message("Glory check results are long; sending as file.", file=file)
        else:
            await interaction.response.send_message(msg)
        
        # Log action
        if warnings_needed:
            await log_action(interaction, "Glory Check", f"Checked glory - {len(warnings_needed)} players need warnings (threshold: {threshold})")

    @app_commands.command(name="view_glory", description="View all stored glory levels")
    async def view_glory(self, interaction: discord.Interaction):
        glory_data = get_glory_data(interaction.channel_id)
        if not glory_data:
            await interaction.response.send_message("No glory data stored for this channel. Use `/update_glory` to add glory data first.")
            return

        threshold = get_glory_threshold(interaction.channel_id)
        
        # Sort by glory level (highest first)
        sorted_glory = sorted(glory_data, key=lambda x: x[1], reverse=True)
        
        # Build CSV data
        glory_csv = "Name,Glory\n"
        for uid, glory in sorted_glory:
            player_name = get_member_name_by_uid(interaction.channel_id, str(uid))
            display_name = player_name if player_name else f"Unknown"
            glory_csv += f"{display_name},{glory}\n"
        
        msg = f"**Glory Levels**\n```csv\n{glory_csv}\n```"
        
        if len(msg) > 1900:
            # If too long, send as file
            file = discord.File(io.BytesIO(glory_csv.encode('utf-8')), filename="glory_data.csv")
            await interaction.response.send_message(f"Glory data for {len(sorted_glory)} players is too long; file attached:", file=file)
        else:
            await interaction.response.send_message(msg)
        
        await log_action(interaction, "View Glory", f"Viewed glory levels for {len(sorted_glory)} players")

    @app_commands.command(name="glory_warn", description="Automatically warn players below glory threshold (resets next Monday 00:00 IST)")
    async def glory_warn(self, interaction: discord.Interaction):
        if not is_commander(interaction):
            await interaction.response.send_message("Only Commanders can issue glory warnings.", ephemeral=True)
            await log_action(interaction, "Permission Denied", f"{interaction.user.mention} attempted /glory_warn without permission.")
            return

        glory_data = get_glory_data(interaction.channel_id)
        if not glory_data:
            await interaction.response.send_message("No glory data stored for this channel. Use `/update_glory` to add glory data first.")
            return

        threshold = get_glory_threshold(interaction.channel_id)
        warnings_added = []
        already_warned = []
        errors = []

        for uid, glory in glory_data:
            if glory >= threshold:
                continue  # Skip players with sufficient glory

            # Check if already warned for low glory - next warning allowed only next Monday 00:00 IST
            existing_warnings = get_warnings(interaction.channel_id, uid)
            recent_glory_warnings = [w for w in existing_warnings if "Low glory" in w[1]]
            
            if recent_glory_warnings:
                # Get the most recent glory warning
                most_recent_warning = recent_glory_warnings[0]  # Already ordered by ID DESC (most recent first)
                warning_timestamp_str = most_recent_warning[3]  # timestamp is at index 3
                
                try:
                    warning_timestamp = datetime.fromisoformat(warning_timestamp_str.replace('Z', '+00:00'))
                    # Convert to IST if it's not already
                    if warning_timestamp.tzinfo is None:
                        warning_timestamp = warning_timestamp.replace(tzinfo=timezone.utc).astimezone(IST)
                    elif warning_timestamp.tzinfo != IST:
                        warning_timestamp = warning_timestamp.astimezone(IST)
                    
                    # Calculate next Monday 00:00 IST
                    warning_weekday = warning_timestamp.weekday()  # Monday is 0, Sunday is 6
                    
                    # Days until next Monday from the warning
                    if warning_weekday == 0:  # Warning was on Monday
                        days_until_next_monday = 7
                    else:  # Warning was on another day
                        days_until_next_monday = 7 - warning_weekday
                    
                    # Next Monday at 00:00 IST
                    next_monday_reset = warning_timestamp.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=days_until_next_monday)
                    
                    # Check if current time is before next Monday reset
                    current_time = datetime.now(IST)
                    if current_time < next_monday_reset:
                        already_warned.append((uid, glory))
                        continue
                except (ValueError, TypeError):
                    # If timestamp parsing fails, assume it's recent to be safe
                    already_warned.append((uid, glory))
                    continue

            # Check if player is exempted from glory warnings
            if is_glory_exception(interaction.channel_id, uid):
                continue  # Skip exempted players

            # Add warning
            player_name = get_member_name_by_uid(interaction.channel_id, str(uid))
            reason = f"Low glory: {glory} (threshold: {threshold})"
            timestamp = datetime.now(IST).isoformat()
            
            success = add_warning(interaction.channel_id, uid, reason, str(interaction.user.id), timestamp, guild_id=interaction.guild_id)
            if success:
                display_name = player_name if player_name else f"UID {uid}"
                warnings_added.append((uid, glory, display_name))
            else:
                errors.append((uid, glory))

        # Build response message
        msg = f"**Glory Warnings Issued (Threshold: {threshold})**\n\n"
        if warnings_added:
            msg += f"⚠️ **Added {len(warnings_added)} warning(s):**\n"
            for uid, glory, display_name in warnings_added[:20]:  # Limit display
                msg += f"• {display_name}: Glory {glory}\n"
            if len(warnings_added) > 20:
                msg += f"... and {len(warnings_added) - 20} more\n"
        
        if already_warned:
            msg += f"\n📋 **Already warned - next warning allowed Monday 00:00 IST ({len(already_warned)}):**\n"
            for uid, glory in already_warned[:10]:  # Limit display
                msg += f"• UID {uid}: Glory {glory}\n"
            if len(already_warned) > 10:
                msg += f"... and {len(already_warned) - 10} more\n"
        
        if errors:
            msg += f"\n❌ **Failed to warn ({len(errors)}):**\n"
            for uid, glory in errors[:5]:  # Limit display
                msg += f"• UID {uid}: Glory {glory}\n"
            if len(errors) > 5:
                msg += f"... and {len(errors) - 5} more\n"

        await interaction.response.send_message(msg)
        
        # Log action
        if warnings_added:
            await log_action(interaction, "Glory Warnings", f"Issued {len(warnings_added)} glory warnings (threshold: {threshold})")

    @app_commands.command(name="set_glory_threshold", description="Set minimum glory threshold for this channel (Commanders only)")
    async def set_glory_threshold(self, interaction: discord.Interaction, threshold: int):
        if not is_commander(interaction):
            await interaction.response.send_message("Only Commanders can set glory threshold.", ephemeral=True)
            await log_action(interaction, "Permission Denied", f"{interaction.user.mention} attempted /set_glory_threshold without permission.")
            return

        if threshold < 0:
            await interaction.response.send_message("Threshold must be a positive number.", ephemeral=True)
            return

        timestamp = datetime.now(IST).isoformat()
        success = set_glory_threshold(interaction.channel_id, threshold, str(interaction.user.id), timestamp)
        
        if success:
            await interaction.response.send_message(f"✅ Glory threshold set to {threshold} for this channel.")
            await log_action(interaction, "Glory Threshold Set", f"Set glory threshold to {threshold}")
        else:
            await interaction.response.send_message("Failed to set glory threshold. Please try again.")

    @app_commands.command(name="update_glory", description="Update glory data for players (Commanders only)")
    async def update_glory(self, interaction: discord.Interaction):
        if not is_commander(interaction):
            await interaction.response.send_message("Only Commanders can update glory.", ephemeral=True)
            await log_action(interaction, "Permission Denied", f"{interaction.user.mention} attempted /update_glory without permission.")
            return

        try:
            modal = GloryUpdateModal(self)
            await interaction.response.send_modal(modal)
        except discord.NotFound:
            await interaction.response.send_message("Interaction timed out. Please try the command again.", ephemeral=True)

    @app_commands.command(name="add_glory_exception", description="Add a player to the glory warning exception list")
    @app_commands.describe(uid="Player UID to exempt from glory warnings", reason="Reason for the exception")
    async def add_glory_exception(self, interaction: discord.Interaction, uid: str, reason: str):
        if not is_commander(interaction):
            await interaction.response.send_message("Only Commanders can manage glory exceptions.", ephemeral=True)
            await log_action(interaction, "Permission Denied", f"{interaction.user.mention} attempted /add_glory_exception without permission.")
            return

        try:
            uid_int = int(uid.strip())
        except ValueError:
            await interaction.response.send_message("Invalid UID format. Please provide a numeric UID.", ephemeral=True)
            return

        success = add_glory_exception(interaction.channel_id, uid_int, reason.strip(), str(interaction.user.id))
        if success:
            player_name = get_member_name_by_uid(interaction.channel_id, uid)
            display_name = player_name if player_name else f"UID {uid}"
            await interaction.response.send_message(f"✅ Added {display_name} to glory exception list.\n**Reason:** {reason}")
            await log_action(interaction, "Glory Exception Added", f"{interaction.user.mention} added {display_name} (UID: {uid}) to glory exceptions. Reason: {reason}")
        else:
            await interaction.response.send_message("Failed to add glory exception. Please try again.", ephemeral=True)

    @app_commands.command(name="remove_glory_exception", description="Remove a player from the glory warning exception list")
    @app_commands.describe(uid="Player UID to remove from glory exception list")
    async def remove_glory_exception(self, interaction: discord.Interaction, uid: str):
        if not is_commander(interaction):
            await interaction.response.send_message("Only Commanders can manage glory exceptions.", ephemeral=True)
            await log_action(interaction, "Permission Denied", f"{interaction.user.mention} attempted /remove_glory_exception without permission.")
            return

        try:
            uid_int = int(uid.strip())
        except ValueError:
            await interaction.response.send_message("Invalid UID format. Please provide a numeric UID.", ephemeral=True)
            return

        success = remove_glory_exception(interaction.channel_id, uid_int)
        if success:
            player_name = get_member_name_by_uid(interaction.channel_id, uid)
            display_name = player_name if player_name else f"UID {uid}"
            await interaction.response.send_message(f"✅ Removed {display_name} from glory exception list.")
            await log_action(interaction, "Glory Exception Removed", f"{interaction.user.mention} removed {display_name} (UID: {uid}) from glory exceptions.")
        else:
            await interaction.response.send_message("Player not found in glory exception list or removal failed.", ephemeral=True)

    @app_commands.command(name="list_glory_exceptions", description="List all players exempted from glory warnings")
    async def list_glory_exceptions(self, interaction: discord.Interaction):
        if not is_commander(interaction):
            await interaction.response.send_message("Only Commanders can view glory exceptions.", ephemeral=True)
            await log_action(interaction, "Permission Denied", f"{interaction.user.mention} attempted /list_glory_exceptions without permission.")
            return

        exceptions = get_glory_exceptions(interaction.channel_id)
        if not exceptions:
            await interaction.response.send_message("No glory exceptions configured for this channel.")
            return

        msg = "**Glory Warning Exceptions**\n\n"
        for uid, reason, added_by, timestamp in exceptions:
            player_name = get_member_name_by_uid(interaction.channel_id, str(uid))
            display_name = player_name if player_name else f"UID {uid}"
            msg += f"• **{display_name}** (UID: {uid})\n"
            msg += f"  Reason: {reason}\n"
            msg += f"  Added: {timestamp} IST\n\n"

        if len(msg) > 2000:
            # Split into multiple messages if too long
            parts = []
            current_part = "**Glory Warning Exceptions**\n\n"
            for line in msg.split('\n')[2:]:  # Skip header
                if len(current_part + line + '\n') > 1900:
                    parts.append(current_part)
                    current_part = "**Glory Warning Exceptions (continued)**\n\n" + line + '\n'
                else:
                    current_part += line + '\n'
            if current_part:
                parts.append(current_part)
            
            for part in parts:
                await interaction.followup.send(part)
        else:
            await interaction.response.send_message(msg)


async def setup(bot):
    """Load moderation commands"""
    await bot.add_cog(ModerationCommands(bot))
