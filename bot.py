import os
import logging
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, ConversationHandler, CallbackQueryHandler
from deepseek import DeepSeekAPI
import replicate
import sqlite3
from sqlite3 import Connection
import json

# ============= КОНФИГУРАЦИЯ =============
DEEPSEEK_API_KEY = "sk-..."  # ВСТАВЬ СВОЙ КЛЮЧ
REPLICATE_API_TOKEN = "r-..."  # ВСТАВЬ СВОЙ ТОКЕН
TELEGRAM_TOKEN = "7234567890:AAH..."  # ВСТАВЬ ТОКЕН БОТА

# Инициализация API
deepseek = DeepSeekAPI(DEEPSEEK_API_KEY)
os.environ["REPLICATE_API_TOKEN"] = REPLICATE_API_TOKEN

# ============= БАЗА ДАННЫХ =============
def init_db():
    conn = sqlite3.connect('chats.db')
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

def get_chat_history(conn, user_id, chat_id, limit=20):
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
    import uuid
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
    
    # Создаем первый чат для пользователя
    chats = get_user_chats(conn, user_id)
    if not chats:
        chat_id = create_new_chat(conn, user_id)
    else:
        chat_id = chats[0][0]
    
    context.user_data['current_chat'] = chat_id
    context.user_data['db_conn'] = conn
    
    await update.message.reply_text(
        "🤖 *AI Бот готов к работе!*\n\n"
        "🔹 Просто пиши сообщения — я отвечу\n"
        "🔹 /draw [описание] — нарисовать картинку\n"
        "🔹 /newchat — новый диалог\n"
        "🔹 /chats — переключить чат\n"
        "🔹 /clear — очистить историю\n\n"
        "_Работает на DeepSeek + Replicate_",
        parse_mode='Markdown'
    )

async def new_chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    conn = context.user_data.get('db_conn', init_db())
    
    chat_id = create_new_chat(conn, user_id)
    context.user_data['current_chat'] = chat_id
    context.user_data['db_conn'] = conn
    
    await update.message.reply_text(f"✅ Создан новый чат #{chat_id}")

async def draw(update: Update, context: ContextTypes.DEFAULT_TYPE):
    prompt = ' '.join(context.args)
    if not prompt:
        await update.message.reply_text("❌ Напиши описание: /draw кот в космосе")
        return
    
    waiting_msg = await update.message.reply_text("🎨 Генерирую изображение...")
    
    try:
        output = replicate.run(
            "black-forest-labs/flux-schnell",
            input={"prompt": prompt}
        )
        
        image_url = output[0] if isinstance(output, list) else output
        await waiting_msg.delete()
        await update.message.reply_photo(photo=image_url, caption=f"🖼 {prompt}")
    except Exception as e:
        await waiting_msg.edit_text(f"❌ Ошибка: {str(e)}")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_message = update.message.text
    
    conn = context.user_data.get('db_conn', init_db())
    chat_id = context.user_data.get('current_chat')
    
    if not chat_id:
        chats = get_user_chats(conn, user_id)
        if chats:
            chat_id = chats[0][0]
        else:
            chat_id = create_new_chat(conn, user_id)
        context.user_data['current_chat'] = chat_id
        context.user_data['db_conn'] = conn
    
    # Сохраняем сообщение пользователя
    save_message(conn, user_id, chat_id, "user", user_message)
    
    # Получаем историю
    history = get_chat_history(conn, user_id, chat_id, 10)
    
    # Формируем контекст для DeepSeek
    messages = []
    for role, content in history:
        messages.append({"role": role, "content": content})
    messages.append({"role": "user", "content": user_message})
    
    waiting_msg = await update.message.reply_text("💭 Думаю...")
    
    try:
        response = deepseek.chat_completion(messages)
        bot_reply = response['choices'][0]['message']['content']
        
        # Сохраняем ответ бота
        save_message(conn, user_id, chat_id, "assistant", bot_reply)
        
        await waiting_msg.edit_text(bot_reply)
    except Exception as e:
        await waiting_msg.edit_text(f"❌ Ошибка: {str(e)}")

# ============= ЗАПУСК =============
def main():
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("newchat", new_chat))
    app.add_handler(CommandHandler("draw", draw))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    print("✅ Бот запущен...")
    app.run_polling()

if __name__ == "__main__":
    main()
