# Discord Expense Tracker Bot

A Discord bot that helps users track their expenses by logging them to personalized Google Sheets.

## Features

- **Personal Expense Tracking**: Each user gets their own Google Sheet
- **Easy Logging**: Simply type a category and amount to log an expense
- **Real-time Updates**: Expenses are logged immediately
- **Summary Statistics**: Get a summary of your spending by category
- **Secure Authentication**: Uses Discord DMs for private expense tracking

## Setup Instructions

### Prerequisites

- Python 3.8+
- A Discord application and bot token
- Google Cloud project with Sheets API enabled
- Service account with appropriate permissions

### Environment Setup

1. Clone this repository
   ```
   git clone https://github.com/yourusername/expense-tracker-bot.git
   cd expense-tracker-bot
   ```

2. Install dependencies
   ```
   pip install -r requirements.txt
   ```

3. Create a `.env` file with the following variables:
   ```
   DISCORD_TOKEN=your_discord_bot_token
   GOOGLE_SHEET_PROJECT_ID=your_google_project_id
   GOOGLE_SHEET_PRIVATE_KEY_ID=your_private_key_id
   GOOGLE_SHEET_PRIVATE_KEY="your_private_key"
   GOOGLE_SHEET_CLIENT_EMAIL=your_service_account_email
   CONFIG_FILE_PATH=expense_config.json
   ```

### Running the Bot

```
python bot.py
```

## User Commands

- `!setup your.email@example.com` - Set up personal expense sheet
- `Category Amount` - Log an expense (e.g., `Food 250`)
- `!summary` - View expense summary
- `!url` - Get link to your expense sheet
- `!help` - Show help message

## Developer Notes

- The `expense_config.json` file stores user to sheet mappings
- Each user's expenses are private and stored in their own Google Sheet
- The bot only responds to direct messages for privacy
