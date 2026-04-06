"""Message Cleanup Commands"""
import discord
from discord import app_commands
from discord.ext import commands
from helpers import log_action, safe_send, is_commander, is_commander

class CleanupCommands(commands.Cog):
    """Commands for message management and cleanup"""
    
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="prune", description="Delete a number of recent messages")
    async def prune(self, interaction: discord.Interaction, amount: int):
        try:
            if not interaction.response.is_done():
                await interaction.response.defer(ephemeral=True)
        except discord.NotFound:
            print("⚠️ prune: interaction unknown/expired while deferring.")
        except discord.HTTPException as e:
            if getattr(e, 'code', None) == 40060:
                print("⚠️ prune: interaction already acknowledged while deferring.")
            else:
                print(f"⚠️ prune: HTTPException while deferring: {e}")

        if not is_commander(interaction):
            await safe_send(interaction, "You don't have permission to prune messages.", ephemeral=True)
            await log_action(interaction, "Permission Denied", f"{interaction.user.mention} attempted /prune without permission.")
            return
        if amount < 1 or amount > 100:
            await safe_send(interaction, "You can only delete between 1 and 100 messages.", ephemeral=True)
            return

        deleted = await interaction.channel.purge(limit=amount)
        await safe_send(interaction, f"🧹 Deleted {len(deleted)} messages.", ephemeral=True)
        await log_action(interaction, "Messages Pruned", f"Deleted {len(deleted)} messages in {interaction.channel.mention}")

    @app_commands.command(name="pruneuser", description="Delete recent messages from a specific user")
    async def pruneuser(self, interaction: discord.Interaction, member: discord.Member, amount: int):
        try:
            if not interaction.response.is_done():
                await interaction.response.defer(ephemeral=True)
        except discord.NotFound:
            print("⚠️ pruneuser: interaction unknown/expired while deferring.")
        except discord.HTTPException as e:
            if getattr(e, 'code', None) == 40060:
                print("⚠️ pruneuser: interaction already acknowledged while deferring.")
            else:
                print(f"⚠️ pruneuser: HTTPException while deferring: {e}")

        if not is_commander(interaction):
            await safe_send(interaction, "You don't have permission to prune messages.", ephemeral=True)
            await log_action(interaction, "Permission Denied", f"{interaction.user.mention} attempted /pruneuser without permission.")
            return
        if amount < 1 or amount > 100:
            await safe_send(interaction, "You can only delete between 1 and 100 messages.", ephemeral=True)
            return
        deleted = await interaction.channel.purge(limit=amount, check=lambda m: m.author == member)
        await safe_send(interaction, f"🧹 Deleted {len(deleted)} messages from {member.display_name}.", ephemeral=True)
        await log_action(interaction, "User Messages Pruned", f"Deleted {len(deleted)} messages from {member.mention} in {interaction.channel.mention}")


async def setup(bot):
    """Load cleanup commands"""
    await bot.add_cog(CleanupCommands(bot))
