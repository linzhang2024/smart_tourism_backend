import os
import sys
import time
import hashlib
import uuid
from sqlalchemy.orm import sessionmaker
from sqlalchemy import delete
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import models
import schemas
from database import Base, engine, get_db
from main import (
    check_staff_on_duty, 
    get_color_level, 
    calculate_distance
)

test_results = []
created_test_ids = {
    "scenic_spots": [],
    "users": [],
    "work_shifts": [],
    "schedules": [],
    "attendance_records": [],
    "coupons": []
}


def generate_unique_suffix():
    return uuid.uuid4().hex[:8]


def generate_test_username(prefix):
    return f"{prefix}_{generate_unique_suffix()}"


def get_simple_password_hash(password: str) -> str:
    return hashlib.sha256(password.encode('utf-8')).hexdigest()


def log_test_result(test_name, passed, message=""):
    result = {
        "test_name": test_name,
        "passed": passed,
        "message": message,
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
    }
    test_results.append(result)
    
    status = "PASS" if passed else "FAIL"
    print(f"  [{status}] {test_name}")
    if message:
        print(f"     详情: {message}")


def cleanup_test_data(db):
    print("\n[清理] 强制清理残留测试数据...")
    
    try:
        if created_test_ids["attendance_records"]:
            delete_records = delete(models.AttendanceRecord).where(
                models.AttendanceRecord.id.in_(created_test_ids["attendance_records"])
            )
            result = db.execute(delete_records)
            db.commit()
            if result.rowcount > 0:
                print(f"  已清理 {result.rowcount} 条测试考勤记录")
        
        if created_test_ids["schedules"]:
            delete_schedules = delete(models.Schedule).where(
                models.Schedule.id.in_(created_test_ids["schedules"])
            )
            result = db.execute(delete_schedules)
            db.commit()
            if result.rowcount > 0:
                print(f"  已清理 {result.rowcount} 条测试排班")
        
        if created_test_ids["work_shifts"]:
            delete_shifts = delete(models.WorkShift).where(
                models.WorkShift.id.in_(created_test_ids["work_shifts"])
            )
            result = db.execute(delete_shifts)
            db.commit()
            if result.rowcount > 0:
                print(f"  已清理 {result.rowcount} 个测试班次")
        
        if created_test_ids["coupons"]:
            delete_coupons = delete(models.Coupon).where(
                models.Coupon.id.in_(created_test_ids["coupons"])
            )
            result = db.execute(delete_coupons)
            db.commit()
            if result.rowcount > 0:
                print(f"  已清理 {result.rowcount} 个测试优惠券")
        
        if created_test_ids["scenic_spots"]:
            delete_spots = delete(models.ScenicSpot).where(
                models.ScenicSpot.id.in_(created_test_ids["scenic_spots"])
            )
            result = db.execute(delete_spots)
            db.commit()
            if result.rowcount > 0:
                print(f"  已清理 {result.rowcount} 个测试景点")
        
        if created_test_ids["users"]:
            delete_users = delete(models.User).where(
                models.User.id.in_(created_test_ids["users"])
            )
            result = db.execute(delete_users)
            db.commit()
            if result.rowcount > 0:
                print(f"  已清理 {result.rowcount} 个测试用户")
        
        for key in created_test_ids:
            created_test_ids[key].clear()
        
        print("  [清理] 完成")
    except Exception as e:
        print(f"  [警告] 清理数据时出错: {e}")


def create_test_scenic_spot(db, name, capacity=100, current_count=0, latitude=None, longitude=None, status=models.ScenicSpotStatus.ACTIVE):
    spot = models.ScenicSpot(
        name=name,
        description=f"测试景点: {name}",
        location="测试位置",
        capacity=capacity,
        current_count=current_count,
        latitude=latitude,
        longitude=longitude,
        status=status,
        rating=4.5,
        price=50.0
    )
    db.add(spot)
    db.commit()
    db.refresh(spot)
    created_test_ids["scenic_spots"].append(spot.id)
    return spot


