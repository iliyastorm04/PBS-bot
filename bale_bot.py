from bale import Bot, Message
import jdatetime
import locale
import random
import aiohttp
import json
import os
import time
import re
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import arabic_reshaper
from bidi.algorithm import get_display
from collections import defaultdict

BOT_TOKEN = "545865286:AXfEStZsKuKvMUR_b7LYhjnR0G5y-oLhCJE"
client = Bot(token=BOT_TOKEN)

awaiting_sticker = set()
game_states = {}
game_cooldowns = {}
from collections import defaultdict
user_messages = defaultdict(list)


try:
    locale.setlocale(locale.LC_ALL, 'fa_IR')
except locale.Error:
    pass

STATS_FILE = "stats.json"
NICKNAME_FILE = "nicknames.json"
ANTILINK_FILE = "antilink.json"
ANTISPAM_FILE = "antispam.json"
user_messages = defaultdict(list)
game_states = {}
game_cooldowns = {}

def load_json(filename):
    if os.path.exists(filename):
        try:
            with open(filename, "r", encoding="utf-8") as f:
                return json.load(f)
        except: return {}
    return {}

def save_json(filename, data):
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def format_persian(text):
    try: return arabic_reshaper.reshape(str(text))
    except: return str(text)
async def api_call(method, payload):
    url = f"https://tapi.bale.ai/bot{BOT_TOKEN}/{method}"
    async with aiohttp.ClientSession() as session:
        async with session.post(url, json=payload) as resp:
            return await resp.json()

async def is_admin(chat_id, user_id):
    try:
        res = await api_call("getChatMember", {"chat_id": chat_id, "user_id": user_id})
        if res and res.get("ok"):
            return res.get("result", {}).get("status", "") in ["creator", "administrator"]
        return False
    except: return False

def is_group(chat):
    try: return chat.type in ['group', 'supergroup'] or (hasattr(chat, 'title') and chat.title)
    except: return False

async def send_photo(chat_id, photo_path):
    url = f"https://tapi.bale.ai/bot{BOT_TOKEN}/sendPhoto"
    async with aiohttp.ClientSession() as session:
        with open(photo_path, 'rb') as f:
            data = aiohttp.FormData()
            data.add_field('chat_id', str(chat_id))
            data.add_field('photo', f, filename='img.png', content_type='image/png')
            async with session.post(url, data=data) as resp:
                return await resp.json()

def check_flood(chat_id, user_id, msg_id):
    now = time.time()
    key = (chat_id, user_id)
    user_messages[key].append((now, msg_id))
    user_messages[key] = [(t, m) for t, m in user_messages[key] if now - t <= 1.0]
    if len(user_messages[key]) > 3:
        msgs = [m for t, m in user_messages[key]]
        user_messages[key] = []
        return msgs
    return None


def add_points(chat_id, user_id, amount):
    data = load_json(STATS_FILE)
    chat_key = str(chat_id)
    user_key = str(user_id)
    if chat_key not in data: data[chat_key] = {}
    if user_key not in data[chat_key]: data[chat_key][user_key] = {"messages": 0, "points": 0}
    
    data[chat_key][user_key]["points"] += amount
    save_json(STATS_FILE, data)

def get_persian_time():
    try:
        now = jdatetime.datetime.now()
        weekdays = ["شنبه", "یک‌شنبه", "دوشنبه", "سه‌شنبه", "چهارشنبه", "پنج‌شنبه", "جمعه"]
        months = ["فروردین", "اردیبهشت", "خرداد", "تیر", "مرداد", "شهریور", "مهر", "آبان", "آذر", "دی", "بهمن", "اسفند"]
        return f"{weekdays[now.weekday()]} {now.day} {months[now.month-1]} {now.year} - ساعت {now.strftime('%H:%M:%S')}"
    except: return ""

def create_stats_image(chat_id):
    try:
        data = load_json(STATS_FILE)
        chat_key = str(chat_id)
        members_data = data.get(chat_key, {})
        total_messages = sum(m.get("messages", 0) for m in members_data.values())
        total_members = len(members_data)
        top_users = sorted(members_data.items(), key=lambda x: x[1].get("messages", 0), reverse=True)[:5]
        
        now = jdatetime.datetime.now()
        months = ["فروردین", "اردیبهشت", "خرداد", "تیر", "مرداد", "شهریور", "مهر", "آبان", "آذر", "دی", "بهمن", "اسفند"]
        date_str = f"تاریخ {now.day} {months[now.month-1]} {now.year}"
        
        W, H = 1200, 800
        img = Image.new('RGB', (W, H), (12, 14, 25))
        draw = ImageDraw.Draw(img)

        f_path = "/data/data/com.termux/files/home/Vazirmatn-Bold.ttf"
        try:
            f_title = ImageFont.truetype(f_path, 38)
            f_huge = ImageFont.truetype(f_path, 32)
            f_big = ImageFont.truetype(f_path, 22)
            f_med = ImageFont.truetype(f_path, 18)
            f_small = ImageFont.truetype(f_path, 14)
        except:
            f_title = f_huge = f_big = f_med = f_small = ImageFont.load_default()

        def t(text): return format_persian(str(text))
        def draw_rtl(y, text, font, color=(255,255,255), x_offset=40):
            txt = t(text)
            bbox = draw.textbbox((0,0), txt, font=font)
            w = bbox[2] - bbox[0]
            draw.text((W - x_offset - w, y), txt, font=font, fill=color)

        draw_rtl(40, "داشبورد تحلیلی گروه", f_title, (0, 255, 220))
        draw_rtl(90, f"تعداد کل پیام‌ها: {total_messages} | اعضای فعال: {total_members}", f_big, (255, 255, 255))
        draw_rtl(140, "کاربران برتر:", f_big, (255, 200, 0))
        
        y = 190
        for i, (uid, udata) in enumerate(top_users):
            name = udata.get("first_name", "کاربر")
            msgs = udata.get("messages", 0)
            draw_rtl(y, f"{i+1}. {name} - {msgs} پیام", f_med, (200, 200, 200))
            y += 45

        out_path = f"/data/data/com.termux/files/home/stats_{chat_id}.png"
        img.save(out_path)
        return out_path
    except Exception as e:
        print(f"Stats error: {e}")
        return None

