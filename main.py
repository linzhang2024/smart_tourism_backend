from fastapi import FastAPI, Depends, HTTPException, status, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import text
from typing import List, Optional

import models
import schemas
from database import engine, get_db


def migrate_database():
    with engine.connect() as conn:
        try:
            result = conn.execute(text("PRAGMA table_info(scenic_spots)"))
            columns = [row[1] for row in result]
            
            if 'total_inventory' not in columns:
                print("[迁移] 添加 total_inventory 列到 scenic_spots 表...")
                conn.execute(text("ALTER TABLE scenic_spots ADD COLUMN total_inventory INTEGER DEFAULT 100"))
                print("[迁移] 完成!")
            
            if 'remained_inventory' not in columns:
                print("[迁移] 添加 remained_inventory 列到 scenic_spots 表...")
                conn.execute(text("ALTER TABLE scenic_spots ADD COLUMN remained_inventory INTEGER DEFAULT 100"))
                print("[迁移] 完成!")
            
            conn.commit()
        except Exception as e:
            print(f"[迁移] 警告: {e}")


migrate_database()
models.Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="智慧旅游后端API",
    description="智慧旅游系统后端服务，包含景点、门票、游客管理功能",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/", tags=["根路径"])
def root():
    return {
        "message": "智慧旅游后端API服务",
        "version": "1.0.0",
        "docs": "http://localhost:8000/docs"
    }


# Tourist endpoints
@app.post("/tourists/", response_model=schemas.Tourist, status_code=status.HTTP_201_CREATED, tags=["游客管理"])
def create_tourist(tourist: schemas.TouristCreate, db: Session = Depends(get_db)):
    db_tourist = models.Tourist(**tourist.model_dump())
    db.add(db_tourist)
    db.commit()
    db.refresh(db_tourist)
    return db_tourist


