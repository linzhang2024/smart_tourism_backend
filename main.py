from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from typing import List
<<<<<<< HEAD
=======
from contextlib import asynccontextmanager
>>>>>>> 15287fd83133d44f145eb7238af429817396e642

import models
import schemas
from database import engine, get_db

<<<<<<< HEAD
models.Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="智慧旅游后端API",
    description="智慧旅游系统后端服务，包含景点、门票、游客管理功能",
    version="1.0.0"
=======

@asynccontextmanager
async def lifespan(app: FastAPI):
    models.Base.metadata.create_all(bind=engine)
    
    print("\n" + "=" * 60)
    print("  智慧旅游管理系统 API 已启动！")
    print("=" * 60)
    print("")
    print("  访问地址：")
    print("  ┌─────────────────────────────────────────────────────┐")
    print("  │  主页面:    http://localhost:8000/                  │")
    print("  │  API 文档:  http://localhost:8000/docs              │")
    print("  │  备选文档:  http://localhost:8000/redoc             │")
    print("  │  OpenAPI:   http://localhost:8000/openapi.json      │")
    print("  └─────────────────────────────────────────────────────┘")
    print("")
    print("  提示：点击 http://localhost:8000/docs 可以直接测试 API")
    print("  按 Ctrl+C 可以停止服务器")
    print("")
    print("=" * 60)
    
    yield
    
    print("\n  智慧旅游管理系统 API 已停止。")


