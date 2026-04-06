# Discord Bot with MongoDB Setup Guide

## Overview
Your Discord bot now uses **MongoDB** to persistently store guild and bound member lists, instead of storing data in memory.

## Changes Made

### 1. **MongoDB Integration**
- Removed in-memory `self.storage` dictionary
- Added `get_channel_data()` and `update_channel_data()` helper functions
- All data is now automatically saved to MongoDB

### 2. **Database Structure**
- **Database**: `discord_bot`
- **Collections**:
  - `guild_data`: Stores guild and bound member lists per channel
  - `audit_logs`: Available for future logging

### 3. **Security Improvements**
- Bot TOKEN moved from hardcoded to environment variable `TOKEN`
- Added `.env.example` file with template
- Added `.gitignore` to prevent committing sensitive data

### 4. **Dependencies**
- Added `pymongo` to requirements.txt

## Installation & Setup

### Step 1: Install MongoDB
**Option A: Local MongoDB**
- Download from: https://www.mongodb.com/try/download/community
- Follow official installation guide for your OS

**Option B: MongoDB Atlas (Cloud)**
1. Create free account at https://www.mongodb.com/cloud/atlas
2. Create a cluster
3. Get your connection string

### Step 2: Install Dependencies
```bash
pip install -r requirments.txt
```

### Step 3: Configure Environment Variables
1. Copy `.env.example` to `.env`:
```bash
cp .env.example .env
```

2. Edit `.env` and add:
```
TOKEN=your_discord_bot_token
MONGO_URI=mongodb://localhost:27017  # For local
# OR
MONGO_URI=mongodb+srv://user:pass@cluster.mongodb.net/  # For Atlas
```

### Step 4: Run the Bot
```bash
python reconcile_bot.py
```

## How It Works

### Data Storage
When you use commands like `/setguild` or `/setbound`, data is automatically saved to MongoDB:
```
Channel 123456 {
  guild: { "12345": "Player Name", ... },
  bound: { "67890": "Bound Player", ... }
}
```

### Data Retrieval
Commands like `/notbind` and `/missing_player` automatically fetch from MongoDB.

### Updates
When you `/update` a player's name, it immediately saves to MongoDB.

### Clearing Data
`/clear` removes data for that specific channel from the database.

## Commands Overview
- `/setguild <text>` - Store/import guild member list
- `/setbound <text>` - Store/import bound member list
- `/notbind` - Show unbound guild members (from MongoDB)
- `/missing_player` - Show missing players (from MongoDB)
- `/showdata` - Preview stored data
- `/update <list_type> <id> <name>` - Update player name
- `/clear` - Clear all data for channel
- `/count` - Show member counts
- `/export` - Export as CSV
- `/addcommander`, `/removecommander`, `/listcommanders` - Role management
- `/mute`, `/unmute`, `/warn` - User discipline
- `/prune`, `/pruneuser` - Message cleanup
- `/lockchannel`, `/unlockchannel` - Channel control

## Troubleshooting

**Issue**: "No module named 'pymongo'"
- Solution: `pip install pymongo`

**Issue**: Connection refused to MongoDB
- Check MongoDB service is running
- Verify MONGO_URI in .env

**Issue**: Bot doesn't respond
- Verify TOKEN is correct
- Check bot has required permissions in Discord

**Issue**: Commands not syncing
- Bot internally calls `tree.sync()` on startup
- Wait a few seconds after starting

## Data Persistence Benefits
✅ Data survives bot restarts
✅ Multiple bot instances can share data
✅ Easy backups with MongoDB
✅ Scalable for adding more features
