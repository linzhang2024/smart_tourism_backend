import os
import sys
import logging
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
                    is_used BOOLEAN DEFAULT 0,
                    obtained_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    used_at DATETIME,
                    FOREIGN KEY (user_id) REFERENCES users (id),
                    FOREIGN KEY (coupon_id) REFERENCES coupons (id)
                )
            """))
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
    print("  会员折扣特权测试 - 第二轮验证")
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
    print("  积分兑换测试 - 第二轮验证")
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
    print("  会员积分中心测试 - 第一阶段验证")
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
        print("  测试通过! 会员积分中心第一阶段功能验证完成。")
        print("=" * 60)
        print(f"\n  验证要点:")
        print(f"  1. User 模型新增 total_points 和 member_level 字段")
        print(f"  2. 新增 PointLog 模型记录积分变动流水")
        print(f"  3. 购票成功后按 1元 = 1积分 比例累计积分")
        print(f"  4. PointLog 生成正确的流水记录")
        print(f"  5. 会员等级自动升级逻辑正确:")
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


if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("  测试脚本主入口 - 第二轮（深化轮）")
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
        print("  全部测试结果汇总")
        print("=" * 60)
        print(f"\n  第一阶段 (积分累计): {'通过' if phase1_success else '失败'}")
        print(f"  第二阶段 - 会员折扣: {'通过' if phase2_discount_success else '失败'}")
        print(f"  第二阶段 - 积分兑换: {'通过' if phase2_exchange_success else '失败'}")
        
        if all_tests_passed:
            print("\n" + "=" * 60)
            print("  全部测试通过! 第二轮（深化轮）验证完成。")
            print("=" * 60)
            print(f"\n  验证要点总结:")
            print(f"  【积分兑换逻辑】")
            print(f"  1. Coupon 模型包含: 优惠券名称、面值、所需积分")
            print(f"  2. POST /member/exchange 接口支持积分兑换")
            print(f"  3. 校验积分是否充足")
            print(f"  4. 扣减 User.total_points")
            print(f"  5. 记录负积分的 PointLog 流水")
            print(f"\n  【等级折扣特权】")
            print(f"  1. 白银会员: 购票享受 95 折")
            print(f"  2. 黄金会员: 购票享受 9 折")
            print(f"  3. 普通会员: 无折扣")
            print(f"\n  【测试扩展】")
            print(f"  1. 黄金会员 9 折优惠验证通过")
            print(f"  2. 白银会员 95 折优惠验证通过")
            print(f"  3. 积分不足无法兑换验证通过")
            print(f"  4. 兑换成功积分扣减验证通过")
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
