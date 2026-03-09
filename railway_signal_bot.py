"""
BRANVEE GOLD SIGNAL BOT - UPGRADED VERSION WITH ADMIN MESSAGES
Professional flow with login button, clean interface, and admin broadcast receiver
"""

import logging
import sqlite3
import os
from datetime import datetime, timedelta
import requests
import pytz  # Added for timezone handling
import re
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
    ConversationHandler,
    ContextTypes
)

# ============================================
# CONFIGURATION
# ============================================

BOT_TOKEN = os.environ.get('SIGNAL_BOT_TOKEN', '8381499817:AAF4Aow7qa8JVRQ3WJrSoqH5D-DSt-FuljU')
API_URL = os.environ.get('RAILWAY_API_URL', 'https://branvee-gold-system-production.up.railway.app')
DB_PATH = 'data/branvee.db'
ADMIN_ID = 6980711942  # Your admin ID - add this

# Stickers
STICKERS = {
    'BUY': 'CAACAgUAAxkBAAEQrM1pqHn0R0kEa_N26VvUd3ql5z2ALQAC8BAAAuyHeVQNfOSljHlxXToE',
    'SELL': 'CAACAgUAAxkBAAEQrM9pqHn3xrEok5y9PgRla3BDglVNRwACBBIAAyV4VL-svKl04_rUOgQ',
    'HOLD': 'CAACAgUAAxkBAAEQrNFpqHoAAYs3q4IclmTtzx1bM5jWTmMAAnMVAAJkTHlUfqdnK5jbckQ6BA'
}

os.makedirs('data', exist_ok=True)

# ============================================
# MARKET HOURS FILTER
# ============================================

def is_market_open():
    """Check if gold market is currently open"""
    # Get current time in GMT
    gmt_tz = pytz.timezone('GMT')
    now = datetime.now(gmt_tz)
    
    # Get day of week (0=Monday, 6=Sunday)
    day = now.weekday()
    hour = now.hour
    
    # Market closed: Friday 22:00 GMT to Sunday 23:00 GMT
    if day == 4:  # Friday
        if hour >= 22:  # 22:00 or later
            return False
    elif day == 5:  # Saturday
        return False
    elif day == 6:  # Sunday
        if hour < 23:  # Before 23:00
            return False
    
    return True

