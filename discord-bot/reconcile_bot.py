"""Discord Bot - Main Entry Point"""
import os
import sys
import discord
from discord.ext import commands
import re
from dotenv import load_dotenv

# Ensure root emits this folder in module search path so cogs can import helpers.
sys.path.append(os.path.abspath(os.path.dirname(__file__)))

# Load environment variables from .env file
load_dotenv()

TOKEN = os.getenv("TOKEN")
GUILD_ID = os.getenv("GUILD_ID")  # optional for instant guild-level slash command registration

class MyBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True
        super().__init__(command_prefix="!", intents=intents)
        self.owner_id = 1304326261241413664  # Set bot owner ID
        self.ID_RE = re.compile(r"\b(\d{6,20})\b")

    async def setup_hook(self):
        """Load all command cogs at startup"""
        # Load cogs from commands folder
        await self.load_cog('commands.member_commands')
        await self.load_cog('commands.commander_commands')
        await self.load_cog('commands.channel_commands')
        await self.load_cog('commands.moderation_commands')
        await self.load_cog('commands.cleanup_commands')
        await self.load_cog('commands.utility_commands')
        await self.load_cog('commands.reconcile_bot')
        
        # Sync commands (guild-specific if configured, otherwise global)
        if GUILD_ID:
            guild_obj = discord.Object(id=int(GUILD_ID))
            await self.tree.sync(guild=guild_obj)
            print(f"✅ Synced {len(self.tree._get_all_commands())} commands to guild {GUILD_ID}")
        else:
            await self.tree.sync()
            print(f"✅ Synced {len(self.tree._get_all_commands())} commands globally")

        # Print command list for debug
        all_names = [cmd.name for cmd in self.tree.walk_commands()]
        print("🧩 Registered slash commands:", ", ".join(sorted(all_names)))

    async def load_cog(self, cog_name):
        """Load a cog with error handling"""
        try:
            await self.load_extension(cog_name)
            print(f"✅ Loaded {cog_name}")
        except Exception as e:
            print(f"❌ Failed to load {cog_name}: {e}")

bot = MyBot()

@bot.event
async def on_ready():
    print(f"✅ Bot is ready. Logged in as {bot.user}")
    print(f"🎮 Active in {len(bot.guilds)} guild(s)")

@bot.event
async def on_app_command_error(interaction: discord.Interaction, error):
    # Keep app command errors from crashing the bot and provide debug output.
    if isinstance(error, discord.NotFound):
        print("⚠️ App command failed: interaction not found (likely timed out).")
        return
    if isinstance(error, discord.HTTPException) and getattr(error, 'code', None) == 40060:
        print("⚠️ App command failed: interaction already acknowledged.")
        return
    print(f"❌ App command error: {error}")
    try:
        from helpers import safe_send
        await safe_send(interaction, "An error occurred while processing your command. Please try again later.", ephemeral=True)
    except Exception:
        pass


def main():
    """Start the bot"""
    if not TOKEN:
        print("❌ ERROR: TOKEN environment variable not set!")
        print("   Please set TOKEN in your .env file")
        return
    
    try:
        bot.run(TOKEN)
    except Exception as e:
        print(f"❌ Bot crashed: {e}")

if __name__ == "__main__":
    main()
