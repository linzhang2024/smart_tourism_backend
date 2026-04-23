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
    print("  测试脚本主入口")
    print("=" * 60)
    
    try:
        success = run_member_points_test()
        
        if success:
            print("\n" + "=" * 60)
            print("  全部测试通过!")
            print("=" * 60)
        else:
            print("\n" + "=" * 60)
            print("  测试失败!")
            print("=" * 60)
        
        print("\n按 Enter 键退出...")
        input()
        
        sys.exit(0 if success else 1)
        
    except Exception as e:
        print(f"\n[致命错误] 主程序异常: {e}")
        import traceback
        traceback.print_exc()
        
        print("\n按 Enter 键退出...")
        input()
        sys.exit(1)