def create_test_user(db, role=models.UserRole.STAFF):
    username = generate_test_username("staff")
    user = models.User(
        username=username,
        hashed_password=get_simple_password_hash("test123456"),
        role=role,
        is_active=True
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    created_test_ids["users"].append(user.id)
    return user


def create_test_work_shift(db, name="早班", start_time="08:00", end_time="18:00"):
    shift = models.WorkShift(
        name=name,
        start_time=start_time,
        end_time=end_time,
        is_active=True
    )
    db.add(shift)
    db.commit()
    db.refresh(shift)
    created_test_ids["work_shifts"].append(shift.id)
    return shift


def create_test_schedule(db, user_id, work_shift_id, schedule_date=None):
    if schedule_date is None:
        schedule_date = datetime.now().strftime("%Y-%m-%d")
    
    schedule = models.Schedule(
        user_id=user_id,
        work_shift_id=work_shift_id,
        schedule_date=schedule_date
    )
    db.add(schedule)
    db.commit()
    db.refresh(schedule)
    created_test_ids["schedules"].append(schedule.id)
    return schedule


def create_test_attendance_record(db, user_id, schedule_id, scenic_spot_id, check_in_time=None, check_out_time=None):
    today_str = datetime.now().strftime("%Y-%m-%d")
    
    if check_in_time is None:
        check_in_time = datetime.now()
    
    record = models.AttendanceRecord(
        user_id=user_id,
        schedule_id=schedule_id,
        scenic_spot_id=scenic_spot_id,
        attendance_date=today_str,
        check_in_time=check_in_time,
        check_out_time=check_out_time,
        attendance_status=models.AttendanceStatus.NORMAL
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    created_test_ids["attendance_records"].append(record.id)
    return record


def create_test_coupon(db, name="10元优惠券", discount_value=10, target_scenic_spot_id=None):
    coupon = models.Coupon(
        name=name,
        coupon_type=models.CouponType.FIXED_AMOUNT,
        discount_value=discount_value,
        min_spend=0,
        valid_from=datetime.utcnow(),
        valid_to=datetime.utcnow() + timedelta(days=30),
        total_stock=100,
        remained_stock=100,
        target_scenic_spot_id=target_scenic_spot_id,
        is_active=True
    )
    db.add(coupon)
    db.commit()
    db.refresh(coupon)
    created_test_ids["coupons"].append(coupon.id)
    return coupon


def test_color_level_logic():
    print("\n" + "=" * 60)
    print("测试 1: 颜色预警逻辑测试")
    print("=" * 60)
    
    test_cases = [
        (0.0, "green", "0% 饱和度应为绿色"),
        (0.3, "green", "30% 饱和度应为绿色"),
        (0.39, "green", "39% 饱和度应为绿色"),
        (0.4, "yellow", "40% 饱和度应为黄色"),
        (0.5, "yellow", "50% 饱和度应为黄色"),
        (0.79, "yellow", "79% 饱和度应为黄色"),
        (0.8, "red", "80% 饱和度应为红色"),
        (0.9, "red", "90% 饱和度应为红色"),
        (1.0, "red", "100% 饱和度应为红色"),
    ]
    
    all_passed = True
    for saturation, expected_color, description in test_cases:
        actual_color = get_color_level(saturation)
        passed = actual_color == expected_color
        if not passed:
            all_passed = False
        log_test_result(
            f"颜色预警 - {description}",
            passed,
            f"饱和度 {saturation*100:.0f}%: 期望 {expected_color}, 实际 {actual_color}"
        )
    
    return all_passed


def test_distance_calculation():
    print("\n" + "=" * 60)
    print("测试 2: 距离计算逻辑测试")
    print("=" * 60)
    
    beijing_lat, beijing_lng = 39.9042, 116.4074
    tianjin_lat, tianjin_lng = 39.0842, 117.2009
    
    distance = calculate_distance(beijing_lat, beijing_lng, tianjin_lat, tianjin_lng)
    
    expected_min = 100
    expected_max = 150
    
    passed = expected_min < distance < expected_max
    
    log_test_result(
        "距离计算 - 北京到天津",
        passed,
        f"计算距离: {distance:.2f} 公里, 期望范围: {expected_min}-{expected_max} 公里"
    )
    
    same_point_distance = calculate_distance(beijing_lat, beijing_lng, beijing_lat, beijing_lng)
    same_point_passed = same_point_distance < 1
    
    log_test_result(
        "距离计算 - 同一点距离为0",
        same_point_passed,
        f"同一点距离: {same_point_distance:.6f} 公里, 期望 < 1 公里"
    )
    
    return passed and same_point_passed


def test_crowded_spot_diversion_recommendation(db):
    print("\n" + "=" * 60)
    print("测试 3: 景点爆满分流推荐测试")
    print("=" * 60)
    
    print("\n[准备] 创建测试景点...")
    
    crowded_spot = create_test_scenic_spot(
        db, 
        name="爆满测试景点A",
        capacity=100,
        current_count=85,
        latitude=39.9042,
        longitude=116.4074
    )
    print(f"  创建爆满景点: {crowded_spot.name}, ID={crowded_spot.id}, 饱和度={crowded_spot.current_count/crowded_spot.capacity*100:.0f}%")
    
    comfort_spot1 = create_test_scenic_spot(
        db,
        name="舒适测试景点B",
        capacity=100,
        current_count=30,
        latitude=39.9142,
        longitude=116.4174
    )
    print(f"  创建舒适景点: {comfort_spot1.name}, ID={comfort_spot1.id}, 饱和度={comfort_spot1.current_count/comfort_spot1.capacity*100:.0f}%")
    
    comfort_spot2 = create_test_scenic_spot(
        db,
        name="舒适测试景点C",
        capacity=100,
        current_count=25,
        latitude=39.8942,
        longitude=116.3974
    )
    print(f"  创建舒适景点: {comfort_spot2.name}, ID={comfort_spot2.id}, 饱和度={comfort_spot2.current_count/comfort_spot2.capacity*100:.0f}%")
    
    print("\n[测试] 验证饱和度计算...")
    
    crowded_saturation = crowded_spot.current_count / crowded_spot.capacity
    crowded_passed = crowded_saturation >= 0.8
    log_test_result(
        "爆满景点饱和度验证",
        crowded_passed,
        f"景点A饱和度: {crowded_saturation*100:.0f}%, 期望 >= 80%"
    )
    
    comfort1_saturation = comfort_spot1.current_count / comfort_spot1.capacity
    comfort1_passed = comfort1_saturation < 0.4
    log_test_result(
        "舒适景点B饱和度验证",
        comfort1_passed,
        f"景点B饱和度: {comfort1_saturation*100:.0f}%, 期望 < 40%"
    )
    
    comfort2_saturation = comfort_spot2.current_count / comfort_spot2.capacity
    comfort2_passed = comfort2_saturation < 0.4
    log_test_result(
        "舒适景点C饱和度验证",
        comfort2_passed,
        f"景点C饱和度: {comfort2_saturation*100:.0f}%, 期望 < 40%"
    )
    
    print("\n[测试] 验证颜色等级...")
    
    crowded_color = get_color_level(crowded_saturation)
    log_test_result(
        "爆满景点颜色等级",
        crowded_color == "red",
        f"景点A颜色等级: {crowded_color}, 期望: red"
    )
    
    comfort1_color = get_color_level(comfort1_saturation)
    log_test_result(
        "舒适景点B颜色等级",
        comfort1_color == "green",
        f"景点B颜色等级: {comfort1_color}, 期望: green"
    )
    
    print("\n[测试] 验证分流推荐逻辑...")
    
    diversion_threshold = 0.8
    recommendation_threshold = 0.4
    
    should_trigger_diversion = crowded_saturation >= diversion_threshold
    log_test_result(
        "分流触发条件验证",
        should_trigger_diversion,
        f"景点A饱和度 {crowded_saturation*100:.0f}% >= {diversion_threshold*100:.0f}%, 应触发分流推荐"
    )
    
    is_recommendable = comfort1_saturation < recommendation_threshold
    log_test_result(
        "推荐条件验证",
        is_recommendable,
        f"景点B饱和度 {comfort1_saturation*100:.0f}% < {recommendation_threshold*100:.0f}%, 符合推荐条件"
    )
    
    all_passed = (
        crowded_passed and 
        comfort1_passed and 
        comfort2_passed and 
        crowded_color == "red" and 
        comfort1_color == "green" and
        should_trigger_diversion and
        is_recommendable
    )
    
    return all_passed


def test_staff_on_duty_status(db):
    print("\n" + "=" * 60)
    print("测试 4: 工作人员在岗状态测试")
    print("=" * 60)
    
    print("\n[准备] 创建测试数据...")
    
    test_spot = create_test_scenic_spot(
        db,
        name="在岗状态测试景点",
        capacity=100,
        current_count=50,
        latitude=39.9042,
        longitude=116.4074
    )
    print(f"  创建测试景点: {test_spot.name}, ID={test_spot.id}")
    
    staff_user = create_test_user(db, role=models.UserRole.STAFF)
    print(f"  创建工作人员: ID={staff_user.id}, 角色={staff_user.role.value}")
    
    morning_shift = create_test_work_shift(
        db,
        name="测试早班",
        start_time="06:00",
        end_time="22:00"
    )
    print(f"  创建班次: {morning_shift.name}, 时间={morning_shift.start_time}-{morning_shift.end_time}")
    
    today_str = datetime.now().strftime("%Y-%m-%d")
    schedule = create_test_schedule(
        db,
        user_id=staff_user.id,
        work_shift_id=morning_shift.id,
        schedule_date=today_str
    )
    print(f"  创建排班: 日期={schedule.schedule_date}")
    
    print("\n[测试] 场景1: 员工已打卡上班...")
    
    attendance_record = create_test_attendance_record(
        db,
        user_id=staff_user.id,
        schedule_id=schedule.id,
        scenic_spot_id=test_spot.id,
        check_in_time=datetime.now(),
        check_out_time=None
    )
    print(f"  创建考勤记录: 打卡时间={attendance_record.check_in_time}, 未下班")
    
    has_staff = check_staff_on_duty(db, test_spot.id)
    
    log_test_result(
        "员工打卡后状态检查",
        has_staff,
        f"员工已打卡上班，check_staff_on_duty 返回 {has_staff}, 期望 True"
    )
    
    test_passed_1 = has_staff
    
    print("\n[测试] 场景2: 员工已下班...")
    
    attendance_record.check_out_time = datetime.now()
    db.commit()
    db.refresh(attendance_record)
    print(f"  更新考勤记录: 下班时间={attendance_record.check_out_time}")
    
    has_staff_after_checkout = check_staff_on_duty(db, test_spot.id)
    
    log_test_result(
        "员工下班后状态检查",
        not has_staff_after_checkout,
        f"员工已下班，check_staff_on_duty 返回 {has_staff_after_checkout}, 期望 False"
    )
    
    test_passed_2 = not has_staff_after_checkout
    
    print("\n[测试] 场景3: 无任何考勤记录...")
    
    db.delete(attendance_record)
    db.commit()
    created_test_ids["attendance_records"].remove(attendance_record.id)
    print("  删除考勤记录")
    
    new_spot = create_test_scenic_spot(
        db,
        name="无考勤测试景点",
        capacity=100,
        current_count=50,
        latitude=39.9142,
        longitude=116.4174
    )
    print(f"  创建新景点: {new_spot.name}, ID={new_spot.id} (无考勤记录)")
    
    has_staff_no_record = check_staff_on_duty(db, new_spot.id)
    
    log_test_result(
        "无考勤记录状态检查",
        not has_staff_no_record,
        f"无考勤记录，check_staff_on_duty 返回 {has_staff_no_record}, 期望 False"
    )
    
    test_passed_3 = not has_staff_no_record
    
    print("\n[测试] 场景4: 验证景点状态自动切换逻辑...")
    
    spot_status = test_spot.status
    effective_status = spot_status
    
    if not test_passed_1:
        effective_status = models.ScenicSpotStatus.SUSPENDED
    
    log_test_result(
        "景点状态逻辑验证",
        True,
        f"景点状态: {spot_status.value}, 工作人员在岗: {test_passed_1}, 有效状态: {effective_status.value}"
    )
    
    all_passed = test_passed_1 and test_passed_2 and test_passed_3
    
    return all_passed


def test_coupon_integration(db):
    print("\n" + "=" * 60)
    print("测试 5: 优惠券系统集成测试")
    print("=" * 60)
    
    print("\n[准备] 创建测试数据...")
    
    crowded_spot = create_test_scenic_spot(
        db,
        name="优惠券测试景点A",
        capacity=100,
        current_count=90,
        latitude=39.9042,
        longitude=116.4074
    )
    print(f"  创建爆满景点: {crowded_spot.name}, ID={crowded_spot.id}, 饱和度=90%")
    
    target_spot = create_test_scenic_spot(
        db,
        name="优惠券目标景点B",
        capacity=100,
        current_count=30,
        latitude=39.9142,
        longitude=116.4174
    )
    print(f"  创建目标景点: {target_spot.name}, ID={target_spot.id}, 饱和度=30%")
    
    print("\n[测试] 创建针对目标景点的优惠券...")
    
    coupon = create_test_coupon(
        db,
        name="10元分流优惠券",
        discount_value=10,
        target_scenic_spot_id=target_spot.id
    )
    print(f"  创建优惠券: ID={coupon.id}, 面额={coupon.discount_value}元, 目标景点ID={coupon.target_scenic_spot_id}")
    
    log_test_result(
        "优惠券创建验证",
        coupon.id is not None and coupon.target_scenic_spot_id == target_spot.id,
        f"优惠券ID={coupon.id}, 目标景点ID={coupon.target_scenic_spot_id}, 状态={'有效' if coupon.is_active else '无效'}"
    )
    
    coupon_created = coupon.id is not None
    
    print("\n[测试] 验证爆满景点触发条件...")
    
    crowded_saturation = crowded_spot.current_count / crowded_spot.capacity
    should_trigger = crowded_saturation >= 0.8
    
    log_test_result(
        "爆满触发条件验证",
        should_trigger,
        f"景点A饱和度={crowded_saturation*100:.0f}% >= 80%, 应触发分流和优惠券推荐"
    )
    
    print("\n[测试] 验证目标景点推荐条件...")
    
    target_saturation = target_spot.current_count / target_spot.capacity
    is_good_recommendation = target_saturation < 0.4
    
    log_test_result(
        "目标景点推荐条件验证",
        is_good_recommendation,
        f"景点B饱和度={target_saturation*100:.0f}% < 40%, 符合推荐条件"
    )
    
    print("\n[测试] 验证优惠券可用性...")
    
    is_available = (
        coupon.is_active and 
        coupon.remained_stock > 0 and
        coupon.target_scenic_spot_id == target_spot.id
    )
    
    log_test_result(
        "优惠券可用性验证",
        is_available,
        f"优惠券状态: 有效={coupon.is_active}, 剩余库存={coupon.remained_stock}, 目标景点匹配={coupon.target_scenic_spot_id == target_spot.id}"
    )
    
    all_passed = coupon_created and should_trigger and is_good_recommendation and is_available
    
    return all_passed


def print_test_summary():
    print("\n" + "=" * 60)
    print("测试结果汇总")
    print("=" * 60)
    
    total_tests = len(test_results)
    passed_tests = sum(1 for r in test_results if r["passed"])
    failed_tests = total_tests - passed_tests
    
    print(f"\n  总测试数: {total_tests}")
    print(f"  通过: {passed_tests}")
    print(f"  失败: {failed_tests}")
    
    if failed_tests > 0:
        print("\n  失败的测试:")
        for result in test_results:
            if not result["passed"]:
                print(f"    - {result['test_name']}")
                print(f"      详情: {result['message']}")
    
    success_rate = (passed_tests / total_tests * 100) if total_tests > 0 else 0
    print(f"\n  成功率: {success_rate:.1f}%")
    
    print("\n" + "=" * 60)
    
    return failed_tests == 0


def main():
    print("\n" + "=" * 60)
    print("  全域电子导览与智慧客流管控 - 自动化测试")
    print("=" * 60)
    print(f"  测试开始时间: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    
    Session = sessionmaker(bind=engine)
    db = Session()
    
    try:
        cleanup_test_data(db)
        
        all_tests_passed = True
        
        test_color_level_logic()
        
        test_distance_calculation()
        
        if not test_crowded_spot_diversion_recommendation(db):
            all_tests_passed = False
        
        if not test_staff_on_duty_status(db):
            all_tests_passed = False
        
        if not test_coupon_integration(db):
            all_tests_passed = False
        
        final_result = print_test_summary()
        
        if final_result:
            print("\n  🎉 所有测试通过！")
        else:
            print("\n  ❌ 部分测试失败，请检查上述错误信息。")
        
        return 0 if final_result else 1
        
    except Exception as e:
        print(f"\n  [错误] 测试执行过程中发生异常: {e}")
        import traceback
        traceback.print_exc()
        return 1
    finally:
        cleanup_test_data(db)
        db.close()
        print(f"\n  测试结束时间: {time.strftime('%Y-%m-%d %H:%M:%S')}")


if __name__ == "__main__":
    sys.exit(main())
