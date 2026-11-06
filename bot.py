import os
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    filters,
    ConversationHandler,
)
from dotenv import load_dotenv
from database import get_connection

load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_IDS = [int(x) for x in os.getenv("ADMIN_IDS", "").split(",") if x]

logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

# States for Admin Input Conversation
SELECT_MEMBER, INPUT_DEPOSIT, INPUT_FEE, CONFIRM_DATA = range(4)

# Helper: Format USC & USD
def fmt_money(usc: float) -> str:
    usd = usc / 100
    # Format ribuan titik, desimal koma / standar rapi
    return f"{usc:,.0f} USC (${usd:,.2f})"

# Helper: Hitung Level Berdasarkan Deposit USC
def calculate_level(deposit_usc: float) -> int:
    if deposit_usc >= 500000: return 15
    elif deposit_usc >= 400000: return 14
    elif deposit_usc >= 300000: return 12
    elif deposit_usc >= 150000: return 10
    elif deposit_usc >= 100000: return 8
    elif deposit_usc >= 50000: return 6
    elif deposit_usc >= 30000: return 4
    elif deposit_usc >= 10000: return 2
    elif deposit_usc >= 5000: return 1
    else: return 0

LEVEL_PERCENTAGES = {
    1: 4.0, 2: 4.0, 3: 2.0, 4: 2.0, 5: 1.0, 6: 1.0, 7: 1.0, 8: 1.0, 9: 1.0,
    10: 0.5, 11: 0.5, 12: 0.5, 13: 0.5, 14: 0.5, 15: 0.5
}

# /start Handler & Registration Check
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM users WHERE telegram_id = %s", (user.id,))
    db_user = cur.fetchone()
    cur.close()
    conn.close()

    if not db_user:
        args = context.args
        upline_ref = args[0].replace("REF", "") if args else None
        
        # Simpan state sementara di context untuk registrasi
        context.user_data['reg_upline'] = upline_ref
        await update.message.reply_text(
            "👋 Selamat datang di **ZERO EIGHT Loyalty Bot**!\n\n"
            "Silakan ketik **Nama Lengkap** Anda untuk memulai registrasi:"
        )
        context.user_data['reg_step'] = 'full_name'
        return
    
    if db_user['status'] == 'pending':
        await update.message.reply_text("⏳ Akun Anda sedang diverifikasi oleh Admin. Mohon tunggu.")
        return

    # Menu Utama
    text = (
        f"👋 Halo, {db_user['full_name']}!\n"
        f"Selamat datang di ZERO EIGHT Loyalty Bot\n\n"
        f"Akun Broker: {db_user['broker_account']}\n"
        f"Level Terbuka: {db_user['open_levels']} Level\n\n"
        f"Pilih menu di bawah:"
    )
    keyboard = [
        [InlineKeyboardButton("👤 Profil Saya", callback_data="menu_profil"), InlineKeyboardButton("💰 Poin Saya", callback_data="menu_poin")],
        [InlineKeyboardButton("🌐 Jaringan Saya", callback_data="menu_jaringan"), InlineKeyboardButton("🎁 Daftar Reward", callback_data="menu_reward")],
        [InlineKeyboardButton("🔗 Link Referral Saya", callback_data="menu_link")],
        [InlineKeyboardButton("❓ Bantuan", callback_data="menu_bantuan")]
    ]
    if user.id in ADMIN_IDS:
        keyboard.append([InlineKeyboardButton("🛠️ Panel Admin", callback_data="menu_admin")])

    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(text, reply_markup=reply_markup, parse_mode="Markdown")

