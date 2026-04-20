import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from datetime import datetime

from database import Base
import models
import schemas

SQLALCHEMY_DATABASE_URL = "sqlite:///./test_favorites.db"
engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def setup_test_db():
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    try:
        tourist = models.Tourist(
            name="测试游客",
            email="test_favorite@example.com",
            phone="13800138000"
        )
        db.add(tourist)
        
        spot = models.ScenicSpot(
            name="故宫博物院",
            description="中国明清两代的皇家宫殿",
            price=60.0,
            total_inventory=100,
            remained_inventory=100
        )
        db.add(spot)
        
        db.commit()
        db.refresh(tourist)
        db.refresh(spot)
        
        return tourist.id, spot.id
    finally:
        db.close()

def toggle_favorite(db, tourist_id, scenic_spot_id):
    tourist = db.query(models.Tourist).filter(models.Tourist.id == tourist_id).first()
    if tourist is None:
        raise Exception("游客不存在")
    
    scenic_spot = db.query(models.ScenicSpot).filter(models.ScenicSpot.id == scenic_spot_id).first()
    if scenic_spot is None:
        raise Exception("景点不存在")
    
    existing_favorite = db.query(models.Favorite).filter(
        models.Favorite.tourist_id == tourist_id,
        models.Favorite.scenic_spot_id == scenic_spot_id
    ).first()
    
    if existing_favorite:
        db.delete(existing_favorite)
        db.commit()
        return {
            "is_favorited": False,
            "message": "已取消收藏"
        }
    else:
        new_favorite = models.Favorite(
            tourist_id=tourist_id,
            scenic_spot_id=scenic_spot_id
        )
        db.add(new_favorite)
        db.commit()
        return {
            "is_favorited": True,
            "message": "已收藏"
        }

def get_scenic_spot_with_favorite_status(db, spot_id, tourist_id=None):
    spot = db.query(models.ScenicSpot).filter(models.ScenicSpot.id == spot_id).first()
    if spot is None:
        raise Exception("景点不存在")
    
    is_favorited = False
    if tourist_id is not None:
        tourist = db.query(models.Tourist).filter(models.Tourist.id == tourist_id).first()
        if tourist is None:
            raise Exception("游客不存在")
        
        favorite = db.query(models.Favorite).filter(
            models.Favorite.tourist_id == tourist_id,
            models.Favorite.scenic_spot_id == spot_id
        ).first()
        is_favorited = favorite is not None
    
    return {
        "id": spot.id,
        "name": spot.name,
        "description": spot.description,
        "location": spot.location,
        "rating": spot.rating,
        "price": spot.price,
        "total_inventory": spot.total_inventory,
        "remained_inventory": spot.remained_inventory,
        "created_at": spot.created_at,
        "tickets": [],
        "is_favorited": is_favorited
    }

def get_favorites_by_tourist(db, tourist_id):
    tourist = db.query(models.Tourist).filter(models.Tourist.id == tourist_id).first()
    if tourist is None:
        raise Exception("游客不存在")
    
    favorites = db.query(models.Favorite).filter(models.Favorite.tourist_id == tourist_id).all()
    return [{
        "id": fav.scenic_spot.id,
        "name": fav.scenic_spot.name,
        "description": fav.scenic_spot.description,
        "location": fav.scenic_spot.location,
        "rating": fav.scenic_spot.rating,
        "price": fav.scenic_spot.price,
        "total_inventory": fav.scenic_spot.total_inventory,
        "remained_inventory": fav.scenic_spot.remained_inventory,
        "created_at": fav.scenic_spot.created_at
    } for fav in favorites]

def run_tests():
    print("=" * 60)
    print("测试收藏功能（直接数据库测试，不依赖网络）")
    print("=" * 60)
    
    if os.path.exists("./test_favorites.db"):
        os.remove("./test_favorites.db")
    
    print("\n1. 设置测试数据...")
    tourist_id, spot_id = setup_test_db()
    print(f"   游客 ID: {tourist_id}")
    print(f"   景点 ID: {spot_id}")
    
    db = TestingSessionLocal()
    try:
        print("\n2. 查看景点详情（未传入 tourist_id）...")
        spot_detail = get_scenic_spot_with_favorite_status(db, spot_id)
        print(f"   景点名称: {spot_detail['name']}")
        print(f"   is_favorited: {spot_detail['is_favorited']}")
        
        print("\n3. 查看景点详情（传入 tourist_id）...")
        spot_detail = get_scenic_spot_with_favorite_status(db, spot_id, tourist_id)
        print(f"   景点名称: {spot_detail['name']}")
        print(f"   is_favorited: {spot_detail['is_favorited']}")
        
        print("\n4. 第一次点击收藏（应该添加收藏）...")
        result = toggle_favorite(db, tourist_id, spot_id)
        print(f"   is_favorited: {result['is_favorited']}")
        print(f"   message: {result['message']}")
        assert result['is_favorited'] == True, "应该已收藏"
        
        print("\n5. 再次查看景点详情（传入 tourist_id）...")
        spot_detail = get_scenic_spot_with_favorite_status(db, spot_id, tourist_id)
        print(f"   景点名称: {spot_detail['name']}")
        print(f"   is_favorited: {spot_detail['is_favorited']}")
        assert spot_detail['is_favorited'] == True, "应该已收藏"
        
        print("\n6. 查看收藏列表...")
        favorites = get_favorites_by_tourist(db, tourist_id)
        print(f"   收藏的景点数量: {len(favorites)}")
        for spot in favorites:
            print(f"   - {spot['name']} (ID: {spot['id']})")
        assert len(favorites) == 1, "应该有1个收藏"
        
        print("\n7. 第二次点击收藏（应该取消收藏）...")
        result = toggle_favorite(db, tourist_id, spot_id)
        print(f"   is_favorited: {result['is_favorited']}")
        print(f"   message: {result['message']}")
        assert result['is_favorited'] == False, "应该已取消收藏"
        
        print("\n8. 再次查看景点详情（传入 tourist_id）...")
        spot_detail = get_scenic_spot_with_favorite_status(db, spot_id, tourist_id)
        print(f"   景点名称: {spot_detail['name']}")
        print(f"   is_favorited: {spot_detail['is_favorited']}")
        assert spot_detail['is_favorited'] == False, "应该已取消收藏"
        
        print("\n9. 再次查看收藏列表...")
        favorites = get_favorites_by_tourist(db, tourist_id)
        print(f"   收藏的景点数量: {len(favorites)}")
        assert len(favorites) == 0, "应该没有收藏"
        
        print("\n10. 第三次点击收藏（重新收藏）...")
        result = toggle_favorite(db, tourist_id, spot_id)
        print(f"   is_favorited: {result['is_favorited']}")
        print(f"   message: {result['message']}")
        assert result['is_favorited'] == True, "应该已收藏"
        
        print("\n" + "=" * 60)
        print("所有测试通过！✅")
        print("=" * 60)
        
    finally:
        db.close()
        if os.path.exists("./test_favorites.db"):
            os.remove("./test_favorites.db")

if __name__ == "__main__":
    run_tests()
