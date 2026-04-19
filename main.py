from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from typing import List

import models
import schemas
from database import engine, get_db

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
    tourists = db.query(models.Tourist).offset(skip).limit(limit).all()
    return tourists


@app.get("/tourists/{tourist_id}", response_model=schemas.TouristWithTickets)
def get_tourist(tourist_id: int, db: Session = Depends(get_db)):
    tourist = db.query(models.Tourist).filter(models.Tourist.id == tourist_id).first()
    if tourist is None:
        raise HTTPException(status_code=404, detail="游客不存在")
    return tourist


@app.put("/tourists/{tourist_id}", response_model=schemas.Tourist)
def update_tourist(tourist_id: int, tourist: schemas.TouristUpdate, db: Session = Depends(get_db)):
    db_tourist = db.query(models.Tourist).filter(models.Tourist.id == tourist_id).first()
    if db_tourist is None:
        raise HTTPException(status_code=404, detail="游客不存在")
    
    for key, value in tourist.model_dump(exclude_unset=True).items():
        setattr(db_tourist, key, value)
    
    db.commit()
    db.refresh(db_tourist)
    return db_tourist


@app.delete("/tourists/{tourist_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_tourist(tourist_id: int, db: Session = Depends(get_db)):
    db_tourist = db.query(models.Tourist).filter(models.Tourist.id == tourist_id).first()
    if db_tourist is None:
        raise HTTPException(status_code=404, detail="游客不存在")
    
    db.delete(db_tourist)
    db.commit()
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
    tickets = db.query(models.Ticket).offset(skip).limit(limit).all()
    return tickets


@app.get("/tickets/{ticket_id}", response_model=schemas.TicketWithDetails)
def get_ticket(ticket_id: int, db: Session = Depends(get_db)):
    ticket = db.query(models.Ticket).filter(models.Ticket.id == ticket_id).first()
    if ticket is None:
        raise HTTPException(status_code=404, detail="门票不存在")
    return ticket


@app.put("/tickets/{ticket_id}", response_model=schemas.Ticket)
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


@app.delete("/tickets/{ticket_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_ticket(ticket_id: int, db: Session = Depends(get_db)):
    db_ticket = db.query(models.Ticket).filter(models.Ticket.id == ticket_id).first()
    if db_ticket is None:
        raise HTTPException(status_code=404, detail="门票不存在")
    
    db.delete(db_ticket)
    db.commit()
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


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