def create_prices_image():
    try:
        from gheymat.currency import get_price as get_cur
        from gheymat.crypto import get_price as get_cry
        from gheymat.metal import get_price as get_met
        
        W, H = 800, 850
        img = Image.new('RGB', (W, H), (12, 15, 25))
        draw = ImageDraw.Draw(img)
        
        f_path = "/data/data/com.termux/files/home/Vazirmatn-Bold.ttf"
        try: 
            f_title = ImageFont.truetype(f_path, 36)
            f_big = ImageFont.truetype(f_path, 26)
            f_med = ImageFont.truetype(f_path, 20)
        except: 
            f_title = f_big = f_med = ImageFont.load_default()

        def draw_rtl(y, text, font, color):
            txt = format_persian(str(text))
            bbox = draw.textbbox((0,0), txt, font=font)
            w = bbox[2] - bbox[0]
            draw.text((W - 50 - w, y), txt, font=font, fill=color)

        draw_rtl(40, "بازار ارز، طلا و رمزارز", f_title, (0, 255, 220))
        draw.line([(50, 100), (W-50, 100)], fill=(30, 40, 60), width=2)
        
        y = 130
        items = []
        try: items.append(("دلار آمریکا", get_cur('usd', toman=True, beauty=True), "💵", (0,255,150)))
        except: pass
        try: items.append(("یورو", get_cur('eur', toman=True, beauty=True), "💶", (0,255,150)))
        except: pass
        try: items.append(("پوند", get_cur('gbp', toman=True, beauty=True), "💷", (0,255,150)))
        except: pass
        try: items.append(("بیت‌کوین", get_cry('btc', toman=True, beauty=True), "🪙", (255,200,0)))
        except: pass
        try: items.append(("اتریوم", get_cry('eth', toman=True, beauty=True), "💎", (150,100,255)))
        except: pass
        try: items.append(("طلای ۱۸ عیار", get_met('gold18', toman=True, beauty=True), "🥇", (255,215,0)))
        except: pass
        try: items.append(("سکه امامی", get_met('seke_emam', toman=True, beauty=True), "🪙", (255,215,0)))
        except: pass
        try: items.append(("نقره", get_met('silver', toman=True, beauty=True), "🥈", (200,200,200)))
        except: pass

        for name, price, icon, col in items:
            draw.rounded_rectangle([(50, y), (W-50, y+75)], radius=15, fill=(20, 25, 40), outline=(40,50,70), width=1)
            draw.text((70, y+15), icon, font=f_big, fill=col)
            draw_rtl(y+15, name, f_big, (220,220,240))
            draw_rtl(y+40, f"{price} تومان", f_med, (0,255,200))
            y += 90

        out_path = "/data/data/com.termux/files/home/prices.png"
        img.save(out_path)
        return out_path
    except Exception as e:
        print(f"Price error: {e}")
        return None

HELP_TEXT = """🌟 خوش اومدی به پنل راهنمای ربات PBS! 🌟

👤 **دستورات عمومی:**
پروفایل، تایم، تقویم، ربات، سلام

👮‍♂️ **دستورات مدیریتی (فقط ادمین‌ها):**
🚪 اخراج: بن / کیک / اخراج / سیک
🎉 آزاد کردن: آنبن / حذف بن
🔇 سکوت: سکوت / میوت
🔊 لغو سکوت: حذف سکوت / آن میوت
📢 تگ کردن اعضا: تگ

🔗 **ضد لینک (ادمین):**
ضد لینک روشن / خاموش

🚨 **ضد اسپم (ادمین):**
ضد اسپم روشن / خاموش

📌 **مدیریت پیام‌ها:**
ریپلای + حذف / دیلیت
ریپلای + پین / آن پین

🎮 **بازی:**
دستور بازی

📊 **آمار:**
آمار (داشبورد تصویری)

📌 نکته: دستورات مدیریتی نیاز به ریپلای دارن."""

def get_help_keyboard():
    return {"inline_keyboard": [
        [{"text": "📅 تقویم", "callback_data": "calendar"}, {"text": "📊 قیمت‌ها", "callback_data": "prices"}],
        [{"text": "🖼️ تبدیل عکس به استیکر", "callback_data": "sticker_mode"}]
    ]}

@client.event
async def on_ready():
    print(f"✨ {client.user} با موفقیت روشن شد!")


def check_cooldown(chat_id, user_id, game_name):
    key = f"{chat_id}_{user_id}_{game_name}"
    if key in game_cooldowns:
        diff = time.time() - game_cooldowns[key]
        if diff < 300: # 5 دقیقه = 300 ثانیه
            return int(300 - diff)
    return 0

def set_cooldown(chat_id, user_id, game_name):
    key = f"{chat_id}_{user_id}_{game_name}"
    game_cooldowns[key] = time.time()