app = FastAPI(
    title="智慧旅游管理系统",
    description="一个基于 FastAPI 的智慧旅游项目管理后台",
    version="1.0.0",
    lifespan=lifespan
>>>>>>> 15287fd83133d44f145eb7238af429817396e642
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


<<<<<<< HEAD
# Tourist endpoints
@app.post("/tourists/", response_model=schemas.Tourist, status_code=status.HTTP_201_CREATED)
def create_tourist(tourist: schemas.TouristCreate, db: Session = Depends(get_db)):
    db_tourist = models.Tourist(**tourist.model_dump())
    db.add(db_tourist)
    db.commit()
    db.refresh(db_tourist)
    return db_tourist


@app.get("/tourists/", response_model=List[schemas.Tourist])
def get_tourists(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
=======
@app.get("/", tags=["根路径"])
def read_root():
    return {"message": "欢迎使用智慧旅游管理系统 API"}


@app.get("/scenic-spots/", response_model=List[schemas.ScenicSpotResponse], tags=["景点管理"])
def read_scenic_spots(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    scenic_spots = db.query(models.ScenicSpot).offset(skip).limit(limit).all()
    return scenic_spots


@app.get("/scenic-spots/{scenic_spot_id}", response_model=schemas.ScenicSpotWithTickets, tags=["景点管理"])
def read_scenic_spot(scenic_spot_id: int, db: Session = Depends(get_db)):
    scenic_spot = db.query(models.ScenicSpot).filter(models.ScenicSpot.id == scenic_spot_id).first()
    if scenic_spot is None:
        raise HTTPException(status_code=404, detail="景点不存在")
    return scenic_spot


@app.post("/scenic-spots/", response_model=schemas.ScenicSpotResponse, status_code=status.HTTP_201_CREATED, tags=["景点管理"])
def create_scenic_spot(scenic_spot: schemas.ScenicSpotCreate, db: Session = Depends(get_db)):
    db_scenic_spot = models.ScenicSpot(**scenic_spot.dict())
    db.add(db_scenic_spot)
    db.commit()
    db.refresh(db_scenic_spot)
    return db_scenic_spot


@app.put("/scenic-spots/{scenic_spot_id}", response_model=schemas.ScenicSpotResponse, tags=["景点管理"])
def update_scenic_spot(scenic_spot_id: int, scenic_spot: schemas.ScenicSpotUpdate, db: Session = Depends(get_db)):
    db_scenic_spot = db.query(models.ScenicSpot).filter(models.ScenicSpot.id == scenic_spot_id).first()
    if db_scenic_spot is None:
        raise HTTPException(status_code=404, detail="景点不存在")
    
    update_data = scenic_spot.dict(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_scenic_spot, key, value)
    
    db.commit()
    db.refresh(db_scenic_spot)
    return db_scenic_spot


@app.delete("/scenic-spots/{scenic_spot_id}", tags=["景点管理"])
def delete_scenic_spot(scenic_spot_id: int, db: Session = Depends(get_db)):
    db_scenic_spot = db.query(models.ScenicSpot).filter(models.ScenicSpot.id == scenic_spot_id).first()
    if db_scenic_spot is None:
        raise HTTPException(status_code=404, detail="景点不存在")
    
    db.delete(db_scenic_spot)
    db.commit()
    return {"message": "景点已删除"}


@app.get("/scenic-spots/{scenic_spot_id}/inventory-status", response_model=schemas.ScenicSpotInventoryAlert, tags=["库存管理"])
def get_scenic_spot_inventory_status(scenic_spot_id: int, db: Session = Depends(get_db)):
    db_scenic_spot = db.query(models.ScenicSpot).filter(models.ScenicSpot.id == scenic_spot_id).first()
    if db_scenic_spot is None:
        raise HTTPException(status_code=404, detail="景点不存在")
    
    inventory_percentage = 0.0
    if db_scenic_spot.total_inventory > 0:
        inventory_percentage = (db_scenic_spot.remained_inventory / db_scenic_spot.total_inventory) * 100
    
    is_low_inventory = inventory_percentage < db_scenic_spot.alert_threshold
    
    alert_response = schemas.ScenicSpotInventoryAlert(
        id=db_scenic_spot.id,
        name=db_scenic_spot.name,
        total_inventory=db_scenic_spot.total_inventory,
        remained_inventory=db_scenic_spot.remained_inventory,
        inventory_percentage=round(inventory_percentage, 2),
        alert_threshold=db_scenic_spot.alert_threshold,
        is_low_inventory=is_low_inventory
    )
    
    return alert_response


@app.get("/scenic-spots/inventory/low-alert", response_model=List[schemas.ScenicSpotInventoryAlert], tags=["库存管理"])
def get_low_inventory_alert(db: Session = Depends(get_db)):
    all_scenic_spots = db.query(models.ScenicSpot).all()
    low_inventory_spots = []
    
    for spot in all_scenic_spots:
        inventory_percentage = 0.0
        if spot.total_inventory > 0:
            inventory_percentage = (spot.remained_inventory / spot.total_inventory) * 100
        
        is_low_inventory = inventory_percentage < spot.alert_threshold
        
        if is_low_inventory:
            low_inventory_spots.append(schemas.ScenicSpotInventoryAlert(
                id=spot.id,
                name=spot.name,
                total_inventory=spot.total_inventory,
                remained_inventory=spot.remained_inventory,
                inventory_percentage=round(inventory_percentage, 2),
                alert_threshold=spot.alert_threshold,
                is_low_inventory=True
            ))
    
    return low_inventory_spots


@app.get("/tourists/", response_model=List[schemas.TouristResponse], tags=["游客管理"])
def read_tourists(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
>>>>>>> 15287fd83133d44f145eb7238af429817396e642
    tourists = db.query(models.Tourist).offset(skip).limit(limit).all()
    return tourists


<<<<<<< HEAD
@app.get("/tourists/{tourist_id}", response_model=schemas.TouristWithTickets)
def get_tourist(tourist_id: int, db: Session = Depends(get_db)):
=======
@app.get("/tourists/{tourist_id}", response_model=schemas.TouristWithTickets, tags=["游客管理"])
def read_tourist(tourist_id: int, db: Session = Depends(get_db)):
>>>>>>> 15287fd83133d44f145eb7238af429817396e642
    tourist = db.query(models.Tourist).filter(models.Tourist.id == tourist_id).first()
    if tourist is None:
        raise HTTPException(status_code=404, detail="游客不存在")
    return tourist


<<<<<<< HEAD
@app.put("/tourists/{tourist_id}", response_model=schemas.Tourist)
=======
@app.post("/tourists/", response_model=schemas.TouristResponse, status_code=status.HTTP_201_CREATED, tags=["游客管理"])
def create_tourist(tourist: schemas.TouristCreate, db: Session = Depends(get_db)):
    db_tourist = db.query(models.Tourist).filter(models.Tourist.id_card == tourist.id_card).first()
    if db_tourist:
        raise HTTPException(status_code=400, detail="身份证号已存在")
    
    db_tourist = models.Tourist(**tourist.dict())
    db.add(db_tourist)
    db.commit()
    db.refresh(db_tourist)
    return db_tourist


@app.put("/tourists/{tourist_id}", response_model=schemas.TouristResponse, tags=["游客管理"])
>>>>>>> 15287fd83133d44f145eb7238af429817396e642
def update_tourist(tourist_id: int, tourist: schemas.TouristUpdate, db: Session = Depends(get_db)):
    db_tourist = db.query(models.Tourist).filter(models.Tourist.id == tourist_id).first()
    if db_tourist is None:
        raise HTTPException(status_code=404, detail="游客不存在")
    
<<<<<<< HEAD
    for key, value in tourist.model_dump(exclude_unset=True).items():
=======
    if tourist.id_card:
        existing_tourist = db.query(models.Tourist).filter(
            models.Tourist.id_card == tourist.id_card,
            models.Tourist.id != tourist_id
        ).first()
        if existing_tourist:
            raise HTTPException(status_code=400, detail="身份证号已存在")
    
    update_data = tourist.dict(exclude_unset=True)
    for key, value in update_data.items():
>>>>>>> 15287fd83133d44f145eb7238af429817396e642
        setattr(db_tourist, key, value)
    
    db.commit()
    db.refresh(db_tourist)
    return db_tourist


<<<<<<< HEAD
@app.delete("/tourists/{tourist_id}", status_code=status.HTTP_204_NO_CONTENT)
=======
@app.delete("/tourists/{tourist_id}", tags=["游客管理"])
>>>>>>> 15287fd83133d44f145eb7238af429817396e642
def delete_tourist(tourist_id: int, db: Session = Depends(get_db)):
    db_tourist = db.query(models.Tourist).filter(models.Tourist.id == tourist_id).first()
    if db_tourist is None:
        raise HTTPException(status_code=404, detail="游客不存在")
    
    db.delete(db_tourist)
    db.commit()
<<<<<<< HEAD
    return None


# ScenicSpot endpoints
@app.post("/scenic-spots/", response_model=schemas.ScenicSpot, status_code=status.HTTP_201_CREATED)
def create_scenic_spot(spot: schemas.ScenicSpotCreate, db: Session = Depends(get_db)):
    db_spot = models.ScenicSpot(**spot.model_dump())
    db.add(db_spot)
    db.commit()
    db.refresh(db_spot)
    return db_spot


@app.get("/scenic-spots/", response_model=List[schemas.ScenicSpot])
def get_scenic_spots(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    spots = db.query(models.ScenicSpot).offset(skip).limit(limit).all()
    return spots


@app.get("/scenic-spots/{spot_id}", response_model=schemas.ScenicSpotWithTickets)
def get_scenic_spot(spot_id: int, db: Session = Depends(get_db)):
    spot = db.query(models.ScenicSpot).filter(models.ScenicSpot.id == spot_id).first()
    if spot is None:
        raise HTTPException(status_code=404, detail="景点不存在")
    return spot


@app.put("/scenic-spots/{spot_id}", response_model=schemas.ScenicSpot)
def update_scenic_spot(spot_id: int, spot: schemas.ScenicSpotUpdate, db: Session = Depends(get_db)):
    db_spot = db.query(models.ScenicSpot).filter(models.ScenicSpot.id == spot_id).first()
    if db_spot is None:
        raise HTTPException(status_code=404, detail="景点不存在")
    
    for key, value in spot.model_dump(exclude_unset=True).items():
        setattr(db_spot, key, value)
    
    db.commit()
    db.refresh(db_spot)
    return db_spot


@app.delete("/scenic-spots/{spot_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_scenic_spot(spot_id: int, db: Session = Depends(get_db)):
    db_spot = db.query(models.ScenicSpot).filter(models.ScenicSpot.id == spot_id).first()
    if db_spot is None:
        raise HTTPException(status_code=404, detail="景点不存在")
    
    db.delete(db_spot)
    db.commit()
    return None


# Ticket endpoints
@app.post("/tickets/", response_model=schemas.Ticket, status_code=status.HTTP_201_CREATED)
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


@app.get("/tickets/", response_model=List[schemas.Ticket])
def get_tickets(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
=======
    return {"message": "游客已删除"}


@app.get("/tickets/", response_model=List[schemas.TicketResponse], tags=["门票管理"])
def read_tickets(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
>>>>>>> 15287fd83133d44f145eb7238af429817396e642
    tickets = db.query(models.Ticket).offset(skip).limit(limit).all()
    return tickets


<<<<<<< HEAD
@app.get("/tickets/{ticket_id}", response_model=schemas.TicketWithDetails)
def get_ticket(ticket_id: int, db: Session = Depends(get_db)):
=======
@app.get("/tickets/{ticket_id}", response_model=schemas.TicketResponse, tags=["门票管理"])
def read_ticket(ticket_id: int, db: Session = Depends(get_db)):
>>>>>>> 15287fd83133d44f145eb7238af429817396e642
    ticket = db.query(models.Ticket).filter(models.Ticket.id == ticket_id).first()
    if ticket is None:
        raise HTTPException(status_code=404, detail="门票不存在")
    return ticket


<<<<<<< HEAD
@app.put("/tickets/{ticket_id}", response_model=schemas.Ticket)
=======
@app.post("/tickets/", response_model=schemas.TicketResponse, status_code=status.HTTP_201_CREATED, tags=["门票管理"])
def create_ticket(ticket: schemas.TicketCreate, db: Session = Depends(get_db)):
    db_scenic_spot = db.query(models.ScenicSpot).filter(models.ScenicSpot.id == ticket.scenic_spot_id).first()
    if db_scenic_spot is None:
        raise HTTPException(status_code=404, detail="景点不存在")
    
    if db_scenic_spot.remained_inventory <= 0:
        raise HTTPException(status_code=400, detail="库存不足")
    
    db_tourist = db.query(models.Tourist).filter(models.Tourist.id == ticket.tourist_id).first()
    if db_tourist is None:
        raise HTTPException(status_code=404, detail="游客不存在")
    
    db_scenic_spot.remained_inventory -= 1
    
    db_ticket = models.Ticket(**ticket.dict())
    db.add(db_ticket)
    db.commit()
    db.refresh(db_scenic_spot)
    db.refresh(db_ticket)
    return db_ticket


@app.put("/tickets/{ticket_id}", response_model=schemas.TicketResponse, tags=["门票管理"])
>>>>>>> 15287fd83133d44f145eb7238af429817396e642
def update_ticket(ticket_id: int, ticket: schemas.TicketUpdate, db: Session = Depends(get_db)):
    db_ticket = db.query(models.Ticket).filter(models.Ticket.id == ticket_id).first()
    if db_ticket is None:
        raise HTTPException(status_code=404, detail="门票不存在")
    
<<<<<<< HEAD
    update_data = ticket.model_dump(exclude_unset=True)
    
    if "quantity" in update_data:
        scenic_spot = db.query(models.ScenicSpot).filter(models.ScenicSpot.id == db_ticket.scenic_spot_id).first()
        update_data["total_price"] = scenic_spot.price * update_data["quantity"]
    
=======
    if ticket.scenic_spot_id:
        db_scenic_spot = db.query(models.ScenicSpot).filter(models.ScenicSpot.id == ticket.scenic_spot_id).first()
        if db_scenic_spot is None:
            raise HTTPException(status_code=404, detail="景点不存在")
    
    if ticket.tourist_id:
        db_tourist = db.query(models.Tourist).filter(models.Tourist.id == ticket.tourist_id).first()
        if db_tourist is None:
            raise HTTPException(status_code=404, detail="游客不存在")
    
    update_data = ticket.dict(exclude_unset=True)
>>>>>>> 15287fd83133d44f145eb7238af429817396e642
    for key, value in update_data.items():
        setattr(db_ticket, key, value)
    
    db.commit()
    db.refresh(db_ticket)
    return db_ticket


<<<<<<< HEAD
@app.delete("/tickets/{ticket_id}", status_code=status.HTTP_204_NO_CONTENT)
=======
@app.delete("/tickets/{ticket_id}", tags=["门票管理"])
>>>>>>> 15287fd83133d44f145eb7238af429817396e642
def delete_ticket(ticket_id: int, db: Session = Depends(get_db)):
    db_ticket = db.query(models.Ticket).filter(models.Ticket.id == ticket_id).first()
    if db_ticket is None:
        raise HTTPException(status_code=404, detail="门票不存在")
    
    db.delete(db_ticket)
    db.commit()
<<<<<<< HEAD
    return None


@app.get("/scenic-spots/{spot_id}/inventory-status", response_model=schemas.ScenicSpotInventoryAlert)
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


@app.get("/scenic-spots/low-alert", response_model=List[schemas.ScenicSpotInventoryAlert])
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


@app.get("/")
def root():
    return {"message": "智慧旅游后端API服务", "version": "1.0.0"}
=======
    return {"message": "门票已删除"}
>>>>>>> 15287fd83133d44f145eb7238af429817396e642


if __name__ == "__main__":
    import uvicorn
<<<<<<< HEAD
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
=======
    uvicorn.run(app, host="0.0.0.0", port=8000)
>>>>>>> 15287fd83133d44f145eb7238af429817396e642
