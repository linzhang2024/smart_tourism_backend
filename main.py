import logging
import json
import traceback
from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from sqlalchemy import text
from typing import List, Optional, Dict, Any
import os
from datetime import datetime

import models
import schemas
from database import engine, get_db
from analytics_report import get_analytics_report


class JSONLogFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        log_data: Dict[str, Any] = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "message": record.getMessage(),
        }
        
        if hasattr(record, 'order_id'):
            log_data["order_id"] = record.order_id
        if hasattr(record, 'scenic_spot_id'):
            log_data["scenic_spot_id"] = record.scenic_spot_id
        if hasattr(record, 'action'):
            log_data["action"] = record.action
        if hasattr(record, 'tourist_id'):
            log_data["tourist_id"] = record.tourist_id
        if hasattr(record, 'quantity'):
            log_data["quantity"] = record.quantity
        if hasattr(record, 'remaining_inventory'):
            log_data["remaining_inventory"] = record.remaining_inventory
        
        if record.exc_info:
            log_data["exception"] = {
                "type": record.exc_info[0].__name__,
                "message": str(record.exc_info[1]),
                "traceback": traceback.format_exc()
            }
        
        return json.dumps(log_data, ensure_ascii=False)


def setup_logging():
    logger = logging.getLogger("payment_service")
    logger.setLevel(logging.INFO)
    logger.propagate = False
    
    file_handler = logging.FileHandler('app.log', encoding='utf-8')
    file_handler.setFormatter(JSONLogFormatter())
    
    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(JSONLogFormatter())
    
    logger.addHandler(file_handler)
    logger.addHandler(stream_handler)
    
    return logger


logger = setup_logging()


def log_info(
    message: str,
    action: str,
    order_id: Optional[str] = None,
    scenic_spot_id: Optional[int] = None,
    tourist_id: Optional[int] = None,
    quantity: Optional[int] = None,
    remaining_inventory: Optional[int] = None
):
    extra = {
        "action": action,
    }
    if order_id:
        extra["order_id"] = order_id
    if scenic_spot_id:
        extra["scenic_spot_id"] = scenic_spot_id
    if tourist_id:
        extra["tourist_id"] = tourist_id
    if quantity:
        extra["quantity"] = quantity
    if remaining_inventory is not None:
        extra["remaining_inventory"] = remaining_inventory
    
    logger.info(message, extra=extra)


