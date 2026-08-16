import asyncio
import json
import sqlite3
import logging
from aiohttp import ClientSession

# --- CONFIGURATION ---
BOT_TOKEN = "8518780878:AAHn_DoBUW6JXZzJracncOJ0OvRkbNtg86o"
ADMIN_ID = 6408565838
ADMIN_USERNAME = "@ALL_ID_RCV"
API_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"

logging.basicConfig(level=logging.INFO)

# --- DATABASE SETUP ---
def init_db():
    conn = sqlite3.connect("bot_database.db")
    cursor = conn.cursor()
    # Users table
    cursor.execute('''CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        balance REAL DEFAULT 0.0,
        state TEXT DEFAULT 'MAIN_MENU',
        temp_platform TEXT,
        temp_amount REAL
    )''')
    # Orders table
    cursor.execute('''CREATE TABLE IF NOT EXISTS orders (
        order_id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        type TEXT, -- 'SELL' or 'WITHDRAW'
        details TEXT,
        amount REAL DEFAULT 0.0,
        status TEXT DEFAULT 'PENDING'
    )''')
    conn.commit()
    conn.close()

init_db()

# --- DATABASE HELPER FUNCTIONS ---
def get_user(user_id):
    conn = sqlite3.connect("bot_database.db")
    cursor = conn.cursor()
    cursor.execute("SELECT balance, state, temp_platform, temp_amount FROM users WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    if not row:
        cursor.execute("INSERT INTO users (user_id) VALUES (?)", (user_id,))
        conn.commit()
        return 0.0, 'MAIN_MENU', None, None
    conn.close()
    return row

def update_user_state(user_id, state, platform=None, amount=None):
    conn = sqlite3.connect("bot_database.db")
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET state = ?, temp_platform = ?, temp_amount = ? WHERE user_id = ?", (state, platform, amount, user_id))
    conn.commit()
    conn.close()

def update_balance(user_id, amount):
    conn = sqlite3.connect("bot_database.db")
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (amount, user_id))
    conn.commit()
    conn.close()

def create_order(user_id, o_type, details, amount=0.0):
    conn = sqlite3.connect("bot_database.db")
    cursor = conn.cursor()
    cursor.execute("INSERT INTO orders (user_id, type, details, amount) VALUES (?, ?, ?, ?)", (user_id, o_type, details, amount))
    order_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return order_id

def get_order(order_id):
    conn = sqlite3.connect("bot_database.db")
    cursor = conn.cursor()
    cursor.execute("SELECT user_id, type, details, amount, status FROM orders WHERE order_id = ?", (order_id,))
    row = cursor.fetchone()
    conn.close()
    return row

def update_order_status(order_id, status):
    conn = sqlite3.connect("bot_database.db")
    cursor = conn.cursor()
    cursor.execute("UPDATE orders SET status = ? WHERE order_id = ?", (status, order_id))
    conn.commit()
    conn.close()

# --- TELEGRAM API REQUESTS ---
async def send_api_request(session, method, payload):
    url = f"{API_URL}/{method}"
    try:
        async with session.post(url, json=payload) as response:
            return await response.json()
    except Exception as e:
        logging.error(f"Error sending request {method}: {e}")
        return None

async def send_message(session, chat_id, text, reply_markup=None):
    payload = {"chat_id": chat_id, "text": text, "parse_mode": "HTML"}
    if reply_markup:
        payload["reply_markup"] = reply_markup
    await send_api_request(session, "sendMessage", payload)

# --- KEYBOARDS ---
def get_main_menu():
    return {
        "keyboard": [
            [{"text": "🚀 Future Panel"}]
        ],
        "resize_keyboard": True
    }

def get_future_menu():
    return {
        "keyboard": [
            [{"text": "💰 Account Sell"}, {"text": "👤 My Account"}],
            [{"text": "💳 Withdraw / Payment"}, {"text": "📞 Support"}],
            [{"text": "🔙 Back to Main Menu"}]
        ],
        "resize_keyboard": True
    }

