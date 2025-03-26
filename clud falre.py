import requests
import time
import schedule
import threading
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from datetime import datetime, timedelta

# تنظیمات اصلی
CLOUDFLARE_API_TOKEN = "aWtt8OsIROdqOE7XOuK1KgiAgqjwfLjzcH_1zpfr"
TELEGRAM_BOT_TOKEN = "7514795418:AAH7d2M1ZrUGsDLGjNOueavdYS2pbqlFIgg"
zone_id = "bcbccdf3c615ab3238b822e9e341a3bf"

# ذخیره دامنه‌ها، رکوردها و زمان‌بندی‌ها
domains = {}  # {دامنه: رکوردID}
domain_ips = {}  # {دامنه: [(IP, زمان_تغییر)]}

# تغییر IP در Cloudflare
def change_ip():
    now = datetime.now()
    for domain, record_id in domains.items():
        if domain in domain_ips:
            ip_schedule = domain_ips[domain]

            # پیدا کردن IP مناسب برای زمان فعلی
            for ip, change_time in ip_schedule:
                if change_time <= now:
                    update_cloudflare(domain, record_id, ip)
                    domain_ips[domain].remove((ip, change_time))

# ارسال درخواست به Cloudflare برای تغییر IP
def update_cloudflare(domain, record_id, new_ip):
    url = f"https://api.cloudflare.com/client/v4/zones/{zone_id}/dns_records/{record_id}"
    headers = {
        "Authorization": f"Bearer {CLOUDFLARE_API_TOKEN}",
        "Content-Type": "application/json"
    }
    data = {
        "type": "A",
        "name": domain,
        "content": new_ip,
        "ttl": 1,
        "proxied": False
    }
    response = requests.put(url, json=data, headers=headers)

    if response.status_code == 200:
        print(f"✅ IP دامنه {domain} به {new_ip} تغییر یافت")
    else:
        print(f"❌ خطا در تغییر IP دامنه {domain}: {response.text}")

# اجرای زمان‌بندی در ترد جداگانه
def run_scheduler():
    while True:
        schedule.run_pending()
        time.sleep(1)

# فرمان /adddomain برای افزودن دامنه
async def add_domain(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) != 2:
        await update.message.reply_text("فرمت صحیح: /adddomain دامنه رکوردID")
        return

    domain, record_id = context.args
    domains[domain] = record_id
    await update.message.reply_text(f"✅ دامنه {domain} با رکورد {record_id} اضافه شد.")

# فرمان /setip برای تنظیم IP مشخص با زمان‌بندی بر حسب ثانیه
async def set_ip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) != 3:
        await update.message.reply_text("فرمت صحیح: /setip دامنه IP زمان(به ثانیه)")
        return

    domain, new_ip, delay = context.args

    if domain not in domains:
        await update.message.reply_text(f"❌ دامنه {domain} ثبت نشده. ابتدا از دستور /adddomain استفاده کنید.")
        return

    # زمان تغییر IP را محاسبه کن
    try:
        change_time = datetime.now() + timedelta(seconds=int(delay))
    except ValueError:
        await update.message.reply_text("❌ زمان باید به‌صورت عدد صحیح باشد.")
        return

    if domain not in domain_ips:
        domain_ips[domain] = []
    domain_ips[domain].append((new_ip, change_time))

    await update.message.reply_text(f"✅ IP {new_ip} برای دامنه {domain} تنظیم شد و در {delay} ثانیه تغییر خواهد کرد.")

# فرمان /listinfo برای نمایش دامنه‌ها و زمان‌بندی‌ها
async def list_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = "📄 **وضعیت فعلی:**\n\n"

    if domains:
        message += "**✅ دامنه‌ها:**\n" + "\n".join([f"{domain} - {record_id}" for domain, record_id in domains.items()]) + "\n\n"
    else:
        message += "❌ دامنه‌ای ثبت نشده.\n\n"

    if domain_ips:
        message += "**🌐 زمان‌بندی IPها:**\n"
        for domain, schedules in domain_ips.items():
            for ip, time in schedules:
                message += f"{domain} → {ip} (در {time.strftime('%Y-%m-%d %H:%M:%S')})\n"
    else:
        message += "❌ هیچ IPی برای دامنه‌ها ثبت نشده.\n\n"

    await update.message.reply_text(message)

# تنظیم ربات تلگرام
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🤖 ربات مدیریت Cloudflare فعال شد.")

def main():
    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("adddomain", add_domain))
    app.add_handler(CommandHandler("setip", set_ip))
    app.add_handler(CommandHandler("listinfo", list_info))

    # زمان‌بندی تغییر IP
    schedule.every(1).seconds.do(change_ip)

    # اجرای زمان‌بندی در ترد جداگانه
    scheduler_thread = threading.Thread(target=run_scheduler, daemon=True)
    scheduler_thread.start()

    print("🤖 ربات فعال شد...")
    app.run_polling()

if __name__ == "__main__":
    main()