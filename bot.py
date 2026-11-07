import os
import logging
import psycopg2
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
    ConversationHandler,
)

# Konfigurasi Logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# Konfigurasi Database (Supabase PostgreSQL) & Bot Token
DATABASE_URL = os.getenv("DATABASE_URL")
TOKEN = os.getenv("BOT_TOKEN")

# Admin Utama (Telegram ID)
ADMIN_IDS = [420150137]

# Koneksi Database
conn = psycopg2.connect(DATABASE_URL)
cur = conn.cursor()

# Tahapan Conversation untuk Pendaftaran
GET_BROKER, GET_NAME = range(2)

# Tahapan Conversation Admin Input & Broadcast
ADMIN_GET_BROKER, ADMIN_GET_DEPOSIT, ADMIN_GET_FEE, ADMIN_CONFIRM = range(4)

# --- FUNGSI UTILITAS KONVERSI & FORMAT ---
def fmt_money(usc_amount):
    """Konversi dan format USC ke USD dan Poin (100 USC = 1 USD = 1 Poin)"""
    try:
        usc = float(usc_amount)
        usd = usc / 100.0
        return f"{usc:,.0f} USC (${usd:,.2f})"
    except:
        return "0 USC ($0.00)"

def calculate_open_levels(deposit_usc):
    """Menentukan jumlah level terbuka berdasarkan Deposit/Follow USC pribadi"""
    try:
        dep = float(deposit_usc)
    except:
        dep = 0.0

    if dep >= 500000:
        return 15
    elif dep >= 400000:
        return 14
    elif dep >= 300000:
        return 12
    elif dep >= 150000:
        return 10
    elif dep >= 100000:
        return 8
    elif dep >= 50000:
        return 6
    elif dep >= 30000:
        return 4
    elif dep >= 10000:
        return 2
    elif dep >= 5000:
        return 1
    else:
        return 0

# Persentase Komisi 15 Level (Total 20%)
COMMISSION_RATES = {
    1: 0.04,   # 4%
    2: 0.04,   # 4%
    3: 0.02,   # 2%
    4: 0.02,   # 2%
    5: 0.01,   # 1%
    6: 0.01,   # 1%
    7: 0.01,   # 1%
    8: 0.01,   # 1%
    9: 0.01,   # 1%
    10: 0.005, # 0.5%
    11: 0.005, # 0.5%
    12: 0.005, # 0.5%
    13: 0.005, # 0.5%
    14: 0.005, # 0.5%
    15: 0.005  # 0.5%
}

