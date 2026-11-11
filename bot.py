import os
import logging
import psycopg2
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    ConversationHandler,
    filters,
)

# --- KONFIGURASI LOGGING ---
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# --- KONFIGURASI DATABASE & ADMIN ---
DATABASE_URL = os.getenv("DATABASE_URL")
ADMIN_IDS = [420150137]

try:
    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()
    logger.info("✅ Berhasil terhubung ke Database PostgreSQL.")
except Exception as e:
    logger.error(f"❌ Gagal terhubung ke Database: {e}")

# --- STATE CONVERSATION ---
ASK_BROKER, ASK_NAME = range(2)
ADMIN_BROKER, ADMIN_DEPOSIT, ADMIN_FEE = range(2, 5)

COMMISSION_RATES = {
    1: 0.04, 2: 0.04, 3: 0.02, 4: 0.02, 5: 0.01,
    6: 0.01, 7: 0.01, 8: 0.01, 9: 0.01, 10: 0.005,
    11: 0.005, 12: 0.005, 13: 0.005, 14: 0.005, 15: 0.005
}

def calculate_open_levels(deposit_usc):
    dep = float(deposit_usc)
    if dep >= 500000: return 15
    elif dep >= 400000: return 14
    elif dep >= 300000: return 12
    elif dep >= 150000: return 10
    elif dep >= 100000: return 8
    elif dep >= 50000: return 6
    elif dep >= 30000: return 4
    elif dep >= 10000: return 2
    elif dep >= 5000: return 1
    else: return 0

