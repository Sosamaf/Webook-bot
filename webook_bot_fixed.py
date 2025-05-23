from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    CallbackQueryHandler, ContextTypes, filters, ConversationHandler
)
import requests
from bs4 import BeautifulSoup
import csv
import os
from datetime import datetime
from telegram.ext import Defaults

TOKEN = os.getenv("TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")
ADMIN_ID = 1144370824

ASK_TICKETS, ASK_DATE = range(2)

def save_booking(user_name, event_title, event_url, tickets, date):
    with open("bookings.csv", mode="a", newline="", encoding='utf-8') as file:
        writer = csv.writer(file)
        writer.writerow([user_name, event_title, event_url, tickets, date, datetime.now().isoformat()])

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("مرحبًا! أرسل اسم الفعالية التي ترغب في حجز تذكرة لها من WeBook.")

async def handle_query(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.message.text
    context.user_data['last_query'] = query
    await update.message.reply_text(f"جارٍ البحث عن: {query} ...")
    results = search_webook(query)
    if results:
        for title, url in results:
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("احجز الآن", callback_data=f"book|{title}|{url}")]
            ])
            await update.message.reply_text(f"• {title}
{url}", reply_markup=keyboard)
    else:
        await update.message.reply_text("لم يتم العثور على نتائج.")

def search_webook(event_name):
    search_url = f"https://webook.com/ar/search?query={event_name.replace(' ', '%20')}"
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        response = requests.get(search_url, headers=headers)
        if response.status_code != 200:
            return None
        soup = BeautifulSoup(response.text, 'html.parser')
        results = []
        for card in soup.select('.card-event')[:3]:
            title = card.select_one('.card-event-title')
            link_tag = card.find('a', href=True)
            if title and link_tag:
                full_link = f"https://webook.com{link_tag['href']}"
                results.append((title.text.strip(), full_link))
        return results if results else None
    except:
        return None

async def handle_booking(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    _, title, url = query.data.split("|", 2)
    context.user_data['event_title'] = title
    context.user_data['event_url'] = url
    await query.message.reply_text("كم عدد التذاكر التي ترغب بحجزها؟")
    return ASK_TICKETS

async def ask_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['tickets'] = update.message.text
    await update.message.reply_text("ما هو تاريخ الحجز؟ (مثال: 2025-06-15)")
    return ASK_DATE

async def confirm_booking(update: Update, context: ContextTypes.DEFAULT_TYPE):
    date = update.message.text
    context.user_data['date'] = date
    name = update.effective_user.full_name
    title = context.user_data['event_title']
    url = context.user_data['event_url']
    tickets = context.user_data['tickets']

    save_booking(name, title, url, tickets, date)
    await update.message.reply_text(
        f"تم الحجز بنجاح لـ {name}:

{title}
عدد التذاكر: {tickets}
التاريخ: {date}
{url}"
    )
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("تم إلغاء الحجز.")
    return ConversationHandler.END

async def view_bookings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("❌ لا تملك صلاحية الوصول.")
        return

    query = " ".join(context.args) if context.args else None
    try:
        with open("bookings.csv", "r", encoding="utf-8") as file:
            bookings = file.readlines()

        filtered = []
        for row in bookings:
            name, event, url, tickets, date, timestamp = row.strip().split(",", 5)
            if not query or query.lower() in event.lower():
                filtered.append(f"• {name}
{event}
{url}
عدد: {tickets} | التاريخ: {date}
")

        if filtered:
            await update.message.reply_text("".join(filtered), disable_web_page_preview=True)
        else:
            await update.message.reply_text("لا توجد حجوزات مطابقة.")

    except FileNotFoundError:
        await update.message.reply_text("❌ لا يوجد ملف حجوزات.")

def main():
    app = ApplicationBuilder().token(TOKEN).webhook_path("/webhook").webhook_url(WEBHOOK_URL).build()

    conv_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(handle_booking, pattern=r'^book\|')],
        states={
            ASK_TICKETS: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_date)],
            ASK_DATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, confirm_booking)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    app.add_handler(conv_handler)
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("الحجوزات", view_bookings))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_query))

    app.run_webhook(listen="0.0.0.0", port=10000)

if __name__ == '__main__':
    main()
