import os
from fastapi import FastAPI, Request, Response, HTTPException
from telegram import Update, Bot
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, MessageHandler, filters
import uvicorn

TOKEN = os.getenv("7921062029:AAECf80Pj4mtaPJS5TbR2Nl4qx3uSQNZsXo")
WEBHOOK_PATH = f"/webhook/{TOKEN}"
WEBHOOK_URL = os.getenv("WEBHOOK_URL")  # e.g. https://yourapp.scalingo.io/webhook/<token>

if not TOKEN or not WEBHOOK_URL:
    raise RuntimeError("BOT_TOKEN and WEBHOOK_URL env variables must be set")

app = FastAPI()
bot = Bot(token=TOKEN)

# Create telegram bot application
application = ApplicationBuilder().token(TOKEN).build()

# /start command handler
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Hello! I am your Telegram bot running with FastAPI on Scalingo."
    )

# /info command handler
async def info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    await update.message.reply_text(f"Hello, {user.first_name}! This is your info command.")

# Echo all other text messages
async def echo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    await update.message.reply_text(f"You said: {text}")

application.add_handler(CommandHandler("start", start))
application.add_handler(CommandHandler("info", info))
application.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), echo))

# Telegram webhook handler endpoint
@app.post(WEBHOOK_PATH)
async def telegram_webhook(request: Request):
    # Telegram sends update as JSON
    try:
        json_data = await request.json()
        update = Update.de_json(json_data, bot)
        await application.update_queue.put(update)
        return Response(status_code=200)
    except Exception as e:
        return Response(content=str(e), status_code=400)

# Set webhook on startup
@app.on_event("startup")
async def on_startup():
    # Set webhook to Telegram API
    await bot.set_webhook(url=WEBHOOK_URL)
    print(f"Webhook set to: {WEBHOOK_URL}")

# Remove webhook on shutdown (optional)
@app.on_event("shutdown")
async def on_shutdown():
    await bot.delete_webhook()
    print("Webhook removed")

if __name__ == "__main__":
    # Local development with uvicorn
    uvicorn.run("bot:app", host="0.0.0.0", port=int(os.getenv("PORT", 8000)), reload=True)
