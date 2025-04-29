import discord
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
import os
import sys
import time
import json
from collections import defaultdict
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Log function for debugging
def log(message):
    print(f"[DEBUG] {message}")
    sys.stdout.flush()  # Force output to display immediately

log("Starting bot initialization...")

# Config file
CONFIG_FILE = os.environ.get("CONFIG_FILE_PATH", "expense_config.json")

# Load or create config
def load_config():
    default_config = {
        "user_emails": {}  # Discord user ID to email mapping
    }
    
    try:
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, 'r') as f:
                return json.load(f)
        else:
            with open(CONFIG_FILE, 'w') as f:
                json.dump(default_config, f)
            return default_config
    except Exception as e:
        log(f"Error loading config: {e}")
        return default_config

def save_config(config):
    try:
        with open(CONFIG_FILE, 'w') as f:
            json.dump(config, f)
    except Exception as e:
        log(f"Error saving config: {e}")

# Load config
config = load_config()
user_sheets = {}  # Map user IDs to their sheet info

# Discord intents and client
intents = discord.Intents.default()
intents.messages = True
intents.message_content = True  # Required to read message content
client = discord.Client(intents=intents)

# Google Sheets setup
log("Setting up Google Sheets connection...")
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]

try:
    # Get credentials from environment variables
    creds_dict = {
        "type": "service_account",
        "project_id": os.environ.get("GOOGLE_SHEET_PROJECT_ID"),
        "private_key_id": os.environ.get("GOOGLE_SHEET_PRIVATE_KEY_ID"),
        "private_key": os.environ.get("GOOGLE_SHEET_PRIVATE_KEY").replace('\\n', '\n'),
        "client_email": os.environ.get("GOOGLE_SHEET_CLIENT_EMAIL"),
        "client_id": "",
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": "https://oauth2.googleapis.com/token",
        "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
        "client_x509_cert_url": f"https://www.googleapis.com/robot/v1/metadata/x509/{os.environ.get('GOOGLE_SHEET_CLIENT_EMAIL').replace('@', '%40')}",
        "universe_domain": "googleapis.com"
    }
    
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    log("Successfully loaded credentials from environment variables")
    log(f"Service account email: {creds.service_account_email}")
except Exception as e:
    log(f"ERROR loading credentials: {str(e)}")
    raise

try:
    client_gsheets = gspread.authorize(creds)
    log("Successfully authorized with Google Sheets API")
except Exception as e:
    log(f"ERROR authorizing with Google Sheets: {str(e)}")
    raise

# Create a function to handle sheet setup for a user
def setup_sheet_for_user(user_id, user_email=None):
    try:
        # Create unique sheet name for this user
        timestamp = int(time.time())
        user_sheet_name = f"ExpenseTracker_{user_id}_{timestamp}"
        log(f"Creating sheet for user {user_id}: {user_sheet_name}")
        
        # Create the sheet
        workbook = client_gsheets.create(user_sheet_name)
        sheet = workbook.sheet1
        
        # Add headers to the sheet
        sheet.append_row(["Date", "Category", "Amount"])
        log("Added headers to new sheet")
        
        # Share with user email if provided
        if user_email:
            log(f"Sharing sheet with: {user_email}")
            try:
                workbook.share(user_email, perm_type='user', role='writer', notify=True)
                log(f"Successfully shared sheet with {user_email} as editor")
            except Exception as share_error:
                log(f"Error sharing with email: {str(share_error)}")
        
        # Make it accessible to anyone with the link (read-only)
        try:
            workbook.share('', perm_type='anyone', role='reader')
            log("Successfully made sheet accessible to anyone with the link")
        except Exception as public_error:
            log(f"Error making sheet public: {str(public_error)}")
        
        sheet_id = workbook.id
        direct_url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/edit"
        log(f"Sheet created. Sheet ID: {sheet_id}")
        log(f"DIRECT ACCESS URL: {direct_url}")
        
        # Store sheet info in config
        config["user_emails"][user_id] = {
            "email": user_email,
            "sheet_id": sheet_id,
            "sheet_url": direct_url
        }
        save_config(config)
        
        # Return sheet object and URL
        return sheet, direct_url
    except Exception as e:
        log(f"ERROR creating sheet for user {user_id}: {str(e)}")
        raise

# Get expense summary for a user
def get_expense_summary(sheet, limit=5):
    try:
        # Get all records (skipping header row)
        records = sheet.get_all_records()
        
        # If no records, return empty summary
        if not records:
            return "No expenses recorded yet."
        
        # Calculate total
        total = sum(float(record["Amount"]) for record in records)
        
        # Group by category
        categories = defaultdict(float)
        for record in records:
            categories[record["Category"]] += float(record["Amount"])
        
        # Get recent expenses (up to limit)
        recent = records[-limit:] if len(records) > limit else records
        recent.reverse()  # Most recent first
        
        # Format the summary
        summary = f"📊 **Expense Summary**\n\n"
        
        # Recent expenses
        summary += "**Recent Expenses:**\n"
        for record in recent:
            date = record["Date"].split()[0]  # Just get the date part
            summary += f"• {date}: {record['Category']} - ₹{record['Amount']}\n"
        
        # Category breakdown
        summary += "\n**By Category:**\n"
        for category, amount in sorted(categories.items(), key=lambda x: x[1], reverse=True):
            percent = (amount / total) * 100
            summary += f"• {category}: ₹{amount:.2f} ({percent:.1f}%)\n"
        
        # Total
        summary += f"\n**Total Expenses:** ₹{total:.2f}"
        
        return summary
    except Exception as e:
        log(f"Error generating summary: {str(e)}")
        return f"Error generating summary: {str(e)}"

@client.event
async def on_ready():
    log(f'Logged in as {client.user}')