# Menu Callbacks
async def menu_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    user_id = query.from_user.id

    # Ambil data user dengan konversi aman ke integer/string
    db_user = None
    try:
        # Coba ambil berdasarkan telegram_id sebagai integer
        cur.execute("SELECT full_name, broker_account, status, deposit_usc, open_levels, language FROM users WHERE telegram_id = %s", (int(user_id),))
        db_user = cur.fetchone()
    except Exception as e:
        try:
            # Cadangan jika telegram_id disimpan sebagai string di database
            cur.execute("SELECT full_name, broker_account, status, deposit_usc, open_levels, language FROM users WHERE telegram_id = %s", (str(user_id),))
            db_user = cur.fetchone()
        except Exception as err:
            print(f"Database fetch error: {err}")

    # Tentukan nilai broker_account dengan aman
    broker_acc = str(db_user[1]) if db_user and len(db_user) > 1 and db_user[1] else str(user_id)
    lang = db_user[5] if db_user and len(db_user) > 5 and db_user[5] else "id"

    if data == "main_menu":
        text = (
            "🌟 **SELAMAT DATANG DI MENU UTAMA**\n\n"
            "Silakan pilih menu di bawah ini:"
        )
        keyboard = [
            [InlineKeyboardButton("👤 Profil Saya", callback_data="menu_profil"), InlineKeyboardButton("💰 Poin Saya", callback_data="menu_poin")],
            [InlineKeyboardButton("🌐 Jaringan Saya", callback_data="menu_jaringan"), InlineKeyboardButton("🎁 Daftar Reward", callback_data="menu_reward")],
            [InlineKeyboardButton("🔗 Link Referral Saya", callback_data="menu_referral"), InlineKeyboardButton("🌐 Ganti Bahasa", callback_data="menu_language")],
            [InlineKeyboardButton("❓ Bantuan", callback_data="menu_bantuan")]
        ]
        await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

    elif data == "menu_profil":
        if db_user:
            name, broker, status, deposit, levels, _ = db_user
            text = (
                f"👤 **PROFIL SAYA**\n\n"
                f"Nama: {name}\n"
                f"Akun Broker: {broker}\n"
                f"Status: {status}\n"
                f"Deposit USC: {deposit}\n"
                f"Level Terbuka: {levels} Level"
            )
        else:
            text = f"👤 **PROFIL SAYA**\n\nData profil tidak ditemukan untuk ID: {user_id}."
            
        keyboard = [[InlineKeyboardButton("🔙 Menu Utama", callback_data="main_menu")]]
        await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

    elif data == "menu_poin":
        text = "💰 **POIN SAYA**\n\nTotal Poin Anda: **0 Poin**\n\nTerus tingkatkan aktivitas dan jaringan Anda untuk mendapatkan lebih banyak poin."
        keyboard = [[InlineKeyboardButton("🔙 Menu Utama", callback_data="main_menu")]]
        await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

    elif data == "menu_jaringan":
        text = "🌐 **JARINGAN SAYA**\n\nFitur jaringan downline sedang dalam pengembangan."
        keyboard = [[InlineKeyboardButton("🔙 Menu Utama", callback_data="main_menu")]]
        await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

    elif data == "menu_reward":
        text = "🎁 **DAFTAR REWARD**\n\nBelum ada reward yang tersedia saat ini. Stay tuned!"
        keyboard = [[InlineKeyboardButton("🔙 Menu Utama", callback_data="main_menu")]]
        await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

    elif data == "menu_referral":
        # Menggunakan nomor akun broker asli dari database
        referral_link = f"https://t.me/loyalty_08_bot?start=REF{broker_acc}"
        text = (
            "🔗 **LINK REFERRAL ANDA**\n\n"
            "Bagikan link di bawah ini ke teman atau partner Anda untuk bergabung ke jaringan:\n\n"
            f"`{referral_link}`"
        )
        keyboard = [[InlineKeyboardButton("🔙 Menu Utama", callback_data="main_menu")]]
        await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

    elif data == "menu_bantuan":
        text = "❓ **BANTUAN**\n\nSilakan hubungi Admin jika Anda mengalami kendala pada akun atau transaksi."
        keyboard = [[InlineKeyboardButton("🔙 Menu Utama", callback_data="main_menu")]]
        await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

    elif data == "menu_language":
        text = "🌐 **PILIH BAHASA / SELECT LANGUAGE**\n\nSilakan pilih bahasa Anda / Please select your language:"
        keyboard = [
            [InlineKeyboardButton("🇮🇩 Indonesia", callback_data="lang_id"), InlineKeyboardButton("🇬🇧 English", callback_data="lang_en")],
            [InlineKeyboardButton("🇻🇳 Tiếng Việt", callback_data="lang_vi"), InlineKeyboardButton("🇹🇭 ไทย", callback_data="lang_th")],
            [InlineKeyboardButton("🇰🇭 ភាសាខ្មែរ", callback_data="lang_km"), InlineKeyboardButton("🇨🇳 中文", callback_data="lang_zh")],
            [InlineKeyboardButton("🇮🇳 भारत (Hindi)", callback_data="lang_hi"), InlineKeyboardButton("🇸🇦 العربية", callback_data="lang_ar")],
            [InlineKeyboardButton("🇫🇷 Français", callback_data="lang_fr"), InlineKeyboardButton("🇷🇺 Русский", callback_data="lang_ru")],
            [InlineKeyboardButton("🔙 Menu Utama", callback_data="main_menu")]
        ]
        await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

    elif data.startswith("lang_"):
        selected_lang = data.split("_")[1]
        
        try:
            cur.execute("UPDATE users SET language = %s WHERE telegram_id = %s", (selected_lang, int(user_id)))
            conn.commit()
        except Exception as e:
            try:
                cur.execute("UPDATE users SET language = %s WHERE telegram_id = %s", (selected_lang, str(user_id)))
                conn.commit()
            except Exception as err:
                print(f"Error saving language: {err}")

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
        
        keyboard = [[InlineKeyboardButton("🔙 Menu Utama", callback_data="main_menu")]]
        await query.message.edit_text(
            confirmation_texts.get(selected_lang, "✅ Language updated."), 
            reply_markup=InlineKeyboardMarkup(keyboard), 
            parse_mode="Markdown"
        )

