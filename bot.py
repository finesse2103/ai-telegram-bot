import os
import sqlite3
from datetime import datetime
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import requests
import urllib.parse
import uuid
import logging

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ============= ТВОИ КЛЮЧИ =============
TELEGRAM_TOKEN = "7216980289:AAHzEXM6Cwp1NPoBbxXxglSXoxaMpUcqPL8"
DEEPSEEK_KEY = "sk-f960cb9054e048ff93c48d10c6e6e516"

# ============= БЕСПЛАТНЫЙ AI (DeepSeek) =============
def get_ai_response(user_message):
    """Получение ответа от DeepSeek API"""
    try:
        headers = {
            "Authorization": f"Bearer {DEEPSEEK_KEY}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": "deepseek-chat",
            "messages": [
                {"role": "system", "content": "Ты полезный ассистент. Отвечай кратко и по делу."},
                {"role": "user", "content": user_message}
            ],
            "temperature": 0.7,
            "max_tokens": 500
        }
        
        logger.info(f"Отправка запроса к DeepSeek: {user_message[:50]}...")
        response = requests.post(
            "https://api.deepseek.com/v1/chat/completions",
            headers=headers,
            json=payload,
            timeout=30
        )
        
        if response.status_code == 200:
            result = response.json()
            ai_response = result['choices'][0]['message']['content']
            logger.info(f"Получен ответ от DeepSeek: {ai_response[:50]}...")
            return ai_response
        else:
            logger.error(f"Ошибка DeepSeek API: {response.status_code}")
            logger.error(f"Ответ: {response.text}")
            return f"🤖 [DeepSeek временно недоступен. Ваше сообщение: {user_message[:50]}...]"
            
    except Exception as e:
        logger.error(f"Ошибка при запросе к DeepSeek: {e}")
        return f"🤖 [Ошибка: {str(e)[:50]}]"

