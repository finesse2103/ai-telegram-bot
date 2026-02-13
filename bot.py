import os
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import requests

# ============= ТВОИ КЛЮЧИ =============
TELEGRAM_TOKEN = "7216980289:AAHzEXM6Cwp1NPoBbxXxglSXoxaMpUcqPL8"

# ============= GEMINI =============
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("✅ Бот работает! Gemini API пока отключен для теста.")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🤖 Бот запущен!")

def main():
    print("🚀 Запуск...")
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    print("✅ Бот готов!")
    app.run_polling()

if __name__ == "__main__":
    main()
