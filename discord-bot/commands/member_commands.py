"""Guild & Bound Member List Commands"""
import os
import sys
import discord
from discord import app_commands
from discord.ext import commands
import io, csv

# Ensure root folder is importable so helpers can be located from cogs
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from helpers import get_channel_data_async, update_channel_data_async, clear_channel_data_async, is_commander, parse_member_lines, safe_send, log_action

class MemberCommands(commands.Cog):
    """Commands for managing guild and bound member lists"""
    
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="setguild", description="Store guild member list")
    async def setguild(self, interaction: discord.Interaction, text: str):
        if not is_commander(interaction):
            await safe_send(interaction, "You don't have permission.", ephemeral=True)
            await log_action(interaction, "Permission Denied", f"{interaction.user.mention} attempted /setguild without permission.")
            return
        channel_id = interaction.channel_id
        guild_members = parse_member_lines(text, interaction.client.ID_RE)
        await update_channel_data_async(channel_id, guild=guild_members)
        await safe_send(interaction, f"Stored {len(guild_members)} guild members.")
        await log_action(interaction, "Guild Members Set", f"{interaction.user.mention} stored {len(guild_members)} guild members in {interaction.channel.mention}.")

    @app_commands.command(name="setbound", description="Store bound member list")
    async def setbound(self, interaction: discord.Interaction, text: str):
        if not is_commander(interaction):
            await safe_send(interaction, "You don't have permission.", ephemeral=True)
            await log_action(interaction, "Permission Denied", f"{interaction.user.mention} attempted /setbound without permission.")
            return
        channel_id = interaction.channel_id
        bound_members = parse_member_lines(text, interaction.client.ID_RE)
        await update_channel_data_async(channel_id, bound=bound_members)
        await safe_send(interaction, f"Stored {len(bound_members)} bound members.")
        await log_action(interaction, "Bound Members Set", f"{interaction.user.mention} stored {len(bound_members)} bound members in {interaction.channel.mention}.")

    @app_commands.command(name="notbind", description="Show guild members not yet bound")
    async def notbind(self, interaction: discord.Interaction):
        if not is_commander(interaction):
            await safe_send(interaction, "You don't have permission.", ephemeral=True)
            await log_action(interaction, "Permission Denied", f"{interaction.user.mention} attempted /notbind without permission.")
            return
        channel_id = interaction.channel_id
        guild, bound = await get_channel_data_async(channel_id)
        if not guild or not bound:
            await safe_send(interaction, "Use /setguild and /setbound first.")
            return
        rows = [(guild[i], i) for i in guild if i not in bound]
        if not rows:
            await safe_send(interaction, "All guild members are bound.")
            await log_action(interaction, "Not Bind Query", f"{interaction.user.mention} queried notbind: All members are bound.")
            return
        csv_text = "Display Name,ID\n" + "\n".join(f"{n},{i}" for n,i in rows)
        await safe_send(interaction, f"**Guild members not bound:**\n```csv\n{csv_text}\n```")
        await log_action(interaction, "Not Bind Query", f"{interaction.user.mention} queried notbind: {len(rows)} unbound members found.")

    @app_commands.command(name="missing_player", description="Show bound members not in guild")
    async def missing_player(self, interaction: discord.Interaction):
        if not is_commander(interaction):
            await safe_send(interaction, "You don't have permission.", ephemeral=True)
            await log_action(interaction, "Permission Denied", f"{interaction.user.mention} attempted /missing_player without permission.")
            return
        channel_id = interaction.channel_id
        guild, bound = await get_channel_data_async(channel_id)
        if not guild or not bound:
            await safe_send(interaction, "Use /setguild and /setbound first.")
            return
        rows = [(bound[i], i) for i in bound if i not in guild]
        if not rows:
            await safe_send(interaction, "All bound members are in the guild.")
            await log_action(interaction, "Missing Player Query", f"{interaction.user.mention} queried missing_player: All bound members are in guild.")
            return
        csv_text = "Display Name,ID\n" + "\n".join(f"{n},{i}" for n,i in rows)
        await safe_send(interaction, f"**Bound members not in guild:**\n```csv\n{csv_text}\n```")
        await log_action(interaction, "Missing Player Query", f"{interaction.user.mention} queried missing_player: {len(rows)} missing members found.")

    @app_commands.command(name="showdata", description="Show stored guild and bound lists")
    async def showdata(self, interaction: discord.Interaction):
        if not is_commander(interaction):
            await safe_send(interaction, "You don't have permission.", ephemeral=True)
            await log_action(interaction, "Permission Denied", f"{interaction.user.mention} attempted /showdata without permission.")
            return
        channel_id = interaction.channel_id
        guild, bound = await get_channel_data_async(channel_id)
        if not guild and not bound:
            await safe_send(interaction, "No data stored yet. Use /setguild and /setbound first.")
            return
        guild_text = "\n".join([f"{n},{i}" for i,n in guild.items()][:10]) or "No guild members stored."
        bound_text = "\n".join([f"{n},{i}" for i,n in bound.items()][:10]) or "No bound members stored."
        await safe_send(interaction,
            f"**Guild list (first 10):**\n```csv\n{guild_text}\n```\n"
            f"**Bound list (first 10):**\n```csv\n{bound_text}\n```"
        )
        await log_action(interaction, "Show Data Query", f"{interaction.user.mention} viewed guild and bound data. Guild: {len(guild)} members, Bound: {len(bound)} members.")

    @app_commands.command(name="update", description="Update a player's name in guild or bound list")
    async def update(self, interaction: discord.Interaction, list_type: str, player_id: str, new_name: str):
        if not is_commander(interaction):
            await safe_send(interaction, "You don't have permission.", ephemeral=True)
            await log_action(interaction, "Permission Denied", f"{interaction.user.mention} attempted /update without permission.")
            return
        channel_id = interaction.channel_id
        guild, bound = await get_channel_data_async(channel_id)
        if not guild and not bound:
            await safe_send(interaction, "No data stored yet. Use /setguild and /setbound first.")
            return
        if list_type.lower() not in ["guild", "bound"]:
            await safe_send(interaction, "Invalid list type. Use 'guild' or 'bound'.", ephemeral=True)
            return
        target_list = guild if list_type.lower() == "guild" else bound
        if player_id not in target_list:
            await safe_send(interaction, f"Player ID {player_id} not found in {list_type} list.", ephemeral=True)
            return
        old_name = target_list[player_id]
        target_list[player_id] = new_name
        if list_type.lower() == "guild":
            await update_channel_data_async(channel_id, guild=guild)
        else:
            await update_channel_data_async(channel_id, bound=bound)
        await safe_send(interaction, f"Updated {list_type} list: ID {player_id} → {new_name}")
        await log_action(interaction, "Member Updated", f"{interaction.user.mention} updated {list_type} member ID {player_id}: '{old_name}' → '{new_name}'.")

    @app_commands.command(name="clear", description="Clear stored guild and bound lists")
    async def clear(self, interaction: discord.Interaction):
        if not is_commander(interaction):
            await safe_send(interaction, "You don't have permission.", ephemeral=True)
            await log_action(interaction, "Permission Denied", f"{interaction.user.mention} attempted /clear without permission.")
            return
        channel_id = interaction.channel_id
        await clear_channel_data_async(channel_id)
        await safe_send(interaction, "Cleared guild and bound lists for this channel.")
        await log_action(interaction, "Member Data Cleared", f"{interaction.user.mention} cleared all member data in {interaction.channel.mention}.")

    @app_commands.command(name="count", description="Show counts of guild and bound lists")
    async def count(self, interaction: discord.Interaction):
        if not is_commander(interaction):
            await safe_send(interaction, "You don't have permission.", ephemeral=True)
            await log_action(interaction, "Permission Denied", f"{interaction.user.mention} attempted /count without permission.")
            return
        channel_id = interaction.channel_id
        guild, bound = await get_channel_data_async(channel_id)
        guild_count = len(guild)
        bound_count = len(bound)
        await safe_send(interaction, f"Guild list: {guild_count} members\nBound list: {bound_count} members")
        await log_action(interaction, "Count Query", f"{interaction.user.mention} queried member counts. Guild: {guild_count}, Bound: {bound_count}.")

    @app_commands.command(name="exportdiff", description="Export guild-only members as CSV (members in guild but not bound)")
    async def exportdiff(self, interaction: discord.Interaction):
        if not is_commander(interaction):
            await safe_send(interaction, "You don't have permission.", ephemeral=True)
            await log_action(interaction, "Permission Denied", f"{interaction.user.mention} attempted /export without permission.")
            return
        channel_id = interaction.channel_id
        guild, bound = await get_channel_data_async(channel_id)
        rows = [(guild[i], i) for i in guild if i not in bound]
        if not rows:
            await safe_send(interaction, "No differences found.")
            await log_action(interaction, "Member Export", f"{interaction.user.mention} exported member data: No differences found.")
            return
        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow(["Display Name","ID"])
        for name,id_ in rows:
            writer.writerow([name,id_])
        file = discord.File(io.BytesIO(buf.getvalue().encode("utf-8")), filename="guild_only.csv")
        await interaction.response.send_message("Here's the CSV file:", file=file)
        await log_action(interaction, "Member Export", f"{interaction.user.mention} exported {len(rows)} guild-only members as CSV.")


async def setup(bot):
    """Load member commands"""
    await bot.add_cog(MemberCommands(bot))
