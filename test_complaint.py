import os
import sys
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import models
import schemas
import auth
from database import Base, engine, SessionLocal
from sqlalchemy.orm import Session
from fastapi import HTTPException


def create_test_users(db: Session):
    print("\n" + "=" * 60)
    print("[准备] 创建测试用户...")
    print("=" * 60)

    tourist_user = db.query(models.User).filter(
        models.User.username == "test_tourist"
    ).first()
    
    if tourist_user:
        db.query(models.Complaint).filter(
            models.Complaint.user_id == tourist_user.id
        ).delete()
        db.delete(tourist_user)
        db.commit()

    admin_user = db.query(models.User).filter(
        models.User.username == "test_admin"
    ).first()
    
    if admin_user:
        db.delete(admin_user)
        db.commit()

    hashed_password = "$2b$12$KIXKOPYx3mQb5t14hQ5e3uH8k9L0mN1oP2qR3sT4uV5wX6yZ7aB8cD9eF0gH1iJ"

    tourist_user = models.User(
        username="test_tourist",
        hashed_password=hashed_password,
        role=models.UserRole.TOURIST,
        phone="13800001111",
        is_active=True
    )
    db.add(tourist_user)
    db.commit()
    db.refresh(tourist_user)
    print(f"[准备] 创建游客用户: ID={tourist_user.id}, 用户名={tourist_user.username}, 角色={tourist_user.role.value}")

    admin_user = models.User(
        username="test_admin",
        hashed_password=hashed_password,
        role=models.UserRole.ADMIN,
        phone="13800002222",
        is_active=True
    )
    db.add(admin_user)
    db.commit()
    db.refresh(admin_user)
    print(f"[准备] 创建管理员用户: ID={admin_user.id}, 用户名={admin_user.username}, 角色={admin_user.role.value}")

    return tourist_user, admin_user


def test_tourist_submit_complaint(db: Session, tourist_user: models.User):
    print("\n" + "=" * 60)
    print("[测试 1/5] 游客提交投诉")
    print("=" * 60)

    from main import create_complaint

    complaint_data = schemas.ComplaintCreate(
        title="测试投诉标题",
        content="这是一条测试投诉内容，测试游客提交投诉的功能是否正常工作。"
    )

    try:
        result = create_complaint(complaint_data, db, tourist_user)
        
        print(f"  [OK] 投诉创建成功!")
        print(f"  - 投诉ID: {result.id}")
        print(f"  - 标题: {result.title}")
        print(f"  - 状态: {result.status.value}")
        print(f"  - 创建时间: {result.created_at}")

        assert result.id is not None
        assert result.user_id == tourist_user.id
        assert result.title == "测试投诉标题"
        assert result.status == models.ComplaintStatus.PENDING

        return result
    except HTTPException as e:
        print(f"  [FAIL] 投诉创建失败: 状态码={e.status_code}, 详情={e.detail}")
        raise
    except Exception as e:
        print(f"  [FAIL] 投诉创建失败: {str(e)}")
        raise


def test_admin_get_all_complaints(db: Session, admin_user: models.User):
    print("\n" + "=" * 60)
    print("[测试 2/5] 管理员查询所有投诉")
    print("=" * 60)

    from main import get_all_complaints

    try:
        complaints = get_all_complaints(0, 100, db, admin_user)
        
        print(f"  [OK] 查询成功!")
        print(f"  - 投诉数量: {len(complaints)}")

        for c in complaints:
            print(f"\n  投诉 {c.id}:")
            print(f"    - 用户名: {c.user.username if c.user else '未知'}")
            print(f"    - 标题: {c.title}")
            print(f"    - 状态: {c.status.value}")
            print(f"    - 创建时间: {c.created_at}")

        assert len(complaints) > 0

        return complaints
    except HTTPException as e:
        print(f"  [FAIL] 查询失败: 状态码={e.status_code}, 详情={e.detail}")
        raise
    except Exception as e:
        print(f"  [FAIL] 查询失败: {str(e)}")
        raise


def test_admin_reply_complaint(db: Session, admin_user: models.User, complaint: models.Complaint):
    print("\n" + "=" * 60)
    print("[测试 3/5] 管理员回复投诉")
    print("=" * 60)

    from main import update_complaint

    update_data = schemas.ComplaintUpdate(
        reply="这是管理员的回复内容，问题已处理完毕。",
        status=models.ComplaintStatus.RESOLVED
    )

    try:
        result = update_complaint(complaint.id, update_data, db, admin_user)
        
        print(f"  [OK] 回复成功!")
        print(f"  - 投诉ID: {result.id}")
        print(f"  - 新状态: {result.status.value}")
        print(f"  - 回复内容: {result.reply}")

        assert result.status == models.ComplaintStatus.RESOLVED
        assert result.reply == "这是管理员的回复内容，问题已处理完毕。"

        return result
    except HTTPException as e:
        print(f"  [FAIL] 回复失败: 状态码={e.status_code}, 详情={e.detail}")
        raise
    except Exception as e:
        print(f"  [FAIL] 回复失败: {str(e)}")
        raise


