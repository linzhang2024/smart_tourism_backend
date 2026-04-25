import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy.orm import sessionmaker
from sqlalchemy import text
from database import engine

Session = sessionmaker(bind=engine)


def verify_database_columns():
    print("=" * 60)
    print("数据库迁移验证")
    print("=" * 60)
    
    db = Session()
    
    try:
        result = db.execute(text("PRAGMA table_info(scenic_spots)"))
        columns = [row[1] for row in result]
        
        print("\n[检查] scenic_spots 表的列:")
        for col in columns:
            print(f"  - {col}")
        
        required_columns = ['capacity', 'current_count', 'status']
        missing_columns = []
        
        print("\n[验证] 检查必需列:")
        for col in required_columns:
            if col in columns:
                print(f"  ✓ {col}: 存在")
            else:
                print(f"  ✗ {col}: 缺失")
                missing_columns.append(col)
        
        if missing_columns:
            print(f"\n[警告] 缺失 {len(missing_columns)} 个必需列，尝试添加...")
            
            for col in missing_columns:
                try:
                    if col == 'capacity':
                        db.execute(text("ALTER TABLE scenic_spots ADD COLUMN capacity INTEGER DEFAULT 100"))
                        print(f"  ✓ 添加 capacity 列成功")
                    elif col == 'current_count':
                        db.execute(text("ALTER TABLE scenic_spots ADD COLUMN current_count INTEGER DEFAULT 0"))
                        print(f"  ✓ 添加 current_count 列成功")
                    elif col == 'status':
                        db.execute(text("ALTER TABLE scenic_spots ADD COLUMN status VARCHAR(20) DEFAULT '正常开放'"))
                        print(f"  ✓ 添加 status 列成功")
                    db.commit()
                except Exception as e:
                    print(f"  ✗ 添加 {col} 列失败: {e}")
                    db.rollback()
            
            result = db.execute(text("PRAGMA table_info(scenic_spots)"))
            columns = [row[1] for row in result]
            
            still_missing = [col for col in required_columns if col not in columns]
            if still_missing:
                print(f"\n[错误] 仍然缺失列: {still_missing}")
                return False
            else:
                print("\n[成功] 所有必需列已添加完成！")
        else:
            print("\n[成功] 所有必需列已存在！")
        
        print("\n[验证] 测试数据操作:")
        
        test_spot_name = f"测试景点_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        
        try:
            result = db.execute(text("""
                INSERT INTO scenic_spots (name, description, location, capacity, current_count, status, rating, price, created_at)
                VALUES (:name, :description, :location, :capacity, :current_count, :status, :rating, :price, :created_at)
            """), {
                "name": test_spot_name,
                "description": "测试数据库迁移",
                "location": "测试位置",
                "capacity": 200,
                "current_count": 160,
                "status": "正常开放",
                "rating": 4.5,
                "price": 50.0,
                "created_at": datetime.now()
            })
            db.commit()
            print(f"  ✓ 插入测试数据成功 (capacity=200, current_count=160)")
            
            result = db.execute(text("""
                SELECT id, name, capacity, current_count, status, (current_count * 1.0 / capacity) as saturation
                FROM scenic_spots 
                WHERE name = :name
            """), {"name": test_spot_name})
            
            row = result.fetchone()
            if row:
                spot_id = row[0]
                spot_name = row[1]
                capacity = row[2]
                current_count = row[3]
                status = row[4]
                saturation = row[5]
                
                print(f"  ✓ 读取测试数据成功:")
                print(f"    - ID: {spot_id}")
                print(f"    - 名称: {spot_name}")
                print(f"    - 最大承载量 (capacity): {capacity}")
                print(f"    - 当前人数 (current_count): {current_count}")
                print(f"    - 状态 (status): {status}")
                print(f"    - 饱和度: {saturation*100:.1f}%")
                
                if saturation >= 0.8:
                    print(f"  ✓ 饱和度 {saturation*100:.1f}% >= 80%，将触发分流推荐")
                else:
                    print(f"  - 饱和度 {saturation*100:.1f}% < 80%，不会触发分流推荐")
            
            db.execute(text("DELETE FROM scenic_spots WHERE name = :name"), {"name": test_spot_name})
            db.commit()
            print(f"  ✓ 清理测试数据成功")
            
        except Exception as e:
            print(f"  ✗ 数据操作失败: {e}")
            import traceback
            traceback.print_exc()
            db.rollback()
            return False
        
        print("\n" + "=" * 60)
        print("数据库迁移验证完成！")
        print("=" * 60)
        
        return True
        
    except Exception as e:
        print(f"\n[错误] 验证过程中发生异常: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        db.close()


def test_core_logic():
    print("\n" + "=" * 60)
    print("核心逻辑验证")
    print("=" * 60)
    
    from main import get_color_level, calculate_distance
    
    print("\n[测试] 颜色预警逻辑:")
    
    test_cases = [
        (0.0, "green", "0% 饱和度"),
        (0.3, "green", "30% 饱和度"),
        (0.39, "green", "39% 饱和度"),
        (0.4, "yellow", "40% 饱和度"),
        (0.5, "yellow", "50% 饱和度"),
        (0.79, "yellow", "79% 饱和度"),
        (0.8, "red", "80% 饱和度"),
        (0.9, "red", "90% 饱和度"),
        (1.0, "red", "100% 饱和度"),
    ]
    
    all_passed = True
    for saturation, expected_color, description in test_cases:
        actual_color = get_color_level(saturation)
        passed = actual_color == expected_color
        if passed:
            print(f"  ✓ {description}: {actual_color} (期望: {expected_color})")
        else:
            print(f"  ✗ {description}: {actual_color} (期望: {expected_color}) - 失败!")
            all_passed = False
    
    print("\n[测试] 分流触发条件:")
    
    diversion_threshold = 0.8
    recommendation_threshold = 0.4
    
    print(f"  分流阈值: {diversion_threshold*100:.0f}%")
    print(f"  推荐阈值: {recommendation_threshold*100:.0f}%")
    
    test_spots = [
        {"name": "景点A", "capacity": 100, "current_count": 85, "expected_trigger": True},
        {"name": "景点B", "capacity": 100, "current_count": 80, "expected_trigger": True},
        {"name": "景点C", "capacity": 100, "current_count": 79, "expected_trigger": False},
        {"name": "景点D", "capacity": 100, "current_count": 39, "expected_recommendable": True},
        {"name": "景点E", "capacity": 100, "current_count": 40, "expected_recommendable": False},
    ]
    
    for spot in test_spots:
        saturation = spot["current_count"] / spot["capacity"]
        
        if "expected_trigger" in spot:
            should_trigger = saturation >= diversion_threshold
            expected = spot["expected_trigger"]
            if should_trigger == expected:
                status = "✓"
            else:
                status = "✗"
                all_passed = False
            print(f"  {status} {spot['name']}: 饱和度={saturation*100:.0f}%, 触发分流={should_trigger} (期望={expected})")
        
        if "expected_recommendable" in spot:
            is_recommendable = saturation < recommendation_threshold
            expected = spot["expected_recommendable"]
            if is_recommendable == expected:
                status = "✓"
            else:
                status = "✗"
                all_passed = False
            print(f"  {status} {spot['name']}: 饱和度={saturation*100:.0f}%, 可推荐={is_recommendable} (期望={expected})")
    
    print("\n[测试] 距离计算:")
    
    beijing_lat, beijing_lng = 39.9042, 116.4074
    tianjin_lat, tianjin_lng = 39.0842, 117.2009
    
    distance = calculate_distance(beijing_lat, beijing_lng, tianjin_lat, tianjin_lng)
    
    expected_min = 100
    expected_max = 150
    
    if expected_min < distance < expected_max:
        print(f"  ✓ 北京到天津距离: {distance:.2f} 公里 (期望范围: {expected_min}-{expected_max} 公里)")
    else:
        print(f"  ✗ 北京到天津距离: {distance:.2f} 公里 (期望范围: {expected_min}-{expected_max} 公里)")
        all_passed = False
    
    same_point = calculate_distance(beijing_lat, beijing_lng, beijing_lat, beijing_lng)
    if same_point < 1:
        print(f"  ✓ 同一点距离: {same_point:.6f} 公里 (期望 < 1 公里)")
    else:
        print(f"  ✗ 同一点距离: {same_point:.6f} 公里 (期望 < 1 公里)")
        all_passed = False
    
    print("\n" + "=" * 60)
    if all_passed:
        print("核心逻辑验证完成！所有测试通过！")
    else:
        print("核心逻辑验证完成！部分测试失败！")
    print("=" * 60)
    
    return all_passed


if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("  全域电子导览与智慧客流管控 - 数据库验证")
    print("=" * 60)
    print(f"  验证时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    db_success = verify_database_columns()
    logic_success = test_core_logic()
    
    print("\n" + "=" * 60)
    print("最终验证结果")
    print("=" * 60)
    
    if db_success and logic_success:
        print("\n  🎉 所有验证通过！数据库迁移已完成，核心逻辑正常工作。")
        print("\n  现在可以运行完整的测试套件:")
        print("    python test_crowd_control.py")
        sys.exit(0)
    else:
        print("\n  ❌ 部分验证失败，请检查上述错误信息。")
        sys.exit(1)
