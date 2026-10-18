"""Bot messages in the languages the admin can choose (see /language).

The language is one setting for the whole bot, stored in the index database.
Until an admin picks one, English is used.
"""
LANGS = {"en": "English", "fa": "فارسی", "hi": "हिन्दी", "ru": "Русский", "zh": "中文"}
DEFAULT = "en"
_current = DEFAULT


def set_language(code: str):
    global _current
    _current = code if code in LANGS else DEFAULT


def current() -> str:
    return _current


def t(key: str, **kw) -> str:
    texts = MESSAGES[key]
    return (texts.get(_current) or texts[DEFAULT]).format(**kw)


# Each entry: key -> {language code: text}. {placeholders} are filled by t().
MESSAGES: dict[str, dict[str, str]] = {
    "lang_prompt": {"en": "🌐 Choose the language of the bot / زبان ربات را انتخاب کنید / भाषा चुनें / Выберите язык / 选择语言"},
    "lang_saved": {
        "en": "✅ The bot language is now English.",
        "fa": "✅ زبان ربات «فارسی» شد.",
        "hi": "✅ बॉट की भाषा अब हिन्दी है।",
        "ru": "✅ Язык бота: русский.",
        "zh": "✅ 机器人语言已设为中文。"},
    "admins_only": {
        "en": "⛔️ Admins only.", "fa": "⛔️ فقط ادمین.", "hi": "⛔️ केवल एडमिन के लिए।",
        "ru": "⛔️ Только для администраторов.", "zh": "⛔️ 仅限管理员。"},
    "rate_hour": {
        "en": "⏳ The limit of {limit} searches per hour is reached. Try again later.",
        "fa": "⏳ سقف {limit} جستجو در هر ساعت پر شده است. بعداً دوباره تلاش کنید.",
        "hi": "⏳ प्रति घंटा {limit} खोजों की सीमा पूरी हो गई। बाद में फिर कोशिश करें।",
        "ru": "⏳ Достигнут лимит {limit} поисков в час. Попробуйте позже.",
        "zh": "⏳ 每小时 {limit} 次搜索的上限已用完，请稍后再试。"},
    "rate_day": {
        "en": "⏳ The limit of {limit} searches per day is reached. Try again later.",
        "fa": "⏳ سقف {limit} جستجو در هر روز پر شده است. بعداً دوباره تلاش کنید.",
        "hi": "⏳ प्रति दिन {limit} खोजों की सीमा पूरी हो गई। बाद में फिर कोशिश करें।",
        "ru": "⏳ Достигнут лимит {limit} поисков в сутки. Попробуйте позже.",
        "zh": "⏳ 每天 {limit} 次搜索的上限已用完，请稍后再试。"},
    "admin_link": {"en": "admin", "fa": "ادمین", "hi": "एडमिन", "ru": "администратор", "zh": "管理员"},
    "no_access": {
        "en": "⛔️ You don't have access to this bot.",
        "fa": "⛔️ شما به این ربات دسترسی ندارید.",
        "hi": "⛔️ आपको इस बॉट की पहुँच नहीं है।",
        "ru": "⛔️ У вас нет доступа к этому боту.",
        "zh": "⛔️ 你没有使用此机器人的权限。"},
    "no_access_contact": {
        "en": "\nTalk to the admin: {contacts}\nOr tap the button below to send them a request.",
        "fa": "\nبا ادمین صحبت کنید: {contacts}\nیا دکمه‌ی زیر را بزنید تا درخواست شما برای ادمین فرستاده شود.",
        "hi": "\nएडमिन से बात करें: {contacts}\nया नीचे का बटन दबाकर अनुरोध भेजें।",
        "ru": "\nНапишите администратору: {contacts}\nИли нажмите кнопку ниже, чтобы отправить запрос.",
        "zh": "\n请联系管理员：{contacts}\n或点击下方按钮向管理员发送申请。"},
    "btn_request": {
        "en": "📩 Request access", "fa": "📩 درخواست دسترسی", "hi": "📩 पहुँच का अनुरोध",
        "ru": "📩 Запросить доступ", "zh": "📩 申请权限"},
    "already_access": {
        "en": "You already have access. Send a word to search.",
        "fa": "شما دسترسی دارید. یک کلمه بفرستید تا جستجو کنم.",
        "hi": "आपके पास पहुँच है। खोजने के लिए कोई शब्द भेजें।",
        "ru": "У вас уже есть доступ. Отправьте слово для поиска.",
        "zh": "你已有权限，发送一个词即可搜索。"},
    "request_already": {
        "en": "Your request was already sent; wait for the admin to approve it.",
        "fa": "درخواست شما قبلاً فرستاده شده؛ منتظر تأیید ادمین بمانید.",
        "hi": "आपका अनुरोध पहले ही भेजा जा चुका है; एडमिन की मंज़ूरी का इंतज़ार करें।",
        "ru": "Ваш запрос уже отправлен; дождитесь решения администратора.",
        "zh": "你的申请已发送，请等待管理员批准。"},
    "request_sent": {
        "en": "✅ Your request was sent to the admin.",
        "fa": "✅ درخواست برای ادمین فرستاده شد.",
        "hi": "✅ आपका अनुरोध एडमिन को भेज दिया गया।",
        "ru": "✅ Запрос отправлен администратору.",
        "zh": "✅ 申请已发送给管理员。"},
    "request_text": {
        "en": "📩 Access request\n👤 {name}\nUsername: {handle}\nID: <code>{id}</code>",
        "fa": "📩 درخواست دسترسی\n👤 {name}\nیوزرنیم: {handle}\nشناسه: <code>{id}</code>",
        "hi": "📩 पहुँच का अनुरोध\n👤 {name}\nयूज़रनेम: {handle}\nआईडी: <code>{id}</code>",
        "ru": "📩 Запрос доступа\n👤 {name}\nИмя пользователя: {handle}\nID: <code>{id}</code>",
        "zh": "📩 权限申请\n👤 {name}\n用户名：{handle}\nID：<code>{id}</code>"},
    "btn_approve": {"en": "✅ Approve", "fa": "✅ تأیید", "hi": "✅ मंज़ूर", "ru": "✅ Одобрить", "zh": "✅ 同意"},
    "btn_reject": {"en": "❌ Reject", "fa": "❌ رد", "hi": "❌ अस्वीकार", "ru": "❌ Отклонить", "zh": "❌ 拒绝"},
    "verdict_ok": {"en": "✅ Approved", "fa": "✅ تأیید شد", "hi": "✅ मंज़ूर", "ru": "✅ Одобрено", "zh": "✅ 已同意"},
    "verdict_no": {"en": "❌ Rejected", "fa": "❌ رد شد", "hi": "❌ अस्वीकृत", "ru": "❌ Отклонено", "zh": "❌ 已拒绝"},
    "note_ok": {
        "en": "✅ Your access was approved. Send any word to search.",
        "fa": "✅ دسترسی شما تأیید شد. هر کلمه‌ای بفرستید تا جستجو کنم.",
        "hi": "✅ आपकी पहुँच मंज़ूर हो गई। खोजने के लिए कोई भी शब्द भेजें।",
        "ru": "✅ Ваш доступ одобрен. Отправьте любое слово для поиска.",
        "zh": "✅ 你的权限已批准，发送任意词即可搜索。"},
    "note_no": {
        "en": "❌ Your access request was rejected.",
        "fa": "❌ درخواست دسترسی شما رد شد.",
        "hi": "❌ आपका पहुँच अनुरोध अस्वीकार कर दिया गया।",
        "ru": "❌ Ваш запрос на доступ отклонён.",
        "zh": "❌ 你的权限申请被拒绝。"},
    "indexed": {
        "en": "✅ “{name}” indexed with {count:,} rows.",
        "fa": "✅ «{name}» با {count:,} ردیف ثبت شد.",
        "hi": "✅ «{name}» {count:,} पंक्तियों के साथ इंडेक्स हो गई।",
        "ru": "✅ «{name}» проиндексирован: {count:,} строк.",
        "zh": "✅ 「{name}」已建立索引，共 {count:,} 行。"},
    "no_results": {
        "en": "🔍 No results for “{q}”.",
        "fa": "🔍 نتیجه‌ای برای «{q}» پیدا نشد.",
        "hi": "🔍 «{q}» के लिए कोई नतीजा नहीं मिला।",
        "ru": "🔍 По запросу «{q}» ничего не найдено.",
        "zh": "🔍 没有找到「{q}」的结果。"},
    "results_header": {
        "en": "🔍 <b>{shown}</b> results for “{q}” (showing {a}–{b})",
        "fa": "🔍 <b>{shown}</b> نتیجه برای «{q}» (نمایش {a} تا {b})",
        "hi": "🔍 «{q}» के लिए <b>{shown}</b> नतीजे ({a}–{b} दिख रहे हैं)",
        "ru": "🔍 Результатов по «{q}»: <b>{shown}</b> (показаны {a}–{b})",
        "zh": "🔍 「{q}」共 <b>{shown}</b> 条结果（显示 {a}–{b}）"},
    "result_line": {
        "en": "<b>{i}.</b> 📄 <code>{name}</code> — row {row:,}",
        "fa": "<b>{i}.</b> 📄 <code>{name}</code> — ردیف {row:,}",
        "hi": "<b>{i}.</b> 📄 <code>{name}</code> — पंक्ति {row:,}",
        "ru": "<b>{i}.</b> 📄 <code>{name}</code> — строка {row:,}",
        "zh": "<b>{i}.</b> 📄 <code>{name}</code> — 第 {row:,} 行"},
    "cap_note": {
        "en": "⚠️ Only the first {cap} results are shown; add more words for a more precise search.",
        "fa": "⚠️ فقط {cap} نتیجه‌ی اول نمایش داده می‌شود؛ برای نتیجه‌ی دقیق‌تر، کلمات بیشتری بنویسید.",
        "hi": "⚠️ केवल पहले {cap} नतीजे दिखाए जाते हैं; सटीक खोज के लिए और शब्द लिखें।",
        "ru": "⚠️ Показаны только первые {cap} результатов; добавьте слов для более точного поиска.",
        "zh": "⚠️ 只显示前 {cap} 条结果；请多输入几个词以缩小范围。"},
    "btn_prev": {"en": "« Previous", "fa": "« قبلی", "hi": "« पिछला", "ru": "« Назад", "zh": "« 上一页"},
    "btn_next": {"en": "Next »", "fa": "بعدی »", "hi": "अगला »", "ru": "Далее »", "zh": "下一页 »"},
    "enter_query": {
        "en": "Type what to search for. Example: John Smith",
        "fa": "عبارت مورد نظر را بنویسید. مثال: علی رضایی",
        "hi": "खोजने के लिए कुछ लिखें। उदाहरण: राहुल शर्मा",
        "ru": "Введите, что искать. Пример: Иван Петров",
        "zh": "请输入要搜索的内容，例如：王小明"},
    "search_expired": {
        "en": "This search expired; search again.",
        "fa": "جستجو منقضی شده، دوباره جستجو کنید.",
        "hi": "यह खोज समाप्त हो गई; दोबारा खोजें।",
        "ru": "Поиск устарел; повторите запрос.",
        "zh": "该搜索已过期，请重新搜索。"},
    "btn_del_index": {
        "en": "✅ Delete from the index (source file stays)",
        "fa": "✅ حذف از ایندکس (فایل اصلی می‌ماند)",
        "hi": "✅ इंडेक्स से हटाएँ (मूल फ़ाइल रहेगी)",
        "ru": "✅ Удалить из индекса (исходный файл останется)",
        "zh": "✅ 从索引中删除（保留原文件）"},
    "btn_del_source": {
        "en": "⚠️ Delete from the index and the source file (irreversible)",
        "fa": "⚠️ حذف از ایندکس و از فایل اصلی (برگشت‌ناپذیر)",
        "hi": "⚠️ इंडेक्स और मूल फ़ाइल दोनों से हटाएँ (वापस नहीं होगा)",
        "ru": "⚠️ Удалить из индекса и из исходного файла (необратимо)",
        "zh": "⚠️ 从索引和原文件中删除（不可恢复）"},
    "btn_cancel": {"en": "❌ Cancel", "fa": "❌ انصراف", "hi": "❌ रद्द करें", "ru": "❌ Отмена", "zh": "❌ 取消"},
    "deleting_source": {
        "en": "⏳ Deleting from the source file...",
        "fa": "⏳ در حال حذف از فایل اصلی...",
        "hi": "⏳ मूल फ़ाइल से हटाया जा रहा है...",
        "ru": "⏳ Удаление из исходного файла...",
        "zh": "⏳ 正在从原文件中删除..."},
    "delete_failed": {
        "en": "❌ Deleting from the source file failed (see the log).",
        "fa": "❌ حذف از فایل اصلی انجام نشد (جزئیات در لاگ).",
        "hi": "❌ मूल फ़ाइल से हटाना विफल रहा (लॉग देखें)।",
        "ru": "❌ Не удалось удалить из исходного файла (см. журнал).",
        "zh": "❌ 从原文件删除失败（详见日志）。"},
    "deleted": {"en": "🗑 Deleted.", "fa": "🗑 حذف شد.", "hi": "🗑 हटा दिया गया।", "ru": "🗑 Удалено.", "zh": "🗑 已删除。"},
    "already_deleted": {
        "en": "This row was already deleted.", "fa": "این ردیف قبلاً حذف شده بود.",
        "hi": "यह पंक्ति पहले ही हटाई जा चुकी थी।", "ru": "Эта строка уже была удалена.",
        "zh": "这一行已被删除。"},
    "start": {
        "en": "Hi! 👋\nSend any word or phrase and I'll search the files.\n\n"
              "• several words: rows that contain all of them\n"
              "• a phrase in \"quotes\": exact match\n\n"
              "ℹ️ Searches are logged and limited.",
        "fa": "سلام! 👋\nهر کلمه یا عبارتی را بفرستید تا در فایل‌ها جستجو کنم.\n\n"
              "• چند کلمه: ردیف‌هایی که همه کلمات را دارند\n"
              "• عبارت داخل \"گیومه\": جستجوی دقیق همان عبارت\n\n"
              "ℹ️ جستجوها ثبت می‌شوند و تعدادشان محدود است.",
        "hi": "नमस्ते! 👋\nकोई भी शब्द या वाक्यांश भेजें, मैं फ़ाइलों में खोजूँगा।\n\n"
              "• कई शब्द: वे पंक्तियाँ जिनमें सभी शब्द हों\n"
              "• \"उद्धरण चिह्न\" में वाक्यांश: ठीक वही वाक्यांश\n\n"
              "ℹ️ खोजें दर्ज की जाती हैं और उनकी संख्या सीमित है।",
        "ru": "Привет! 👋\nОтправьте слово или фразу, и я поищу в файлах.\n\n"
              "• несколько слов: строки, где есть все слова\n"
              "• фраза в \"кавычках\": точное совпадение\n\n"
              "ℹ️ Поиски записываются в журнал и ограничены по числу.",
        "zh": "你好！👋\n发送任意词或短语，我会在文件中搜索。\n\n"
              "• 多个词：必须同时包含所有词的行\n"
              "• 用 \"引号\" 括起的短语：精确匹配\n\n"
              "ℹ️ 搜索会被记录，且次数有限。"},
    "start_admin": {
        "en": "\n\nAdmin: put CSV and DB files in the data folder and they are indexed automatically, "
              "or send files under 20 MB right here.\n/reload — scan the folder now\n/files — list files\n"
              "/users — allowed users with remove buttons (access requests arrive here too)\n"
              "/audit — recent searches (or /audit ID for one user)\n/language — change the bot language\n"
              "Under each result there is a 🗑 button to delete that row.",
        "fa": "\n\nادمین: فایل‌های CSV و DB را در پوشه‌ی data بگذارید تا خودکار ثبت شوند، "
              "یا فایل‌های زیر ۲۰ مگابایت را همین‌جا بفرستید.\n/reload — بررسی فوری پوشه\n/files — فهرست فایل‌ها\n"
              "/users — فهرست کاربران با دکمه‌ی حذف (درخواست‌های دسترسی هم همین‌جا برایتان می‌آید)\n"
              "/audit — آخرین جستجوها (یا /audit ID برای یک کاربر)\n/language — تغییر زبان ربات\n"
              "زیر هر نتیجه‌ی جستجو دکمه‌ی 🗑 هست تا همان ردیف را حذف کنید.",
        "hi": "\n\nएडमिन: CSV और DB फ़ाइलें data फ़ोल्डर में रखें, वे अपने-आप इंडेक्स हो जाएँगी, "
              "या 20 MB से छोटी फ़ाइलें यहीं भेजें।\n/reload — फ़ोल्डर अभी जाँचें\n/files — फ़ाइलों की सूची\n"
              "/users — हटाने के बटन के साथ अनुमत यूज़र (पहुँच के अनुरोध भी यहीं आते हैं)\n"
              "/audit — हाल की खोजें (या किसी यूज़र के लिए /audit ID)\n/language — बॉट की भाषा बदलें\n"
              "हर नतीजे के नीचे 🗑 बटन है, उस पंक्ति को हटाने के लिए।",
        "ru": "\n\nАдминистратору: положите CSV и DB файлы в папку data, они проиндексируются сами, "
              "или отправьте файлы до 20 МБ прямо сюда.\n/reload — проверить папку сейчас\n/files — список файлов\n"
              "/users — разрешённые пользователи с кнопками удаления (запросы доступа приходят сюда же)\n"
              "/audit — последние поиски (или /audit ID для одного пользователя)\n/language — сменить язык бота\n"
              "Под каждым результатом есть кнопка 🗑 для удаления строки.",
        "zh": "\n\n管理员：把 CSV 和 DB 文件放进 data 文件夹即可自动索引，或直接在这里发送 20 MB 以下的文件。\n"
              "/reload — 立即扫描文件夹\n/files — 文件列表\n"
              "/users — 允许的用户及删除按钮（权限申请也会发到这里）\n"
              "/audit — 最近的搜索（或 /audit ID 查看某个用户）\n/language — 更改机器人语言\n"
              "每条结果下方都有 🗑 按钮，用来删除该行。"},
    "no_files": {
        "en": "No files are indexed yet.", "fa": "هنوز فایلی ثبت نشده است.",
        "hi": "अभी तक कोई फ़ाइल इंडेक्स नहीं हुई।", "ru": "Пока нет проиндексированных файлов.",
        "zh": "还没有已索引的文件。"},
    "files_header": {
        "en": "📚 Indexed files:", "fa": "📚 فایل‌های ثبت‌شده:", "hi": "📚 इंडेक्स की गई फ़ाइलें:",
        "ru": "📚 Проиндексированные файлы:", "zh": "📚 已索引的文件："},
    "file_line": {
        "en": "• {name} — {count:,} rows", "fa": "• {name} — {count:,} ردیف",
        "hi": "• {name} — {count:,} पंक्तियाँ", "ru": "• {name} — {count:,} строк", "zh": "• {name} — {count:,} 行"},
    "adduser_usage": {
        "en": "Write the user's numeric id. Example: /adduser 123456789\n(They can get it from @userinfobot.)",
        "fa": "شناسه‌ی عددی کاربر را بنویسید. مثال: /adduser 123456789\n(کاربر می‌تواند شناسه‌اش را از @userinfobot بگیرد.)",
        "hi": "यूज़र की संख्यात्मक आईडी लिखें। उदाहरण: /adduser 123456789\n(वे इसे @userinfobot से पा सकते हैं।)",
        "ru": "Укажите числовой id пользователя. Пример: /adduser 123456789\n(Узнать его можно у @userinfobot.)",
        "zh": "请输入用户的数字 id，例如：/adduser 123456789\n（用户可从 @userinfobot 获取）"},
    "user_added": {
        "en": "✅ User {uid} added.", "fa": "✅ کاربر {uid} اضافه شد.", "hi": "✅ यूज़र {uid} जोड़ा गया।",
        "ru": "✅ Пользователь {uid} добавлен.", "zh": "✅ 已添加用户 {uid}。"},
    "user_exists": {
        "en": "User {uid} is already in the list.", "fa": "کاربر {uid} از قبل در فهرست است.",
        "hi": "यूज़र {uid} पहले से सूची में है।", "ru": "Пользователь {uid} уже в списке.",
        "zh": "用户 {uid} 已在列表中。"},
    "deluser_usage": {
        "en": "Write the user's numeric id. Example: /deluser 123456789",
        "fa": "شناسه‌ی عددی کاربر را بنویسید. مثال: /deluser 123456789",
        "hi": "यूज़र की संख्यात्मक आईडी लिखें। उदाहरण: /deluser 123456789",
        "ru": "Укажите числовой id пользователя. Пример: /deluser 123456789",
        "zh": "请输入用户的数字 id，例如：/deluser 123456789"},
    "user_removed": {
        "en": "🗑 User {uid} removed.", "fa": "🗑 کاربر {uid} حذف شد.", "hi": "🗑 यूज़र {uid} हटा दिया गया।",
        "ru": "🗑 Пользователь {uid} удалён.", "zh": "🗑 已删除用户 {uid}。"},
    "user_in_env": {
        "en": "User {uid} is in the .env file (ALLOWED_USER_IDS); edit it there to remove them.",
        "fa": "کاربر {uid} در فایل .env (ALLOWED_USER_IDS) است؛ برای حذف، آنجا را ویرایش کنید.",
        "hi": "यूज़र {uid} .env फ़ाइल (ALLOWED_USER_IDS) में है; हटाने के लिए वहीं बदलें।",
        "ru": "Пользователь {uid} указан в .env (ALLOWED_USER_IDS); удалите его оттуда.",
        "zh": "用户 {uid} 在 .env 文件（ALLOWED_USER_IDS）中，请在那里修改。"},
    "user_missing": {
        "en": "User {uid} was not in the list.", "fa": "کاربر {uid} در فهرست نبود.",
        "hi": "यूज़र {uid} सूची में नहीं था।", "ru": "Пользователя {uid} нет в списке.",
        "zh": "用户 {uid} 不在列表中。"},
    "user_still_env": {
        "en": "\n⚠️ They are also in .env and still have access.",
        "fa": "\n⚠️ هنوز در .env هم هست و دسترسی دارد.",
        "hi": "\n⚠️ वे .env में भी हैं और अभी भी पहुँच रखते हैं।",
        "ru": "\n⚠️ Он также указан в .env и сохраняет доступ.",
        "zh": "\n⚠️ 该用户也在 .env 中，仍有权限。"},
    "users_title": {
        "en": "👥 Allowed users:", "fa": "👥 کاربران مجاز:", "hi": "👥 अनुमत यूज़र:",
        "ru": "👥 Разрешённые пользователи:", "zh": "👥 允许的用户："},
    "users_empty": {
        "en": "👥 No users added yet; only admins can search.",
        "fa": "👥 هنوز کاربری اضافه نشده؛ فقط ادمین‌ها می‌توانند جستجو کنند.",
        "hi": "👥 अभी कोई यूज़र नहीं जोड़ा गया; केवल एडमिन खोज सकते हैं।",
        "ru": "👥 Пользователей пока нет; искать могут только администраторы.",
        "zh": "👥 还没有添加用户；目前只有管理员可以搜索。"},
    "from_env": {"en": "(from .env)", "fa": "(از .env)", "hi": "(.env से)", "ru": "(из .env)", "zh": "（来自 .env）"},
    "users_footer": {
        "en": "\n\nTap ❌ to remove. To add someone, they send /start to the bot and tap “Request access”, "
              "or write /adduser ID.\n\nAdmins: {admins}",
        "fa": "\n\nبرای حذف، دکمه‌ی ❌ را بزنید. برای افزودن، کاربر در ربات /start را بزند و «درخواست دسترسی» را انتخاب کند، "
              "یا بنویسید /adduser شناسه\n\nادمین‌ها: {admins}",
        "hi": "\n\nहटाने के लिए ❌ दबाएँ। जोड़ने के लिए व्यक्ति बॉट को /start भेजकर «पहुँच का अनुरोध» दबाए, "
              "या /adduser ID लिखें।\n\nएडमिन: {admins}",
        "ru": "\n\nНажмите ❌, чтобы удалить. Чтобы добавить человека, пусть он отправит боту /start и нажмёт "
              "«Запросить доступ», или напишите /adduser ID.\n\nАдминистраторы: {admins}",
        "zh": "\n\n点击 ❌ 即可删除。要添加用户，请对方给机器人发送 /start 并点击“申请权限”，或输入 /adduser ID。\n\n管理员：{admins}"},
    "removed_ok": {"en": "🗑 Removed.", "fa": "🗑 حذف شد.", "hi": "🗑 हटा दिया गया।", "ru": "🗑 Удалено.", "zh": "🗑 已删除。"},
    "removed_already": {
        "en": "Already removed.", "fa": "قبلاً حذف شده بود.", "hi": "पहले ही हटाया जा चुका था।",
        "ru": "Уже удалён.", "zh": "已被删除。"},
    "audit_empty": {
        "en": "No searches logged yet.", "fa": "هنوز جستجویی ثبت نشده است.",
        "hi": "अभी तक कोई खोज दर्ज नहीं हुई।", "ru": "Поисков пока нет.", "zh": "还没有搜索记录。"},
    "audit_title": {
        "en": "📋 Recent searches:", "fa": "📋 آخرین جستجوها:", "hi": "📋 हाल की खोजें:",
        "ru": "📋 Последние поиски:", "zh": "📋 最近的搜索："},
    "reload_checking": {
        "en": "⏳ Scanning the folder...", "fa": "⏳ در حال بررسی پوشه...", "hi": "⏳ फ़ोल्डर जाँचा जा रहा है...",
        "ru": "⏳ Проверяю папку...", "zh": "⏳ 正在扫描文件夹..."},
    "reload_done": {
        "en": "✅ Scan finished: {added} new, {removed} removed.",
        "fa": "✅ بررسی شد: {added} مورد جدید، {removed} مورد حذف‌شده.",
        "hi": "✅ जाँच पूरी: {added} नई, {removed} हटाई गईं।",
        "ru": "✅ Проверка завершена: новых {added}, удалено {removed}.",
        "zh": "✅ 扫描完成：新增 {added} 个，删除 {removed} 个。"},
    "reload_pending": {
        "en": "\n⏳ {n} file(s) are still being copied and will be indexed shortly.",
        "fa": "\n⏳ {n} فایل در حال کپی است و کمی بعد ثبت می‌شود.",
        "hi": "\n⏳ {n} फ़ाइल अभी कॉपी हो रही है और थोड़ी देर में इंडेक्स होगी।",
        "ru": "\n⏳ Файлов в процессе копирования: {n}; они будут проиндексированы чуть позже.",
        "zh": "\n⏳ 有 {n} 个文件仍在复制，稍后会自动索引。"},
    "reload_errors": {
        "en": "\n❌ {n} file(s) could not be read (see the log).",
        "fa": "\n❌ {n} فایل قابل خواندن نبود (جزئیات در لاگ).",
        "hi": "\n❌ {n} फ़ाइल पढ़ी नहीं जा सकी (लॉग देखें)।",
        "ru": "\n❌ Не удалось прочитать файлов: {n} (см. журнал).",
        "zh": "\n❌ 有 {n} 个文件无法读取（详见日志）。"},
    "upload_admin_only": {
        "en": "⛔️ Only an admin can add files.", "fa": "⛔️ فقط ادمین می‌تواند فایل اضافه کند.",
        "hi": "⛔️ केवल एडमिन फ़ाइल जोड़ सकता है।", "ru": "⛔️ Добавлять файлы может только администратор.",
        "zh": "⛔️ 只有管理员可以添加文件。"},
    "upload_type": {
        "en": "Only CSV and DB files are supported.", "fa": "فقط فایل‌های CSV و DB پشتیبانی می‌شوند.",
        "hi": "केवल CSV और DB फ़ाइलें समर्थित हैं।", "ru": "Поддерживаются только файлы CSV и DB.",
        "zh": "只支持 CSV 和 DB 文件。"},
    "upload_big": {
        "en": "⚠️ The file is larger than 20 MB; copy it straight into the data folder.",
        "fa": "⚠️ فایل بزرگ‌تر از ۲۰ مگابایت است؛ آن را مستقیم در پوشه‌ی data کپی کنید.",
        "hi": "⚠️ फ़ाइल 20 MB से बड़ी है; इसे सीधे data फ़ोल्डर में कॉपी करें।",
        "ru": "⚠️ Файл больше 20 МБ; скопируйте его прямо в папку data.",
        "zh": "⚠️ 文件超过 20 MB，请直接复制到 data 文件夹。"},
    "receiving": {
        "en": "⏳ Downloading...", "fa": "⏳ در حال دریافت...", "hi": "⏳ डाउनलोड हो रहा है...",
        "ru": "⏳ Скачиваю...", "zh": "⏳ 正在下载..."},
    "indexing": {
        "en": "⏳ Indexing...", "fa": "⏳ در حال ثبت...", "hi": "⏳ इंडेक्स हो रहा है...",
        "ru": "⏳ Индексирую...", "zh": "⏳ 正在建立索引..."},
    "saved": {
        "en": "✅ Saved and indexed ({n}).", "fa": "✅ ذخیره و ثبت شد ({n} مورد).",
        "hi": "✅ सहेजा और इंडेक्स किया गया ({n}).", "ru": "✅ Сохранено и проиндексировано ({n}).",
        "zh": "✅ 已保存并建立索引（{n} 个）。"},
    "unreadable": {
        "en": "❌ The file was saved but could not be read.", "fa": "❌ فایل ذخیره شد ولی قابل خواندن نبود.",
        "hi": "❌ फ़ाइल सहेजी गई लेकिन पढ़ी नहीं जा सकी।", "ru": "❌ Файл сохранён, но прочитать его не удалось.",
        "zh": "❌ 文件已保存，但无法读取。"},
}
