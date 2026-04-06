"""Shared helper functions and utilities"""
import asyncio
import discord
import sqlite3
import json
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# SQLite setup - local file database
DB_FILE = "discord_bot.db"

# Initialize SQLite database
def init_db():
    """Initialize SQLite database and create tables"""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    # Create channel_data table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS channel_data (
            channel_id TEXT PRIMARY KEY,
            guild_data TEXT,
            bound_data TEXT
        )
    ''')

    # Create log_settings table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS log_settings (
            guild_id TEXT PRIMARY KEY,
            log_channel_id TEXT
        )
    ''')

    # Created warning records table for UID-based moderation
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS warnings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            guild_id TEXT,
            channel_id TEXT,
            uid TEXT,
            reason TEXT,
            warned_by TEXT,
            timestamp TEXT
        )
    ''')

    # Create ban records table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS bans (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            guild_id TEXT,
            channel_id TEXT,
            uid TEXT,
            player_name TEXT,
            reason TEXT,
            whatsapp TEXT,
            banned_by TEXT,
            timestamp TEXT
        )
    ''')

    # Create universal global ban list for all guilds
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS global_bans (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            uid TEXT UNIQUE,
            player_name TEXT,
            reason TEXT,
            whatsapp TEXT,
            banned_by TEXT,
            timestamp TEXT,
            source_guild_id TEXT
        )
    ''')

    # Create glory records table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS glory (
            channel_id TEXT,
            uid TEXT,
            glory INTEGER,
            updated_by TEXT,
            timestamp TEXT,
            PRIMARY KEY (channel_id, uid)
        )
    ''')

    # Create glory settings table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS glory_settings (
            channel_id TEXT PRIMARY KEY,
            threshold INTEGER DEFAULT 7000,
            updated_by TEXT,
            timestamp TEXT
        )
    ''')

    # Create glory exceptions table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS glory_exceptions (
            channel_id TEXT,
            uid TEXT,
            added_by TEXT,
            timestamp TEXT,
            PRIMARY KEY (channel_id, uid)
        )
    ''')

    # Migration support for older schema without channel_id (warnings/bans)
    cursor.execute("PRAGMA table_info(warnings)")
    columns = [row[1] for row in cursor.fetchall()]
    if "channel_id" not in columns:
        try:
            cursor.execute("ALTER TABLE warnings ADD COLUMN channel_id TEXT")
            cursor.execute("UPDATE warnings SET channel_id = guild_id WHERE channel_id IS NULL OR channel_id = ''")
            print("Migrated warnings table to include channel_id")
        except Exception as e:
            print(f"Migration note: could not alter warnings table: {e}")

    cursor.execute("PRAGMA table_info(bans)")
    ban_columns = [row[1] for row in cursor.fetchall()]
    if "channel_id" not in ban_columns:
        try:
            cursor.execute("ALTER TABLE bans ADD COLUMN channel_id TEXT")
            cursor.execute("UPDATE bans SET channel_id = guild_id WHERE channel_id IS NULL OR channel_id = ''")
            print("Migrated bans table to include channel_id")
        except Exception as e:
            print(f"Migration note: could not alter bans table: {e}")

    conn.commit()
    conn.close()

# Initialize database on import
init_db()
print("Connected to local SQLite database")

# SQLite helper functions
def get_channel_data(channel_id):
    """Retrieve guild and bound data for a channel"""
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT guild_data, bound_data FROM channel_data WHERE channel_id = ?",
            (str(channel_id),)
        )
        result = cursor.fetchone()
        conn.close()

        if result:
            guild = json.loads(result[0]) if result[0] else {}
            bound = json.loads(result[1]) if result[1] else {}
            return guild, bound
        return {}, {}
    except Exception as e:
        print(f"Could not read channel data for {channel_id}: {e}")
        return {}, {}


def update_channel_data(channel_id, guild=None, bound=None):
    """Update guild and/or bound data for a channel"""
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()

        # Get existing data
        cursor.execute(
            "SELECT guild_data, bound_data FROM channel_data WHERE channel_id = ?",
            (str(channel_id),)
        )
        result = cursor.fetchone()

        current_guild = json.loads(result[0]) if result and result[0] else {}
        current_bound = json.loads(result[1]) if result and result[1] else {}

        # Update with new data
        if guild is not None:
            current_guild = guild
        if bound is not None:
            current_bound = bound

        # Save back to database
        cursor.execute(
            "INSERT OR REPLACE INTO channel_data (channel_id, guild_data, bound_data) VALUES (?, ?, ?)",
            (str(channel_id), json.dumps(current_guild), json.dumps(current_bound))
        )

        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Could not update channel data for {channel_id}: {e}")


