"""
Free Fire Guild Management Web Interface
Web version of the Discord bot functionality
"""

import os
import sqlite3
import json
import io
import csv
from datetime import datetime, timezone, timedelta
from flask import Flask, render_template, request, redirect, url_for, flash, session, send_file, jsonify
from flask_session import Session
import discord
from discord.ext import commands
import asyncio

# IST timezone constant
IST = timezone(timedelta(hours=5, minutes=30))

# Configuration
app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-change-this-in-production'
app.config['SESSION_TYPE'] = 'filesystem'
Session(app)

# Database paths
DB_PATH = os.path.join(os.path.dirname(__file__), "..", "guild.db")
DISCORD_DB_PATH = os.path.join(os.path.dirname(__file__), "..", "discord_bot.db")

# Initialize databases
def init_databases():
    """Initialize all required databases"""
    # Guild database (from reconcile_bot)
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS guild_state (
        channel_id INTEGER PRIMARY KEY,
        members TEXT
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS guild_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        channel_id INTEGER,
        timestamp TEXT,
        joined TEXT,
        left TEXT
    )
    """)

    # Discord bot database (from helpers)
    discord_conn = sqlite3.connect(DISCORD_DB_PATH, check_same_thread=False)
    discord_cursor = discord_conn.cursor()

    # Channel data table
    discord_cursor.execute('''
        CREATE TABLE IF NOT EXISTS channel_data (
            channel_id TEXT PRIMARY KEY,
            guild_data TEXT,
            bound_data TEXT
        )
    ''')

    # Log settings table
    discord_cursor.execute('''
        CREATE TABLE IF NOT EXISTS log_settings (
            guild_id TEXT PRIMARY KEY,
            log_channel_id TEXT
        )
    ''')

    # Warnings table
    discord_cursor.execute('''
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

    # Bans table
    discord_cursor.execute('''
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

    # Global bans table
    discord_cursor.execute('''
        CREATE TABLE IF NOT EXISTS global_bans (
            uid TEXT PRIMARY KEY,
            player_name TEXT,
            reason TEXT,
            whatsapp TEXT,
            banned_by TEXT,
            timestamp TEXT,
            source_guild_id TEXT
        )
    ''')

    discord_conn.commit()
    discord_conn.close()
    conn.commit()
    conn.close()

# Initialize on startup
init_databases()

# Helper functions
def get_channel_data(channel_id):
    """Get guild and bound data for a channel"""
    try:
        conn = sqlite3.connect(DISCORD_DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT guild_data, bound_data FROM channel_data WHERE channel_id=?", (str(channel_id),))
        row = cursor.fetchone()
        conn.close()

        if row:
            guild_data = json.loads(row[0]) if row[0] else {}
            bound_data = json.loads(row[1]) if row[1] else {}
            return guild_data, bound_data
        return {}, {}
    except Exception as e:
        print(f"Error getting channel data: {e}")
        return {}, {}

def update_channel_data(channel_id, guild_data, bound_data):
    """Update guild and bound data for a channel"""
    try:
        conn = sqlite3.connect(DISCORD_DB_PATH)
        cursor = conn.cursor()
        cursor.execute(
            "REPLACE INTO channel_data (channel_id, guild_data, bound_data) VALUES (?, ?, ?)",
            (str(channel_id), json.dumps(guild_data), json.dumps(bound_data))
        )
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"Error updating channel data: {e}")
        return False

def clear_channel_data(channel_id):
    """Clear all data for a channel"""
    try:
        conn = sqlite3.connect(DISCORD_DB_PATH)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM channel_data WHERE channel_id=?", (str(channel_id),))
        cursor.execute("DELETE FROM warnings WHERE channel_id=?", (str(channel_id),))
        cursor.execute("DELETE FROM bans WHERE channel_id=?", (str(channel_id),))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"Error clearing channel data: {e}")
        return False

def parse_member_lines(text):
    """Parse member lines in format: Name,UID"""
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

def get_member_name_by_uid(channel_id, uid):
    """Get member name by UID from guild state"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT members FROM guild_state WHERE channel_id=?", (channel_id,))
        row = cursor.fetchone()
        conn.close()

        if row and row[0]:
            members = json.loads(row[0])
            # Try both string and int keys
            return members.get(str(uid)) or members.get(int(uid), f"Unknown ({uid})")
        return f"Unknown ({uid})"
    except Exception as e:
        print(f"Error getting member name: {e}")
        return f"Unknown ({uid})"

def add_warning(channel_id, uid, reason, warned_by, timestamp, guild_id=None):
    """Add a warning"""
    try:
        conn = sqlite3.connect(DISCORD_DB_PATH)
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO warnings (guild_id, channel_id, uid, reason, warned_by, timestamp) VALUES (?, ?, ?, ?, ?, ?)",
            (str(guild_id), str(channel_id), str(uid), reason, warned_by, timestamp)
        )
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"Error adding warning: {e}")
        return False