def get_withdraw_platforms():
    return {
        "inline_keyboard": [
            [{"text": "বিকাশ", "callback_data": "w_plat_Bkash"}],
            [{"text": "নগদ", "callback_data": "w_plat_Nagad"}],
            [{"text": "রকেট", "callback_data": "w_plat_Rocket"}]
        ]
    }

# --- MESSAGE & CALLBACK HANDLERS ---
async def handle_message(session, message):
    chat_id = message["chat"]["id"]
    text = message.get("text", "")
    
    balance, state, temp_platform, temp_amount = get_user(chat_id)
    
    # Global Command
    if text == "/start" or text == "🔙 Back to Main Menu":
        update_user_state(chat_id, "MAIN_MENU")
        await send_message(session, chat_id, "👋 স্বাগতম! নিচে থেকে অপশন সিলেক্ট করুন।", get_main_menu())
        return

    if text == "🚀 Future Panel":
        update_user_state(chat_id, "FUTURE_MENU")
        await send_message(session, chat_id, "📂 ফিউচার প্যানেল মেনু:", get_future_menu())
        return

    # Future Menu Actions
    if state == "FUTURE_MENU":
        if text == "💰 Account Sell":
            update_user_state(chat_id, "WAITING_FOR_PLATFORM")
            await send_message(session, chat_id, "📝 কিসের অ্যাকাউন্ট বা কোন প্ল্যাটফর্মের অ্যাকাউন্ট বিক্রি করতে চান তা লিখে পাঠান:")
            return
            
        elif text == "👤 My Account":
            await send_message(session, chat_id, f"👤 <b>আপনার অ্যাকাউন্ট ইনফো:</b>\n\n💵 বর্তমান ব্যালেন্স: <b>{balance} টাকা</b>")
            return
            
        elif text == "💳 Withdraw / Payment":
            if balance <= 0:
                await send_message(session, chat_id, "❌ আপনার অ্যাকাউন্টে পর্যাপ্ত ব্যালেন্স নেই।")
                return
            update_user_state(chat_id, "WAITING_FOR_WITHDRAW_AMOUNT")
            await send_message(session, chat_id, f"💵 কত টাকা উইথড্র করতে চান লিখুন (আপনার ব্যালেন্স: {balance} টাকা):")
            return
            
        elif text == "📞 Support":
            await send_message(session, chat_id, f"📞 <b>সাপোর্ট টিম:</b>\n\nযেকোনো সমস্যায় এডমিনের সাথে যোগাযোগ করুন:\n👤 ইউজারনেম: {ADMIN_USERNAME}")
            return

    # FSM States - Account Selling Flow
    if state == "WAITING_FOR_PLATFORM":
        update_user_state(chat_id, "WAITING_FOR_SHEET_LINK", platform=text)
        await send_message(session, chat_id, f"🔗 ধন্যবাদ। এখন আপনার <b>{text}</b> অ্যাকাউন্টের ডিটেইলস সম্বলিত গুগল শিটের (Google Sheets) লিংকটি দিন:")
        return

    if state == "WAITING_FOR_SHEET_LINK":
        if "docs.google.com/spreadsheets" in text:
            order_id = create_order(chat_id, "SELL", f"Platform: {temp_platform} | Sheet: {text}")
            update_user_state(chat_id, "FUTURE_MENU")
            await send_message(session, chat_id, "✅ আপনার অ্যাকাউন্ট বিক্রির রিকোয়েস্টটি এডমিনের কাছে পাঠানো হয়েছে। অনুগ্রহ করে অপেক্ষা করুন।", get_future_menu())
            
            # Admin Notification
            admin_text = f"📥 <b>নতুন অ্যাকাউন্ট সেল রিকোয়েস্ট!</b>\n\n👤 ইউজার আইডি: <code>{chat_id}</code>\n🎮 প্ল্যাটফর্ম: {temp_platform}\n📊 গুগল শিট লিংক: {text}"
            admin_markup = {
                "inline_keyboard": [
                    [{"text": "🟢 Confirm Order", "callback_data": f"adm_conf_{order_id}"}],
                    [{"text": "🔴 Reject Order", "callback_data": f"adm_rej_{order_id}"}]
                ]
            }
            await send_message(session, ADMIN_ID, admin_text, admin_markup)
        else:
            await send_message(session, chat_id, "❌ এটা কোনো বৈধ গুগল শিট লিংক নয়। অনুগ্রহ করে সঠিক লিংকটি দিন:")
        return

    # FSM States - Withdraw Flow
    if state == "WAITING_FOR_WITHDRAW_AMOUNT":
        try:
            amount = float(text)
            if amount <= 0 or amount > balance:
                await send_message(session, chat_id, "❌ অবৈধ অ্যামাউন্ট! আপনার ব্যালেন্সের মধ্যে সঠিক সংখ্যা লিখুন:")
                return
            update_user_state(chat_id, "WAITING_FOR_WITHDRAW_METHOD", amount=amount)
            await send_message(session, chat_id, "💳 পেমেন্ট নেওয়ার মাধ্যমটি সিলেক্ট করুন:", get_withdraw_platforms())
        except ValueError:
            await send_message(session, chat_id, "❌ অনুগ্রহ করে শুধুমাত্র সংখ্যায় টাকার পরিমাণটি লিখুন:")
        return

    if state == "WAITING_FOR_WITHDRAW_NUMBER":
        # Here temp_platform stores selected method, temp_amount stores cash amount
        order_id = create_order(chat_id, "WITHDRAW", f"Method: {temp_platform} | Number: {text}", amount=temp_amount)
        update_balance(chat_id, -temp_amount) # Deduct balance instantly
        update_user_state(chat_id, "FUTURE_MENU")
        await send_message(session, chat_id, f"✅ আপনার {temp_amount} টাকা উইথড্র রিকোয়েস্টটি সাবমিট হয়েছে।", get_future_menu())
        
        # Admin Notification
        admin_text = f"💸 <b>নতুন উইথড্র রিকোয়েস্ট!</b>\n\n👤 ইউজার আইডি: <code>{chat_id}</code>\n💰 পরিমাণ: {temp_amount} টাকা\n🏦 মাধ্যম: {temp_platform}\n📱 নাম্বার: {text}"
        admin_markup = {
            "inline_keyboard": [
                [{"text": "✅ Accept Withdraw", "callback_data": f"w_acc_{order_id}"}],
                [{"text": "❌ Reject Withdraw", "callback_data": f"w_rej_{order_id}"}]
            ]
        }
        await send_message(session, ADMIN_ID, admin_text, admin_markup)
        return

    # Admin Input States (When Admin is replying with payment amount)
    if chat_id == ADMIN_ID:
        if state.startswith("ADMIN_ENTERING_PAYMENT_"):
            try:
                pay_amount = float(text)
                order_id = int(state.split("_")[-1])
                u_id, o_type, details, _, status = get_order(order_id)
                
                if status == "PENDING":
                    update_order_status(order_id, "CONFIRMED")
                    update_balance(u_id, pay_amount)
                    update_user_state(ADMIN_ID, "MAIN_MENU")
                    
                    await send_message(session, ADMIN_ID, "✅ ইউজার প্যানেলে টাকা সফলভাবে যুক্ত হয়েছে!")
                    await send_message(session, u_id, f"🎉 আপনার অ্যাকাউন্ট সেল অর্ডারটি কনফার্ম করা হয়েছে এবং আপনার অ্যাকাউন্টে <b>{pay_amount} টাকা</b> যোগ করা হয়েছে!")
                else:
                    await send_message(session, ADMIN_ID, "❌ এই অর্ডারটি ইতিমধ্যেই প্রসেস করা হয়ে গেছে।")
            except ValueError:
                await send_message(session, ADMIN_ID, "❌ অনুগ্রহ করে সঠিক অ্যামাউন্ট (সংখ্যায়) লিখুন:")
            return

