# ZERO EIGHT Loyalty Bot

Bot Telegram untuk mengelola program poin loyalitas komunitas Zero EIGHT berdasarkan Performance Fee CopyTrade.

## Fitur Utama
- **Konversi Wajib USC & USD**: Semua nilai uang otomatis tersinkronisasi dalam format `X USC ($Y)`.
- **Sistem Level Berjenjang (15 Level)**: Komisi mengalir hingga 15 level upline dengan alokasi total 20%.
- **Auto-Update Level**: Level terbuka secara otomatis berdasarkan jumlah deposit/follow pribadi member.
- **Panel Admin**: Input harian, manajemen member, dan verifikasi reward via Telegram.

## Cara Install & Menjalankan

1. **Clone Repository & Setup Environment**
   ```bash
   git clone [https://github.com/username/zero-eight-bot.git](https://github.com/username/zero-eight-bot.git)
   cd zero-eight-bot
   python -m venv venv
   source venv/bin/activate  # Windows: venv\Scripts\activate
   pip install -r requirements.txt