# Admin Input Flow Handler using ConversationHandler
async def admin_input_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT broker_account, full_name FROM users WHERE status = 'verified'")
    members = cur.fetchall()
    cur.close()
    conn.close()

    if not members:
        await query.message.reply_text("Tidak ada member terverifikasi.")
        return ConversationHandler.END

    text = "🛠️ **INPUT DATA HARIAN**\n\nSilakan ketik **Nomor Akun Broker** member yang ingin diinput datanya:"
    await query.message.reply_text(text, parse_mode="Markdown")
    return SELECT_MEMBER

async def admin_get_member(update: Update, context: ContextTypes.DEFAULT_TYPE):
    broker_acc = update.message.text.strip()
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM users WHERE broker_account = %s", (broker_acc,))
    member = cur.fetchone()
    cur.close()
    conn.close()

    if not member:
        await update.message.reply_text("Nomor Akun Broker tidak ditemukan. Ketik ulang:")
        return SELECT_MEMBER

    context.user_data['target_member'] = member
    await update.message.reply_text(
        f"Member dipilih: {member['full_name']} ({member['broker_account']})\n\n"
        f"Masukkan **Deposit / Nilai Follow Terbaru (dalam USC)**:"
    )
    return INPUT_DEPOSIT

async def admin_get_deposit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        deposit_usc = float(update.message.text.strip())
    except ValueError:
        await update.message.reply_text("Masukkan angka yang valid dalam USC:")
        return INPUT_DEPOSIT

    context.user_data['new_deposit'] = deposit_usc
    await update.message.reply_text(
        f"Kamu input {deposit_usc:,.0f} USC ({fmt_money(deposit_usc)}).\n\n"
        f"Masukkan **Performance Fee (dalam USC)**:"
    )
    return INPUT_FEE

