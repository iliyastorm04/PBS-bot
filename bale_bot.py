from bale import Bot, Message
import jdatetime
import locale
import random
import aiohttp
import json
import os
import asyncio
import time

BOT_TOKEN = "545865286:AXfEStZsKuKvMUR_b7LYhjnR0G5y-oLhCJE"
client = Bot(token=BOT_TOKEN)

try:
    locale.setlocale(locale.LC_ALL, 'fa_IR')
except locale.Error:
    pass


NICKNAME_FILE = "nicknames.json"
STATS_FILE = "stats.json"
CHATS_FILE = "chats.json"
WARNINGS_FILE = "warnings.json"
ANTISPAM_FILE = "antispam.json"

last_activity = {}
last_nudge = {}
known_chats = {}

# تنظیمات ضد اسپم و اخطار
antispam_settings = {}
user_warnings = {}
recent_msgs = {}

SILENT_THRESHOLD = 30 * 60
NUDGE_COOLDOWN = 60 * 60
CHECK_INTERVAL = 60

FLOOD_THRESHOLD = 3
FLOOD_WINDOW = 1.0


def load_json(filename):
    if os.path.exists(filename):
        try:
            with open(filename, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            return {}
    return {}


def save_json(filename, data):
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def load_all_data():
    global antispam_settings, user_warnings
    antispam_settings = load_json(ANTISPAM_FILE)
    user_warnings = load_json(WARNINGS_FILE)


def get_persian_time():
    try:
        now = jdatetime.datetime.now()
        weekdays = ["شنبه", "یک‌شنبه", "دوشنبه", "سه‌شنبه", "چهارشنبه", "پنج‌شنبه", "جمعه"]
        months = ["فروردین", "اردیبهشت", "خرداد", "تیر", "مرداد", "شهریور", "مهر", "آبان", "آذر", "دی", "بهمن", "اسفند"]
        weekday_name = weekdays[now.weekday()]
        month_name = months[now.month - 1]
        return f"{weekday_name} {now.day} {month_name} {now.year} - ساعت {now.strftime('%H:%M:%S')}"
    except Exception as e:
        print(f"Time error: {e}")
        import datetime
        now = datetime.datetime.now()
        return now.strftime("%Y/%m/%d - %H:%M:%S")


async def set_nickname(user_id, nickname, set_by):
    data = load_json(NICKNAME_FILE)
    data[str(user_id)] = {"nickname": nickname, "set_by": str(set_by)}
    save_json(NICKNAME_FILE, data)


def get_nickname(user_id):
    data = load_json(NICKNAME_FILE)
    user_data = data.get(str(user_id))
    if user_data:
        return user_data.get("nickname")
    return None


async def remove_nickname(user_id):
    data = load_json(NICKNAME_FILE)
    if str(user_id) in data:
        del data[str(user_id)]
        save_json(NICKNAME_FILE, data)
        return True
    return False


def get_level(points):
    return max(1, points // 25)


def add_message_count(chat_id, user_id, username=None, first_name=None):
    data = load_json(STATS_FILE)
    chat_key = str(chat_id)
    user_key = str(user_id)
    if chat_key not in data:
        data[chat_key] = {}
    if user_key not in data[chat_key]:
        data[chat_key][user_key] = {"messages": 0, "points": 0, "username": username, "first_name": first_name}
    if username:
        data[chat_key][user_key]["username"] = username
    if first_name:
        data[chat_key][user_key]["first_name"] = first_name
    old_points = data[chat_key][user_key]["points"]
    old_level = get_level(old_points)
    data[chat_key][user_key]["messages"] += 1
    data[chat_key][user_key]["points"] += 1
    new_points = data[chat_key][user_key]["points"]
    new_level = get_level(new_points)
    save_json(STATS_FILE, data)
    return {
        "messages": data[chat_key][user_key]["messages"],
        "points": new_points,
        "old_level": old_level,
        "new_level": new_level,
        "leveled_up": new_level > old_level
    }


def get_user_stats(chat_id, user_id):
    data = load_json(STATS_FILE)
    chat_key = str(chat_id)
    user_key = str(user_id)
    if chat_key in data and user_key in data[chat_key]:
        return data[chat_key][user_key]
    return {"messages": 0, "points": 0}


def get_chat_members(chat_id):
    data = load_json(STATS_FILE)
    chat_key = str(chat_id)
    if chat_key in data:
        return data[chat_key]
    return {}


def load_known_chats():
    global known_chats
    known_chats = load_json(CHATS_FILE)


def save_known_chats():
    save_json(CHATS_FILE, known_chats)


# ============ توابع ضد اسپم و اخطار ============

def get_antispam(chat_id):
    chat_key = str(chat_id)
    if chat_key not in antispam_settings:
        antispam_settings[chat_key] = {"enabled": False, "limit": 5}
        save_json(ANTISPAM_FILE, antispam_settings)
    return antispam_settings[chat_key]


def set_antispam(chat_id, enabled):
    chat_key = str(chat_id)
    if chat_key not in antispam_settings:
        antispam_settings[chat_key] = {"enabled": False, "limit": 5}
    antispam_settings[chat_key]["enabled"] = enabled
    save_json(ANTISPAM_FILE, antispam_settings)


def set_warning_limit(chat_id, limit):
    chat_key = str(chat_id)
    if chat_key not in antispam_settings:
        antispam_settings[chat_key] = {"enabled": False, "limit": 5}
    antispam_settings[chat_key]["limit"] = limit
    save_json(ANTISPAM_FILE, antispam_settings)


def get_warning_limit(chat_id):
    return get_antispam(chat_id).get("limit", 5)


def get_warning(chat_id, user_id):
    chat_key = str(chat_id)
    user_key = str(user_id)
    if chat_key in user_warnings and user_key in user_warnings[chat_key]:
        return user_warnings[chat_key][user_key]
    return 0


def set_warning(chat_id, user_id, count):
    chat_key = str(chat_id)
    user_key = str(user_id)
    if chat_key not in user_warnings:
        user_warnings[chat_key] = {}
    if count <= 0:
        if user_key in user_warnings[chat_key]:
            del user_warnings[chat_key][user_key]
    else:
        user_warnings[chat_key][user_key] = count
    save_json(WARNINGS_FILE, user_warnings)


def check_flood(chat_id, user_id, msg_id):
    key = (chat_id, user_id)
    now = time.time()
    if key not in recent_msgs:
        recent_msgs[key] = []
    recent_msgs[key] = [(t, m) for t, m in recent_msgs[key] if now - t < 3.0]
    recent_msgs[key].append((now, msg_id))
    recent_one_sec = [(t, m) for t, m in recent_msgs[key] if now - t < FLOOD_WINDOW]
    if len(recent_one_sec) > FLOOD_THRESHOLD:
        msgs_to_delete = [m for t, m in recent_msgs[key]]
        recent_msgs[key] = []
        return msgs_to_delete
    return None


async def delete_messages(chat_id, msg_ids):
    for mid in msg_ids:
        try:
            await api_call("deleteMessage", {"chat_id": chat_id, "message_id": mid})
        except:
            pass


async def mute_user_for(chat_id, user_id, seconds):
    try:
        from datetime import datetime, timedelta
        until = int((datetime.now() + timedelta(seconds=seconds)).timestamp())
    except:
        until = int(time.time() + seconds)
    result = await api_call("restrictChatMember", {
        "chat_id": chat_id,
        "user_id": user_id,
        "permissions": {
            "can_send_messages": False,
            "can_send_media_messages": False,
            "can_send_other_messages": False,
            "can_add_web_page_previews": False
        },
        "until_date": until
    })
    return result


async def apply_warning(chat_id, user_id, user_name):
    limit = get_warning_limit(chat_id)
    current = get_warning(chat_id, user_id) + 1
    set_warning(chat_id, user_id, current)
    if current >= limit:
        set_warning(chat_id, user_id, 0)
        try:
            await client.ban_chat_member(chat_id, user_id)
        except:
            pass
        await api_call("sendMessage", {
            "chat_id": chat_id,
            "text": f"🚫 **{user_name}** جان، به خاطر رسیدن اخطارها به سقف ({current}/{limit})، از گروه اخراج شدی! 👋"
        })
        return "kick"
    elif limit == 5 and current == 4:
        await mute_user_for(chat_id, user_id, 3 * 3600)
        await api_call("sendMessage", {
            "chat_id": chat_id,
            "text": f"🔇 **{user_name}** جان، به خاطر اخطارها ۳ ساعت سکوت شدی!\n📊 اخطار: **{current}/{limit}**"
        })
        return "mute_3h"
    elif limit == 5 and current == 3:
        await mute_user_for(chat_id, user_id, 1 * 3600)
        await api_call("sendMessage", {
            "chat_id": chat_id,
            "text": f"🔇 **{user_name}** جان، به خاطر اخطارها ۱ ساعت سکوت شدی!\n📊 اخطار: **{current}/{limit}**"
        })
        return "mute_1h"
    else:
        await api_call("sendMessage", {
            "chat_id": chat_id,
            "text": f"⚠️ **{user_name}** جان، یه اخطار گرفتی!\n📊 اخطار: **{current}/{limit}**"
        })
        return "warn"


CALL_RESPONSES = [
    "جانم؟ 💚 چه خبر رفیق؟ چطور می‌تونم کمکت کنم؟",
    "سلام گل من! 🌹 بگو ببینم چی می‌خوای؟",
    "اومدم! 🏃‍♂️ چیکار داری برام؟ همیشه آماده‌ام!",
    "بله بله؟ 😊 من اینجام، بگو چی شده.",
    "جان دلم! 💫 بفرما، در خدمتم.",
    "چه خوب که صدام زدی! 🤗 چطور می‌تونم خوشحالت کنم؟",
    "من همیشه بیدارم! 🌙 بگو ببینم چی می‌خوای رفیق.",
    "سلام سلام! 🌸 چه عجب یادی از ما کردی! بگو چیکار داری.",
    "بله؟ 🎯 گوش به فرمانم! دستور بده.",
    "اومدم پیشت! ✨ هر چی بخوای انجام می‌دم.",
]

TIME_QUOTES = [
    "✨ زمان می‌گذرد، اما لحظه‌های خوب در یادها می‌مانند.",
    "💚 هر ثانیه یه فرصت تازه‌ست، قدرش رو بدون.",
    "🌟 امروز یه صفحه‌ی خالی از دفتر زندگیته، زیبا بنویسش.",
    "🌱 همین حالا وقت شروع یه کار خوبه!",
    "🔥 لحظه‌ها منتظر نمی‌مونن، پس خودت رو بساز.",
    "💫 بهترین زمان برای شروع، همین حالاست.",
    "🌸 یه لبخند بزن، دنیا قشنگ‌تر می‌شه.",
    "🎯 هدف‌هات رو یادت باشه، وقت طلاست!",
    "🌙 بعضی وقتا سکوت و آرامش، بهترین گزینه‌ست.",
    "☀️ هر روز، یه شروع جدید و پر از امیده.",
]

LEVELUP_REPLIES = [
    "🎉 **{name} جان، تبریک می‌گم!** 🌟\n\n🏆 به **لول {level}** رسیدی! 🎊\n💚 امتیازت الان: **{points}**\n\nهمین‌طور فعال بمون، داری می‌ترکونی! 🔥",
    "✨ **{name} عزیز، یه خبر خوب!** 🎈\n\n🚀 سطحت رفت بالاتر و الان **لول {level}** هستی!\n⭐ امتیاز: **{points}**\n\nافتخار می‌کنم بهت رفیق! 💫",
    "🎊 **{name} جان، لول آپ شدی!** 🌈\n\n🏅 لول جدیدت: **{level}**\n💎 امتیاز: **{points}**\n\nداری پیشرفت می‌کنی، همین‌طور ادامه بده! 💚",
    "🌟 **آفرین {name}!** 🎉\n\nتو الان **لول {level}** هستی! 🏆\nامتیاز: **{points}** ✨\n\nیه قدم دیگه به افتخارات نزدیک‌تر شدی! 💫",
    "🔥 **{name} داری می‌درخشی!** 💥\n\nبه **لول {level}** رسیدی و امتیازت شد **{points}**! 💎\n\nهمین انگیزه رو حفظ کن، قهرمان! 🏆",
]


SALAM_RESPONSES = [
    "سلام {name} جان! 🌹 چه خوب که اومدی، دلم برات تنگ شده بود! 💚",
    "سلام سلام! 🌸 {name} عزیز، چطوری؟ امیدوارم روزت پر از انرژی باشه! ✨",
    "سلام {name} جان! 😊 چه خبر؟ همه چی خوبه؟ من همینجام اگه کمکی خواستی! 💫",
    "به به! {name} اومد! 🎉 سلام رفیق، خوش اومدی! چطوری؟ 💚",
    "سلام {name} جان! 🌻 دلم روشن شد که دیدمت! روزت بخیر! ☀️",
    "سلام {name} عزیز! 🥰 چه عجب! یادی از ما کردی! چطوری رفیق؟",
    "سلام گلم! 🌷 {name} جان، حالت چطوره؟ همیشه خوشحالم که می‌بینمت! 💚",
    "سلام {name} جان! 🌺 چه خوب که سلام دادی، منم بهت سلام می‌کنم! روزت قشنگ! ✨",
    "سلام {name}! 💐 امیدوارم امروز روز فوق‌العاده‌ای داشته باشی! 💫",
    "سلام {name} جان! 🍀 چه خبر از احوالات؟ همه چی آرومه پیشت؟ 💚",
]

SALAM_KEYWORDS = ["سلام", "سلام علیکم", "سلام علیک", "سلام دوستان", "سلام بچه‌ها"]

SILENT_MESSAGES = [
    "🔔 سلام سلام! چقدر اینجا ساکته!\n\nکسی اینجا نیست یه سلامی بکنه؟ 😊\nمن دلم براتون تنگ شده بود! 💚",
    "🍃 هوووم... اینجا بوی سکوت می‌ده!\n\nکجایید رفقا؟ بیاید یه گپی بزنیم، یه خنده‌ای بکنیم! 😄\nدلم برای صداتون تنگ شده 🥺",
    "☕️ یه چایی می‌ریزم، کی پایه‌ی گپِ؟\n\nبیاید بچه‌ها، گروه بدون شما روح نداره! 💫\nیه پیام بدید، حال ما رو خوب کنید 🌹",
    "🎈 هوی! کسی خونه هست؟\n\nگروه ما یه کم زنده‌شدن می‌خواد!\nبیاید یه گفتگوی گرم راه بندازیم 💚\nچه خبر از احوالاتتون؟",
    "🌙 سکوت اینجا خیلی طولانی شد!\n\nرفقای گلم کجایید؟ بیاید یه لحظه هم که شده کنار هم باشیم و گپ بزنیم 😊\nچه چیز جالبی امروز یاد گرفتید؟",
    "🎵 یه ترانه از سکوت می‌شنویم!\n\nاما ما ترجیح می‌دیم صدای شما رو بشنویم!\nبیاید از روزتون بگید، از احساستون بنویسید 💚",
    "🌟 ستاره‌ها هم توی آسمون تنها نیستن، پس ما چرا ساکت باشیم؟\n\nبیاید کنار هم، یه گپ گرم بزنیم! ☕️\nچی باعث شد امروز لبخند بزنید؟",
    "🎨 زندگی یه بوم خالیه، با کلماتتون رنگش کنید!\n\nگروه منتظر کلمات گرمتونه 💫\nبیاید یه گفتگوی قشنگ بسازیم 🌹",
    "🌸 حتی یه گل هم برای رشد به مراقبت نیاز داره!\n\nگروه ما هم به حضورتون نیاز داره 💚\nبیاید با هم پرش کنیم، حرف بزنیم، بخندیم 😊",
    "🏡 خونه بدون اهلش سرد می‌شه!\n\nاین گروه، خونه‌ی دوم ماست.\nبیاید با هم این خونه رو گرم کنیم! 🔥💚",
]

WELCOME_MESSAGES = [
    "🌟 به به! **{name}** عزیز اومد!\n\nخوش اومدی به جمع گرممون 💚\nامیدوارم اینجا لحظه‌های خوبی داشته باشی! ✨",
    "🎉 **{name}** جان، خوش اومدی!\n\nچه خوب که بهمون پیوستی 🌹\nدلمون برات تنگ شده بود! 💫",
    "🌸 سلام **{name}** عزیز!\n\nخوش اومدی به خونه‌ی جدیدت 🏡\nامیدوارم کنارمون احساس راحتی کنی 💚",
    "✨ **{name}** جان، به جمعمون خوش اومدی!\n\nامیدوارم اینجا پُر از لحظه‌های قشنگ باشه برات 🌟\nراحت باش و خودت رو خونه بدون 💫",
    "🔥 **{name}** عزیز، خوش اومدی!\n\nچه عجب! بهمون سر زدی 🌹\nامیدوارم روزای خوبی رو اینجا بگذرونی 💚",
    "🌟 خوش اومدی **{name}** جان!\n\nیه چایی برات بریزم؟ ☕️\nکنارمون راحت باش، ما همه رفیقیم 💫",
    "🎊 **{name}** عزیز، به خانواده‌مون خوش اومدی!\n\nامیدوارم اینجا کلی دوست خوب پیدا کنی 🌸\nخوشحالیم که هستی! 💚",
    "💫 سلام **{name}** جان!\n\nخوش اومدی به جمعمون 🌹\nدلمون می‌خواست زودتر ببینیمت! ✨",
    "🌺 **{name}** عزیز، خوش اومدی!\n\nچه خبر؟ 🌸\nامیدوارم اینجا لحظه‌های خوبی بسازی 💚",
    "🏡 به **{name}** جان، خوش اومدی!\n\nاین خونه حالا با تو گرم‌تر شد 🔥\nخوشحالیم که کنارمونی 💫",
]

GOODBYE_MESSAGES = [
    "😢 **{name}** جان، داری میری؟\n\nامیدوارم هر جا هستی حالت خوب باشه 💚\nما همیشه به یادت هستیم 🌹",
    "🥺 **{name}** عزیز، رفتنت رو دیدیم...\n\nامیدوارم یه روز برگردی 🌸\nدلمون برات تنگ می‌شه! 💫",
    "👋 **{name}** جان، خداحافظ!\n\nسفرت بی‌خطر و روزات پر از خوبی 🌟\nهر وقت خواستی، درِ گروه بازه! 💚",
    "🌙 **{name}** عزیز، دلمون گرفت...\n\nامیدوارم بهترین‌ها برات اتفاق بیفته ✨\nما همیشه اینجاییم اگه برگشتی 🌹",
    "💫 **{name}** جان، خدافظ!\n\nممنون که یه مدت کنارمون بودی 💚\nموفق باشی رفیق! 🌸",
    "😔 **{name}** عزیز رفت...\n\nولی خاطرش همیشه پیشمونه 🌹\nامیدوارم بهترین سرنوشت رو داشته باشی 💫",
    "🍃 **{name}** جان، خداحافظ!\n\nامیدوارم تو مسیر زندگی، گل‌های زیبایی بچینی 🌸\nخدانگهدار رفیق! 💚",
    "🌺 **{name}** عزیز، رفتن انتخاب توئه...\n\nما همیشه آرزوی خوبی برات داریم 🌟\nهر وقت خواستی، برگرد! 💫",
    "💚 **{name}** جان، خدافظ!\n\nامیدوارم یاد لحظه‌های خوبی که با هم داشتیم بخیر 🌹\nموفق باشی! ✨",
    "🌈 **{name}** عزیز، رفتنت دلگیرمون کرد...\n\nولی بهترین آرزوها رو برات داریم 🌸\nخدانگهدار رفیق! 💚",
]


ABOUT_TEXT = (
    "🌘 **𝙻𝚒𝚍𝚘𝚌𝚊𝚒𝚗𝚎 𝚜𝚝𝚞𝚍𝚒𝚘** 🩸\n\n"
    "═══════════════════════\n\n"
    "🎯 **ما کی هستیم؟**\n\n"
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
    "👥 **اعضای تیم:**\n\n"
    "👑 **مدیریت و پشتیبانی:**\n"
    "💬 @pv_storms\n\n"
    "🛠️ **توسعه و فنی:**\n"
    "💬 @pv_ahzar\n\n"
    "═══════════════════════\n\n"
    "📌 **ارتباط با ما:**\n"
    "برای سفارش یا مشاوره، به یکی از آیدی‌های بالا پیام بدید.\n\n"
    "💚 ممنون که به ما اعتماد می‌کنید! 🌹"
)


def get_calendar_text():
    try:
        now = jdatetime.datetime.now()
        weekdays = ["شنبه", "یک‌شنبه", "دوشنبه", "سه‌شنبه", "چهارشنبه", "پنج‌شنبه", "جمعه"]
        months = ["فروردین", "اردیبهشت", "خرداد", "تیر", "مرداد", "شهریور", "مهر", "آبان", "آذر", "دی", "بهمن", "اسفند"]
        weekday_name = weekdays[now.weekday()]
        month_name = months[now.month - 1]
        date_str = f"{weekday_name} {now.day} {month_name} {now.year}"
        time_str = now.strftime("%H:%M:%S")
        if now.month in [1, 2, 3]:
            season = "🌸 بهار"
        elif now.month in [4, 5, 6]:
            season = "☀️ تابستان"
        elif now.month in [7, 8, 9]:
            season = "🍂 پاییز"
        else:
            season = "❄️ زمستان"
        text = (
            f"📅 **تقویم امروز**\n\n"
            f"═══════════════════\n\n"
            f"🗓️ **تاریخ:** {date_str}\n"
            f"🕐 **ساعت:** {time_str}\n\n"
            f"───────────────────\n"
            f"📌 **جزئیات:**\n"
            f"🔸 روز: {weekday_name}\n"
            f"🔹 ماه: {month_name}\n"
            f"🔸 سال: {now.year}\n"
            f"🔹 فصل: {season}\n\n"
            f"═══════════════════\n\n"
            f"💚 امیدوارم امروزت پر از لحظه‌های خوب باشه! ✨"
        )
        return text
    except Exception as e:
        print(f"Calendar error: {e}")
        return "❌ متاسفانه در نمایش تقویم خطایی پیش اومد."


def get_calendar_keyboard():
    return {"inline_keyboard": [[{"text": "📅 تقویم امروز", "callback_data": "calendar"}]]}


async def api_call(method, payload):
    url = f"https://tapi.bale.ai/bot{BOT_TOKEN}/{method}"
    async with aiohttp.ClientSession() as session:
        async with session.post(url, json=payload) as resp:
            return await resp.json()


async def is_admin(chat_id, user_id):
    try:
        admins = await client.get_chat_administrators(chat_id)
        if admins:
            for admin in admins:
                if admin.user.id == user_id:
                    return True
        return False
    except Exception as e:
        print(f"Admin check error: {e}")
        return False


def get_warm_reply(action, user_name=""):
    replies = {
        "ban": f"🚫 {user_name} جان، با احترام از جمعمون خداحافظی کرد. امیدوارم روز خوبی داشته باشی! 👋",
        "unban": f"🎉 {user_name} عزیز دوباره به جمعمون برگشت! خوش اومدی رفیق! 💚",
        "mute": f"🔇 {user_name} جان، یه کم ساکت باش تا جمع آروم بشه. بعداً دوباره حرف بزن! 😊",
        "unmute": f"🔊 {user_name} عزیز، سکوتت تموم شد. می‌تونی دوباره حرف بزنی! 💬",
    }
    return replies.get(action, "")


def get_help_text():
    return (
        "🌟 خوش اومدی به پنل راهنمای ربات مدیریت گروه PBS! 🌟\n\n"
        "👤 **دستورات عمومی:**\n"
        "پروفایل → نمایش اطلاعات و آمار\n"
        "تایم یا ساعت → نمایش ساعت و تاریخ\n"
        "تقویم یا تاریخ → نمایش تقویم شمسی\n"
        "ربات → صدا زدن ربات\n"
        "سلام → ربات جواب سلام می‌ده\n\n"
        "👮‍♂️ **دستورات مدیریتی (فقط ادمین‌ها):**\n"
        "🚪 اخراج: بن / کیک / اخراج / سیک\n"
        "🎉 آزاد کردن: آنبن / حذف بن\n"
        "🔇 سکوت: سکوت / میوت\n"
        "🔊 لغو سکوت: حذف سکوت / آن میوت\n"
        "📢 تگ کردن اعضا: تگ\n\n"
        "⚠️ **سیستم اخطار:**\n"
        "ریپلای + اخطار → اخطار دادن\n"
        "ریپلای + حذف اخطار → حذف یه اخطار\n"
        "ریپلای + حذف همه اخطارها → حذف کل اخطارها\n\n"
        "🛡️ **ضد اسپم:**\n"
        "ضد اسپم روشن / فعال → روشن کردن\n"
        "تنظیم اخطار → تنظیم تعداد اخطار\n\n"
        "🏷️ **دستورات لقب (فقط ادمین‌ها):**\n"
        "ریپلای + لقب [متن] → ثبت لقب\n"
        "ریپلای + حذف لقب → حذف لقب\n\n"
        "📊 سیستم لول: هر ۲۵ امتیاز = ۱ لول\n"
        "🔔 سیستم ضد سکوت: اگه گروه ۳۰ دقیقه ساکت بمونه، ربات پیام می‌فرسته."
    )


def is_group(chat):
    try:
        if hasattr(chat, 'type') and chat.type:
            return chat.type in ['group', 'supergroup']
        if hasattr(chat, 'title') and chat.title:
            return True
        return False
    except:
        return False


async def silence_checker():
    print("🔍 تسک بررسی سکوت گروه‌ها شروع شد.")
    while True:
        try:
            await asyncio.sleep(CHECK_INTERVAL)
            now = time.time()
            for chat_id_str, title in list(known_chats.items()):
                try:
                    chat_id = int(chat_id_str)
                except:
                    continue
                last = last_activity.get(chat_id, 0)
                last_nudge_time = last_nudge.get(chat_id, 0)
                if last == 0:
                    continue
                silent_for = now - last
                if silent_for >= SILENT_THRESHOLD and (now - last_nudge_time) >= NUDGE_COOLDOWN:
                    msg = random.choice(SILENT_MESSAGES)
                    result = await api_call("sendMessage", {"chat_id": chat_id, "text": msg})
                    if result.get("ok"):
                        last_nudge[chat_id] = now
                        last_activity[chat_id] = now
                        print(f"✅ پیام سکوت به گروه {title} ({chat_id}) فرستاده شد.")
        except Exception as e:
            print(f"Silence checker error: {e}")


@client.event
async def on_ready():
    print(f"✨ {client.user} با موفقیت روشن شد و آماده‌ی خدمته!")
    load_known_chats()
    load_all_data()
    asyncio.create_task(silence_checker())


@client.event
async def on_callback(callback_query):
    try:
        callback_data = callback_query.data
        chat_id = callback_query.message.chat.id
        user_id = callback_query.from_user.id
        user_name = callback_query.from_user.first_name

        print(f"🔍 کلیک روی دکمه: {callback_data}")

        if callback_data == "help_menu":
            await api_call("sendMessage", {
                "chat_id": chat_id,
                "text": get_help_text(),
                "reply_markup": get_calendar_keyboard()
            })

        elif callback_data == "about_us":
            await api_call("sendMessage", {"chat_id": chat_id, "text": ABOUT_TEXT})

        elif callback_data == "support":
            support_text = (
                "💬 **پشتیبانی ربات PBS**\n\n"
                "اگه سوال، مشکل یا پیشنهادی داری، می‌تونی به آیدی‌های زیر پیام بدی:\n\n"
                "👤 @pv_storms\n"
                "👤 @pv_ahzar\n\n"
                "من همیشه خوشحال می‌شم کمکت کنم! 💚"
            )
            await api_call("sendMessage", {"chat_id": chat_id, "text": support_text})

        elif callback_data == "calendar":
            await api_call("sendMessage", {"chat_id": chat_id, "text": get_calendar_text()})

        elif callback_data == "warn_limit_3":
            if not await is_admin(chat_id, user_id):
                return
            set_warning_limit(chat_id, 3)
            await api_call("sendMessage", {
                "chat_id": chat_id,
                "text": "✅ تعداد اخطار روی **۳** تنظیم شد."
            })

        elif callback_data == "warn_limit_5":
            if not await is_admin(chat_id, user_id):
                return
            set_warning_limit(chat_id, 5)
            await api_call("sendMessage", {
                "chat_id": chat_id,
                "text": "✅ تعداد اخطار روی **۵** تنظیم شد."
            })

        elif callback_data == "warn_limit_save":
            if not await is_admin(chat_id, user_id):
                return
            current = get_warning_limit(chat_id)
            await api_call("sendMessage", {
                "chat_id": chat_id,
                "text": f"💾 تنظیمات ذخیره شد.\n📊 تعداد اخطار فعلی: **{current}**"
            })

        elif callback_data == "antispam_on":
            if not await is_admin(chat_id, user_id):
                return
            set_antispam(chat_id, True)
            keyboard = {"inline_keyboard": [[{"text": "🛑 خاموش کردن ضد اسپم", "callback_data": "antispam_off"}]]}
            await api_call("sendMessage", {
                "chat_id": chat_id,
                "text": "🟢 **ضد اسپم روشن شد!**\n\nاز این به بعد اگه کاربری بیش از ۳ پیام در ۱ ثانیه بفرسته، پیام‌هاش حذف و اخطار می‌گیره.\n\nبرای خاموش کردن روی دکمه‌ی زیر بزنید 👇",
                "reply_markup": keyboard
            })

        elif callback_data == "antispam_off":
            if not await is_admin(chat_id, user_id):
                return
            set_antispam(chat_id, False)
            keyboard = {"inline_keyboard": [[{"text": "🟢 روشن کردن ضد اسپم", "callback_data": "antispam_on"}]]}
            await api_call("sendMessage", {
                "chat_id": chat_id,
                "text": "🔴 **ضد اسپم خاموش شد!**\n\nاز این به بعد پیام‌ها بررسی نمی‌شن.\n\nبرای روشن کردن روی دکمه‌ی زیر بزنید 👇",
                "reply_markup": keyboard
            })

    except Exception as e:
        print(f"Callback error: {e}")


@client.event
async def on_member_chat_join(message, chat, user):
    try:
        if not is_group(chat):
            return
        if user.is_bot:
            return
        chat_id = chat.id
        name = user.first_name or "دوست عزیز"
        join_time = get_persian_time()
        welcome = random.choice(WELCOME_MESSAGES).format(name=name)
        welcome += f"\n\n🕐 **زمان ورود:** {join_time}"
        await api_call("sendMessage", {"chat_id": chat_id, "text": welcome})
        print(f"👋 خوش‌آمدگویی به {name} در گروه {chat_id}")
    except Exception as e:
        print(f"Welcome error: {e}")


@client.event
async def on_member_chat_leave(message, chat, user):
    try:
        if not is_group(chat):
            return
        if user.is_bot:
            return
        chat_id = chat.id
        name = user.first_name or "دوست عزیز"
        leave_time = get_persian_time()
        goodbye = random.choice(GOODBYE_MESSAGES).format(name=name)
        goodbye += f"\n\n🕐 **زمان خروج:** {leave_time}"
        await api_call("sendMessage", {"chat_id": chat_id, "text": goodbye})
        print(f"👋 خداحافظی با {name} از گروه {chat_id}")
    except Exception as e:
        print(f"Goodbye error: {e}")


@client.event
async def on_message(message: Message):
    if not message.text:
        return

    text = message.text.strip()
    chat_id = message.chat.id
    user_id = message.author.id
    user_name = message.author.first_name
    username = getattr(message.author, 'username', None)

    if is_group(message.chat):
        last_activity[chat_id] = time.time()
        if str(chat_id) not in known_chats:
            chat_title = getattr(message.chat, 'title', None) or 'گروه'
            known_chats[str(chat_id)] = chat_title
            save_known_chats()

    # ===== ضد اسپم =====
    is_user_admin = False
    if is_group(message.chat):
        is_user_admin = await is_admin(chat_id, user_id)

    if is_group(message.chat) and not is_user_admin:
        spam = get_antispam(chat_id)
        if spam.get("enabled", False):
            flood_msgs = check_flood(chat_id, user_id, message.id)
            if flood_msgs:
                await delete_messages(chat_id, flood_msgs)
                result = await apply_warning(chat_id, user_id, user_name)
                if result == "kick":
                    await api_call("sendMessage", {
                        "chat_id": chat_id,
                        "text": f"🗑️ تمام پیام‌های اسپم **{user_name}** پاک شدن."
                    })
                return

    # ===== ثبت آمار =====
    stats = add_message_count(chat_id, user_id, username=username, first_name=user_name)

    if stats["leveled_up"]:
        level_msg = random.choice(LEVELUP_REPLIES).format(
            name=user_name, level=stats["new_level"], points=stats["points"]
        )
        await message.reply(level_msg)

    # ===== دستورات عمومی =====
    if text == "/start":
        reply_text = (
            f"سلام {user_name} جان! 🌹\n\n"
            f"چه خوب که اومدی پیشم 💚\n"
            f"من اینجام تا کمکت کنم، باهات گپ بزنم و هر کاری از دستم بربیاد برات انجام بدم.\n\n"
            f"از دکمه‌های زیر استفاده کن 👇"
        )
        keyboard = {
            "inline_keyboard": [
                [{"text": "📖 راهنما", "callback_data": "help_menu"}],
                [{"text": "🌘 درباره ما", "callback_data": "about_us"}],
                [{"text": "💬 پشتیبانی", "callback_data": "support"}]
            ]
        }
        await api_call("sendMessage", {"chat_id": chat_id, "text": reply_text, "reply_markup": keyboard})
        return

    if text == "/help" or text == "راهنما":
        await api_call("sendMessage", {
            "chat_id": chat_id, "text": get_help_text(), "reply_markup": get_calendar_keyboard()
        })
        return

    if text == "درباره ما" or text == "/about":
        await message.reply(ABOUT_TEXT)
        return

    if text in ["تقویم", "تاریخ"]:
        await message.reply(get_calendar_text())
        return


    # ===== تنظیم اخطار =====
    if text == "تنظیم اخطار":
        if not await is_admin(chat_id, user_id):
            await message.reply("⚠️ فقط ادمین‌ها می‌تونن این تنظیم رو انجام بدن.")
            return
        current = get_warning_limit(chat_id)
        keyboard = {
            "inline_keyboard": [
                [{"text": "⚠️ از ۳ اخطار", "callback_data": "warn_limit_3"}],
                [{"text": "⚠️ از ۵ اخطار", "callback_data": "warn_limit_5"}],
                [{"text": "💾 ثبت تغییرات", "callback_data": "warn_limit_save"}]
            ]
        }
        await api_call("sendMessage", {
            "chat_id": chat_id,
            "text": f"⚙️ **تنظیمات اخطار**\n\nتعداد اخطار فعلی: **{current}**\n\nاز دکمه‌های زیر استفاده کن 👇",
            "reply_markup": keyboard
        })
        return

    # ===== ضد اسپم روشن =====
    if text in ["ضد اسپم روشن", "ضد اسپم فعال"]:
        if not await is_admin(chat_id, user_id):
            await message.reply("⚠️ فقط ادمین‌ها می‌تونن ضد اسپم رو روشن کنن.")
            return
        set_antispam(chat_id, True)
        keyboard = {"inline_keyboard": [[{"text": "🛑 خاموش کردن ضد اسپم", "callback_data": "antispam_off"}]]}
        await api_call("sendMessage", {
            "chat_id": chat_id,
            "text": "🟢 **ضد اسپم روشن شد!**\n\nبرای خاموش کردن از دکمه‌ی زیر استفاده کنید 👇",
            "reply_markup": keyboard
        })
        return

    # ===== اخطار دادن (ادمین) =====
    if text == "اخطار":
        if not await is_admin(chat_id, user_id):
            await message.reply("⚠️ فقط ادمین‌ها می‌تونن اخطار بدن.")
            return
        if not message.reply_to_message:
            await message.reply("⚠️ روی پیام کاربر ریپلای کن و بنویس: اخطار")
            return
        target_user_id = message.reply_to_message.author.id
        target_user_name = message.reply_to_message.author.first_name
        await apply_warning(chat_id, target_user_id, target_user_name)
        return

    # ===== حذف اخطار =====
    if text == "حذف اخطار":
        if not await is_admin(chat_id, user_id):
            await message.reply("⚠️ فقط ادمین‌ها می‌تونن اخطار رو حذف کنن.")
            return
        if not message.reply_to_message:
            await message.reply("⚠️ روی پیام کاربر ریپلای کن و بنویس: حذف اخطار")
            return
        target_user_id = message.reply_to_message.author.id
        target_user_name = message.reply_to_message.author.first_name
        current = get_warning(chat_id, target_user_id)
        if current > 0:
            set_warning(chat_id, target_user_id, current - 1)
            new_count = current - 1
            await api_call("sendMessage", {
                "chat_id": chat_id,
                "text": f"✅ یک اخطار **{target_user_name}** حذف شد.\n📊 اخطار فعلی: **{new_count}/{get_warning_limit(chat_id)}**"
            })
        else:
            await message.reply(f"⚠️ **{target_user_name}** هیچ اخطاری نداره.")
        return

    # ===== حذف همه اخطارها =====
    if text == "حذف همه اخطارها" or text == "حذف همه اخطار":
        if not await is_admin(chat_id, user_id):
            await message.reply("⚠️ فقط ادمین‌ها می‌تونن اخطارها رو حذف کنن.")
            return
        if not message.reply_to_message:
            await message.reply("⚠️ روی پیام کاربر ریپلای کن و بنویس: حذف همه اخطارها")
            return
        target_user_id = message.reply_to_message.author.id
        target_user_name = message.reply_to_message.author.first_name
        set_warning(chat_id, target_user_id, 0)
        await api_call("sendMessage", {
            "chat_id": chat_id,
            "text": f"✅ تمام اخطارهای **{target_user_name}** حذف شدن."
        })
        return

    # ===== تگ =====
    if text == "تگ":
        if not is_group(message.chat):
            await message.reply("⚠️ این دستور فقط توی گروه کار می‌کنه.")
            return
        if not await is_admin(chat_id, user_id):
            await message.reply("⚠️ فقط ادمین‌ها می‌تونن از این دستور استفاده کنن.")
            return
        members = get_chat_members(chat_id)
        if not members:
            await message.reply("⚠️ هنوز کسی توی گروه پیام نداده.")
            return
        mentions = []
        for member_id, member_data in members.items():
            member_username = member_data.get("username")
            if member_username:
                mentions.append(f"@{member_username}")
        if not mentions:
            await message.reply("⚠️ هیچ کاربری با یوزرنیم پیدا نشد.")
            return
        tag_text = (
            f"📢 **توجه توجه!**\n\n"
            f"🔔 همه بیان که یه خبر مهم داریم!\n\n"
            f"{' '.join(mentions)}\n\n"
            f"💚 منتظرتونیم، بیاید گپ بزنیم! 🌹"
        )
        await api_call("sendMessage", {"chat_id": chat_id, "text": tag_text})
        return


    # ===== پروفایل =====
    if text == "پروفایل" or text == "/profile":
        if message.reply_to_message:
            target = message.reply_to_message.author
        else:
            target = message.author
        target_id = target.id
        target_name = target.first_name
        target_username = target.username or "ندارد"
        user_stats = get_user_stats(chat_id, target_id)
        messages = user_stats.get("messages", 0)
        points = user_stats.get("points", 0)
        level = get_level(points)
        progress = points % 25
        filled = int(progress / 25 * 10)
        bar = "▓" * filled + "░" * (10 - filled)
        nickname = get_nickname(target_id)
        nickname_text = nickname if nickname else "ثبت نشده"
        warn_count = get_warning(chat_id, target_id)
        warn_limit = get_warning_limit(chat_id)
        reply = (
            f"═══════════════════\n"
            f"   🎴 کارت کاربری\n"
            f"═══════════════════\n\n"
            f"   👤 {target_name}\n"
            f"   🔗 @{target_username}\n"
            f"   🔑 {target_id}\n\n"
            f"───────────────────\n"
            f"📊 آمار فعالیت\n"
            f"───────────────────\n"
            f"💬 پیام‌ها: {messages}\n"
            f"⭐ لول: {level}\n"
            f"✨ امتیاز: {points}\n"
            f"⚠️ اخطار: {warn_count}/{warn_limit}\n\n"
            f"📈 پیشرفت تا لول بعدی:\n"
            f"{bar} {progress}/25\n\n"
            f"───────────────────\n"
            f"🏷️ لقب: {nickname_text}\n"
            f"───────────────────"
        )
        await message.reply(reply)
        return

    # ===== لقب =====
    if text.startswith("لقب ") or text.startswith("لقب بذار "):
        if not await is_admin(chat_id, user_id):
            await message.reply("⚠️ فقط ادمین‌های گروه می‌تونن لقب تعیین کنن.")
            return
        if not message.reply_to_message:
            await message.reply("⚠️ روی پیام کاربر ریپلای کن و بنویس:\nلقب [متن]")
            return
        if text.startswith("لقب بذار "):
            nickname = text[len("لقب بذار "):].strip()
        else:
            nickname = text[len("لقب "):].strip()
        if not nickname:
            await message.reply("⚠️ متن لقب رو بنویس.")
            return
        if len(nickname) > 20:
            await message.reply("⚠️ لقب نباید بیشتر از ۲۰ کاراکتر باشه.")
            return
        target_user_id = message.reply_to_message.author.id
        target_user_name = message.reply_to_message.author.first_name
        await set_nickname(target_user_id, nickname, user_id)
        await message.reply(
            f"✨ لقب **{target_user_name}** ثبت شد: **{nickname}**"
        )
        return

    if text == "حذف لقب" or text == "پاک کردن لقب":
        if not await is_admin(chat_id, user_id):
            await message.reply("⚠️ فقط ادمین‌های گروه می‌تونن لقب رو حذف کنن.")
            return
        if not message.reply_to_message:
            await message.reply("⚠️ روی پیام کاربر ریپلای کن و بنویس: حذف لقب")
            return
        target_user_id = message.reply_to_message.author.id
        target_user_name = message.reply_to_message.author.first_name
        removed = await remove_nickname(target_user_id)
        if removed:
            await message.reply(f"🗑️ لقب **{target_user_name}** حذف شد.")
        else:
            await message.reply(f"⚠️ **{target_user_name}** لقبی نداره.")
        return


    # ===== تایم =====
    if text in ["تایم", "ساعت"]:
        try:
            now = jdatetime.datetime.now()
            weekdays = ["شنبه", "یک‌شنبه", "دوشنبه", "سه‌شنبه", "چهارشنبه", "پنج‌شنبه", "جمعه"]
            months = ["فروردین", "اردیبهشت", "خرداد", "تیر", "مرداد", "شهریور", "مهر", "آبان", "آذر", "دی", "بهمن", "اسفند"]
            weekday_name = weekdays[now.weekday()]
            month_name = months[now.month - 1]
            date_str = f"{weekday_name} {now.day} {month_name} {now.year}"
            time_str = now.strftime("%H:%M:%S")
        except Exception:
            import datetime
            now = datetime.datetime.now()
            date_str = now.strftime("%Y/%m/%d")
            time_str = now.strftime("%H:%M:%S")
        random_quote = random.choice(TIME_QUOTES)
        reply = (
            f"⏰ ساعت دقیق به وقت ایران:\n\n"
            f"📅 {date_str}\n"
            f"🕐 {time_str}\n\n"
            f"━━━━━━━━━━━━━━━\n"
            f"{random_quote}"
        )
        await message.reply(reply)
        return

    # ===== صدا زدن ربات =====
    if text in ["ربات", "ربات؟", "ربات!", "هی ربات"]:
        await message.reply(random.choice(CALL_RESPONSES))
        return

    # ===== پاسخ سلام =====
    if text in SALAM_KEYWORDS or (text.startswith("سلام") and len(text) <= 15):
        await message.reply(random.choice(SALAM_RESPONSES).format(name=user_name))
        return

    # ===== دستورات مدیریتی =====
    admin_commands = ["بن", "کیک", "اخراج", "سیک", "آنبن", "حذف بن", "سکوت", "میوت", "حذف سکوت", "آن میوت"]

    if text in admin_commands:
        if not await is_admin(chat_id, user_id):
            await message.reply("⚠️ عزیزم، این دستور فقط برای ادمین‌های گروهه. 🙏")
            return
        if not message.reply_to_message:
            await message.reply("⚠️ روی پیام کاربر ریپلای کن و بعد دستور رو بفرست. 🙏")
            return
        target_user_id = message.reply_to_message.author.id
        target_user_name = message.reply_to_message.author.first_name
        try:
            if text in ["بن", "کیک", "اخراج", "سیک"]:
                await client.ban_chat_member(chat_id, target_user_id)
                await message.reply(get_warm_reply("ban", target_user_name))
            elif text in ["آنبن", "حذف بن"]:
                await client.unban_chat_member(chat_id, target_user_id)
                await message.reply(get_warm_reply("unban", target_user_name))
            elif text in ["سکوت", "میوت"]:
                result = await api_call("restrictChatMember", {
                    "chat_id": chat_id,
                    "user_id": target_user_id,
                    "permissions": {
                        "can_send_messages": False,
                        "can_send_media_messages": False,
                        "can_send_other_messages": False,
                        "can_add_web_page_previews": False
                    }
                })
                if result.get("ok"):
                    await message.reply(get_warm_reply("mute", target_user_name))
                else:
                    await message.reply(f"❌ خطا: {result.get('description')}")
            elif text in ["حذف سکوت", "آن میوت"]:
                result = await api_call("restrictChatMember", {
                    "chat_id": chat_id,
                    "user_id": target_user_id,
                    "permissions": {
                        "can_send_messages": True,
                        "can_send_media_messages": True,
                        "can_send_other_messages": True,
                        "can_add_web_page_previews": True
                    }
                })
                if result.get("ok"):
                    await message.reply(get_warm_reply("unmute", target_user_name))
                else:
                    await message.reply(f"❌ خطا: {result.get('description')}")
        except Exception as e:
            print(f"Admin command error: {e}")
            await message.reply(f"❌ خطایی پیش اومد: {e}")


if __name__ == "__main__":
    client.run()