@app.get("/tourists/", response_model=List[schemas.Tourist], tags=["游客管理"])
def get_tourists(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    tourists = db.query(models.Tourist).offset(skip).limit(limit).all()
    return tourists


@app.get("/tourists/{tourist_id}", response_model=schemas.TouristWithTickets, tags=["游客管理"])
def get_tourist(tourist_id: int, db: Session = Depends(get_db)):
    tourist = db.query(models.Tourist).filter(models.Tourist.id == tourist_id).first()
    if tourist is None:
        raise HTTPException(status_code=404, detail="游客不存在")
    return tourist


@app.put("/tourists/{tourist_id}", response_model=schemas.Tourist, tags=["游客管理"])
def update_tourist(tourist_id: int, tourist: schemas.TouristUpdate, db: Session = Depends(get_db)):
    db_tourist = db.query(models.Tourist).filter(models.Tourist.id == tourist_id).first()
    if db_tourist is None:
        raise HTTPException(status_code=404, detail="游客不存在")
    
    for key, value in tourist.model_dump(exclude_unset=True).items():
        setattr(db_tourist, key, value)
    
    db.commit()
    db.refresh(db_tourist)
    return db_tourist


@app.delete("/tourists/{tourist_id}", status_code=status.HTTP_204_NO_CONTENT, tags=["游客管理"])
def delete_tourist(tourist_id: int, db: Session = Depends(get_db)):
    db_tourist = db.query(models.Tourist).filter(models.Tourist.id == tourist_id).first()
    if db_tourist is None:
        raise HTTPException(status_code=404, detail="游客不存在")
    
    db.delete(db_tourist)
    db.commit()
    return None


# Inventory alert endpoints - 这些路由必须放在 /scenic-spots/{spot_id} 前面
@app.get("/scenic-spots/low-alert", response_model=List[schemas.ScenicSpotInventoryAlert], tags=["库存管理"])
def get_low_inventory_spots(db: Session = Depends(get_db)):
    spots = db.query(models.ScenicSpot).all()
    low_inventory_spots = []
    
    for spot in spots:
        if spot.total_inventory == 0:
            inventory_ratio = 0.0
        else:
            inventory_ratio = spot.remained_inventory / spot.total_inventory
        
        if inventory_ratio < 0.10:
            low_inventory_spots.append(schemas.ScenicSpotInventoryAlert(
                id=spot.id,
                name=spot.name,
                total_inventory=spot.total_inventory,
                remained_inventory=spot.remained_inventory,
                inventory_ratio=round(inventory_ratio, 4),
                is_low_inventory=True
            ))
    
    return low_inventory_spots


@app.get("/scenic-spots/{spot_id}/inventory-status", response_model=schemas.ScenicSpotInventoryAlert, tags=["库存管理"])
def get_inventory_status(spot_id: int, db: Session = Depends(get_db)):
    spot = db.query(models.ScenicSpot).filter(models.ScenicSpot.id == spot_id).first()
    if spot is None:
        raise HTTPException(status_code=404, detail="景点不存在")
    
    if spot.total_inventory == 0:
        inventory_ratio = 0.0
    else:
        inventory_ratio = spot.remained_inventory / spot.total_inventory
    
    is_low_inventory = inventory_ratio < 0.10
    
    return schemas.ScenicSpotInventoryAlert(
        id=spot.id,
        name=spot.name,
        total_inventory=spot.total_inventory,
        remained_inventory=spot.remained_inventory,
        inventory_ratio=round(inventory_ratio, 4),
        is_low_inventory=is_low_inventory
    )


# ScenicSpot endpoints
@app.post("/scenic-spots/", response_model=schemas.ScenicSpot, status_code=status.HTTP_201_CREATED, tags=["景点管理"])
def create_scenic_spot(spot: schemas.ScenicSpotCreate, db: Session = Depends(get_db)):
    spot_data = spot.model_dump()
    
    if spot_data.get("total_inventory") is not None and spot_data.get("remained_inventory") is None:
        spot_data["remained_inventory"] = spot_data["total_inventory"]
    
    db_spot = models.ScenicSpot(**spot_data)
    db.add(db_spot)
    db.commit()
    db.refresh(db_spot)
    return db_spot


@app.get("/scenic-spots/", response_model=List[schemas.ScenicSpot], tags=["景点管理"])
def get_scenic_spots(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    spots = db.query(models.ScenicSpot).offset(skip).limit(limit).all()
    return spots


@app.get("/scenic-spots/{spot_id}", response_model=schemas.ScenicSpotWithTickets, tags=["景点管理"])
def get_scenic_spot(
    spot_id: int,
    tourist_id: Optional[int] = Query(None, description="游客ID（可选，用于判断是否已收藏）"),
    db: Session = Depends(get_db)
):
    spot = db.query(models.ScenicSpot).filter(models.ScenicSpot.id == spot_id).first()
    if spot is None:
        raise HTTPException(status_code=404, detail="景点不存在")
    
    is_favorited = False
    if tourist_id is not None:
        tourist = db.query(models.Tourist).filter(models.Tourist.id == tourist_id).first()
        if tourist is None:
            raise HTTPException(status_code=404, detail="游客不存在")
        
        favorite = db.query(models.Favorite).filter(
            models.Favorite.tourist_id == tourist_id,
            models.Favorite.scenic_spot_id == spot_id
        ).first()
        is_favorited = favorite is not None
    
    result = schemas.ScenicSpotWithTickets(
        id=spot.id,
        name=spot.name,
        description=spot.description,
        location=spot.location,
        rating=spot.rating,
        price=spot.price,
        total_inventory=spot.total_inventory,
        remained_inventory=spot.remained_inventory,
        created_at=spot.created_at,
        tickets=spot.tickets,
        is_favorited=is_favorited
    )
    return result


@app.put("/scenic-spots/{spot_id}", response_model=schemas.ScenicSpot, tags=["景点管理"])
def update_scenic_spot(spot_id: int, spot: schemas.ScenicSpotUpdate, db: Session = Depends(get_db)):
    db_spot = db.query(models.ScenicSpot).filter(models.ScenicSpot.id == spot_id).first()
    if db_spot is None:
        raise HTTPException(status_code=404, detail="景点不存在")
    
    for key, value in spot.model_dump(exclude_unset=True).items():
        setattr(db_spot, key, value)
    
    db.commit()
    db.refresh(db_spot)
    return db_spot


@app.delete("/scenic-spots/{spot_id}", status_code=status.HTTP_204_NO_CONTENT, tags=["景点管理"])
def delete_scenic_spot(spot_id: int, db: Session = Depends(get_db)):
    db_spot = db.query(models.ScenicSpot).filter(models.ScenicSpot.id == spot_id).first()
    if db_spot is None:
        raise HTTPException(status_code=404, detail="景点不存在")
    
    db.delete(db_spot)
    db.commit()
    return None


# Ticket endpoints
@app.post("/tickets/", response_model=schemas.Ticket, status_code=status.HTTP_201_CREATED, tags=["门票管理"])
def create_ticket(ticket: schemas.TicketCreate, db: Session = Depends(get_db)):
    tourist = db.query(models.Tourist).filter(models.Tourist.id == ticket.tourist_id).first()
    if tourist is None:
        raise HTTPException(status_code=404, detail="游客不存在")
    
    scenic_spot = db.query(models.ScenicSpot).filter(models.ScenicSpot.id == ticket.scenic_spot_id).first()
    if scenic_spot is None:
        raise HTTPException(status_code=404, detail="景点不存在")
    
    if scenic_spot.remained_inventory < ticket.quantity:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"库存不足，当前剩余库存: {scenic_spot.remained_inventory}"
        )
    
    scenic_spot.remained_inventory -= ticket.quantity
    
    total_price = scenic_spot.price * ticket.quantity
    
    db_ticket = models.Ticket(
        tourist_id=ticket.tourist_id,
        scenic_spot_id=ticket.scenic_spot_id,
        quantity=ticket.quantity,
        total_price=total_price
    )
    db.add(db_ticket)
    db.commit()
    db.refresh(scenic_spot)
    db.refresh(db_ticket)
    return db_ticket


@app.get("/tickets/", response_model=List[schemas.Ticket], tags=["门票管理"])
def get_tickets(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    tickets = db.query(models.Ticket).offset(skip).limit(limit).all()
    return tickets


@app.get("/tickets/{ticket_id}", response_model=schemas.TicketWithDetails, tags=["门票管理"])
def get_ticket(ticket_id: int, db: Session = Depends(get_db)):
    ticket = db.query(models.Ticket).filter(models.Ticket.id == ticket_id).first()
    if ticket is None:
        raise HTTPException(status_code=404, detail="门票不存在")
    return ticket


@app.put("/tickets/{ticket_id}", response_model=schemas.Ticket, tags=["门票管理"])
def update_ticket(ticket_id: int, ticket: schemas.TicketUpdate, db: Session = Depends(get_db)):
    db_ticket = db.query(models.Ticket).filter(models.Ticket.id == ticket_id).first()
    if db_ticket is None:
        raise HTTPException(status_code=404, detail="门票不存在")
    
    update_data = ticket.model_dump(exclude_unset=True)
    
    if "quantity" in update_data:
        scenic_spot = db.query(models.ScenicSpot).filter(models.ScenicSpot.id == db_ticket.scenic_spot_id).first()
        update_data["total_price"] = scenic_spot.price * update_data["quantity"]
    
    for key, value in update_data.items():
        setattr(db_ticket, key, value)
    
    db.commit()
    db.refresh(db_ticket)
    return db_ticket


@app.delete("/tickets/{ticket_id}", status_code=status.HTTP_204_NO_CONTENT, tags=["门票管理"])
def delete_ticket(ticket_id: int, db: Session = Depends(get_db)):
    db_ticket = db.query(models.Ticket).filter(models.Ticket.id == ticket_id).first()
    if db_ticket is None:
        raise HTTPException(status_code=404, detail="门票不存在")
    
    db.delete(db_ticket)
    db.commit()
    return None


# Favorite endpoints
@app.post("/favorites/toggle", response_model=schemas.FavoriteToggleResponse, tags=["收藏管理"])
def toggle_favorite(favorite_data: schemas.FavoriteCreate, db: Session = Depends(get_db)):
    tourist = db.query(models.Tourist).filter(models.Tourist.id == favorite_data.tourist_id).first()
    if tourist is None:
        raise HTTPException(status_code=404, detail="游客不存在")
    
    scenic_spot = db.query(models.ScenicSpot).filter(models.ScenicSpot.id == favorite_data.scenic_spot_id).first()
    if scenic_spot is None:
        raise HTTPException(status_code=404, detail="景点不存在")
    
    existing_favorite = db.query(models.Favorite).filter(
        models.Favorite.tourist_id == favorite_data.tourist_id,
        models.Favorite.scenic_spot_id == favorite_data.scenic_spot_id
    ).first()
    
    if existing_favorite:
        db.delete(existing_favorite)
        db.commit()
        return schemas.FavoriteToggleResponse(
            is_favorited=False,
            message="已取消收藏"
        )
    else:
        new_favorite = models.Favorite(
            tourist_id=favorite_data.tourist_id,
            scenic_spot_id=favorite_data.scenic_spot_id
        )
        db.add(new_favorite)
        db.commit()
        return schemas.FavoriteToggleResponse(
            is_favorited=True,
            message="已收藏"
        )


@app.get("/favorites/tourists/{tourist_id}", response_model=List[schemas.ScenicSpot], tags=["收藏管理"])
def get_favorites_by_tourist(tourist_id: int, db: Session = Depends(get_db)):
    tourist = db.query(models.Tourist).filter(models.Tourist.id == tourist_id).first()
    if tourist is None:
        raise HTTPException(status_code=404, detail="游客不存在")
    
    favorites = db.query(models.Favorite).filter(models.Favorite.tourist_id == tourist_id).all()
    scenic_spots = [fav.scenic_spot for fav in favorites]
    return scenic_spots


if __name__ == "__main__":
    import uvicorn
    
    print("\n" + "=" * 60)
    print("  智慧旅游后端API 启动中...")
    print("=" * 60)
    print("")
    print("  访问地址：")
    print("  ┌─────────────────────────────────────────────────────┐")
    print("  │  主页面:    http://localhost:8000/                  │")
    print("  │  API 文档:  http://localhost:8000/docs              │")
    print("  │  备选文档:  http://localhost:8000/redoc             │")
    print("  │  库存预警:  http://localhost:8000/scenic-spots/low-alert │")
    print("  └─────────────────────────────────────────────────────┘")
    print("")
    print("  按 Ctrl+C 可以停止服务器")
    print("")
    print("=" * 60)
    
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