@client.event
async def on_callback(callback_query):
    try:
        cb = callback_query.data
        chat_id = callback_query.message.chat.id
        user_id = callback_query.from_user.id # اصلاح شده برای بله

        if cb in ["antilink_on", "antilink_off", "antispam_on", "antispam_off"]:
            try: await api_call("answerCallbackQuery", {"callback_query_id": callback_query.id})
            except: pass

            if not await is_admin(chat_id, user_id):
                await api_call("sendMessage", {"chat_id": chat_id, "text": "⚠️ فقط ادمین‌ها!", "reply_to_message_id": callback_query.message.message_id})
                return

            is_on = "on" in cb
            is_link = "link" in cb
            fname = ANTILINK_FILE if is_link else ANTISPAM_FILE
            
            al = load_json(fname); al[str(chat_id)] = is_on; save_json(fname, al)
            
            if is_link:
                text = "🟢 **ضد لینک روشن شد!**" if is_on else "🔴 **ضد لینک خاموش شد!**"
                kb = {"inline_keyboard": [[{"text": "🛑 خاموش کردن", "callback_data": "antilink_off"}]]} if is_on else {"inline_keyboard": [[{"text": "🔗 روشن کردن", "callback_data": "antilink_on"}]]}
            else:
                text = "🟢 **ضد اسپم روشن شد!**" if is_on else "🔴 **ضد اسپم خاموش شد!**"
                kb = {"inline_keyboard": [[{"text": "🛑 خاموش کردن", "callback_data": "antispam_off"}]]} if is_on else {"inline_keyboard": [[{"text": "🔗 روشن کردن", "callback_data": "antispam_on"}]]}
            
            await api_call("sendMessage", {"chat_id": chat_id, "text": text, "reply_markup": kb})
            return

        if cb == "menu_guess":
            cd = check_cooldown(chat_id, user_id, "guess")
            if cd > 0:
                await api_call("sendMessage", {"chat_id": chat_id, "text": f"⏳ باید {cd} ثانیه صبر کنی تا دوباره حدس عدد بازی کنی!"})
                return
            import random
            game_states[chat_id] = {"target": random.randint(1, 10)}
            kb = []
            row = []
            for i in range(1, 11):
                row.append({"text": str(i), "callback_data": f"guess_{i}"})
                if i % 5 == 0:
                    kb.append(row)
                    row = []
            if row: kb.append(row)
            await api_call("sendMessage", {"chat_id": chat_id, "text": "🔢 من یه عدد بین ۱ تا ۱۰ انتخاب کردم. حدس بزن کدومه؟", "reply_markup": {"inline_keyboard": kb}})
            return
            
        elif cb.startswith("guess_"):
            set_cooldown(chat_id, user_id, "guess")
            if chat_id not in game_states: return
            target = game_states[chat_id].get("target")
            guess = int(cb.split("_")[-1])
            del game_states[chat_id]
            if guess == target:
                add_points(chat_id, user_id, 10)
                await api_call("sendMessage", {"chat_id": chat_id, "text": f"🎉 آفرین! عدد {target} بود. درست حدس زدی!\n+10 الماس 💎"})
            else:
                await api_call("sendMessage", {"chat_id": chat_id, "text": f"❌ باختی! عدد {guess} نبود، عدد من {target} بود."})
            return

        elif cb == "menu_rps":
            cd = check_cooldown(chat_id, user_id, "rps")
            if cd > 0:
                await api_call("sendMessage", {"chat_id": chat_id, "text": f"⏳ باید {cd} ثانیه صبر کنی تا دوباره سنگ کاغذ قیچی بازی کنی!"})
                return
            kb = {"inline_keyboard": [[
                {"text": "✊ سنگ", "callback_data": "rps_rock"},
                {"text": "✌️ کاغذ", "callback_data": "rps_paper"},
                {"text": "✋ قیچی", "callback_data": "rps_scissors"}
            ]]}
            await api_call("sendMessage", {"chat_id": chat_id, "text": "انتخاب کن:", "reply_markup": kb})
            return

        elif cb.startswith("rps_"):
            set_cooldown(chat_id, user_id, "rps")
            import random
            choice = cb.split("_")[-1]
            bot_choice = random.choice(["rock", "paper", "scissors"])
            names = {"rock": "✊ سنگ", "paper": "✌️ کاغذ", "scissors": "✋ قیچی"}
            if choice == bot_choice: txt = f"🤝 مساوی! هر دو {names[choice]} انتخاب کردیم."
            elif (choice == "rock" and bot_choice == "scissors") or (choice == "paper" and bot_choice == "rock") or (choice == "scissors" and bot_choice == "paper"):
                add_points(chat_id, user_id, 5)
                txt = f"🎉 بردی! تو {names[choice]} و من {names[bot_choice]}.\n+5 الماس 💎"
            else: txt = f"😢 باختی! تو {names[choice]} و من {names[bot_choice]}."
            await api_call("sendMessage", {"chat_id": chat_id, "text": txt})
            return

        if cb == "menu_coin":
            cd = check_cooldown(chat_id, user_id, "coin")
            if cd > 0:
                await api_call("answerCallbackQuery", {"callback_query_id": callback_query.id, "text": f"⏳ باید {cd} ثانیه صبر کنی!", "show_alert": True})
                return
                
            kb = {"inline_keyboard": [[
                {"text": "شیر 🦁", "callback_data": "coin_heads"},
                {"text": "خط ✍️", "callback_data": "coin_tails"}
            ]]}
            await api_call("sendMessage", {"chat_id": chat_id, "text": "🪙 شیر می‌زنی یا خط؟ یکی رو انتخاب کن:", "reply_markup": kb})
            return
            
        elif cb in ["coin_heads", "coin_tails"]:
            set_cooldown(chat_id, user_id, "coin")
            import random
            user_pick = "شیر" if cb == "coin_heads" else "خط"
            result = random.choice(["شیر", "خط"])
            
            txt = f"🪙 سکه انداختی...\n\nنتیجه: **{result}**\n\n"
            if user_pick == result:
                add_points(chat_id, user_id, 5)
                txt += "🎉 آفرین! درست حدس زدی. +5 الماس 💎"
            else:
                txt += "😢 اشتباه حدس زدی! دفعه بعد حتما می‌بری."
                
            await api_call("sendMessage", {"chat_id": chat_id, "text": txt})
            return

        if cb == "help_menu":
            await api_call("sendMessage", {"chat_id": chat_id, "text": HELP_TEXT, "reply_markup": get_help_keyboard()})
        elif cb == "help_send_group":
            await api_call("sendMessage", {"chat_id": chat_id, "text": HELP_TEXT, "reply_markup": get_help_keyboard()})
            try: await api_call("deleteMessage", {"chat_id": chat_id, "message_id": callback_query.message.message_id})
            except: pass
        elif cb == "sticker_mode":
            awaiting_sticker.add(user_id)
            await api_call("sendMessage", {"chat_id": chat_id, "text": "📸 عکس مورد نظرت رو بفرست تا استیکر بشه!"})
            return
        elif cb == "about_us":
            about_text = (
                "🌘 **𝙻𝚒𝚍𝚘𝚌𝚊𝚒𝚗𝚎 𝚜𝚝𝚞𝚍𝚒𝚘** 🩸\n\n"
                "ما یه تیم خلاق و حرفه‌ای هستیم که توی زمینه‌های مختلف دیجیتال فعالیت می‌کنیم. "
                "هدفمون اینه که با کیفیت بالا و ایده‌های نو، بهترین تجربه‌ها رو برای کاربران بسازیم.\n\n"
                "✨ **حوزه‌های فعالیت ما:**\n"
                "🎨 طراحی گرافیک و لوگو\n"
                "🤖 ساخت ربات‌های تلگرام و بله\n"
                "💻 برنامه‌نویسی و توسعه وب\n"
                "📱 طراحی اپلیکیشن\n"
                "🎬 تولید محتوای ویدیویی\n"
                "🌐 طراحی سایت و فروشگاه\n\n"
                "═══════════════════════\n\n"
                "👥 **اعضای تیم:**\n"
                "👑 **مدیریت و پشتیبانی:**\n"
                "💬 @pv_storms\n\n"
                "🛠️ **توسعه و فنی:**\n"
                "💬 @pv_ahzar\n\n"
                "═══════════════════════\n\n"
                "📌 **ارتباط با ما:**\n"
                "برای سفارش یا مشاوره، به یکی از آیدی‌های بالا پیام بدید.\n\n"
                "💚 ممنون که به ما اعتماد می‌کنید! 🌹"
            )
            await api_call("sendMessage", {"chat_id": chat_id, "text": about_text})
        elif cb == "support":
            support_text = (
                "💬 **پشتیبانی ربات PBS**\n\n"
                "اگه سوال، مشکل یا پیشنهادی داری، می‌تونی به آیدی‌های زیر پیام بدی:\n\n"
                "👤 @pv_storms\n"
                "👤 @pv_ahzar\n\n"
                "من همیشه خوشحال می‌شم کمکت کنم! 💚"
            )
            await api_call("sendMessage", {"chat_id": chat_id, "text": support_text})
        elif cb == "calendar":
            now = jdatetime.datetime.now()
            await api_call("sendMessage", {"chat_id": chat_id, "text": f"📅 امروز: {now.strftime('%Y/%m/%d')}\\n🕐 ساعت: {now.strftime('%H:%M')}"})
        elif cb == "prices":
            img = create_prices_image()
            if img: await send_photo(chat_id, img)
            
    except Exception as e: print(f"🚨 CB Error: {e}")