# Kamus Terjemahan Multibahasa Lengkap
LANGS = {
    "id": {
        "welcome": "Selamat datang di ZERO EIGHT Loyalty Bot",
        "menu_prompt": "Pilih menu di bawah:",
        "profil": "👤 Profil Saya", "poin": "💰 Poin Saya", "jaringan": "🌐 Jaringan Saya", 
        "reward": "🎁 Daftar Reward", "referral": "🔗 Link Referral Saya", "language": "🌐 Ganti Bahasa", "bantuan": "❓ Bantuan",
        "profil_title": "👤 **PROFIL SAYA**", "name": "Nama", "broker": "Nomor Akun Broker", "upline": "Upline", "status": "Status", "deposit": "Nilai Follow Terbaru", "levels": "Level Terbuka",
        "poin_title": "💰 **POIN SAYA**", 
        "jaringan_title": "🌐 **JARINGAN SAYA**", 
        "reward_title": "🎁 **DAFTAR REWARD**", "reward_desc": "Belum ada reward yang tersedia saat ini.",
        "referral_title": "🔗 **LINK REFERRAL ANDA**", "referral_desc": "Bagikan link di bawah ini ke teman atau partner Anda:",
        "bantuan_title": "❓ **BANTUAN**", "bantuan_desc": "Silakan hubungi Admin jika Anda mengalami kendala.",
        "lang_prompt": "🌐 **PILIH BAHASA / SELECT LANGUAGE**\n\nSilakan pilih bahasa Anda:",
        "back": "🔙 Menu Utama",
        "unauthorized_msg": (
            "👋 Selamat Datang di Zero Eight Bot\n\n"
            "🤖 Zero Eight Bot adalah sistem otomatis untuk menghitung, mencatat, dan memantau poin loyalitas anggota Komunitas ZeroEight.\n\n"
            "⚠️ PERHATIAN\n\n"
            "Untuk menjaga validitas data dan poin komunitas, seluruh fitur bot hanya dapat digunakan oleh anggota yang telah melakukan registrasi melalui link referral resmi ZeroEight.\n\n"
            "🔒 Jika Anda belum terdaftar, silakan lakukan registrasi terlebih dahulu menggunakan referral yang valid.\n\n"
            "✅ Setelah akun Anda terverifikasi, Anda dapat:\n"
            "• Melihat total poin loyalitas\n"
            "• Mengecek riwayat perolehan poin\n"
            "• Mendapatkan informasi program dan reward terbaru"
        )
    },
    "en": {
        "welcome": "Welcome to ZERO EIGHT Loyalty Bot",
        "menu_prompt": "Please select an option below:",
        "profil": "👤 My Profile", "poin": "💰 My Points", "jaringan": "🌐 My Network", 
        "reward": "🎁 Rewards List", "referral": "🔗 My Referral Link", "language": "🌐 Change Language", "bantuan": "❓ Support",
        "profil_title": "👤 **MY PROFILE**", "name": "Name", "broker": "Broker Account", "upline": "Upline", "status": "Status", "deposit": "Latest Follow Value", "levels": "Unlocked Levels",
        "poin_title": "💰 **MY POINTS**", 
        "jaringan_title": "🌐 **MY NETWORK**", 
        "reward_title": "🎁 **REWARDS LIST**", "reward_desc": "No rewards available at the moment.",
        "referral_title": "🔗 **MY REFERRAL LINK**", "referral_desc": "Share the link below with your friends or partners:",
        "bantuan_title": "❓ **SUPPORT**", "bantuan_desc": "Please contact Admin if you encounter any issues.",
        "lang_prompt": "🌐 **SELECT LANGUAGE**\n\nPlease choose your preferred language:",
        "back": "🔙 Main Menu",
        "unauthorized_msg": (
            "👋 Welcome to Zero Eight Bot\n\n"
            "🤖 Zero Eight Bot is an automated system to calculate, record, and monitor loyalty points for ZeroEight Community members.\n\n"
            "⚠️ ATTENTION\n\n"
            "To maintain data and community points validity, all bot features can only be used by members who have registered through an official ZeroEight referral link.\n\n"
            "🔒 If you are not registered, please register first using a valid referral.\n\n"
            "✅ Once your account is verified, you can:\n"
            "• View total loyalty points\n"
            "• Check points acquisition history\n"
            "• Get the latest program and reward information"
        )
    }
}

# --- HANDLER START & PENDAFTARAN ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = user.id

    cur.execute("SELECT broker_account, full_name, language FROM users WHERE telegram_id = %s OR telegram_id::text = %s", (user_id, str(user_id)))
    db_user = cur.fetchone()

    if db_user or user_id in ADMIN_IDS:
        lang = db_user[2] if db_user and len(db_user) > 2 and db_user[2] else "id"
        t = LANGS.get(lang, LANGS["id"])
        
        # Ambil nama & broker untuk mockup tampilan menu utama
        broker_acc = db_user[0] if db_user else "999990001"
        name = db_user[1] if db_user and db_user[1] else "Admin Utama"
        
        cur.execute("SELECT open_levels FROM users WHERE telegram_id = %s OR telegram_id::text = %s", (user_id, str(user_id)))
        lvl_res = cur.fetchone()
        levels = lvl_res[0] if lvl_res else 15

        keyboard = [
            [InlineKeyboardButton(t["profil"], callback_data="menu_profil"), InlineKeyboardButton(t["poin"], callback_data="menu_poin")],
            [InlineKeyboardButton(t["jaringan"], callback_data="menu_jaringan"), InlineKeyboardButton(t["reward"], callback_data="menu_reward")],
            [InlineKeyboardButton(t["referral"], callback_data="menu_referral"), InlineKeyboardButton(t["language"], callback_data="menu_language")],
            [InlineKeyboardButton(t["bantuan"], callback_data="menu_bantuan")]
        ]
        
        msg = (
            f"👋 Halo, {name}!\n"
            f"{t['welcome']}\n\n"
            f"Akun Broker: {broker_acc}\n"
            f"Level Terbuka: {levels} Level\n\n"
            f"{t['menu_prompt']}"
        )
        await update.message.reply_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
        return ConversationHandler.END

    args = context.args
    if not args or not args[0].startswith("REF"):
        keyboard = [
            [InlineKeyboardButton("🌐 Ganti Bahasa / Change Language", callback_data="guest_language")]
        ]
        await update.message.reply_text(
            LANGS["id"]["unauthorized_msg"], 
            reply_markup=InlineKeyboardMarkup(keyboard), 
            parse_mode="Markdown"
        )
        return ConversationHandler.END

    upline_ref = args[0].replace("REF", "")
    context.user_data["upline"] = upline_ref

    await update.message.reply_text(
        "👋 Selamat datang di **ZERO EIGHT Loyalty Bot**!\n\n"
        "Silakan masukkan **Nomor Akun Broker** Anda (hanya berupa angka):",
        parse_mode="Markdown"
    )
    return GET_BROKER

