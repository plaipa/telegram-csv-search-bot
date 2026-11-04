# راه‌اندازی روی Oracle Cloud Free Tier

## ۱. ساخت حساب
1. به [oracle.com/cloud/free](https://www.oracle.com/cloud/free/) بروید و ثبت‌نام کنید. کارت بین‌المللی فقط برای تأیید هویت لازم است و پولی کم نمی‌شود.
2. **Home Region** را با دقت انتخاب کنید، چون بعداً قابل تغییر نیست و سرور رایگان فقط در همین منطقه ساخته می‌شود. منطقه‌ای نزدیک به اروپا (مثلاً Frankfurt یا Amsterdam) مناسب است.

### (پیشنهادی) ارتقا به Pay As You Go
اوراکل سرورهای رایگانی را که ۷ روز «بی‌کار» باشند (مصرف CPU، شبکه و رم زیر ۲۰٪) **پس می‌گیرد**، و این ربات بیشتر وقت بی‌کار است.
با ارتقای حساب به Pay As You Go (منوی Billing → Upgrade) این قانون اعمال نمی‌شود. تا وقتی فقط منابع Always Free استفاده کنید هزینه‌ای ندارد. پیدا کردن ظرفیت برای ساخت سرور هم راحت‌تر می‌شود.
برای اطمینان در Billing → Budgets یک بودجه‌ی ۱ دلاری با هشدار ایمیلی بسازید.

## ۲. ساخت سرور
در منوی **Compute → Instances → Create instance**:

| تنظیم | مقدار |
|---|---|
| Image | **Canonical Ubuntu 24.04** |
| Shape | **Ampere → VM.Standard.A1.Flex** با 4 OCPU و 24 GB رم (یا 2 و 12) |
| Networking | پیش‌فرض، با **Assign a public IPv4 address** روشن |
| SSH keys | **Generate a key pair** و دانلود کلید خصوصی (Save private key) |
| Boot volume | **Specify a custom boot volume size** را بزنید و **200** GB بگذارید |

اگر خطای **Out of capacity** گرفتید، یک Availability Domain دیگر را امتحان کنید یا چند ساعت بعد دوباره تلاش کنید.

بعد از ساخت، **Public IP** سرور را از صفحه‌ی Instance کپی کنید.

## ۳. اتصال به سرور
در ترمینال (در ویندوز: PowerShell):
```bash
ssh -i path/to/ssh-key.key ubuntu@<PUBLIC_IP>
```
در لینوکس/مک اگر خطای دسترسی کلید گرفتید، اول `chmod 400 path/to/ssh-key.key` را بزنید.

بررسی کنید فضای دیسک حدود 200G باشد:
```bash
df -h /
```
اگر کمتر بود: `sudo growpart /dev/sda 1 && sudo resize2fs /dev/sda1`

## ۴. نصب ربات
```bash
git clone https://github.com/plaipa/telegram-csv-search-bot.git
cd DB
bash deploy/setup.sh
```
> اگر مخزن خصوصی است، git نام کاربری و رمز می‌خواهد. به‌جای رمز یک
> [توکن گیت‌هاب](https://github.com/settings/personal-access-tokens/new) با دسترسی فقط-خواندنی به همین مخزن بسازید و وارد کنید.

اسکریپت فایل `.env` را می‌سازد. آن را پر کنید:
```bash
nano .env
```
(ذخیره با `Ctrl+O` و Enter، خروج با `Ctrl+X`)

تنظیمات را بررسی کنید:
```bash
.venv/bin/python -m csvbot.check
```

بعد دوباره اجرا کنید تا ربات به‌عنوان سرویس روشن شود:
```bash
bash deploy/setup.sh
```
ربات حالا همیشه روشن است و بعد از ری‌استارت سرور یا خطا خودش دوباره بالا می‌آید.
- لاگ‌ها: `journalctl -u csvbot -f`
- وضعیت: `sudo systemctl status csvbot`
- توقف / شروع: `sudo systemctl stop csvbot` / `sudo systemctl start csvbot`

به ربات `/start` بفرستید تا مطمئن شوید جواب می‌دهد.

## ۵. انتقال فایل‌ها به سرور
از **کامپیوتر خودتان** (نه داخل SSH) فایل‌ها را به پوشه‌ی `data` روی سرور کپی کنید:
```bash
scp -i path/to/ssh-key.key file1.csv file2.db ubuntu@<PUBLIC_IP>:~/DB/data/
```
برای یک پوشه‌ی کامل: `scp -i path/to/ssh-key.key -r my-folder ubuntu@<PUBLIC_IP>:~/DB/data/`

ربات هر ۶۰ ثانیه پوشه را بررسی می‌کند. وقتی کپی تمام شد فایل‌ها را ثبت می‌کند و به شما پیام می‌دهد. برای بررسی فوری `/reload` را بفرستید.

## ۶. به‌روزرسانی
```bash
cd ~/DB && git pull && bash deploy/setup.sh
```

## نکته‌های امنیتی
- فایل `.env` (توکن ربات) و پوشه‌ی `data` را با کسی به اشتراک نگذارید.
- اگر داده‌ها اطلاعات شخصی دارند، کاربران مجاز را با `/adduser` (یا `ALLOWED_USER_IDS` در `.env`) اضافه کنید؛ ربات پیش‌فرض بسته است و جستجوها در `/audit` ثبت می‌شوند.
- ربات به هیچ پورت ورودی نیاز ندارد. در تنظیمات شبکه‌ی اوراکل فقط SSH (پورت 22) باز باشد که پیش‌فرض همین است.
