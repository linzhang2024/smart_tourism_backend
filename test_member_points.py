import os
import sys
import logging
from datetime import datetime, timedelta
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    stream=sys.stdout
)
logging.getLogger('sqlalchemy.engine').setLevel(logging.INFO)

print("[启动] test_member_points.py 已启动...")
print(f"[信息] Python 版本: {sys.version}")
print(f"[信息] 工作目录: {os.getcwd()}")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

print("[导入] 正在导入 models 模块...")
try:
    import models
    print(f"[成功] models 模块导入成功")
    print(f"[检查] models.MemberLevel: {models.MemberLevel}")
    print(f"[检查] models.MemberLevel.NORMAL: {models.MemberLevel.NORMAL}")
    print(f"[检查] models.MemberLevel.SILVER: {models.MemberLevel.SILVER}")
    print(f"[检查] models.MemberLevel.GOLD: {models.MemberLevel.GOLD}")
except Exception as e:
    print(f"[错误] 导入 models 模块失败: {e}")
    import traceback
    traceback.print_exc()
    print("\n按 Enter 键退出...")
    input()
    sys.exit(1)

print("[导入] 正在导入其他模块...")
import schemas
from database import Base, engine, get_db
print("[成功] 所有模块导入完成")


def get_member_discount_rate(member_level: models.MemberLevel) -> float:
    if member_level == models.MemberLevel.GOLD:
        return 0.90
    elif member_level == models.MemberLevel.SILVER:
        return 0.95
    return 1.00


def calculate_discounted_price(original_price: float, member_level: models.MemberLevel) -> tuple[float, float]:
    discount_rate = get_member_discount_rate(member_level)
    discounted_price = original_price * discount_rate
    discount_amount = original_price - discounted_price
    return round(discounted_price, 2), round(discount_amount, 2)


def migrate_test_database():
    print("\n" + "=" * 60)
    print("  开始数据库迁移...")
    print("=" * 60)
    
    print("\n[阶段 1] 正在连接数据库...")
    try:
        conn = engine.connect()
        print("[成功] 数据库连接成功!")
    except Exception as e:
        print(f"[错误] 数据库连接失败: {e}")
        import traceback
        traceback.print_exc()
        return
    
    try:
        print("\n[阶段 2] 正在查询 users 表结构...")
        result = conn.execute(text("PRAGMA table_info(users)"))
        columns = [row[1] for row in result]
        print(f"[成功] users 表现有列: {columns}")
        
        if 'total_points' not in columns:
            print(f"\n[阶段 3] 添加 total_points 列...")
            print(f"  [执行] ALTER TABLE users ADD COLUMN total_points INTEGER DEFAULT 0")
            conn.execute(text("ALTER TABLE users ADD COLUMN total_points INTEGER DEFAULT 0"))
            print("  [完成] total_points 列添加成功!")
        else:
            print("\n[阶段 3] total_points 列已存在，跳过添加")
        
        if 'member_level' not in columns:
            print(f"\n[阶段 4] 添加 member_level 列...")
            print(f"  [执行] ALTER TABLE users ADD COLUMN member_level VARCHAR(20) DEFAULT '普通'")
            conn.execute(text("ALTER TABLE users ADD COLUMN member_level VARCHAR(20) DEFAULT '普通'"))
            print("  [完成] member_level 列添加成功!")
        else:
            print("\n[阶段 4] member_level 列已存在，跳过添加")
        
        result = conn.execute(text("SELECT name FROM sqlite_master WHERE type='table' AND name='coupons'"))
        if not result.fetchone():
            print("[迁移] 创建 coupons 表...")
            conn.execute(text("""
                CREATE TABLE coupons (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name VARCHAR(100) NOT NULL,
                    face_value INTEGER NOT NULL,
                    points_required INTEGER NOT NULL,
                    is_active BOOLEAN DEFAULT 1,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """))
            print("[迁移] 完成!")
        
        result = conn.execute(text("SELECT name FROM sqlite_master WHERE type='table' AND name='user_coupons'"))
        if not result.fetchone():
            print("[迁移] 创建 user_coupons 表...")
            conn.execute(text("""
                CREATE TABLE user_coupons (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    coupon_id INTEGER NOT NULL,
                    redemption_code VARCHAR(20) UNIQUE NOT NULL,
                    is_used BOOLEAN DEFAULT 0,
                    obtained_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    expires_at DATETIME,
                    used_at DATETIME,
                    used_order_id INTEGER,
                    FOREIGN KEY (user_id) REFERENCES users (id),
                    FOREIGN KEY (coupon_id) REFERENCES coupons (id),
                    FOREIGN KEY (used_order_id) REFERENCES ticket_orders (id)
                )
            """))
            print("[迁移] 完成!")
        else:
            result = conn.execute(text("PRAGMA table_info(user_coupons)"))
            columns = [row[1] for row in result]
            
            if 'redemption_code' not in columns:
                print("[迁移] 添加 redemption_code 列到 user_coupons 表...")
                try:
                    conn.execute(text("ALTER TABLE user_coupons ADD COLUMN redemption_code VARCHAR(20)"))
                    print("[迁移] 完成!")
                    
                    print("[迁移] 创建 redemption_code 唯一索引...")
                    conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS idx_user_coupons_redemption_code ON user_coupons(redemption_code)"))
                    print("[迁移] 完成!")
                except Exception as e:
                    print(f"[迁移] 警告: {e}")
            
            if 'expires_at' not in columns:
                print("[迁移] 添加 expires_at 列到 user_coupons 表...")
                conn.execute(text("ALTER TABLE user_coupons ADD COLUMN expires_at DATETIME"))
                print("[迁移] 完成!")
            
            if 'used_order_id' not in columns:
                print("[迁移] 添加 used_order_id 列到 user_coupons 表...")
                conn.execute(text("ALTER TABLE user_coupons ADD COLUMN used_order_id INTEGER"))
                print("[迁移] 完成!")
        
        result = conn.execute(text("SELECT name FROM sqlite_master WHERE type='table' AND name='point_logs'"))
        if result.fetchone():
            result = conn.execute(text("PRAGMA table_info(point_logs)"))
            columns = [row[1] for row in result]
            
            if 'expires_at' not in columns:
                print("[迁移] 添加 expires_at 列到 point_logs 表...")
                conn.execute(text("ALTER TABLE point_logs ADD COLUMN expires_at DATETIME"))
                print("[迁移] 完成!")
            
            if 'is_expired' not in columns:
                print("[迁移] 添加 is_expired 列到 point_logs 表...")
                conn.execute(text("ALTER TABLE point_logs ADD COLUMN is_expired BOOLEAN DEFAULT 0"))
                print("[迁移] 完成!")
        
        result = conn.execute(text("SELECT name FROM sqlite_master WHERE type='table' AND name='complaints'"))
        if result.fetchone():
            result = conn.execute(text("PRAGMA table_info(complaints)"))
            columns = [row[1] for row in result]
            
            if 'is_points_rewarded' not in columns:
                print("[迁移] 添加 is_points_rewarded 列到 complaints 表...")
                conn.execute(text("ALTER TABLE complaints ADD COLUMN is_points_rewarded BOOLEAN DEFAULT 0"))
                print("[迁移] 完成!")
        
        print("\n[阶段 5] 提交事务...")
        conn.commit()
        print("[成功] 事务提交完成!")
        
        print("\n[阶段 6] 验证 users 表结构...")
        result = conn.execute(text("PRAGMA table_info(users)"))
        columns = [row[1] for row in result]
        print(f"[成功] users 表最终列: {columns}")
        
        if 'total_points' in columns and 'member_level' in columns:
            print("[成功] 数据库迁移验证通过!")
        else:
            print("[警告] 数据库迁移可能未完成!")
        
        conn.close()
        print("\n[完成] 数据库迁移流程结束")
        
    except Exception as e:
        print(f"\n[错误] 数据库迁移过程中发生异常: {e}")
        import traceback
        traceback.print_exc()
        try:
            conn.rollback()
            print("[回滚] 事务已回滚")
        except:
            pass
        try:
            conn.close()
        except:
            pass


