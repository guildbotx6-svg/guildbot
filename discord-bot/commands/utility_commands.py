"""Utility Commands"""
import discord
from discord import app_commands
from discord.ext import commands
from helpers import is_commander, set_log_channel_async, get_log_channel_async, safe_send, log_action

class UtilityCommands(commands.Cog):
    """General utility commands"""
    
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="setlogchannel", description="Set the log channel for bot actions (Commanders only)")
    async def setlogchannel(self, interaction: discord.Interaction, channel: discord.TextChannel):
        if not is_commander(interaction):
            await safe_send(interaction, "Only Commanders can set the log channel.", ephemeral=True)
            await log_action(interaction, "Permission Denied", f"{interaction.user.mention} attempted /setlogchannel without permission.")
            return
        await set_log_channel_async(interaction.guild_id, channel.id)
        await safe_send(interaction, f"✅ Log channel set to {channel.mention}", ephemeral=True)
        await log_action(interaction, "Log Channel Updated", f"{interaction.user.mention} set the log channel to {channel.mention}.")

    @app_commands.command(name="getlogchannel", description="Show the current log channel (Commanders only)")
    async def getlogchannel(self, interaction: discord.Interaction):
        if not is_commander(interaction):
            await safe_send(interaction, "Only Commanders can view the log channel.", ephemeral=True)
            await log_action(interaction, "Permission Denied", f"{interaction.user.mention} attempted /getlogchannel without permission.")
            return
        log_channel_id = await get_log_channel_async(interaction.guild_id)
        if not log_channel_id:
            await safe_send(interaction, "No log channel set yet. Use `/setlogchannel` to set one.", ephemeral=True)
            await log_action(interaction, "Get Log Channel", f"{interaction.user.mention} checked log channel: Not set.")
        else:
            log_channel = interaction.guild.get_channel(log_channel_id)
            if log_channel:
                await safe_send(interaction, f"📋 Current log channel: {log_channel.mention}", ephemeral=True)
                await log_action(interaction, "Get Log Channel", f"{interaction.user.mention} viewed log channel: {log_channel.mention}")
            else:
                await safe_send(interaction, "Log channel no longer exists. Use `/setlogchannel` to set a new one.", ephemeral=True)
                await log_action(interaction, "Get Log Channel", f"{interaction.user.mention} checked log channel: Channel no longer exists.")

    @app_commands.command(name="pingdb", description="Check database connection status")
    async def pingdb(self, interaction: discord.Interaction):
        """Utility: Ping DB status"""
        if not is_commander(interaction):
            await safe_send(interaction, "You don't have permission.", ephemeral=True)
            await log_action(interaction, "Permission Denied", f"{interaction.user.mention} attempted /pingdb without permission.")
            return
        await safe_send(interaction, "Database is connected (SQLite).", ephemeral=True)
        await log_action(interaction, "Database Ping", f"{interaction.user.mention} pinged the database - Connected.")
    @app_commands.command(name="help", description="Show available commands")
    async def help(self, interaction: discord.Interaction):
        if not is_commander(interaction):
            await safe_send(interaction, "You don't have permission.", ephemeral=True)
            return

        commands = [
            "**📋 Member Commands**",
            "  • `/setguild <text>` – Store guild list",
            "  • `/setbound <text>` – Store bound list",
            "  • `/notbind` – Guild members not bound",
            "  • `/missing_player` – Bound members not in guild",
            "  • `/showdata` – Preview lists",
            "  • `/update <type> <id> <name>` – Update player name",
            "  • `/clear` – Reset lists",
            "  • `/count` – Show counts",
            "  • `/exportdiff` – Export guild-only members (CSV)",
            "",
            "**⚔️ Guild Reconciliation Commands**",
            "  • `/currentmembers` – Show current guild members",
            "  • `/guildupdates` – Update guild and show changes",
            "  • `/clearguild` – Clear guild data (Head Commander only)",
            "  • `/editguild <text>` – Edit guild members (Head Commander only)",
            "  • `/guildhistory` – Show guild change history",
            "  • `/resethistory` – Clear history (Head Commander only)",
            "  • `/export <type> <format>` – Export guild data (CSV/JSON/TXT)",
            "  • `/exportall` – Export all guild data as ZIP",
            "  • `/export <type> <format>` – Export guild data",
            "  • `/exportall` – Export all data as ZIP",
            "  • `/addheadcommander <user>` – Add Head Commander role (Admin only)",
            "  • `/removeheadcommander <user>` – Remove Head Commander role (Admin only)",
            "  • `/listheadcommanders` – List all Head Commanders",
            "",
            "**👤 Commander Commands**",
            "  • `/addcommander <user>` – Promote user",
            "  • `/removecommander <user>` – Demote user",
            "  • `/listcommanders` – List all commanders",
            "",
            "**🔐 Channel Commands**",
            "  • `/lockchannel` – Lock channel",
            "  • `/unlockchannel` – Unlock channel",
            "",
            "**⚠️ Moderation Commands**",
            "  • `/warnuid` – Warn players by UID (modal)",
            "  • `/warnings <uid>` – View warnings for UID",
            "  • `/listwarnings` – List all warned members",
            "  • `/clearwarnings <uid>` – Clear warnings (Admin)",
            "  • `/check_glory` – Check stored glory levels below threshold",
            "  • `/view_glory` – View all glory levels",
            "  • `/glory_warn` – Auto-warn players below glory threshold (resets next Monday 00:00 IST)",
            "  • `/set_glory_threshold <threshold>` – Set glory threshold",
            "  • `/update_glory` – Update glory data (modal)",
            "  • `/add_glory_exception <uid> <reason>` – Exempt player from glory warnings",
            "  • `/remove_glory_exception <uid>` – Remove player from glory exception list",
            "  • `/list_glory_exceptions` – View all glory exception players",
            "  • `/mute <user>` – Mute user",
            "  • `/unmute <user>` – Unmute user",
            "",
            "**🧹 Cleanup Commands**",
            "  • `/prune <amount>` – Delete messages",
            "  • `/pruneuser <user> <amount>` – Delete user messages",
            "",
            "**📊 Logging Commands**",
            "  • `/setlogchannel <channel>` – Set log channel",
            "  • `/getlogchannel` – View log channel",
        ]

        await safe_send(interaction, "**Available Commands:**\n" + "\n".join(commands))


async def setup(bot):
    """Load utility commands"""
    await bot.add_cog(UtilityCommands(bot))