def get_market_closed_message():
    """Get styled market closed message"""
    gmt_tz = pytz.timezone('GMT')
    now = datetime.now(gmt_tz)
    
    # Calculate next open time
    if now.weekday() == 4 and now.hour >= 22:  # Friday after 22:00
        next_open = now + timedelta(days=2)  # Sunday
        next_open = next_open.replace(hour=23, minute=0, second=0, microsecond=0)
    elif now.weekday() == 5:  # Saturday
        days_until_sunday = 1
        next_open = now + timedelta(days=days_until_sunday)
        next_open = next_open.replace(hour=23, minute=0, second=0, microsecond=0)
    elif now.weekday() == 6 and now.hour < 23:  # Sunday before 23:00
        next_open = now.replace(hour=23, minute=0, second=0, microsecond=0)
    else:
        next_open = now + timedelta(hours=1)  # Fallback
    
    # Format time remaining
    time_remaining = next_open - now
    hours = int(time_remaining.total_seconds() // 3600)
    minutes = int((time_remaining.total_seconds() % 3600) // 60)
    
    # Styled message with box drawing characters
    message = (
        "╔══════════════════════════════╗\n"
        "║     🚫 MARKET CLOSED 🚫      ║\n"
        "╠══════════════════════════════╣\n"
        "║ Gold market is currently     ║\n"
        "║ closed for the weekend.      ║\n"
        "║                              ║\n"
        "║ 📅 Next Open:                 ║\n"
        f"║    {next_open.strftime('%A %H:%M')} GMT   ║\n"
        "║                              ║\n"
        f"║ ⏳ Time remaining:            ║\n"
        f"║    {hours}h {minutes}m        ║\n"
        "╚══════════════════════════════╝\n\n"
        "💤 Please check back when market opens."
    )
    
    return message

# ============================================
# ACCOUNT STATUS CHECK
# ============================================

async def check_account_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Check if user account is active, if not force re-login"""
    user_id = update.effective_user.id
    
    # Check if user is in session
    if 'user_id' not in context.user_data:
        return False
    
    db_user = get_user_by_id(context.user_data['user_id'])
    
    # If user not found in DB or was deleted
    if not db_user:
        await force_relogin(update, context, "Account not found. Please login again.")
        return False
    
    # Check if suspended
    if db_user['is_suspended'] == 1:
        await force_relogin(update, context, "Your account has been suspended. Please contact admin and login again.")
        return False
    
    # Check if expired
    now = datetime.now().isoformat()
    if db_user['expires_at'] < now:
        await force_relogin(update, context, "Your subscription has expired. Please renew and login again.")
        return False
    
    return True

async def force_relogin(update: Update, context: ContextTypes.DEFAULT_TYPE, message: str):
    """Force user to re-login by clearing session and showing login button"""
    # Clear user session
    context.user_data.clear()
    
    # Show login button
    keyboard = [[InlineKeyboardButton("🔐 LOGIN TO YOUR ACCOUNT", callback_data='start_login')]]
    
    # Handle both callback queries and direct messages
    if update.callback_query:
        await update.callback_query.edit_message_text(
            f"⚠️ **{message}**\n\n"
            f"Please login again to continue.",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
    else:
        await update.message.reply_text(
            f"⚠️ **{message}**\n\n"
            f"Please login again to continue.",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )

# ============================================
# DATABASE FUNCTIONS
# ============================================

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        email TEXT UNIQUE NOT NULL,
        token TEXT UNIQUE NOT NULL,
        telegram_id INTEGER,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        expires_at TIMESTAMP NOT NULL,
        is_suspended BOOLEAN DEFAULT 0
    )''')
    conn.commit()
    conn.close()
    print("✅ Database initialized")

def get_user_by_email(email):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute('SELECT * FROM users WHERE LOWER(email) = LOWER(?)', (email,))
    user = c.fetchone()
    conn.close()
    return user

def get_user_by_id(user_id):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute('SELECT * FROM users WHERE id = ?', (user_id,))
    user = c.fetchone()
    conn.close()
    return user

def get_user_by_telegram(telegram_id):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute('SELECT * FROM users WHERE telegram_id = ?', (telegram_id,))
    user = c.fetchone()
    conn.close()
    return user

def link_telegram_id(user_id, telegram_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('UPDATE users SET telegram_id = ? WHERE id = ?', (telegram_id, user_id))
    conn.commit()
    conn.close()
    return True

def validate_email(email):
    return '@' in email and '.' in email

# ============================================
# ADMIN MESSAGE HANDLER - NEW FUNCTION
# ============================================

async def handle_admin_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle incoming messages - detect if they're from admin or regular"""
    user_id = update.effective_user.id
    message_text = update.message.text
    
    # If message is from admin ID, don't process (admin uses admin bot)
    if user_id == ADMIN_ID:
        return
    
    # Check if message is an admin broadcast
    if is_admin_message(message_text):
        # Show admin message in a nice format
        await show_admin_broadcast(update, message_text)
        return
    
    # Check if user is logged in
    if 'user_id' not in context.user_data:
        # Not logged in, show login button
        await handle_non_logged_in(update)
        return
    
    # Check account status
    if not await check_account_status(update, context):
        return
    
    # If user is logged in but sent a message, handle appropriately
    if message_text.upper() in ['SELL', 'BUY', 'HOLD', 'GET SIGNAL', 'SIGNAL']:
        # Handle as signal request
        await handle_signal_request(update, context)
    else:
        # Unknown message, show menu
        await show_main_menu_after_message(update, context)

def is_admin_message(text):
    """Check if message is from admin broadcast"""
    # Look for patterns in admin messages
    patterns = [
        r'^Dear .*?,',
        r'Branvee Gold System$',
        r'---\nBranvee Gold System'
    ]
    
    for pattern in patterns:
        if re.search(pattern, text, re.MULTILINE):
            return True
    return False

async def show_admin_broadcast(update: Update, message_text: str):
    """Display admin broadcast messages in a nice format"""
    
    # Extract the actual message if possible
    # Format: Dear email,\n\nMESSAGE\n\n---\nBranvee Gold System
    match = re.search(r'Dear .*?,\n\n(.*?)\n\n---', message_text, re.DOTALL)
    
    if match:
        actual_message = match.group(1)
        display_text = (
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "📢 **ADMIN ANNOUNCEMENT** 📢\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"{actual_message}\n\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "_From Branvee Gold Admin_"
        )
    else:
        # If format is different, just show as is
        display_text = (
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "📢 **MESSAGE FROM ADMIN** 📢\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"{message_text}\n\n"
            "━━━━━━━━━━━━━━━━━━━━━━"
        )
    
    # Add a button to get back to main menu
    keyboard = [[InlineKeyboardButton("🏠 BACK TO MAIN MENU", callback_data='home_menu')]]
    
    await update.message.reply_text(
        display_text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )

async def handle_non_logged_in(update: Update):
    """Handle messages from users who aren't logged in"""
    keyboard = [[InlineKeyboardButton("🔐 LOGIN TO YOUR ACCOUNT", callback_data='start_login')]]
    
    await update.message.reply_text(
        "🔒 **Please login first**\n\n"
        "You need to login to access the signal bot.",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )

async def handle_signal_request(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle direct signal requests from logged-in users"""
    # Check if market is open
    if not is_market_open():
        await update.message.reply_text(
            get_market_closed_message(),
            parse_mode='Markdown'
        )
        return
    
    # Send "fetching" message
    loading_msg = await update.message.reply_text("🔄 Fetching signal...")
    
    try:
        # Fetch signal from API
        response = requests.get(f"{API_URL}/api/signal", timeout=5)
        data = response.json()
        signal = data.get('signal', 'HOLD').upper()
        
        # Send sticker
        sticker = STICKERS.get(signal, STICKERS['HOLD'])
        await update.message.reply_sticker(sticker)
        
        # Show continuation buttons
        keyboard = [
            [InlineKeyboardButton("📊 GET SIGNAL", callback_data='get_signal')],
            [InlineKeyboardButton("🏠 HOME", callback_data='home_menu')]
        ]
        
        await update.message.reply_text(
            f"✅ Signal received!\n\nWhat would you like to do?",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        
        # Delete loading message
        await loading_msg.delete()
        
    except Exception as e:
        await loading_msg.edit_text("❌ Error fetching signal. Please try again.")
        logging.error(f"Signal error: {e}")

async def show_main_menu_after_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show main menu after receiving an unknown message"""
    user_id = context.user_data.get('user_id')
    if not user_id:
        return
    
    user = get_user_by_id(user_id)
    if not user:
        return
    
    keyboard = [
        [InlineKeyboardButton("📊 GET SIGNAL", callback_data='get_signal')],
        [InlineKeyboardButton("👤 ACCOUNT DETAILS", callback_data='account_info')]
    ]
    
    await update.message.reply_text(
        "🤖 **BRANVEE XAUUSD SCALP AI** 🤖\n\n"
        "Select an option below:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )

# ============================================
# CONVERSATION STATES
# ============================================

EMAIL, TOKEN = range(2)

# ============================================
# START HANDLER
# ============================================

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start command - shows login button"""
    user_id = update.effective_user.id
    
    # If it's admin, don't show login (admin uses admin bot)
    if user_id == ADMIN_ID:
        await update.message.reply_text("👋 Welcome Admin! Please use the admin bot.")
        return
    
    # Check if already logged in
    existing_user = get_user_by_telegram(user_id)
    if existing_user:
        # User already logged in, go to main menu
        context.user_data['user_id'] = existing_user['id']
        context.user_data['email'] = existing_user['email']
        context.user_data['expires_at'] = existing_user['expires_at']
        await show_welcome_back(update, existing_user)
        return ConversationHandler.END
    
    # Show login button
    keyboard = [
        [InlineKeyboardButton("🔐 LOGIN TO YOUR ACCOUNT", callback_data='start_login')]
    ]
    
    await update.message.reply_text(
        "🤖 **BRANVEE XAUUSD SCALP AI** 🤖\n\n"
        "Welcome to the advanced XAUUSD scalping system.\n\n"
        "Please tap the button below to access your account:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )
    return ConversationHandler.END

async def show_welcome_back(update, user):
    """Show welcome back message for returning users"""
    expiry = datetime.fromisoformat(user['expires_at'])
    now = datetime.now()
    
    if expiry > now:
        days_left = (expiry - now).days
        hours_left = ((expiry - now).seconds // 3600)
        time_left = f"{days_left} days, {hours_left} hours" if days_left > 0 else f"{hours_left} hours"
    else:
        time_left = "EXPIRED"
    
    welcome_msg = (
        f"🤖 **WELCOME BACK TO BRANVEE XAUUSD SCALP AI** 🤖\n\n"
        f"📧 **Email:** {user['email']}\n"
        f"⏳ **Time Remaining:** {time_left}\n"
        f"🔒 **Account Status:** {'✅ Active' if expiry > now else '❌ Expired'}\n\n"
        f"Select an option below:"
    )
    
    keyboard = [
        [InlineKeyboardButton("📊 GET SIGNAL", callback_data='get_signal')],
        [InlineKeyboardButton("👤 ACCOUNT DETAILS", callback_data='account_info')]
    ]
    
    await update.message.reply_text(
        welcome_msg,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )

# ============================================
# LOGIN FLOW
# ============================================

async def login_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle login button click"""
    query = update.callback_query
    await query.answer()
    
    if query.data == 'start_login':
        context.user_data['login_state'] = 'email'
        await query.edit_message_text(
            "📧 **LOGIN**\n\nPlease enter your registered email address:",
            parse_mode='Markdown'
        )
        return EMAIL

async def handle_email(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle email input"""
    email = update.message.text.strip()
    telegram_id = update.effective_user.id
    
    if not validate_email(email):
        await update.message.reply_text("❌ Invalid email format. Please try again:")
        return EMAIL
    
    user = get_user_by_email(email)
    
    if not user:
        await update.message.reply_text("❌ Email not registered. Contact admin.")
        return EMAIL
    
    if user['is_suspended']:
        await update.message.reply_text("❌ Account suspended. Contact admin.")
        return EMAIL
    
    now = datetime.now().isoformat()
    if user['expires_at'] < now:
        await update.message.reply_text("⚠️ Your subscription has expired. Contact admin to renew.")
        return EMAIL
    
    if user['telegram_id'] and user['telegram_id'] != telegram_id:
        await update.message.reply_text(
            "❌ This account is already linked to another Telegram user.\n"
            "Contact admin if you believe this is an error."
        )
        return EMAIL
    
    context.user_data['auth_user'] = {
        'id': user['id'],
        'email': user['email'],
        'token': user['token'],
        'expires_at': user['expires_at']
    }
    context.user_data['telegram_id'] = telegram_id
    
    await update.message.reply_text(
        f"✅ Email verified: {user['email']}\n\n"
        f"Now enter your activation code:"
    )
    return TOKEN

async def handle_token(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle token input"""
    token = update.message.text.strip().upper()
    user_data = context.user_data.get('auth_user')
    telegram_id = context.user_data.get('telegram_id')
    
    if not user_data:
        await update.message.reply_text("❌ Session expired. Please /start again.")
        return ConversationHandler.END
    
    if user_data['token'] != token:
        await update.message.reply_text("❌ Invalid activation code. Try again:")
        return TOKEN
    
    # Link Telegram ID if first time
    if not get_user_by_telegram(telegram_id):
        link_telegram_id(user_data['id'], telegram_id)
    
    # Store in session
    context.user_data['user_id'] = user_data['id']
    context.user_data['email'] = user_data['email']
    context.user_data['expires_at'] = user_data['expires_at']
    
    # Calculate time remaining
    expiry = datetime.fromisoformat(user_data['expires_at'])
    now = datetime.now()
    days_left = (expiry - now).days
    hours_left = ((expiry - now).seconds // 3600)
    
    if days_left > 0:
        time_left = f"{days_left} days, {hours_left} hours"
    else:
        time_left = f"{hours_left} hours"
    
    # Success message
    await update.message.reply_text(
        f"✅ **LOGIN SUCCESSFUL!** ✅\n\n"
        f"🤖 Welcome to BRANVEE XAUUSD SCALP AI\n\n"
        f"📧 **Email:** {user_data['email']}\n"
        f"⏳ **Time Remaining:** {time_left}\n"
        f"🔒 **Account locked to this Telegram**",
        parse_mode='Markdown'
    )
    
    # Show main menu
    await show_main_menu(update, context)
    return ConversationHandler.END

# ============================================
# MAIN MENU
# ============================================

async def show_main_menu(update, context):
    """Show main menu with GET SIGNAL and ACCOUNT DETAILS"""
    keyboard = [
        [InlineKeyboardButton("📊 GET SIGNAL", callback_data='get_signal')],
        [InlineKeyboardButton("👤 ACCOUNT DETAILS", callback_data='account_info')]
    ]
    
    await update.message.reply_text(
        "🤖 **BRANVEE XAUUSD SCALP AI** 🤖\n\n"
        "Select an option below:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )

# ============================================
# ACCOUNT DETAILS
# ============================================

async def account_info_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show detailed account information"""
    query = update.callback_query
    await query.answer()
    
    # Check account status first
    if not await check_account_status(update, context):
        return
    
    user_id = context.user_data.get('user_id')
    if not user_id:
        await query.edit_message_text("Session expired. Please /start again.")
        return
    
    user = get_user_by_id(user_id)
    if not user:
        await query.edit_message_text("Error retrieving account.")
        return
    
    # Calculate time remaining
    expiry = datetime.fromisoformat(user['expires_at'])
    now = datetime.now()
    
    if expiry > now:
        days = (expiry - now).days
        hours = ((expiry - now).seconds // 3600)
        minutes = ((expiry - now).seconds % 3600) // 60
        
        if days > 0:
            duration = f"{days} days, {hours} hours"
        elif hours > 0:
            duration = f"{hours} hours, {minutes} minutes"
        else:
            duration = f"{minutes} minutes"
        
        status = "✅ ACTIVE"
    else:
        duration = "EXPIRED"
        status = "❌ EXPIRED"
    
    # Format dates
    created = user['created_at'][:10] if user['created_at'] else "N/A"
    expires = user['expires_at'][:10] if user['expires_at'] else "N/A"
    
    account_msg = (
        f"👤 **ACCOUNT DETAILS**\n\n"
        f"📧 **Email:** `{user['email']}`\n"
        f"🔑 **Activation Code:** `{user['token']}`\n"
        f"🆔 **Telegram ID:** `{user['telegram_id'] or 'Not linked'}`\n"
        f"📊 **Status:** {status}\n"
        f"📅 **Created:** {created}\n"
        f"⏳ **Expires:** {expires}\n"
        f"⌛ **Time Remaining:** {duration}\n\n"
        f"🔒 This account is locked to Telegram ID: `{user['telegram_id']}`"
    )
    
    keyboard = [
        [InlineKeyboardButton("📊 GET SIGNAL", callback_data='get_signal')],
        [InlineKeyboardButton("🏠 HOME", callback_data='home_menu')]
    ]
    
    await query.edit_message_text(
        account_msg,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )

# ============================================
# SIGNAL HANDLER
# ============================================

async def signal_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle get signal button"""
    query = update.callback_query
    await query.answer()
    
    # Check if market is open
    if not is_market_open():
        closed_message = get_market_closed_message()
        keyboard = [[InlineKeyboardButton("🏠 HOME", callback_data='home_menu')]]
        await query.edit_message_text(
            closed_message,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
        return
    
    # Check account status
    if not await check_account_status(update, context):
        return
    
    user_id = context.user_data.get('user_id')
    if not user_id:
        await query.edit_message_text("Session expired. Please /start again.")
        return
    
    # Check if still active
    user = get_user_by_id(user_id)
    if not user or user['is_suspended']:
        await query.edit_message_text("Your account is not active. Contact admin.")
        return
    
    now = datetime.now().isoformat()
    if user['expires_at'] < now:
        await query.edit_message_text("⚠️ Your subscription has expired. Contact admin to renew.")
        return
    
    # Show loading
    await query.edit_message_text("🔄 Fetching signal...")
    
    try:
        # Fetch signal from API
        response = requests.get(f"{API_URL}/api/signal", timeout=5)
        data = response.json()
        signal = data.get('signal', 'HOLD').upper()
        
        # Send sticker
        sticker = STICKERS.get(signal, STICKERS['HOLD'])
        await query.message.reply_sticker(sticker)
        
        # Show continuation buttons
        keyboard = [
            [InlineKeyboardButton("📊 GET SIGNAL", callback_data='get_signal')],
            [InlineKeyboardButton("🏠 HOME", callback_data='home_menu')]
        ]
        
        await query.message.reply_text(
            f"✅ Signal received!\n\nWhat would you like to do?",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        
        # Delete loading message
        await query.message.delete()
        
    except Exception as e:
        await query.edit_message_text("❌ Error fetching signal. Please try again.")
        logging.error(f"Signal error: {e}")

# ============================================
# HOME MENU
# ============================================

async def home_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Return to home menu"""
    query = update.callback_query
    await query.answer()
    
    user_id = context.user_data.get('user_id')
    if not user_id:
        await query.edit_message_text("Session expired. Please /start again.")
        return
    
    user = get_user_by_id(user_id)
    if not user:
        await query.edit_message_text("Error retrieving account.")
        return
    
    # Calculate time remaining for welcome message
    expiry = datetime.fromisoformat(user['expires_at'])
    now = datetime.now()
    
    if expiry > now:
        days_left = (expiry - now).days
        hours_left = ((expiry - now).seconds // 3600)
        time_left = f"{days_left} days, {hours_left} hours" if days_left > 0 else f"{hours_left} hours"
    else:
        time_left = "EXPIRED"
    
    welcome_msg = (
        f"🤖 **BRANVEE XAUUSD SCALP AI** 🤖\n\n"
        f"📧 **Email:** {user['email']}\n"
        f"⏳ **Time Remaining:** {time_left}\n\n"
        f"Select an option below:"
    )
    
    keyboard = [
        [InlineKeyboardButton("📊 GET SIGNAL", callback_data='get_signal')],
        [InlineKeyboardButton("👤 ACCOUNT DETAILS", callback_data='account_info')]
    ]
    
    await query.edit_message_text(
        welcome_msg,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )

# ============================================
# CANCEL
# ============================================

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cancel operation"""
    await update.message.reply_text("❌ Operation cancelled.")
    return ConversationHandler.END

# ============================================
# MAIN
# ============================================

def main():
    """Start the bot"""
    init_db()
    
    app = Application.builder().token(BOT_TOKEN).build()
    
    # Conversation handler for login flow
    conv_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(login_callback, pattern='^start_login$')],
        states={
            EMAIL: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_email)],
            TOKEN: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_token)],
        },
        fallbacks=[CommandHandler('cancel', cancel)],
        allow_reentry=True
    )
    app.add_handler(conv_handler)
    
    # Command handlers
    app.add_handler(CommandHandler('start', start_command))
    
    # Callback handlers
    app.add_handler(CallbackQueryHandler(signal_callback, pattern='^get_signal$'))
    app.add_handler(CallbackQueryHandler(account_info_callback, pattern='^account_info$'))
    app.add_handler(CallbackQueryHandler(home_callback, pattern='^home_menu$'))
    
    # ADD THIS: Message handler for all text messages (including admin broadcasts)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_admin_message))
    
    print("\n" + "="*60)
    print("🤖 BRANVEE SIGNAL BOT - WITH ADMIN MESSAGES")
    print("="*60)
    print("✅ Features:")
    print("   • Login button on /start")
    print("   • Professional welcome message")
    print("   • Account details with full info")
    print("   • Time remaining (days/hours/minutes)")
    print("   • Stickers for BUY/SELL/HOLD")
    print("   • GET SIGNAL button after each signal")
    print("   • MARKET HOURS - Shows closed on weekends")
    print("   • AUTO RE-LOGIN - For suspended/expired accounts")
    print("   • 📢 ADMIN MESSAGES - Now receives broadcasts!")
    print("="*60 + "\n")
    
    app.run_polling()

if __name__ == '__main__':
    main()