# Track first interactions with users
first_time_users = set()

@client.event
async def on_message(message):
    if message.author == client.user:
        return
    
    # Only respond to DMs
    if isinstance(message.channel, discord.DMChannel):
        user_id = str(message.author.id)
        log(f"Received DM from user {user_id}: {message.content}")
        
        # Send welcome message for first-time users
        if user_id not in first_time_users and user_id not in config["user_emails"]:
            first_time_users.add(user_id)
            welcome_message = (
                f"👋 **Welcome to the Expense Tracker Bot!**\n\n"
                f"I help you track your expenses by logging them to a Google Sheet.\n\n"
                f"**Getting Started:**\n"
                f"1️⃣ Set up with: `!setup your.email@example.com`\n"
                f"2️⃣ Log expenses with: `Category Amount` (e.g., `Food 250`)\n"
                f"3️⃣ View your sheet with: `!url`\n\n"
                f"Type `!help` anytime to see all commands."
            )
            await message.channel.send(welcome_message)
            # If the user sent a command, continue processing it
            # If not, wait for them to send a proper command
            if not message.content.startswith("!") and not any(cmd in message.content.lower() for cmd in ["help", "setup"]):
                return
        
        # Check for setup command: !setup your.email@example.com
        if message.content.lower().startswith("!setup "):
            parts = message.content.strip().split(maxsplit=1)
            if len(parts) == 2 and "@" in parts[1]:
                user_email = parts[1].strip()
                log(f"Setting up user {user_id} with email {user_email}")
                
                try:
                    sheet, url = setup_sheet_for_user(user_id, user_email)
                    user_sheets[user_id] = sheet
                    
                    setup_message = (
                        f"✅ Setup complete! Your expenses will be logged to:\n{url}\n\n"
                        f"📝 To log an expense, send: Category Amount\n"
                        f"🔗 To get your sheet link: !url\n"
                        f"📊 To see your expense summary: !summary"
                    )
                    await message.channel.send(setup_message)
                except Exception as e:
                    await message.channel.send(f"❌ Error setting up your expense sheet: {str(e)}")
                return
        
        # Get or check if user is set up
        user_sheet = None
        if user_id in user_sheets:
            user_sheet = user_sheets[user_id]
        elif user_id in config["user_emails"]:
            # Try to load from config
            try:
                sheet_id = config["user_emails"][user_id]["sheet_id"]
                workbook = client_gsheets.open_by_key(sheet_id)
                user_sheet = workbook.sheet1
                user_sheets[user_id] = user_sheet
                log(f"Loaded existing sheet for user {user_id}")
            except Exception as e:
                log(f"Error loading saved sheet for user {user_id}: {str(e)}")
        
        # Handle URL command
        if message.content.lower() in ["!sheet", "!url", "!link"]:
            if user_id in config["user_emails"]:
                url = config["user_emails"][user_id]["sheet_url"]
                await message.channel.send(f"Here's the link to your expense sheet: {url}")
            else:
                await message.channel.send(
                    "You haven't set up your expense tracking yet! Use:\n"
                    "!setup your.email@example.com"
                )
            return
        
        # Handle summary command
        if message.content.lower() in ["!summary", "!expenses", "!stats"]:
            if not user_sheet:
                await message.channel.send(
                    "You need to set up your expense tracking first! Use:\n"
                    "!setup your.email@example.com"
                )
                return
                
            await message.channel.send("Generating your expense summary... 📊")
            summary = get_expense_summary(user_sheet)
            await message.channel.send(summary)
            return
        
        # Handle help command
        if message.content.lower() in ["!help", "help", "!commands"]:
            help_text = (
                "📋 **Expense Tracker Bot Commands:**\n\n"
                "**Setup Commands:**\n"
                "• `!setup your.email@example.com` - Set up your personal expense sheet\n"
                "• `!url` or `!sheet` or `!link` - Get link to your expense sheet\n\n"
                "**Expense Logging:**\n"
                "• `Category Amount` - Log an expense (e.g., `Food 250`, `Gas 45.50`)\n"
                "• Categories can be anything you choose (Food, Transport, Rent, etc.)\n\n"
                "**Analysis:**\n"
                "• `!summary` - View a summary of your expenses\n\n"
                "**Examples:**\n"
                "• `Food 120.50` - Logs a food expense of ₹120.50\n"
                "• `Transport 50` - Logs a transport expense of ₹50\n"
                "• `Coffee 30` - Logs a coffee expense of ₹30\n\n"
                "**Other Commands:**\n"
                "• `!help` - Show this help message\n"
            )
            await message.channel.send(help_text)
            return
        
        # If user not set up, prompt them
        if not user_sheet:
            await message.channel.send(
                "You need to set up your expense tracking first! Use:\n"
                "!setup your.email@example.com"
            )
            return
            
        # Process expense
        try:
            parts = message.content.strip().split()
            if len(parts) != 2:
                await message.channel.send("Please use format: Category Amount (e.g. Food 250)")
                return

            category = parts[0]
            amount = float(parts[1])
            date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            # Append to Google Sheet
            log(f"Saving expense for user {user_id}: {date}, {category}, {amount}")
            user_sheet.append_row([date, category, amount])
            log("Successfully saved to Google Sheet")
            
            await message.channel.send(f"Logged: {category} - ₹{amount}")
        except Exception as e:
            error_msg = str(e)
            log(f"ERROR processing message: {error_msg}")
            await message.channel.send(f"Error: {error_msg}")

# Start the bot
TOKEN = os.environ.get("DISCORD_TOKEN")
if not TOKEN:
    log("ERROR: Discord token not found in environment variables!")
    sys.exit(1)

log("Starting Discord bot...")
client.run(TOKEN)
