import os
import sys
import shutil
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database import Base, engine
import models

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "smart_tourism.db")
BACKUP_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    f"smart_tourism_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
)


def backup_database():
    if os.path.exists(DB_PATH):
        shutil.copy2(DB_PATH, BACKUP_PATH)
        print(f"[备份] 数据库已备份到: {BACKUP_PATH}")
        return True
    return False


def get_existing_tables(conn):
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = [row[0] for row in cursor.fetchall()]
    print(f"[检查] 现有表: {tables}")
    return tables


def get_table_columns(conn, table_name):
    cursor = conn.cursor()
    cursor.execute(f"PRAGMA table_info({table_name})")
    columns = {row[1]: row[2] for row in cursor.fetchall()}
    return columns


def migrate_distributors_table(conn):
    print("\n[迁移] 处理 distributors 表...")
    
    columns = get_table_columns(conn, "distributors")
    print(f"  现有列: {list(columns.keys())}")
    
    needs_migration = False
    if 'payment_account_encrypted' not in columns:
        needs_migration = True
        print("  [需要迁移] 缺少 payment_account_encrypted 列")
    if 'payment_account_type' not in columns:
        needs_migration = True
        print("  [需要迁移] 缺少 payment_account_type 列")
    
    if not needs_migration:
        print("  [跳过] distributors 表结构已是最新")
        return
    
    print("\n  [执行迁移] 重建 distributors 表...")
    cursor = conn.cursor()
    
    cursor.execute("""
        CREATE TABLE distributors_new (
            id INTEGER PRIMARY KEY,
            user_id INTEGER NOT NULL UNIQUE,
            distributor_code VARCHAR(20) NOT NULL UNIQUE,
            commission_rate FLOAT NOT NULL,
            is_active BOOLEAN NOT NULL,
            created_at DATETIME,
            payment_account_encrypted TEXT,
            payment_account_type VARCHAR(20),
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    """)
    print("    创建新表 distributors_new")
    
    cursor.execute("""
        INSERT INTO distributors_new (id, user_id, distributor_code, commission_rate, is_active, created_at)
        SELECT id, user_id, distributor_code, commission_rate, is_active, created_at
        FROM distributors
    """)
    print("    迁移现有数据")
    
    cursor.execute("DROP TABLE distributors")
    print("    删除旧表 distributors")
    
    cursor.execute("ALTER TABLE distributors_new RENAME TO distributors")
    print("    重命名新表为 distributors")
    
    conn.commit()
    print("  [完成] distributors 表迁移成功")


def migrate_coupons_table(conn):
    print("\n[迁移] 处理 coupons 表...")
    
    columns = get_table_columns(conn, "coupons")
    print(f"  现有列: {list(columns.keys())}")
    
    new_model_columns = [
        'id', 'name', 'coupon_type', 'discount_value', 'discount_percentage',
        'min_spend', 'max_discount', 'valid_from', 'valid_to',
        'total_stock', 'remained_stock', 'points_required',
        'target_member_level', 'target_scenic_spot_id', 'is_active', 'created_at'
    ]
    
    needs_migration = False
    for col in new_model_columns:
        if col not in columns and col not in ['face_value']:
            needs_migration = True
            print(f"  [需要迁移] 缺少 {col} 列")
    
    if 'face_value' in columns and 'discount_value' not in columns:
        needs_migration = True
        print("  [需要迁移] 需要将 face_value 迁移到 discount_value")
    
    if not needs_migration:
        print("  [跳过] coupons 表结构已是最新")
        return
    
    print("\n  [执行迁移] 重建 coupons 表...")
    cursor = conn.cursor()
    
    cursor.execute("""
        CREATE TABLE coupons_new (
            id INTEGER PRIMARY KEY,
            name VARCHAR(100) NOT NULL,
            coupon_type VARCHAR(10) NOT NULL DEFAULT '满减券',
            discount_value FLOAT NOT NULL,
            discount_percentage FLOAT,
            min_spend FLOAT NOT NULL DEFAULT 0.0,
            max_discount FLOAT,
            valid_from DATETIME NOT NULL,
            valid_to DATETIME NOT NULL,
            total_stock INTEGER NOT NULL DEFAULT 100,
            remained_stock INTEGER NOT NULL DEFAULT 100,
            points_required INTEGER NOT NULL DEFAULT 0,
            target_member_level VARCHAR(10),
            target_scenic_spot_id INTEGER,
            is_active BOOLEAN NOT NULL DEFAULT 1,
            created_at DATETIME,
            FOREIGN KEY (target_scenic_spot_id) REFERENCES scenic_spots (id)
        )
    """)
    print("    创建新表 coupons_new")
    
    if 'face_value' in columns:
        cursor.execute("""
            INSERT INTO coupons_new (
                id, name, coupon_type, discount_value, discount_percentage,
                min_spend, max_discount, valid_from, valid_to,
                total_stock, remained_stock, points_required,
                target_member_level, target_scenic_spot_id, is_active, created_at
            )
            SELECT 
                id, name, '满减券' as coupon_type, face_value as discount_value, NULL,
                0.0 as min_spend, NULL as max_discount,
                CURRENT_TIMESTAMP as valid_from, 
                datetime(CURRENT_TIMESTAMP, '+365 days') as valid_to,
                100 as total_stock, 100 as remained_stock,
                points_required, NULL, NULL, is_active, created_at
            FROM coupons
        """)
    else:
        cursor.execute("""
            INSERT INTO coupons_new (
                id, name, coupon_type, discount_value, discount_percentage,
                min_spend, max_discount, valid_from, valid_to,
                total_stock, remained_stock, points_required,
                target_member_level, target_scenic_spot_id, is_active, created_at
            )
            SELECT 
                id, name, coupon_type, discount_value, discount_percentage,
                min_spend, max_discount, valid_from, valid_to,
                total_stock, remained_stock, points_required,
                target_member_level, target_scenic_spot_id, is_active, created_at
            FROM coupons
        """)
    print("    迁移现有数据")
    
    cursor.execute("DROP TABLE coupons")
    print("    删除旧表 coupons")
    
    cursor.execute("ALTER TABLE coupons_new RENAME TO coupons")
    print("    重命名新表为 coupons")
    
    conn.commit()
    print("  [完成] coupons 表迁移成功")