def clear_channel_data(channel_id):
    """Clear all data for a channel"""
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE channel_data SET guild_data = ?, bound_data = ? WHERE channel_id = ?",
            (json.dumps({}), json.dumps({}), str(channel_id))
        )
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Could not clear channel data for {channel_id}: {e}")


async def get_channel_data_async(channel_id):
    """Async wrapper around get_channel_data"""
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, get_channel_data, channel_id)


async def update_channel_data_async(channel_id, guild=None, bound=None):
    """Async wrapper around update_channel_data"""
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, update_channel_data, channel_id, guild, bound)


async def clear_channel_data_async(channel_id):
    """Async wrapper around clear_channel_data"""
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, clear_channel_data, channel_id)

# Logging helper functions

async def safe_send(interaction: discord.Interaction, content: str, *, ephemeral: bool = False):
    """Send message or follow-up safely for an interaction."""
    try:
        if interaction.response.is_done():
            await interaction.followup.send(content, ephemeral=ephemeral)
        else:
            await interaction.response.send_message(content, ephemeral=ephemeral)
    except discord.NotFound:
        print("Interaction stale or unknown: cannot send message.")
    except discord.HTTPException as e:
        if getattr(e, 'code', None) == 40060:
            print("Interaction already acknowledged: skipping message.")
        else:
            print(f"HTTPException while sending response: {e}")
    except Exception as e:
        print(f"Unexpected exception while sending response: {e}")


def get_log_channel(guild_id):
    """Get the log channel ID for a guild (blocking)."""
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT log_channel_id FROM log_settings WHERE guild_id = ?",
            (str(guild_id),)
        )
        result = cursor.fetchone()
        conn.close()
        # Convert to int if result exists, since Discord API expects int
        return int(result[0]) if result else None
    except Exception as e:
        print(f"Could not get log channel for guild {guild_id}: {e}")
        return None


def set_log_channel(guild_id, channel_id):
    """Set the log channel for a guild (blocking)."""
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute(
            "INSERT OR REPLACE INTO log_settings (guild_id, log_channel_id) VALUES (?, ?)",
            (str(guild_id), str(channel_id))
        )
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Could not set log channel for guild {guild_id}: {e}")


async def get_log_channel_async(guild_id):
    """Get the log channel ID for a guild in a thread pool."""
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, get_log_channel, guild_id)


async def set_log_channel_async(guild_id, channel_id):
    """Set the log channel for a guild in a thread pool."""
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, set_log_channel, guild_id, channel_id)


def add_warning(channel_id, uid, reason, warned_by, timestamp, guild_id=None):
    """Add a UID warning record for a channel."""
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        guild_value = str(guild_id) if guild_id is not None else ""
        cursor.execute(
            "INSERT INTO warnings (guild_id, channel_id, uid, reason, warned_by, timestamp) VALUES (?, ?, ?, ?, ?, ?)",
            (guild_value, str(channel_id), str(uid), reason, warned_by, timestamp)
        )
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"Could not add warning for {uid} in channel {channel_id}: {e}")
        return False


def get_warnings(channel_id, uid):
    """Retrieve all warnings for a UID in a channel."""
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, reason, warned_by, timestamp FROM warnings WHERE channel_id = ? AND uid = ? ORDER BY id DESC",
            (str(channel_id), str(uid))
        )
        rows = cursor.fetchall()
        conn.close()
        return rows
    except Exception as e:
        print(f"Could not fetch warnings for {uid} in channel {channel_id}: {e}")
        return []


def clear_warnings(channel_id, uid):
    """Clear warnings for a specific UID in a channel."""
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute(
            "DELETE FROM warnings WHERE channel_id = ? AND uid = ?",
            (str(channel_id), str(uid))
        )
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"Could not clear warnings for {uid} in channel {channel_id}: {e}")
        return False


def clear_all_warnings(channel_id):
    """Clear all warnings in a channel."""
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute(
            "DELETE FROM warnings WHERE channel_id = ?",
            (str(channel_id),)
        )
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"Could not clear all warnings in channel {channel_id}: {e}")
        return False


def get_all_warned_members(channel_id):
    """Retrieve all warned members in a channel with their warning counts."""
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT uid, COUNT(*) as warning_count FROM warnings WHERE channel_id = ? GROUP BY uid ORDER BY warning_count DESC",
            (str(channel_id),)
        )
        rows = cursor.fetchall()
        conn.close()
        return rows
    except Exception as e:
        print(f"Could not fetch warned members for channel {channel_id}: {e}")
        return []


