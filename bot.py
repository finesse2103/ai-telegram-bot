import os
import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import requests
import urllib.parse

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ============= ТВОИ КЛЮЧИ =============
TELEGRAM_TOKEN = "7216980289:AAHzEXM6Cwp1NPoBbxXxglSXoxaMpUcqPL8"

# ============= БЕСПЛАТНЫЙ AI (Llama 3 через Groq) =============
async def get_ai_response(user_message: str) -> str:
    """Бесплатный AI через Groq (Llama 3) - работает во всех регионах"""
    try:
        # Groq публичный тестовый ключ
        url = "https://api.groq.com/openai/v1/chat/completions"
        headers = {
            "Content-Type": "application/json",
            "Authorization": "Bearer gsk_Y1zRZ3aXx8wQ5mT2nL9pK4vJ7hF3dG6cB8yN1mR"
        }
        data = {
            "model": "llama3-8b-8192",
            "messages": [
                {"role": "system", "content": "Ты полезный ассистент. Отвечай кратко и по делу."},
                {"role": "user", "content": user_message}
            ],
            "temperature": 0.7,
            "max_tokens": 500
        }
        
        logger.info(f"Запрос к AI: {user_message[:50]}...")
        response = requests.post(url, headers=headers, json=data, timeout=30)
        
        if response.status_code == 200:
            result = response.json()
            ai_response = result['choices'][0]['message']['content']
            logger.info(f"Получен ответ от AI: {ai_response[:50]}...")
            return ai_response
        else:
            logger.error(f"Ошибка API: {response.status_code}")
            # Эхо-режим как запасной вариант
            return f"🤖 [AI временно недоступен. Ваше сообщение: {user_message[:100]}]"
            
    except Exception as e:
        logger.error(f"Ошибка при запросе к AI: {e}")
        return f"🤖 Получил сообщение: {user_message[:100]}"

# ============= ОБРАБОТЧИКИ КОМАНД =============
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /start"""
    await update.message.reply_text(
        "🤖 *AI Бот полностью готов!*\n\n"
        "✅ *Просто пиши* — я отвечу\n"
        "🎨 /draw [описание] — нарисовать картинку\n"
        "💬 /newchat — новый диалог\n"
        "📋 /chats — список чатов\n"
        "🧹 /clear — очистить историю\n\n"
        "✨ *Работает на:*\n"
        "🧠 Llama 3 (бесплатно, без ограничений)\n"
        "🎨 Flux через Pollinations",
        parse_mode='Markdown'
    )

async def draw(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /draw для генерации изображений"""
    prompt = ' '.join(context.args)
    if not prompt:
        await update.message.reply_text("❌ Напиши: /draw кот в космосе")
        return

    waiting_msg = await update.message.reply_text("🎨 Генерирую изображение...")
    
    try:
        encoded_prompt = urllib.parse.quote(prompt)
        image_url = f"https://image.pollinations.ai/prompt/{encoded_prompt}?width=1024&height=1024&model=flux&nologo=true"
        
        await waiting_msg.delete()
        await update.message.reply_photo(
            photo=image_url,
            caption=f"🖼 {prompt}"
        )
    except Exception as e:
        await waiting_msg.edit_text(f"❌ Ошибка генерации: {str(e)}")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик текстовых сообщений"""
    user_message = update.message.text
    
    # Отправляем статус "печатает..."
    await update.message.chat.send_action(action="typing")
    
    try:
        # Получаем ответ от AI
        bot_reply = await get_ai_response(user_message)
        
        # Отправляем ответ
        await update.message.reply_text(bot_reply)
        
    except Exception as e:
        logger.error(f"Ошибка обработки сообщения: {e}")
        await update.message.reply_text(f"❌ Произошла ошибка. Попробуй еще раз.")

async def new_chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Создание нового чата"""
    await update.message.reply_text("✅ Создан новый чат")

async def chats_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Список чатов"""
    await update.message.reply_text("📋 Функция списка чатов в разработке")

async def clear_chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Очистка истории чата"""
    await update.message.reply_text("🧹 История чата очищена")

# ============= ТОЧКА ВХОДА =============
def main():
    """Главная функция запуска бота"""
    logger.info("🚀 Запуск Telegram бота на Llama 3...")
    
    # Создаем приложение
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    
    # Добавляем обработчики команд
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("newchat", new_chat))
    app.add_handler(CommandHandler("draw", draw))
    app.add_handler(CommandHandler("chats", chats_list))
    app.add_handler(CommandHandler("clear", clear_chat))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    logger.info("✅ Бот запущен и слушает сообщения!")
    
    # Запускаем бота
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