@client.event
async def on_message(message: Message):
    if not message.author: return
    chat_id = message.chat.id
    user_id = message.author.id
    user_name = message.author.first_name or "کاربر"
    text = message.text.strip() if message.text else ""


    if user_id in awaiting_sticker and (message.photos or message.document):
        awaiting_sticker.remove(user_id)
        await message.reply("⏳ چند لحظه صبر کن تا استیکرت آماده بشه...")
        try:
            f_id = message.photos[-1].file_id if message.photos else message.document.file_id
            res = await api_call("getFile", {"file_id": f_id})
            url = f"https://tapi.bale.ai/file/bot{BOT_TOKEN}/{res['result']['file_path']}"
            async with aiohttp.ClientSession() as s:
                async with s.get(url) as r:
                    img_data = await r.read()
            
            in_path = f"/data/data/com.termux/files/home/tmp_{user_id}.jpg"
            with open(in_path, "wb") as f:
                f.write(img_data)

            from PIL import Image, ImageOps
            img = Image.open(in_path)
            # تبدیل به سایز استاندارد استیکر (512x512)
            img = ImageOps.fit(img, (512, 512), Image.Resampling.LANCZOS)
            out_path = f"/data/data/com.termux/files/home/stk_{user_id}.webp"
            img.save(out_path, "WEBP")
            
            # ارسال به عنوان استیکر واقعی
            sticker_url = f"https://tapi.bale.ai/bot{BOT_TOKEN}/sendSticker"
            async with aiohttp.ClientSession() as session:
                with open(out_path, 'rb') as sf:
                    data = aiohttp.FormData()
                    data.add_field('chat_id', str(chat_id))
                    data.add_field('sticker', sf, filename='sticker.webp', content_type='image/webp')
                    async with session.post(sticker_url, data=data) as sres:
                        sjson = await sres.json()
                        
            if not sjson.get("ok"):
                print(f"🚨 خطای API استیکر بله: {sjson}")
                # اگر بله استیکر رو قبول نکرد، عکس رو می‌فرستیم که لااقل کاربر ناراضی نباشه
                await send_photo(chat_id, out_path)

            os.remove(in_path)
            os.remove(out_path)
        except Exception as e:
            await message.reply(f"❌ خطا در ساخت استیکر: {e}")
        return

    if not text: return

    if text in ["ربات", "ربات؟", "ربات!", "هی ربات"]:
        responses = [
            "جانم؟ 💚 چه خبر رفیق؟ چطور می‌تونم کمکت کنم؟",
            "سلام گل من! 🌹 بگو ببینم چی می‌خوای؟",
            "اومدم! 🏃‍♂️ چیکار داری برام؟ همیشه آماده‌ام!",
            "بله بله؟ 😊 من اینجام، بگو چی شده.",
            "جان دلم! 💫 بفرما، در خدمتم."
        ]
        await message.reply(random.choice(responses))
        return

    if text == "/start":
        reply_text = (
            f"سلام {user_name} جان! 🌹\n\n"
            f"چه خوب که اومدی پیشم 💚\n"
            f"من اینجام تا کمکت کنم، باهات گپ بزنم و هر کاری از دستم بربیاد برات انجام بدم.\n\n"
            f"از دکمه‌های زیر استفاده کن 👇"
        )
        kb = {"inline_keyboard": [
            [{"text": "📖 راهنما", "callback_data": "help_menu"}, {"text": "🌘 درباره ما", "callback_data": "about_us"}],
            [{"text": "💬 پشتیبانی", "callback_data": "support"}]
        ]}
        await api_call("sendMessage", {"chat_id": chat_id, "text": reply_text, "reply_markup": kb})
        return

    if text in ["راهنما", "/help"]:
        if is_group(message.chat):
            kb = {"inline_keyboard": [[{"text": "📥 در پیوی", "callback_data": "help_send_pv"}, {"text": "👥 در گروه", "callback_data": "help_send_group"}]]}
            await api_call("sendMessage", {"chat_id": chat_id, "text": "راهنما رو کجا بفرستم؟", "reply_markup": kb})
        else:
            await api_call("sendMessage", {"chat_id": chat_id, "text": HELP_TEXT, "reply_markup": get_help_keyboard()})
        return

    if text == "آمار":
        img = create_stats_image(chat_id)
        if img: await send_photo(chat_id, img)
        return

    if text in ["قیمت", "قیمت دلار"]:
        img = create_prices_image()
        if img: await send_photo(chat_id, img)
        return

    if text in ["ضد لینک روشن", "ضد لینک فعال"]:
        if not await is_admin(chat_id, user_id): return
        al = load_json(ANTILINK_FILE); al[str(chat_id)] = True; save_json(ANTILINK_FILE, al)
        await api_call("sendMessage", {"chat_id": chat_id, "text": "🟢 **ضد لینک روشن شد!**", "reply_markup": {"inline_keyboard": [[{"text": "🛑 خاموش کردن", "callback_data": "antilink_off"}]]}})
        return
        
    if text in ["ضد لینک خاموش", "ضد لینک غیرفعال"]:
        if not await is_admin(chat_id, user_id): return
        al = load_json(ANTILINK_FILE); al[str(chat_id)] = False; save_json(ANTILINK_FILE, al)
        await api_call("sendMessage", {"chat_id": chat_id, "text": "🔴 **ضد لینک خاموش شد!**", "reply_markup": {"inline_keyboard": [[{"text": "🔗 روشن کردن", "callback_data": "antilink_on"}]]}})
        return

    if text in ["ضد اسپم روشن", "ضد اسپم فعال"]:
        if not await is_admin(chat_id, user_id): return
        al = load_json(ANTISPAM_FILE); al[str(chat_id)] = True; save_json(ANTISPAM_FILE, al)
        await api_call("sendMessage", {"chat_id": chat_id, "text": "🟢 **ضد اسپم روشن شد!**", "reply_markup": {"inline_keyboard": [[{"text": "🛑 خاموش کردن", "callback_data": "antispam_off"}]]}})
        return
        
    if text in ["ضد اسپم خاموش", "ضد اسپم غیرفعال"]:
        if not await is_admin(chat_id, user_id): return
        al = load_json(ANTISPAM_FILE); al[str(chat_id)] = False; save_json(ANTISPAM_FILE, al)
        await api_call("sendMessage", {"chat_id": chat_id, "text": "🔴 **ضد اسپم خاموش شد!**", "reply_markup": {"inline_keyboard": [[{"text": "🔗 روشن کردن", "callback_data": "antispam_on"}]]}})
        return

    if is_group(message.chat) and text:
        if not await is_admin(chat_id, user_id):
            if load_json(ANTILINK_FILE).get(str(chat_id), False):
                if re.search(r'(https?://|www\\.|t\\.me/|ble\\.ir/)', text, re.IGNORECASE):
                    try: await api_call("deleteMessage", {"chat_id": chat_id, "message_id": message.message_id})
                    except: pass
                    await api_call("sendMessage", {"chat_id": chat_id, "text": f"🚫 **{user_name}** جان، ارسال لینک مجاز نیست!"})
                    return
            
            if load_json(ANTISPAM_FILE).get(str(chat_id), False):
                flood = check_flood(chat_id, user_id, message.message_id)
                if flood:
                    for m_id in flood:
                        try: await api_call("deleteMessage", {"chat_id": chat_id, "message_id": m_id})
                        except: pass
                    await api_call("sendMessage", {"chat_id": chat_id, "text": f"⚠️ **{user_name}** جان، اسپم نکن!"})
                    return

    if text == "تگ":
        if not await is_admin(chat_id, user_id): return
        members = load_json(STATS_FILE).get(str(chat_id), {})
        mentions = [f"@{m.get('username')}" for uid, m in members.items() if m.get("username")]
        if mentions: await api_call("sendMessage", {"chat_id": chat_id, "text": "📢 " + " ".join(mentions)})
        return

    admin_cmds = ["بن", "کیک", "اخراج", "سیک", "آنبن", "حذف بن", "سکوت", "میوت", "حذف سکوت", "آن میوت", "حذف", "دیلیت", "پین", "آن پین"]
    if text in admin_cmds:
        if not is_group(message.chat):
            await message.reply("⚠️ عزیزم، این دستور فقط توی گروه کار می‌کنه.")
            return
        if not is_group(message.chat):
            await message.reply("⚠️ عزیزم، این دستور فقط توی گروه کار می‌کنه.")
            return
        if not await is_admin(chat_id, user_id):
            await message.reply("⚠️ این دستور فقط برای ادمین‌های گروهه.")
            return
        if not message.reply_to_message:
            await message.reply("⚠️ روی پیام کاربر ریپلای کن و بعد دستور رو بفرست.")
            return
        target_id = message.reply_to_message.author.id
        try:
            if text in ["بن", "کیک", "اخراج", "سیک"]: await client.ban_chat_member(chat_id, target_id)
            elif text in ["آنبن", "حذف بن"]: await client.unban_chat_member(chat_id, target_id)
            elif text in ["سکوت", "میوت"]: await api_call("restrictChatMember", {"chat_id": chat_id, "user_id": target_id, "permissions": {"can_send_messages": False}})
            elif text in ["حذف سکوت", "آن میوت"]: await api_call("restrictChatMember", {"chat_id": chat_id, "user_id": target_id, "permissions": {"can_send_messages": True}})
            elif text in ["حذف", "دیلیت"]: await api_call("deleteMessage", {"chat_id": chat_id, "message_id": message.reply_to_message.message_id})
            elif text == "پین": await api_call("pinChatMessage", {"chat_id": chat_id, "message_id": message.reply_to_message.message_id})
            elif text == "آن پین": await api_call("unpinChatMessage", {"chat_id": chat_id, "message_id": message.reply_to_message.message_id})
        except: pass
        return

    if text in ["تایم", "ساعت"]:
        import jdatetime
        import random
        now = jdatetime.datetime.now()
        hour = now.hour
        
        if 5 <= hour < 12:
            greeting = "☀️ صبح بخیر! روز زیبایی داشته باشی."
        elif 12 <= hour < 17:
            greeting = "🌤️ ظهر بخیر! امیدوارم روزت عالی باشه."
        elif 17 <= hour < 20:
            greeting = "🌇 عصر بخیر! غروبت پر از آرامش."
        else:
            greeting = "🌙 شب بخیر! امشبت پر از ستاره."

        day_progress = (hour * 3600 + now.minute * 60 + now.second) / 86400
        filled = int(day_progress * 10)
        bar = "▓" * filled + "░" * (10 - filled)
        pct = int(day_progress * 100)

        weekdays = ["شنبه", "یک‌شنبه", "دوشنبه", "سه‌شنبه", "چهارشنبه", "پنج‌شنبه", "جمعه"]
        months = ["فروردین", "اردیبهشت", "خرداد", "تیر", "مرداد", "شهریور", "مهر", "آبان", "آذر", "دی", "بهمن", "اسفند"]
        date_str = f"{weekdays[now.weekday()]} {now.day} {months[now.month-1]} {now.year}"
        time_str = now.strftime("%H:%M:%S")

        quotes = [
            "«زمان مثل رودخانه است، نمی‌ایستد. تو هم جاری باش.»",
            "«هر ثانیه‌ای که می‌گذرد، فرصتی تازه برای ساختن است.»",
            "«بهترین زمان برای شروع، همین حالاست.»",
            "«قدر لحظه‌ها را بدان، که بازگشتی نیست.»",
            "«امروز، فردایی است که دیروز منتظرش بودی.»"
        ]
        
        text = (
            f"{greeting}\n\n"
            f"┏━━━━━━━━━━━━━━━━━━┓\n"
            f"     🕰️ **زمان و تاریخ**\n"
            f"┗━━━━━━━━━━━━━━━━━━┛\n\n"
            f"📅 **تاریخ:** {date_str}\n"
            f"⏰ **ساعت:** {time_str}\n\n"
            f"⏳ **پیشرفت امروز:**\n"
            f"`{bar}` **{pct}%**\n\n"
            f"✨ {random.choice(quotes)}"
        )
        await message.reply(text)
        return

    if text == "بازی":
        kb = {"inline_keyboard": [
            [{"text": "🔢 حدس عدد", "callback_data": "menu_guess"}],
            [{"text": "✊✌️✋ سنگ کاغذ قیچی", "callback_data": "menu_rps"}],
            [{"text": "🪙 شیر یا خط", "callback_data": "menu_coin"}]
        ]}
        await api_call("sendMessage", {"chat_id": chat_id, "text": "🎮 کدوم بازی رو می‌خوای؟ از دکمه‌های پایین انتخاب کن 👇", "reply_markup": kb})
        return

    if text.startswith("سلام") or text in ["ربات", "تایم", "ساعت", "پروفایل"]:
        if text.startswith("سلام"): await message.reply(f"سلام {user_name} جان! 🌹")
        elif text in ["تایم", "ساعت"]: await message.reply(f"⏰ {get_persian_time()}")
        elif text == "پروفایل":
            stats = load_json(STATS_FILE).get(str(chat_id), {}).get(str(user_id), {"messages": 0, "points": 0})
            messages = stats.get("messages", 0)
            points = stats.get("points", 0)
            level = max(1, points // 25)
            progress = points % 25
            filled = int(progress / 25 * 10)
            bar = "█" * filled + "░" * (10 - filled)
            pct = int(progress / 25 * 100)
            
            if level <= 2: title = "تازه‌کار 🌱"
            elif level <= 4: title = "مبارز 🗡️"
            elif level <= 6: title = "شوالیه 🛡️"
            elif level <= 9: title = "قهرمان ⚔️"
            else: title = "افسانه 👑"

            nickname = "ثبت نشده"
            if os.path.exists(NICKNAME_FILE):
                n_data = load_json(NICKNAME_FILE).get(str(user_id))
                if n_data: nickname = n_data.get("nickname", "ثبت نشده")

            reply_text = (
                f"⚔️ **کارت مبارز** ⚔️\n"
                f"👤 **{user_name}**\n"
                f"🏅 درجه: {title}\n"
                f"🏷️ لقب: {nickname}\n"
                f"──────────────────────\n"
                f"❤️ **پیام‌ها:** {messages}\n"
                f"🔮 **سطح:** {level}\n"
                f"💎 **الماس (امتیاز):** {points}\n"
                f"──────────────────────\n"
                f"⏳ **تجربه تا درجه بعد:**\n"
                f"[{bar}] {pct}%"
            )
            await message.reply(reply_text)
            return

if __name__ == "__main__":
    client.run()

@client.event
async def on_message(message: Message):
    if not message.author: return
    chat_id = message.chat.id
    user_id = message.author.id
    user_name = message.author.first_name or "کاربر"
    text = message.text.strip() if message.text else ""

    if not text: return

    if text in ["ربات", "ربات؟", "ربات!", "هی ربات"]:
        responses = [
            "جانم؟ 💚 چه خبر رفیق؟ چطور می‌تونم کمکت کنم؟",
            "سلام گل من! 🌹 بگو ببینم چی می‌خوای؟",
            "اومدم! 🏃‍♂️ چیکار داری برام؟ همیشه آماده‌ام!",
            "بله بله؟ 😊 من اینجام، بگو چی شده.",
            "جان دلم! 💫 بفرما، در خدمتم."
        ]
        await message.reply(random.choice(responses))
        return

    if text == "/start":
        reply_text = (
            f"سلام {user_name} جان! 🌹\n\n"
            f"چه خوب که اومدی پیشم 💚\n"
            f"من اینجام تا کمکت کنم، باهات گپ بزنم و هر کاری از دستم بربیاد برات انجام بدم.\n\n"
            f"از دکمه‌های زیر استفاده کن 👇"
        )
        kb = {"inline_keyboard": [
            [{"text": "📖 راهنما", "callback_data": "help_menu"}, {"text": "🌘 درباره ما", "callback_data": "about_us"}],
            [{"text": "💬 پشتیبانی", "callback_data": "support"}]
        ]}
        await api_call("sendMessage", {"chat_id": chat_id, "text": reply_text, "reply_markup": kb})
        return

    if text in ["راهنما", "/help"]:
        if is_group(message.chat):
            kb = {"inline_keyboard": [[{"text": "📥 در پیوی", "callback_data": "help_send_pv"}, {"text": "👥 در گروه", "callback_data": "help_send_group"}]]}
            await api_call("sendMessage", {"chat_id": chat_id, "text": "راهنما رو کجا بفرستم؟", "reply_markup": kb})
        else:
            await api_call("sendMessage", {"chat_id": chat_id, "text": HELP_TEXT, "reply_markup": get_help_keyboard()})
        return

    if text == "آمار":
        img = create_stats_image(chat_id)
        if img: await send_photo(chat_id, img)
        return

    if text in ["قیمت", "قیمت دلار"]:
        img = create_prices_image()
        if img: await send_photo(chat_id, img)
        return

    if text in ["ضد لینک روشن", "ضد لینک فعال"]:
        if not await is_admin(chat_id, user_id): return
        al = load_json(ANTILINK_FILE); al[str(chat_id)] = True; save_json(ANTILINK_FILE, al)
        await api_call("sendMessage", {"chat_id": chat_id, "text": "🟢 **ضد لینک روشن شد!**", "reply_markup": {"inline_keyboard": [[{"text": "🛑 خاموش کردن", "callback_data": "antilink_off"}]]}})
        return
        
    if text in ["ضد لینک خاموش", "ضد لینک غیرفعال"]:
        if not await is_admin(chat_id, user_id): return
        al = load_json(ANTILINK_FILE); al[str(chat_id)] = False; save_json(ANTILINK_FILE, al)
        await api_call("sendMessage", {"chat_id": chat_id, "text": "🔴 **ضد لینک خاموش شد!**", "reply_markup": {"inline_keyboard": [[{"text": "🔗 روشن کردن", "callback_data": "antilink_on"}]]}})
        return

    if text in ["ضد اسپم روشن", "ضد اسپم فعال"]:
        if not await is_admin(chat_id, user_id): return
        al = load_json(ANTISPAM_FILE); al[str(chat_id)] = True; save_json(ANTISPAM_FILE, al)
        await api_call("sendMessage", {"chat_id": chat_id, "text": "🟢 **ضد اسپم روشن شد!**", "reply_markup": {"inline_keyboard": [[{"text": "🛑 خاموش کردن", "callback_data": "antispam_off"}]]}})
        return
        
    if text in ["ضد اسپم خاموش", "ضد اسپم غیرفعال"]:
        if not await is_admin(chat_id, user_id): return
        al = load_json(ANTISPAM_FILE); al[str(chat_id)] = False; save_json(ANTISPAM_FILE, al)
        await api_call("sendMessage", {"chat_id": chat_id, "text": "🔴 **ضد اسپم خاموش شد!**", "reply_markup": {"inline_keyboard": [[{"text": "🔗 روشن کردن", "callback_data": "antispam_on"}]]}})
        return

    if is_group(message.chat) and text:
        if not await is_admin(chat_id, user_id):
            if load_json(ANTILINK_FILE).get(str(chat_id), False):
                if re.search(r'(https?://|www\\.|t\\.me/|ble\\.ir/)', text, re.IGNORECASE):
                    try: await api_call("deleteMessage", {"chat_id": chat_id, "message_id": message.message_id})
                    except: pass
                    await api_call("sendMessage", {"chat_id": chat_id, "text": f"🚫 **{user_name}** جان، ارسال لینک مجاز نیست!"})
                    return
            
            if load_json(ANTISPAM_FILE).get(str(chat_id), False):
                flood = check_flood(chat_id, user_id, message.message_id)
                if flood:
                    for m_id in flood:
                        try: await api_call("deleteMessage", {"chat_id": chat_id, "message_id": m_id})
                        except: pass
                    await api_call("sendMessage", {"chat_id": chat_id, "text": f"⚠️ **{user_name}** جان، اسپم نکن!"})
                    return

    if text == "تگ":
        if not await is_admin(chat_id, user_id): return
        members = load_json(STATS_FILE).get(str(chat_id), {})
        mentions = [f"@{m.get('username')}" for uid, m in members.items() if m.get("username")]
        if mentions: await api_call("sendMessage", {"chat_id": chat_id, "text": "📢 " + " ".join(mentions)})
        return

    admin_cmds = ["بن", "کیک", "اخراج", "سیک", "آنبن", "حذف بن", "سکوت", "میوت", "حذف سکوت", "آن میوت", "حذف", "دیلیت", "پین", "آن پین"]
    if text in admin_cmds:
        if not is_group(message.chat):
            await message.reply("⚠️ عزیزم، این دستور فقط توی گروه کار می‌کنه.")
            return
        if not is_group(message.chat):
            await message.reply("⚠️ عزیزم، این دستور فقط توی گروه کار می‌کنه.")
            return
        if not await is_admin(chat_id, user_id):
            await message.reply("⚠️ این دستور فقط برای ادمین‌های گروهه.")
            return
        if not message.reply_to_message:
            await message.reply("⚠️ روی پیام کاربر ریپلای کن و بعد دستور رو بفرست.")
            return
        target_id = message.reply_to_message.author.id
        try:
            if text in ["بن", "کیک", "اخراج", "سیک"]: await client.ban_chat_member(chat_id, target_id)
            elif text in ["آنبن", "حذف بن"]: await client.unban_chat_member(chat_id, target_id)
            elif text in ["سکوت", "میوت"]: await api_call("restrictChatMember", {"chat_id": chat_id, "user_id": target_id, "permissions": {"can_send_messages": False}})
            elif text in ["حذف سکوت", "آن میوت"]: await api_call("restrictChatMember", {"chat_id": chat_id, "user_id": target_id, "permissions": {"can_send_messages": True}})
            elif text in ["حذف", "دیلیت"]: await api_call("deleteMessage", {"chat_id": chat_id, "message_id": message.reply_to_message.message_id})
            elif text == "پین": await api_call("pinChatMessage", {"chat_id": chat_id, "message_id": message.reply_to_message.message_id})
            elif text == "آن پین": await api_call("unpinChatMessage", {"chat_id": chat_id, "message_id": message.reply_to_message.message_id})
        except: pass
        return

    if text.startswith("سلام") or text in ["ربات", "تایم", "ساعت", "پروفایل"]:
        if text.startswith("سلام"): await message.reply(f"سلام {user_name} جان! 🌹")
        elif text in ["تایم", "ساعت"]: await message.reply(f"⏰ {get_persian_time()}")
        elif text == "پروفایل":
            stats = load_json(STATS_FILE).get(str(chat_id), {}).get(str(user_id), {"messages": 0})
            await message.reply(f"👤 {user_name}\\n💬 پیام‌ها: {stats['messages']}")
        return

if __name__ == "__main__":
    client.run()