def get_member_name_by_uid(channel_id, uid):
    """Get a player's name from the reconcile guild_state database by channel and UID."""
    try:
        conn = sqlite3.connect("guild.db")
        cursor = conn.cursor()
        cursor.execute("SELECT members FROM guild_state WHERE channel_id = ?", (channel_id,))
        row = cursor.fetchone()
        conn.close()

        if not row or not row[0]:
            return None

        members = json.loads(row[0])
        # JSON object keys are strings, so resolve both string and integer forms for compatibility
        if str(uid).isdigit():
            return members.get(str(uid)) or members.get(int(uid))
        return members.get(uid)
    except Exception as e:
        print(f"Could not resolve UID {uid} for channel {channel_id}: {e}")
        return None


def add_ban(channel_id, uid, player_name, reason, whatsapp, banned_by, timestamp, guild_id=None, global_ban=False):
    """Add a ban entry for a channel."""
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        guild_value = str(guild_id) if guild_id is not None else ""
        cursor.execute(
            "INSERT INTO bans (guild_id, channel_id, uid, player_name, reason, whatsapp, banned_by, timestamp) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (guild_value, str(channel_id), str(uid), player_name, reason, whatsapp, banned_by, timestamp)
        )
        conn.commit()
        conn.close()
        if global_ban:
            add_global_ban(uid, player_name, reason, whatsapp, banned_by, timestamp, source_guild_id=guild_id)
        return True
    except Exception as e:
        print(f"Could not add ban for {uid} in channel {channel_id}: {e}")
        return False


def get_bans(channel_id):
    """Retrieve all bans for a channel."""
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, uid, player_name, reason, whatsapp, banned_by, timestamp FROM bans WHERE channel_id = ? ORDER BY id DESC",
            (str(channel_id),)
        )
        rows = cursor.fetchall()
        conn.close()
        return rows
    except Exception as e:
        print(f"Could not fetch bans for channel {channel_id}: {e}")
        return []


def get_ban(channel_id, uid):
    """Get a ban record for a specific UID in a channel."""
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, uid, player_name, reason, whatsapp, banned_by, timestamp FROM bans WHERE channel_id = ? AND uid = ? ORDER BY id DESC",
            (str(channel_id), str(uid))
        )
        row = cursor.fetchone()
        conn.close()
        return row
    except Exception as e:
        print(f"Could not fetch ban for {uid} in channel {channel_id}: {e}")
        return None


def remove_ban(channel_id, uid):
    """Remove a ban for a UID in a channel."""
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute(
            "DELETE FROM bans WHERE channel_id = ? AND uid = ?",
            (str(channel_id), str(uid))
        )
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"Could not remove ban for {uid} in channel {channel_id}: {e}")
        return False


def clear_bans(channel_id):
    """Clear all bans in a channel."""
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute(
            "DELETE FROM bans WHERE channel_id = ?",
            (str(channel_id),)
        )
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"Could not clear bans for channel {channel_id}: {e}")
        return False


def get_banned_members(channel_id):
    """Retrieve all banned members for a channel."""
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT uid, player_name, reason, whatsapp, banned_by, timestamp FROM bans WHERE channel_id = ? ORDER BY id DESC",
            (str(channel_id),)
        )
        rows = cursor.fetchall()
        conn.close()
        return rows
    except Exception as e:
        print(f"Could not fetch banned members for channel {channel_id}: {e}")
        return []


def add_global_ban(uid, player_name, reason, whatsapp, banned_by, timestamp, source_guild_id=None):
    """Add (or update) a universal ban across all guilds."""
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        source_value = str(source_guild_id) if source_guild_id is not None else ""
        cursor.execute(
            "INSERT OR REPLACE INTO global_bans (uid, player_name, reason, whatsapp, banned_by, timestamp, source_guild_id) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (str(uid), player_name, reason, whatsapp, banned_by, timestamp, source_value)
        )
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"Could not add global ban for {uid}: {e}")
        return False


def get_global_bans():
    """Retrieve all global bans."""
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT uid, player_name, reason, whatsapp, banned_by, timestamp, source_guild_id FROM global_bans ORDER BY id DESC"
        )
        rows = cursor.fetchall()
        conn.close()
        return rows
    except Exception as e:
        print(f"Could not fetch global bans: {e}")
        return []


def get_global_ban(uid):
    """Retrieve a global ban entry by UID."""
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT uid, player_name, reason, whatsapp, banned_by, timestamp, source_guild_id FROM global_bans WHERE uid = ?",
            (str(uid),)
        )
        row = cursor.fetchone()
        conn.close()
        return row
    except Exception as e:
        print(f"Could not fetch global ban for {uid}: {e}")
        return None


def remove_global_ban(uid):
    """Remove a specific UID from the global ban list."""
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute(
            "DELETE FROM global_bans WHERE uid = ?",
            (str(uid),)
        )
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"Could not remove global ban for {uid}: {e}")
        return False


def clear_global_bans():
    """Clear all global bans."""
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM global_bans")
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"Could not clear global bans: {e}")
        return False