def get_warnings(channel_id, uid):
    """Get warnings for a UID in a channel"""
    try:
        conn = sqlite3.connect(DISCORD_DB_PATH)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT reason, warned_by, timestamp FROM warnings WHERE channel_id=? AND uid=? ORDER BY timestamp DESC",
            (str(channel_id), str(uid))
        )
        rows = cursor.fetchall()
        conn.close()
        return rows
    except Exception as e:
        print(f"Error getting warnings: {e}")
        return []

def get_all_warned_members(channel_id):
    """Get all warned members in a channel with warning counts"""
    try:
        conn = sqlite3.connect(DISCORD_DB_PATH)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT uid, COUNT(*) as count FROM warnings WHERE channel_id=? GROUP BY uid ORDER BY count DESC",
            (str(channel_id),)
        )
        rows = cursor.fetchall()
        conn.close()
        return rows
    except Exception as e:
        print(f"Error getting warned members: {e}")
        return []

def clear_warnings(channel_id, uid):
    """Clear warnings for a UID in a channel"""
    try:
        conn = sqlite3.connect(DISCORD_DB_PATH)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM warnings WHERE channel_id=? AND uid=?", (str(channel_id), str(uid)))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"Error clearing warnings: {e}")
        return False

def clear_all_warnings(channel_id):
    """Clear all warnings in a channel"""
    try:
        conn = sqlite3.connect(DISCORD_DB_PATH)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM warnings WHERE channel_id=?", (str(channel_id),))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"Error clearing all warnings: {e}")
        return False

def add_ban(channel_id, uid, player_name, reason, whatsapp, banned_by, timestamp, guild_id=None, global_ban=False):
    """Add a ban"""
    try:
        conn = sqlite3.connect(DISCORD_DB_PATH)
        cursor = conn.cursor()

        if global_ban:
            # Add to global bans
            cursor.execute(
                "REPLACE INTO global_bans (uid, player_name, reason, whatsapp, banned_by, timestamp, source_guild_id) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (str(uid), player_name, reason, whatsapp, banned_by, timestamp, str(guild_id))
            )
        else:
            # Add to channel bans
            cursor.execute(
                "INSERT INTO bans (guild_id, channel_id, uid, player_name, reason, whatsapp, banned_by, timestamp) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (str(guild_id), str(channel_id), str(uid), player_name, reason, whatsapp, banned_by, timestamp)
            )

        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"Error adding ban: {e}")
        return False

def get_bans(channel_id):
    """Get all bans in a channel"""
    try:
        conn = sqlite3.connect(DISCORD_DB_PATH)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT uid, player_name, reason, whatsapp, banned_by, timestamp FROM bans WHERE channel_id=? ORDER BY timestamp DESC",
            (str(channel_id),)
        )
        rows = cursor.fetchall()
        conn.close()
        return rows
    except Exception as e:
        print(f"Error getting bans: {e}")
        return []