def log_error(
    message: str,
    action: str,
    order_id: Optional[str] = None,
    scenic_spot_id: Optional[int] = None,
    tourist_id: Optional[int] = None,
    quantity: Optional[int] = None,
    remaining_inventory: Optional[int] = None,
    exc_info: Optional[bool] = None
):
    extra = {
        "action": action,
    }
    if order_id:
        extra["order_id"] = order_id
    if scenic_spot_id:
        extra["scenic_spot_id"] = scenic_spot_id
    if tourist_id:
        extra["tourist_id"] = tourist_id
    if quantity:
        extra["quantity"] = quantity
    if remaining_inventory is not None:
        extra["remaining_inventory"] = remaining_inventory
    
    logger.error(message, extra=extra, exc_info=exc_info)


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
    from sqlalchemy import update as sql_update
    
    order: Optional[models.TicketOrder] = None
    failed_order: Optional[models.TicketOrder] = None
    scenic_spot: Optional[models.ScenicSpot] = None
    tourist: Optional[models.Tourist] = None
    
    log_info(
        message="开始处理购票请求",
        action="PURCHASE_REQUEST",
        tourist_id=order_data.tourist_id,
        scenic_spot_id=order_data.scenic_spot_id,
        quantity=order_data.quantity
    )
    
    try:
        tourist = db.query(models.Tourist).filter(
            models.Tourist.id == order_data.tourist_id
        ).first()
        
        if tourist is None:
            log_error(
                message="游客不存在",
                action="VALIDATION_FAILED",
                tourist_id=order_data.tourist_id,
                scenic_spot_id=order_data.scenic_spot_id
            )
            raise HTTPException(status_code=404, detail="游客不存在")
        
        scenic_spot = db.query(models.ScenicSpot).filter(
            models.ScenicSpot.id == order_data.scenic_spot_id
        ).first()
        
        if scenic_spot is None:
            log_error(
                message="景点不存在",
                action="VALIDATION_FAILED",
                tourist_id=order_data.tourist_id,
                scenic_spot_id=order_data.scenic_spot_id
            )
            raise HTTPException(status_code=404, detail="景点不存在")
        
        log_info(
            message=f"当前库存: {scenic_spot.remained_inventory}",
            action="INVENTORY_CHECK",
            scenic_spot_id=order_data.scenic_spot_id,
            remaining_inventory=scenic_spot.remained_inventory
        )
        
        update_stmt = sql_update(models.ScenicSpot).where(
            models.ScenicSpot.id == order_data.scenic_spot_id,
            models.ScenicSpot.remained_inventory >= order_data.quantity
        ).values(
            remained_inventory=models.ScenicSpot.remained_inventory - order_data.quantity
        ).execution_options(synchronize_session="fetch")
        
        result = db.execute(update_stmt)
        affected_rows = result.rowcount
        
        if affected_rows == 0:
            db.refresh(scenic_spot)
            log_error(
                message=f"库存不足，需求: {order_data.quantity}, 可用: {scenic_spot.remained_inventory}",
                action="INVENTORY_SHORTAGE",
                scenic_spot_id=order_data.scenic_spot_id,
                quantity=order_data.quantity,
                remaining_inventory=scenic_spot.remained_inventory
            )
            
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
            
            log_error(
                message="库存不足订单记录已保存",
                action="FAILED_ORDER_SAVED",
                order_id=failed_order.order_no,
                scenic_spot_id=order_data.scenic_spot_id
            )
            
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"库存不足，当前剩余库存: {scenic_spot.remained_inventory}"
            )
        
        db.refresh(scenic_spot)
        
        log_info(
            message=f"库存扣减成功，扣减数量: {order_data.quantity}, 剩余: {scenic_spot.remained_inventory}",
            action="INVENTORY_DEDUCTED",
            scenic_spot_id=order_data.scenic_spot_id,
            quantity=order_data.quantity,
            remaining_inventory=scenic_spot.remained_inventory
        )
        
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
        db.flush()
        
        log_info(
            message=f"订单创建成功，订单号: {order.order_no}",
            action="ORDER_CREATED",
            order_id=order.order_no,
            scenic_spot_id=order_data.scenic_spot_id
        )
        
        db.commit()
        db.refresh(order)
        
        log_info(
            message=f"支付成功，订单号: {order.order_no}, 支付时间: {order.paid_at}",
            action="PAYMENT_SUCCESS",
            order_id=order.order_no,
            scenic_spot_id=order_data.scenic_spot_id
        )
        
        return order
        
    except HTTPException:
        raise
        
    except Exception as e:
        db.rollback()
        
        log_error(
            message=f"购票过程中发生系统错误: {str(e)}",
            action="SYSTEM_ERROR",
            tourist_id=order_data.tourist_id,
            scenic_spot_id=order_data.scenic_spot_id,
            exc_info=True
        )
        
        try:
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
            
            log_error(
                message="系统错误订单记录已保存",
                action="FAILED_ORDER_SAVED",
                order_id=failed_order.order_no,
                scenic_spot_id=order_data.scenic_spot_id
            )
        except Exception as save_error:
            log_error(
                message=f"保存失败订单时发生错误: {str(save_error)}",
                action="SAVE_FAILED_ORDER_ERROR",
                exc_info=True
            )
        
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="系统内部错误，请稍后重试"
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


@app.get("/system/health", tags=["系统监控"])
def get_system_health():
    report = get_analytics_report()
    return report


@app.get("/analytics/traffic-series", tags=["流量监控"])
def get_traffic_series(spot_id: int, db: Session = Depends(get_db)):
    scenic_spot = db.query(models.ScenicSpot).filter(
        models.ScenicSpot.id == spot_id
    ).first()
    if scenic_spot is None:
        raise HTTPException(status_code=404, detail="景点不存在")

    recent_records = db.query(models.TouristFlow).filter(
        models.TouristFlow.scenic_spot_id == spot_id
    ).order_by(models.TouristFlow.record_time.desc()).limit(10).all()

    times = []
    values = []

    for record in reversed(recent_records):
        times.append(record.record_time.strftime("%H:%M:%S"))
        values.append(record.entry_count)

    return {
        "spot_id": spot_id,
        "spot_name": scenic_spot.name,
        "times": times,
        "values": values,
        "records": [
            {
                "time": record.record_time.strftime("%H:%M:%S"),
                "entry_count": record.entry_count
            }
            for record in reversed(recent_records)
        ]
    }


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