# ============= БАЗА ДАННЫХ =============
def init_db():
    conn = sqlite3.connect('chats.db', check_same_thread=False)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS conversations
                 (user_id INTEGER, chat_id TEXT, role TEXT, content TEXT, timestamp DATETIME)''')
    c.execute('''CREATE TABLE IF NOT EXISTS user_chats
                 (user_id INTEGER, chat_id TEXT, title TEXT, created_at DATETIME)''')
    conn.commit()
    return conn

def save_message(conn, user_id, chat_id, role, content):
    c = conn.cursor()
    c.execute("INSERT INTO conversations VALUES (?,?,?,?,?)",
              (user_id, chat_id, role, content, datetime.now()))
    conn.commit()

def get_chat_history(conn, user_id, chat_id, limit=5):
    c = conn.cursor()
    c.execute("SELECT role, content FROM conversations WHERE user_id=? AND chat_id=? ORDER BY timestamp DESC LIMIT ?",
              (user_id, chat_id, limit))
    messages = c.fetchall()
    messages.reverse()
    return messages

def get_user_chats(conn, user_id):
    c = conn.cursor()
    c.execute("SELECT chat_id, title, created_at FROM user_chats WHERE user_id=? ORDER BY created_at DESC", (user_id,))
    return c.fetchall()

def create_new_chat(conn, user_id):
    chat_id = str(uuid.uuid4())[:8]
    c = conn.cursor()
    c.execute("INSERT INTO user_chats VALUES (?,?,?,?)",
              (user_id, chat_id, f"Чат {chat_id}", datetime.now()))
    conn.commit()
    return chat_id

# ============= ОБРАБОТЧИКИ КОМАНД =============
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    conn = init_db()
    
    # Получаем или создаем чат
    chats = get_user_chats(conn, user_id)
    if not chats:
        chat_id = create_new_chat(conn, user_id)
    else:
        chat_id = chats[0][0]
    
    context.user_data['current_chat'] = chat_id
    context.user_data['db_conn'] = conn
    
    await update.message.reply_text(
        "🤖 *AI Бот полностью готов!*\n\n"
        "✅ *Просто пиши* — я отвечу\n"
        "🎨 /draw [описание] — нарисовать картинку\n"
        "💬 /newchat — новый диалог\n"
        "📋 /chats — список чатов\n"
        "🧹 /clear — очистить историю\n\n"
        "✨ *Работает на DeepSeek AI*",
        parse_mode='Markdown'
    )

async def draw(update: Update, context: ContextTypes.DEFAULT_TYPE):
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
        await waiting_msg.edit_text(f"❌ Ошибка: {str(e)}")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_message = update.message.text
    
    # Получаем соединение с БД
    conn = context.user_data.get('db_conn')
    if not conn:
        conn = init_db()
        context.user_data['db_conn'] = conn
    
    # Получаем текущий чат
    chat_id = context.user_data.get('current_chat')
    if not chat_id:
        chats = get_user_chats(conn, user_id)
        if chats:
            chat_id = chats[0][0]
        else:
            chat_id = create_new_chat(conn, user_id)
        context.user_data['current_chat'] = chat_id
    
    # Сохраняем сообщение пользователя
    save_message(conn, user_id, chat_id, "user", user_message)
    
    # Отправляем статус "печатает..."
    await update.message.chat.send_action(action="typing")
    
    try:
        # Получаем ответ от AI
        bot_reply = get_ai_response(user_message)
        
        # Сохраняем ответ
        save_message(conn, user_id, chat_id, "assistant", bot_reply)
        
        # Отправляем ответ
        await update.message.reply_text(bot_reply)
        
    except Exception as e:
        error_msg = f"❌ Ошибка: {str(e)}"
        logger.error(error_msg)
        await update.message.reply_text(error_msg)

async def new_chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    conn = context.user_data.get('db_conn', init_db())
    
    chat_id = create_new_chat(conn, user_id)
    context.user_data['current_chat'] = chat_id
    context.user_data['db_conn'] = conn
    
    await update.message.reply_text(f"✅ Создан новый чат #{chat_id}")

async def chats_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    conn = context.user_data.get('db_conn', init_db())
    
    chats = get_user_chats(conn, user_id)
    if not chats:
        await update.message.reply_text("📭 У тебя нет чатов. Создай /newchat")
        return
    
    text = "📁 *Твои чаты:*\n\n"
    for i, (chat_id, title, created) in enumerate(chats, 1):
        current = " ✅" if context.user_data.get('current_chat') == chat_id else ""
        text += f"{i}. `{chat_id}` - {title}{current}\n"
    
    text += "\n🔹 Переключиться: /switch [ID чата]"
    await update.message.reply_text(text, parse_mode='Markdown')

async def switch_chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("❌ Укажи ID чата: /switch 12345678")
        return
    
    chat_id = context.args[0]
    user_id = update.effective_user.id
    conn = context.user_data.get('db_conn', init_db())
    
    chats = [c[0] for c in get_user_chats(conn, user_id)]
    
    if chat_id in chats:
        context.user_data['current_chat'] = chat_id
        await update.message.reply_text(f"✅ Переключился на чат {chat_id}")
    else:
        await update.message.reply_text("❌ Чат не найден")

async def clear_chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    chat_id = context.user_data.get('current_chat')
    conn = context.user_data.get('db_conn', init_db())
    
    c = conn.cursor()
    c.execute("DELETE FROM conversations WHERE user_id=? AND chat_id=?", (user_id, chat_id))
    conn.commit()
    
    await update.message.reply_text(f"🧹 История чата {chat_id} очищена")

# ============= ЗАПУСК =============
def main():
    logger.info("🚀 Запуск Telegram бота...")
    
    # Создаем приложение
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    
    # Добавляем обработчики
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("newchat", new_chat))
    app.add_handler(CommandHandler("draw", draw))
    app.add_handler(CommandHandler("chats", chats_list))
    app.add_handler(CommandHandler("switch", switch_chat))
    app.add_handler(CommandHandler("clear", clear_chat))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    logger.info("✅ Бот запущен и готов к работе!")
    
    # Запускаем бота
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
