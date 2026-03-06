"""
BRANVEE GOLD SIGNAL BOT - UPGRADED VERSION
Professional flow with login button and clean interface
"""

import logging
import sqlite3
import os
from datetime import datetime
import requests
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

BOT_TOKEN = os.environ.get('SIGNAL_BOT_TOKEN', '8233171599:AAGcqQQN3AoOOeOe_7w_0BXeyi0a9rpVIQE')
API_URL = os.environ.get('RAILWAY_API_URL', 'https://branvee-gold-system-production.up.railway.app')
DB_PATH = 'data/branvee.db'

# Stickers
STICKERS = {
    'BUY': 'CAACAgUAAxkBAAEQrM1pqHn0R0kEa_N26VvUd3ql5z2ALQAC8BAAAuyHeVQNfOSljHlxXToE',
    'SELL': 'CAACAgUAAxkBAAEQrM9pqHn3xrEok5y9PgRla3BDglVNRwACBBIAAyV4VL-svKl04_rUOgQ',
    'HOLD': 'CAACAgUAAxkBAAEQrNFpqHoAAYs3q4IclmTtzx1bM5jWTmMAAnMVAAJkTHlUfqdnK5jbckQ6BA'
}

os.makedirs('data', exist_ok=True)

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
# CONVERSATION STATES
# ============================================

EMAIL, TOKEN = range(2)

# ============================================
# START HANDLER
# ============================================

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start command - shows login button"""
    user_id = update.effective_user.id
    
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
    
    print("\n" + "="*60)
    print("🤖 BRANVEE SIGNAL BOT - UPGRADED VERSION")
    print("="*60)
    print("✅ Features:")
    print("   • Login button on /start")
    print("   • Professional welcome message")
    print("   • Account details with full info")
    print("   • Time remaining (days/hours/minutes)")
    print("   • Stickers for BUY/SELL/HOLD")
    print("   • GET SIGNAL button after each signal")
    print("="*60 + "\n")
    
    app.run_polling()

if __name__ == '__main__':
    main()