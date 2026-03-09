"""
BRANVEE ADMIN BOT - COMPLETE VERSION
Full user management with hours/days/weeks/months expiry
"""

import logging
import sqlite3
import os
from datetime import datetime, timedelta
import random
import string
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

BOT_TOKEN = os.environ.get('ADMIN_BOT_TOKEN', '8673278512:AAEpXTJOPNeTNpnyag7KL61qbqiQ1adWnUM')
ADMIN_ID = int(os.environ.get('ADMIN_ID', 6980711942))
DB_PATH = 'data/branvee.db'

os.makedirs('data', exist_ok=True)

# ============================================
# DATABASE FUNCTIONS
# ============================================

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    # Users table
    c.execute('''CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        email TEXT UNIQUE NOT NULL,
        token TEXT UNIQUE NOT NULL,
        telegram_id INTEGER,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        expires_at TIMESTAMP NOT NULL,
        is_suspended BOOLEAN DEFAULT 0,
        created_by INTEGER,
        notes TEXT
    )''')
    
    # Renewal history
    c.execute('''CREATE TABLE IF NOT EXISTS renewal_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        old_expiry TIMESTAMP,
        new_expiry TIMESTAMP,
        renewed_by INTEGER,
        renewed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')
    
    # Add test user if none exists
    c.execute("SELECT COUNT(*) FROM users")
    if c.fetchone()[0] == 0:
        test_expiry = (datetime.now() + timedelta(days=30)).isoformat()
        c.execute('INSERT INTO users (email, token, expires_at, created_by) VALUES (?, ?, ?, ?)',
                 ('test@branvee.com', 'BRANVEE-TEST-1234', test_expiry, ADMIN_ID))
        print("✅ Test user added")
    
    conn.commit()
    conn.close()
    print("✅ Database initialized")

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

# ============================================
# USER OPERATIONS
# ============================================

def add_user(email, token, expires_at, created_by):
    conn = get_db()
    c = conn.cursor()
    try:
        c.execute('INSERT INTO users (email, token, expires_at, created_by) VALUES (?, ?, ?, ?)',
                 (email, token, expires_at, created_by))
        conn.commit()
        user_id = c.lastrowid
        conn.close()
        return user_id
    except Exception as e:
        conn.close()
        return None

def get_user_by_email(email):
    conn = get_db()
    c = conn.cursor()
    c.execute('SELECT * FROM users WHERE LOWER(email) = LOWER(?)', (email,))
    user = c.fetchone()
    conn.close()
    return user

def get_user_by_id(user_id):
    conn = get_db()
    c = conn.cursor()
    c.execute('SELECT * FROM users WHERE id = ?', (user_id,))
    user = c.fetchone()
    conn.close()
    return user

def get_all_users():
    conn = get_db()
    c = conn.cursor()
    c.execute('SELECT * FROM users ORDER BY created_at DESC')
    users = c.fetchall()
    conn.close()
    return users

def search_users(search_term):
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE email LIKE ? OR token LIKE ? ORDER BY created_at DESC", 
             (f'%{search_term}%', f'%{search_term}%'))
    users = c.fetchall()
    conn.close()
    return users

def get_active_users():
    conn = get_db()
    c = conn.cursor()
    now = datetime.now().isoformat()
    c.execute('SELECT * FROM users WHERE expires_at > ? AND is_suspended = 0 ORDER BY expires_at ASC', (now,))
    users = c.fetchall()
    conn.close()
    return users

def get_expired_users():
    conn = get_db()
    c = conn.cursor()
    now = datetime.now().isoformat()
    c.execute('SELECT * FROM users WHERE expires_at <= ? ORDER BY expires_at DESC', (now,))
    users = c.fetchall()
    conn.close()
    return users

def get_suspended_users():
    conn = get_db()
    c = conn.cursor()
    c.execute('SELECT * FROM users WHERE is_suspended = 1 ORDER BY created_at DESC')
    users = c.fetchall()
    conn.close()
    return users

def suspend_user(user_id):
    conn = get_db()
    c = conn.cursor()
    c.execute('UPDATE users SET is_suspended = 1 WHERE id = ?', (user_id,))
    conn.commit()
    conn.close()
    return True

def activate_user(user_id):
    conn = get_db()
    c = conn.cursor()
    c.execute('UPDATE users SET is_suspended = 0 WHERE id = ?', (user_id,))
    conn.commit()
    conn.close()
    return True

def delete_user(user_id):
    conn = get_db()
    c = conn.cursor()
    c.execute('DELETE FROM users WHERE id = ?', (user_id,))
    conn.commit()
    conn.close()
    return True

def update_user_expiry(user_id, new_expiry):
    conn = get_db()
    c = conn.cursor()
    c.execute('UPDATE users SET expires_at = ? WHERE id = ?', (new_expiry, user_id))
    conn.commit()
    conn.close()
    return True

def get_stats():
    conn = get_db()
    c = conn.cursor()
    now = datetime.now().isoformat()
    
    total = c.execute('SELECT COUNT(*) FROM users').fetchone()[0]
    active = c.execute('SELECT COUNT(*) FROM users WHERE expires_at > ? AND is_suspended = 0', (now,)).fetchone()[0]
    expired = c.execute('SELECT COUNT(*) FROM users WHERE expires_at <= ?', (now,)).fetchone()[0]
    suspended = c.execute('SELECT COUNT(*) FROM users WHERE is_suspended = 1').fetchone()[0]
    linked = c.execute('SELECT COUNT(*) FROM users WHERE telegram_id IS NOT NULL').fetchone()[0]
    
    conn.close()
    return {'total': total, 'active': active, 'expired': expired, 'suspended': suspended, 'linked': linked}

# ============================================
# UTILITY FUNCTIONS
# ============================================

def generate_token():
    chars = string.ascii_uppercase + string.digits
    part1 = ''.join(random.choices(chars, k=4))
    part2 = ''.join(random.choices(chars, k=4))
    return f"BRANVEE-{part1}-{part2}"

def format_token(token):
    return f"`{token}`"

def calculate_expiry(amount, unit):
    now = datetime.now()
    if unit == 'hours':
        return now + timedelta(hours=amount)
    elif unit == 'days':
        return now + timedelta(days=amount)
    elif unit == 'weeks':
        return now + timedelta(weeks=amount)
    elif unit == 'months':
        return now + timedelta(days=amount * 30)
    elif unit == 'years':
        return now + timedelta(days=amount * 365)
    else:
        return now + timedelta(days=30)

def days_until(expiry_date):
    if isinstance(expiry_date, str):
        expiry_date = datetime.fromisoformat(expiry_date)
    delta = expiry_date - datetime.now()
    return delta.days

def format_expiry(expiry_date):
    if isinstance(expiry_date, str):
        expiry_date = datetime.fromisoformat(expiry_date)
    return expiry_date.strftime('%Y-%m-%d %H:%M')

def validate_email(email):
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None

# ============================================
# CONVERSATION STATES
# ============================================

(EMAIL_INPUT, DURATION_TYPE, DURATION_AMOUNT, CONFIRM_ADD, 
 SEARCH_INPUT, SELECT_USER, EDIT_ACTION, EDIT_EXPIRY,
 MESSAGE_INPUT, MESSAGE_CONFIRM) = range(10)

# ============================================
# KEYBOARDS
# ============================================

def get_main_menu():
    keyboard = [
        [InlineKeyboardButton("👥 USER MANAGEMENT", callback_data='menu_users')],
        [InlineKeyboardButton("⚙️ SETTINGS", callback_data='menu_settings')],
        [InlineKeyboardButton("📊 ANALYTICS", callback_data='menu_analytics')],
        [InlineKeyboardButton("❓ HELP", callback_data='menu_help')]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_users_menu():
    keyboard = [
        [InlineKeyboardButton("➕ ADD USER", callback_data='users_add')],
        [InlineKeyboardButton("🔍 SEARCH USER", callback_data='users_search')],
        [InlineKeyboardButton("✅ ACTIVE USERS", callback_data='users_active')],
        [InlineKeyboardButton("❌ EXPIRED USERS", callback_data='users_expired')],
        [InlineKeyboardButton("⏸️ SUSPENDED USERS", callback_data='users_suspended')],
        [InlineKeyboardButton("📋 ALL USERS", callback_data='users_all')],
        [InlineKeyboardButton("⚡ BULK ACTIONS", callback_data='bulk_menu')],
        [InlineKeyboardButton("🔙 MAIN MENU", callback_data='menu_main')]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_bulk_menu():
    keyboard = [
        [InlineKeyboardButton("⏸️ SUSPEND ALL USERS", callback_data='bulk_suspend_all')],
        [InlineKeyboardButton("▶️ ACTIVATE ALL USERS", callback_data='bulk_activate_all')],
        [InlineKeyboardButton("📢 SEND MESSAGE", callback_data='broadcast_menu')],
        [InlineKeyboardButton("🔙 BACK TO USERS", callback_data='menu_users')]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_broadcast_menu():
    keyboard = [
        [InlineKeyboardButton("📢 BROADCAST TO ALL", callback_data='broadcast_all')],
        [InlineKeyboardButton("👤 MESSAGE INDIVIDUAL", callback_data='broadcast_individual')],
        [InlineKeyboardButton("🔙 BACK TO BULK MENU", callback_data='bulk_menu')]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_broadcast_confirmation_menu():
    keyboard = [
        [InlineKeyboardButton("✅ SEND NOW", callback_data='broadcast_send')],
        [InlineKeyboardButton("✏️ EDIT MESSAGE", callback_data='broadcast_edit')],
        [InlineKeyboardButton("❌ CANCEL", callback_data='bulk_menu')]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_settings_menu():
    keyboard = [
        [InlineKeyboardButton("🔄 RENEW USER", callback_data='settings_renew')],
        [InlineKeyboardButton("⏸️ SUSPEND USER", callback_data='settings_suspend')],
        [InlineKeyboardButton("▶️ ACTIVATE USER", callback_data='settings_activate')],
        [InlineKeyboardButton("❌ DELETE USER", callback_data='settings_delete')],
        [InlineKeyboardButton("📝 EDIT EXPIRY", callback_data='settings_edit_expiry')],
        [InlineKeyboardButton("🔙 MAIN MENU", callback_data='menu_main')]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_duration_type_menu():
    keyboard = [
        [InlineKeyboardButton("⏰ HOURS", callback_data='dur_hours')],
        [InlineKeyboardButton("📅 DAYS", callback_data='dur_days')],
        [InlineKeyboardButton("📆 WEEKS", callback_data='dur_weeks')],
        [InlineKeyboardButton("🗓️ MONTHS", callback_data='dur_months')],
        [InlineKeyboardButton("📅 YEARS", callback_data='dur_years')],
        [InlineKeyboardButton("🎁 FREE (No expiry)", callback_data='dur_free')],
        [InlineKeyboardButton("🔙 BACK", callback_data='users_add')]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_hours_menu():
    keyboard = [
        [InlineKeyboardButton("1 Hour", callback_data='hour_1'),
         InlineKeyboardButton("6 Hours", callback_data='hour_6')],
        [InlineKeyboardButton("12 Hours", callback_data='hour_12'),
         InlineKeyboardButton("24 Hours", callback_data='hour_24')],
        [InlineKeyboardButton("48 Hours", callback_data='hour_48'),
         InlineKeyboardButton("72 Hours", callback_data='hour_72')],
        [InlineKeyboardButton("✏️ CUSTOM", callback_data='dur_custom')],
        [InlineKeyboardButton("🔙 BACK", callback_data='dur_type_back')]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_days_menu():
    keyboard = [
        [InlineKeyboardButton("1 Day", callback_data='day_1'),
         InlineKeyboardButton("3 Days", callback_data='day_3')],
        [InlineKeyboardButton("7 Days", callback_data='day_7'),
         InlineKeyboardButton("15 Days", callback_data='day_15')],
        [InlineKeyboardButton("30 Days", callback_data='day_30'),
         InlineKeyboardButton("60 Days", callback_data='day_60')],
        [InlineKeyboardButton("90 Days", callback_data='day_90'),
         InlineKeyboardButton("180 Days", callback_data='day_180')],
        [InlineKeyboardButton("✏️ CUSTOM", callback_data='dur_custom')],
        [InlineKeyboardButton("🔙 BACK", callback_data='dur_type_back')]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_weeks_menu():
    keyboard = [
        [InlineKeyboardButton("1 Week", callback_data='week_1'),
         InlineKeyboardButton("2 Weeks", callback_data='week_2')],
        [InlineKeyboardButton("3 Weeks", callback_data='week_3'),
         InlineKeyboardButton("4 Weeks", callback_data='week_4')],
        [InlineKeyboardButton("8 Weeks", callback_data='week_8'),
         InlineKeyboardButton("12 Weeks", callback_data='week_12')],
        [InlineKeyboardButton("✏️ CUSTOM", callback_data='dur_custom')],
        [InlineKeyboardButton("🔙 BACK", callback_data='dur_type_back')]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_months_menu():
    keyboard = [
        [InlineKeyboardButton("1 Month", callback_data='month_1'),
         InlineKeyboardButton("3 Months", callback_data='month_3')],
        [InlineKeyboardButton("6 Months", callback_data='month_6'),
         InlineKeyboardButton("9 Months", callback_data='month_9')],
        [InlineKeyboardButton("12 Months", callback_data='month_12'),
         InlineKeyboardButton("24 Months", callback_data='month_24')],
        [InlineKeyboardButton("✏️ CUSTOM", callback_data='dur_custom')],
        [InlineKeyboardButton("🔙 BACK", callback_data='dur_type_back')]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_years_menu():
    keyboard = [
        [InlineKeyboardButton("1 Year", callback_data='year_1'),
         InlineKeyboardButton("2 Years", callback_data='year_2')],
        [InlineKeyboardButton("3 Years", callback_data='year_3'),
         InlineKeyboardButton("5 Years", callback_data='year_5')],
        [InlineKeyboardButton("10 Years", callback_data='year_10')],
        [InlineKeyboardButton("✏️ CUSTOM", callback_data='dur_custom')],
        [InlineKeyboardButton("🔙 BACK", callback_data='dur_type_back')]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_confirmation_menu():
    keyboard = [
        [InlineKeyboardButton("✅ CONFIRM", callback_data='confirm_yes')],
        [InlineKeyboardButton("✏️ EDIT", callback_data='confirm_edit')],
        [InlineKeyboardButton("❌ CANCEL", callback_data='confirm_cancel')]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_user_action_menu(user_id):
    keyboard = [
        [InlineKeyboardButton("👁️ VIEW", callback_data=f'view_{user_id}')],
        [InlineKeyboardButton("🔄 RENEW", callback_data=f'renew_{user_id}')],
        [InlineKeyboardButton("⏸️ SUSPEND", callback_data=f'suspend_{user_id}')],
        [InlineKeyboardButton("▶️ ACTIVATE", callback_data=f'activate_{user_id}')],
        [InlineKeyboardButton("❌ DELETE", callback_data=f'delete_{user_id}')],
        [InlineKeyboardButton("📝 EDIT EXPIRY", callback_data=f'editexpiry_{user_id}')],
        [InlineKeyboardButton("🔙 BACK", callback_data='back_to_users')]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_back_button():
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("🔙 BACK", callback_data='menu_users')
    ]])

# ============================================
# HANDLERS
# ============================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id != ADMIN_ID:
        await update.message.reply_text("⛔ Unauthorized")
        return
    
    await update.message.reply_text(
        "🔷 **BRANVEE GOLD ADMIN PANEL** 🔷\n\n"
        "Welcome to the complete admin system.\n"
        "Select an option below:",
        reply_markup=get_main_menu(),
        parse_mode='Markdown'
    )

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    if user_id != ADMIN_ID:
        await query.edit_message_text("⛔ Unauthorized")
        return
    
    data = query.data
    
    # ========== MAIN MENU ==========
    if data == 'menu_main':
        await query.edit_message_text(
            "🔷 **BRANVEE GOLD ADMIN PANEL** 🔷\n\nSelect an option:",
            reply_markup=get_main_menu(),
            parse_mode='Markdown'
        )
    
    elif data == 'menu_users':
        await query.edit_message_text(
            "👥 **USER MANAGEMENT**\n\nChoose an option:",
            reply_markup=get_users_menu(),
            parse_mode='Markdown'
        )
    
    elif data == 'bulk_menu':
        await query.edit_message_text(
            "⚡ **BULK ACTIONS**\n\n"
            "These actions affect ALL users in the database.\n"
            "Use with caution!",
            reply_markup=get_bulk_menu(),
            parse_mode='Markdown'
        )
    
    elif data == 'menu_settings':
        await query.edit_message_text(
            "⚙️ **SETTINGS**\n\nSelect user management action:",
            reply_markup=get_settings_menu(),
            parse_mode='Markdown'
        )
    
    elif data == 'menu_analytics':
        stats = get_stats()
        msg = (
            "📊 **ANALYTICS**\n\n"
            f"👥 **Total Users:** {stats['total']}\n"
            f"✅ **Active:** {stats['active']}\n"
            f"❌ **Expired:** {stats['expired']}\n"
            f"⏸️ **Suspended:** {stats['suspended']}\n"
            f"📱 **Linked:** {stats['linked']}\n\n"
            f"📈 **Active Rate:** {stats['active']/max(stats['total'],1)*100:.1f}%"
        )
        await query.edit_message_text(
            msg,
            reply_markup=get_back_button(),
            parse_mode='Markdown'
        )
    
    elif data == 'menu_help':
        msg = (
            "❓ **HELP**\n\n"
            "**USER MANAGEMENT**\n"
            "• Add User - Create new user\n"
            "• Search User - Find by email/token\n"
            "• Active Users - View active users\n"
            "• Expired Users - View expired\n"
            "• Suspended Users - View suspended\n"
            "• All Users - List all users\n\n"
            "**SETTINGS**\n"
            "• Renew User - Extend expiry\n"
            "• Suspend User - Block access\n"
            "• Activate User - Restore access\n"
            "• Delete User - Remove user\n"
            "• Edit Expiry - Change expiry date\n\n"
            "**BULK ACTIONS**\n"
            "• Suspend All - Block all users\n"
            "• Activate All - Restore all users\n"
            "• Send Message - Broadcast to users\n\n"
            "**EXPIRY OPTIONS**\n"
            "Hours, Days, Weeks, Months, Years, or Free"
        )
        await query.edit_message_text(
            msg,
            reply_markup=get_back_button(),
            parse_mode='Markdown'
        )
    
    # ========== USER LISTINGS ==========
    elif data == 'users_all':
        users = get_all_users()
        await show_user_list(query, users, "ALL USERS")
    
    elif data == 'users_active':
        users = get_active_users()
        await show_user_list(query, users, "ACTIVE USERS")
    
    elif data == 'users_expired':
        users = get_expired_users()
        await show_user_list(query, users, "EXPIRED USERS")
    
    elif data == 'users_suspended':
        users = get_suspended_users()
        await show_user_list(query, users, "SUSPENDED USERS")
    
    elif data == 'users_search':
        await query.edit_message_text(
            "🔍 **SEARCH USER**\n\nEnter email or token to search:",
            parse_mode='Markdown'
        )
        return SEARCH_INPUT
    
    # ========== BROADCAST MENU ==========
    elif data == 'broadcast_menu':
        await query.edit_message_text(
            "📢 **MESSAGING CENTER**\n\n"
            "Choose who you want to message:",
            reply_markup=get_broadcast_menu(),
            parse_mode='Markdown'
        )
    
    elif data == 'broadcast_all':
        context.user_data['broadcast_type'] = 'all'
        await query.edit_message_text(
            "📢 **MESSAGE TO ALL USERS**\n\n"
            "Enter your message below.\n\n"
            "The message will be sent as:\n"
            "`Dear [email], [your message]`\n\n"
            "Type your message:",
            parse_mode='Markdown'
        )
        return MESSAGE_INPUT
    
    elif data == 'broadcast_individual':
        context.user_data['broadcast_type'] = 'individual'
        await query.edit_message_text(
            "👤 **MESSAGE INDIVIDUAL USER**\n\n"
            "Enter the user's email address:",
            parse_mode='Markdown'
        )
        return SEARCH_INPUT
    
    # ========== BROADCAST CONFIRMATION ==========
    elif data == 'broadcast_send':
        broadcast_type = context.user_data.get('broadcast_type')
        message = context.user_data.get('broadcast_message')
        
        if not message:
            await query.edit_message_text(
                "❌ No message found. Please try again.",
                reply_markup=get_back_button()
            )
            return
        
        await query.edit_message_text("📤 Sending messages...")
        
        if broadcast_type == 'all':
            # Get all users with telegram_id
            users = get_all_users()
            sent_count = 0
            failed_count = 0
            
            for user in users:
                if user['telegram_id']:
                    try:
                        personalized = f"Dear {user['email']},\n\n{message}\n\n---\nBranvee Gold System"
                        await context.bot.send_message(
                            chat_id=user['telegram_id'],
                            text=personalized,
                            parse_mode='Markdown'
                        )
                        sent_count += 1
                        await asyncio.sleep(0.05)  # Small delay to avoid rate limiting
                    except Exception as e:
                        failed_count += 1
                        print(f"Failed to send to {user['email']}: {e}")
            
            await query.edit_message_text(
                f"✅ **BROADCAST COMPLETE**\n\n"
                f"📤 **Sent:** {sent_count}\n"
                f"❌ **Failed:** {failed_count}\n"
                f"👥 **Total Users:** {len(users)}",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("👥 BACK TO USERS", callback_data='menu_users')
                ]]),
                parse_mode='Markdown'
            )
        
        elif broadcast_type == 'individual':
            user = context.user_data.get('broadcast_user', {})
            if user and user.get('telegram_id'):
                try:
                    personalized = f"Dear {user['email']},\n\n{message}\n\n---\nBranvee Gold System"
                    await context.bot.send_message(
                        chat_id=user['telegram_id'],
                        text=personalized,
                        parse_mode='Markdown'
                    )
                    await query.edit_message_text(
                        f"✅ **MESSAGE SENT**\n\n"
                        f"📧 **To:** {user['email']}",
                        reply_markup=InlineKeyboardMarkup([[
                            InlineKeyboardButton("👥 BACK TO USERS", callback_data='menu_users')
                        ]]),
                        parse_mode='Markdown'
                    )
                except Exception as e:
                    await query.edit_message_text(
                        f"❌ **Failed to send**\n\n"
                        f"Error: {str(e)}",
                        reply_markup=get_back_button()
                    )
            else:
                await query.edit_message_text(
                    "❌ User has no Telegram ID linked.",
                    reply_markup=get_back_button()
                )
        
        context.user_data.clear()
    
    elif data == 'broadcast_edit':
        await query.edit_message_text(
            "✏️ **EDIT MESSAGE**\n\n"
            "Type your new message:",
            parse_mode='Markdown'
        )
        return MESSAGE_INPUT
    
    # ========== ADD USER FLOW ==========
    elif data == 'users_add':
        await query.edit_message_text(
            "➕ **ADD USER**\n\nEnter user's email address:",
            parse_mode='Markdown'
        )
        return EMAIL_INPUT
    
    elif data == 'dur_type_back':
        await query.edit_message_text(
            "➕ **ADD USER**\n\nSelect duration type:",
            reply_markup=get_duration_type_menu(),
            parse_mode='Markdown'
        )
    
    elif data in ['dur_hours', 'dur_days', 'dur_weeks', 'dur_months', 'dur_years']:
        context.user_data['duration_unit'] = data.replace('dur_', '')
        
        if data == 'dur_hours':
            await query.edit_message_text(
                "⏰ Select hours:",
                reply_markup=get_hours_menu()
            )
        elif data == 'dur_days':
            await query.edit_message_text(
                "📅 Select days:",
                reply_markup=get_days_menu()
            )
        elif data == 'dur_weeks':
            await query.edit_message_text(
                "📆 Select weeks:",
                reply_markup=get_weeks_menu()
            )
        elif data == 'dur_months':
            await query.edit_message_text(
                "🗓️ Select months:",
                reply_markup=get_months_menu()
            )
        elif data == 'dur_years':
            await query.edit_message_text(
                "📅 Select years:",
                reply_markup=get_years_menu()
            )
    
    elif data == 'dur_free':
        context.user_data['duration_amount'] = 0
        context.user_data['duration_unit'] = 'free'
        # Check if this is for renewal or new user
        if 'edit_user_id' in context.user_data:
            await show_renew_confirmation(query, context)
        else:
            await show_add_confirmation(query, context)
    
    elif data.startswith('hour_') or data.startswith('day_') or data.startswith('week_') or \
         data.startswith('month_') or data.startswith('year_'):
        
        parts = data.split('_')
        amount = int(parts[1])
        context.user_data['duration_amount'] = amount
        
        # Check if this is for renewal or new user
        if 'edit_user_id' in context.user_data:
            await show_renew_confirmation(query, context)
        else:
            await show_add_confirmation(query, context)
    
    elif data == 'dur_custom':
        await query.edit_message_text(
            "✏️ **CUSTOM DURATION**\n\nEnter the number:",
            parse_mode='Markdown'
        )
        return DURATION_AMOUNT
    
    # ========== CONFIRMATION ==========
    elif data == 'confirm_yes':
        # Check if this is a renewal or new user
        if 'edit_user_id' in context.user_data:
            await complete_renew_user(query, context)
        else:
            await complete_add_user(query, context)
    
    elif data == 'confirm_edit':
        if 'edit_user_id' in context.user_data:
            # Return to renewal flow
            await query.edit_message_text(
                "🔄 **RENEW USER**\n\nSelect new duration type:",
                reply_markup=get_duration_type_menu(),
                parse_mode='Markdown'
            )
        else:
            await query.edit_message_text(
                "➕ **ADD USER**\n\nEnter user's email address:",
                parse_mode='Markdown'
            )
            return EMAIL_INPUT
    
    elif data == 'confirm_cancel':
        await query.edit_message_text(
            "❌ Operation cancelled.",
            reply_markup=get_back_button()
        )
        context.user_data.clear()
    
    # ========== USER ACTIONS ==========
    elif data.startswith('view_'):
        user_id = int(data.split('_')[1])
        await show_user_details(query, user_id)
    
    elif data.startswith('renew_'):
        user_id = int(data.split('_')[1])
        user = get_user_by_id(user_id)
        if user:
            context.user_data['edit_user_id'] = user_id
            context.user_data['edit_user_email'] = user['email']
            await query.edit_message_text(
                f"🔄 **RENEW USER**\n\n"
                f"📧 **Email:** {user['email']}\n"
                f"Current expiry: {user['expires_at'][:10]}\n\n"
                f"Select new duration type:",
                reply_markup=get_duration_type_menu(),
                parse_mode='Markdown'
            )
    
    elif data.startswith('suspend_'):
        user_id = int(data.split('_')[1])
        suspend_user(user_id)
        await query.edit_message_text(
            "✅ User suspended successfully.",
            reply_markup=get_back_button()
        )
    
    elif data.startswith('activate_'):
        user_id = int(data.split('_')[1])
        activate_user(user_id)
        await query.edit_message_text(
            "✅ User activated successfully.",
            reply_markup=get_back_button()
        )
    
    elif data.startswith('delete_'):
        user_id = int(data.split('_')[1])
        delete_user(user_id)
        await query.edit_message_text(
            "✅ User deleted successfully.",
            reply_markup=get_back_button()
        )
    
    elif data.startswith('editexpiry_'):
        user_id = int(data.split('_')[1])
        user = get_user_by_id(user_id)
        if user:
            context.user_data['edit_user_id'] = user_id
            context.user_data['edit_user_email'] = user['email']
            await query.edit_message_text(
                f"📝 **EDIT EXPIRY**\n\n"
                f"📧 **Email:** {user['email']}\n"
                f"Current expiry: {user['expires_at'][:10]}\n\n"
                f"Select new duration type:",
                reply_markup=get_duration_type_menu(),
                parse_mode='Markdown'
            )
    
    elif data == 'back_to_users':
        await query.edit_message_text(
            "👥 **USER MANAGEMENT**",
            reply_markup=get_users_menu(),
            parse_mode='Markdown'
        )
    
    # ========== BULK ACTIONS ==========
    elif data == 'bulk_suspend_all':
        keyboard = [
            [InlineKeyboardButton("✅ YES, SUSPEND ALL", callback_data='bulk_suspend_confirm')],
            [InlineKeyboardButton("❌ NO, CANCEL", callback_data='back_to_users')]
        ]
        await query.edit_message_text(
            "⚠️ **WARNING** ⚠️\n\n"
            "This will suspend ALL users in the database.\n"
            "They will not be able to access the bot.\n\n"
            "Are you ABSOLUTELY sure?",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
    
    elif data == 'bulk_activate_all':
        keyboard = [
            [InlineKeyboardButton("✅ YES, ACTIVATE ALL", callback_data='bulk_activate_confirm')],
            [InlineKeyboardButton("❌ NO, CANCEL", callback_data='back_to_users')]
        ]
        await query.edit_message_text(
            "⚠️ **WARNING** ⚠️\n\n"
            "This will activate ALL users in the database.\n"
            "All suspended accounts will be restored.\n\n"
            "Are you sure?",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
    
    elif data == 'bulk_suspend_confirm':
        conn = get_db()
        c = conn.cursor()
        c.execute('UPDATE users SET is_suspended = 1')
        count = c.rowcount
        conn.commit()
        conn.close()
        
        await query.edit_message_text(
            f"✅ **BULK ACTION COMPLETE**\n\n"
            f"Successfully suspended **{count}** users.\n"
            f"All accounts are now suspended.",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("👥 BACK TO USERS", callback_data='menu_users')
            ]]),
            parse_mode='Markdown'
        )
    
    elif data == 'bulk_activate_confirm':
        conn = get_db()
        c = conn.cursor()
        c.execute('UPDATE users SET is_suspended = 0')
        count = c.rowcount
        conn.commit()
        conn.close()
        
        await query.edit_message_text(
            f"✅ **BULK ACTION COMPLETE**\n\n"
            f"Successfully activated **{count}** users.\n"
            f"All accounts are now active.",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("👥 BACK TO USERS", callback_data='menu_users')
            ]]),
            parse_mode='Markdown'
        )

async def show_user_list(query, users, title):
    if not users:
        await query.edit_message_text(
            f"📋 **{title}**\n\nNo users found.",
            reply_markup=get_back_button(),
            parse_mode='Markdown'
        )
        return
    
    msg = f"📋 **{title}**\n\n"
    
    for user in users[:10]:
        status = "✅" if not user['is_suspended'] else "⏸️"
        days = days_until(user['expires_at']) if user['expires_at'] > datetime.now().isoformat() else "Expired"
        
        # Show first 10 chars of email
        email_short = user['email'][:20] + "..." if len(user['email']) > 20 else user['email']
        token_short = user['token'][:15] + "..."
        
        msg += f"{status} **{email_short}**\n"
        msg += f"🔑 `{token_short}`\n"
        msg += f"📅 Expires: {user['expires_at'][:10]} ({days} days)\n"
        msg += f"🆔 ID: {user['id']}\n\n"
    
    if len(users) > 10:
        msg += f"... and {len(users) - 10} more users\n\n"
    
    # Add action buttons for first user as example
    if users:
        first_user = users[0]
        await query.edit_message_text(
            msg + f"Actions for {first_user['email'][:20]}:",
            reply_markup=get_user_action_menu(first_user['id']),
            parse_mode='Markdown'
        )
    else:
        await query.edit_message_text(
            msg,
            reply_markup=get_back_button(),
            parse_mode='Markdown'
        )

async def show_user_details(query, user_id):
    user = get_user_by_id(user_id)
    if not user:
        await query.edit_message_text("User not found.")
        return
    
    days = days_until(user['expires_at']) if user['expires_at'] > datetime.now().isoformat() else "Expired"
    status = "✅ Active" if not user['is_suspended'] else "⏸️ Suspended"
    linked = "Yes" if user['telegram_id'] else "No"
    
    msg = (
        f"👤 **USER DETAILS**\n\n"
        f"📧 **Email:** {user['email']}\n"
        f"🔑 **Token:** `{user['token']}`\n"
        f"🆔 **User ID:** {user['id']}\n"
        f"📱 **Telegram Linked:** {linked}\n"
        f"📊 **Status:** {status}\n"
        f"📅 **Expires:** {user['expires_at'][:10]}\n"
        f"⏳ **Days Left:** {days}\n"
        f"📆 **Created:** {user['created_at'][:10]}\n"
    )
    
    await query.edit_message_text(
        msg,
        reply_markup=get_user_action_menu(user_id),
        parse_mode='Markdown'
    )

async def show_add_confirmation(query, context):
    email = context.user_data.get('email')
    unit = context.user_data.get('duration_unit', 'days')
    amount = context.user_data.get('duration_amount', 30)
    
    if unit == 'free':
        expiry = "No expiry (free)"
        expiry_date = "2099-12-31"
    else:
        expiry_date = calculate_expiry(amount, unit)
        expiry = expiry_date.strftime('%Y-%m-%d')
    
    context.user_data['expiry_date'] = expiry_date.isoformat() if unit != 'free' else '2099-12-31T00:00:00'
    
    msg = (
        f"📧 **Email:** {email}\n"
        f"⏳ **Duration:** {amount} {unit if unit != 'free' else 'free'}\n"
        f"📅 **Expires:** {expiry}\n\n"
        f"Confirm?"
    )
    
    await query.edit_message_text(
        msg,
        reply_markup=get_confirmation_menu(),
        parse_mode='Markdown'
    )

async def show_renew_confirmation(query, context):
    user_id = context.user_data.get('edit_user_id')
    email = context.user_data.get('edit_user_email')
    unit = context.user_data.get('duration_unit', 'days')
    amount = context.user_data.get('duration_amount', 30)
    
    # Debug print to see what's in context
    print(f"Renew confirmation - User ID: {user_id}, Email: {email}, Unit: {unit}, Amount: {amount}")
    
    if not email and user_id:
        # If email is missing, try to get it from database
        user = get_user_by_id(user_id)
        if user:
            email = user['email']
            context.user_data['edit_user_email'] = email
            print(f"Retrieved email from DB: {email}")
    
    if unit == 'free':
        expiry = "No expiry (free)"
        expiry_date = "2099-12-31"
    else:
        expiry_date = calculate_expiry(amount, unit)
        expiry = expiry_date.strftime('%Y-%m-%d')
    
    context.user_data['new_expiry_date'] = expiry_date.isoformat() if unit != 'free' else '2099-12-31T00:00:00'
    
    msg = (
        f"🔄 **RENEW USER**\n\n"
        f"📧 **Email:** {email}\n"
        f"⏳ **New Duration:** {amount} {unit if unit != 'free' else 'free'}\n"
        f"📅 **New Expiry:** {expiry}\n\n"
        f"Confirm renewal?"
    )
    
    await query.edit_message_text(
        msg,
        reply_markup=get_confirmation_menu(),
        parse_mode='Markdown'
    )

async def complete_add_user(query, context):
    email = context.user_data.get('email')
    expiry_date = context.user_data.get('expiry_date')
    token = generate_token()
    
    user_id = add_user(email, token, expiry_date, ADMIN_ID)
    
    if user_id:
        msg = (
            f"✅ **USER ADDED SUCCESSFULLY**\n\n"
            f"📧 **Email:** {email}\n"
            f"🔑 **Token:** `{token}`\n"
            f"📅 **Expires:** {expiry_date[:10]}\n\n"
            f"Share these credentials with the user."
        )
    else:
        msg = "❌ Error adding user. Email may already exist."
    
    await query.edit_message_text(
        msg,
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("👥 BACK TO USERS", callback_data='menu_users')
        ]]),
        parse_mode='Markdown'
    )
    
    context.user_data.clear()

async def complete_renew_user(query, context):
    user_id = context.user_data.get('edit_user_id')
    email = context.user_data.get('edit_user_email')
    new_expiry = context.user_data.get('new_expiry_date')
    
    update_user_expiry(user_id, new_expiry)
    
    await query.edit_message_text(
        f"✅ **USER RENEWED SUCCESSFULLY**\n\n"
        f"📧 **Email:** {email}\n"
        f"📅 **New Expiry:** {new_expiry[:10]}\n\n"
        f"User's access has been extended.",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("👥 BACK TO USERS", callback_data='menu_users')
        ]]),
        parse_mode='Markdown'
    )
    
    context.user_data.clear()

# ============================================
# MESSAGE HANDLERS
# ============================================

async def handle_email_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    email = update.message.text.strip()
    
    if not validate_email(email):
        await update.message.reply_text("❌ Invalid email. Try again:")
        return EMAIL_INPUT
    
    if get_user_by_email(email):
        await update.message.reply_text("❌ Email already exists. Try another:")
        return EMAIL_INPUT
    
    context.user_data['email'] = email
    
    await update.message.reply_text(
        "⏰ Select duration type:",
        reply_markup=get_duration_type_menu()
    )
    return ConversationHandler.END

async def handle_search_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    search_term = update.message.text.strip()
    
    users = search_users(search_term)
    
    if not users:
        await update.message.reply_text(
            "❌ No users found.",
            reply_markup=get_back_button()
        )
        return ConversationHandler.END
    
    # Check if this is for broadcast or regular search
    if context.user_data.get('broadcast_type') == 'individual':
        user = users[0]
        context.user_data['broadcast_user'] = dict(user)
        await update.message.reply_text(
            f"👤 **User Found**\n\n"
            f"📧 Email: {user['email']}\n\n"
            f"Enter your message for this user:",
            parse_mode='Markdown'
        )
        return MESSAGE_INPUT
    
    # Regular search results
    msg = f"🔍 **Search Results for '{search_term}'**\n\n"
    
    for user in users[:5]:
        days = days_until(user['expires_at']) if user['expires_at'] > datetime.now().isoformat() else "Expired"
        status = "✅" if not user['is_suspended'] else "⏸️"
        msg += f"{status} **{user['email']}**\n"
        msg += f"🔑 `{user['token']}`\n"
        msg += f"📅 Expires: {user['expires_at'][:10]} ({days} days)\n\n"
    
    if len(users) > 5:
        msg += f"... and {len(users) - 5} more results\n\n"
    
    # Show actions for first user
    await update.message.reply_text(
        msg + f"Actions for {users[0]['email']}:",
        reply_markup=get_user_action_menu(users[0]['id']),
        parse_mode='Markdown'
    )
    
    return ConversationHandler.END

async def handle_message_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle broadcast message input"""
    message = update.message.text.strip()
    
    if len(message) < 1:
        await update.message.reply_text("❌ Message cannot be empty. Try again:")
        return MESSAGE_INPUT
    
    context.user_data['broadcast_message'] = message
    
    # Show preview based on broadcast type
    broadcast_type = context.user_data.get('broadcast_type')
    
    if broadcast_type == 'individual':
        user = context.user_data.get('broadcast_user', {})
        email = user.get('email', 'user')
        preview = (
            f"📝 **MESSAGE PREVIEW**\n\n"
            f"To: {email}\n\n"
            f"Dear {email},\n\n"
            f"{message}\n\n"
            f"---\n"
            f"Branvee Gold System"
        )
    else:
        preview = (
            f"📝 **MESSAGE PREVIEW**\n\n"
            f"To: ALL USERS\n\n"
            f"Dear [email],\n\n"
            f"{message}\n\n"
            f"---\n"
            f"Branvee Gold System"
        )
    
    await update.message.reply_text(
        f"{preview}\n\n"
        f"Send this message?",
        reply_markup=get_broadcast_confirmation_menu(),
        parse_mode='Markdown'
    )
    return MESSAGE_CONFIRM

async def handle_custom_duration(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        amount = int(update.message.text.strip())
        if amount <= 0:
            raise ValueError
    except:
        await update.message.reply_text("❌ Please enter a positive number:")
        return DURATION_AMOUNT
    
    context.user_data['duration_amount'] = amount
    
    # Check if this is for renewal or new user
    if 'edit_user_id' in context.user_data:
        await show_renew_confirmation(update, context)
    else:
        await show_add_confirmation(update, context)
    return ConversationHandler.END

async def show_add_confirmation(update, context):
    email = context.user_data.get('email')
    unit = context.user_data.get('duration_unit', 'days')
    amount = context.user_data.get('duration_amount', 30)
    
    expiry_date = calculate_expiry(amount, unit)
    context.user_data['expiry_date'] = expiry_date.isoformat()
    
    await update.message.reply_text(
        f"📧 **Email:** {email}\n"
        f"⏳ **Duration:** {amount} {unit}\n"
        f"📅 **Expires:** {expiry_date.strftime('%Y-%m-%d')}\n\n"
        f"Confirm?",
        reply_markup=get_confirmation_menu(),
        parse_mode='Markdown'
    )

async def show_renew_confirmation(update, context):
    user_id = context.user_data.get('edit_user_id')
    email = context.user_data.get('edit_user_email')
    unit = context.user_data.get('duration_unit', 'days')
    amount = context.user_data.get('duration_amount', 30)
    
    if not email and user_id:
        user = get_user_by_id(user_id)
        if user:
            email = user['email']
            context.user_data['edit_user_email'] = email
    
    expiry_date = calculate_expiry(amount, unit)
    context.user_data['new_expiry_date'] = expiry_date.isoformat()
    
    await update.message.reply_text(
        f"🔄 **RENEW USER**\n\n"
        f"📧 **Email:** {email}\n"
        f"⏳ **New Duration:** {amount} {unit}\n"
        f"📅 **New Expiry:** {expiry_date.strftime('%Y-%m-%d')}\n\n"
        f"Confirm renewal?",
        reply_markup=get_confirmation_menu(),
        parse_mode='Markdown'
    )

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ Operation cancelled.")
    context.user_data.clear()
    return ConversationHandler.END

# ============================================
# MAIN
# ============================================

def main():
    init_db()
    
    app = Application.builder().token(BOT_TOKEN).build()
    
    # Conversation handler for adding users
    add_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(button_handler, pattern='^users_add$')],
        states={
            EMAIL_INPUT: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_email_input)],
        },
        fallbacks=[CommandHandler('cancel', cancel)],
        allow_reentry=True
    )
    app.add_handler(add_conv)
    
    # Conversation handler for search
    search_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(button_handler, pattern='^users_search$')],
        states={
            SEARCH_INPUT: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_search_input)],
        },
        fallbacks=[CommandHandler('cancel', cancel)],
        allow_reentry=True
    )
    app.add_handler(search_conv)
    
    # Conversation handler for custom duration
    custom_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(button_handler, pattern='^dur_custom$')],
        states={
            DURATION_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_custom_duration)],
        },
        fallbacks=[CommandHandler('cancel', cancel)],
        allow_reentry=True
    )
    app.add_handler(custom_conv)
    
    # Conversation handler for broadcast message
    broadcast_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(button_handler, pattern='^broadcast_(all|individual)$')],
        states={
            MESSAGE_INPUT: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message_input)],
            MESSAGE_CONFIRM: [CallbackQueryHandler(button_handler, pattern='^(broadcast_send|broadcast_edit)$')],
        },
        fallbacks=[CommandHandler('cancel', cancel)],
        allow_reentry=True
    )
    app.add_handler(broadcast_conv)
    
    # Main handlers
    app.add_handler(CommandHandler('start', start))
    app.add_handler(CallbackQueryHandler(button_handler))
    
    print("\n" + "="*60)
    print("🤖 BRANVEE ADMIN BOT - COMPLETE VERSION")
    print("="*60)
    print("✅ Features loaded:")
    print("   • Hours/Days/Weeks/Months/Years/Free expiry")
    print("   • Search users by email/token")
    print("   • View all/active/expired/suspended users")
    print("   • Suspend/Activate/Delete users")
    print("   • Edit expiry dates")
    print("   • View user details with token")
    print("   • BULK ACTIONS - Suspend/Activate ALL users")
    print("   • BROADCAST - Send messages to users (individual or all)")
    print("   • Renew with email confirmation (FIXED)")
    print("="*60 + "\n")
    
    app.run_polling()

if __name__ == '__main__':
    main()