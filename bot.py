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

# Konfigurasi Database (Supabase PostgreSQL) & Bot Token dari Environment Variables
DATABASE_URL = os.getenv("DATABASE_URL")
TOKEN = os.getenv("BOT_TOKEN")

# Admin Utama (Telegram ID)
ADMIN_IDS = [420150137]

# Koneksi Database
conn = psycopg2.connect(DATABASE_URL)
cur = conn.cursor()

# Tahapan Conversation untuk Pendaftaran
GET_BROKER, GET_NAME = range(2)

# Kamus Terjemahan Multibahasa (Termasuk Pesan Akses Tanpa Referral)
LANGS = {
    "id": {
        "welcome": "🌟 **SELAMAT DATANG DI ZERO EIGHT LOYALTY BOT**",
        "menu_prompt": "Silakan pilih menu di bawah ini:",
        "profil": "👤 Profil Saya", "poin": "💰 Poin Saya", "jaringan": "🌐 Jaringan Saya", 
        "reward": "🎁 Daftar Reward", "referral": "🔗 Link Referral Saya", "language": "🌐 Ganti Bahasa", "bantuan": "❓ Bantuan",
        "profil_title": "👤 **PROFIL SAYA**", "name": "Nama", "broker": "Akun Broker", "status": "Status", "deposit": "Deposit USC", "levels": "Level Terbuka",
        "poin_title": "💰 **POIN SAYA**", "poin_desc": "Total Poin Anda: **0 Poin**",
        "jaringan_title": "🌐 **JARINGAN SAYA**", "jaringan_desc": "Fitur jaringan downline sedang dalam pengembangan.",
        "reward_title": "🎁 **DAFTAR REWARD**", "reward_desc": "Belum ada reward yang tersedia saat ini. Stay tuned!",
        "referral_title": "🔗 **LINK REFERRAL ANDA**", "referral_desc": "Bagikan link di bawah ini ke teman atau partner Anda untuk bergabung ke jaringan:",
        "bantuan_title": "❓ **BANTUAN**", "bantuan_desc": "Silakan hubungi Admin jika Anda mengalami kendala pada akun atau transaksi.",
        "lang_prompt": "🌐 **PILIH BAHASA / SELECT LANGUAGE**\n\nSilakan pilih bahasa Anda:",
        "back": "🔙 Menu Utama",
        "unauthorized_msg": (
            "👋 **Selamat Datang di Zero Eight Bot**\n\n"
            "🤖 Zero Eight Bot adalah sistem otomatis untuk menghitung, mencatat, dan memantau poin loyalitas anggota Komunitas ZeroEight.\n\n"
            "⚠️ **PERHATIAN**\n\n"
            "Untuk menjaga validitas data dan poin komunitas, seluruh fitur bot hanya dapat digunakan oleh anggota yang telah melakukan registrasi melalui link referral resmi ZeroEight.\n\n"
            "🔒 Jika Anda belum terdaftar, silakan lakukan registrasi terlebih dahulu menggunakan referral yang valid.\n\n"
            "✅ Setelah akun Anda terverifikasi, Anda dapat:\n"
            "• Melihat total poin loyalitas\n"
            "• Mengecek riwayat perolehan poin\n"
            "• Mendapatkan informasi program dan reward terbaru"
        )
    },
    "en": {
        "welcome": "🌟 **WELCOME TO ZERO EIGHT LOYALTY BOT**",
        "menu_prompt": "Please select an option below:",
        "profil": "👤 My Profile", "poin": "💰 My Points", "jaringan": "🌐 My Network", 
        "reward": "🎁 Rewards List", "referral": "🔗 My Referral Link", "language": "🌐 Change Language", "bantuan": "❓ Support",
        "profil_title": "👤 **MY PROFILE**", "name": "Name", "broker": "Broker Account", "status": "Status", "deposit": "Deposit USC", "levels": "Unlocked Levels",
        "poin_title": "💰 **MY POINTS**", "poin_desc": "Your Total Points: **0 Points**",
        "jaringan_title": "🌐 **MY NETWORK**", "jaringan_desc": "Downline network feature is under development.",
        "reward_title": "🎁 **REWARDS LIST**", "reward_desc": "No rewards available at the moment. Stay tuned!",
        "referral_title": "🔗 **MY REFERRAL LINK**", "referral_desc": "Share the link below with your friends or partners to join the network:",
        "bantuan_title": "❓ **SUPPORT**", "bantuan_desc": "Please contact Admin if you encounter any account or transaction issues.",
        "lang_prompt": "🌐 **SELECT LANGUAGE**\n\nPlease choose your preferred language:",
        "back": "🔙 Main Menu",
        "unauthorized_msg": (
            "👋 **Welcome to Zero Eight Bot**\n\n"
            "🤖 Zero Eight Bot is an automated system to calculate, record, and monitor loyalty points for ZeroEight Community members.\n\n"
            "⚠️ **ATTENTION**\n\n"
            "To maintain data and community points validity, all bot features can only be used by members who have registered through an official ZeroEight referral link.\n\n"
            "🔒 If you are not registered, please register first using a valid referral.\n\n"
            "✅ Once your account is verified, you can:\n"
            "• View total loyalty points\n"
            "• Check points acquisition history\n"
            "• Get the latest program and reward information"
        )
    }
}

