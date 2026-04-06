# Command Structure Guide

Your Discord bot commands are now organized into separate files for easy maintenance and access!

## 📁 Directory Structure

```
discord-bot/
├── reconcile_bot.py          # Main bot entry point (clean & minimal)
├── helpers.py                # Shared utilities & MongoDB functions
├── commands/                 # All commands organized by category
│   ├── __init__.py
│   ├── member_commands.py    # Guild & Bound member list commands
│   ├── commander_commands.py # Commander role management
│   ├── channel_commands.py   # Channel control commands
│   ├── moderation_commands.py# User discipline commands
│   ├── cleanup_commands.py   # Message cleanup commands
│   └── utility_commands.py   # Help and utility commands
├── .env                      # Environment variables (TOKEN, MONGO_URI)
├── requirments.txt           # Python dependencies
├── MONGODB_SETUP.md          # MongoDB setup guide
└── .gitignore               # Git ignore file
```

## 🎯 Finding Command Files

### **Member List Commands** → [commands/member_commands.py](commands/member_commands.py)
- `/members setguild <text>` - Store guild member list
- `/members setbound <text>` - Store bound member list
- `/members notbind` - Show unbound guild members
- `/members missing_player` - Show missing players
- `/members showdata` - Preview stored lists
- `/members update <type> <id> <name>` - Update player name
- `/members clear` - Clear all data
- `/members count` - Show member counts
- `/members export` - Export as CSV

### **Commander Management** → [commands/commander_commands.py](commands/commander_commands.py)
- `/addcommander <user>` - Promote user to Commander
- `/removecommander <user>` - Demote user from Commander
- `/listcommanders` - List all Commanders

### **Channel Control** → [commands/channel_commands.py](commands/channel_commands.py)
- `/lockchannel` - Lock the current channel
- `/unlockchannel` - Unlock the current channel

### **User Moderation** → [commands/moderation_commands.py](commands/moderation_commands.py)
- `/warn <user> <reason>` - Warn a user
- `/mute <user>` - Mute a user
- `/unmute <user>` - Unmute a user

### **Message Cleanup** → [commands/cleanup_commands.py](commands/cleanup_commands.py)
- `/prune <amount>` - Delete recent messages (1-100)
- `/pruneuser <user> <amount>` - Delete messages from specific user

### **Utility & Help** → [commands/utility_commands.py](commands/utility_commands.py)
- `/help` - Show all available commands

## 🔧 Helper Functions → [helpers.py](helpers.py)

Shared utility functions used by all commands:
- `get_channel_data(channel_id)` - Fetch data from MongoDB
- `update_channel_data(channel_id, ...)` - Save data to MongoDB
- `clear_channel_data(channel_id)` - Delete channel data
- `is_commander(interaction)` - Check user permissions
- `parse_member_lines(text, regex)` - Parse member list from text

## 📝 How to Add a New Command

### Step 1: Create a new Cog class in appropriate file
```python
class MyNewCommands(discord.Cog):
    def __init__(self, bot):
        self.bot = bot
    
    @app_commands.command(name="mycommand", description="...")
    async def mycommand(self, interaction: discord.Interaction):
        await interaction.response.send_message("Hello!")

async def setup(bot):
    await bot.add_cog(MyNewCommands(bot))
```

### Step 2: Load in main bot file
Add to `reconcile_bot.py` in `setup_hook()`:
```python
await self.load_cog('commands.my_commands')
```

## ✨ Key Features

✅ **Clean separation of concerns** - Each file handles one category  
✅ **Easy to navigate** - Find what you need quickly  
✅ **Modular design** - Add/remove commands without affecting others  
✅ **MongoDB persistence** - Data survives bot restarts  
✅ **Shared utilities** - DRY principle with helpers.py  
✅ **Proper error handling** - Cogs load with error feedback  

## 🚀 Running the Bot

```bash
# Install dependencies
pip install -r requirments.txt

# Set up environment
cp .env.example .env
# Edit .env with TOKEN and MONGO_URI

# Run the bot
python reconcile_bot.py
```

## 📚 To Learn More

- See [MONGODB_SETUP.md](MONGODB_SETUP.md) for database setup
- Each command file has docstrings explaining what it does
- Check `.env.example` for configuration

---

**Happy coding! 🎉**
