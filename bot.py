import os
import logging
import psycopg2
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
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

# Daftar Telegram ID Admin (Sesuaikan dengan ID Telegram Anda)
ADMIN_IDS = [777777001]

# Koneksi ke Database Supabase PostgreSQL
try:
    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()
    logger.info("✅ Berhasil terhubung ke Database PostgreSQL.")
except Exception as e:
    logger.error(f"❌ Gagal terhubung ke Database: {e}")

# --- STATE CONVERSATION ---
ASK_BROKER, ASK_NAME = range(2)
ADMIN_BROKER, ADMIN_DEPOSIT, ADMIN_FEE = range(2, 5)

# Persentase Komisi 15 Level
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


# ==========================================
# 1. FITUR AKSES, PENDAFTARAN & MENU UTAMA
# ==========================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    telegram_id = user.id

    # Cek apakah user sudah terdaftar di database
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
            f"Pilih menu di bawah atau gunakan /menu:"
        )
        await update.message.reply_text(welcome_msg, parse_mode="Markdown")
        return ConversationHandler.END

    # ATURAN: Jika diakses TANPA link referral (tidak ada context.args)
    if not context.args:
        intro_text = (
            "🖲️ **Selamat Datang di Zero Eight Bot**\n\n"
            "🌐 *Zero Eight Bot adalah sistem otomatis untuk menghitung, mencatat, dan memantau poin loyalitas anggota Komunitas ZeroEight.*\n\n"
            "⚠️ **PERHATIAN**\n"
            "Untuk menjaga validitas data dan poin komunitas, seluruh fitur bot hanya dapat digunakan oleh anggota yang telah melakukan registrasi melalui link referral resmi ZeroEight.\n\n"
            "🔒 Jika Anda belum terdaftar, silakan lakukan registrasi terlebih dahulu menggunakan referral yang valid."
        )
        
        keyboard = [[InlineKeyboardButton("🌐 Ganti Bahasa / Change Language", callback_data="change_lang")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(intro_text, reply_markup=reply_markup, parse_mode="Markdown")
        return ConversationHandler.END

    # ATURAN: Jika diakses DENGAN link referral (?start=BROKER)
    upline_broker = context.args[0].strip()
    
    # Validasi apakah upline broker valid/ada di database
    cur.execute("SELECT full_name FROM users WHERE broker_account = %s", (upline_broker,))
    if not cur.fetchone():
        await update.message.reply_text("❌ Link referral tidak valid atau upline tidak ditemukan. Silakan gunakan link referral yang benar.")
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
    
    cur.execute("SELECT telegram_id FROM users WHERE broker_account = %s", (broker_account,))
    if cur.fetchone():
        await update.message.reply_text("⚠️ Nomor akun broker ini sudah terdaftar di sistem. Silakan masukkan nomor akun broker lain yang valid:")
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
            f"Gunakan /menu untuk melihat informasi akun Anda.",
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
        await update.message.reply_text("❌ Anda belum terdaftar. Silakan gunakan link referral resmi untuk mendaftar.")
        return

    broker, status, deposit, levels = res
    bot_username = context.bot.username
    
    if status == "Verified":
        ref_link = f"https://t.me/{bot_username}?start={broker}"
    else:
        ref_link = "Belum aktif (Menunggu verifikasi/deposit pertama dari Admin)"

    menu_text = (
        f"📌 **MENU UTAMA ZERO EIGHT**\n\n"
        f"• Akun Broker: `{broker}`\n"
        f"• Status: {'✅ Terverifikasi & Aktif' if status == 'Verified' else '⏳ Unverified'}\n"
        f"• Total Deposit: `{deposit:,.0f} USC` (${deposit / 100:,.2f})\n"
        f"• Level Terbuka: `{levels} Level`\n\n"
        f"🔗 **Link Referral Anda:**\n`{ref_link}`"
    )
    await update.message.reply_text(menu_text, parse_mode="Markdown")


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ Proses dibatalkan.")
    return ConversationHandler.END


# ==========================================
# 2. PANEL ADMIN & REKAP HARIAN (/admin)
# ==========================================

async def admin_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in ADMIN_IDS:
        await update.message.reply_text("❌ Anda tidak memiliki akses admin.")
        return ConversationHandler.END

    await update.message.reply_text(
        "⚙️ **PANEL ADMIN: REKAP HARIAN**\n\n"
        "Masukkan **Nomor Akun Broker** member yang ingin di-update deposit/follow-nya:",
        parse_mode="Markdown"
    )
    return ADMIN_BROKER


async def admin_get_broker(update: Update, context: ContextTypes.DEFAULT_TYPE):
    broker = update.message.text.strip()
    
    cur.execute("SELECT full_name, deposit_usc, open_levels, status FROM users WHERE broker_account = %s", (broker,))
    res = cur.fetchone()

    if not res:
        await update.message.reply_text(f"❌ Akun broker `{broker}` tidak ditemukan di database. Masukkan nomor broker yang benar:", parse_mode="Markdown")
        return ADMIN_BROKER

    context.user_data["admin_broker"] = broker
    name, current_dep, current_lvl, status = res
    context.user_data["current_level"] = current_lvl

    await update.message.reply_text(
        f"✅ Member ditemukan:\n"
        f"Nama: **{name}**\n"
        f"Akun Broker: `{broker}`\n"
        f"Deposit Lama: `{current_dep:,.0f} USC` (${current_dep / 100:,.2f})\n\n"
        f"Sekarang, masukkan **Deposit / Nilai Follow Terbaru (dalam USC)**:\n"
        f"*(Ketik 0 jika melakukan unfollow total)*",
        parse_mode="Markdown"
    )
    return ADMIN_DEPOSIT


async def admin_get_deposit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        new_dep = float(update.message.text.strip())
        if new_dep < 0:
            raise ValueError()
    except ValueError:
        await update.message.reply_text("⚠️ Masukkan angka deposit yang valid (contoh: 150000 atau 0):")
        return ADMIN_DEPOSIT

    context.user_data["admin_deposit"] = new_dep
    await update.message.reply_text(
        f"✅ Deposit diterima: `{new_dep:,.0f} USC` (${new_dep / 100:,.2f})\n\n"
        f"Sekarang, masukkan **Performance Fee** hari ini untuk member tersebut (dalam USC):"
        f"\n*(Ketik 0 jika tidak ada fee)*",
        parse_mode="Markdown"
    )
    return ADMIN_FEE


async def admin_get_fee(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        perf_fee = float(update.message.text.strip())
        if perf_fee < 0:
            raise ValueError()
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

    # Logika indikator panah Naik / Turun level
    if new_lvl > old_lvl:
        lvl_diff_text = f"-> Level Terbuka jadi: {new_lvl} Level (Sebelumnya: {old_lvl} Level - NAIK ⬆️)"
    elif new_lvl < old_lvl:
        lvl_diff_text = f"-> Level Terbuka jadi: {new_lvl} Level (Sebelumnya: {old_lvl} Level - TURUN ⬇️)"
    else:
        lvl_diff_text = f"-> Level Terbuka: {new_lvl} Level (Tetap)"

    total_pool_network = perf_fee * 0.20 # 20% dibagikan ke jaringan

    cur.execute("SELECT full_name FROM users WHERE broker_account = %s", (broker,))
    name = cur.fetchone()[0]

    preview_text = (
        f"📋 **PREVIEW SEBELUM SIMPAN:**\n\n"
        f"Member: **{name}** (`{broker}`)\n"
        f"Tanggal: Hari Ini\n"
        f"Deposit: `{new_dep:,.0f} USC` (${new_dep / 100:,.2f})\n"
        f"{lvl_diff_text}\n\n"
        f"Performance Fee: `{perf_fee:,.0f} USC` (${perf_fee / 100:,.2f})\n"
        f"-> Total Poin yang dibagi ke jaringan (20%): `{total_pool_network:,.2f} USC` = `{total_pool_network / 100:,.2f} Poin`\n\n"
        f"Apakah data sudah benar?"
    )

    keyboard = [
        [InlineKeyboardButton("✅ Ya, Simpan", callback_data="admin_save"),
         InlineKeyboardButton("❌ Batal", callback_data="admin_cancel")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(preview_text, reply_markup=reply_markup, parse_mode="Markdown")
    return ConversationHandler.END


async def admin_save_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "admin_cancel":
        await query.edit_message_text("❌ Proses rekap admin dibatalkan.")
        return

    broker = context.user_data.get("admin_broker")
    new_dep = context.user_data.get("admin_deposit")
    new_lvl = context.user_data.get("admin_new_level")
    new_status = context.user_data.get("admin_status")
    perf_fee = context.user_data.get("admin_fee")

    try:
        # Update data member di database
        cur.execute(
            """
            UPDATE users 
            SET deposit_usc = %s, open_levels = %s, status = %s 
            WHERE broker_account = %s
            """,
            (new_dep, new_lvl, new_status, broker)
        )
        conn.commit()

        distribusi_log = ""
        if perf_fee > 0:
            current_upline = broker
            for level in range(1, 16):
                cur.execute("SELECT upline_broker FROM users WHERE broker_account = %s", (current_upline,))
                res = cur.fetchone()
                if not res or not res[0] or res[0] == "-":
                    break
                
                upline_broker = res[0]
                cur.execute("SELECT full_name, open_levels FROM users WHERE broker_account = %s", (upline_broker,))
                upline_data = cur.fetchone()
                if not upline_data:
                    break

                upline_name, upline_open_levels = upline_data
                rate = COMMISSION_RATES.get(level, 0.0)
                earned_usc = perf_fee * rate

                if upline_open_levels >= level:
                    distribusi_log += f"Lv {level}: {upline_name} (+{earned_usc:,.0f} USC / ${earned_usc/100:.2f})\n"
                else:
                    distribusi_log += f"Lv {level}: {upline_name} (Terkunci, Open Lv: {upline_open_levels})\n"

                current_upline = upline_broker

        await query.edit_message_text(
            f"✅ **DATA BERHASIL DISIMPAN!**\n\n"
            f"Akun Broker: `{broker}`\n"
            f"• Deposit Baru: `{new_dep:,.0f} USC` (${new_dep / 100:,.2f})\n"
            f"• Level Terbuka: `{new_lvl} Level`\n"
            f"• Performance Fee: `{perf_fee:,.0f} USC`\n\n"
            f"📦 **Distribusi Komisi Jaringan:**\n{distribusi_log if perf_fee > 0 else 'Tidak ada Performance Fee.'}",
            parse_mode="Markdown"
        )
    except Exception as e:
        logger.error(f"Error saving admin update: {e}")
        conn.rollback()
        await query.edit_message_text("❌ Terjadi kesalahan saat menyimpan data ke database.")


# ==========================================
# 3. MANAJEMEN ADMIN TAMBAHAN & CLEANUP
# ==========================================

async def auto_cleanup_unverified_users(context: ContextTypes.DEFAULT_TYPE):
    try:
        cur.execute(
            """
            DELETE FROM users 
            WHERE status = 'Unverified' 
            AND created_at < NOW() - INTERVAL '48 hours'
            """
        )
        deleted_count = cur.rowcount
        conn.commit()
        if deleted_count > 0:
            logger.info(f"🧹 Auto-Cleanup: Menghapus {deleted_count} akun unverified (>48 jam).")
    except Exception as e:
        logger.error(f"Error auto cleanup: {e}")
        conn.rollback()


async def admin_delete_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in ADMIN_IDS:
        await update.message.reply_text("❌ Anda tidak memiliki akses admin.")
        return

    if not context.args:
        await update.message.reply_text("⚠️ Format salah. Gunakan: `/delete_user <nomor_akun_broker>`", parse_mode="Markdown")
        return

    broker_acc = context.args[0].strip()

    try:
        cur.execute("SELECT full_name FROM users WHERE broker_account = %s", (broker_acc,))
        user = cur.fetchone()

        if not user:
            await update.message.reply_text(f"❌ Akun broker `{broker_acc}` tidak ditemukan.", parse_mode="Markdown")
            return

        cur.execute("DELETE FROM users WHERE broker_account = %s", (broker_acc,))
        conn.commit()

        await update.message.reply_text(
            f"✅ **AKUN BERHASIL DIHAPUS**\n\n"
            f"Nama: {user[0]}\n"
            f"Broker: `{broker_acc}` telah dihapus permanen dari sistem.",
            parse_mode="Markdown"
        )
    except Exception as e:
        logger.error(f"Error deleting user: {e}")
        conn.rollback()
        await update.message.reply_text("❌ Terjadi kesalahan saat menghapus data.")


async def admin_list_members(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in ADMIN_IDS:
        await update.message.reply_text("❌ Anda tidak memiliki akses admin.")
        return

    try:
        cur.execute(
            """
            SELECT broker_account, full_name, username, status, deposit_usc, open_levels, upline_broker, created_at 
            FROM users 
            ORDER BY created_at DESC
            """
        )
        members = cur.fetchall()

        if not members:
            await update.message.reply_text("📂 Belum ada member terdaftar.")
            return

        response_text = "📋 **DAFTAR SELURUH MEMBER KOMUNITAS**\n\n"
        for idx, m in enumerate(members, start=1):
            broker, name, username, status, deposit, levels, upline, created = m
            status_emoji = "✅" if status == "Verified" else "⏳"
            
            response_text += (
                f"{idx}. **{name}** (@{username or 'tanpa_username'})\n"
                f"   • Broker: `{broker}`\n"
                f"   • Status: {status_emoji} {status}\n"
                f"   • Deposit: `{deposit:,.0f} USC` (${deposit/100:.2f})\n"
                f"   • Open Level: {levels} Level\n"
                f"   • Upline: `{upline}`\n"
                f"   -----------------------------------\n"
            )

            if len(response_text) > 3500:
                await update.message.reply_text(response_text, parse_mode="Markdown")
                response_text = ""

        if response_text:
            await update.message.reply_text(response_text, parse_mode="Markdown")

    except Exception as e:
        logger.error(f"Error listing members: {e}")
        await update.message.reply_text("❌ Terjadi kesalahan saat mengambil data member.")


async def admin_check_member(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in ADMIN_IDS:
        return

    if not context.args:
        await update.message.reply_text("⚠️ Gunakan format: `/check_member <nomor_broker>`", parse_mode="Markdown")
        return

    broker_acc = context.args[0].strip()

    cur.execute(
        """
        SELECT full_name, username, status, deposit_usc, open_levels, upline_broker, created_at 
        FROM users WHERE broker_account = %s
        """, 
        (broker_acc,)
    )
    m = cur.fetchone()

    if not m:
        await update.message.reply_text(f"❌ Member dengan akun broker `{broker_acc}` tidak ditemukan.", parse_mode="Markdown")
        return

    name, username, status, deposit, levels, upline, created = m
    details = (
        f"🔍 **DETAIL INFORMASI MEMBER**\n\n"
        f"• Nama: **{name}**\n"
        f"• Username: @{username or '-'}\n"
        f"• Akun Broker: `{broker_acc}`\n"
        f"• Status: **{status}**\n"
        f"• Total Deposit: **`{deposit:,.0f} USC`** (${deposit/100:.2f})\n"
        f"• Level Terbuka: **{levels} Level**\n"
        f"• Upline Broker: `{upline}`\n"
        f"• Tanggal Daftar: {created}"
    )
    await update.message.reply_text(details, parse_mode="Markdown")


# ==========================================
# 4. MAIN PROGRAM & HANDLER REGISTRATION
# ==========================================

def main():
    TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "MASUKKAN_TOKEN_BOT_ANDA_DISINI")
    
    app = ApplicationBuilder().token(TOKEN).build()

    # --- JOB QUEUE (Auto Cleanup setiap 1 Jam) ---
    job_queue = app.job_queue
    job_queue.run_repeating(auto_cleanup_unverified_users, interval=3600, first=10)

    # --- CONVERSATION HANDLER: PENDAFTARAN MEMBER ---
    reg_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            ASK_BROKER: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_broker)],
            ASK_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_name)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    # --- CONVERSATION HANDLER: PANEL ADMIN REKAP ---
    admin_handler = ConversationHandler(
        entry_points=[CommandHandler("admin", admin_start)],
        states={
            ADMIN_BROKER: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_get_broker)],
            ADMIN_DEPOSIT: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_get_deposit)],
            ADMIN_FEE: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_get_fee)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    # Registrasi Handler Utama
    app.add_handler(reg_handler)
    app.add_handler(admin_handler)
    app.add_handler(CommandHandler("menu", menu))
    app.add_handler(CallbackQueryHandler(admin_save_callback, pattern="^admin_"))
    
    # Perintah Admin Tambahan
    app.add_handler(CommandHandler("delete_user", admin_delete_user))
    app.add_handler(CommandHandler("list_members", admin_list_members))
    app.add_handler(CommandHandler("check_member", admin_check_member))

    logger.info("🤖 Bot ZERO EIGHT Loyalty sedang berjalan...")
    app.run_polling()

if __name__ == "__main__":
    main()