async def handle_callback_query(session, callback_query):
    query_id = callback_query["id"]
    from_id = callback_query["from"]["id"]
    data = callback_query["data"]
    
    # Answer Callback Query to prevent loading icon
    await send_api_request(session, "answerCallbackQuery", {"callback_query_id": query_id})
    
    _, _, temp_platform, temp_amount = get_user(from_id)
    
    # User selected withdraw platform
    if data.startswith("w_plat_"):
        platform_name = data.split("_")[-1]
        update_user_state(from_id, "WAITING_FOR_WITHDRAW_NUMBER", platform=platform_name, amount=temp_amount)
        await send_message(session, from_id, f"📱 আপনার <b>{platform_name}</b> পার্সোনাল নাম্বারটি লিখুন:")
        return

    # Admin Actions
    if from_id == ADMIN_ID:
        # Account Sell Handling
        if data.startswith("adm_conf_"):
            order_id = data.split("_")[-1]
            update_user_state(ADMIN_ID, f"ADMIN_ENTERING_PAYMENT_{order_id}")
            await send_message(session, ADMIN_ID, "💰 এই অর্ডারের জন্য ইউজারকে কত টাকা দিতে চান তা সংখ্যায় লিখে পাঠান:")
            
        elif data.startswith("adm_rej_"):
            order_id = int(data.split("_")[-1])
            u_id, _, _, _, status = get_order(order_id)
            if status == "PENDING":
                update_order_status(order_id, "REJECTED")
                await send_message(session, ADMIN_ID, "🔴 অর্ডারটি রিজেক্ট করা হয়েছে।")
                await send_message(session, u_id, "❌ দুঃখিত, আপনার অ্যাকাউন্ট সেল রিকোয়েস্টটি এডমিন রিজেক্ট করে দিয়েছে।")

        # Withdraw Handling
        elif data.startswith("w_acc_"):
            order_id = int(data.split("_")[-1])
            u_id, _, _, amount, status = get_order(order_id)
            if status == "PENDING":
                update_order_status(order_id, "CONFIRMED")
                await send_message(session, ADMIN_ID, "✅ উইথড্র রিকোয়েস্ট সফলভাবে একসেপ্ট করা হয়েছে।")
                await send_message(session, u_id, f"💵 আপনার {amount} টাকা উইথড্র রিকোয়েস্টটি একসেপ্ট করা হয়েছে এবং পেমেন্ট সম্পন্ন হয়েছে।")
                
        elif data.startswith("w_rej_"):
            order_id = int(data.split("_")[-1])
            u_id, _, _, amount, status = get_order(order_id)
            if status == "PENDING":
                update_order_status(order_id, "REJECTED")
                update_balance(u_id, amount) # Refund money back to user balance
                await send_message(session, ADMIN_ID, "🔴 উইথড্র রিকোয়েস্ট রিজেক্ট করা হয়েছে এবং ইউজারের ব্যালেন্স রিফান্ড করা হয়েছে।")
                await send_message(session, u_id, f"❌ আপনার {amount} টাকা উইথড্র রিকোয়েস্টটি রিজেক্ট করা হয়েছে এবং টাকা আপনার মেইন ব্যালেন্সে ফেরত দেওয়া হয়েছে।")

# --- MAIN POLLING LOOP ---
async def main():
    async with ClientSession() as session:
        offset = 0
        logging.info("Bot started successfully using aiohttp polling...")
        
        while True:
            try:
                payload = {"offset": offset, "timeout": 20}
                url = f"{API_URL}/getUpdates"
                async with session.post(url, json=payload) as response:
                    updates = await response.json()
                    
                    if "result" in updates:
                        for update in updates["result"]:
                            offset = update["update_id"] + 1
                            
                            if "message" in update:
                                await handle_message(session, update["message"])
                            elif "callback_query" in update:
                                await handle_callback_query(session, update["callback_query"])
                                
            except Exception as e:
                logging.error(f"Error in polling loop: {e}")
            await asyncio.sleep(0.5)

if __name__ == "__main__":
    asyncio.run(main())
