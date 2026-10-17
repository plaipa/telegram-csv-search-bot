# اجرا و تست روی کامپیوتر خودتان

ربات فقط تا وقتی کامپیوتر روشن است و برنامه باز است کار می‌کند. برای تست عالی است، برای استفاده‌ی دائمی سرور بهتر است.

## ۱. نصب پایتون
- **ویندوز:** از [python.org/downloads](https://www.python.org/downloads/) نسخه‌ی **3.13** را نصب کنید. در اولین صفحه‌ی نصب تیک **Add python.exe to PATH** را بزنید.
- **مک:** از همان سایت نسخه‌ی 3.13 را نصب کنید.
- **لینوکس:** معمولاً نصب است (`python3 --version`).

## ۲. دریافت کد
در صفحه‌ی مخزن در گیت‌هاب: دکمه‌ی سبز **Code → Download ZIP**. فایل را از حالت فشرده خارج کنید.

## ۳. نصب کتابخانه‌ها
در پوشه‌ی کد، روی نوار آدرس File Explorer بنویسید `cmd` و Enter بزنید تا ترمینال در همان پوشه باز شود. بعد:

**ویندوز:**
```bat
py -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
pip install --only-binary=:all: cryptg
copy .env.example .env
notepad .env
```
**مک / لینوکس:**
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install --only-binary=:all: cryptg
cp .env.example .env
nano .env
```
(خطا در نصب `cryptg` مهم نیست؛ فقط دانلود کندتر می‌شود.)

## ۴. پر کردن `.env`
| مقدار | از کجا |
|---|---|
| `API_ID` و `API_HASH` | [my.telegram.org](https://my.telegram.org) → API development tools |
| `BOT_TOKEN` | [@BotFather](https://t.me/BotFather) — **توکن جدید** بعد از `/revoke` |
| `CHANNEL` | آدرس کانال، مثلاً `@mychannel` یا `-1001234567890` |
| `ADMIN_IDS` | شناسه‌ی عددی خودتان از [@userinfobot](https://t.me/userinfobot) |
| `PROXY` | فقط اگر تلگرام فیلتر است — بخش بعد |

### اگر تلگرام فیلتر است (`PROXY`)
VPN را روشن کنید.
- اگر VPN در حالت **TUN / کل سیستم** است، `PROXY` را خالی بگذارید.
- در غیر این صورت پورت SOCKS برنامه‌ی VPN را بنویسید. این پورت در تنظیمات برنامه پیدا می‌شود:

| برنامه | مقدار معمول |
|---|---|
| v2rayN | `PROXY=socks5://127.0.0.1:10808` |
| Nekoray / NekoBox | `PROXY=socks5://127.0.0.1:2080` |
| Hiddify | `PROXY=socks5://127.0.0.1:12334` |

## ۵. اجرا
```bash
python -m csvbot.bot
```
وقتی `Bot started` را دیدید ربات آماده است. این پنجره را باز نگه دارید؛ برای توقف `Ctrl+C`.

## ۶. تست
1. به ربات `/start` بفرستید.
2. فایل نمونه‌ی `samples/people.csv` را به ربات بفرستید. باید بگوید «با 5 ردیف ثبت شد».
3. بنویسید `علی` یا `0935` یا `"مریم کاظمی"` و نتیجه را ببینید.
4. یک فایل کوچک از کانال خودتان را فوروارد کنید و جستجو کنید.
5. اگر همه چیز درست بود، فایل بزرگ را امتحان کنید. ربات درصد دانلود را نشان می‌دهد.
6. برای حذف فایل نمونه: `/files` را بزنید و بعد `/delete 1`.

برای ثبت همه‌ی فایل‌های کانال، در یک ترمینال **دیگر** (بعد از فعال کردن `.venv`) اجرا کنید:
```bash
python -m csvbot.sync
```
> در ویندوز، `sync` و ربات را هم‌زمان برای ثبت فایل استفاده نکنید: یا ربات را ببندید یا تا تمام شدن `sync` فایلی در کانال نگذارید.

## مشکلات رایج
| پیام | راه‌حل |
|---|---|
| `KeyError: 'API_ID'` | فایل `.env` پر نشده یا اسمش `.env.txt` شده (در ویندوز پسوند فایل‌ها را نمایش دهید) |
| `Connection to Telegram failed` | VPN خاموش است یا `PROXY` اشتباه است |
| `Could not connect to proxy` | شماره پورت `PROXY` با برنامه‌ی VPN یکی نیست |
| `SQLite >= 3.43 is required` | پایتون قدیمی است؛ 3.13 نصب کنید |
| `'python' is not recognized` | هنگام نصب پایتون تیک Add to PATH زده نشده؛ دوباره نصب کنید یا به‌جای `python` بنویسید `py` |
| ربات به فایل جواب «فقط ادمین» می‌دهد | شناسه‌ی شما در `ADMIN_IDS` نیست |
