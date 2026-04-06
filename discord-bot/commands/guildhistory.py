import discord
from discord.ext import commands
import sqlite3, json, os
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv

# Load environment variables from .env
load_dotenv()
BOT_TOKEN = os.getenv("TOKEN")

# IST timezone constant
IST = timezone(timedelta(hours=5, minutes=30))

intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)

# Connect to SQLite database
conn = sqlite3.connect("guild.db")
cursor = conn.cursor()

# Create tables if they don't exist
cursor.execute("""
CREATE TABLE IF NOT EXISTS guild_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    channel_id INTEGER,
    timestamp TEXT,
    members TEXT
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS guild_changes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    channel_id INTEGER,
    timestamp TEXT,
    joined TEXT,
    left TEXT
)
""")
conn.commit()

# Helper: parse text into {uid: name}
def parse_member_lines(text: str):
    members = {}
    for line in text.splitlines():
        parts = line.strip().split()
        if len(parts) >= 2:
            name = " ".join(parts[:-1])
            uid = parts[-1]
            members[uid] = name
    return members

# Command: initialize guild data
@bot.tree.command(name="initguild", description="Add initial guild data")
async def initguild(interaction: discord.Interaction, text: str):
    members = parse_member_lines(text)
    cursor.execute(
        "INSERT INTO guild_snapshots (channel_id, timestamp, members) VALUES (?, ?, ?)",
        (interaction.channel_id, str(datetime.now(IST)), json.dumps(members))
    )
    conn.commit()
    await interaction.response.send_message(f"Initial guild snapshot saved with {len(members)} members.")

# Command: check updates
@bot.tree.command(name="checkupdates", description="Check guild updates")
async def checkupdates(interaction: discord.Interaction, text: str):
    current_members = parse_member_lines(text)

    # Get last snapshot
    cursor.execute(
        "SELECT members FROM guild_snapshots WHERE channel_id=? ORDER BY id DESC LIMIT 1",
        (interaction.channel_id,)
    )
    row = cursor.fetchone()

    joined, left = [], []
    if row:
        old_members = json.loads(row[0])
        joined = [name for uid, name in current_members.items() if uid not in old_members]
        left = [name for uid, name in old_members.items() if uid not in current_members]

    # Save new snapshot
    cursor.execute(
        "INSERT INTO guild_snapshots (channel_id, timestamp, members) VALUES (?, ?, ?)",
        (interaction.channel_id, str(datetime.now(IST)), json.dumps(current_members))
    )
    conn.commit()

    # Log changes
    cursor.execute(
        "INSERT INTO guild_changes (channel_id, timestamp, joined, left) VALUES (?, ?, ?, ?)",
        (interaction.channel_id, str(datetime.now(IST)), json.dumps(joined), json.dumps(left))
    )
    conn.commit()

    # Build response
    msg = "**Guild Update Log**\n"
    if joined:
        msg += f"✅ Joined: {', '.join(joined)}\n"
    if left:
        msg += f"❌ Left: {', '.join(left)}\n"
    if not joined and not left:
        msg += "No changes since last snapshot."

    await interaction.response.send_message(msg)

# Run your bot using token from .env
bot.run(BOT_TOKEN)