def is_globally_banned(uid):
    """Check if the UID is in the global ban list."""
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("SELECT 1 FROM global_bans WHERE uid = ?", (str(uid),))
        result = cursor.fetchone()
        conn.close()
        return bool(result)
    except Exception as e:
        print(f"Could not check global ban for {uid}: {e}")
        return False


def update_glory(channel_id, uid, glory, updated_by, timestamp):
    """Update glory data for a player in a channel."""
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute(
            "INSERT OR REPLACE INTO glory (channel_id, uid, glory, updated_by, timestamp) VALUES (?, ?, ?, ?, ?)",
            (str(channel_id), str(uid), glory, updated_by, timestamp)
        )
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"Could not update glory for {uid} in channel {channel_id}: {e}")
        return False


def get_glory_data(channel_id):
    """Retrieve all glory data for a channel."""
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT uid, glory FROM glory WHERE channel_id = ?",
            (str(channel_id),)
        )
        rows = cursor.fetchall()
        conn.close()
        return rows  # list of (uid, glory)
    except Exception as e:
        print(f"Could not fetch glory data for channel {channel_id}: {e}")
        return []


def set_glory_threshold(channel_id, threshold, updated_by, timestamp):
    """Set the glory threshold for a channel."""
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute(
            "INSERT OR REPLACE INTO glory_settings (channel_id, threshold, updated_by, timestamp) VALUES (?, ?, ?, ?)",
            (str(channel_id), threshold, updated_by, timestamp)
        )
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"Could not set glory threshold for channel {channel_id}: {e}")
        return False


def get_glory_threshold(channel_id):
    """Get the glory threshold for a channel, defaulting to 7000."""
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT threshold FROM glory_settings WHERE channel_id = ?",
            (str(channel_id),)
        )
        row = cursor.fetchone()
        conn.close()
        return row[0] if row else 7000
    except Exception as e:
        print(f"Could not fetch glory threshold for channel {channel_id}: {e}")
        return 7000


def add_glory_exception(channel_id, uid, added_by, timestamp):
    """Add a player to glory exception list."""
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute(
            "INSERT OR REPLACE INTO glory_exceptions (channel_id, uid, added_by, timestamp) VALUES (?, ?, ?, ?)",
            (str(channel_id), str(uid), added_by, timestamp)
        )
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"Could not add glory exception for {uid} in channel {channel_id}: {e}")
        return False


def remove_glory_exception(channel_id, uid):
    """Remove a player from glory exception list."""
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute(
            "DELETE FROM glory_exceptions WHERE channel_id = ? AND uid = ?",
            (str(channel_id), str(uid))
        )
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"Could not remove glory exception for {uid} in channel {channel_id}: {e}")
        return False


def get_glory_exceptions(channel_id):
    """Get all glory exceptions for a channel."""
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT uid, added_by, timestamp FROM glory_exceptions WHERE channel_id = ? ORDER BY timestamp DESC",
            (str(channel_id),)
        )
        rows = cursor.fetchall()
        conn.close()
        return rows  # list of (uid, added_by, timestamp)
    except Exception as e:
        print(f"Could not fetch glory exceptions for channel {channel_id}: {e}")
        return []


def is_glory_exception(channel_id, uid):
    """Check if a player is in the glory exception list."""
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT 1 FROM glory_exceptions WHERE channel_id = ? AND uid = ?",
            (str(channel_id), str(uid))
        )
        row = cursor.fetchone()
        conn.close()
        return row is not None
    except Exception as e:
        print(f"Could not check glory exception for {uid} in channel {channel_id}: {e}")
        return False


async def log_action(interaction, action_type: str, details: str):
    """Log a bot action to the guild's log channel"""
    log_channel_id = await get_log_channel_async(interaction.guild_id)
    if not log_channel_id:
        return  # No log channel set
    
    try:
        log_channel = interaction.client.get_channel(log_channel_id)
        if not log_channel:
            return
        
        embed = discord.Embed(
            title=f"🔔 {action_type}",
            description=details,
            color=discord.Color.blue()
        )
        embed.set_author(name=interaction.user.display_name, icon_url=interaction.user.display_avatar.url)
        embed.set_footer(text=f"Guild: {interaction.guild.name}")
        
        await log_channel.send(embed=embed)
    except Exception as e:
        print(f"Error logging action: {e}")

# Permission helper functions
def is_commander(interaction):
    """Check if user is a commander or admin"""
    if interaction.user.guild_permissions.administrator:
        return True
    for role in interaction.user.roles:
        if role.name.lower() == "commander":
            return True
    return False

# Data processing
def parse_member_lines(text, ID_RE):
    """Parse member list from text input"""
    members = {}
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        m = ID_RE.search(line)
        if m:
            id_ = m.group(1)
            name = line.replace(id_, "").replace(",", " ").strip(" -:|")
            members[id_] = name
    return members