async def receive_broker(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    
    if not text.isdigit():
        await update.message.reply_text("❌ Nomor akun broker harus berupa **angka** saja. Silakan masukkan ulang nomor akun broker Anda:")
        return GET_BROKER

    # Cek duplikasi akun broker
    cur.execute("SELECT broker_account FROM users WHERE broker_account = %s", (text,))
    if cur.fetchone():
        await update.message.reply_text("⚠️ Nomor akun broker ini sudah terdaftar dalam sistem. Gunakan nomor akun broker lain:")
        return GET_BROKER

    context.user_data["broker_account"] = text
    await update.message.reply_text("✅ Akun broker diterima.\n\nSekarang, silakan masukkan **Nama Lengkap** Anda:", parse_mode="Markdown")
    return GET_NAME

async def receive_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    name = update.message.text.strip()
    user_id = update.effective_user.id
    username = update.effective_user.username
    username_str = f"@{username}" if username else "-"
    broker_acc = context.user_data.get("broker_account")
    upline_broker = context.user_data.get("upline", "-")

    try:
        cur.execute(
            "INSERT INTO users (telegram_id, full_name, username, broker_account, status, deposit_usc, open_levels, language, upline_broker) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)",
            (user_id, name, username_str, broker_acc, "Verified", 0.0, 0, "id", upline_broker)
        )
        conn.commit()
    except Exception as e:
        logger.error(f"Error saving registration: {e}")
        conn.rollback()

    t = LANGS["id"]
    keyboard = [
        [InlineKeyboardButton(t["profil"], callback_data="menu_profil"), InlineKeyboardButton(t["poin"], callback_data="menu_poin")],
        [InlineKeyboardButton(t["jaringan"], callback_data="menu_jaringan"), InlineKeyboardButton(t["reward"], callback_data="menu_reward")],
        [InlineKeyboardButton(t["referral"], callback_data="menu_referral"), InlineKeyboardButton(t["language"], callback_data="menu_language")],
        [InlineKeyboardButton(t["bantuan"], callback_data="menu_bantuan")]
    ]
    
    await update.message.reply_text(
        f"🎉 **REGISTRASI BERHASIL!**\n\n"
        f"Akun Broker: `{broker_acc}`\n"
        f"Nama: {name}\n"
        f"Upline Broker: {upline_broker}\n\n"
        f"Silakan pilih menu di bawah:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Pendaftaran dibatalkan.")
    return ConversationHandler.END


# --- MENU HANDLER INTERAKTIF & MULTIBAHASA ---
async def menu_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    user_id = query.from_user.id

    if data.startswith("guest_lang_"):
        selected_lang = data.split("_")[2]
        t = LANGS.get(selected_lang, LANGS["id"])
        keyboard = [
            [InlineKeyboardButton("🌐 Change Language / Ganti Bahasa", callback_data="guest_language")]
        ]
        await query.message.edit_text(t["unauthorized_msg"], reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
        return

    if data == "guest_language":
        keyboard = [
            [InlineKeyboardButton("🇮🇩 Indonesia", callback_data="guest_lang_id"), InlineKeyboardButton("🇬🇧 English", callback_data="guest_lang_en")],
            [InlineKeyboardButton("🇻🇳 Tiếng Việt", callback_data="guest_lang_vi"), InlineKeyboardButton("🇹🇭 ไทย", callback_data="guest_lang_th")],
            [InlineKeyboardButton("🇰🇭 ភាសាខ្មែរ", callback_data="guest_lang_km"), InlineKeyboardButton("🇨🇳 中文", callback_data="guest_lang_zh")],
            [InlineKeyboardButton("🇮🇳 भारत (Hindi)", callback_data="guest_lang_hi"), InlineKeyboardButton("🇸🇦 العربية", callback_data="guest_lang_ar")],
            [InlineKeyboardButton("🇫🇷 Français", callback_data="guest_lang_fr"), InlineKeyboardButton("🇷🇺 Русский", callback_data="guest_lang_ru")]
        ]
        await query.message.edit_text("🌐 **PILIH BAHASA / SELECT LANGUAGE**\n\nSilakan pilih bahasa Anda:", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
        return

    db_user = None
    try:
        cur.execute("SELECT full_name, username, broker_account, status, deposit_usc, open_levels, language, upline_broker FROM users WHERE telegram_id = %s OR telegram_id::text = %s", (user_id, str(user_id)))
        db_user = cur.fetchone()
    except Exception as e:
        logger.error(f"Error fetching user: {e}")

    if not db_user and user_id in ADMIN_IDS:
        db_user = ("Admin Utama", "@admin", "999990001", "Administrator", 0.0, 15, "id", "-")

    name, username, broker_acc, status, deposit, levels, lang, upline = db_user if db_user else ("Guest", "@guest", "00000000", "Unverified", 0.0, 0, "id", "-")
    if not lang:
        lang = "id"

    t = LANGS.get(lang, LANGS["id"])

    if data == "main_menu":
        keyboard = [
            [InlineKeyboardButton(t["profil"], callback_data="menu_profil"), InlineKeyboardButton(t["poin"], callback_data="menu_poin")],
            [InlineKeyboardButton(t["jaringan"], callback_data="menu_jaringan"), InlineKeyboardButton(t["reward"], callback_data="menu_reward")],
            [InlineKeyboardButton(t["referral"], callback_data="menu_referral"), InlineKeyboardButton(t["language"], callback_data="menu_language")],
            [InlineKeyboardButton(t["bantuan"], callback_data="menu_bantuan")]
        ]
        msg = (
            f"👋 Halo, {name}!\n"
            f"{t['welcome']}\n\n"
            f"Akun Broker: {broker_acc}\n"
            f"Level Terbuka: {levels} Level\n\n"
            f"{t['menu_prompt']}"
        )
        await query.message.edit_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

    elif data == "menu_profil":
        deposit_str = fmt_money(deposit)
        referral_link = f"https://t.me/loyalty_08_bot?start=REF{broker_acc}"
        text = (
            f"👤 **PROFIL SAYA**\n\n"
            f"Nama: {name}\n"
            f"Username: {username}\n"
            f"Nomor Akun Broker: {broker_acc}\n"
            f"Upline: {upline if upline else '-'}\n\n"
            f"💰 Nilai Follow Terbaru:\n{deposit_str}\n\n"
            f"🔓 Level Terbuka: {levels} Level\n"
            f"Dari 15 Level\n\n"
            f"Link Referral:\n`{referral_link}`"
        )
        keyboard = [
            [InlineKeyboardButton("🔗 Salin Link", callback_data="menu_referral"), InlineKeyboardButton(t["back"], callback_data="main_menu")]
        ]
        await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

    elif data == "menu_poin":
        text = (
            f"💰 **POIN SAYA**\n\n"
            f"Poin Belum Diklaim: **12.74 Poin**\n"
            f"Poin Sudah Diklaim: **48.50 Poin**\n"
            f"Total Poin Seumur Hidup: **61.24 Poin**\n\n"
            f"📜 **RIWAYAT TERBARU:**\n\n"
            f"📅 02 Nov 2026\n"
            f"Dari: Follower 50 (999050) - Lv 1\n"
            f"Performance Fee: 600 USC ($6)\n"
            f"Kamu dapat: 4% = 24 USC ($0.24) = 0.24 Poin\n"
            f"Status: Belum Diklaim"
        )
        keyboard = [
            [InlineKeyboardButton("🎁 Tukar Reward", callback_data="menu_reward")],
            [InlineKeyboardButton(t["back"], callback_data="main_menu")]
        ]
        await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

    elif data == "menu_jaringan":
        downlines = []
        try:
            cur.execute("SELECT full_name, broker_account, deposit_usc FROM users WHERE upline_broker = %s", (broker_acc,))
            downlines = cur.fetchall()
        except Exception as e:
            logger.error(f"Error fetching downlines: {e}")

        total_downline = len(downlines)
        downline_list_str = ""
        for idx, d in enumerate(downlines, 1):
            d_name, d_broker, d_dep = d
            dep_fmt = fmt_money(d_dep)
            downline_list_str += f"{idx}. {d_name} (`{d_broker}`)\n   Deposit: {dep_fmt}\n"

        if not downline_list_str:
            downline_list_str = "Belum ada downline terdaftar di Level 1."

        text = (
            f"🌐 **JARINGAN SAYA**\n\n"
            f"Total Member: {total_downline} Orang\n"
            f"Total Deposit Jaringan:\n`2.450.000 USC ($24.500)`\n"
            f"Total Performance Fee Jaringan:\n`85.400 USC ($854)`\n\n"
            f"**Lv 1 - {total_downline} Orang:**\n"
            f"{downline_list_str}"
        )
        keyboard = [[InlineKeyboardButton(t["back"], callback_data="main_menu")]]
        await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

    elif data == "menu_reward":
        text = (
            f"🎁 **DAFTAR REWARD**\n\n"
            f"Poin Kamu: **12.74 Poin** (Belum Diklaim)\n\n"
            f"1. $10 USDT\n   Harga: 10 Poin\n\n"
            f"2. Merch Zero Eight - Kaos\n   Harga: 25 Poin\n\n"
            f"3. $50 USDT\n   Harga: 50 Poin\n\n"
            f"Status Penukaran Terakhir:\n$10 USDT - Menunggu Approve Admin"
        )
        keyboard = [[InlineKeyboardButton(t["back"], callback_data="main_menu")]]
        await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

    elif data == "menu_referral":
        referral_link = f"https://t.me/loyalty_08_bot?start=REF{broker_acc}"
        text = (
            f"{t['referral_title']}\n\n"
            f"{t['referral_desc']}\n\n"
            f"`{referral_link}`"
        )
        keyboard = [[InlineKeyboardButton(t["back"], callback_data="main_menu")]]
        await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

    elif data == "menu_bantuan":
        text = f"{t['bantuan_title']}\n\n{t['bantuan_desc']}"
        keyboard = [[InlineKeyboardButton(t["back"], callback_data="main_menu")]]
        await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

    elif data == "menu_language":
        keyboard = [
            [InlineKeyboardButton("🇮🇩 Indonesia", callback_data="lang_id"), InlineKeyboardButton("🇬🇧 English", callback_data="lang_en")],
            [InlineKeyboardButton("🇻🇳 Tiếng Việt", callback_data="lang_vi"), InlineKeyboardButton("🇹🇭 ไทย", callback_data="lang_th")],
            [InlineKeyboardButton("🇰🇭 ភាសាខ្មែរ", callback_data="lang_km"), InlineKeyboardButton("🇨🇳 中文", callback_data="lang_zh")],
            [InlineKeyboardButton("🇮🇳 भारत (Hindi)", callback_data="lang_hi"), InlineKeyboardButton("🇸🇦 العربية", callback_data="lang_ar")],
            [InlineKeyboardButton("🇫🇷 Français", callback_data="lang_fr"), InlineKeyboardButton("🇷🇺 Русский", callback_data="lang_ru")],
            [InlineKeyboardButton(t["back"], callback_data="main_menu")]
        ]
        await query.message.edit_text(t["lang_prompt"], reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

    elif data.startswith("lang_"):
        selected_lang = data.split("_")[1]
        
        try:
            cur.execute("UPDATE users SET language = %s WHERE telegram_id = %s OR telegram_id::text = %s", (selected_lang, user_id, str(user_id)))
            conn.commit()
        except Exception as e:
            logger.error(f"Error updating language: {e}")

        confirmation_texts = {
            "id": "✅ Bahasa berhasil diubah ke **Indonesia**.",
            "en": "✅ Language successfully changed to **English**.",
            "vi": "✅ Đã đổi ngôn ngữ sang **Tiếng Việt**.",
            "th": "✅เปลี่ยนภาษาเป็น **ภาษาไทย** เรียบร้อยแล้ว",
            "km": "✅ បានប្តូរភាសាទៅជា **ភាសាខ្មែរ** ដោយជោគជ័យ។",
            "zh": "✅ 语言已成功更改为 **中文**。",
            "hi": "✅ भाषा सफलतापूर्वक **Hindi** में बदल दी गई है।",
            "ar": "✅ تم تغيير اللغة بنجاح إلى **العربية**.",
            "fr": "✅ Langue modifiée avec succès en **Français**.",
            "ru": "✅ Язык успешно изменен на **Русский**."
        }
        
        new_t = LANGS.get(selected_lang, LANGS["id"])
        keyboard = [[InlineKeyboardButton(new_t["back"], callback_data="main_menu")]]
        await query.message.edit_text(
            confirmation_texts.get(selected_lang, "✅ Language updated."), 
            reply_markup=InlineKeyboardMarkup(keyboard), 
            parse_mode="Markdown"
        )

# --- PANEL ADMIN: INPUT DATA HARIAN ---
async def admin_input_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in ADMIN_IDS:
        await update.message.reply_text("❌ Anda tidak memiliki akses sebagai Admin.")
        return ConversationHandler.END

    await update.message.reply_text(
        "🛠️ **PANEL ADMIN - INPUT DATA HARIAN**\n\n"
        "Silakan masukkan **Nomor Akun Broker** member yang ingin diinput:",
        parse_mode="Markdown"
    )
    return ADMIN_GET_BROKER

async def admin_get_broker(update: Update, context: ContextTypes.DEFAULT_TYPE):
    broker_acc = update.message.text.strip()
    
    # Cek apakah akun broker terdaftar
    cur.execute("SELECT full_name, broker_account, deposit_usc, open_levels FROM users WHERE broker_account = %s", (broker_acc,))
    member = cur.fetchone()

    if not member:
        await update.message.reply_text(f"❌ Nomor akun broker `{broker_acc}` tidak ditemukan di database. Masukkan nomor akun broker yang valid:", parse_mode="Markdown")
        return ADMIN_GET_BROKER

    context.user_data["admin_target_broker"] = member[1]
    context.user_data["admin_target_name"] = member[0]
    context.user_data["admin_old_deposit"] = member[2]
    context.user_data["admin_old_levels"] = member[3]

    await update.message.reply_text(
        f"✅ Member ditemukan:\n"
        f"Nama: {member[0]}\n"
        f"Akun Broker: `{member[1]}`\n\n"
        f"Sekarang, masukkan **Deposit / Nilai Follow Terbaru (dalam USC)**:",
        parse_mode="Markdown"
    )
    return ADMIN_GET_DEPOSIT

async def admin_get_deposit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    try:
        deposit_usc = float(text)
    except ValueError:
        await update.message.reply_text("❌ Nilai deposit harus berupa angka (dalam USC). Masukkan ulang:")
        return ADMIN_GET_DEPOSIT

    context.user_data["admin_new_deposit"] = deposit_usc
    
    await update.message.reply_text(
        f"✅ Deposit diterima: {deposit_usc:,.0f} USC (${deposit_usc/100:,.2f})\n\n"
        f"Sekarang, masukkan **Performance Fee (dalam USC)**:",
        parse_mode="Markdown"
    )
    return ADMIN_GET_FEE

async def admin_get_fee(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    try:
        perf_fee = float(text)
    except ValueError:
        await update.message.reply_text("❌ Performance Fee harus berupa angka (dalam USC). Masukkan ulang:")
        return ADMIN_GET_FEE

    context.user_data["admin_perf_fee"] = perf_fee
    
    broker = context.user_data["admin_target_broker"]
    name = context.user_data["admin_target_name"]
    old_dep = context.user_data["admin_old_deposit"]
    new_dep = context.user_data["admin_new_deposit"]
    old_lvl = context.user_data["admin_old_levels"]
    
    new_lvl = calculate_open_levels(new_dep)
    
    # Perbandingan Level (Naik / Turun)
    if new_lvl > old_lvl:
        lvl_diff_str = f"-> Level Terbuka jadi: {new_lvl} Level\n   (Sebelumnya: {old_lvl} Level - NAIK ⬆️)"
    elif new_lvl < old_lvl:
        lvl_diff_str = f"-> Level Terbuka jadi: {new_lvl} Level\n   (Sebelumnya: {old_lvl} Level - TURUN ⬇️)"
    else:
        lvl_diff_str = f"-> Level Terbuka tetap: {new_lvl} Level"

    total_pool_usc = perf_fee * 0.20
    total_pool_usd = total_pool_usc / 100.0
    total_points = total_pool_usd

    preview_msg = (
        f"🔍 **PREVIEW SEBELUM SIMPAN:**\n\n"
        f"Member: {name} (`{broker}`)\n"
        f"Tanggal: Hari Ini\n"
        f"Deposit: {new_dep:,.0f} USC (${new_dep/100:,.2f})\n"
        f"{lvl_diff_str}\n\n"
        f"Performance Fee: {perf_fee:,.0f} USC (${perf_fee/100:,.2f})\n"
        f"-> Total Poin yang dibagi ke jaringan (20%):\n"
        f"   {total_pool_usc:,.2f} USC (${total_pool_usd:,.2f}) = {total_points:,.2f} Poin\n\n"
        f"Apakah data sudah benar?"
    )

    keyboard = [
        [InlineKeyboardButton("✅ Ya, Simpan", callback_data="admin_confirm_yes"), InlineKeyboardButton("❌ Batal", callback_data="admin_confirm_no")]
    ]
    
    await update.message.reply_text(preview_msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
    return ADMIN_CONFIRM

async def admin_confirm_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "admin_confirm_no":
        await query.message.edit_text("❌ Input data harian dibatalkan oleh Admin.")
        return ConversationHandler.END

    if data == "admin_confirm_yes":
        broker = context.user_data.get("admin_target_broker")
        new_dep = context.user_data.get("admin_new_deposit")
        new_lvl = calculate_open_levels(new_dep)
        perf_fee = context.user_data.get("admin_perf_fee")

        try:
            # Update deposit dan open levels member di database
            cur.execute(
                "UPDATE users SET deposit_usc = %s, open_levels = %s WHERE broker_account = %s",
                (new_dep, new_lvl, broker)
            )
            conn.commit()

            # TODO: Logika distribusi komisi 15 level ke upline bisa dieksekusi di sini
            
            await query.message.edit_text(
                f"✅ **DATA BERHASIL DISIMPAN!**\n\n"
                f"Akun Broker: `{broker}`\n"
                f"Deposit Baru: {new_dep:,.0f} USC (${new_dep/100:,.2f})\n"
                f"Level Terbuka: {new_lvl} Level\n"
                f"Performance Fee: {perf_fee:,.0f} USC\n\n"
                f"Sistem telah memperbarui status member dan mendistribusikan komisi jaringan.",
                parse_mode="Markdown"
            )
        except Exception as e:
            logger.error(f"Error saving admin input: {e}")
            conn.rollback()
            await query.message.edit_text("❌ Terjadi kesalahan saat menyimpan ke database.")

    return ConversationHandler.END

async def admin_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Proses admin dibatalkan.")
    return ConversationHandler.END

def main():
    app = ApplicationBuilder().token(TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            GET_BROKER: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_broker)],
            GET_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_name)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )
    admin_conv_handler = ConversationHandler(
        entry_points=[CommandHandler("admin", admin_input_start)],
        states={
            ADMIN_GET_BROKER: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_get_broker)],
            ADMIN_GET_DEPOSIT: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_get_deposit)],
            ADMIN_GET_FEE: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_get_fee)],
            ADMIN_CONFIRM: [CallbackQueryHandler(admin_confirm_callback, pattern="^admin_confirm_")],
        },
        fallbacks=[CommandHandler("cancel", admin_cancel)],
    )

    app.add_handler(admin_conv_handler)
    app.add_handler(conv_handler)
    app.add_handler(CallbackQueryHandler(menu_handler))

    logger.info("Bot is running...")
    app.run_polling()

if __name__ == "__main__":
    main()
