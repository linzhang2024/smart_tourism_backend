import sys
sys.path.insert(0, '.')

from database import Base, engine
import models

print("创建数据库表...")
Base.metadata.create_all(bind=engine)
print("数据库表创建完成")

from sqlalchemy import inspect
inspector = inspect(engine)
tables = inspector.get_table_names()
print(f"已创建的表: {tables}")

if 'ticket_orders' in tables:
    columns = inspector.get_columns('ticket_orders')
    print("\nticket_orders 表的列:")
    for col in columns:
        print(f"  - {col['name']}: {col['type']}")

if 'complaints' in tables:
    columns = inspector.get_columns('complaints')
    print("\ncomplaints 表的列:")
    for col in columns:
        print(f"  - {col['name']}: {col['type']}")

print("\n数据库初始化完成!")