# --- Command /start & Sistem Pendaftaran ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = user.id

    # Cek apakah user sudah terdaftar di database
    cur.execute("SELECT broker_account, full_name, language FROM users WHERE telegram_id = %s OR telegram_id::text = %s", (user_id, str(user_id)))
    db_user = cur.fetchone()

    # Jika sudah terdaftar atau merupakan Admin Utama, langsung tampilkan menu utama
    if db_user or user_id in ADMIN_IDS:
        lang = db_user[2] if db_user and len(db_user) > 2 and db_user[2] else "id"
        t = LANGS.get(lang, LANGS["id"])
        
        keyboard = [
            [InlineKeyboardButton(t["profil"], callback_data="menu_profil"), InlineKeyboardButton(t["poin"], callback_data="menu_poin")],
            [InlineKeyboardButton(t["jaringan"], callback_data="menu_jaringan"), InlineKeyboardButton(t["reward"], callback_data="menu_reward")],
            [InlineKeyboardButton(t["referral"], callback_data="menu_referral"), InlineKeyboardButton(t["language"], callback_data="menu_language")],
            [InlineKeyboardButton(t["bantuan"], callback_data="menu_bantuan")]
        ]
        await update.message.reply_text(f"{t['welcome']}\n\n{t['menu_prompt']}", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
        return ConversationHandler.END

    # Cek parameter referral dari link start (contoh: /start REF999990001)
    args = context.args
    if not args or not args[0].startswith("REF"):
        # Jika akses langsung tanpa referral dan bukan admin, tampilkan pesan informasi umum + tombol ganti bahasa
        keyboard = [
            [InlineKeyboardButton("🌐 Ganti Bahasa / Change Language", callback_data="guest_language")]
        ]
        await update.message.reply_text(
            LANGS["id"]["unauthorized_msg"], 
            reply_markup=InlineKeyboardMarkup(keyboard), 
            parse_mode="Markdown"
        )
        return ConversationHandler.END

    # Ambil upline broker account dari parameter referral
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
    
    # Validasi ketat: Akun broker harus berupa angka sepenuhnya
    if not text.isdigit():
        await update.message.reply_text("❌ Nomor akun broker harus berupa **angka** saja. Silakan masukkan ulang nomor akun broker Anda:")
        return GET_BROKER

    context.user_data["broker_account"] = text
    await update.message.reply_text("✅ Akun broker diterima.\n\nSekarang, silakan masukkan **Nama Lengkap** Anda:")
    return GET_NAME

async def receive_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    name = update.message.text.strip()
    user_id = update.effective_user.id
    broker_acc = context.user_data.get("broker_account")

    # Simpan data registrasi baru ke Supabase
    try:
        cur.execute(
            "INSERT INTO users (telegram_id, full_name, broker_account, status, deposit_usc, open_levels, language) VALUES (%s, %s, %s, %s, %s, %s, %s)",
            (user_id, name, broker_acc, "Verified", 0, 0, "id")
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
        f"Nama: {name}\n\n"
        f"Silakan pilih menu di bawah:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Pendaftaran dibatalkan.")
    return ConversationHandler.END


# --- Menu Handler Interaktif & Multibahasa ---
async def menu_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    user_id = query.from_user.id

    # Handle pilihan bahasa untuk Guest (pengguna tanpa referral)
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

    # Ambil data user terdaftar dari database
    db_user = None
    try:
        cur.execute("SELECT full_name, broker_account, status, deposit_usc, open_levels, language FROM users WHERE telegram_id = %s OR telegram_id::text = %s", (user_id, str(user_id)))
        db_user = cur.fetchone()
    except Exception as e:
        logger.error(f"Error fetching user: {e}")

    # Fallback data jika admin utama
    if not db_user and user_id in ADMIN_IDS:
        db_user = ("Admin Utama", "999990001", "Administrator", 0, 0, "id")

    name, broker_acc, status, deposit, levels, lang = db_user if db_user else ("Guest", "00000000", "Unverified", 0, 0, "id")
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
        await query.message.edit_text(f"{t['welcome']}\n\n{t['menu_prompt']}", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

    elif data == "menu_profil":
        text = (
            f"{t['profil_title']}\n\n"
            f"{t['name']}: {name}\n"
            f"{t['broker']}: {broker_acc}\n"
            f"{t['status']}: {status}\n"
            f"{t['deposit']}: {deposit}\n"
            f"{t['levels']}: {levels} Level"
        )
        keyboard = [[InlineKeyboardButton(t["back"], callback_data="main_menu")]]
        await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

    elif data == "menu_poin":
        text = f"{t['poin_title']}\n\n{t['poin_desc']}"
        keyboard = [[InlineKeyboardButton(t["back"], callback_data="main_menu")]]
        await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

    elif data == "menu_jaringan":
        text = f"{t['jaringan_title']}\n\n{t['jaringan_desc']}"
        keyboard = [[InlineKeyboardButton(t["back"], callback_data="main_menu")]]
        await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

    elif data == "menu_reward":
        text = f"{t['reward_title']}\n\n{t['reward_desc']}"
        keyboard = [[InlineKeyboardButton(t["back"], callback_data="main_menu")]]
        await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

    elif data == "menu_referral":
        # Link referral menggunakan nomor akun broker pengguna yang benar
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

    app.add_handler(conv_handler)
    app.add_handler(CallbackQueryHandler(menu_handler))

    logger.info("Bot is running...")
    app.run_polling()

if __name__ == "__main__":
    main()