def get_global_bans():
    """Get all global bans"""
    try:
        conn = sqlite3.connect(DISCORD_DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT uid, player_name, reason, whatsapp, banned_by, timestamp, source_guild_id FROM global_bans ORDER BY timestamp DESC")
        rows = cursor.fetchall()
        conn.close()
        return rows
    except Exception as e:
        print(f"Error getting global bans: {e}")
        return []

def is_globally_banned(uid):
    """Check if a UID is globally banned"""
    try:
        conn = sqlite3.connect(DISCORD_DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT uid FROM global_bans WHERE uid=?", (str(uid),))
        row = cursor.fetchone()
        conn.close()
        return row is not None
    except Exception as e:
        print(f"Error checking global ban: {e}")
        return False

def get_banned_members(channel_id):
    """Get all banned members in a channel"""
    try:
        conn = sqlite3.connect(DISCORD_DB_PATH)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT uid, player_name FROM bans WHERE channel_id=?",
            (str(channel_id),)
        )
        rows = cursor.fetchall()
        conn.close()
        return rows
    except Exception as e:
        print(f"Error getting banned members: {e}")
        return []

# Database helper functions
def get_channel_data(channel_id):
    """Retrieve guild and bound data for a channel"""
    try:
        conn = sqlite3.connect(DISCORD_DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT guild_data, bound_data FROM channel_data WHERE channel_id=?", (str(channel_id),))
        row = cursor.fetchone()
        conn.close()

        if row:
            guild_data = json.loads(row[0]) if row[0] else {}
            bound_data = json.loads(row[1]) if row[1] else {}
            return guild_data, bound_data
        return {}, {}
    except Exception as e:
        print(f"Error getting channel data: {e}")
        return {}, {}

def update_channel_data(channel_id, guild_data, bound_data):
    """Update guild and bound data for a channel"""
    try:
        conn = sqlite3.connect(DISCORD_DB_PATH)
        cursor = conn.cursor()
        cursor.execute(
            "REPLACE INTO channel_data (channel_id, guild_data, bound_data) VALUES (?, ?, ?)",
            (str(channel_id), json.dumps(guild_data), json.dumps(bound_data))
        )
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"Error updating channel data: {e}")
        return False

def clear_channel_data(channel_id):
    """Clear all data for a channel"""
    try:
        conn = sqlite3.connect(DISCORD_DB_PATH)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM channel_data WHERE channel_id=?", (str(channel_id),))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"Error clearing channel data: {e}")
        return False

def parse_member_lines(text):
    """Parse member lines from text input"""
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

def get_member_name_by_uid(channel_id, uid):
    """Get member name by UID from guild state"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT members FROM guild_state WHERE channel_id=?", (channel_id,))
        row = cursor.fetchone()
        conn.close()

        if row and row[0]:
            members = json.loads(row[0])
            return members.get(str(uid)) or members.get(int(uid))
        return None
    except Exception as e:
        print(f"Error getting member name: {e}")
        return None

# Warning functions
def add_warning(channel_id, uid, reason, warned_by, timestamp, guild_id=None):
    """Add a warning"""
    try:
        conn = sqlite3.connect(DISCORD_DB_PATH)
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO warnings (guild_id, channel_id, uid, reason, warned_by, timestamp) VALUES (?, ?, ?, ?, ?, ?)",
            (guild_id, channel_id, uid, reason, warned_by, timestamp)
        )
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"Error adding warning: {e}")
        return False

def get_warnings(channel_id, uid):
    """Get warnings for a UID in a channel"""
    try:
        conn = sqlite3.connect(DISCORD_DB_PATH)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT reason, warned_by, timestamp FROM warnings WHERE channel_id=? AND uid=? ORDER BY timestamp DESC",
            (channel_id, uid)
        )
        rows = cursor.fetchall()
        conn.close()
        return rows
    except Exception as e:
        print(f"Error getting warnings: {e}")
        return []

def get_all_warned_members(channel_id):
    """Get all warned members in a channel"""
    try:
        conn = sqlite3.connect(DISCORD_DB_PATH)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT uid, COUNT(*) as count FROM warnings WHERE channel_id=? GROUP BY uid ORDER BY count DESC",
            (channel_id,)
        )
        rows = cursor.fetchall()
        conn.close()
        return rows
    except Exception as e:
        print(f"Error getting warned members: {e}")
        return []

def clear_warnings(channel_id, uid):
    """Clear warnings for a UID in a channel"""
    try:
        conn = sqlite3.connect(DISCORD_DB_PATH)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM warnings WHERE channel_id=? AND uid=?", (channel_id, uid))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"Error clearing warnings: {e}")
        return False

def clear_all_warnings(channel_id):
    """Clear all warnings in a channel"""
    try:
        conn = sqlite3.connect(DISCORD_DB_PATH)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM warnings WHERE channel_id=?", (channel_id,))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"Error clearing all warnings: {e}")
        return False

# Ban functions
def add_ban(channel_id, uid, player_name, reason, whatsapp, banned_by, timestamp, guild_id=None, global_ban=False):
    """Add a ban"""
    try:
        if global_ban:
            conn = sqlite3.connect(DISCORD_DB_PATH)
            cursor = conn.cursor()
            cursor.execute(
                "INSERT OR REPLACE INTO global_bans (uid, player_name, reason, whatsapp, banned_by, timestamp, source_guild_id) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (uid, player_name, reason, whatsapp, banned_by, timestamp, guild_id)
            )
        else:
            conn = sqlite3.connect(DISCORD_DB_PATH)
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO bans (guild_id, channel_id, uid, player_name, reason, whatsapp, banned_by, timestamp) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (guild_id, channel_id, uid, player_name, reason, whatsapp, banned_by, timestamp)
            )
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"Error adding ban: {e}")
        return False

def get_bans(channel_id):
    """Get all bans in a channel"""
    try:
        conn = sqlite3.connect(DISCORD_DB_PATH)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT uid, player_name, reason, whatsapp, banned_by, timestamp FROM bans WHERE channel_id=? ORDER BY timestamp DESC",
            (channel_id,)
        )
        rows = cursor.fetchall()
        conn.close()
        return rows
    except Exception as e:
        print(f"Error getting bans: {e}")
        return []

def get_global_bans():
    """Get all global bans"""
    try:
        conn = sqlite3.connect(DISCORD_DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT uid, player_name, reason, whatsapp, banned_by, timestamp, source_guild_id FROM global_bans ORDER BY timestamp DESC")
        rows = cursor.fetchall()
        conn.close()
        return rows
    except Exception as e:
        print(f"Error getting global bans: {e}")
        return []

def is_globally_banned(uid):
    """Check if a UID is globally banned"""
    try:
        conn = sqlite3.connect(DISCORD_DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT 1 FROM global_bans WHERE uid=?", (uid,))
        result = cursor.fetchone()
        conn.close()
        return result is not None
    except Exception as e:
        print(f"Error checking global ban: {e}")
        return False

# Dashboard statistics functions
def get_guild_member_count():
    """Get total number of guild members across all channels"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT members FROM guild_state")
        rows = cursor.fetchall()
        conn.close()

        total_count = 0
        for row in rows:
            if row[0]:
                members = json.loads(row[0])
                total_count += len(members)
        return total_count
    except Exception as e:
        print(f"Error getting guild count: {e}")
        return 0

