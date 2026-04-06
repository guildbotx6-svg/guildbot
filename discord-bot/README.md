# Discord Bot - Reconcile

A Discord bot for managing guild members and bound player lists with MongoDB persistence.

## Features

- 12 slash commands organized by category
- MongoDB database integration
- Member binding and tracking
- Moderation tools (warn, mute, unmute)
- Message cleanup (prune)
- Channel management

## Setup

### Local Setup
1. Install Python 3.10+
2. Install dependencies: `pip install -r requirements.txt`
3. Create `.env` file with:
   ```
   TOKEN=your_discord_bot_token
   MONGO_URI=your_mongodb_connection_string
   ```
4. Run: `python reconcile_bot.py`

### Cloud Setup (Replit)
1. Import this repo to Replit
2. Add secrets in Replit:
   - `TOKEN` → Your Discord bot token
   - `MONGO_URI` → Your MongoDB URI
3. Click Run

### Cloud Setup (Render)
1. Add this repo to Render and choose a **Background Worker** service.
2. Render will use `requirements.txt` and `runtime.txt`.
3. Set environment variables in Render:
   - `TOKEN`
   - `MONGO_URI`
   - `GUILD_ID` (optional)
4. Render start command:
   ```bash
   python reconcile_bot.py
   ```

> Note: This bot stores local SQLite data files in the repo folder. For persistent guild history or state across deploys, use MongoDB or external storage.

## Commands

### Members (`/members`)
- `setguild` - Set guild member list
- `setbound` - Set bound member list
- `notbind` - Show unbound members
- `missing_player` - Show missing players
- `showdata` - Preview lists
- `update` - Update member info
- `clear` - Clear all data
- `count` - Show member counts
- `export` - Export as CSV

### Commander (`/addcommander`, `/removecommander`, `/listcommanders`)
- Manage commander role

### Channel (`/lockchannel`, `/unlockchannel`)
- Control channel permissions

### Moderation (`/warn`, `/mute`, `/unmute`)
- User discipline tools

### Cleanup (`/prune`, `/pruneuser`)
- Message management

### Utility (`/help`)
- Command reference

## Requirements

- discord.py
- pymongo
- python-dotenv
- MongoDB (local or Atlas)