async def admin_get_fee(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        fee_usc = float(update.message.text.strip())
    except ValueError:
        await update.message.reply_text("Masukkan angka Performance Fee yang valid dalam USC:")
        return INPUT_FEE

    context.user_data['new_fee'] = fee_usc
    member = context.user_data['target_member']
    new_dep = context.user_data['new_deposit']
    
    old_level = member['open_levels']
    new_level = calculate_level(new_dep)
    level_diff_str = f"Lev Terbuka jadi: {new_level} Level (Sebelumnya: {old_level} Level)"
    if new_level > old_level: level_diff_str += " - NAIK ⬆️"
    elif new_level < old_level: level_diff_str += " - TURUN ⬇️"

    pool_20 = fee_usc * 0.20
    pool_20_pts = pool_20 / 100

    preview_text = (
        f"🔍 **PREVIEW SEBELUM SIMPAN:**\n\n"
        f"Member: {member['full_name']} ({member['broker_account']})\n"
        f"Deposit: {fmt_money(new_dep)}\n"
        f"-> {level_diff_str}\n\n"
        f"Performance Fee: {fmt_money(fee_usc)}\n"
        f"-> Total Poin yang dibagi ke jaringan (20%):\n"
        f"{fmt_money(pool_20)} = {pool_20_pts:.2f} Poin\n\n"
        f"Apakah data sudah benar?"
    )
    
    keyboard = [
        [InlineKeyboardButton("✅ Ya, Simpan", callback_data="confirm_save"), InlineKeyboardButton("❌ Batal", callback_data="cancel_save")]
    ]
    await update.message.reply_text(preview_text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
    return CONFIRM_DATA

async def admin_confirm_save(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.data == "cancel_save":
        await query.message.edit_text("Input data dibatalkan.")
        return ConversationHandler.END

    member = context.user_data['target_member']
    new_dep = context.user_data['new_deposit']
    fee_usc = context.user_data['new_fee']
    new_level = calculate_level(new_dep)

    conn = get_connection()
    cur = conn.cursor()

    # Update member deposit & level + Log follow
    cur.execute("""
        INSERT INTO follow_logs (broker_account, old_deposit, new_deposit, old_level, new_level, changed_by)
        VALUES (%s, %s, %s, %s, %s, %s)
    """, (member['broker_account'], member['deposit_usc'], new_dep, member['open_levels'], new_level, f"Admin {query.from_user.id}"))

    cur.execute("""
        UPDATE users SET deposit_usc = %s, open_levels = %s WHERE broker_account = %s
    """, (new_dep, new_level, member['broker_account']))

    # Distribusi Komisi Jaringan (15 Level)
    curr_upline = member['upline_broker']
    level = 1
    while curr_upline and level <= 15:
        cur.execute("SELECT * FROM users WHERE broker_account = %s", (curr_upline,))
        up_user = cur.fetchone()
        if not up_user:
            break

        # Cek apakah level upline terbuka
        if up_user['open_levels'] >= level:
            pct = LEVEL_PERCENTAGES[level]
            reward_usc = fee_usc * (pct / 100)
            reward_pts = reward_usc / 100

            cur.execute("""
                INSERT INTO transactions (source_broker, recipient_broker, level, perf_fee_usc, percentage, reward_usc, reward_points)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (member['broker_account'], curr_upline, level, fee_usc, pct, reward_usc, reward_pts))
            
            # Kirim Notifikasi ke Upline jika telegram_id ada
            try:
                notif_text = (
                    f"🔔 **Poin Baru Masuk!**\n\n"
                    f"Kamu dapat +{reward_pts:.2f} Poin\n"
                    f"Dari: {member['full_name']} - Lv {level}\n"
                    f"Performance Fee: {fmt_money(fee_usc)}\n"
                    f"Persentase: {pct}%\n\n"
                    f"Cek di /poin"
                )
                await context.bot.send_message(chat_id=up_user['telegram_id'], text=notif_text, parse_mode="Markdown")
            except Exception:
                pass

        curr_upline = up_user['upline_broker']
        level += 1

    conn.commit()
    cur.close()
    conn.close()

    await query.message.edit_text("✅ Data berhasil disimpan dan komisi jaringan telah didistribusikan!")
    return ConversationHandler.END

# Pendaftaran Member Baru Step-by-Step
async def register_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    step = context.user_data.get('reg_step')

    if not step:
        return

    if step == 'full_name':
        context.user_data['reg_name'] = text
        context.user_data['reg_step'] = 'broker_acc'
        await update.message.reply_text("Masukkan **Nomor Akun Broker** Anda (contoh: MT4/MT5 ID / Akun CopyTrade):")
    elif step == 'broker_acc':
        context.user_data['reg_broker'] = text
        
        user = update.effective_user
        conn = get_connection()
        cur = conn.cursor()
        try:
            cur.execute("""
                INSERT INTO users (telegram_id, username, full_name, broker_account, upline_broker, status)
                VALUES (%s, %s, %s, %s, %s, 'pending')
            """, (user.id, user.username, context.user_data['reg_name'], text, context.user_data.get('reg_upline')))
            conn.commit()
            await update.message.reply_text("✅ Pendaftaran berhasil! Akun Anda sedang menunggu verifikasi Admin.")
            context.user_data.clear()
        except Exception as e:
            conn.rollback()
            logger.error(f"Error saat registrasi: {e}")
            await update.message.reply_text(f"❌ Terjadi kesalahan database: {str(e)}\nSilakan mulai ulang dengan /start.")
        finally:
            cur.close()
            conn.close()

def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    # Conversation Handler untuk Admin Input Data
    admin_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(admin_input_start, pattern="^admin_input_start$")],
        states={
            SELECT_MEMBER: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_get_member)],
            INPUT_DEPOSIT: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_get_deposit)],
            INPUT_FEE: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_get_fee)],
            CONFIRM_DATA: [CallbackQueryHandler(admin_confirm_save, pattern="^(confirm_save|cancel_save)$")],
        },
        fallbacks=[],
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(admin_conv)
    app.add_handler(CallbackQueryHandler(menu_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, register_handler))

    print("Bot is running...")
    app.run_polling()

if __name__ == "__main__":
    main()