def test_tourist_get_my_complaints(db: Session, tourist_user: models.User):
    print("\n" + "=" * 60)
    print("[测试 4/5] 游客查看自己的投诉")
    print("=" * 60)

    from main import get_my_complaints

    try:
        complaints = get_my_complaints(0, 100, db, tourist_user)
        
        print(f"  [OK] 查询成功!")
        print(f"  - 投诉数量: {len(complaints)}")

        for c in complaints:
            print(f"\n  投诉 {c.id}:")
            print(f"    - 标题: {c.title}")
            print(f"    - 状态: {c.status.value}")
            print(f"    - 回复: {c.reply or '暂无回复'}")
            print(f"    - 创建时间: {c.created_at}")

        assert len(complaints) > 0
        assert complaints[0].status == models.ComplaintStatus.RESOLVED
        assert complaints[0].reply is not None

        return complaints
    except HTTPException as e:
        print(f"  [FAIL] 查询失败: 状态码={e.status_code}, 详情={e.detail}")
        raise
    except Exception as e:
        print(f"  [FAIL] 查询失败: {str(e)}")
        raise


def test_staff_permission(db: Session):
    print("\n" + "=" * 60)
    print("[测试 5/5] STAFF 角色权限验证")
    print("=" * 60)

    hashed_password = "$2b$12$KIXKOPYx3mQb5t14hQ5e3uH8k9L0mN1oP2qR3sT4uV5wX6yZ7aB8cD9eF0gH1iJ"

    staff_user = db.query(models.User).filter(
        models.User.username == "test_staff"
    ).first()
    
    if staff_user:
        db.delete(staff_user)
        db.commit()

    staff_user = models.User(
        username="test_staff",
        hashed_password=hashed_password,
        role=models.UserRole.STAFF,
        phone="13800003333",
        is_active=True
    )
    db.add(staff_user)
    db.commit()
    db.refresh(staff_user)
    print(f"  [OK] 创建 STAFF 用户: ID={staff_user.id}")

    from main import get_all_complaints

    try:
        complaints = get_all_complaints(0, 100, db, staff_user)
        print(f"  [OK] STAFF 查询成功! 投诉数量: {len(complaints)}")

        assert len(complaints) > 0

        db.delete(staff_user)
        db.commit()

        return True
    except HTTPException as e:
        print(f"  [FAIL] 查询失败: 状态码={e.status_code}, 详情={e.detail}")
        raise
    except Exception as e:
        print(f"  [FAIL] 查询失败: {str(e)}")
        raise


def cleanup_test_data(db: Session):
    print("\n" + "=" * 60)
    print("[清理] 清理测试数据")
    print("=" * 60)

    tourist_user = db.query(models.User).filter(
        models.User.username == "test_tourist"
    ).first()
    
    if tourist_user:
        db.query(models.Complaint).filter(
            models.Complaint.user_id == tourist_user.id
        ).delete()
        db.delete(tourist_user)
        db.commit()
        print("  [OK] 游客用户和关联投诉已删除")

    admin_user = db.query(models.User).filter(
        models.User.username == "test_admin"
    ).first()
    
    if admin_user:
        db.delete(admin_user)
        db.commit()
        print("  [OK] 管理员用户已删除")

    staff_user = db.query(models.User).filter(
        models.User.username == "test_staff"
    ).first()
    
    if staff_user:
        db.delete(staff_user)
        db.commit()
        print("  [OK] STAFF 用户已删除")


def run_tests():
    print("\n" + "#" * 60)
    print("#" * 60)
    print("#          投诉咨询模块完整流程测试")
    print("#" * 60)
    print("#" * 60)

    Base.metadata.create_all(bind=engine)

    db = SessionLocal()

    try:
        tourist_user, admin_user = create_test_users(db)

        complaint = test_tourist_submit_complaint(db, tourist_user)

        test_admin_get_all_complaints(db, admin_user)

        test_admin_reply_complaint(db, admin_user, complaint)

        test_tourist_get_my_complaints(db, tourist_user)

        test_staff_permission(db)

        print("\n" + "=" * 60)
        print("[OK] 所有测试通过!")
        print("=" * 60)

    except Exception as e:
        print(f"\n[FAIL] 测试失败: {str(e)}")
        import traceback
        traceback.print_exc()
        raise
    finally:
        cleanup_test_data(db)
        db.close()

    print("\n" + "#" * 60)
    print("# 测试完成!")
    print("#" * 60)


if __name__ == "__main__":
    run_tests()
