import os
import telebot
from telebot import types
from PIL import Image
import fitz  # PyMuPDF
import time
import json
from datetime import datetime
import threading
from flask import Flask, request
from threading import Thread

# === CONFIG ===
API_TOKEN = '7968076629:AAG6kq569q300tmBJkWSXrbBi-39d2HnRh4'
CHANNEL_USERNAME = '@PeshangAcademy'
ADMIN_CONTACT_LINK = 'https://t.me/MasterLordBoss'
BOT_OWNER_ID = 1908245207
STATS_FILE = 'bot_stats.json'

bot = telebot.TeleBot(API_TOKEN)
media_group_buffers = {}
last_media_time = {}

# === Flask App for Webhook ===
app = Flask(__name__)

@app.route('/')
def home():
    return "🤖 Bot is alive!"

@app.route(f"/{API_TOKEN}", methods=["POST"])
def webhook():
    json_string = request.get_data().decode("utf-8")
    update = telebot.types.Update.de_json(json_string)
    bot.process_new_updates([update])
    return '', 200


def set_webhook():
    webhook_url = f"https://{os.environ.get('APP_URL')}/{API_TOKEN}"
    bot.remove_webhook()
    time.sleep(1)
    bot.set_webhook(url=webhook_url)


# === Stats Handling ===
def load_stats():
    if not os.path.exists(STATS_FILE):
        return {
            "total_users": 0,
            "monthly_users": {},
            "new_users_this_month": []
        }
    with open(STATS_FILE, 'r') as f:
        return json.load(f)

def save_stats(stats):
    with open(STATS_FILE, 'w') as f:
        json.dump(stats, f)

def update_user_stats(user_id):
    stats = load_stats()
    month = datetime.now().strftime("%Y-%m")
    if str(user_id) not in stats.get("new_users_this_month", []):
        stats['total_users'] += 1
        stats['new_users_this_month'].append(str(user_id))
    if month not in stats['monthly_users']:
        stats['monthly_users'][month] = []
    if str(user_id) not in stats['monthly_users'][month]:
        stats['monthly_users'][month].append(str(user_id))
    save_stats(stats)

def get_stats():
    stats = load_stats()
    month = datetime.now().strftime("%Y-%m")
    total = stats.get('total_users', 0)
    monthly = len(stats['monthly_users'].get(month, []))
    new_this_month = len(stats.get("new_users_this_month", []))
    return total, monthly, new_this_month


# === User Subscription Check ===
def is_user_subscribed(user_id):
    try:
        member = bot.get_chat_member(CHANNEL_USERNAME, user_id)
        return member.status in ['member', 'creator', 'administrator']
    except:
        return False


# === Handlers ===

@bot.message_handler(commands=['start'])
def handle_start(message):
    update_user_stats(message.from_user.id)
    if not is_user_subscribed(message.from_user.id):
        join_button = types.InlineKeyboardMarkup()
        join_button.add(
            types.InlineKeyboardButton(
                "سەردانی کەناڵەکەمان بکە ❤️",
                url=f"https://t.me/{CHANNEL_USERNAME.strip('@')}"))
        bot.send_message(
            message.chat.id,
            "👋 تکایە یەکەم سەردانی کەناڵەکەمان بکە بۆ بەکارهێنانی بۆتەکە",
            reply_markup=join_button)
        return
    kb = types.InlineKeyboardMarkup()
    kb.add(
        types.InlineKeyboardButton(
            "سەردانی کەناڵەکەمان بکە ❤️",
            url=f"https://t.me/{CHANNEL_USERNAME.strip('@')}"))
    welcome_text = (
        "👋 بەخێربێیت بۆ بۆتی گۆڕینی وێنە بۆ پی دی ئێف و پی دی ئێف بۆ وێنە\n\n"
        "🚀 ئەم بۆتە ئەم دوو ئەرکەی هەیە:\n\n"
        "- فایلی پی دی ئێف بنێرە تاکو بیکەم بە وێنە\n"
        "- وێنە بنێرە تاکو بیکەم بە فایلێکی پی دی ئێف")
    bot.send_message(message.chat.id, welcome_text, reply_markup=kb)

@bot.message_handler(commands=['info'])
def handle_info(message):
    if message.from_user.id != BOT_OWNER_ID:
        return
    total, monthly, new_this_month = get_stats()
    stats_text = (f"📊 ئاماری بۆت:\n"
                  f"- 👥 کۆی بەکارهێنەرەکان: {total}\n"
                  f"- 📅 بەکارهێنەری ئەم مانگە: {monthly}\n"
                  f"- 🆕 بەکارهێنەری نوێی ئەم مانگە: {new_this_month}")
    bot.send_message(message.chat.id, stats_text)