def migrate_user_coupons_table(conn):
    print("\n[迁移] 检查 user_coupons 表...")
    
    columns = get_table_columns(conn, "user_coupons")
    print(f"  现有列: {list(columns.keys())}")
    print("  [跳过] user_coupons 表结构不需要变更")


def migrate_time_limited_commissions(conn):
    print("\n[迁移] 检查 time_limited_commissions 表...")
    
    tables = get_existing_tables(conn)
    if 'time_limited_commissions' not in tables:
        print("  [创建] time_limited_commissions 表不存在，需要创建")
        
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE time_limited_commissions (
                id INTEGER PRIMARY KEY,
                name VARCHAR(100) NOT NULL,
                distributor_id INTEGER,
                scenic_spot_id INTEGER,
                commission_rate FLOAT NOT NULL,
                valid_from DATETIME NOT NULL,
                valid_to DATETIME NOT NULL,
                is_active BOOLEAN NOT NULL DEFAULT 1,
                created_at DATETIME,
                FOREIGN KEY (distributor_id) REFERENCES distributors (id),
                FOREIGN KEY (scenic_spot_id) REFERENCES scenic_spots (id)
            )
        """)
        conn.commit()
        print("  [完成] time_limited_commissions 表创建成功")
    else:
        print("  [跳过] time_limited_commissions 表已存在")


def verify_migration(conn):
    print("\n" + "=" * 60)
    print("  [验证] 检查迁移结果")
    print("=" * 60)
    
    tables = get_existing_tables(conn)
    
    required_tables = [
        'users', 'scenic_spots', 'ticket_orders', 'distributors',
        'coupons', 'user_coupons', 'time_limited_commissions',
        'financial_logs', 'audit_logs'
    ]
    
    all_ok = True
    for table in required_tables:
        if table in tables:
            columns = get_table_columns(conn, table)
            print(f"  [OK] {table}: {list(columns.keys())}")
        else:
            print(f"  [WARN] {table} 表不存在")
            all_ok = False
    
    print("\n" + "=" * 60)
    if all_ok:
        print("  [完成] 所有表结构验证通过！")
    else:
        print("  [警告] 部分表存在问题")
    print("=" * 60)
    
    return all_ok


def run_migration():
    print("\n" + "=" * 60)
    print("  数据库迁移脚本")
    print("=" * 60)
    print(f"\n[信息] 数据库路径: {DB_PATH}")
    print(f"[时间] {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    import sqlite3
    
    if os.path.exists(DB_PATH):
        backup_database()
        
        conn = sqlite3.connect(DB_PATH)
        
        try:
            migrate_distributors_table(conn)
            migrate_coupons_table(conn)
            migrate_user_coupons_table(conn)
            migrate_time_limited_commissions(conn)
            
            verify_migration(conn)
            
        except Exception as e:
            print(f"\n[错误] 迁移过程中发生错误: {e}")
            import traceback
            traceback.print_exc()
            conn.rollback()
            return False
        finally:
            conn.close()
    else:
        print("\n[信息] 数据库不存在，将创建新数据库...")
        Base.metadata.create_all(bind=engine)
        print("[完成] 新数据库创建完成")
    
    return True


if __name__ == "__main__":
    run_migration()
