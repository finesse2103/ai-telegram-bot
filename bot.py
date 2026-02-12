import os
import sqlite3
from datetime import datetime
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import requests
import urllib.parse
import threading
import time

# ============= ТВОИ КЛЮЧИ =============
DEEPSEEK_API_KEY = "sk-f960cb9054e048ff93c48d10c6e6e516"
TELEGRAM_TOKEN = "7216980289:AAHzEXM6Cwp1NPoBbxXxglSXoxaMpUcqPL8"

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

# ============= DEEPSEEK API =============
def deepseek_chat(messages):
    headers = {
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
        "Content-Type": "application/json"
    }
    
    data = {
        "model": "deepseek-chat",
        "messages": messages,
        "temperature": 0.7
    }
    
    try:
        response = requests.post(
            "https://api.deepseek.com/v1/chat/completions",
            headers=headers,
            json=data,
            timeout=30
        )
        response.raise_for_status()
        return response.json()['choices'][0]['message']['content']
    except Exception as e:
        print(f"DeepSeek Error: {e}")
        raise

# ============= ОБРАБОТЧИКИ =============
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    conn = init_db()
    
    chats = get_user_chats(conn, user_id)
    if not chats:
        chat_id = create_new_chat(conn, user_id)
    else:
        chat_id = chats[0][0]
    
    context.user_data['current_chat'] = chat_id
    context.user_data['db_conn'] = conn
    
    await update.message.reply_text(
        "🤖 *AI Бот готов!*\n\n"
        "🔹 Просто пиши сообщения — отвечу\n"
        "🔹 /draw [описание] — нарисовать картинку\n"
        "🔹 /newchat — новый диалог\n"
        "🔹 /chats — список чатов\n"
        "🔹 /clear — очистить историю\n\n"
        "_Работает на DeepSeek + Pollinations_",
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
    
    conn = context.user_data.get('db_conn')
    if not conn:
        conn = init_db()
        context.user_data['db_conn'] = conn
    
    chat_id = context.user_data.get('current_chat')
    if not chat_id:
        chats = get_user_chats(conn, user_id)
        if chats:
            chat_id = chats[0][0]
        else:
            chat_id = create_new_chat(conn, user_id)
        context.user_data['current_chat'] = chat_id
    
    save_message(conn, user_id, chat_id, "user", user_message)
    
    history = get_chat_history(conn, user_id, chat_id, 10)
    
    messages = []
    for role, content in history:
        messages.append({"role": role, "content": content})
    messages.append({"role": "user", "content": user_message})
    
    waiting_msg = await update.message.reply_text("💭 Думаю...")
    
    try:
        bot_reply = deepseek_chat(messages)
        save_message(conn, user_id, chat_id, "assistant", bot_reply)
        await waiting_msg.edit_text(bot_reply)
    except Exception as e:
        await waiting_msg.edit_text(f"❌ Ошибка: {str(e)}")

async def chats_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    conn = context.user_data.get('db_conn', init_db())
    
    chats = get_user_chats(conn, user_id)
    if not chats:
        await update.message.reply_text("У тебя нет чатов. Создай /newchat")
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
    print("🚀 Запускаем Telegram бота...")
    
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
    
    print("✅ Бот запущен и слушает сообщения!")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
