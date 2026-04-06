"""Channel Control Commands"""
import discord
from discord import app_commands
from discord.ext import commands
from helpers import log_action, is_commander, is_commander

class ChannelCommands(commands.Cog):
    """Commands for managing channel permissions"""
    
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="lockchannel", description="Lock the current channel (Commanders only)")
    async def lockchannel(self, interaction: discord.Interaction):
        await interaction.response.defer()
        
        if not is_commander(interaction):
            await interaction.followup.send("Only Commanders can lock channels.", ephemeral=True)
            await log_action(interaction, "Permission Denied", f"{interaction.user.mention} attempted /lockchannel without permission.")
            return
        overwrite = interaction.channel.overwrites_for(interaction.guild.default_role)
        overwrite.send_messages = False
        await interaction.channel.set_permissions(interaction.guild.default_role, overwrite=overwrite)
        await interaction.followup.send("🔒 Channel locked.")
        await log_action(interaction, "Channel Locked", f"{interaction.channel.mention} has been locked.")

    @app_commands.command(name="unlockchannel", description="Unlock the current channel (Commanders only)")
    async def unlockchannel(self, interaction: discord.Interaction):
        await interaction.response.defer()
        
        if not is_commander(interaction):
            await interaction.followup.send("Only Commanders can unlock channels.", ephemeral=True)
            await log_action(interaction, "Permission Denied", f"{interaction.user.mention} attempted /unlockchannel without permission.")
            return
        overwrite = interaction.channel.overwrites_for(interaction.guild.default_role)
        overwrite.send_messages = True
        await interaction.channel.set_permissions(interaction.guild.default_role, overwrite=overwrite)
        await interaction.followup.send("🔓 Channel unlocked.")
        await log_action(interaction, "Channel Unlocked", f"{interaction.channel.mention} has been unlocked.")


async def setup(bot):
    """Load channel commands"""
    await bot.add_cog(ChannelCommands(bot))
