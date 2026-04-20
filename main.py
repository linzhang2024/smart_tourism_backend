import logging
from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from sqlalchemy import text
from typing import List
import os
from datetime import datetime

import models
import schemas
from database import engine, get_db


logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('app.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


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

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, "static")

if os.path.exists(STATIC_DIR):
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/", tags=["根路径"])
def root():
    index_path = os.path.join(STATIC_DIR, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
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
def get_scenic_spot(spot_id: int, db: Session = Depends(get_db)):
    spot = db.query(models.ScenicSpot).filter(models.ScenicSpot.id == spot_id).first()
    if spot is None:
        raise HTTPException(status_code=404, detail="景点不存在")
    return spot


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


# TouristFlow endpoints
@app.post("/traffic/record", response_model=schemas.TouristFlow, status_code=status.HTTP_201_CREATED, tags=["流量监控"])
def create_traffic_record(traffic: schemas.TouristFlowCreate, db: Session = Depends(get_db)):
    scenic_spot = db.query(models.ScenicSpot).filter(models.ScenicSpot.id == traffic.scenic_spot_id).first()
    if scenic_spot is None:
        raise HTTPException(status_code=404, detail="景点不存在")
    
    db_traffic = models.TouristFlow(**traffic.model_dump())
    db.add(db_traffic)
    db.commit()
    db.refresh(db_traffic)
    return db_traffic


@app.get("/traffic/analytics/{spot_id}", response_model=schemas.TouristFlowAnalytics, tags=["流量监控"])
def get_traffic_analytics(spot_id: int, db: Session = Depends(get_db)):
    scenic_spot = db.query(models.ScenicSpot).filter(models.ScenicSpot.id == spot_id).first()
    if scenic_spot is None:
        raise HTTPException(status_code=404, detail="景点不存在")
    
    recent_records = db.query(models.TouristFlow).filter(
        models.TouristFlow.scenic_spot_id == spot_id
    ).order_by(models.TouristFlow.record_time.desc()).limit(5).all()
    
    if not recent_records:
        return schemas.TouristFlowAnalytics(
            scenic_spot_id=spot_id,
            scenic_spot_name=scenic_spot.name,
            recent_records=[],
            average_entry_count=0.0,
            congestion_level="舒适",
            trend="持平"
        )
    
    total = sum(record.entry_count for record in recent_records)
    average = total / len(recent_records)
    
    if average < 100:
        congestion_level = "舒适"
    elif 100 <= average <= 200:
        congestion_level = "正常"
    else:
        congestion_level = "拥挤"
    
    if len(recent_records) >= 2:
        last_record = recent_records[0]
        second_last_record = recent_records[1]
        if last_record.entry_count > second_last_record.entry_count:
            trend = "上升"
        elif last_record.entry_count < second_last_record.entry_count:
            trend = "下降"
        else:
            trend = "持平"
    else:
        trend = "持平"
    
    return schemas.TouristFlowAnalytics(
        scenic_spot_id=spot_id,
        scenic_spot_name=scenic_spot.name,
        recent_records=recent_records,
        average_entry_count=round(average, 2),
        congestion_level=congestion_level,
        trend=trend
    )


@app.post("/tickets/purchase", response_model=schemas.TicketOrder, status_code=status.HTTP_201_CREATED, tags=["门票支付"])
def purchase_ticket(order_data: schemas.TicketOrderCreate, db: Session = Depends(get_db)):
    logger.info(f"开始处理购票请求 - 游客ID: {order_data.tourist_id}, 景点ID: {order_data.scenic_spot_id}, 数量: {order_data.quantity}")
    
    tourist = db.query(models.Tourist).filter(models.Tourist.id == order_data.tourist_id).first()
    if tourist is None:
        logger.warning(f"购票请求失败 - 游客不存在: {order_data.tourist_id}")
        raise HTTPException(status_code=404, detail="游客不存在")
    
    scenic_spot = db.query(models.ScenicSpot).filter(
        models.ScenicSpot.id == order_data.scenic_spot_id
    ).first()
    
    if scenic_spot is None:
        logger.warning(f"购票请求失败 - 景点不存在: {order_data.scenic_spot_id}")
        raise HTTPException(status_code=404, detail="景点不存在")
    
    try:
        logger.info(f"开始数据库事务 - 景点 {scenic_spot.name} 当前库存: {scenic_spot.remained_inventory}")
        
        from sqlalchemy import update
        
        update_stmt = update(models.ScenicSpot).where(
            models.ScenicSpot.id == order_data.scenic_spot_id,
            models.ScenicSpot.remained_inventory >= order_data.quantity
        ).values(
            remained_inventory=models.ScenicSpot.remained_inventory - order_data.quantity
        ).execution_options(synchronize_session="fetch")
        
        result = db.execute(update_stmt)
        affected_rows = result.rowcount
        
        if affected_rows == 0:
            db.refresh(scenic_spot)
            logger.error(f"库存不足 - 景点: {scenic_spot.name}, 需求: {order_data.quantity}, 可用: {scenic_spot.remained_inventory}")
            
            failed_order = models.TicketOrder(
                tourist_id=order_data.tourist_id,
                scenic_spot_id=order_data.scenic_spot_id,
                quantity=order_data.quantity,
                total_price=scenic_spot.price * order_data.quantity,
                status=models.OrderStatus.FAILED,
                created_at=datetime.utcnow()
            )
            db.add(failed_order)
            db.commit()
            db.refresh(failed_order)
            
            logger.error(f"订单创建失败 - 订单号: {failed_order.order_no}, 原因: 库存不足")
            
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"库存不足，当前剩余库存: {scenic_spot.remained_inventory}"
            )
        
        db.refresh(scenic_spot)
        logger.info(f"扣减库存 - 景点: {scenic_spot.name}, 扣减数量: {order_data.quantity}, 剩余: {scenic_spot.remained_inventory}")
        
        total_price = scenic_spot.price * order_data.quantity
        
        order = models.TicketOrder(
            tourist_id=order_data.tourist_id,
            scenic_spot_id=order_data.scenic_spot_id,
            quantity=order_data.quantity,
            total_price=total_price,
            status=models.OrderStatus.PAID,
            created_at=datetime.utcnow(),
            paid_at=datetime.utcnow()
        )
        db.add(order)
        
        db.commit()
        db.refresh(order)
        
        logger.info(f"订单创建成功 - 订单号: {order.order_no}, 游客: {tourist.name}, 景点: {scenic_spot.name}, 数量: {order_data.quantity}, 总价: {total_price}")
        logger.info(f"支付成功 - 订单号: {order.order_no}, 支付时间: {order.paid_at}")
        
        return order
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"购票过程中发生错误: {str(e)}")
        db.rollback()
        
        scenic_spot = db.query(models.ScenicSpot).filter(
            models.ScenicSpot.id == order_data.scenic_spot_id
        ).first()
        
        failed_order = models.TicketOrder(
            tourist_id=order_data.tourist_id,
            scenic_spot_id=order_data.scenic_spot_id,
            quantity=order_data.quantity,
            total_price=scenic_spot.price * order_data.quantity if scenic_spot else 0,
            status=models.OrderStatus.FAILED,
            created_at=datetime.utcnow()
        )
        db.add(failed_order)
        db.commit()
        db.refresh(failed_order)
        
        logger.error(f"订单创建失败 - 订单号: {failed_order.order_no}, 错误: {str(e)}")
        
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"购票失败: {str(e)}"
        )


@app.get("/tickets/orders/", response_model=list[schemas.TicketOrder], tags=["门票支付"])
def get_ticket_orders(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    orders = db.query(models.TicketOrder).offset(skip).limit(limit).all()
    return orders


@app.get("/tickets/orders/{order_id}", response_model=schemas.TicketOrderWithDetails, tags=["门票支付"])
def get_ticket_order(order_id: int, db: Session = Depends(get_db)):
    order = db.query(models.TicketOrder).filter(models.TicketOrder.id == order_id).first()
    if order is None:
        raise HTTPException(status_code=404, detail="订单不存在")
    return order


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
