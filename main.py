from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from typing import List

import models
import schemas
from database import engine, get_db

models.Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="智慧旅游管理系统",
    description="一个基于 FastAPI 的智慧旅游项目管理后台",
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


@app.get("/tourists/", response_model=List[schemas.TouristResponse], tags=["游客管理"])
def read_tourists(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    tourists = db.query(models.Tourist).offset(skip).limit(limit).all()
    return tourists


@app.get("/tourists/{tourist_id}", response_model=schemas.TouristWithTickets, tags=["游客管理"])
def read_tourist(tourist_id: int, db: Session = Depends(get_db)):
    tourist = db.query(models.Tourist).filter(models.Tourist.id == tourist_id).first()
    if tourist is None:
        raise HTTPException(status_code=404, detail="游客不存在")
    return tourist


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
def update_tourist(tourist_id: int, tourist: schemas.TouristUpdate, db: Session = Depends(get_db)):
    db_tourist = db.query(models.Tourist).filter(models.Tourist.id == tourist_id).first()
    if db_tourist is None:
        raise HTTPException(status_code=404, detail="游客不存在")
    
    if tourist.id_card:
        existing_tourist = db.query(models.Tourist).filter(
            models.Tourist.id_card == tourist.id_card,
            models.Tourist.id != tourist_id
        ).first()
        if existing_tourist:
            raise HTTPException(status_code=400, detail="身份证号已存在")
    
    update_data = tourist.dict(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_tourist, key, value)
    
    db.commit()
    db.refresh(db_tourist)
    return db_tourist


@app.delete("/tourists/{tourist_id}", tags=["游客管理"])
def delete_tourist(tourist_id: int, db: Session = Depends(get_db)):
    db_tourist = db.query(models.Tourist).filter(models.Tourist.id == tourist_id).first()
    if db_tourist is None:
        raise HTTPException(status_code=404, detail="游客不存在")
    
    db.delete(db_tourist)
    db.commit()
    return {"message": "游客已删除"}


@app.get("/tickets/", response_model=List[schemas.TicketResponse], tags=["门票管理"])
def read_tickets(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    tickets = db.query(models.Ticket).offset(skip).limit(limit).all()
    return tickets


@app.get("/tickets/{ticket_id}", response_model=schemas.TicketResponse, tags=["门票管理"])
def read_ticket(ticket_id: int, db: Session = Depends(get_db)):
    ticket = db.query(models.Ticket).filter(models.Ticket.id == ticket_id).first()
    if ticket is None:
        raise HTTPException(status_code=404, detail="门票不存在")
    return ticket


@app.post("/tickets/", response_model=schemas.TicketResponse, status_code=status.HTTP_201_CREATED, tags=["门票管理"])
def create_ticket(ticket: schemas.TicketCreate, db: Session = Depends(get_db)):
    db_scenic_spot = db.query(models.ScenicSpot).filter(models.ScenicSpot.id == ticket.scenic_spot_id).first()
    if db_scenic_spot is None:
        raise HTTPException(status_code=404, detail="景点不存在")
    
    db_tourist = db.query(models.Tourist).filter(models.Tourist.id == ticket.tourist_id).first()
    if db_tourist is None:
        raise HTTPException(status_code=404, detail="游客不存在")
    
    db_ticket = models.Ticket(**ticket.dict())
    db.add(db_ticket)
    db.commit()
    db.refresh(db_ticket)
    return db_ticket


@app.put("/tickets/{ticket_id}", response_model=schemas.TicketResponse, tags=["门票管理"])
def update_ticket(ticket_id: int, ticket: schemas.TicketUpdate, db: Session = Depends(get_db)):
    db_ticket = db.query(models.Ticket).filter(models.Ticket.id == ticket_id).first()
    if db_ticket is None:
        raise HTTPException(status_code=404, detail="门票不存在")
    
    if ticket.scenic_spot_id:
        db_scenic_spot = db.query(models.ScenicSpot).filter(models.ScenicSpot.id == ticket.scenic_spot_id).first()
        if db_scenic_spot is None:
            raise HTTPException(status_code=404, detail="景点不存在")
    
    if ticket.tourist_id:
        db_tourist = db.query(models.Tourist).filter(models.Tourist.id == ticket.tourist_id).first()
        if db_tourist is None:
            raise HTTPException(status_code=404, detail="游客不存在")
    
    update_data = ticket.dict(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_ticket, key, value)
    
    db.commit()
    db.refresh(db_ticket)
    return db_ticket


@app.delete("/tickets/{ticket_id}", tags=["门票管理"])
def delete_ticket(ticket_id: int, db: Session = Depends(get_db)):
    db_ticket = db.query(models.Ticket).filter(models.Ticket.id == ticket_id).first()
    if db_ticket is None:
        raise HTTPException(status_code=404, detail="门票不存在")
    
    db.delete(db_ticket)
    db.commit()
    return {"message": "门票已删除"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
