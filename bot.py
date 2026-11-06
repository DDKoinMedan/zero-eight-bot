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

    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM users WHERE telegram_id = %s", (user_id,))
    db_user = cur.fetchone()

    if data == "menu_profil":
        link = f"https://t.me/{loyalty_08_bot}?start=REF{db_user['broker_account']}"
        text = (
            f"👤 **PROFIL SAYA**\n\n"
            f"Nama: {db_user['full_name']}\n"
            f"Username: @{query.from_user.username or '-'}\n"
            f"Nomor Akun Broker: {db_user['broker_account']}\n"
            f"Upline: {db_user['upline_broker'] or '-'}\n\n"
            f"💰 **Nilai Follow Terbaru:**\n"
            f"{fmt_money(float(db_user['deposit_usc']))}\n\n"
            f"🔓 **Level Terbuka:** {db_user['open_levels']} Level\n"
            f"Dari 15 Level\n\n"
            f"Link Referral:\n{link}"
        )
        keyboard = [[InlineKeyboardButton("🔗 Salin Link", callback_data="menu_link")], [InlineKeyboardButton("🔙 Menu Utama", callback_data="main_menu")]]
        await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

    elif data == "menu_poin":
        cur.execute("SELECT COALESCE(SUM(reward_points), 0) FROM transactions WHERE recipient_broker = %s AND status = 'unclaimed'", (db_user['broker_account'],))
        unclaimed = cur.fetchone()['coalesce']
        cur.execute("SELECT COALESCE(SUM(reward_points), 0) FROM transactions WHERE recipient_broker = %s AND status = 'claimed'", (db_user['broker_account'],))
        claimed = cur.fetchone()['coalesce']
        total = float(unclaimed) + float(claimed)

        cur.execute("SELECT * FROM transactions WHERE recipient_broker = %s ORDER BY created_at DESC LIMIT 3", (db_user['broker_account'],))
        txs = cur.fetchall()

        text = (
            f"💰 **POIN SAYA**\n\n"
            f"Poin Belum Diklaim: {unclaimed:.2f} Poin\n"
            f"Poin Sudah Diklaim: {claimed:.2f} Poin\n"
            f"Total Poin Seumur Hidup: {total:.2f} Poin\n\n"
            f"📜 **RIWAYAT TERBARU:**\n"
        )
        for tx in txs:
            fee_str = fmt_money(float(tx['perf_fee_usc']))
            reward_usc_str = fmt_money(float(tx['reward_usc']))
            text += (
                f"\n📅 {tx['created_at'].strftime('%d %b %Y')}\n"
                f"Dari: {tx['source_broker']} - Lv {tx['level']}\n"
                f"Performance Fee: {fee_str}\n"
                f"Kamu dapat: {tx['percentage']}% = {reward_usc_str} = {tx['reward_points']:.2f} Poin\n"
                f"Status: {'Belum Diklaim' if tx['status']=='unclaimed' else 'Sudah Diklaim'}\n"
            )

        keyboard = [[InlineKeyboardButton("🎁 Tukar Reward", callback_data="menu_reward"), InlineKeyboardButton("🔙 Menu Utama", callback_data="main_menu")]]
        await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

    elif data == "menu_reward":
        cur.execute("SELECT COALESCE(SUM(reward_points), 0) FROM transactions WHERE recipient_broker = %s AND status = 'unclaimed'", (db_user['broker_account'],))
        points = cur.fetchone()['coalesce']
        
        cur.execute("SELECT * FROM rewards WHERE is_active = TRUE")
        rewards = cur.fetchall()

        text = f"🎁 **DAFTAR REWARD**\n\nPoin Kamu: {points:.2f} Poin (Belum Diklaim)\n\n"
        keyboard = []
        for r in rewards:
            text += f"{r['id']}. {r['name']}\n   Harga: {r['cost_points']} Poin\n"
            keyboard.append([InlineKeyboardButton(f"Tukar {r['name']}", callback_data=f"redeem_{r['id']}")])
        
        keyboard.append([InlineKeyboardButton("🔙 Menu Utama", callback_data="main_menu")])
        await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

    elif data == "menu_admin" and user_id in ADMIN_IDS:
        text = "🛠️ **PANEL ADMIN**\nPilih aksi di bawah:"
        keyboard = [
            [InlineKeyboardButton("➕ Input Data Harian", callback_data="admin_input_start")],
            [InlineKeyboardButton("👥 Daftar Member / Verifikasi", callback_data="admin_members")],
            [InlineKeyboardButton("🔙 Menu Utama", callback_data="main_menu")]
        ]
        await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

    elif data == "main_menu":
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
        if user_id in ADMIN_IDS:
            keyboard.append([InlineKeyboardButton("🛠️ Panel Admin", callback_data="menu_admin")])
        await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

    cur.close()
    conn.close()

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
