import os
import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import requests

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ============= ТВОИ КЛЮЧИ =============
TELEGRAM_TOKEN = "7216980289:AAHzEXM6Cwp1NPoBbxXxglSXoxaMpUcqPL8"
GEMINI_API_KEY = "AIzaSyAGwROvPS3Jw8XcyjOuwX2AtRc2rdciYg8"

# ============= GEMINI API =============
async def get_gemini_response(user_message: str) -> str:
    """Отправляет запрос к Gemini API и возвращает ответ."""
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"
    headers = {'Content-Type': 'application/json'}
    data = {
        "contents": [{
            "parts": [{"text": user_message}]
        }]
    }

    try:
        logger.info(f"Запрос к Gemini: {user_message[:50]}...")
        response = requests.post(url, headers=headers, json=data, timeout=15)
        response.raise_for_status()
        result = response.json()

        if 'candidates' in result and result['candidates']:
            text = result['candidates'][0]['content']['parts'][0]['text']
            logger.info("Ответ от Gemini получен")
            return text
        else:
            logger.warning("Неожиданный ответ Gemini")
            return "🤖 Не удалось получить осмысленный ответ."
    except requests.exceptions.RequestException as e:
        logger.error(f"Ошибка сети/API Gemini: {e}")
        return f"🤖 Ошибка связи с AI. Пожалуйста, попробуй позже."
    except Exception as e:
        logger.error(f"Неизвестная ошибка Gemini: {e}")
        return "🤖 Произошла внутренняя ошибка."

# ============= ОБРАБОТЧИКИ КОМАНД =============
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🤖 *AI Бот полностью готов!*\n\n"
        "✅ *Просто пиши* — я отвечу\n"
        "🎨 /draw [описание] — нарисовать картинку\n\n"
        "✨ *Работает на Google Gemini 1.5 Flash*",
        parse_mode='Markdown'
    )

async def draw(update: Update, context: ContextTypes.DEFAULT_TYPE):
    prompt = ' '.join(context.args)
    if not prompt:
        await update.message.reply_text("❌ Напиши: /draw кот в космосе")
        return

    waiting_msg = await update.message.reply_text("🎨 Генерирую изображение...")
    try:
        import urllib.parse
        encoded_prompt = urllib.parse.quote(prompt)
        image_url = f"https://image.pollinations.ai/prompt/{encoded_prompt}?width=1024&height=1024&model=flux&nologo=true"
        await waiting_msg.delete()
        await update.message.reply_photo(photo=image_url, caption=f"🖼 {prompt}")
    except Exception as e:
        await waiting_msg.edit_text(f"❌ Ошибка генерации: {str(e)}")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_message = update.message.text
    await update.message.chat.send_action(action="typing")
    bot_reply = await get_gemini_response(user_message)
    await update.message.reply_text(bot_reply)

# ============= ТОЧКА ВХОДА =============
def main():
    logger.info("🚀 Запуск Telegram бота на Gemini...")
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("draw", draw))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    logger.info("✅ Бот запущен и слушает сообщения!")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