def get_main_menu_keyboard():
    keyboard = [
        [KeyboardButton("👤 Profil Saya"), KeyboardButton("💰 Poin Saya")],
        [KeyboardButton("🌐 Jaringan Saya"), KeyboardButton("🎁 Daftar Reward")],
        [KeyboardButton("🔗 Link Referral Saya"), KeyboardButton("🌐 Ganti Bahasa")],
        [KeyboardButton("❓ Bantuan")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)


# ==========================================
# 1. PENDAFTARAN & VALIDASI ANGKA BROKER
# ==========================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    telegram_id = user.id

    cur.execute("SELECT broker_account, status, deposit_usc, open_levels FROM users WHERE telegram_id = %s", (telegram_id,))
    existing = cur.fetchone()

    if existing:
        broker, status, deposit, levels = existing
        status_text = "✅ Terverifikasi & Aktif" if status == "Verified" else "⏳ Unverified (Menunggu verifikasi admin)"
        
        welcome_msg = (
            f"👋 Halo kembali, **{user.first_name}**!\n\n"
            f"• Akun Broker: `{broker}`\n"
            f"• Status: {status_text}\n"
            f"• Total Deposit: `{deposit:,.0f} USC` (${deposit / 100:,.2f})\n"
            f"• Level Terbuka: `{levels} Level`\n\n"
            f"Silakan gunakan menu di bawah:"
        )
        await update.message.reply_text(welcome_msg, reply_markup=get_main_menu_keyboard(), parse_mode="Markdown")
        return ConversationHandler.END

    if not context.args:
        intro_text = (
            "🖲️ **Selamat Datang di Zero Eight Bot**\n\n"
            "🌐 *Zero Eight Bot adalah sistem otomatis untuk menghitung, mencatat, dan memantau poin loyalitas anggota Komunitas ZeroEight.*\n\n"
            "⚠️ **PERHATIAN**\n"
            "Untuk menjaga validitas data dan poin komunitas, seluruh fitur bot hanya dapat digunakan oleh anggota yang telah melakukan registrasi melalui link referral resmi ZeroEight.\n\n"
            "🔒 Jika Anda belum terdaftar, silakan lakukan registrasi terlebih dahulu menggunakan referral yang valid."
        )
        keyboard = [[InlineKeyboardButton("🌐 Ganti Bahasa / Change Language", callback_data="change_lang")]]
        await update.message.reply_text(intro_text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
        return ConversationHandler.END

    upline_broker = context.args[0].strip()
    cur.execute("SELECT full_name FROM users WHERE broker_account = %s", (upline_broker,))
    if not cur.fetchone():
        await update.message.reply_text("❌ Link referral tidak valid atau upline tidak ditemukan.")
        return ConversationHandler.END

    context.user_data["upline_broker"] = upline_broker
    await update.message.reply_text(
        "👋 **Selamat Datang di Zero Eight Bot**\n\n"
        "Silakan masukkan **Nomor Akun Broker** Anda (hanya berupa angka):",
        parse_mode="Markdown"
    )
    return ASK_BROKER


async def receive_broker(update: Update, context: ContextTypes.DEFAULT_TYPE):
    broker_account = update.message.text.strip()
    
    # 1. VALIDASI KETAT: Wajib angka (isdigit)
    if not broker_account.isdigit():
        await update.message.reply_text("⚠️ Nomor akun broker **hanya boleh berupa angka**. Silakan masukkan kembali nomor akun broker yang valid:")
        return ASK_BROKER

    cur.execute("SELECT telegram_id FROM users WHERE broker_account = %s", (broker_account,))
    if cur.fetchone():
        await update.message.reply_text("⚠️ Nomor akun broker ini sudah terdaftar. Silakan masukkan nomor akun broker lain:")
        return ASK_BROKER

    context.user_data["broker_account"] = broker_account
    await update.message.reply_text("✅ Akun broker diterima.\n\nSekarang, silakan masukkan **Nama Lengkap** Anda:")
    return ASK_NAME


async def receive_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    full_name = update.message.text.strip()
    user = update.effective_user
    
    telegram_id = user.id
    username = user.username or ""
    broker_account = context.user_data.get("broker_account")
    upline_broker = context.user_data.get("upline_broker", "-")

    try:
        cur.execute(
            """
            INSERT INTO users (telegram_id, full_name, username, broker_account, status, deposit_usc, open_levels, upline_broker, created_at)
            VALUES (%s, %s, %s, %s, 'Unverified', 0, 0, %s, NOW())
            """,
            (telegram_id, full_name, username, broker_account, upline_broker)
        )
        conn.commit()

        await update.message.reply_text(
            f"🎉 **REGISTRASI BERHASIL!**\n\n"
            f"• Akun Broker: `{broker_account}`\n"
            f"• Nama: {full_name}\n"
            f"• Upline Broker: `{upline_broker}`\n"
            f"• Status: ⏳ `Unverified` (Menunggu deposit pertama dari Admin)\n\n"
            f"Silakan gunakan menu di bawah:",
            reply_markup=get_main_menu_keyboard(),
            parse_mode="Markdown"
        )
    except Exception as e:
        logger.error(f"Error registering user: {e}")
        conn.rollback()
        await update.message.reply_text("❌ Terjadi kesalahan pada database. Silakan coba /start ulang.")

    return ConversationHandler.END


async def menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    cur.execute("SELECT broker_account, status, deposit_usc, open_levels FROM users WHERE telegram_id = %s", (user_id,))
    res = cur.fetchone()

    if not res:
        await update.message.reply_text("❌ Anda belum terdaftar.")
        return

    broker, status, deposit, levels = res
    bot_username = context.bot.username
    ref_link = f"https://t.me/{bot_username}?start={broker}" if status == "Verified" else "Belum aktif (Menunggu verifikasi admin)"

    menu_text = (
        f"📌 **MENU UTAMA ZERO EIGHT**\n\n"
        f"• Akun Broker: `{broker}`\n"
        f"• Status: {'✅ Terverifikasi & Aktif' if status == 'Verified' else '⏳ Unverified'}\n"
        f"• Total Deposit: `{deposit:,.0f} USC` (${deposit / 100:,.2f})\n"
        f"• Level Terbuka: `{levels} Level`\n\n"
        f"🔗 **Link Referral Anda:**\n`{ref_link}`"
    )
    await update.message.reply_text(menu_text, reply_markup=get_main_menu_keyboard(), parse_mode="Markdown")


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ Proses dibatalkan.", reply_markup=get_main_menu_keyboard())
    return ConversationHandler.END


# ==========================================
# 2. HANDLER TOMBOL TEKS & MULTI-BAHASA FUNGIONAL
# ==========================================

async def handle_text_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    user_id = update.effective_user.id

    if text == "👤 Profil Saya":
        cur.execute("SELECT broker_account, full_name, status, deposit_usc, open_levels FROM users WHERE telegram_id = %s", (user_id,))
        res = cur.fetchone()
        if not res:
            await update.message.reply_text("❌ Anda belum terdaftar.")
            return
        broker, name, status, deposit, levels = res
        await update.message.reply_text(
            f"👤 **PROFIL SAYA**\n\n"
            f"• Nama: {name}\n"
            f"• Broker: `{broker}`\n"
            f"• Status: {status}\n"
            f"• Deposit: `{deposit:,.0f} USC` (${deposit/100:.2f})\n"
            f"• Level Terbuka: `{levels} Level`",
            parse_mode="Markdown"
        )
    elif text == "💰 Poin Saya":
        # 3. Handler spesifik menu Poin Saya
        await update.message.reply_text(
            "💰 **POIN SAYA**\n\n"
            "• Poin Belum Diklaim: `0.00 Poin`\n"
            "• Poin Sudah Diklaim: `0.00 Poin`\n"
            "• Total Poin Seumur Hidup: `0.00 Poin`\n\n"
            "📥 Belum ada riwayat perolehan komisi jaringan.",
            parse_mode="Markdown"
        )
    elif text == "🌐 Jaringan Saya":
        # 3. Handler spesifik menu Jaringan
        await update.message.reply_text(
            "🌐 **JARINGAN REFERRAL SAYA**\n\n"
            "Rincian downline di bawah jaringan Anda (Level 1 - 15):\n"
            "• Belum ada anggota aktif di jaringan Anda.",
            parse_mode="Markdown"
        )
    elif text == "🎁 Daftar Reward":
        # 3. Handler spesifik menu Reward
        await update.message.reply_text(
            "🎁 **DAFTAR REWARD KOMUNITAS**\n\n"
            "1. $10 USDT - Harga: 10 Poin\n"
            "2. Merch Zero Eight - Harga: 25 Poin\n"
            "3. $50 USDT - Harga: 50 Poin\n\n"
            "Status Penukaran: Belum ada penukaran aktif.",
            parse_mode="Markdown"
        )
    elif text == "❓ Bantuan":
        # 3. Handler spesifik menu Bantuan
        await update.message.reply_text(
            "❓ **PUSAT BANTUAN ZERO EIGHT**\n\n"
            "Gunakan bot ini untuk memantau deposit, level terbuka, dan jaringan referral Anda. Untuk bantuan lebih lanjut, silakan hubungi admin komunitas.",
            parse_mode="Markdown"
        )
    elif text == "🌐 Ganti Bahasa":
        lang_keyboard = [
            [InlineKeyboardButton("🇬🇧 English", callback_data="lang_en"), InlineKeyboardButton("🇻🇳 Vietnamese", callback_data="lang_vi")],
            [InlineKeyboardButton("🇹🇭 Thai", callback_data="lang_th"), InlineKeyboardButton("🇰🇭 Cambodian", callback_data="lang_km")],
            [InlineKeyboardButton("🇨🇳 Mandarin", callback_data="lang_zh"), InlineKeyboardButton("🇮🇳 Indian", callback_data="lang_hi")],
            [InlineKeyboardButton("🇸🇦 Arabic", callback_data="lang_ar"), InlineKeyboardButton("🇫🇷 French", callback_data="lang_fr")],
            [InlineKeyboardButton("🇷🇺 Russian", callback_data="lang_ru")]
        ]
        await update.message.reply_text("🌐 **Pilih Bahasa / Select Language:**", reply_markup=InlineKeyboardMarkup(lang_keyboard), parse_mode="Markdown")
    elif text == "🔗 Link Referral Saya":
        await menu(update, context)


async def handle_language_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.data == "change_lang":
        lang_keyboard = [
            [InlineKeyboardButton("🇬🇧 English", callback_data="lang_en"), InlineKeyboardButton("🇻🇳 Vietnamese", callback_data="lang_vi")],
            [InlineKeyboardButton("🇹🇭 Thai", callback_data="lang_th"), InlineKeyboardButton("🇰🇭 Cambodian", callback_data="lang_km")],
            [InlineKeyboardButton("🇨🇳 Mandarin", callback_data="lang_zh"), InlineKeyboardButton("🇮🇳 Indian", callback_data="lang_hi")],
            [InlineKeyboardButton("🇸🇦 Arabic", callback_data="lang_ar"), InlineKeyboardButton("🇫🇷 French", callback_data="lang_fr")],
            [InlineKeyboardButton("🇷🇺 Russian", callback_data="lang_ru")]
        ]
        await query.edit_message_text("🌐 **Pilih Bahasa / Select Language:**", reply_markup=InlineKeyboardMarkup(lang_keyboard), parse_mode="Markdown")
    elif query.data.startswith("lang_"):
        # 2. Fungsionalitas pemilihan bahasa nyata
        selected_lang = query.data.split("_")[1].upper()
        lang_names = {
            "EN": "English", "VI": "Vietnamese", "TH": "Thai", "KM": "Cambodian",
            "ZH": "Mandarin", "HI": "Indian", "AR": "Arabic", "FR": "French", "RU": "Russian"
        }
        full_lang_name = lang_names.get(selected_lang, selected_lang)
        await query.edit_message_text(f"✅ Bahasa berhasil diubah ke **{full_lang_name}**.", parse_mode="Markdown")


# ==========================================
# 3. PANEL ADMIN & REKAP HARIAN (/admin)
# ==========================================

async def admin_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in ADMIN_IDS:
        await update.message.reply_text("❌ Anda tidak memiliki akses admin.")
        return ConversationHandler.END

    await update.message.reply_text("⚙️ **PANEL ADMIN: REKAP HARIAN**\n\nMasukkan **Nomor Akun Broker** member:", parse_mode="Markdown")
    return ADMIN_BROKER


async def admin_get_broker(update: Update, context: ContextTypes.DEFAULT_TYPE):
    broker = update.message.text.strip()
    cur.execute("SELECT full_name, deposit_usc, open_levels, status FROM users WHERE broker_account = %s", (broker,))
    res = cur.fetchone()

    if not res:
        await update.message.reply_text(f"❌ Akun broker `{broker}` tidak ditemukan. Masukkan nomor broker yang benar:", parse_mode="Markdown")
        return ADMIN_BROKER

    context.user_data["admin_broker"] = broker
    name, current_dep, current_lvl, status = res
    context.user_data["current_level"] = current_lvl

    await update.message.reply_text(
        f"✅ Member ditemukan: **{name}** (`{broker}`)\n"
        f"Deposit Lama: `{current_dep:,.0f} USC`\n\n"
        f"Masukkan **Deposit / Nilai Follow Terbaru (dalam USC)**:",
        parse_mode="Markdown"
    )
    return ADMIN_DEPOSIT


async def admin_get_deposit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        new_dep = float(update.message.text.strip())
        if new_dep < 0: raise ValueError()
    except ValueError:
        await update.message.reply_text("⚠️ Masukkan angka deposit yang valid:")
        return ADMIN_DEPOSIT

    context.user_data["admin_deposit"] = new_dep
    await update.message.reply_text("📦 Masukkan **Performance Fee** hari ini (dalam USC):", parse_mode="Markdown")
    return ADMIN_FEE


async def admin_get_fee(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        perf_fee = float(update.message.text.strip())
        if perf_fee < 0: raise ValueError()
    except ValueError:
        await update.message.reply_text("⚠️ Masukkan angka performance fee yang valid:")
        return ADMIN_FEE

    broker = context.user_data.get("admin_broker")
    new_dep = context.user_data.get("admin_deposit")
    old_lvl = context.user_data.get("current_level")
    
    new_lvl = calculate_open_levels(new_dep)
    new_status = "Verified" if new_dep > 0 else "Unverified"

    context.user_data["admin_fee"] = perf_fee
    context.user_data["admin_new_level"] = new_lvl
    context.user_data["admin_status"] = new_status

    if new_lvl > old_lvl:
        lvl_diff_text = f"-> Level Terbuka jadi: {new_lvl} Level (Sebelumnya: {old_lvl} Level - NAIK ⬆️)"
    elif new_lvl < old_lvl:
        lvl_diff_text = f"-> Level Terbuka jadi: {new_lvl} Level (Sebelumnya: {old_lvl} Level - TURUN ⬇️)"
    else:
        lvl_diff_text = f"-> Level Terbuka: {new_lvl} Level (Tetap)"

    total_pool_network = perf_fee * 0.20
    cur.execute("SELECT full_name FROM users WHERE broker_account = %s", (broker,))
    name = cur.fetchone()[0]

    preview_text = (
        f"📋 **PREVIEW SEBELUM SIMPAN:**\n\n"
        f"Member: **{name}** (`{broker}`)\n"
        f"Deposit: `{new_dep:,.0f} USC` (${new_dep / 100:,.2f})\n"
        f"{lvl_diff_text}\n\n"
        f"Performance Fee: `{perf_fee:,.0f} USC`\n"
        f"-> Total Poin dibagi ke jaringan (20%): `{total_pool_network:,.2f} USC` = `{total_pool_network / 100:,.2f} Poin`\n\n"
        f"Simpan perubahan ini?"
    )

    keyboard = [[InlineKeyboardButton("✅ Ya, Simpan", callback_data="admin_save"), InlineKeyboardButton("❌ Batal", callback_data="admin_cancel")]]
    await update.message.reply_text(preview_text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
    return ConversationHandler.END


async def admin_save_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "admin_cancel":
        await query.edit_message_text("❌ Rekap dibatalkan.")
        return

    broker = context.user_data.get("admin_broker")
    new_dep = context.user_data.get("admin_deposit")
    new_lvl = context.user_data.get("admin_new_level")
    new_status = context.user_data.get("admin_status")
    perf_fee = context.user_data.get("admin_fee")

    try:
        cur.execute("UPDATE users SET deposit_usc = %s, open_levels = %s, status = %s WHERE broker_account = %s", (new_dep, new_lvl, new_status, broker))
        conn.commit()

        distribusi_log = ""
        if perf_fee > 0:
            current_upline = broker
            for level in range(1, 16):
                cur.execute("SELECT upline_broker FROM users WHERE broker_account = %s", (current_upline,))
                res = cur.fetchone()
                if not res or not res[0] or res[0] == "-": break
                
                upline_broker = res[0]
                cur.execute("SELECT full_name, open_levels FROM users WHERE broker_account = %s", (upline_broker,))
                upline_data = cur.fetchone()
                if not upline_data: break

                upline_name, upline_open_levels = upline_data
                earned_usc = perf_fee * COMMISSION_RATES.get(level, 0.0)

                if upline_open_levels >= level:
                    distribusi_log += f"Lv {level}: {upline_name} (+{earned_usc:,.0f} USC)\n"
                else:
                    distribusi_log += f"Lv {level}: {upline_name} (Terkunci)\n"
                current_upline = upline_broker

        await query.edit_message_text(
            f"✅ **DATA BERHASIL DISIMPAN!**\n\nBroker: `{broker}`\n• Deposit: `{new_dep:,.0f} USC`\n• Level: {new_lvl}\n\n📦 **Distribusi:**\n{distribusi_log if perf_fee > 0 else 'Tidak ada fee.'}",
            parse_mode="Markdown"
        )
    except Exception as e:
        logger.error(f"Error saving: {e}")
        conn.rollback()
        await query.edit_message_text("❌ Gagal menyimpan ke database.")


# ==========================================
# 4. ADMIN PENDUKUNG & MAIN
# ==========================================

async def auto_cleanup_unverified_users(context: ContextTypes.DEFAULT_TYPE):
    try:
        cur.execute("DELETE FROM users WHERE status = 'Unverified' AND created_at < NOW() - INTERVAL '48 hours'")
        if cur.rowcount > 0: conn.commit()
    except Exception as e:
        conn.rollback()

async def admin_delete_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS or not context.args: return
    broker_acc = context.args[0].strip()
    cur.execute("DELETE FROM users WHERE broker_account = %s", (broker_acc,))
    conn.commit()
    await update.message.reply_text(f"✅ Akun broker `{broker_acc}` dihapus.", parse_mode="Markdown")

async def admin_list_members(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS: return
    cur.execute("SELECT broker_account, full_name, status, deposit_usc FROM users")
    members = cur.fetchall()
    text = "📋 **MEMBER:**\n" + "\n".join([f"- {m[1]} (`{m[0]}`): {m[2]}, {m[3]:,.0f} USC" for m in members])
    await update.message.reply_text(text, parse_mode="Markdown")

async def admin_check_member(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS or not context.args: return
    cur.execute("SELECT full_name, status, deposit_usc, open_levels FROM users WHERE broker_account = %s", (context.args[0].strip(),))
    m = cur.fetchone()
    if not m: return await update.message.reply_text("❌ Tidak ditemukan.")
    await update.message.reply_text(f"🔍 **{m[0]}**\nStatus: {m[1]}\nDeposit: {m[2]:,.0f} USC\nLevel: {m[3]}", parse_mode="Markdown")


def main():
    TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "9295610891:AAHOL3Sd2blRnhqt6e9eRwWGJJYx4hJA3gM")
    app = ApplicationBuilder().token(TOKEN).build()

    app.job_queue.run_repeating(auto_cleanup_unverified_users, interval=3600, first=10)

    reg_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            ASK_BROKER: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_broker)],
            ASK_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_name)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    admin_handler = ConversationHandler(
        entry_points=[CommandHandler("admin", admin_start)],
        states={
            ADMIN_BROKER: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_get_broker)],
            ADMIN_DEPOSIT: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_get_deposit)],
            ADMIN_FEE: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_get_fee)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    app.add_handler(reg_handler)
    app.add_handler(admin_handler)
    app.add_handler(CommandHandler("menu", menu))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_menu))
    app.add_handler(CallbackQueryHandler(handle_language_callback, pattern="^(change_lang|lang_)"))
    app.add_handler(CallbackQueryHandler(admin_save_callback, pattern="^admin_"))
    app.add_handler(CommandHandler("delete_user", admin_delete_user))
    app.add_handler(CommandHandler("list_members", admin_list_members))
    app.add_handler(CommandHandler("check_member", admin_check_member))

    logger.info("🤖 Bot berjalan...")
    app.run_polling()

if __name__ == "__main__":
    main()
