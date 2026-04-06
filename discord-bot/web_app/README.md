# Free Fire Guild Manager - Web Interface

A web-based interface for managing Free Fire guild data, warnings, and bans. This is a companion web application to the Discord bot.

## Features

### 🏰 Guild Management
- Update guild members with UID tracking
- Track member joins, leaves, and name changes
- Export guild data and history as CSV
- Automatic detection of globally banned players

### ⚠️ Warning System
- Add warnings to players by UID
- View warning history for specific players
- List all warned players with warning counts
- Export warning data as CSV

### 🚫 Ban Management
- Add channel-specific or global bans
- Track ban reasons and WhatsApp contact info
- Check ban status for any UID
- Export ban lists as CSV
- Global bans apply across all guilds (bot owner only)

## Installation

1. **Install Dependencies:**
   ```bash
   cd web_app
   pip install -r requirements.txt
   ```

2. **Database Setup:**
   The application automatically creates the necessary SQLite databases:
   - `../guild.db` - Guild member data (shared with Discord bot)
   - `../discord_bot.db` - Warnings and bans data (shared with Discord bot)

## Running the Application

```bash
cd web_app
python app.py
```

The web interface will be available at: `http://localhost:5000`

## Usage

### Guild Management
1. Navigate to the "Guild Management" page
2. Enter guild member data in the format: `PlayerName,UID`
3. Click "Update Guild" to process changes
4. Use export buttons to download CSV files

### Warning Management
1. Go to the "Warnings" page
2. Enter warning data in the format: `UID,Reason`
3. Click "Add Warnings" to process
4. Use the view buttons to check specific players or list all warned players

### Ban Management
1. Visit the "Bans" page
2. Enter ban data in the format: `UID,PlayerName,Reason,WhatsApp`
3. Check "Global Ban" for universal bans (bot owner only)
4. Use list and check functions to manage bans

## API Endpoints

- `GET /check-ban/<uid>` - Check if a UID is globally banned
- Returns JSON: `{"banned": true/false, "uid": 123456789}`

## Data Sharing

This web application shares databases with the Discord bot:
- Guild member data is synchronized
- Warnings and bans are shared
- Global bans are universal across both interfaces

## Security Notes

- Global ban management requires bot owner permissions
- Channel-specific data is isolated per Discord channel
- All data is stored locally in SQLite databases
- No external API calls are made

## File Structure

```
web_app/
├── app.py              # Main Flask application
├── requirements.txt    # Python dependencies
├── templates/          # HTML templates
│   ├── base.html       # Base template
│   ├── index.html      # Dashboard
│   ├── guild.html      # Guild management
│   ├── warnings.html   # Warning management
│   └── bans.html       # Ban management
└── README.md          # This file
```

## Support

This web interface provides the same functionality as the Discord bot commands:
- `/guildupdates` → Guild Management page
- `/warnuid` → Add Warnings section
- `/banuid` → Add Bans section
- `/export` → Export functions
- `/listwarnings` → List All Warned Players
- `/listbans` → List Bans function

All data is fully compatible between the Discord bot and web interface.