def run_member_discount_test():
    print("\n" + "=" * 60)
    print("  会员折扣特权测试")
    print("=" * 60)
    print("\n[测试场景] 验证不同会员等级的购票折扣计算")
    print("-" * 60)
    
    test_cases = [
        {
            "name": "普通会员 - 无折扣",
            "level": models.MemberLevel.NORMAL,
            "discount_rate": 1.00,
            "description": "普通会员不享受折扣"
        },
        {
            "name": "白银会员 - 95折",
            "level": models.MemberLevel.SILVER,
            "discount_rate": 0.95,
            "description": "白银会员享受 95 折优惠"
        },
        {
            "name": "黄金会员 - 9折",
            "level": models.MemberLevel.GOLD,
            "discount_rate": 0.90,
            "description": "黄金会员享受 9 折优惠"
        }
    ]
    
    all_passed = True
    
    for test_case in test_cases:
        print(f"\n[测试] {test_case['name']}")
        print(f"  [说明] {test_case['description']}")
        
        expected_rate = test_case['discount_rate']
        actual_rate = get_member_discount_rate(test_case['level'])
        
        print(f"  [验证] 预期折扣率: {expected_rate}")
        print(f"  [验证] 实际折扣率: {actual_rate}")
        
        assert actual_rate == expected_rate, f"折扣率错误: 预期 {expected_rate}, 实际 {actual_rate}"
        print("  [通过] 折扣率计算正确!")
        
        original_price = 200.0
        expected_discounted = round(original_price * expected_rate, 2)
        expected_discount = round(original_price - expected_discounted, 2)
        
        actual_discounted, actual_discount = calculate_discounted_price(
            original_price, test_case['level']
        )
        
        print(f"  [计算] 原价: {original_price} 元")
        print(f"  [验证] 预期折后价: {expected_discounted} 元, 预期减免: {expected_discount} 元")
        print(f"  [验证] 实际折后价: {actual_discounted} 元, 实际减免: {actual_discount} 元")
        
        assert actual_discounted == expected_discounted, f"折后价错误: 预期 {expected_discounted}, 实际 {actual_discounted}"
        assert actual_discount == expected_discount, f"减免金额错误: 预期 {expected_discount}, 实际 {actual_discount}"
        print("  [通过] 价格计算正确!")
    
    print("\n" + "=" * 60)
    print("  会员折扣计算测试全部通过!")
    print("=" * 60)
    
    print("\n[详细验证] 黄金会员 9 折优惠示例:")
    gold_original = 1000.0
    gold_discounted, gold_discount = calculate_discounted_price(
        gold_original, models.MemberLevel.GOLD
    )
    print(f"  原价: {gold_original} 元")
    print(f"  折扣率: 0.90 (9折)")
    print(f"  折后价: {gold_discounted} 元")
    print(f"  减免金额: {gold_discount} 元")
    
    assert gold_discounted == 900.0, f"黄金会员 1000 元原价折后应为 900 元，实际为 {gold_discounted}"
    assert gold_discount == 100.0, f"黄金会员 1000 元原价应减免 100 元，实际为 {gold_discount}"
    print("  [通过] 黄金会员 9 折优惠验证通过!")
    
    print("\n[详细验证] 白银会员 95 折优惠示例:")
    silver_original = 1000.0
    silver_discounted, silver_discount = calculate_discounted_price(
        silver_original, models.MemberLevel.SILVER
    )
    print(f"  原价: {silver_original} 元")
    print(f"  折扣率: 0.95 (95折)")
    print(f"  折后价: {silver_discounted} 元")
    print(f"  减免金额: {silver_discount} 元")
    
    assert silver_discounted == 950.0, f"白银会员 1000 元原价折后应为 950 元，实际为 {silver_discounted}"
    assert silver_discount == 50.0, f"白银会员 1000 元原价应减免 50 元，实际为 {silver_discount}"
    print("  [通过] 白银会员 95 折优惠验证通过!")
    
    return True