def get_warning_count():
    """Get total number of warnings"""
    try:
        conn = sqlite3.connect(DISCORD_DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM warnings")
        row = cursor.fetchone()
        conn.close()
        return row[0] if row else 0
    except Exception as e:
        print(f"Error getting warning count: {e}")
        return 0

def get_ban_count():
    """Get total number of bans (channel + global)"""
    try:
        conn = sqlite3.connect(DISCORD_DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM bans")
        channel_bans = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM global_bans")
        global_bans = cursor.fetchone()[0]

        conn.close()
        return channel_bans + global_bans
    except Exception as e:
        print(f"Error getting ban count: {e}")
        return 0

def get_history_count():
    """Get total number of history entries"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM guild_history")
        row = cursor.fetchone()
        conn.close()
        return row[0] if row else 0
    except Exception as e:
        print(f"Error getting history count: {e}")
        return 0

# Routes
@app.route('/')
def index():
    """Main dashboard"""
    try:
        # Get statistics for dashboard
        guild_count = get_guild_member_count()
        warning_count = get_warning_count()
        ban_count = get_ban_count()
        history_count = get_history_count()

        return render_template('index.html',
                             guild_count=guild_count,
                             warning_count=warning_count,
                             ban_count=ban_count,
                             history_count=history_count)
    except Exception as e:
        print(f"Error loading dashboard: {e}")
        return render_template('index.html',
                             guild_count=0,
                             warning_count=0,
                             ban_count=0,
                             history_count=0)

@app.route('/guild')
def guild_management():
    """Guild management page"""
    return render_template('guild.html')

@app.route('/guild/update', methods=['POST'])
def update_guild():
    """Update guild members"""
    channel_id = request.form.get('channel_id', 'default')
    guild_data = request.form.get('guild_data', '')

    if not guild_data.strip():
        flash('Please enter guild member data', 'error')
        return redirect(url_for('guild_management'))

    current_members, invalid = parse_member_lines(guild_data)

    # Get previous state
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT members FROM guild_state WHERE channel_id=?", (channel_id,))
    row = cursor.fetchone()

    joined, left = [], []
    name_changes = []
    if row:
        old_members = {int(uid): name for uid, name in json.loads(row[0]).items()}
        joined = [(name, uid) for uid, name in current_members.items() if uid not in old_members]
        left = [(name, uid) for uid, name in old_members.items() if uid not in current_members]
        for uid in set(current_members.keys()) & set(old_members.keys()):
            if current_members[uid] != old_members[uid]:
                name_changes.append((old_members[uid], current_members[uid], uid))

    # Save current state
    cursor.execute(
        "REPLACE INTO guild_state (channel_id, members) VALUES (?, ?)",
        (channel_id, json.dumps(current_members))
    )

    # Log to history
    if joined or left:
        cursor.execute(
            "INSERT INTO guild_history (channel_id, timestamp, joined, left) VALUES (?, ?, ?, ?)",
            (channel_id, str(datetime.now(IST)), json.dumps(joined), json.dumps(left))
        )

    conn.commit()
    conn.close()

    # Check for banned players
    banned_players = []
    for uid in current_members.keys():
        if is_globally_banned(uid):
            player_name = get_member_name_by_uid(channel_id, uid) or current_members[uid]
            banned_players.append(f"{player_name} ({uid})")

    flash(f'Guild updated: {len(joined)} joined, {len(left)} left, {len(name_changes)} name changes', 'success')
    if invalid:
        flash(f'Skipped invalid UIDs: {", ".join([f"{name} ({uid})" for name, uid in invalid])}', 'warning')
    if banned_players:
        flash(f'⚠️ Globally banned players detected: {", ".join(banned_players[:5])}{"..." if len(banned_players) > 5 else ""}', 'warning')

    return redirect(url_for('guild_management'))

@app.route('/guild/export/<data_type>')
def export_guild_data(data_type):
    """Export guild data"""
    channel_id = request.args.get('channel_id', 'default')

    if data_type == 'members':
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT members FROM guild_state WHERE channel_id=?", (channel_id,))
        row = cursor.fetchone()
        conn.close()

        if not row or not row[0]:
            flash('No guild data found', 'error')
            return redirect(url_for('guild_management'))

        members = json.loads(row[0])
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(['Name', 'UID'])
        for uid, name in members.items():
            writer.writerow([name, uid])

        output.seek(0)
        return send_file(
            io.BytesIO(output.getvalue().encode('utf-8')),
            mimetype='text/csv',
            as_attachment=True,
            download_name='guild_members.csv'
        )

    elif data_type == 'history':
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT timestamp, joined, left FROM guild_history WHERE channel_id=? ORDER BY id DESC",
            (channel_id,)
        )
        rows = cursor.fetchall()
        conn.close()

        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(['Timestamp', 'Action', 'Name', 'UID'])

        for timestamp, joined_json, left_json in rows:
            if joined_json:
                for name, uid in json.loads(joined_json):
                    writer.writerow([timestamp, 'Joined', name, uid])
            if left_json:
                for name, uid in json.loads(left_json):
                    writer.writerow([timestamp, 'Left', name, uid])

        output.seek(0)
        return send_file(
            io.BytesIO(output.getvalue().encode('utf-8')),
            mimetype='text/csv',
            as_attachment=True,
            download_name='guild_history.csv'
        )

    flash('Invalid export type', 'error')
    return redirect(url_for('guild_management'))

@app.route('/members', methods=['GET', 'POST'])
def members_page():
    """Member and bound list management page"""
    channel_id = request.args.get('channel_id', 'default')

    if request.method == 'POST':
        if 'set_guild' in request.form:
            guild_text = request.form.get('guild_data', '')
            members, invalid = parse_member_lines(guild_text)
            guild_data, bound_data = get_channel_data(channel_id)
            guild_data.update(members)
            update_channel_data(channel_id, guild_data, bound_data)
            flash(f'Updated guild list with {len(members)} members', 'success')
            if invalid:
                flash(f'Skipped {len(invalid)} invalid entries', 'warning')

        elif 'set_bound' in request.form:
            bound_text = request.form.get('bound_data', '')
            members, invalid = parse_member_lines(bound_text)
            guild_data, bound_data = get_channel_data(channel_id)
            bound_data.update(members)
            update_channel_data(channel_id, guild_data, bound_data)
            flash(f'Updated bound list with {len(members)} members', 'success')
            if invalid:
                flash(f'Skipped {len(invalid)} invalid entries', 'warning')

        elif 'clear_data' in request.form:
            clear_channel_data(channel_id)
            flash('Cleared all member data for this channel', 'success')

    guild_data, bound_data = get_channel_data(channel_id)
    guild_only = {uid: name for uid, name in guild_data.items() if uid not in bound_data}
    bound_only = {uid: name for uid, name in bound_data.items() if uid not in guild_data}
    total_unique = len(set(guild_data.keys()) | set(bound_data.keys()))

    return render_template('members.html',
                         channel_id=channel_id,
                         guild_data=guild_data,
                         bound_data=bound_data,
                         guild_only=guild_only,
                         bound_only=bound_only,
                         total_unique=total_unique)

@app.route('/members/export/<export_type>/<channel_id>')
def members_export(export_type, channel_id):
    """Export members or bound lists as CSV"""
    guild_data, bound_data = get_channel_data(channel_id)

    if export_type == 'guild_only':
        rows = {uid: name for uid, name in guild_data.items() if uid not in bound_data}
        download_name = 'members_guild_only.csv'
    elif export_type == 'bound_only':
        rows = {uid: name for uid, name in bound_data.items() if uid not in guild_data}
        download_name = 'members_bound_only.csv'
    else:
        flash('Invalid export type', 'error')
        return redirect(url_for('members_page', channel_id=channel_id))

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['Name', 'UID'])
    for uid, name in rows.items():
        writer.writerow([name, uid])

    output.seek(0)
    return send_file(
        io.BytesIO(output.getvalue().encode('utf-8')),
        mimetype='text/csv',
        as_attachment=True,
        download_name=download_name
    )

@app.route('/warnings')
def warnings_page():
    """Warnings management page"""
    return render_template('warnings.html')

@app.route('/warnings/add', methods=['POST'])
def add_warning_route():
    """Add warnings"""
    channel_id = request.form.get('channel_id', 'default')
    warning_data = request.form.get('warning_data', '')

    if not warning_data.strip():
        flash('Please enter warning data', 'error')
        return redirect(url_for('warnings_page'))

    added_count = 0
    invalid_count = 0

    for line in warning_data.splitlines():
        line = line.strip()
        if not line:
            continue

        parts = line.split(',', 1)
        if len(parts) == 2:
            uid_str, reason = parts
            try:
                uid = int(uid_str.strip())
                success = add_warning(channel_id, uid, reason.strip(), 'Web Interface', str(datetime.now(IST)))
                if success:
                    added_count += 1
                else:
                    invalid_count += 1
            except ValueError:
                invalid_count += 1
        else:
            invalid_count += 1

    flash(f'Added {added_count} warnings, {invalid_count} invalid entries', 'success')
    return redirect(url_for('warnings_page'))

@app.route('/warnings/view/<uid>')
def view_warnings(uid):
    """View warnings for a specific UID"""
    try:
        uid_int = int(uid)
    except ValueError:
        flash('Invalid UID format', 'error')
        return redirect(url_for('warnings_page'))

    channel_id = request.args.get('channel_id', 'default')
    warnings_list = get_warnings(channel_id, uid_int)

    if not warnings_list:
        flash(f'No warnings found for UID {uid}', 'info')
        return redirect(url_for('warnings_page'))

    # Create CSV response
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['Reason', 'Warned By', 'Timestamp'])

    for reason, warned_by, timestamp in warnings_list:
        writer.writerow([reason, warned_by, timestamp])

    output.seek(0)
    return send_file(
        io.BytesIO(output.getvalue().encode('utf-8')),
        mimetype='text/csv',
        as_attachment=True,
        download_name=f'warnings_{uid}.csv'
    )

@app.route('/warnings/list')
def list_warnings():
    """List all warned members"""
    channel_id = request.args.get('channel_id', 'default')
    warned_members = get_all_warned_members(channel_id)

    if not warned_members:
        flash('No warnings found in this channel', 'info')
        return redirect(url_for('warnings_page'))

    # Create CSV response
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['UID', 'Warning Count', 'Player Name'])

    for uid, count in warned_members:
        player_name = get_member_name_by_uid(channel_id, uid) or 'Unknown'
        writer.writerow([uid, count, player_name])

    output.seek(0)
    return send_file(
        io.BytesIO(output.getvalue().encode('utf-8')),
        mimetype='text/csv',
        as_attachment=True,
        download_name='warned_members.csv'
    )

@app.route('/bans')
def bans_page():
    """Bans management page"""
    return render_template('bans.html')

@app.route('/bans/add', methods=['POST'])
def add_ban_route():
    """Add bans"""
    channel_id = request.form.get('channel_id', 'default')
    ban_data = request.form.get('ban_data', '')
    is_global = request.form.get('global_ban') == 'on'

    if not ban_data.strip():
        flash('Please enter ban data', 'error')
        return redirect(url_for('bans_page'))

    added_count = 0
    invalid_count = 0

    for line in ban_data.splitlines():
        line = line.strip()
        if not line:
            continue

        parts = line.split(',', 3)
        if len(parts) >= 4:
            uid_str, player_name, reason, whatsapp = parts
            try:
                uid = int(uid_str.strip())
                success = add_ban(
                    channel_id, uid, player_name.strip(), reason.strip(),
                    whatsapp.strip(), 'Web Interface', str(datetime.now(IST)),
                    global_ban=is_global
                )
                if success:
                    added_count += 1
                else:
                    invalid_count += 1
            except ValueError:
                invalid_count += 1
        else:
            invalid_count += 1

    ban_type = 'global' if is_global else 'channel'
    flash(f'Added {added_count} {ban_type} bans, {invalid_count} invalid entries', 'success')
    return redirect(url_for('bans_page'))

@app.route('/bans/list')
def list_bans():
    """List all bans"""
    channel_id = request.args.get('channel_id', 'default')
    is_global = request.args.get('global') == 'true'

    if is_global:
        bans_list = get_global_bans()
        filename = 'global_bans.csv'
    else:
        bans_list = get_bans(channel_id)
        filename = 'channel_bans.csv'

    if not bans_list:
        ban_type = 'global' if is_global else 'channel'
        flash(f'No {ban_type} bans found', 'info')
        return redirect(url_for('bans_page'))

    # Create CSV response
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['UID', 'Player Name', 'Reason', 'WhatsApp', 'Banned By', 'Timestamp'])

    for ban_data in bans_list:
        if is_global:
            uid, player_name, reason, whatsapp, banned_by, timestamp, source_guild = ban_data
        else:
            uid, player_name, reason, whatsapp, banned_by, timestamp = ban_data
        writer.writerow([uid, player_name, reason, whatsapp, banned_by, timestamp])

    output.seek(0)
    return send_file(
        io.BytesIO(output.getvalue().encode('utf-8')),
        mimetype='text/csv',
        as_attachment=True,
        download_name=filename
    )

@app.route('/commanders')
def commanders_page():
    """Commanders management placeholder page"""
    return render_template('commanders.html')

@app.route('/channels')
def channels_page():
    """Channel management placeholder page"""
    return render_template('channels.html')

@app.route('/cleanup')
def cleanup_page():
    """Cleanup commands placeholder page"""
    return render_template('cleanup.html')

@app.route('/utility')
def utility_page():
    """Utility tools placeholder page"""
    return render_template('utility.html')

@app.route('/help')
def help_page():
    """Help and documentation page"""
    return render_template('help.html')

@app.route('/logs')
def logs_page():
    """Audit log console page"""
    channel_id = request.args.get('channel_id', 'default')
    start_date_raw = request.args.get('start_date', '')
    end_date_raw = request.args.get('end_date', '')
    action_filter = request.args.get('action', 'all')
    app_filter = request.args.get('app', 'all')
    email_filter = request.args.get('email', '').strip()

    def parse_date(value, end_of_day=False):
        if not value:
            return None
        try:
            dt = datetime.fromisoformat(value)
            if dt.tzinfo is not None:
                dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
            if end_of_day:
                return dt.replace(hour=23, minute=59, second=59, microsecond=999999)
            return dt.replace(hour=0, minute=0, second=0, microsecond=0)
        except Exception:
            return None

    def normalize_timestamp(value):
        if isinstance(value, str):
            try:
                dt = datetime.fromisoformat(value)
            except Exception:
                return None
        else:
            dt = value
        if dt is None:
            return None
        if dt.tzinfo is not None:
            dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
        return dt

    start_date = parse_date(start_date_raw)
    end_date = parse_date(end_date_raw, end_of_day=True)

    def normalize_name(full_name):
        if not full_name:
            return 'Unknown', ''
        parts = full_name.strip().split()
        first = parts[0]
        last = ' '.join(parts[1:]) if len(parts) > 1 else ''
        return first, last

    def build_email(first, last):
        if not first and not last:
            return 'noreply@guild.local'
        slug = f"{first}.{last}" if last else first
        slug = ''.join(ch.lower() if ch.isalnum() or ch == '.' else '.' for ch in slug)
        slug = slug.replace('..', '.')
        return f"{slug}@guild.local"

    logs = []
    discord_conn = sqlite3.connect(DISCORD_DB_PATH)
    discord_cursor = discord_conn.cursor()
    guild_conn = sqlite3.connect(DB_PATH)
    guild_cursor = guild_conn.cursor()

    warning_query = "SELECT id, uid, reason, warned_by, timestamp FROM warnings"
    ban_query = "SELECT id, channel_id, uid, player_name, reason, whatsapp, banned_by, timestamp FROM bans"
    history_query = "SELECT id, channel_id, timestamp, joined, left FROM guild_history"
    global_ban_query = "SELECT uid, player_name, reason, whatsapp, banned_by, timestamp, source_guild_id FROM global_bans"

    warning_params = []
    ban_params = []
    history_params = []
    if channel_id and channel_id != 'all':
        warning_query += " WHERE channel_id=?"
        ban_query += " WHERE channel_id=?"
        history_query += " WHERE channel_id=?"
        warning_params = [channel_id]
        ban_params = [channel_id]
        history_params = [channel_id]

    for row in discord_cursor.execute(warning_query, warning_params):
        row_id, uid, reason, warned_by, timestamp = row
        first_name, last_name = normalize_name(get_member_name_by_uid(channel_id, uid) or '')
        email_address = build_email(first_name, last_name)
        logs.append({
            'id': f'W{row_id}',
            'first_name': first_name,
            'last_name': last_name,
            'email_address': email_address,
            'action': 'Warning',
            'browser_time': timestamp,
            'ip_address': 'Web UI',
            'user_agent': 'Browser',
            'application': 'Guild Manager',
            'description': reason or 'Warning issued',
            'timestamp': normalize_timestamp(timestamp)
        })

    for row in discord_cursor.execute(ban_query, ban_params):
        row_id, row_channel, uid, player_name, reason, whatsapp, banned_by, timestamp = row
        first_name, last_name = normalize_name(player_name or get_member_name_by_uid(channel_id, uid) or '')
        email_address = build_email(first_name, last_name)
        logs.append({
            'id': f'B{row_id}',
            'first_name': first_name,
            'last_name': last_name,
            'email_address': email_address,
            'action': 'Ban',
            'browser_time': timestamp,
            'ip_address': whatsapp or 'N/A',
            'user_agent': 'Web UI',
            'application': 'Guild Manager',
            'description': reason or 'Ban recorded',
            'timestamp': normalize_timestamp(timestamp)
        })

    for row in guild_cursor.execute(history_query, history_params):
        row_id, row_channel, timestamp, joined_json, left_json = row
        joined = json.loads(joined_json) if joined_json else []
        left = json.loads(left_json) if left_json else []
        first_name, last_name = normalize_name('Guild Event')
        email_address = build_email(first_name, last_name)
        details = []
        if joined:
            details.append(f"{len(joined)} joined")
        if left:
            details.append(f"{len(left)} left")
        description = ', '.join(details) if details else 'Guild roster updated'
        logs.append({
            'id': f'H{row_id}',
            'first_name': first_name,
            'last_name': last_name,
            'email_address': email_address,
            'action': 'Guild Update',
            'browser_time': timestamp,
            'ip_address': row_channel,
            'user_agent': 'Sync Engine',
            'application': 'Guild Manager',
            'description': description,
            'timestamp': normalize_timestamp(timestamp)
        })

    for row in discord_cursor.execute(global_ban_query):
        uid, player_name, reason, whatsapp, banned_by, timestamp, source_guild_id = row
        first_name, last_name = normalize_name(player_name or '')
        email_address = build_email(first_name, last_name)
        logs.append({
            'id': f'G{uid}',
            'first_name': first_name,
            'last_name': last_name,
            'email_address': email_address,
            'action': 'Global Ban',
            'browser_time': timestamp,
            'ip_address': source_guild_id or 'N/A',
            'user_agent': 'Web UI',
            'application': 'Guild Manager',
            'description': reason or 'Global ban recorded',
            'timestamp': normalize_timestamp(timestamp)
        })

    discord_conn.close()
    guild_conn.close()

    filtered_logs = []
    for entry in logs:
        if action_filter != 'all' and action_filter.lower() != entry['action'].lower().replace(' ', '_'):
            continue
        if email_filter and email_filter.lower() not in entry['email_address'].lower() and email_filter.lower() not in entry['first_name'].lower() and email_filter.lower() not in entry['last_name'].lower():
            continue
        if start_date and entry['timestamp'] < start_date:
            continue
        if end_date and entry['timestamp'] > end_date:
            continue
        filtered_logs.append(entry)

    filtered_logs.sort(key=lambda row: row['timestamp'], reverse=True)

    total_logs = len(filtered_logs)
    warning_count = sum(1 for row in filtered_logs if row['action'] == 'Warning')
    ban_count = sum(1 for row in filtered_logs if row['action'] == 'Ban')
    guild_count = sum(1 for row in filtered_logs if row['action'] == 'Guild Update')
    global_count = sum(1 for row in filtered_logs if row['action'] == 'Global Ban')

    return render_template('logs.html',
                           logs=filtered_logs,
                           total_logs=total_logs,
                           warning_count=warning_count,
                           ban_count=ban_count,
                           guild_count=guild_count,
                           global_count=global_count,
                           channel_id=channel_id,
                           start_date=start_date_raw,
                           end_date=end_date_raw,
                           action_filter=action_filter,
                           app_filter=app_filter,
                           email_filter=email_filter)

@app.route('/check-ban/<uid>')
def check_ban(uid):
    """Check if a UID is banned"""
    try:
        uid_int = int(uid)
    except ValueError:
        return {'error': 'Invalid UID format'}, 400

    is_banned = is_globally_banned(uid_int)
    return {'banned': is_banned, 'uid': uid_int}

@app.route('/api/stats')
def api_stats():
    """Return dashboard statistics as JSON"""
    return jsonify({
        'guild_count': get_guild_member_count(),
        'warning_count': get_warning_count(),
        'ban_count': get_ban_count(),
        'history_count': get_history_count(),
        'last_sync': datetime.now(IST).isoformat(timespec='seconds')
    })

@app.route('/api/warnings')
def api_warnings():
    """Return warnings for a specific UID in a channel"""
    channel_id = request.args.get('channel_id', 'default')
    uid = request.args.get('uid')
    if not uid:
        return jsonify({'error': 'uid query parameter required'}), 400

    try:
        uid_int = int(uid)
    except ValueError:
        return jsonify({'error': 'Invalid UID format'}), 400

    warnings_list = get_warnings(channel_id, uid_int)
    return jsonify({
        'channel_id': channel_id,
        'uid': uid_int,
        'warnings': [
            {'reason': reason, 'warned_by': warned_by, 'timestamp': timestamp}
            for reason, warned_by, timestamp in warnings_list
        ]
    })

@app.route('/api/warnings/list')
def api_list_warnings():
    """Return all warned members in a channel"""
    channel_id = request.args.get('channel_id', 'default')
    warned_members = get_all_warned_members(channel_id)
    return jsonify({
        'channel_id': channel_id,
        'warned_members': [
            {'uid': uid, 'count': count, 'player_name': get_member_name_by_uid(channel_id, uid)}
            for uid, count in warned_members
        ]
    })

@app.route('/api/bans')
def api_bans():
    """Return ban list data for a channel or global bans"""
    channel_id = request.args.get('channel_id', 'default')
    is_global = request.args.get('global') == 'true'

    if is_global:
        bans_list = get_global_bans()
        response = [
            {'uid': uid, 'player_name': player_name, 'reason': reason, 'whatsapp': whatsapp, 'banned_by': banned_by, 'timestamp': timestamp, 'source_guild_id': source_guild_id}
            for uid, player_name, reason, whatsapp, banned_by, timestamp, source_guild_id in bans_list
        ]
    else:
        bans_list = get_bans(channel_id)
        response = [
            {'uid': uid, 'player_name': player_name, 'reason': reason, 'whatsapp': whatsapp, 'banned_by': banned_by, 'timestamp': timestamp}
            for uid, player_name, reason, whatsapp, banned_by, timestamp in bans_list
        ]

    return jsonify({'channel_id': channel_id, 'global': is_global, 'bans': response})

@app.route('/api/guild_members')
def api_guild_members():
    """Return current guild member list for a channel"""
    channel_id = request.args.get('channel_id', 'default')
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('SELECT members FROM guild_state WHERE channel_id=?', (channel_id,))
    row = cursor.fetchone()
    conn.close()

    if not row or not row[0]:
        return jsonify({'channel_id': channel_id, 'members': []})

    members = json.loads(row[0])
    return jsonify({'channel_id': channel_id, 'members': [{'uid': uid, 'name': name} for uid, name in members.items()]})

@app.route('/api/guild_history')
def api_guild_history():
    """Return guild history for a channel"""
    channel_id = request.args.get('channel_id', 'default')
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('SELECT timestamp, joined, left FROM guild_history WHERE channel_id=? ORDER BY id DESC', (channel_id,))
    rows = cursor.fetchall()
    conn.close()

    history = []
    for timestamp, joined_json, left_json in rows:
        history.append({
            'timestamp': timestamp,
            'joined': json.loads(joined_json) if joined_json else [],
            'left': json.loads(left_json) if left_json else []
        })

    return jsonify({'channel_id': channel_id, 'history': history})

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)