@bot.message_handler(content_types=['photo'])
def handle_photo(message):
    chat_id = message.chat.id
    user_id = message.from_user.id
    if not is_user_subscribed(user_id):
        return
    media_group_id = message.media_group_id
    if media_group_id:
        if media_group_id not in media_group_buffers:
            media_group_buffers[media_group_id] = []
        media_group_buffers[media_group_id].append(message)
        bot.send_message(
            chat_id,
            f"🖼 وێنەی {len(media_group_buffers[media_group_id])} وەرگیرا")
        last_media_time[media_group_id] = time.time()
    else:
        bot.send_message(chat_id, "🖼 وێنەی یەکەم وەرگیرا")
        process_images_to_pdf(chat_id, [message.photo[-1].file_id])

def media_group_watcher():
    while True:
        time.sleep(2)
        now = time.time()
        to_process = [
            group_id for group_id, last_time in last_media_time.items()
            if now - last_time > 2
        ]
        for group_id in to_process:
            msgs = media_group_buffers.pop(group_id, [])
            last_media_time.pop(group_id, None)
            file_ids = [m.photo[-1].file_id for m in msgs]
            process_images_to_pdf(msgs[0].chat.id, file_ids)

def process_images_to_pdf(chat_id, file_ids):
    try:
        images = []
        for fid in file_ids:
            file_info = bot.get_file(fid)
            downloaded = bot.download_file(file_info.file_path)
            img_path = f"temp_{fid}.jpg"
            with open(img_path, 'wb') as f:
                f.write(downloaded)
            img = Image.open(img_path).convert('RGB')
            images.append(img)
            os.remove(img_path)
        pdf_path = f"output_{chat_id}.pdf"
        images[0].save(pdf_path, save_all=True, append_images=images[1:])
        with open(pdf_path, 'rb') as pdf_file:
            kb = types.InlineKeyboardMarkup()
            kb.add(
                types.InlineKeyboardButton(
                    "سەردانی کەناڵەکەمان بکە ❤️",
                    url=f"https://t.me/{CHANNEL_USERNAME.strip('@')}"))
            bot.send_document(chat_id,
                              pdf_file,
                              caption="📄 فەرموو ئەمە فایلی پی دی ئێفەکەتە",
                              reply_markup=kb)
        os.remove(pdf_path)
    except Exception:
        send_error(chat_id)

@bot.message_handler(content_types=['document'])
def handle_pdf(message):
    chat_id = message.chat.id
    user_id = message.from_user.id
    if not is_user_subscribed(user_id):
        return
    if message.document.mime_type != 'application/pdf':
        bot.send_message(chat_id, "🔄 تکایە وێنە یاخود فایلی پی دی ئێف بنێرە")
        return
    try:
        file_info = bot.get_file(message.document.file_id)
        downloaded = bot.download_file(file_info.file_path)
        pdf_path = f"input_{chat_id}.pdf"
        with open(pdf_path, 'wb') as f:
            f.write(downloaded)
        doc = fitz.open(pdf_path)
        for i, page in enumerate(doc):
            pix = page.get_pixmap(dpi=150)
            image_path = f"page_{i + 1}_{chat_id}.png"
            pix.save(image_path)
            with open(image_path, 'rb') as img:
                bot.send_photo(chat_id, img, caption=f"🖼 وێنەی {i + 1}")
            os.remove(image_path)
        doc.close()
        os.remove(pdf_path)
    except Exception:
        send_error(chat_id)

def send_error(chat_id):
    kb = types.InlineKeyboardMarkup()
    kb.add(
        types.InlineKeyboardButton("🧑🏻‍💻 پەیوەندی بکە بە خاوەنی بۆت",
                                   url=ADMIN_CONTACT_LINK))
    bot.send_message(chat_id,
                     "⚠ ببورە کێشەیەکی تەکنیکی هەیە لە بۆتەکە",
                     reply_markup=kb)

@bot.message_handler(func=lambda m: True)
def handle_other_messages(message):
    if message.text != "/start" and is_user_subscribed(message.from_user.id):
        bot.send_message(message.chat.id,
                         "🔄 تکایە وێنە یاخود فایلی پی دی ئێف بنێرە")


# === Start Everything ===
if __name__ == "__main__":
    threading.Thread(target=media_group_watcher, daemon=True).start()
    set_webhook()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