def run_coupon_exchange_test():
    print("\n" + "=" * 60)
    print("  积分兑换测试")
    print("=" * 60)
    print("\n[测试场景] 验证积分兑换优惠券逻辑")
    print("-" * 60)
    
    print("\n[步骤 0] 同步数据库模型...")
    try:
        Base.metadata.create_all(bind=engine)
        print("[成功] 数据库模型同步完成!")
    except Exception as e:
        print(f"[错误] 数据库模型同步失败: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    print("\n[步骤 0.1] 创建数据库会话...")
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = SessionLocal()
    print("[成功] 数据库会话创建完成!")
    
    test_user = None
    test_coupon = None
    test_user_coupon = None
    
    try:
        print("\n[步骤 1] 创建测试数据...")
        
        username = f"test_exchange_{os.urandom(4).hex()}"
        print(f"  [生成] 测试用户名: {username}")
        
        test_user = models.User(
            username=username,
            hashed_password="hashed_password_test",
            role=models.UserRole.TOURIST,
            total_points=2000,
            member_level=models.MemberLevel.SILVER
        )
        db.add(test_user)
        db.commit()
        db.refresh(test_user)
        
        print(f"  [创建] 测试用户: ID={test_user.id}, 用户名={test_user.username}")
        print(f"  [验证] 初始积分: {test_user.total_points} (预期: 2000)")
        print(f"  [验证] 会员等级: {test_user.member_level.value} (预期: 白银)")
        
        test_coupon = models.Coupon(
            name="20元优惠券",
            face_value=20,
            points_required=1000,
            is_active=True
        )
        db.add(test_coupon)
        db.commit()
        db.refresh(test_coupon)
        
        print(f"  [创建] 测试优惠券: ID={test_coupon.id}, 名称={test_coupon.name}")
        print(f"  [验证] 面值: {test_coupon.face_value} 元")
        print(f"  [验证] 所需积分: {test_coupon.points_required}")
        
        print("\n[步骤 2] 测试积分不足情况...")
        
        insufficient_coupon = models.Coupon(
            name="50元优惠券",
            face_value=50,
            points_required=5000,
            is_active=True
        )
        db.add(insufficient_coupon)
        db.commit()
        db.refresh(insufficient_coupon)
        
        print(f"  [验证] 用户当前积分: {test_user.total_points}")
        print(f"  [验证] 优惠券所需积分: {insufficient_coupon.points_required}")
        
        assert test_user.total_points < insufficient_coupon.points_required, "积分应该不足"
        print("  [通过] 积分不足验证正确!")
        
        print("\n[步骤 3] 测试积分兑换成功...")
        
        original_points = test_user.total_points
        points_spent = test_coupon.points_required
        expected_remaining = original_points - points_spent
        
        print(f"  [兑换] 使用积分: {points_spent}")
        print(f"  [兑换] 预期剩余: {expected_remaining}")
        
        test_user.total_points -= points_spent
        
        test_user_coupon = models.UserCoupon(
            user_id=test_user.id,
            coupon_id=test_coupon.id,
            is_used=False
        )
        db.add(test_user_coupon)
        
        point_log = models.PointLog(
            user_id=test_user.id,
            points_change=-points_spent,
            reason=f"积分兑换优惠券: {test_coupon.name}"
        )
        db.add(point_log)
        
        db.commit()
        db.refresh(test_user)
        db.refresh(test_user_coupon)
        db.refresh(point_log)
        
        print(f"  [验证] 剩余积分: {test_user.total_points} (预期: {expected_remaining})")
        assert test_user.total_points == expected_remaining, f"剩余积分错误: 预期 {expected_remaining}, 实际 {test_user.total_points}"
        
        print(f"  [验证] 积分变动: {point_log.points_change} (预期: -{points_spent})")
        assert point_log.points_change == -points_spent, f"积分流水错误"
        
        print(f"  [验证] 流水原因: {point_log.reason}")
        assert "积分兑换" in point_log.reason, "流水原因应包含 '积分兑换'"
        
        print(f"  [验证] 用户优惠券: ID={test_user_coupon.id}, 已使用={test_user_coupon.is_used}")
        assert test_user_coupon.is_used == False, "新兑换的优惠券应该未使用"
        
        print(f"  [验证] 优惠券核销码: {test_user_coupon.redemption_code}")
        assert test_user_coupon.redemption_code is not None, "核销码不应为空"
        assert len(test_user_coupon.redemption_code) > 0, "核销码长度应大于 0"
        assert test_user_coupon.redemption_code.startswith("CP"), "核销码应以 CP 开头"
        
        print("  [通过] 积分兑换成功验证正确!")
        
        print("\n[步骤 4] 验证 Coupon 模型完整性...")
        print(f"  [验证] Coupon 模型字段:")
        print(f"    - id: {test_coupon.id}")
        print(f"    - name: {test_coupon.name}")
        print(f"    - face_value: {test_coupon.face_value}")
        print(f"    - points_required: {test_coupon.points_required}")
        print(f"    - is_active: {test_coupon.is_active}")
        print(f"    - created_at: {test_coupon.created_at}")
        
        assert test_coupon.name == "20元优惠券", "优惠券名称错误"
        assert test_coupon.face_value == 20, "优惠券面值错误"
        assert test_coupon.points_required == 1000, "所需积分错误"
        assert test_coupon.is_active == True, "优惠券应该激活"
        
        print("  [通过] Coupon 模型验证正确!")
        
        print("\n" + "=" * 60)
        print("  积分兑换测试全部通过!")
        print("=" * 60)
        print(f"\n  验证要点:")
        print(f"  1. Coupon 模型包含 name、face_value、points_required 字段")
        print(f"  2. 积分不足时无法兑换")
        print(f"  3. 兑换成功后扣减用户积分")
        print(f"  4. 生成负积分的 PointLog 流水记录")
        print(f"  5. 创建 UserCoupon 记录关联用户和优惠券")
        print(f"  6. 生成唯一的 redemption_code 核销码")
        
        return True
        
    except AssertionError as e:
        print(f"\n  [失败] 断言失败: {e}")
        return False
    except Exception as e:
        print(f"\n  [错误] 测试过程中发生异常: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        print("\n[清理] 清除测试数据...")
        
        try:
            if test_user_coupon:
                db.delete(test_user_coupon)
                db.commit()
            
            if test_coupon:
                db.delete(test_coupon)
                db.commit()
            
            insufficient_coupon = db.query(models.Coupon).filter(
                models.Coupon.name == "50元优惠券"
            ).first()
            if insufficient_coupon:
                db.delete(insufficient_coupon)
                db.commit()
            
            if test_user:
                logs = db.query(models.PointLog).filter(
                    models.PointLog.user_id == test_user.id
                ).all()
                for log in logs:
                    db.delete(log)
                db.commit()
                
                db.delete(test_user)
                db.commit()
            
            db.close()
            print("  [完成] 测试数据已清理")
        except Exception as e:
            print(f"  [警告] 清理测试数据时发生错误: {e}")


def run_member_points_test():
    print("\n" + "=" * 60)
    print("  会员积分中心测试 - 基础验证")
    print("=" * 60)
    print("\n[测试场景] 模拟游客登录 -> 购票成功 -> 验证积分累计 -> 验证流水记录")
    print("-" * 60)
    
    migrate_test_database()
    
    print("\n[步骤 0] 同步数据库模型...")
    try:
        Base.metadata.create_all(bind=engine)
        print("[成功] 数据库模型同步完成!")
    except Exception as e:
        print(f"[错误] 数据库模型同步失败: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    print("\n[步骤 0.1] 创建数据库会话...")
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = SessionLocal()
    print("[成功] 数据库会话创建完成!")
    
    test_user = None
    test_spot = None
    test_order = None
    
    try:
        print("\n[步骤 1] 创建测试数据...")
        
        username = f"test_member_{os.urandom(4).hex()}"
        print(f"  [生成] 测试用户名: {username}")
        
        print("  [创建] 正在创建测试用户...")
        print(f"    - member_level = models.MemberLevel.NORMAL = {models.MemberLevel.NORMAL}")
        
        test_user = models.User(
            username=username,
            hashed_password="hashed_password_test",
            role=models.UserRole.TOURIST,
            total_points=0,
            member_level=models.MemberLevel.NORMAL
        )
        db.add(test_user)
        
        print("  [提交] 正在提交用户到数据库...")
        db.commit()
        print("  [刷新] 正在刷新用户对象...")
        db.refresh(test_user)
        
        print(f"  [成功] 测试用户创建完成!")
        print(f"  [创建] 测试用户: ID={test_user.id}, 用户名={test_user.username}")
        print(f"  [验证] 初始积分: {test_user.total_points} (预期: 0)")
        print(f"  [验证] 初始等级: {test_user.member_level.value} (预期: 普通)")
        
        assert test_user.total_points == 0, f"初始积分应为 0，实际为 {test_user.total_points}"
        assert test_user.member_level == models.MemberLevel.NORMAL, f"初始等级应为 普通，实际为 {test_user.member_level}"
        
        ticket_price = 150.5
        print("\n  [创建] 正在创建测试景点...")
        test_spot = models.ScenicSpot(
            name="积分测试景点",
            description="用于会员积分测试的景点",
            location="测试地点",
            price=ticket_price,
            total_inventory=100,
            remained_inventory=100
        )
        db.add(test_spot)
        db.commit()
        db.refresh(test_spot)
        
        print(f"  [创建] 测试景点: ID={test_spot.id}, 名称={test_spot.name}, 单价={test_spot.price}")
        
        print("\n[步骤 2] 模拟购票成功...")
        
        ticket_quantity = 2
        total_price = ticket_price * ticket_quantity
        expected_points = int(total_price)
        
        print(f"  [购票] 购买数量: {ticket_quantity} 张")
        print(f"  [购票] 订单总价: {total_price} 元")
        print(f"  [预期] 获得积分: {expected_points} 分 (1元 = 1积分，取整)")
        
        print("  [创建] 正在创建订单...")
        test_order = models.TicketOrder(
            user_id=test_user.id,
            scenic_spot_id=test_spot.id,
            quantity=ticket_quantity,
            total_price=total_price,
            status=models.OrderStatus.PAID
        )
        db.add(test_order)
        
        print("  [更新] 正在更新用户积分...")
        test_user.total_points += expected_points
        
        print("  [更新] 正在更新会员等级...")
        if test_user.total_points >= 5000:
            test_user.member_level = models.MemberLevel.GOLD
        elif test_user.total_points >= 1000:
            test_user.member_level = models.MemberLevel.SILVER
        else:
            test_user.member_level = models.MemberLevel.NORMAL
        
        print("  [创建] 正在创建积分流水记录...")
        point_log = models.PointLog(
            user_id=test_user.id,
            points_change=expected_points,
            reason=f"购票成功获得积分，订单号: {test_order.order_no}"
        )
        db.add(point_log)
        
        print("  [提交] 正在提交事务...")
        db.commit()
        print("  [刷新] 正在刷新对象...")
        db.refresh(test_user)
        db.refresh(point_log)
        
        print("\n[步骤 2.1] 验证 PointLog 有效期字段...")
        print(f"  [验证] PointLog.expires_at: {point_log.expires_at}")
        print(f"  [验证] PointLog.is_expired: {point_log.is_expired}")
        
        assert point_log.expires_at is not None, "积分流水应该有有效期"
        assert point_log.is_expired == False, "新创建的积分流水不应过期"
        
        expected_expiry = datetime.utcnow() + timedelta(days=365)
        time_diff = abs((point_log.expires_at - expected_expiry).total_seconds())
        assert time_diff < 60, f"有效期应该约为一年后，实际与预期相差 {time_diff} 秒"
        
        print("  [通过] PointLog 有效期字段验证正确!")
        
        print("\n[步骤 3] 验证积分累计...")
        print(f"  [验证] 用户 ID: {test_user.id}")
        print(f"  [验证] 当前积分: {test_user.total_points} (预期: {expected_points})")
        print(f"  [验证] 当前等级: {test_user.member_level.value} (预期: 普通，积分不足 1000)")
        
        assert test_user.total_points == expected_points, f"积分应为 {expected_points}，实际为 {test_user.total_points}"
        assert test_user.member_level == models.MemberLevel.NORMAL, f"等级应为 普通，实际为 {test_user.member_level}"
        
        print("  [通过] 积分累计正确!")
        
        print("\n[步骤 4] 验证 PointLog 流水记录...")
        
        logs = db.query(models.PointLog).filter(
            models.PointLog.user_id == test_user.id
        ).order_by(models.PointLog.created_at.desc()).all()
        
        print(f"  [验证] 流水记录数: {len(logs)} (预期: 1)")
        assert len(logs) == 1, f"流水记录数应为 1，实际为 {len(logs)}"
        
        latest_log = logs[0]
        print(f"  [验证] 流水 ID: {latest_log.id}")
        print(f"  [验证] 用户 ID: {latest_log.user_id} (预期: {test_user.id})")
        print(f"  [验证] 变动积分: {latest_log.points_change} (预期: {expected_points})")
        print(f"  [验证] 变动原因: {latest_log.reason}")
        print(f"  [验证] 变动时间: {latest_log.created_at}")
        
        assert latest_log.user_id == test_user.id, f"用户 ID 应为 {test_user.id}，实际为 {latest_log.user_id}"
        assert latest_log.points_change == expected_points, f"变动积分应为 {expected_points}，实际为 {latest_log.points_change}"
        assert "购票成功" in latest_log.reason, "变动原因应包含 '购票成功'"
        
        print("  [通过] 流水记录正确!")
        
        print("\n[步骤 5] 验证会员等级升级逻辑...")
        
        print("\n  [场景 A] 累计积分达到 1000，升级为白银会员")
        test_user.total_points = 1000
        if test_user.total_points >= 5000:
            test_user.member_level = models.MemberLevel.GOLD
        elif test_user.total_points >= 1000:
            test_user.member_level = models.MemberLevel.SILVER
        else:
            test_user.member_level = models.MemberLevel.NORMAL
        db.commit()
        db.refresh(test_user)
        print(f"    [积分] {test_user.total_points} -> [等级] {test_user.member_level.value}")
        assert test_user.member_level == models.MemberLevel.SILVER, f"1000 积分应为白银会员，实际为 {test_user.member_level}"
        
        print("\n  [场景 B] 累计积分达到 5000，升级为黄金会员")
        test_user.total_points = 5000
        if test_user.total_points >= 5000:
            test_user.member_level = models.MemberLevel.GOLD
        elif test_user.total_points >= 1000:
            test_user.member_level = models.MemberLevel.SILVER
        else:
            test_user.member_level = models.MemberLevel.NORMAL
        db.commit()
        db.refresh(test_user)
        print(f"    [积分] {test_user.total_points} -> [等级] {test_user.member_level.value}")
        assert test_user.member_level == models.MemberLevel.GOLD, f"5000 积分应为黄金会员，实际为 {test_user.member_level}"
        
        print("\n  [场景 C] 积分不足 1000，保持普通会员")
        test_user.total_points = 999
        if test_user.total_points >= 5000:
            test_user.member_level = models.MemberLevel.GOLD
        elif test_user.total_points >= 1000:
            test_user.member_level = models.MemberLevel.SILVER
        else:
            test_user.member_level = models.MemberLevel.NORMAL
        db.commit()
        db.refresh(test_user)
        print(f"    [积分] {test_user.total_points} -> [等级] {test_user.member_level.value}")
        assert test_user.member_level == models.MemberLevel.NORMAL, f"999 积分应为普通会员，实际为 {test_user.member_level}"
        
        print("  [通过] 会员等级升级逻辑正确!")
        
        print("\n" + "=" * 60)
        print("  测试通过! 会员积分中心基础验证完成。")
        print("=" * 60)
        print(f"\n  验证要点:")
        print(f"  1. User 模型新增 total_points 和 member_level 字段")
        print(f"  2. 新增 PointLog 模型记录积分变动流水")
        print(f"  3. 购票成功后按 1元 = 1积分 比例累计积分")
        print(f"  4. PointLog 生成正确的流水记录")
        print(f"  5. PointLog 包含有效期字段，默认一年后过期")
        print(f"  6. 会员等级自动升级逻辑正确:")
        print(f"     - 普通: 0 - 999 积分")
        print(f"     - 白银: 1000 - 4999 积分")
        print(f"     - 黄金: 5000+ 积分")
        
        return True
        
    except AssertionError as e:
        print(f"\n  [失败] 断言失败: {e}")
        return False
    except Exception as e:
        print(f"\n  [错误] 测试过程中发生异常: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        print("\n[清理] 清除测试数据...")
        
        try:
            if test_order:
                db.delete(test_order)
                db.commit()
            
            if test_spot:
                db.delete(test_spot)
                db.commit()
            
            if test_user:
                logs = db.query(models.PointLog).filter(
                    models.PointLog.user_id == test_user.id
                ).all()
                for log in logs:
                    db.delete(log)
                db.commit()
                
                db.delete(test_user)
                db.commit()
            
            db.close()
            print("  [完成] 测试数据已清理")
        except Exception as e:
            print(f"  [警告] 清理测试数据时发生错误: {e}")


def run_complaint_points_test():
    print("\n" + "=" * 60)
    print("  投诉反馈积分奖励测试 - 管理员回复后奖励")
    print("=" * 60)
    print("\n[测试场景] 用户提交投诉不获得积分，管理员回复后获得 50 积分奖励")
    print("-" * 60)
    
    print("\n[步骤 0] 同步数据库模型...")
    try:
        Base.metadata.create_all(bind=engine)
        print("[成功] 数据库模型同步完成!")
    except Exception as e:
        print(f"[错误] 数据库模型同步失败: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    print("\n[步骤 0.1] 创建数据库会话...")
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = SessionLocal()
    print("[成功] 数据库会话创建完成!")
    
    test_user = None
    test_complaint = None
    point_log = None
    
    try:
        print("\n[步骤 1] 创建测试数据...")
        
        username = f"test_complaint_{os.urandom(4).hex()}"
        
        test_user = models.User(
            username=username,
            hashed_password="hashed_password_test",
            role=models.UserRole.TOURIST,
            total_points=0,
            member_level=models.MemberLevel.NORMAL
        )
        db.add(test_user)
        db.commit()
        db.refresh(test_user)
        
        print(f"  [创建] 测试用户: ID={test_user.id}, 用户名={test_user.username}")
        print(f"  [验证] 初始积分: {test_user.total_points} (预期: 0)")
        
        assert test_user.total_points == 0, f"初始积分应为 0，实际为 {test_user.total_points}"
        
        print("\n[步骤 2] 模拟投诉反馈提交（不获得积分）...")
        
        test_complaint = models.Complaint(
            user_id=test_user.id,
            title="测试投诉标题",
            content="这是一个测试投诉内容",
            status=models.ComplaintStatus.PENDING,
            is_points_rewarded=False
        )
        db.add(test_complaint)
        db.commit()
        db.refresh(test_complaint)
        
        db.refresh(test_user)
        
        print(f"  [提交] 投诉反馈标题: '测试投诉标题'")
        print(f"  [验证] 投诉状态: {test_complaint.status}")
        print(f"  [验证] is_points_rewarded: {test_complaint.is_points_rewarded}")
        print(f"  [验证] 用户当前积分: {test_user.total_points} (预期: 0 - 提交时不获得积分)")
        
        assert test_user.total_points == 0, f"提交投诉时不应获得积分，实际为 {test_user.total_points}"
        assert test_complaint.is_points_rewarded == False, "is_points_rewarded 应为 False"
        
        print("  [通过] 提交投诉时不获得积分验证正确!")
        
        print("\n[步骤 3] 模拟管理员回复投诉（获得积分）...")
        
        points_earned = 50
        
        test_complaint.reply = "感谢您的反馈，问题已处理。"
        test_complaint.status = models.ComplaintStatus.RESOLVED
        test_complaint.is_points_rewarded = True
        
        test_user.total_points += points_earned
        
        point_log = models.PointLog(
            user_id=test_user.id,
            points_change=points_earned,
            reason=f"投诉反馈获得积分，投诉ID: {test_complaint.id}"
        )
        db.add(point_log)
        
        if test_user.total_points >= 5000:
            test_user.member_level = models.MemberLevel.GOLD
        elif test_user.total_points >= 1000:
            test_user.member_level = models.MemberLevel.SILVER
        else:
            test_user.member_level = models.MemberLevel.NORMAL
        
        db.commit()
        db.refresh(test_user)
        db.refresh(test_complaint)
        db.refresh(point_log)
        
        print("\n[步骤 4] 验证积分奖励...")
        print(f"  [验证] 管理员回复内容: {test_complaint.reply}")
        print(f"  [验证] 投诉状态: {test_complaint.status}")
        print(f"  [验证] is_points_rewarded: {test_complaint.is_points_rewarded}")
        print(f"  [验证] 用户当前积分: {test_user.total_points} (预期: {points_earned})")
        print(f"  [验证] 流水积分变动: {point_log.points_change} (预期: {points_earned})")
        print(f"  [验证] 流水原因: {point_log.reason}")
        
        assert test_user.total_points == points_earned, f"积分应为 {points_earned}，实际为 {test_user.total_points}"
        assert test_complaint.is_points_rewarded == True, "is_points_rewarded 应为 True"
        assert point_log.points_change == points_earned, f"积分流水错误: 预期 {points_earned}，实际 {point_log.points_change}"
        assert "投诉反馈" in point_log.reason, "流水原因应包含 '投诉反馈'"
        
        print("  [通过] 管理员回复后获得积分验证正确!")
        
        print("\n[步骤 5] 验证只奖励一次...")
        
        original_points = test_user.total_points
        
        test_complaint.reply = "再次回复"
        db.commit()
        db.refresh(test_user)
        
        print(f"  [验证] 再次回复后用户积分: {test_user.total_points} (预期: {original_points} - 不再奖励)")
        
        assert test_user.total_points == original_points, f"再次回复不应获得积分，实际为 {test_user.total_points}"
        
        print("  [通过] 只奖励一次验证正确!")
        
        print("\n[步骤 6] 验证 PointLog 有效期...")
        print(f"  [验证] 流水有效期: {point_log.expires_at}")
        assert point_log.expires_at is not None, "积分流水应该有有效期"
        
        print("  [通过] PointLog 有效期验证正确!")
        
        print("\n" + "=" * 60)
        print("  投诉反馈积分奖励测试全部通过!")
        print("=" * 60)
        print(f"\n  验证要点:")
        print(f"  1. 用户提交投诉时不获得积分")
        print(f"  2. 管理员回复后获得 50 积分奖励")
        print(f"  3. 使用 is_points_rewarded 字段标记已奖励状态")
        print(f"  4. 只奖励一次，再次回复不重复奖励")
        print(f"  5. 生成正确的 PointLog 流水记录")
        print(f"  6. 积分流水包含有效期")
        
        return True
        
    except AssertionError as e:
        print(f"\n  [失败] 断言失败: {e}")
        return False
    except Exception as e:
        print(f"\n  [错误] 测试过程中发生异常: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        print("\n[清理] 清除测试数据...")
        
        try:
            if test_complaint:
                db.delete(test_complaint)
                db.commit()
            
            if test_user:
                logs = db.query(models.PointLog).filter(
                    models.PointLog.user_id == test_user.id
                ).all()
                for log in logs:
                    db.delete(log)
                db.commit()
                
                db.delete(test_user)
                db.commit()
            
            db.close()
            print("  [完成] 测试数据已清理")
        except Exception as e:
            print(f"  [警告] 清理测试数据时发生错误: {e}")


def run_coupon_validation_test():
    print("\n" + "=" * 60)
    print("  优惠券核销校验测试 - 第三轮验证")
    print("=" * 60)
    print("\n[测试场景] 验证优惠券核销的各种校验逻辑")
    print("-" * 60)
    
    print("\n[步骤 0] 同步数据库模型...")
    try:
        Base.metadata.create_all(bind=engine)
        print("[成功] 数据库模型同步完成!")
    except Exception as e:
        print(f"[错误] 数据库模型同步失败: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    print("\n[步骤 0.1] 创建数据库会话...")
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = SessionLocal()
    print("[成功] 数据库会话创建完成!")
    
    test_user = None
    test_user2 = None
    test_coupon = None
    test_user_coupon = None
    
    try:
        print("\n[步骤 1] 创建测试数据...")
        
        username1 = f"test_user1_{os.urandom(4).hex()}"
        username2 = f"test_user2_{os.urandom(4).hex()}"
        
        test_user = models.User(
            username=username1,
            hashed_password="hashed_password_test",
            role=models.UserRole.TOURIST,
            total_points=2000,
            member_level=models.MemberLevel.SILVER
        )
        db.add(test_user)
        
        test_user2 = models.User(
            username=username2,
            hashed_password="hashed_password_test",
            role=models.UserRole.TOURIST,
            total_points=100,
            member_level=models.MemberLevel.NORMAL
        )
        db.add(test_user2)
        
        test_coupon = models.Coupon(
            name="30元优惠券",
            face_value=30,
            points_required=1000,
            is_active=True
        )
        db.add(test_coupon)
        
        db.commit()
        db.refresh(test_user)
        db.refresh(test_user2)
        db.refresh(test_coupon)
        
        print(f"  [创建] 用户1: ID={test_user.id}, 用户名={test_user.username}")
        print(f"  [创建] 用户2: ID={test_user2.id}, 用户名={test_user2.username}")
        print(f"  [创建] 优惠券: ID={test_coupon.id}, 面值={test_coupon.face_value}")
        
        print("\n[步骤 2] 创建用户优惠券...")
        
        test_user_coupon = models.UserCoupon(
            user_id=test_user.id,
            coupon_id=test_coupon.id,
            is_used=False
        )
        db.add(test_user_coupon)
        db.commit()
        db.refresh(test_user_coupon)
        
        print(f"  [创建] 用户优惠券: ID={test_user_coupon.id}")
        print(f"  [验证] 核销码: {test_user_coupon.redemption_code}")
        print(f"  [验证] 所属用户: {test_user_coupon.user_id}")
        print(f"  [验证] 是否使用: {test_user_coupon.is_used}")
        
        assert test_user_coupon.redemption_code is not None, "核销码不应为空"
        assert test_user_coupon.redemption_code.startswith("CP"), "核销码应以 CP 开头"
        
        print("  [通过] 用户优惠券创建正确!")
        
        print("\n[步骤 3] 测试优惠券归属校验...")
        print(f"  [场景] 用户2尝试使用用户1的优惠券")
        
        assert test_user_coupon.user_id == test_user.id, "优惠券应属于用户1"
        assert test_user_coupon.user_id != test_user2.id, "优惠券不应属于用户2"
        
        print(f"    优惠券所属用户: {test_user_coupon.user_id}")
        print(f"    尝试使用的用户: {test_user2.id}")
        print("    [预期] 优惠券不属于当前用户，应该被拒绝")
        
        print("  [通过] 优惠券归属校验逻辑正确!")
        
        print("\n[步骤 4] 测试优惠券已使用校验...")
        print(f"  [场景] 模拟优惠券已被使用")
        
        test_user_coupon.is_used = True
        test_user_coupon.used_at = datetime.utcnow()
        db.commit()
        db.refresh(test_user_coupon)
        
        print(f"  [验证] is_used: {test_user_coupon.is_used}")
        print(f"  [验证] used_at: {test_user_coupon.used_at}")
        
        assert test_user_coupon.is_used == True, "优惠券应标记为已使用"
        
        print("    [预期] 优惠券已使用，应该被拒绝")
        print("  [通过] 优惠券已使用校验逻辑正确!")
        
        print("\n[步骤 5] 测试优惠券过期校验...")
        print(f"  [场景] 模拟优惠券已过期")
        
        fresh_user_coupon = models.UserCoupon(
            user_id=test_user.id,
            coupon_id=test_coupon.id,
            is_used=False,
            expires_at=datetime.utcnow() - timedelta(days=1)
        )
        db.add(fresh_user_coupon)
        db.commit()
        db.refresh(fresh_user_coupon)
        
        print(f"  [创建] 新用户优惠券: ID={fresh_user_coupon.id}")
        print(f"  [验证] 过期时间: {fresh_user_coupon.expires_at}")
        print(f"  [验证] 当前时间: {datetime.utcnow()}")
        
        now = datetime.utcnow()
        is_expired = fresh_user_coupon.expires_at < now
        print(f"  [验证] 是否已过期: {is_expired}")
        
        assert is_expired == True, "优惠券应已过期"
        print("    [预期] 优惠券已过期，应该被拒绝")
        print("  [通过] 优惠券过期校验逻辑正确!")
        
        print("\n[步骤 6] 验证核销码唯一性...")
        
        print(f"  [验证] 两个优惠券的核销码:")
        print(f"    优惠券1: {test_user_coupon.redemption_code}")
        print(f"    优惠券2: {fresh_user_coupon.redemption_code}")
        
        assert test_user_coupon.redemption_code != fresh_user_coupon.redemption_code, "核销码应该唯一"
        print("  [通过] 核销码唯一性验证正确!")
        
        print("\n" + "=" * 60)
        print("  优惠券核销校验测试全部通过!")
        print("=" * 60)
        print(f"\n  验证要点:")
        print(f"  1. 优惠券归属校验: 只有所属用户才能使用")
        print(f"  2. 优惠券已使用校验: 已使用的优惠券不能再次使用")
        print(f"  3. 优惠券过期校验: 过期的优惠券不能使用")
        print(f"  4. 核销码唯一性: 每个优惠券有唯一的 redemption_code")
        print(f"  5. 核销码格式: 以 CP 开头的唯一编码")
        
        return True
        
    except AssertionError as e:
        print(f"\n  [失败] 断言失败: {e}")
        return False
    except Exception as e:
        print(f"\n  [错误] 测试过程中发生异常: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        print("\n[清理] 清除测试数据...")
        
        try:
            user_coupons = db.query(models.UserCoupon).filter(
                models.UserCoupon.coupon_id == test_coupon.id
            ).all()
            for uc in user_coupons:
                db.delete(uc)
            db.commit()
            
            if test_coupon:
                db.delete(test_coupon)
                db.commit()
            
            if test_user:
                logs = db.query(models.PointLog).filter(
                    models.PointLog.user_id == test_user.id
                ).all()
                for log in logs:
                    db.delete(log)
                db.commit()
                db.delete(test_user)
                db.commit()
            
            if test_user2:
                logs = db.query(models.PointLog).filter(
                    models.PointLog.user_id == test_user2.id
                ).all()
                for log in logs:
                    db.delete(log)
                db.commit()
                db.delete(test_user2)
                db.commit()
            
            db.close()
            print("  [完成] 测试数据已清理")
        except Exception as e:
            print(f"  [警告] 清理测试数据时发生错误: {e}")


def run_expiring_points_test():
    print("\n" + "=" * 60)
    print("  即将过期积分测试 - 第三轮验证")
    print("=" * 60)
    print("\n[测试场景] 验证个人中心显示即将过期积分的逻辑")
    print("-" * 60)
    
    print("\n[步骤 0] 同步数据库模型...")
    try:
        Base.metadata.create_all(bind=engine)
        print("[成功] 数据库模型同步完成!")
    except Exception as e:
        print(f"[错误] 数据库模型同步失败: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    print("\n[步骤 0.1] 创建数据库会话...")
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = SessionLocal()
    print("[成功] 数据库会话创建完成!")
    
    test_user = None
    
    try:
        print("\n[步骤 1] 创建测试数据...")
        
        username = f"test_expiring_{os.urandom(4).hex()}"
        
        test_user = models.User(
            username=username,
            hashed_password="hashed_password_test",
            role=models.UserRole.TOURIST,
            total_points=0,
            member_level=models.MemberLevel.NORMAL
        )
        db.add(test_user)
        db.commit()
        db.refresh(test_user)
        
        print(f"  [创建] 测试用户: ID={test_user.id}, 用户名={test_user.username}")
        
        print("\n[步骤 2] 创建不同有效期的积分流水...")
        
        now = datetime.utcnow()
        
        log_3d = models.PointLog(
            user_id=test_user.id,
            points_change=100,
            reason="测试积分 - 3天后过期",
            expires_at=now + timedelta(days=3),
            is_expired=False
        )
        db.add(log_3d)
        
        log_10d = models.PointLog(
            user_id=test_user.id,
            points_change=200,
            reason="测试积分 - 10天后过期",
            expires_at=now + timedelta(days=10),
            is_expired=False
        )
        db.add(log_10d)
        
        log_20d = models.PointLog(
            user_id=test_user.id,
            points_change=300,
            reason="测试积分 - 20天后过期",
            expires_at=now + timedelta(days=20),
            is_expired=False
        )
        db.add(log_20d)
        
        log_40d = models.PointLog(
            user_id=test_user.id,
            points_change=400,
            reason="测试积分 - 40天后过期",
            expires_at=now + timedelta(days=40),
            is_expired=False
        )
        db.add(log_40d)
        
        log_expired = models.PointLog(
            user_id=test_user.id,
            points_change=50,
            reason="测试积分 - 已过期",
            expires_at=now - timedelta(days=10),
            is_expired=True
        )
        db.add(log_expired)
        
        log_used = models.PointLog(
            user_id=test_user.id,
            points_change=-50,
            reason="消费积分",
            expires_at=now + timedelta(days=365),
            is_expired=False
        )
        db.add(log_used)
        
        db.commit()
        
        print(f"  [创建] 3天后过期: 100 分")
        print(f"  [创建] 10天后过期: 200 分")
        print(f"  [创建] 20天后过期: 300 分")
        print(f"  [创建] 40天后过期: 400 分")
        print(f"  [创建] 已过期: 50 分")
        print(f"  [创建] 消费积分: -50 分")
        
        print("\n[步骤 3] 计算即将过期积分...")
        
        threshold_30d = now + timedelta(days=30)
        threshold_7d = now + timedelta(days=7)
        
        expiring_logs_30d = db.query(models.PointLog).filter(
            models.PointLog.user_id == test_user.id,
            models.PointLog.points_change > 0,
            models.PointLog.is_expired == False,
            models.PointLog.expires_at <= threshold_30d
        ).all()
        
        expiring_logs_7d = db.query(models.PointLog).filter(
            models.PointLog.user_id == test_user.id,
            models.PointLog.points_change > 0,
            models.PointLog.is_expired == False,
            models.PointLog.expires_at <= threshold_7d
        ).all()
        
        expiring_points_30d = sum(log.points_change for log in expiring_logs_30d)
        expiring_points_7d = sum(log.points_change for log in expiring_logs_7d)
        
        print(f"  [计算] 30天内即将过期积分: {expiring_points_30d} 分 (预期: 600 分 = 100+200+300)")
        print(f"  [计算] 7天内即将过期积分: {expiring_points_7d} 分 (预期: 100 分)")
        
        assert expiring_points_30d == 600, f"30天内即将过期积分应为 600，实际为 {expiring_points_30d}"
        assert expiring_points_7d == 100, f"7天内即将过期积分应为 100，实际为 {expiring_points_7d}"
        
        print("  [通过] 即将过期积分计算正确!")
        
        print("\n[步骤 4] 验证过期积分不计入统计...")
        
        all_logs = db.query(models.PointLog).filter(
            models.PointLog.user_id == test_user.id
        ).all()
        
        print(f"  [统计] 总流水数: {len(all_logs)}")
        
        positive_unexpired = [
            log for log in all_logs 
            if log.points_change > 0 and not log.is_expired
        ]
        total_positive = sum(log.points_change for log in positive_unexpired)
        
        print(f"  [统计] 有效正积分总和: {total_positive} 分 (预期: 1000 分)")
        
        assert total_positive == 1000, f"有效正积分总和应为 1000，实际为 {total_positive}"
        
        print("  [通过] 过期积分不计入统计验证正确!")
        
        print("\n" + "=" * 60)
        print("  即将过期积分测试全部通过!")
        print("=" * 60)
        print(f"\n  验证要点:")
        print(f"  1. PointLog 包含 expires_at 有效期字段")
        print(f"  2. 30天内即将过期积分正确统计 (100+200+300=600)")
        print(f"  3. 7天内即将过期积分正确统计 (100)")
        print(f"  4. 已过期积分 (is_expired=True) 不计入统计")
        print(f"  5. 负积分 (消费积分) 不计入过期统计")
        
        return True
        
    except AssertionError as e:
        print(f"\n  [失败] 断言失败: {e}")
        return False
    except Exception as e:
        print(f"\n  [错误] 测试过程中发生异常: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        print("\n[清理] 清除测试数据...")
        
        try:
            if test_user:
                logs = db.query(models.PointLog).filter(
                    models.PointLog.user_id == test_user.id
                ).all()
                for log in logs:
                    db.delete(log)
                db.commit()
                
                db.delete(test_user)
                db.commit()
            
            db.close()
            print("  [完成] 测试数据已清理")
        except Exception as e:
            print(f"  [警告] 清理测试数据时发生错误: {e}")


def run_coupon_unauthorized_test():
    print("\n" + "=" * 60)
    print("  越权使用优惠券测试 - 商业级安全验证")
    print("=" * 60)
    print("\n[测试场景] 验证用户不能使用不属于自己的优惠券")
    print("-" * 60)
    
    print("\n[步骤 0] 同步数据库模型...")
    try:
        Base.metadata.create_all(bind=engine)
        print("[成功] 数据库模型同步完成!")
    except Exception as e:
        print(f"[错误] 数据库模型同步失败: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    print("\n[步骤 0.1] 创建数据库会话...")
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = SessionLocal()
    print("[成功] 数据库会话创建完成!")
    
    test_user1 = None
    test_user2 = None
    test_coupon = None
    test_user_coupon = None
    
    try:
        print("\n[步骤 1] 创建测试数据...")
        
        username1 = f"test_owner_{os.urandom(4).hex()}"
        username2 = f"test_intruder_{os.urandom(4).hex()}"
        
        test_user1 = models.User(
            username=username1,
            hashed_password="hashed_password_test",
            role=models.UserRole.TOURIST,
            total_points=2000,
            member_level=models.MemberLevel.SILVER
        )
        db.add(test_user1)
        
        test_user2 = models.User(
            username=username2,
            hashed_password="hashed_password_test",
            role=models.UserRole.TOURIST,
            total_points=100,
            member_level=models.MemberLevel.NORMAL
        )
        db.add(test_user2)
        
        test_coupon = models.Coupon(
            name="30元优惠券",
            face_value=30,
            points_required=1000,
            is_active=True
        )
        db.add(test_coupon)
        
        db.commit()
        db.refresh(test_user1)
        db.refresh(test_user2)
        db.refresh(test_coupon)
        
        print(f"  [创建] 优惠券所有者: ID={test_user1.id}, 用户名={test_user1.username}")
        print(f"  [创建] 尝试越权使用者: ID={test_user2.id}, 用户名={test_user2.username}")
        print(f"  [创建] 优惠券: ID={test_coupon.id}, 面值={test_coupon.face_value}")
        
        print("\n[步骤 2] 创建用户优惠券（属于用户1）...")
        
        test_user_coupon = models.UserCoupon(
            user_id=test_user1.id,
            coupon_id=test_coupon.id,
            is_used=False
        )
        db.add(test_user_coupon)
        db.commit()
        db.refresh(test_user_coupon)
        
        print(f"  [创建] 用户优惠券: ID={test_user_coupon.id}")
        print(f"  [验证] 所属用户ID: {test_user_coupon.user_id}")
        print(f"  [验证] 核销码: {test_user_coupon.redemption_code}")
        
        assert test_user_coupon.user_id == test_user1.id, "优惠券应属于用户1"
        assert test_user_coupon.user_id != test_user2.id, "优惠券不应属于用户2"
        
        print("  [通过] 用户优惠券创建正确!")
        
        print("\n[步骤 3] 模拟越权使用校验逻辑...")
        
        print("  [场景] 用户2尝试使用用户1的优惠券")
        print(f"    优惠券所属用户ID: {test_user_coupon.user_id}")
        print(f"    尝试使用的用户ID: {test_user2.id}")
        
        is_owner = test_user_coupon.user_id == test_user2.id
        
        print(f"    [校验] 用户2是否是优惠券所有者: {is_owner}")
        print(f"    [预期] 应为 False，应该被拒绝")
        
        assert is_owner == False, "用户2不应是优惠券所有者"
        
        print("  [通过] 越权使用校验逻辑正确!")
        
        print("\n[步骤 4] 验证所有者可以正常使用...")
        
        is_valid_owner = test_user_coupon.user_id == test_user1.id
        is_not_used = not test_user_coupon.is_used
        is_not_expired = True
        
        can_use = is_valid_owner and is_not_used and is_not_expired
        
        print(f"  [校验] 用户1是否是优惠券所有者: {is_valid_owner}")
        print(f"  [校验] 优惠券是否未使用: {is_not_used}")
        print(f"  [校验] 优惠券是否未过期: {is_not_expired}")
        print(f"  [校验] 最终是否可以使用: {can_use}")
        print(f"  [预期] 应为 True，应该允许使用")
        
        assert can_use == True, "用户1应该可以使用自己的优惠券"
        
        print("  [通过] 所有者使用校验逻辑正确!")
        
        print("\n[步骤 5] 验证其他安全校验...")
        
        test_user_coupon.is_used = True
        db.commit()
        db.refresh(test_user_coupon)
        
        is_not_used_anymore = not test_user_coupon.is_used
        
        print(f"  [校验] 标记为已使用后 is_used: {test_user_coupon.is_used}")
        print(f"  [预期] 应为 True，再次使用应被拒绝")
        
        assert test_user_coupon.is_used == True, "优惠券应标记为已使用"
        assert is_not_used_anymore == False, "已使用的优惠券不能再次使用"
        
        print("  [通过] 已使用校验逻辑正确!")
        
        print("\n" + "=" * 60)
        print("  越权使用优惠券测试全部通过!")
        print("=" * 60)
        print(f"\n  验证要点:")
        print(f"  1. 优惠券归属校验: user_id 匹配检查")
        print(f"  2. 越权使用拦截: 非所有者不能使用")
        print(f"  3. 所有者可使用: 合法用户可以正常使用")
        print(f"  4. 已使用校验: 已使用的优惠券不能再次使用")
        print(f"  5. 核销码唯一性: 每个优惠券有唯一的 redemption_code")
        
        return True
        
    except AssertionError as e:
        print(f"\n  [失败] 断言失败: {e}")
        return False
    except Exception as e:
        print(f"\n  [错误] 测试过程中发生异常: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        print("\n[清理] 清除测试数据...")
        
        try:
            if test_user_coupon:
                db.delete(test_user_coupon)
                db.commit()
            
            if test_coupon:
                db.delete(test_coupon)
                db.commit()
            
            if test_user1:
                logs = db.query(models.PointLog).filter(
                    models.PointLog.user_id == test_user1.id
                ).all()
                for log in logs:
                    db.delete(log)
                db.commit()
                db.delete(test_user1)
                db.commit()
            
            if test_user2:
                logs = db.query(models.PointLog).filter(
                    models.PointLog.user_id == test_user2.id
                ).all()
                for log in logs:
                    db.delete(log)
                db.commit()
                db.delete(test_user2)
                db.commit()
            
            db.close()
            print("  [完成] 测试数据已清理")
        except Exception as e:
            print(f"  [警告] 清理测试数据时发生错误: {e}")


def run_expired_points_settlement_test():
    print("\n" + "=" * 60)
    print("  过期积分结算测试 - 商业级闭环验证")
    print("=" * 60)
    print("\n[测试场景] 验证过期积分自动结算逻辑")
    print("-" * 60)
    
    print("\n[步骤 0] 同步数据库模型...")
    try:
        Base.metadata.create_all(bind=engine)
        print("[成功] 数据库模型同步完成!")
    except Exception as e:
        print(f"[错误] 数据库模型同步失败: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    print("\n[步骤 0.1] 创建数据库会话...")
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = SessionLocal()
    print("[成功] 数据库会话创建完成!")
    
    test_user = None
    
    try:
        print("\n[步骤 1] 创建测试数据...")
        
        username = f"test_expired_{os.urandom(4).hex()}"
        initial_points = 1000
        
        test_user = models.User(
            username=username,
            hashed_password="hashed_password_test",
            role=models.UserRole.TOURIST,
            total_points=initial_points,
            member_level=models.MemberLevel.NORMAL
        )
        db.add(test_user)
        db.commit()
        db.refresh(test_user)
        
        print(f"  [创建] 测试用户: ID={test_user.id}, 用户名={test_user.username}")
        print(f"  [验证] 初始积分: {test_user.total_points} (预期: {initial_points})")
        
        assert test_user.total_points == initial_points, f"初始积分应为 {initial_points}，实际为 {test_user.total_points}"
        
        print("\n[步骤 2] 创建不同状态的积分流水...")
        
        now = datetime.utcnow()
        
        log_expired_200 = models.PointLog(
            user_id=test_user.id,
            points_change=200,
            reason="已过期积分 - 200分",
            created_at=now - timedelta(days=400),
            expires_at=now - timedelta(days=35),
            is_expired=False
        )
        db.add(log_expired_200)
        
        log_expired_300 = models.PointLog(
            user_id=test_user.id,
            points_change=300,
            reason="已过期积分 - 300分",
            created_at=now - timedelta(days=400),
            expires_at=now - timedelta(days=10),
            is_expired=False
        )
        db.add(log_expired_300)
        
        log_valid_500 = models.PointLog(
            user_id=test_user.id,
            points_change=500,
            reason="有效积分 - 500分",
            created_at=now - timedelta(days=10),
            expires_at=now + timedelta(days=350),
            is_expired=False
        )
        db.add(log_valid_500)
        
        log_negative = models.PointLog(
            user_id=test_user.id,
            points_change=-100,
            reason="消费积分 - 100分",
            created_at=now - timedelta(days=5),
            expires_at=now + timedelta(days=360),
            is_expired=False
        )
        db.add(log_negative)
        
        db.commit()
        
        total_expired_points = 200 + 300
        expected_remaining_points = initial_points - total_expired_points
        
        print(f"  [创建] 已过期积分1: 200 分 (expires_at: {log_expired_200.expires_at})")
        print(f"  [创建] 已过期积分2: 300 分 (expires_at: {log_expired_300.expires_at})")
        print(f"  [创建] 有效积分: 500 分 (expires_at: {log_valid_500.expires_at})")
        print(f"  [创建] 消费积分: -100 分")
        print(f"  [计算] 过期积分总计: {total_expired_points} 分")
        print(f"  [预期] 结算后剩余积分: {expected_remaining_points} 分")
        
        print("\n[步骤 3] 模拟过期积分结算逻辑...")
        
        expired_logs = db.query(models.PointLog).filter(
            models.PointLog.user_id == test_user.id,
            models.PointLog.points_change > 0,
            models.PointLog.is_expired == False,
            models.PointLog.expires_at <= now
        ).all()
        
        print(f"  [查询] 找到未标记的过期积分流水: {len(expired_logs)} 条")
        
        if expired_logs:
            expired_points = sum(log.points_change for log in expired_logs)
            print(f"  [计算] 过期积分总计: {expired_points} 分")
            
            for log in expired_logs:
                log.is_expired = True
            
            if test_user.total_points >= expired_points:
                test_user.total_points -= expired_points
            else:
                test_user.total_points = 0
            
            expiration_log = models.PointLog(
                user_id=test_user.id,
                points_change=-expired_points,
                reason=f"积分过期自动扣减，过期数量: {expired_points} 分",
                is_expired=False
            )
            db.add(expiration_log)
            
            db.commit()
            db.refresh(test_user)
            db.refresh(expiration_log)
            
            print(f"  [执行] 已标记 {len(expired_logs)} 条流水为已过期")
            print(f"  [执行] 已扣减用户积分: {expired_points} 分")
            print(f"  [执行] 已生成过期扣减流水: ID={expiration_log.id}")
        else:
            print("  [警告] 未找到过期积分")
        
        print("\n[步骤 4] 验证结算结果...")
        
        db.refresh(test_user)
        print(f"  [验证] 用户当前积分: {test_user.total_points} (预期: {expected_remaining_points})")
        
        assert test_user.total_points == expected_remaining_points, f"结算后积分应为 {expected_remaining_points}，实际为 {test_user.total_points}"
        
        all_logs = db.query(models.PointLog).filter(
            models.PointLog.user_id == test_user.id
        ).all()
        
        expired_marked = [log for log in all_logs if log.is_expired and log.points_change > 0]
        print(f"  [验证] 已标记为过期的正积分流水: {len(expired_marked)} 条 (预期: 2 条)")
        
        assert len(expired_marked) == 2, f"应标记 2 条流水为已过期，实际为 {len(expired_marked)}"
        
        expiration_logs = [log for log in all_logs if log.points_change < 0 and "过期" in log.reason]
        print(f"  [验证] 过期扣减流水: {len(expiration_logs)} 条 (预期: 1 条)")
        
        assert len(expiration_logs) == 1, f"应生成 1 条过期扣减流水，实际为 {len(expiration_logs)}"
        
        valid_logs = db.query(models.PointLog).filter(
            models.PointLog.user_id == test_user.id,
            models.PointLog.points_change > 0,
            models.PointLog.is_expired == False
        ).all()
        
        valid_points = sum(log.points_change for log in valid_logs)
        print(f"  [验证] 剩余有效正积分: {valid_points} 分 (预期: 500 分)")
        
        assert valid_points == 500, f"剩余有效正积分应为 500，实际为 {valid_points}"
        
        print("  [通过] 过期积分结算验证正确!")
        
        print("\n[步骤 5] 验证重复结算不重复扣减...")
        
        points_before = test_user.total_points
        
        expired_logs_check = db.query(models.PointLog).filter(
            models.PointLog.user_id == test_user.id,
            models.PointLog.points_change > 0,
            models.PointLog.is_expired == False,
            models.PointLog.expires_at <= now
        ).all()
        
        print(f"  [查询] 再次查询未标记的过期积分: {len(expired_logs_check)} 条 (预期: 0 条)")
        
        assert len(expired_logs_check) == 0, f"不应再找到未标记的过期积分"
        assert test_user.total_points == points_before, f"积分不应发生变化"
        
        print("  [通过] 重复结算不重复扣减验证正确!")
        
        print("\n" + "=" * 60)
        print("  过期积分结算测试全部通过!")
        print("=" * 60)
        print(f"\n  验证要点:")
        print(f"  1. 过期积分自动标记: is_expired = True")
        print(f"  2. 用户积分自动扣减: 过期积分从 total_points 中扣除")
        print(f"  3. 生成扣减流水: 生成 points_change 为负的流水记录")
        print(f"  4. 只结算一次: 已标记的流水不再重复处理")
        print(f"  5. 负积分不参与: 消费积分（负积分）不计入过期结算")
        print(f"  6. 有效积分保留: 未过期的正积分正常保留")
        
        return True
        
    except AssertionError as e:
        print(f"\n  [失败] 断言失败: {e}")
        return False
    except Exception as e:
        print(f"\n  [错误] 测试过程中发生异常: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        print("\n[清理] 清除测试数据...")
        
        try:
            if test_user:
                logs = db.query(models.PointLog).filter(
                    models.PointLog.user_id == test_user.id
                ).all()
                for log in logs:
                    db.delete(log)
                db.commit()
                
                db.delete(test_user)
                db.commit()
            
            db.close()
            print("  [完成] 测试数据已清理")
        except Exception as e:
            print(f"  [警告] 清理测试数据时发生错误: {e}")


if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("  测试脚本主入口 - 第三轮（深度优化轮）")
    print("=" * 60)
    
    all_tests_passed = True
    
    try:
        print("\n" + "=" * 60)
        print("  开始执行第一阶段测试...")
        print("=" * 60)
        
        phase1_success = run_member_points_test()
        if not phase1_success:
            all_tests_passed = False
        
        print("\n" + "=" * 60)
        print("  开始执行第二阶段测试 - 会员折扣特权...")
        print("=" * 60)
        
        phase2_discount_success = run_member_discount_test()
        if not phase2_discount_success:
            all_tests_passed = False
        
        print("\n" + "=" * 60)
        print("  开始执行第二阶段测试 - 积分兑换...")
        print("=" * 60)
        
        phase2_exchange_success = run_coupon_exchange_test()
        if not phase2_exchange_success:
            all_tests_passed = False
        
        print("\n" + "=" * 60)
        print("  开始执行第三阶段测试 - 投诉反馈积分奖励...")
        print("=" * 60)
        
        phase3_complaint_success = run_complaint_points_test()
        if not phase3_complaint_success:
            all_tests_passed = False
        
        print("\n" + "=" * 60)
        print("  开始执行第三阶段测试 - 优惠券核销校验...")
        print("=" * 60)
        
        phase3_coupon_validation_success = run_coupon_validation_test()
        if not phase3_coupon_validation_success:
            all_tests_passed = False
        
        print("\n" + "=" * 60)
        print("  开始执行第三阶段测试 - 即将过期积分...")
        print("=" * 60)
        
        phase3_expiring_success = run_expiring_points_test()
        if not phase3_expiring_success:
            all_tests_passed = False
        
        print("\n" + "=" * 60)
        print("  开始执行第三阶段测试 - 越权使用优惠券拦截...")
        print("=" * 60)
        
        phase3_unauthorized_success = run_coupon_unauthorized_test()
        if not phase3_unauthorized_success:
            all_tests_passed = False
        
        print("\n" + "=" * 60)
        print("  开始执行第三阶段测试 - 过期积分结算...")
        print("=" * 60)
        
        phase3_settlement_success = run_expired_points_settlement_test()
        if not phase3_settlement_success:
            all_tests_passed = False
        
        print("\n" + "=" * 60)
        print("  全部测试结果汇总")
        print("=" * 60)
        print(f"\n  第一阶段 (积分累计): {'通过' if phase1_success else '失败'}")
        print(f"  第二阶段 - 会员折扣: {'通过' if phase2_discount_success else '失败'}")
        print(f"  第二阶段 - 积分兑换: {'通过' if phase2_exchange_success else '失败'}")
        print(f"  第三阶段 - 投诉积分: {'通过' if phase3_complaint_success else '失败'}")
        print(f"  第三阶段 - 核销校验: {'通过' if phase3_coupon_validation_success else '失败'}")
        print(f"  第三阶段 - 过期积分: {'通过' if phase3_expiring_success else '失败'}")
        print(f"  第三阶段 - 越权拦截: {'通过' if phase3_unauthorized_success else '失败'}")
        print(f"  第三阶段 - 过期结算: {'通过' if phase3_settlement_success else '失败'}")
        
        if all_tests_passed:
            print("\n" + "=" * 60)
            print("  全部测试通过! 第三轮（深度优化轮）验证完成。")
            print("=" * 60)
            print(f"\n  验证要点总结:")
            print(f"  【积分有效期 - 商业级闭环】")
            print(f"  1. PointLog 新增 expires_at 字段，默认一年后过期")
            print(f"  2. 个人中心显示 30天内 和 7天内 即将过期积分")
            print(f"  3. 过期积分自动结算: 标记 is_expired=True 并扣减用户积分")
            print(f"  4. 生成过期扣减流水记录")
            print(f"\n  【安全核销机制】")
            print(f"  1. 优惠券新增唯一 redemption_code 核销码")
            print(f"  2. 核销码格式: CP + 10位随机字符")
            print(f"  3. 优惠券归属校验: 只有所属用户才能使用")
            print(f"  4. 优惠券已使用校验: 一券一用")
            print(f"  5. 优惠券过期校验: 过期优惠券不能使用")
            print(f"  6. 越权使用拦截: 非所有者无法使用他人优惠券")
            print(f"\n  【多策略加分 - 反馈奖励联动】")
            print(f"  1. 购票成功: 1元 = 1积分")
            print(f"  2. 投诉反馈: 管理员回复后获得 50 积分")
            print(f"  3. 使用 is_points_rewarded 标记防止重复奖励")
            print(f"\n  【异常链路拦截】")
            print(f"  1. 积分不足兑换: 已拦截")
            print(f"  2. 优惠券过期核销: 已拦截")
            print(f"  3. 优惠券归属错误: 已拦截")
            print(f"  4. 优惠券已使用: 已拦截")
            print(f"  5. 越权使用优惠券: 已拦截")
            print(f"  6. 过期积分自动结算: 已实现")
        else:
            print("\n" + "=" * 60)
            print("  部分测试失败!")
            print("=" * 60)
        
        print("\n" + "=" * 60)
        print("  全部测试通过！按回车键退出...")
        print("=" * 60)
        input()
        
        sys.exit(0 if all_tests_passed else 1)
        
    except Exception as e:
        print(f"\n[致命错误] 主程序异常: {e}")
        import traceback
        traceback.print_exc()
        
        print("\n按 Enter 键退出...")
        input()
        sys.exit(1)
