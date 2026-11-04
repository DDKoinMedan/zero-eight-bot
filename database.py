import os
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

load_dotenv()

DB_URL = os.getenv("DATABASE_URL", "postgresql://user:password@localhost:5432/zeroeight_db")

def get_connection():
    return psycopg2.connect(DB_URL, cursor_factory=RealDictCursor)

def init_db():
    conn = get_connection()
    cur = conn.cursor()
    
    # Tabel Users
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            telegram_id BIGINT PRIMARY KEY,
            username VARCHAR(100),
            full_name VARCHAR(150) NOT NULL,
            broker_account VARCHAR(50) UNIQUE NOT NULL,
            upline_broker VARCHAR(50),
            deposit_usc NUMERIC(15, 2) DEFAULT 0,
            open_levels INT DEFAULT 0,
            status VARCHAR(20) DEFAULT 'pending', -- pending, verified, rejected
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)

    # Tabel Riwayat Follow / Deposit Log
    cur.execute("""
        CREATE TABLE IF NOT EXISTS follow_logs (
            id SERIAL PRIMARY KEY,
            broker_account VARCHAR(50),
            old_deposit NUMERIC(15, 2),
            new_deposit NUMERIC(15, 2),
            old_level INT,
            new_level INT,
            changed_by VARCHAR(50),
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)

    # Tabel Transaksi Performance Fee & Poin
    cur.execute("""
        CREATE TABLE IF NOT EXISTS transactions (
            id SERIAL PRIMARY KEY,
            source_broker VARCHAR(50),
            recipient_broker VARCHAR(50),
            level INT,
            perf_fee_usc NUMERIC(15, 2),
            percentage NUMERIC(5, 2),
            reward_usc NUMERIC(15, 2),
            reward_points NUMERIC(10, 2),
            status VARCHAR(20) DEFAULT 'unclaimed', -- unclaimed, claimed
            tx_date DATE DEFAULT CURRENT_DATE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)

    # Tabel Reward
    cur.execute("""
        CREATE TABLE IF NOT EXISTS rewards (
            id SERIAL PRIMARY KEY,
            name VARCHAR(150) NOT NULL,
            cost_points NUMERIC(10, 2) NOT NULL,
            is_active BOOLEAN DEFAULT TRUE
        );
    """)

    # Tabel Penukaran Reward
    cur.execute("""
        CREATE TABLE IF NOT EXISTS redemptions (
            id SERIAL PRIMARY KEY,
            broker_account VARCHAR(50),
            reward_id INT,
            status VARCHAR(30) DEFAULT 'Menunggu Approve Admin',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)

    conn.commit()
    cur.close()
    conn.close()

if __name__ == "__main__":
    init_db()
    print("Database initialized successfully.")
