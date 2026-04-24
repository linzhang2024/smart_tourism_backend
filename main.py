import logging
import json
import traceback
import threading
import time
import sys
from fastapi import FastAPI, Depends, HTTPException, status, APIRouter, Query, Header, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from sqlalchemy.orm import Session
from sqlalchemy import text
from typing import List, Optional, Dict, Any
import os
from datetime import datetime, timedelta
from dataclasses import dataclass
from functools import wraps

import models
import schemas
import auth
from database import engine, get_db
from analytics_report import get_analytics_report
import security

APP_START_TIME = datetime.now()

def get_uptime_seconds() -> int:
    return int((datetime.now() - APP_START_TIME).total_seconds())

def mask_user_response(user: models.User) -> models.User:
    if user.phone:
        user.phone = security.mask_phone(user.phone)
    return user

def mask_user_response_schema(user_response: schemas.UserResponse) -> schemas.UserResponse:
    if user_response.phone:
        user_response.phone = security.mask_phone(user_response.phone)
    return user_response

def performance_monitor_middleware(app: FastAPI):
    @app.middleware("http")
    async def add_performance_monitor(request: Request, call_next):
        start_time = time.time()
        
        try:
            response = await call_next(request)
            
            duration_ms = (time.time() - start_time) * 1000
            endpoint = request.url.path
            
            monitor = security.get_performance_monitor()
            monitor.record_response_time(endpoint, duration_ms)
            
            return response
            
        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            endpoint = request.url.path
            
            status_code = 500
            if hasattr(e, 'status_code'):
                status_code = e.status_code
            
            monitor = security.get_performance_monitor()
            monitor.record_error(endpoint, str(e), status_code)
            
            raise
    
    return app

def mask_response_decorator(func):
    @wraps(func)
    async def wrapper(*args, **kwargs):
        result = await func(*args, **kwargs)
        
        if isinstance(result, schemas.UserResponse):
            return mask_user_response_schema(result)
        elif isinstance(result, list) and len(result) > 0:
            first_item = result[0]
            if isinstance(first_item, schemas.UserResponse):
                return [mask_user_response_schema(item) for item in result]
            elif isinstance(first_item, models.User):
                return [mask_user_response(schemas.UserResponse.model_validate(item)) for item in result]
        elif isinstance(result, models.User):
            return mask_user_response_schema(schemas.UserResponse.model_validate(result))
        elif isinstance(result, schemas.Tourist):
            if result.phone:
                result.phone = security.mask_phone(result.phone)
            if result.email:
                result.email = security.mask_email(result.email)
            return result
        elif isinstance(result, list) and len(result) > 0 and isinstance(result[0], schemas.Tourist):
            for item in result:
                if item.phone:
                    item.phone = security.mask_phone(item.phone)
                if item.email:
                    item.email = security.mask_email(item.email)
            return result
        
        return result
    
    return wrapper

auth_router = APIRouter(prefix="/auth", tags=["认证管理"])


@auth_router.post("/register", response_model=schemas.UserResponse, status_code=status.HTTP_201_CREATED)
@security.rate_limit("10/minute")
async def register(request: Request, user_data: schemas.UserCreate, db: Session = Depends(get_db)):
    result = auth.register_user(db, user_data)
    
    audit_manager = security.get_audit_log_manager()
    audit_manager.log_action(
        user_id=result.id,
        module=models.AuditLogModule.AUTH,
        action=models.AuditLogAction.CREATE,
        details=f"用户注册: {result.username}",
        ip_address=request.client.host if request.client else None
    )
    
    return mask_user_response_schema(schemas.UserResponse.model_validate(result))


@auth_router.post("/login", response_model=schemas.Token)
@security.rate_limit("20/minute")
async def login(request: Request, login_data: schemas.UserLogin, db: Session = Depends(get_db)):
    result = auth.login_user(db, login_data)
    
    result.user = mask_user_response_schema(result.user)
    
    audit_manager = security.get_audit_log_manager()
    audit_manager.log_action(
        user_id=result.user.id,
        module=models.AuditLogModule.AUTH,
        action=models.AuditLogAction.LOGIN,
        details=f"用户登录: {result.user.username}",
        ip_address=request.client.host if request.client else None
    )
    
    return result


@auth_router.get("/me", response_model=schemas.UserResponse)
async def get_current_user_info(
    current_user: models.User = Depends(auth.get_current_active_user)
):
    return mask_user_response_schema(schemas.UserResponse.model_validate(current_user))


@auth_router.get("/users/list", response_model=List[schemas.UserResponse], tags=["用户管理"])
async def get_users_list(
    db: Session = Depends(get_db),
    current_admin: models.User = Depends(auth.require_role(models.UserRole.ADMIN))
):
    users = auth.get_all_users(db)
    return [mask_user_response_schema(schemas.UserResponse.model_validate(u)) for u in users]


@auth_router.patch("/users/{user_id}/status", response_model=schemas.UserResponse, tags=["用户管理"])
@security.rate_limit("10/minute")
async def toggle_user_status(
    request: Request,
    user_id: int,
    db: Session = Depends(get_db),
    current_admin: models.User = Depends(auth.require_role(models.UserRole.ADMIN))
):
    user = auth.toggle_user_status(db, user_id, current_admin.id)
    
    audit_manager = security.get_audit_log_manager()
    audit_manager.log_action(
        user_id=current_admin.id,
        module=models.AuditLogModule.USER,
        action=models.AuditLogAction.UPDATE,
        target_id=user_id,
        target_type="User",
        details=f"管理员 {current_admin.username} 修改用户状态: {user.username}, 新状态: {'启用' if user.is_active else '禁用'}",
        ip_address=request.client.host if request.client else None
    )
    
    return mask_user_response_schema(schemas.UserResponse.model_validate(user))


@auth_router.patch("/users/{user_id}/role", response_model=schemas.UserResponse, tags=["用户管理"])
@security.rate_limit("10/minute")
async def update_user_role(
    request: Request,
    user_id: int,
    new_role: schemas.UserRole,
    db: Session = Depends(get_db),
    current_admin: models.User = Depends(auth.require_role(models.UserRole.ADMIN))
):
    user = auth.update_user_role(db, user_id, new_role, current_admin.id)
    
    audit_manager = security.get_audit_log_manager()
    audit_manager.log_action(
        user_id=current_admin.id,
        module=models.AuditLogModule.USER,
        action=models.AuditLogAction.UPDATE,
        target_id=user_id,
        target_type="User",
        details=f"管理员 {current_admin.username} 修改用户角色: {user.username}, 新角色: {new_role.value}",
        ip_address=request.client.host if request.client else None
    )
    
    return mask_user_response_schema(schemas.UserResponse.model_validate(user))


CACHE_TTL_SECONDS = 10
scenic_spot_cache: Dict[int, Dict[str, Any]] = {}
cache_lock = threading.Lock()

log_write_lock = threading.Lock()


class ThreadSafeFileHandler(logging.FileHandler):
    def __init__(self, filename, mode='a', encoding=None, delay=False):
        super().__init__(filename, mode, encoding, delay)
        self._lock = threading.Lock()
    
    def emit(self, record):
        with self._lock:
            super().emit(record)


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
    
    file_handler = ThreadSafeFileHandler('app.log', encoding='utf-8')
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
            
            if 'latitude' not in columns:
                print("[迁移] 添加 latitude 列到 scenic_spots 表...")
                conn.execute(text("ALTER TABLE scenic_spots ADD COLUMN latitude FLOAT"))
                print("[迁移] 完成!")
            
            if 'longitude' not in columns:
                print("[迁移] 添加 longitude 列到 scenic_spots 表...")
                conn.execute(text("ALTER TABLE scenic_spots ADD COLUMN longitude FLOAT"))
                print("[迁移] 完成!")
            
            if 'geofence_radius' not in columns:
                print("[迁移] 添加 geofence_radius 列到 scenic_spots 表...")
                conn.execute(text("ALTER TABLE scenic_spots ADD COLUMN geofence_radius FLOAT"))
                print("[迁移] 完成!")
            
            result = conn.execute(text("PRAGMA table_info(users)"))
            columns = [row[1] for row in result]
            
            if 'total_points' not in columns:
                print("[迁移] 添加 total_points 列到 users 表...")
                conn.execute(text("ALTER TABLE users ADD COLUMN total_points INTEGER DEFAULT 0"))
                print("[迁移] 完成!")
            
            if 'member_level' not in columns:
                print("[迁移] 添加 member_level 列到 users 表...")
                conn.execute(text("ALTER TABLE users ADD COLUMN member_level VARCHAR(20) DEFAULT '普通'"))
                print("[迁移] 完成!")
            
            result = conn.execute(text("SELECT name FROM sqlite_master WHERE type='table' AND name='coupons'"))
            if not result.fetchone():
                print("[迁移] 创建 coupons 表...")
                conn.execute(text("""
                    CREATE TABLE coupons (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        name VARCHAR(100) NOT NULL,
                        face_value INTEGER NOT NULL,
                        points_required INTEGER NOT NULL,
                        is_active BOOLEAN DEFAULT 1,
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                    )
                """))
                print("[迁移] 完成!")
            
            result = conn.execute(text("SELECT name FROM sqlite_master WHERE type='table' AND name='user_coupons'"))
            if not result.fetchone():
                print("[迁移] 创建 user_coupons 表...")
                conn.execute(text("""
                    CREATE TABLE user_coupons (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id INTEGER NOT NULL,
                        coupon_id INTEGER NOT NULL,
                        redemption_code VARCHAR(20) UNIQUE NOT NULL,
                        is_used BOOLEAN DEFAULT 0,
                        obtained_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        expires_at DATETIME,
                        used_at DATETIME,
                        used_order_id INTEGER,
                        FOREIGN KEY (user_id) REFERENCES users (id),
                        FOREIGN KEY (coupon_id) REFERENCES coupons (id),
                        FOREIGN KEY (used_order_id) REFERENCES ticket_orders (id)
                    )
                """))
                print("[迁移] 完成!")
            else:
                result = conn.execute(text("PRAGMA table_info(user_coupons)"))
                columns = [row[1] for row in result]
                
                if 'redemption_code' not in columns:
                    print("[迁移] 添加 redemption_code 列到 user_coupons 表...")
                    try:
                        conn.execute(text("ALTER TABLE user_coupons ADD COLUMN redemption_code VARCHAR(20)"))
                        print("[迁移] 完成!")
                        
                        print("[迁移] 创建 redemption_code 唯一索引...")
                        conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS idx_user_coupons_redemption_code ON user_coupons(redemption_code)"))
                        print("[迁移] 完成!")
                    except Exception as e:
                        print(f"[迁移] 警告: {e}")
                
                if 'expires_at' not in columns:
                    print("[迁移] 添加 expires_at 列到 user_coupons 表...")
                    conn.execute(text("ALTER TABLE user_coupons ADD COLUMN expires_at DATETIME"))
                    print("[迁移] 完成!")
                
                if 'used_order_id' not in columns:
                    print("[迁移] 添加 used_order_id 列到 user_coupons 表...")
                    conn.execute(text("ALTER TABLE user_coupons ADD COLUMN used_order_id INTEGER"))
                    print("[迁移] 完成!")
            
            result = conn.execute(text("SELECT name FROM sqlite_master WHERE type='table' AND name='point_logs'"))
            if result.fetchone():
                result = conn.execute(text("PRAGMA table_info(point_logs)"))
                columns = [row[1] for row in result]
                
                if 'expires_at' not in columns:
                    print("[迁移] 添加 expires_at 列到 point_logs 表...")
                    conn.execute(text("ALTER TABLE point_logs ADD COLUMN expires_at DATETIME"))
                    print("[迁移] 完成!")
                
                if 'is_expired' not in columns:
                    print("[迁移] 添加 is_expired 列到 point_logs 表...")
                    conn.execute(text("ALTER TABLE point_logs ADD COLUMN is_expired BOOLEAN DEFAULT 0"))
                    print("[迁移] 完成!")
            
            result = conn.execute(text("SELECT name FROM sqlite_master WHERE type='table' AND name='complaints'"))
            if result.fetchone():
                result = conn.execute(text("PRAGMA table_info(complaints)"))
                columns = [row[1] for row in result]
                
                if 'is_points_rewarded' not in columns:
                    print("[迁移] 添加 is_points_rewarded 列到 complaints 表...")
                    conn.execute(text("ALTER TABLE complaints ADD COLUMN is_points_rewarded BOOLEAN DEFAULT 0"))
                    print("[迁移] 完成!")
            
            result = conn.execute(text("SELECT name FROM sqlite_master WHERE type='table' AND name='financial_logs'"))
            if not result.fetchone():
                print("[迁移] 创建 financial_logs 表...")
                conn.execute(text("""
                    CREATE TABLE financial_logs (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        transaction_type VARCHAR(20) NOT NULL,
                        order_no VARCHAR(36),
                        amount FLOAT NOT NULL,
                        transaction_time DATETIME DEFAULT CURRENT_TIMESTAMP,
                        summary VARCHAR(500),
                        related_distributor_id INTEGER,
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (related_distributor_id) REFERENCES distributors (id)
                    )
                """))
                print("[迁移] 完成!")
            
            conn.commit()
        except Exception as e:
            print(f"[迁移] 警告: {e}")


migrate_database()
models.Base.metadata.create_all(bind=engine)


def init_default_admin():
    from database import SessionLocal
    from auth import get_password_hash
    
    db = SessionLocal()
    try:
        existing_admin = db.query(models.User).filter(
            models.User.username == "admin"
        ).first()
        
        if existing_admin is None:
            admin_user = models.User(
                username="admin",
                hashed_password=get_password_hash("admin123"),
                role=models.UserRole.ADMIN,
                phone="13800138000",
                is_active=True
            )
            db.add(admin_user)
            db.commit()
            db.refresh(admin_user)
            print(f"[初始化] 创建默认管理员用户: admin (密码: admin123, 电话: 13800138000)")
        else:
            print(f"[初始化] 默认管理员用户已存在: admin")
        
        existing_test_user = db.query(models.User).filter(
            models.User.username == "test_user"
        ).first()
        
        if existing_test_user is None:
            test_user = models.User(
                username="test_user",
                hashed_password=get_password_hash("test123"),
                role=models.UserRole.TOURIST,
                phone="13912345678",
                is_active=True
            )
            db.add(test_user)
            db.commit()
            db.refresh(test_user)
            print(f"[初始化] 创建测试用户: test_user (密码: test123, 电话: 13912345678)")
        else:
            print(f"[初始化] 测试用户已存在: test_user")
            
    except Exception as e:
        print(f"[初始化警告] 初始化用户时出错: {e}")
        db.rollback()
    finally:
        db.close()


init_default_admin()

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


@app.middleware("http")
async def setup_audit_db_session(request: Request, call_next):
    from database import SessionLocal
    db = SessionLocal()
    try:
        audit_manager = security.get_audit_log_manager()
        audit_manager.set_db_session(db)
        response = await call_next(request)
        return response
    finally:
        db.close()


@app.middleware("http")
async def mask_sensitive_response(request: Request, call_next):
    response = await call_next(request)
    
    try:
        if hasattr(response, 'media_type') and response.media_type == 'application/json':
            import json
            try:
                body_bytes = None
                
                if hasattr(response, '_body'):
                    body_bytes = response._body
                elif hasattr(response, 'body'):
                    if isinstance(response.body, bytes):
                        body_bytes = response.body
                
                if body_bytes:
                    body_str = body_bytes.decode('utf-8')
                    data = json.loads(body_str)
                    masked_data = security.mask_response_content(data)
                    if masked_data != data:
                        from fastapi.responses import JSONResponse
                        new_response = JSONResponse(content=masked_data)
                        new_response.status_code = response.status_code
                        for key, value in response.headers.items():
                            if key.lower() not in ['content-length', 'content-type']:
                                new_response.headers[key] = value
                        return new_response
            except (json.JSONDecodeError, UnicodeDecodeError):
                pass
            except Exception:
                pass
    except Exception:
        pass
    
    return response


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, "static")

if os.path.exists(STATIC_DIR):
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

app.include_router(auth_router)


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


# ScenicSpot endpoints - 仅限 STAFF 角色
@app.post("/scenic-spots/", response_model=schemas.ScenicSpot, status_code=status.HTTP_201_CREATED, tags=["景点管理"])
def create_scenic_spot(
    spot: schemas.ScenicSpotCreate, 
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.require_role(models.UserRole.STAFF))
):
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
    
    result = []
    for spot in spots:
        spot_dict = {
            "id": spot.id,
            "name": spot.name,
            "description": spot.description,
            "location": spot.location,
            "rating": spot.rating,
            "price": spot.price,
            "total_inventory": spot.total_inventory,
            "remained_inventory": spot.remained_inventory,
            "created_at": spot.created_at,
            "status_note": get_scenic_spot_status_note(spot)
        }
        result.append(spot_dict)
    
    return result


def get_scenic_spot_status_note(spot: models.ScenicSpot) -> Optional[str]:
    if spot.total_inventory > 0:
        inventory_ratio = spot.remained_inventory / spot.total_inventory
        if inventory_ratio < 0.10:
            return "🔥 余票紧张，抓紧下单"
    return None


def get_cached_scenic_spot(spot_id: int, db: Session) -> Optional[Dict[str, Any]]:
    current_time = datetime.utcnow()
    
    with cache_lock:
        if spot_id in scenic_spot_cache:
            cache_entry = scenic_spot_cache[spot_id]
            cache_time = cache_entry["timestamp"]
            if (current_time - cache_time).total_seconds() < CACHE_TTL_SECONDS:
                return cache_entry["data"]
    
    spot = db.query(models.ScenicSpot).filter(models.ScenicSpot.id == spot_id).first()
    if spot is None:
        return None
    
    status_note = get_scenic_spot_status_note(spot)
    
    spot_data = {
        "id": spot.id,
        "name": spot.name,
        "description": spot.description,
        "location": spot.location,
        "rating": spot.rating,
        "price": spot.price,
        "total_inventory": spot.total_inventory,
        "remained_inventory": spot.remained_inventory,
        "created_at": spot.created_at,
        "tickets": spot.tickets,
        "status_note": status_note
    }
    
    with cache_lock:
        scenic_spot_cache[spot_id] = {
            "data": spot_data,
            "timestamp": current_time
        }
    
    return spot_data


def invalidate_scenic_spot_cache(spot_id: int):
    with cache_lock:
        if spot_id in scenic_spot_cache:
            del scenic_spot_cache[spot_id]


@app.get("/scenic-spots/{spot_id}", response_model=schemas.ScenicSpotWithTickets, tags=["景点管理"])
def get_scenic_spot(spot_id: int, db: Session = Depends(get_db)):
    spot_data = get_cached_scenic_spot(spot_id, db)
    if spot_data is None:
        raise HTTPException(status_code=404, detail="景点不存在")
    
    class CachedSpot:
        def __init__(self, data):
            for key, value in data.items():
                setattr(self, key, value)
    
    return CachedSpot(spot_data)


@app.put("/scenic-spots/{spot_id}", response_model=schemas.ScenicSpot, tags=["景点管理"])
def update_scenic_spot(
    spot_id: int, 
    spot: schemas.ScenicSpotUpdate, 
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.require_role(models.UserRole.STAFF))
):
    db_spot = db.query(models.ScenicSpot).filter(models.ScenicSpot.id == spot_id).first()
    if db_spot is None:
        raise HTTPException(status_code=404, detail="景点不存在")
    
    for key, value in spot.model_dump(exclude_unset=True).items():
        setattr(db_spot, key, value)
    
    db.commit()
    db.refresh(db_spot)
    
    invalidate_scenic_spot_cache(spot_id)
    
    return db_spot


@app.delete("/scenic-spots/{spot_id}", status_code=status.HTTP_204_NO_CONTENT, tags=["景点管理"])
def delete_scenic_spot(
    spot_id: int, 
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.require_role(models.UserRole.STAFF))
):
    db_spot = db.query(models.ScenicSpot).filter(models.ScenicSpot.id == spot_id).first()
    if db_spot is None:
        raise HTTPException(status_code=404, detail="景点不存在")
    
    db.delete(db_spot)
    db.commit()
    
    invalidate_scenic_spot_cache(spot_id)
    
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


@app.post("/tickets/purchase", response_model=schemas.TicketOrderWithDistributor, status_code=status.HTTP_201_CREATED, tags=["门票支付"])
@security.rate_limit("30/minute")
async def purchase_ticket(
    request: Request,
    order_data: schemas.TicketOrderCreate, 
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.require_role(models.UserRole.TOURIST)),
    ref: Optional[str] = Query(None, description="分销商邀请码（URL参数）"),
    x_distributor_code: Optional[str] = Header(None, alias="X-Distributor-Code", description="分销商邀请码（请求头）")
):
    from sqlalchemy import update as sql_update
    
    order: Optional[models.TicketOrder] = None
    failed_order: Optional[models.TicketOrder] = None
    scenic_spot: Optional[models.ScenicSpot] = None
    user: Optional[models.User] = None
    user_coupon: Optional[models.UserCoupon] = None
    coupon_value: int = 0
    distributor: Optional[models.Distributor] = None
    
    distributor_code = ref or x_distributor_code
    
    if distributor_code:
        distributor = db.query(models.Distributor).filter(
            models.Distributor.distributor_code == distributor_code,
            models.Distributor.is_active == True
        ).first()
        
        if distributor:
            log_info(
                message=f"检测到分销商邀请码: {distributor_code}, 分销商ID: {distributor.id}",
                action="DISTRIBUTOR_CODE_DETECTED",
                tourist_id=order_data.user_id,
                scenic_spot_id=order_data.scenic_spot_id
            )
    
    log_info(
        message="开始处理购票请求",
        action="PURCHASE_REQUEST",
        tourist_id=order_data.user_id,
        scenic_spot_id=order_data.scenic_spot_id,
        quantity=order_data.quantity,
        user_coupon_id=order_data.user_coupon_id
    )
    
    try:
        if order_data.quantity > 5:
            log_error(
                message=f"单笔购票数量超限: {order_data.quantity} 张",
                action="QUANTITY_LIMIT_EXCEEDED",
                tourist_id=order_data.user_id,
                scenic_spot_id=order_data.scenic_spot_id,
                quantity=order_data.quantity
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="单笔订单最多购买 5 张门票"
            )
        
        user = db.query(models.User).filter(
            models.User.id == order_data.user_id
        ).first()
        
        if user is None:
            log_error(
                message="用户不存在",
                action="VALIDATION_FAILED",
                tourist_id=order_data.user_id,
                scenic_spot_id=order_data.scenic_spot_id
            )
            raise HTTPException(status_code=404, detail="用户不存在")
        
        scenic_spot = db.query(models.ScenicSpot).filter(
            models.ScenicSpot.id == order_data.scenic_spot_id
        ).first()
        
        if scenic_spot is None:
            log_error(
                message="景点不存在",
                action="VALIDATION_FAILED",
                tourist_id=order_data.user_id,
                scenic_spot_id=order_data.scenic_spot_id
            )
            raise HTTPException(status_code=404, detail="景点不存在")
        
        log_info(
            message=f"当前库存: {scenic_spot.remained_inventory}",
            action="INVENTORY_CHECK",
            scenic_spot_id=order_data.scenic_spot_id,
            remaining_inventory=scenic_spot.remained_inventory
        )
        
        original_total_price = scenic_spot.price * order_data.quantity
        discounted_price, discount_amount = calculate_discounted_price(
            original_total_price, user.member_level
        )
        
        log_info(
            message=f"会员折扣计算: 原价={original_total_price}, 折扣后={discounted_price}, 减免={discount_amount}, 会员等级={user.member_level.value}",
            action="MEMBER_DISCOUNT_CALCULATED",
            tourist_id=order_data.user_id,
            scenic_spot_id=order_data.scenic_spot_id
        )
        
        if order_data.user_coupon_id is not None:
            user_coupon = db.query(models.UserCoupon).filter(
                models.UserCoupon.id == order_data.user_coupon_id
            ).first()
            
            if user_coupon is None:
                log_error(
                    message=f"优惠券不存在: {order_data.user_coupon_id}",
                    action="COUPON_NOT_FOUND",
                    tourist_id=order_data.user_id
                )
                raise HTTPException(status_code=404, detail="优惠券不存在")
            
            if user_coupon.user_id != user.id:
                log_error(
                    message=f"优惠券不属于当前用户: coupon_id={user_coupon.id}, user_id={user_coupon.user_id}, current_user={user.id}",
                    action="COUPON_OWNERSHIP_ERROR",
                    tourist_id=order_data.user_id
                )
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="优惠券不属于当前用户"
                )
            
            if user_coupon.is_used:
                log_error(
                    message=f"优惠券已使用: coupon_id={user_coupon.id}, redemption_code={user_coupon.redemption_code}",
                    action="COUPON_ALREADY_USED",
                    tourist_id=order_data.user_id
                )
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="优惠券已使用"
                )
            
            now = datetime.utcnow()
            if user_coupon.expires_at and user_coupon.expires_at < now:
                log_error(
                    message=f"优惠券已过期: coupon_id={user_coupon.id}, expires_at={user_coupon.expires_at}",
                    action="COUPON_EXPIRED",
                    tourist_id=order_data.user_id
                )
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="优惠券已过期"
                )
            
            db.refresh(user_coupon, ['coupon'])
            
            if user_coupon.coupon:
                coupon_discount_amount, is_valid, coupon_message = calculate_coupon_discount(
                    discounted_price,
                    user_coupon.coupon,
                    order_data.scenic_spot_id
                )
                
                if not is_valid:
                    log_error(
                        message=f"优惠券验证失败: coupon_id={user_coupon.id}, reason={coupon_message}",
                        action="COUPON_VALIDATION_FAILED",
                        tourist_id=order_data.user_id
                    )
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=coupon_message
                    )
                
                coupon_value = coupon_discount_amount
                
                log_info(
                    message=f"优惠券验证通过: coupon_id={user_coupon.id}, redemption_code={user_coupon.redemption_code}, 类型={user_coupon.coupon.coupon_type.value}, 优惠金额={coupon_value} 元",
                    action="COUPON_VALIDATED",
                    tourist_id=order_data.user_id
                )
            else:
                coupon_value = 0
                log_error(
                    message=f"优惠券数据不完整: coupon_id={user_coupon.id}",
                    action="COUPON_DATA_INCOMPLETE",
                    tourist_id=order_data.user_id
                )
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="优惠券数据不完整"
                )
        else:
            user_coupon = None
            coupon_value = 0
        
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
                user_id=order_data.user_id,
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
        
        total_price = discounted_price
        
        coupon_discount = 0
        if user_coupon and coupon_value > 0:
            coupon_discount = min(coupon_value, total_price)
            total_price = max(0, total_price - coupon_discount)
            
            log_info(
                message=f"优惠券抵扣: 优惠金额={coupon_value} 元, 实际抵扣={coupon_discount} 元, 最终价格={total_price} 元",
                action="COUPON_APPLIED",
                tourist_id=order_data.user_id,
                redemption_code=user_coupon.redemption_code
            )
        
        commission_amount = 0.0
        commission_rate = 0.0
        used_time_limited = False
        if distributor:
            commission_rate = get_applicable_commission_rate(
                db, distributor, order_data.scenic_spot_id
            )
            used_time_limited = (commission_rate != distributor.commission_rate)
            commission_amount = total_price * commission_rate
            
            if used_time_limited:
                log_info(
                    message=f"订单已绑定分销商（限时高佣）: 分销商ID={distributor.id}, 邀请码={distributor.distributor_code}, 原佣金比例={distributor.commission_rate*100}%, 限时佣金比例={commission_rate*100}%, 订单金额={total_price}元, 佣金={commission_amount}元",
                    action="DISTRIBUTOR_BOUND_TIME_LIMITED",
                    order_id=order.order_no,
                    tourist_id=order_data.user_id,
                    scenic_spot_id=order_data.scenic_spot_id,
                    commission_rate=commission_rate,
                    commission_amount=commission_amount
                )
            else:
                log_info(
                    message=f"订单已绑定分销商: 分销商ID={distributor.id}, 邀请码={distributor.distributor_code}, 佣金比例={commission_rate*100}%, 订单金额={total_price}元, 佣金={commission_amount}元",
                    action="DISTRIBUTOR_BOUND",
                    order_id=order.order_no,
                    tourist_id=order_data.user_id,
                    scenic_spot_id=order_data.scenic_spot_id,
                    commission_rate=commission_rate,
                    commission_amount=commission_amount
                )
        
        order = models.TicketOrder(
            user_id=order_data.user_id,
            scenic_spot_id=order_data.scenic_spot_id,
            quantity=order_data.quantity,
            total_price=total_price,
            status=models.OrderStatus.PAID,
            created_at=datetime.utcnow(),
            paid_at=datetime.utcnow(),
            distributor_id=distributor.id if distributor else None,
            commission_amount=commission_amount if distributor else None
        )
        db.add(order)
        db.flush()
        
        if user_coupon:
            user_coupon.is_used = True
            user_coupon.used_at = datetime.utcnow()
            user_coupon.used_order_id = order.id
            
            log_info(
                message=f"优惠券已核销: redemption_code={user_coupon.redemption_code}, 订单号={order.order_no}",
                action="COUPON_REDEEMED",
                tourist_id=order_data.user_id,
                order_id=order.order_no,
                redemption_code=user_coupon.redemption_code
            )
        
        log_info(
            message=f"订单创建成功，订单号: {order.order_no}",
            action="ORDER_CREATED",
            order_id=order.order_no,
            scenic_spot_id=order_data.scenic_spot_id
        )
        
        points_earned = int(total_price)
        
        user.total_points += points_earned
        
        update_member_level(user)
        
        point_log = models.PointLog(
            user_id=order_data.user_id,
            points_change=points_earned,
            reason=f"购票成功获得积分，订单号: {order.order_no}"
        )
        db.add(point_log)
        
        log_info(
            message=f"用户 [{order_data.user_id}] 获得积分: {points_earned}，当前总积分: {user.total_points}",
            action="POINTS_EARNED",
            order_id=order.order_no,
            tourist_id=order_data.user_id,
            quantity=points_earned
        )
        
        income_log = models.FinancialLog(
            transaction_type=models.TransactionType.INCOME,
            order_no=order.order_no,
            amount=total_price,
            transaction_time=datetime.utcnow(),
            summary=f"门票销售收入，订单号: {order.order_no}, 景点ID: {order_data.scenic_spot_id}, 数量: {order_data.quantity}"
        )
        db.add(income_log)
        
        log_info(
            message=f"财务流水已记录: 收入 +{total_price} 元, 订单号: {order.order_no}",
            action="FINANCIAL_LOG_INCOME",
            order_id=order.order_no,
            scenic_spot_id=order_data.scenic_spot_id
        )
        
        if distributor and commission_amount > 0:
            distribution_expense_log = models.FinancialLog(
                transaction_type=models.TransactionType.DISTRIBUTION_EXPENSE,
                order_no=order.order_no,
                amount=commission_amount,
                transaction_time=datetime.utcnow(),
                summary=f"分销佣金支出，订单号: {order.order_no}, 分销商ID: {distributor.id}, 佣金比例: {distributor.commission_rate * 100}%",
                related_distributor_id=distributor.id
            )
            db.add(distribution_expense_log)
            
            log_info(
                message=f"财务流水已记录: 分销支出 -{commission_amount} 元, 订单号: {order.order_no}, 分销商ID: {distributor.id}",
                action="FINANCIAL_LOG_DISTRIBUTION_EXPENSE",
                order_id=order.order_no,
                tourist_id=distributor.id
            )
        
        db.commit()
        db.refresh(order)
        db.refresh(user)
        
        if user_coupon:
            db.refresh(user_coupon)
        
        invalidate_scenic_spot_cache(order_data.scenic_spot_id)
        
        log_info(
            message=f"支付成功，订单号: {order.order_no}, 支付时间: {order.paid_at}, 原价: {original_total_price}, 会员折扣减免: {discount_amount}, 优惠券抵扣: {coupon_discount}, 实付: {total_price}",
            action="PAYMENT_SUCCESS",
            order_id=order.order_no,
            scenic_spot_id=order_data.scenic_spot_id
        )
        
        log_info(
            message=f"祝贺用户 [{order_data.user_id}] 抢票成功！请提醒其准时入园。",
            action="TICKET_SUCCESS_NOTIFICATION",
            order_id=order.order_no,
            tourist_id=order_data.user_id,
            scenic_spot_id=order_data.scenic_spot_id,
            quantity=order_data.quantity
        )
        
        audit_manager = security.get_audit_log_manager()
        audit_manager.log_action(
            user_id=current_user.id,
            module=models.AuditLogModule.ORDER,
            action=models.AuditLogAction.CREATE,
            target_id=order.id,
            target_type="TicketOrder",
            details=f"用户 {current_user.username} 购买门票成功: 订单号={order.order_no}, 景点ID={order_data.scenic_spot_id}, 数量={order_data.quantity}, 金额={total_price}元",
            ip_address=request.client.host if request.client else None
        )
        
        return schemas.TicketOrderWithDistributor(
            id=order.id,
            order_no=order.order_no,
            user_id=order.user_id,
            scenic_spot_id=order.scenic_spot_id,
            quantity=order.quantity,
            total_price=order.total_price,
            status=order.status,
            created_at=order.created_at,
            paid_at=order.paid_at,
            distributor_id=order.distributor_id,
            distributor_code=distributor.distributor_code if distributor else None,
            commission_amount=order.commission_amount
        )
        
    except HTTPException:
        raise
        
    except Exception as e:
        db.rollback()
        
        log_error(
            message=f"购票过程中发生系统错误: {str(e)}",
            action="SYSTEM_ERROR",
            tourist_id=order_data.user_id,
            scenic_spot_id=order_data.scenic_spot_id,
            exc_info=True
        )
        
        try:
            failed_order = models.TicketOrder(
                user_id=order_data.user_id,
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


def get_time_ago(dt: datetime) -> str:
    if dt is None:
        return "刚刚"
    
    now = datetime.utcnow()
    diff = now - dt
    
    seconds = diff.total_seconds()
    
    if seconds < 60:
        return "刚刚"
    elif seconds < 3600:
        minutes = int(seconds // 60)
        return f"{minutes} 分钟前"
    elif seconds < 86400:
        hours = int(seconds // 3600)
        return f"{hours} 小时前"
    else:
        days = int(seconds // 86400)
        return f"{days} 天前"


def update_member_level(user: models.User):
    if user.total_points >= 5000:
        user.member_level = models.MemberLevel.GOLD
    elif user.total_points >= 1000:
        user.member_level = models.MemberLevel.SILVER
    else:
        user.member_level = models.MemberLevel.NORMAL


def get_member_discount_rate(member_level: models.MemberLevel) -> float:
    if member_level == models.MemberLevel.GOLD:
        return 0.90
    elif member_level == models.MemberLevel.SILVER:
        return 0.95
    return 1.00


def calculate_discounted_price(original_price: float, member_level: models.MemberLevel) -> tuple[float, float]:
    discount_rate = get_member_discount_rate(member_level)
    discounted_price = original_price * discount_rate
    discount_amount = original_price - discounted_price
    return round(discounted_price, 2), round(discount_amount, 2)


def calculate_coupon_discount(
    total_price: float,
    coupon: models.Coupon,
    scenic_spot_id: int
) -> tuple[float, bool, str]:
    if not coupon.is_active:
        return 0.0, False, "优惠券已下架"
    
    now = datetime.utcnow()
    if coupon.valid_from > now:
        return 0.0, False, "优惠券尚未生效"
    if coupon.valid_to < now:
        return 0.0, False, "优惠券已过期"
    
    if coupon.target_scenic_spot_id and coupon.target_scenic_spot_id != scenic_spot_id:
        return 0.0, False, "该优惠券不适用于当前景点"
    
    if total_price < coupon.min_spend:
        return 0.0, False, f"未达到最低消费门槛 {coupon.min_spend} 元"
    
    if coupon.coupon_type == models.CouponType.FIXED_AMOUNT:
        discount_amount = coupon.discount_value
    elif coupon.coupon_type == models.CouponType.DISCOUNT:
        if coupon.discount_percentage is None:
            return 0.0, False, "折扣券配置错误"
        discount_amount = total_price * (1 - coupon.discount_percentage)
        if coupon.max_discount:
            discount_amount = min(discount_amount, coupon.max_discount)
    else:
        return 0.0, False, "未知的优惠券类型"
    
    discount_amount = round(discount_amount, 2)
    
    return discount_amount, True, "优惠券可用"


def get_applicable_commission_rate(
    db: Session,
    distributor: models.Distributor,
    scenic_spot_id: int
) -> float:
    now = datetime.utcnow()
    
    time_limited = db.query(models.TimeLimitedCommission).filter(
        models.TimeLimitedCommission.is_active == True,
        models.TimeLimitedCommission.valid_from <= now,
        models.TimeLimitedCommission.valid_to >= now
    ).order_by(
        models.TimeLimitedCommission.created_at.desc()
    ).all()
    
    for tlc in time_limited:
        if tlc.distributor_id and tlc.distributor_id != distributor.id:
            continue
        if tlc.scenic_spot_id and tlc.scenic_spot_id != scenic_spot_id:
            continue
        return tlc.commission_rate
    
    return distributor.commission_rate


@app.get("/tickets/recent-success", response_model=List[schemas.TicketSuccessBrief], tags=["门票支付"])
def get_recent_success_orders(limit: int = 5, db: Session = Depends(get_db)):
    orders = db.query(models.TicketOrder).filter(
        models.TicketOrder.status == models.OrderStatus.PAID
    ).order_by(
        models.TicketOrder.paid_at.desc()
    ).limit(limit).all()
    
    result = []
    for order in orders:
        user = db.query(models.User).filter(
            models.User.id == order.user_id
        ).first()
        
        scenic_spot = db.query(models.ScenicSpot).filter(
            models.ScenicSpot.id == order.scenic_spot_id
        ).first()
        
        tourist_name = user.username if user else "未知用户"
        scenic_spot_name = scenic_spot.name if scenic_spot else "未知景点"
        
        time_ago = get_time_ago(order.paid_at)
        
        brief = schemas.TicketSuccessBrief(
            order_no=order.order_no,
            tourist_name=tourist_name,
            scenic_spot_name=scenic_spot_name,
            quantity=order.quantity,
            paid_at=order.paid_at,
            time_ago=time_ago
        )
        result.append(brief)
    
    return result


@app.get("/system/health", tags=["系统监控"])
def get_system_health(
    current_user: models.User = Depends(auth.require_role(models.UserRole.ADMIN))
):
    report = get_analytics_report()
    return report


@app.get("/analytics/traffic-series", tags=["流量监控"])
def get_traffic_series(
    spot_id: int, 
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_active_user)
):
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


@app.post("/complaints", response_model=schemas.Complaint, status_code=status.HTTP_201_CREATED, tags=["投诉咨询"])
def create_complaint(
    complaint_data: schemas.ComplaintCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.require_role(models.UserRole.TOURIST))
):
    new_complaint = models.Complaint(
        user_id=current_user.id,
        title=complaint_data.title,
        content=complaint_data.content,
        status=models.ComplaintStatus.PENDING,
        is_points_rewarded=False,
        created_at=datetime.utcnow()
    )
    db.add(new_complaint)
    
    log_info(
        message=f"用户 [{current_user.id}] 提交投诉反馈，等待管理员回复",
        action="COMPLAINT_CREATED",
        tourist_id=current_user.id
    )
    
    db.commit()
    db.refresh(new_complaint)
    return new_complaint


@app.get("/complaints/my", response_model=List[schemas.Complaint], tags=["投诉咨询"])
def get_my_complaints(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_active_user)
):
    complaints = db.query(models.Complaint).filter(
        models.Complaint.user_id == current_user.id
    ).order_by(models.Complaint.created_at.desc()).offset(skip).limit(limit).all()
    return complaints


@app.get("/complaints/all", response_model=List[schemas.ComplaintWithUser], tags=["投诉咨询"])
def get_all_complaints(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.require_role(models.UserRole.STAFF, models.UserRole.ADMIN))
):
    complaints = db.query(models.Complaint).order_by(
        models.Complaint.created_at.desc()
    ).offset(skip).limit(limit).all()
    return complaints


@app.patch("/complaints/{complaint_id}", response_model=schemas.Complaint, tags=["投诉咨询"])
def update_complaint(
    complaint_id: int,
    update_data: schemas.ComplaintUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.require_role(models.UserRole.STAFF, models.UserRole.ADMIN))
):
    complaint = db.query(models.Complaint).filter(
        models.Complaint.id == complaint_id
    ).first()
    
    if complaint is None:
        raise HTTPException(status_code=404, detail="投诉不存在")
    
    update_dict = update_data.model_dump(exclude_unset=True)
    
    is_replying = False
    if "reply" in update_dict and not complaint.is_points_rewarded:
        new_reply = update_dict["reply"]
        if new_reply and new_reply.strip():
            is_replying = True
    
    if "reply" in update_dict:
        complaint.reply = update_dict["reply"]
    
    if "status" in update_dict:
        complaint.status = update_dict["status"]
    
    if is_replying:
        points_earned = 50
        
        user = db.query(models.User).filter(
            models.User.id == complaint.user_id
        ).first()
        
        if user:
            user.total_points += points_earned
            
            point_log = models.PointLog(
                user_id=complaint.user_id,
                points_change=points_earned,
                reason=f"投诉反馈获得积分，投诉ID: {complaint.id}"
            )
            db.add(point_log)
            
            update_member_level(user)
            
            complaint.is_points_rewarded = True
            
            log_info(
                message=f"管理员回复投诉 [{complaint.id}]，用户 [{complaint.user_id}] 获得 {points_earned} 积分",
                action="COMPLAINT_REPLY_POINTS_EARNED",
                tourist_id=complaint.user_id
            )
    
    db.commit()
    db.refresh(complaint)
    return complaint


@app.get("/member/profile", response_model=schemas.MemberProfileResponse, tags=["会员积分"])
def get_member_profile(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_active_user)
):
    from datetime import timedelta
    
    now = datetime.utcnow()
    
    expired_logs = db.query(models.PointLog).filter(
        models.PointLog.user_id == current_user.id,
        models.PointLog.points_change > 0,
        models.PointLog.is_expired == False,
        models.PointLog.expires_at <= now
    ).all()
    
    if expired_logs:
        expired_points = sum(log.points_change for log in expired_logs)
        
        for log in expired_logs:
            log.is_expired = True
        
        if current_user.total_points >= expired_points:
            current_user.total_points -= expired_points
        else:
            current_user.total_points = 0
        
        expiration_log = models.PointLog(
            user_id=current_user.id,
            points_change=-expired_points,
            reason=f"积分过期自动扣减，过期数量: {expired_points} 分",
            is_expired=False
        )
        db.add(expiration_log)
        
        log_info(
            message=f"用户 [{current_user.id}] 过期积分自动扣减: {expired_points} 分",
            action="POINTS_EXPIRED",
            tourist_id=current_user.id,
            quantity=expired_points
        )
        
        db.commit()
        db.refresh(current_user)
    
    recent_logs = db.query(models.PointLog).filter(
        models.PointLog.user_id == current_user.id
    ).order_by(
        models.PointLog.created_at.desc()
    ).limit(5).all()
    
    threshold_30d = now + timedelta(days=30)
    threshold_7d = now + timedelta(days=7)
    
    expiring_logs_30d = db.query(models.PointLog).filter(
        models.PointLog.user_id == current_user.id,
        models.PointLog.points_change > 0,
        models.PointLog.is_expired == False,
        models.PointLog.expires_at <= threshold_30d
    ).all()
    
    expiring_logs_7d = db.query(models.PointLog).filter(
        models.PointLog.user_id == current_user.id,
        models.PointLog.points_change > 0,
        models.PointLog.is_expired == False,
        models.PointLog.expires_at <= threshold_7d
    ).all()
    
    expiring_points_30d = sum(log.points_change for log in expiring_logs_30d)
    expiring_points_7d = sum(log.points_change for log in expiring_logs_7d)
    
    return schemas.MemberProfileResponse(
        user_id=current_user.id,
        username=current_user.username,
        member_level=current_user.member_level,
        total_points=current_user.total_points,
        expiring_points_30d=expiring_points_30d,
        expiring_points_7d=expiring_points_7d,
        recent_logs=recent_logs
    )


@app.get("/member/coupons/available", response_model=List[schemas.Coupon], tags=["会员积分"])
def get_available_coupons(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_active_user)
):
    coupons = db.query(models.Coupon).filter(
        models.Coupon.is_active == True
    ).order_by(models.Coupon.points_required).all()
    return coupons


@app.get("/member/coupons/my", response_model=List[schemas.UserCoupon], tags=["会员积分"])
def get_my_coupons(
    include_used: bool = False,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_active_user)
):
    query = db.query(models.UserCoupon).filter(
        models.UserCoupon.user_id == current_user.id
    )
    
    if not include_used:
        query = query.filter(models.UserCoupon.is_used == False)
    
    user_coupons = query.order_by(models.UserCoupon.obtained_at.desc()).all()
    
    for uc in user_coupons:
        db.refresh(uc, ['coupon'])
    
    return user_coupons


@app.post("/member/exchange", response_model=schemas.ExchangeResponse, tags=["会员积分"])
def exchange_coupon(
    exchange_data: schemas.ExchangeRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.require_role(models.UserRole.TOURIST))
):
    coupon = db.query(models.Coupon).filter(
        models.Coupon.id == exchange_data.coupon_id,
        models.Coupon.is_active == True
    ).first()
    
    if coupon is None:
        return schemas.ExchangeResponse(
            success=False,
            message="优惠券不存在或已下架",
            remaining_points=current_user.total_points
        )
    
    if current_user.total_points < coupon.points_required:
        return schemas.ExchangeResponse(
            success=False,
            message=f"积分不足，需要 {coupon.points_required} 积分，当前只有 {current_user.total_points} 积分",
            remaining_points=current_user.total_points
        )
    
    try:
        current_user.total_points -= coupon.points_required
        
        user_coupon = models.UserCoupon(
            user_id=current_user.id,
            coupon_id=coupon.id,
            is_used=False,
            obtained_at=datetime.utcnow()
        )
        db.add(user_coupon)
        
        point_log = models.PointLog(
            user_id=current_user.id,
            points_change=-coupon.points_required,
            reason=f"积分兑换优惠券: {coupon.name}"
        )
        db.add(point_log)
        
        db.commit()
        db.refresh(user_coupon)
        db.refresh(current_user)
        
        db.refresh(user_coupon, ['coupon'])
        
        log_info(
            message=f"用户 [{current_user.id}] 成功兑换优惠券: {coupon.name}, 消耗积分: {coupon.points_required}",
            action="COUPON_EXCHANGED",
            tourist_id=current_user.id
        )
        
        return schemas.ExchangeResponse(
            success=True,
            message=f"成功兑换 [{coupon.name}]，面值 {coupon.face_value} 元",
            user_coupon=user_coupon,
            remaining_points=current_user.total_points
        )
        
    except Exception as e:
        db.rollback()
        log_error(
            message=f"兑换优惠券时发生错误: {str(e)}",
            action="EXCHANGE_ERROR",
            tourist_id=current_user.id,
            exc_info=True
        )
        return schemas.ExchangeResponse(
            success=False,
            message="兑换失败，请稍后重试",
            remaining_points=current_user.total_points
        )


distributor_router = APIRouter(prefix="/distributors", tags=["分销管理"])


@distributor_router.post("/", response_model=schemas.Distributor, status_code=status.HTTP_201_CREATED)
def create_distributor(
    distributor_data: schemas.DistributorCreate,
    db: Session = Depends(get_db),
    current_admin: models.User = Depends(auth.require_role(models.UserRole.ADMIN, models.UserRole.STAFF))
):
    existing_distributor = db.query(models.Distributor).filter(
        models.Distributor.user_id == distributor_data.user_id
    ).first()
    
    if existing_distributor:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="该用户已经是分销商"
        )
    
    user = db.query(models.User).filter(
        models.User.id == distributor_data.user_id
    ).first()
    
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用户不存在"
        )
    
    new_distributor = models.Distributor(
        user_id=distributor_data.user_id,
        commission_rate=distributor_data.commission_rate or 0.05,
        is_active=True
    )
    
    db.add(new_distributor)
    db.commit()
    db.refresh(new_distributor)
    
    log_info(
        message=f"创建分销商成功: 用户ID={distributor_data.user_id}, 邀请码={new_distributor.distributor_code}, 佣金比例={new_distributor.commission_rate}",
        action="DISTRIBUTOR_CREATED",
        tourist_id=distributor_data.user_id
    )
    
    return new_distributor


@distributor_router.get("/", response_model=List[schemas.DistributorWithDetails])
def get_distributors(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_admin: models.User = Depends(auth.require_role(models.UserRole.ADMIN))
):
    distributors = db.query(models.Distributor).order_by(
        models.Distributor.created_at.desc()
    ).offset(skip).limit(limit).all()
    
    result = []
    for distributor in distributors:
        db.refresh(distributor, ['user'])
        result.append(distributor)
    
    return result


@distributor_router.get("/{distributor_id}", response_model=schemas.DistributorWithDetails)
def get_distributor(
    distributor_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_active_user)
):
    distributor = db.query(models.Distributor).filter(
        models.Distributor.id == distributor_id
    ).first()
    
    if distributor is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="分销商不存在"
        )
    
    if current_user.role not in [models.UserRole.ADMIN, models.UserRole.STAFF]:
        if distributor.user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="无权查看其他分销商信息"
            )
    
    db.refresh(distributor, ['user'])
    return distributor


@distributor_router.get("/code/{distributor_code}", response_model=schemas.Distributor)
def get_distributor_by_code(
    distributor_code: str,
    db: Session = Depends(get_db)
):
    distributor = db.query(models.Distributor).filter(
        models.Distributor.distributor_code == distributor_code,
        models.Distributor.is_active == True
    ).first()
    
    if distributor is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="分销商邀请码无效或已停用"
        )
    
    return distributor


@distributor_router.put("/{distributor_id}", response_model=schemas.Distributor)
def update_distributor(
    distributor_id: int,
    update_data: schemas.DistributorUpdate,
    db: Session = Depends(get_db),
    current_admin: models.User = Depends(auth.require_role(models.UserRole.ADMIN))
):
    distributor = db.query(models.Distributor).filter(
        models.Distributor.id == distributor_id
    ).first()
    
    if distributor is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="分销商不存在"
        )
    
    update_dict = update_data.model_dump(exclude_unset=True)
    
    for key, value in update_dict.items():
        setattr(distributor, key, value)
    
    db.commit()
    db.refresh(distributor)
    
    log_info(
        message=f"更新分销商信息: 分销商ID={distributor_id}, 更新字段={list(update_dict.keys())}",
        action="DISTRIBUTOR_UPDATED"
    )
    
    return distributor


@distributor_router.post("/generate-link", response_model=Dict[str, str])
def generate_promotion_link(
    spot_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_active_user)
):
    distributor = db.query(models.Distributor).filter(
        models.Distributor.user_id == current_user.id,
        models.Distributor.is_active == True
    ).first()
    
    if distributor is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="您不是有效的分销商"
        )
    
    scenic_spot = db.query(models.ScenicSpot).filter(
        models.ScenicSpot.id == spot_id
    ).first()
    
    if scenic_spot is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="景点不存在"
        )
    
    promotion_link = f"/?ref={distributor.distributor_code}&spot={spot_id}"
    full_link = f"http://localhost:8000{promotion_link}"
    
    log_info(
        message=f"分销商 [{distributor.id}] 生成景点 [{spot_id}] 的推广链接",
        action="PROMOTION_LINK_GENERATED",
        tourist_id=current_user.id,
        scenic_spot_id=spot_id
    )
    
    return {
        "distributor_code": distributor.distributor_code,
        "spot_id": str(spot_id),
        "promotion_link": promotion_link,
        "full_link": full_link,
        "commission_rate": f"{distributor.commission_rate * 100}%"
    }


@distributor_router.get("/me/earnings", response_model=schemas.DistributorEarnings)
def get_my_earnings(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_active_user)
):
    distributor = db.query(models.Distributor).filter(
        models.Distributor.user_id == current_user.id,
        models.Distributor.is_active == True
    ).first()
    
    if distributor is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="您不是有效的分销商"
        )
    
    from sqlalchemy import func
    
    order_stats = db.query(
        func.count(models.TicketOrder.id).label('total_orders'),
        func.sum(models.TicketOrder.total_price).label('total_revenue'),
        func.sum(models.TicketOrder.commission_amount).label('total_commission')
    ).filter(
        models.TicketOrder.distributor_id == distributor.id,
        models.TicketOrder.status == models.OrderStatus.PAID
    ).first()
    
    total_orders = order_stats.total_orders or 0
    total_revenue = order_stats.total_revenue or 0.0
    total_commission = order_stats.total_commission or 0.0
    
    log_info(
        message=f"分销商 [{distributor.id}] 查询收益: 订单数={total_orders}, 总收入={total_revenue}, 总佣金={total_commission}",
        action="DISTRIBUTOR_EARNINGS_QUERIED",
        tourist_id=current_user.id
    )
    
    return schemas.DistributorEarnings(
        distributor_id=distributor.id,
        distributor_code=distributor.distributor_code,
        total_orders=total_orders,
        total_revenue=total_revenue,
        total_commission=total_commission,
        commission_rate=distributor.commission_rate
    )


@distributor_router.get("/me/orders", response_model=List[schemas.DistributorOrderListItem])
def get_my_orders(
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_active_user)
):
    distributor = db.query(models.Distributor).filter(
        models.Distributor.user_id == current_user.id,
        models.Distributor.is_active == True
    ).first()
    
    if distributor is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="您不是有效的分销商"
        )
    
    orders = db.query(models.TicketOrder).filter(
        models.TicketOrder.distributor_id == distributor.id
    ).order_by(
        models.TicketOrder.created_at.desc()
    ).offset(skip).limit(limit).all()
    
    result = []
    for order in orders:
        spot_name = None
        if order.scenic_spot:
            spot_name = order.scenic_spot.name
        
        result.append(schemas.DistributorOrderListItem(
            id=order.id,
            order_no=order.order_no,
            user_id=order.user_id,
            scenic_spot_id=order.scenic_spot_id,
            quantity=order.quantity,
            total_price=order.total_price,
            status=order.status,
            created_at=order.created_at,
            paid_at=order.paid_at,
            distributor_id=order.distributor_id,
            commission_amount=order.commission_amount,
            scenic_spot_name=spot_name
        ))
    
    log_info(
        message=f"分销商 [{distributor.id}] 查询订单列表: 共 {len(result)} 条",
        action="DISTRIBUTOR_ORDERS_QUERIED",
        tourist_id=current_user.id
    )
    
    return result


@distributor_router.get("/me/status")
def get_my_distributor_status(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_active_user)
):
    distributor = db.query(models.Distributor).filter(
        models.Distributor.user_id == current_user.id
    ).first()
    
    if distributor is None:
        return {
            "is_distributor": False,
            "message": "您不是分销商"
        }
    
    from sqlalchemy import func
    
    order_stats = db.query(
        func.count(models.TicketOrder.id).label('total_orders'),
        func.sum(models.TicketOrder.commission_amount).label('total_commission')
    ).filter(
        models.TicketOrder.distributor_id == distributor.id,
        models.TicketOrder.status == models.OrderStatus.PAID
    ).first()
    
    return {
        "is_distributor": True,
        "is_active": distributor.is_active,
        "distributor_id": distributor.id,
        "distributor_code": distributor.distributor_code,
        "commission_rate": distributor.commission_rate,
        "total_orders": order_stats.total_orders or 0,
        "total_commission": order_stats.total_commission or 0.0,
        "created_at": distributor.created_at
    }


@distributor_router.get("/me/finance", response_model=schemas.DistributorFinanceReport)
def get_distributor_finance(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_active_user)
):
    distributor = db.query(models.Distributor).filter(
        models.Distributor.user_id == current_user.id,
        models.Distributor.is_active == True
    ).first()
    
    if distributor is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="您不是有效的分销商"
        )
    
    from sqlalchemy import func, and_
    from datetime import datetime, date, timedelta
    
    today_start = datetime.combine(date.today(), datetime.min.time())
    
    total_stats = db.query(
        func.count(models.TicketOrder.id).label('total_orders'),
        func.sum(models.TicketOrder.total_price).label('total_revenue'),
        func.sum(models.TicketOrder.commission_amount).label('total_commission')
    ).filter(
        models.TicketOrder.distributor_id == distributor.id,
        models.TicketOrder.status == models.OrderStatus.PAID
    ).first()
    
    settled_stats = db.query(
        func.count(models.TicketOrder.id).label('settled_orders'),
        func.sum(models.TicketOrder.commission_amount).label('settled_commission')
    ).filter(
        models.TicketOrder.distributor_id == distributor.id,
        models.TicketOrder.status == models.OrderStatus.PAID,
        models.TicketOrder.is_settled == True
    ).first()
    
    pending_stats = db.query(
        func.count(models.TicketOrder.id).label('pending_orders'),
        func.sum(models.TicketOrder.commission_amount).label('pending_commission')
    ).filter(
        models.TicketOrder.distributor_id == distributor.id,
        models.TicketOrder.status == models.OrderStatus.PAID,
        models.TicketOrder.is_settled == False
    ).first()
    
    today_stats = db.query(
        func.count(models.TicketOrder.id).label('today_orders'),
        func.sum(models.TicketOrder.total_price).label('today_revenue'),
        func.sum(models.TicketOrder.commission_amount).label('today_commission')
    ).filter(
        models.TicketOrder.distributor_id == distributor.id,
        models.TicketOrder.status == models.OrderStatus.PAID,
        models.TicketOrder.created_at >= today_start
    ).first()
    
    log_info(
        message=f"分销商 [{distributor.id}] 查询财务报表",
        action="DISTRIBUTOR_FINANCE_QUERIED",
        tourist_id=current_user.id
    )
    
    return schemas.DistributorFinanceReport(
        distributor_id=distributor.id,
        distributor_code=distributor.distributor_code,
        commission_rate=distributor.commission_rate,
        total_orders=total_stats.total_orders or 0,
        total_revenue=total_stats.total_revenue or 0.0,
        total_commission=total_stats.total_commission or 0.0,
        settled_orders=settled_stats.settled_orders or 0,
        settled_commission=settled_stats.settled_commission or 0.0,
        pending_orders=pending_stats.pending_orders or 0,
        pending_commission=pending_stats.pending_commission or 0.0,
        today_orders=today_stats.today_orders or 0,
        today_revenue=today_stats.today_revenue or 0.0,
        today_commission=today_stats.today_commission or 0.0
    )


@distributor_router.get("/me/finance/orders", response_model=List[schemas.FinanceOrderItem])
def get_distributor_finance_orders(
    is_settled: Optional[bool] = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_active_user)
):
    distributor = db.query(models.Distributor).filter(
        models.Distributor.user_id == current_user.id,
        models.Distributor.is_active == True
    ).first()
    
    if distributor is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="您不是有效的分销商"
        )
    
    query = db.query(models.TicketOrder).filter(
        models.TicketOrder.distributor_id == distributor.id,
        models.TicketOrder.status == models.OrderStatus.PAID
    )
    
    if is_settled is not None:
        query = query.filter(models.TicketOrder.is_settled == is_settled)
    
    orders = query.order_by(
        models.TicketOrder.created_at.desc()
    ).offset(skip).limit(limit).all()
    
    result = []
    for order in orders:
        spot_name = None
        if order.scenic_spot:
            spot_name = order.scenic_spot.name
        
        order_date = None
        if order.created_at:
            order_date = order.created_at.strftime("%Y-%m-%d %H:%M:%S")
        
        result.append(schemas.FinanceOrderItem(
            order_no=order.order_no,
            scenic_spot_name=spot_name,
            order_date=order_date,
            quantity=order.quantity,
            total_price=order.total_price,
            commission_amount=order.commission_amount,
            is_settled=order.is_settled
        ))
    
    return result


marketing_router = APIRouter(prefix="/marketing", tags=["营销引擎与精细化运营"])


@marketing_router.post("/coupons", response_model=schemas.Coupon, status_code=status.HTTP_201_CREATED)
def create_coupon(
    coupon_data: schemas.CouponCreate,
    db: Session = Depends(get_db),
    current_admin: models.User = Depends(auth.require_role(models.UserRole.ADMIN, models.UserRole.STAFF))
):
    if coupon_data.coupon_type == models.CouponType.DISCOUNT:
        if coupon_data.discount_percentage is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="折扣券必须指定折扣比例"
            )
        if coupon_data.discount_percentage <= 0 or coupon_data.discount_percentage >= 1:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="折扣比例必须在 0 到 1 之间（不包括边界）"
            )
    
    if coupon_data.valid_to <= coupon_data.valid_from:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="有效期结束时间必须晚于开始时间"
        )
    
    new_coupon = models.Coupon(
        name=coupon_data.name,
        coupon_type=coupon_data.coupon_type,
        discount_value=coupon_data.discount_value,
        discount_percentage=coupon_data.discount_percentage,
        min_spend=coupon_data.min_spend,
        max_discount=coupon_data.max_discount,
        valid_from=coupon_data.valid_from,
        valid_to=coupon_data.valid_to,
        total_stock=coupon_data.total_stock,
        remained_stock=coupon_data.remained_stock,
        points_required=coupon_data.points_required,
        target_member_level=coupon_data.target_member_level,
        target_scenic_spot_id=coupon_data.target_scenic_spot_id,
        is_active=coupon_data.is_active
    )
    
    db.add(new_coupon)
    db.commit()
    db.refresh(new_coupon)
    
    log_info(
        message=f"管理员 [{current_admin.id}] 创建了优惠券: {new_coupon.name}",
        action="COUPON_CREATED",
        tourist_id=current_admin.id
    )
    
    return new_coupon


@marketing_router.get("/coupons", response_model=List[schemas.Coupon])
def list_coupons(
    is_active: Optional[bool] = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_active_user)
):
    query = db.query(models.Coupon)
    
    if is_active is not None:
        query = query.filter(models.Coupon.is_active == is_active)
    
    coupons = query.order_by(models.Coupon.created_at.desc()).offset(skip).limit(limit).all()
    return coupons


@marketing_router.get("/coupons/{coupon_id}", response_model=schemas.Coupon)
def get_coupon(
    coupon_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_active_user)
):
    coupon = db.query(models.Coupon).filter(models.Coupon.id == coupon_id).first()
    if coupon is None:
        raise HTTPException(status_code=404, detail="优惠券不存在")
    return coupon


@marketing_router.put("/coupons/{coupon_id}", response_model=schemas.Coupon)
def update_coupon(
    coupon_id: int,
    coupon_data: schemas.CouponUpdate,
    db: Session = Depends(get_db),
    current_admin: models.User = Depends(auth.require_role(models.UserRole.ADMIN, models.UserRole.STAFF))
):
    coupon = db.query(models.Coupon).filter(models.Coupon.id == coupon_id).first()
    if coupon is None:
        raise HTTPException(status_code=404, detail="优惠券不存在")
    
    update_data = coupon_data.model_dump(exclude_unset=True)
    
    if "valid_from" in update_data and "valid_to" in update_data:
        if update_data["valid_to"] <= update_data["valid_from"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="有效期结束时间必须晚于开始时间"
            )
    
    for key, value in update_data.items():
        setattr(coupon, key, value)
    
    db.commit()
    db.refresh(coupon)
    
    log_info(
        message=f"管理员 [{current_admin.id}] 更新了优惠券: {coupon.name}",
        action="COUPON_UPDATED",
        tourist_id=current_admin.id
    )
    
    return coupon


@marketing_router.delete("/coupons/{coupon_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_coupon(
    coupon_id: int,
    db: Session = Depends(get_db),
    current_admin: models.User = Depends(auth.require_role(models.UserRole.ADMIN, models.UserRole.STAFF))
):
    coupon = db.query(models.Coupon).filter(models.Coupon.id == coupon_id).first()
    if coupon is None:
        raise HTTPException(status_code=404, detail="优惠券不存在")
    
    coupon_name = coupon.name
    db.delete(coupon)
    db.commit()
    
    log_info(
        message=f"管理员 [{current_admin.id}] 删除了优惠券: {coupon_name}",
        action="COUPON_DELETED",
        tourist_id=current_admin.id
    )


@marketing_router.post("/assign-coupon", response_model=schemas.AssignCouponResponse)
def assign_coupon(
    request: Request,
    assign_data: schemas.AssignCouponRequest,
    db: Session = Depends(get_db),
    current_admin: models.User = Depends(auth.require_role(models.UserRole.ADMIN, models.UserRole.STAFF))
):
    coupon = db.query(models.Coupon).filter(
        models.Coupon.id == assign_data.coupon_id,
        models.Coupon.is_active == True
    ).first()
    
    if coupon is None:
        return schemas.AssignCouponResponse(
            success=False,
            message="优惠券不存在或已下架",
            assigned_count=0,
            failed_count=0,
            failed_user_ids=[]
        )
    
    now = datetime.utcnow()
    if coupon.valid_from > now:
        return schemas.AssignCouponResponse(
            success=False,
            message="优惠券尚未开始发放",
            assigned_count=0,
            failed_count=0,
            failed_user_ids=[]
        )
    
    if coupon.valid_to < now:
        return schemas.AssignCouponResponse(
            success=False,
            message="优惠券已过期",
            assigned_count=0,
            failed_count=0,
            failed_user_ids=[]
        )
    
    target_users = []
    
    if assign_data.user_ids and len(assign_data.user_ids) > 0:
        query = db.query(models.User).filter(
            models.User.id.in_(assign_data.user_ids),
            models.User.is_active == True
        )
        if assign_data.target_member_level:
            query = query.filter(models.User.member_level == assign_data.target_member_level)
        target_users = query.all()
    else:
        query = db.query(models.User).filter(models.User.is_active == True)
        if assign_data.target_member_level:
            query = query.filter(models.User.member_level == assign_data.target_member_level)
        target_users = query.all()
    
    if not target_users:
        return schemas.AssignCouponResponse(
            success=True,
            message="没有符合条件的用户",
            assigned_count=0,
            failed_count=0,
            failed_user_ids=[]
        )
    
    assigned_count = 0
    failed_count = 0
    failed_user_ids = []
    
    for user in target_users:
        if coupon.remained_stock <= 0:
            failed_count += 1
            failed_user_ids.append(user.id)
            continue
        
        existing_user_coupon = db.query(models.UserCoupon).filter(
            models.UserCoupon.user_id == user.id,
            models.UserCoupon.coupon_id == coupon.id,
            models.UserCoupon.is_used == False
        ).first()
        
        if existing_user_coupon:
            failed_count += 1
            failed_user_ids.append(user.id)
            continue
        
        try:
            user_coupon = models.UserCoupon(
                user_id=user.id,
                coupon_id=coupon.id,
                is_used=False,
                obtained_at=datetime.utcnow(),
                expires_at=coupon.valid_to
            )
            db.add(user_coupon)
            
            coupon.remained_stock -= 1
            
            assigned_count += 1
            
        except Exception as e:
            log_error(
                message=f"给用户 [{user.id}] 发放优惠券时发生错误: {str(e)}",
                action="ASSIGN_COUPON_ERROR",
                tourist_id=user.id
            )
            failed_count += 1
            failed_user_ids.append(user.id)
    
    db.commit()
    
    log_info(
        message=f"管理员 [{current_admin.id}] 执行智能发券: 优惠券 {coupon.name}, 成功发放 {assigned_count} 张, 失败 {failed_count} 张",
        action="COUPON_ASSIGNED",
        tourist_id=current_admin.id
    )
    
    audit_manager = security.get_audit_log_manager()
    audit_manager.log_action(
        user_id=current_admin.id,
        module=models.AuditLogModule.ORDER,
        action=models.AuditLogAction.CREATE,
        target_id=coupon.id,
        target_type="CouponAssignment",
        details=f"管理员 {current_admin.username} 执行智能发券: 优惠券ID={coupon.id}, 成功发放 {assigned_count} 张, 失败 {failed_count} 张",
        ip_address=request.client.host if request.client else None
    )
    
    return schemas.AssignCouponResponse(
        success=True,
        message=f"发券完成，成功发放 {assigned_count} 张，失败 {failed_count} 张",
        assigned_count=assigned_count,
        failed_count=failed_count,
        failed_user_ids=failed_user_ids
    )


@marketing_router.post("/time-limited-commissions", response_model=schemas.TimeLimitedCommission, status_code=status.HTTP_201_CREATED)
def create_time_limited_commission(
    request: Request,
    commission_data: schemas.TimeLimitedCommissionCreate,
    db: Session = Depends(get_db),
    current_admin: models.User = Depends(auth.require_role(models.UserRole.ADMIN, models.UserRole.STAFF))
):
    if commission_data.valid_to <= commission_data.valid_from:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="有效期结束时间必须晚于开始时间"
        )
    
    if commission_data.commission_rate < 0 or commission_data.commission_rate > 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="佣金比例必须在 0 到 1 之间"
        )
    
    if commission_data.distributor_id:
        distributor = db.query(models.Distributor).filter(
            models.Distributor.id == commission_data.distributor_id
        ).first()
        if distributor is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="指定的分销商不存在"
            )
    
    if commission_data.scenic_spot_id:
        scenic_spot = db.query(models.ScenicSpot).filter(
            models.ScenicSpot.id == commission_data.scenic_spot_id
        ).first()
        if scenic_spot is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="指定的景点不存在"
            )
    
    new_commission = models.TimeLimitedCommission(
        name=commission_data.name,
        distributor_id=commission_data.distributor_id,
        scenic_spot_id=commission_data.scenic_spot_id,
        commission_rate=commission_data.commission_rate,
        valid_from=commission_data.valid_from,
        valid_to=commission_data.valid_to,
        is_active=commission_data.is_active
    )
    
    db.add(new_commission)
    db.commit()
    db.refresh(new_commission)
    
    log_info(
        message=f"管理员 [{current_admin.id}] 创建了限时高佣活动: {new_commission.name}",
        action="TIME_LIMITED_COMMISSION_CREATED",
        tourist_id=current_admin.id
    )
    
    audit_manager = security.get_audit_log_manager()
    audit_manager.log_action(
        user_id=current_admin.id,
        module=models.AuditLogModule.DISTRIBUTION,
        action=models.AuditLogAction.CREATE,
        target_id=new_commission.id,
        target_type="TimeLimitedCommission",
        details=f"管理员 {current_admin.username} 创建限时高佣活动: {new_commission.name}, 佣金比例: {new_commission.commission_rate * 100}%",
        ip_address=request.client.host if request.client else None
    )
    
    return new_commission


@marketing_router.get("/time-limited-commissions", response_model=List[schemas.TimeLimitedCommission])
def list_time_limited_commissions(
    is_active: Optional[bool] = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_active_user)
):
    query = db.query(models.TimeLimitedCommission)
    
    if is_active is not None:
        query = query.filter(models.TimeLimitedCommission.is_active == is_active)
    
    commissions = query.order_by(
        models.TimeLimitedCommission.created_at.desc()
    ).offset(skip).limit(limit).all()
    
    return commissions


@marketing_router.get("/time-limited-commissions/{commission_id}", response_model=schemas.TimeLimitedCommission)
def get_time_limited_commission(
    commission_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_active_user)
):
    commission = db.query(models.TimeLimitedCommission).filter(
        models.TimeLimitedCommission.id == commission_id
    ).first()
    
    if commission is None:
        raise HTTPException(status_code=404, detail="限时高佣活动不存在")
    
    return commission


@marketing_router.put("/time-limited-commissions/{commission_id}", response_model=schemas.TimeLimitedCommission)
def update_time_limited_commission(
    commission_id: int,
    commission_data: schemas.TimeLimitedCommissionUpdate,
    db: Session = Depends(get_db),
    current_admin: models.User = Depends(auth.require_role(models.UserRole.ADMIN, models.UserRole.STAFF))
):
    commission = db.query(models.TimeLimitedCommission).filter(
        models.TimeLimitedCommission.id == commission_id
    ).first()
    
    if commission is None:
        raise HTTPException(status_code=404, detail="限时高佣活动不存在")
    
    update_data = commission_data.model_dump(exclude_unset=True)
    
    for key, value in update_data.items():
        setattr(commission, key, value)
    
    db.commit()
    db.refresh(commission)
    
    log_info(
        message=f"管理员 [{current_admin.id}] 更新了限时高佣活动: {commission.name}",
        action="TIME_LIMITED_COMMISSION_UPDATED",
        tourist_id=current_admin.id
    )
    
    return commission


@marketing_router.delete("/time-limited-commissions/{commission_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_time_limited_commission(
    commission_id: int,
    db: Session = Depends(get_db),
    current_admin: models.User = Depends(auth.require_role(models.UserRole.ADMIN, models.UserRole.STAFF))
):
    commission = db.query(models.TimeLimitedCommission).filter(
        models.TimeLimitedCommission.id == commission_id
    ).first()
    
    if commission is None:
        raise HTTPException(status_code=404, detail="限时高佣活动不存在")
    
    commission_name = commission.name
    db.delete(commission)
    db.commit()
    
    log_info(
        message=f"管理员 [{current_admin.id}] 删除了限时高佣活动: {commission_name}",
        action="TIME_LIMITED_COMMISSION_DELETED",
        tourist_id=current_admin.id
    )


@marketing_router.get("/dashboard/stats", response_model=dict)
def get_marketing_dashboard_stats(
    db: Session = Depends(get_db),
    current_admin: models.User = Depends(auth.get_current_active_user)
):
    from sqlalchemy import func, and_
    from datetime import datetime, date
    
    today_start = datetime.combine(date.today(), datetime.min.time())
    
    today_coupon_used_count = db.query(
        func.count(models.UserCoupon.id)
    ).filter(
        models.UserCoupon.is_used == True,
        models.UserCoupon.used_at >= today_start
    ).scalar() or 0
    
    today_coupon_orders = db.query(
        func.count(models.TicketOrder.id).label('order_count'),
        func.sum(models.TicketOrder.total_price).label('total_revenue')
    ).filter(
        models.TicketOrder.status == models.OrderStatus.PAID,
        models.TicketOrder.created_at >= today_start
    ).join(
        models.UserCoupon,
        models.UserCoupon.used_order_id == models.TicketOrder.id
    ).first()
    
    today_coupon_orders_count = today_coupon_orders.order_count or 0
    today_coupon_revenue = today_coupon_orders.total_revenue or 0.0
    
    active_coupons = db.query(
        func.count(models.Coupon.id)
    ).filter(
        models.Coupon.is_active == True,
        models.Coupon.valid_from <= datetime.utcnow(),
        models.Coupon.valid_to >= datetime.utcnow(),
        models.Coupon.remained_stock > 0
    ).scalar() or 0
    
    active_time_limited = db.query(
        func.count(models.TimeLimitedCommission.id)
    ).filter(
        models.TimeLimitedCommission.is_active == True,
        models.TimeLimitedCommission.valid_from <= datetime.utcnow(),
        models.TimeLimitedCommission.valid_to >= datetime.utcnow()
    ).scalar() or 0
    
    total_coupons_issued = db.query(
        func.count(models.UserCoupon.id)
    ).scalar() or 0
    
    total_coupons_used = db.query(
        func.count(models.UserCoupon.id)
    ).filter(
        models.UserCoupon.is_used == True
    ).scalar() or 0
    
    coupon_utilization_rate = 0.0
    if total_coupons_issued > 0:
        coupon_utilization_rate = round(total_coupons_used / total_coupons_issued * 100, 1)
    
    return {
        "today_coupon_used_count": today_coupon_used_count,
        "today_coupon_orders_count": today_coupon_orders_count,
        "today_coupon_revenue": today_coupon_revenue,
        "active_coupons": active_coupons,
        "active_time_limited": active_time_limited,
        "total_coupons_issued": total_coupons_issued,
        "total_coupons_used": total_coupons_used,
        "coupon_utilization_rate": coupon_utilization_rate
    }


app.include_router(marketing_router)


app.include_router(distributor_router)


attendance_router = APIRouter(prefix="/attendance", tags=["排班考勤管理"])


@attendance_router.get("/work-shifts", response_model=List[schemas.WorkShift])
def get_work_shifts(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_active_user)
):
    work_shifts = db.query(models.WorkShift).offset(skip).limit(limit).all()
    return work_shifts


@attendance_router.get("/work-shifts/{shift_id}", response_model=schemas.WorkShift)
def get_work_shift(
    shift_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_active_user)
):
    work_shift = db.query(models.WorkShift).filter(
        models.WorkShift.id == shift_id
    ).first()
    if work_shift is None:
        raise HTTPException(status_code=404, detail="班次不存在")
    return work_shift


@attendance_router.post("/work-shifts", response_model=schemas.WorkShift, status_code=status.HTTP_201_CREATED)
def create_work_shift(
    shift_data: schemas.WorkShiftCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.require_role(models.UserRole.ADMIN, models.UserRole.DEPT_ADMIN))
):
    existing = db.query(models.WorkShift).filter(
        models.WorkShift.name == shift_data.name
    ).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="班次名称已存在"
        )
    
    db_shift = models.WorkShift(
        name=shift_data.name,
        start_time=shift_data.start_time,
        end_time=shift_data.end_time,
        max_staff=shift_data.max_staff
    )
    db.add(db_shift)
    db.commit()
    db.refresh(db_shift)
    
    log_info(
        message=f"管理员 [{current_user.id}] 创建班次: {shift_data.name}",
        action="WORK_SHIFT_CREATED",
        tourist_id=current_user.id
    )
    
    return db_shift


@attendance_router.put("/work-shifts/{shift_id}", response_model=schemas.WorkShift)
def update_work_shift(
    shift_id: int,
    shift_data: schemas.WorkShiftUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.require_role(models.UserRole.ADMIN, models.UserRole.STAFF))
):
    db_shift = db.query(models.WorkShift).filter(
        models.WorkShift.id == shift_id
    ).first()
    if db_shift is None:
        raise HTTPException(status_code=404, detail="班次不存在")
    
    update_dict = shift_data.model_dump(exclude_unset=True)
    
    if "name" in update_dict:
        existing = db.query(models.WorkShift).filter(
            models.WorkShift.name == update_dict["name"],
            models.WorkShift.id != shift_id
        ).first()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="班次名称已存在"
            )
    
    for key, value in update_dict.items():
        setattr(db_shift, key, value)
    
    db.commit()
    db.refresh(db_shift)
    
    log_info(
        message=f"管理员 [{current_user.id}] 更新班次: ID={shift_id}",
        action="WORK_SHIFT_UPDATED",
        tourist_id=current_user.id
    )
    
    return db_shift


@attendance_router.delete("/work-shifts/{shift_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_work_shift(
    shift_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.require_role(models.UserRole.ADMIN))
):
    db_shift = db.query(models.WorkShift).filter(
        models.WorkShift.id == shift_id
    ).first()
    if db_shift is None:
        raise HTTPException(status_code=404, detail="班次不存在")
    
    existing_schedules = db.query(models.Schedule).filter(
        models.Schedule.work_shift_id == shift_id
    ).first()
    if existing_schedules:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="该班次已有排班记录，无法删除"
        )
    
    db.delete(db_shift)
    db.commit()
    
    log_info(
        message=f"管理员 [{current_user.id}] 删除班次: ID={shift_id}",
        action="WORK_SHIFT_DELETED",
        tourist_id=current_user.id
    )
    
    return None


def is_shift_over_day(start_time: str, end_time: str) -> bool:
    start_hour = int(start_time.split(':')[0])
    end_hour = int(end_time.split(':')[0])
    return end_hour < start_hour


def get_shift_time_range(schedule_date: str, start_time: str, end_time: str) -> tuple:
    from datetime import datetime, timedelta
    
    date_dt = datetime.strptime(schedule_date, "%Y-%m-%d")
    start_dt = datetime.combine(date_dt.date(), datetime.strptime(start_time, "%H:%M").time())
    end_dt = datetime.combine(date_dt.date(), datetime.strptime(end_time, "%H:%M").time())
    
    if end_dt <= start_dt:
        end_dt += timedelta(days=1)
    
    return (start_dt, end_dt)


def check_schedule_conflict(db: Session, user_id: int, schedule_date: str, work_shift_id: int) -> Optional[models.Schedule]:
    from datetime import datetime, timedelta
    
    new_shift = db.query(models.WorkShift).filter(
        models.WorkShift.id == work_shift_id
    ).first()
    if new_shift is None:
        return None
    
    new_start, new_end = get_shift_time_range(
        schedule_date, new_shift.start_time, new_shift.end_time
    )
    
    try:
        current_dt = datetime.strptime(schedule_date, "%Y-%m-%d")
        dates_to_check = [
            (current_dt - timedelta(days=1)).strftime("%Y-%m-%d"),
            schedule_date,
            (current_dt + timedelta(days=1)).strftime("%Y-%m-%d")
        ]
    except ValueError:
        return None
    
    existing_schedules = db.query(models.Schedule).filter(
        models.Schedule.user_id == user_id,
        models.Schedule.schedule_date.in_(dates_to_check)
    ).all()
    
    for existing in existing_schedules:
        existing_shift = existing.work_shift
        if existing_shift is None:
            continue
        
        existing_start, existing_end = get_shift_time_range(
            existing.schedule_date, existing_shift.start_time, existing_shift.end_time
        )
        
        if (new_start < existing_end and new_end > existing_start):
            return existing
    
    return None


def check_shift_capacity(db: Session, work_shift_id: int, schedule_date: str, current_count: int = 0) -> tuple:
    work_shift = db.query(models.WorkShift).filter(
        models.WorkShift.id == work_shift_id
    ).first()
    
    if work_shift is None or work_shift.max_staff is None:
        return (True, 0, None)
    
    existing_count = db.query(models.Schedule).filter(
        models.Schedule.work_shift_id == work_shift_id,
        models.Schedule.schedule_date == schedule_date
    ).count()
    
    total_count = existing_count + current_count
    
    if total_count >= work_shift.max_staff:
        return (False, total_count, work_shift.max_staff)
    
    return (True, total_count, work_shift.max_staff)


def can_manage_user(current_user: models.User, target_user_id: int, db: Session) -> bool:
    if current_user.role == models.UserRole.ADMIN:
        return True
    
    if current_user.role == models.UserRole.DEPT_ADMIN:
        target_user = db.query(models.User).filter(
            models.User.id == target_user_id
        ).first()
        if target_user is None:
            return False
        if current_user.department_id is None:
            return False
        return target_user.department_id == current_user.department_id
    
    return False


def get_managed_user_ids(current_user: models.User, db: Session) -> List[int]:
    if current_user.role == models.UserRole.ADMIN:
        users = db.query(models.User).all()
        return [u.id for u in users]
    
    if current_user.role == models.UserRole.DEPT_ADMIN:
        if current_user.department_id is None:
            return []
        users = db.query(models.User).filter(
            models.User.department_id == current_user.department_id
        ).all()
        return [u.id for u in users]
    
    return [current_user.id]


@attendance_router.get("/schedules", response_model=List[schemas.ScheduleWithDetails])
def get_schedules(
    user_id: Optional[int] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_active_user)
):
    query = db.query(models.Schedule)
    
    managed_user_ids = get_managed_user_ids(current_user, db)
    
    if current_user.role == models.UserRole.STAFF:
        query = query.filter(models.Schedule.user_id == current_user.id)
    else:
        query = query.filter(models.Schedule.user_id.in_(managed_user_ids))
    
    if user_id is not None:
        if current_user.role != models.UserRole.ADMIN and user_id not in managed_user_ids:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="无权查看该员工的排班"
            )
        query = query.filter(models.Schedule.user_id == user_id)
    if start_date is not None:
        query = query.filter(models.Schedule.schedule_date >= start_date)
    if end_date is not None:
        query = query.filter(models.Schedule.schedule_date <= end_date)
    
    schedules = query.order_by(
        models.Schedule.schedule_date.desc()
    ).offset(skip).limit(limit).all()
    
    return schedules


@attendance_router.get("/schedules/calendar", response_model=List[schemas.ScheduleWithDetails])
def get_schedules_calendar(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_active_user)
):
    from datetime import datetime, timedelta
    
    if start_date is None:
        today = datetime.now()
        start_date = (today - timedelta(days=today.weekday())).strftime("%Y-%m-%d")
    if end_date is None:
        start_dt = datetime.strptime(start_date, "%Y-%m-%d")
        end_date = (start_dt + timedelta(days=30)).strftime("%Y-%m-%d")
    
    query = db.query(models.Schedule).filter(
        models.Schedule.schedule_date >= start_date,
        models.Schedule.schedule_date <= end_date
    )
    
    managed_user_ids = get_managed_user_ids(current_user, db)
    
    if current_user.role == models.UserRole.STAFF:
        query = query.filter(models.Schedule.user_id == current_user.id)
    else:
        query = query.filter(models.Schedule.user_id.in_(managed_user_ids))
    
    query = query.order_by(
        models.Schedule.schedule_date,
        models.Schedule.id
    ).all()
    
    return query


@attendance_router.post("/schedules", response_model=schemas.ScheduleWithDetails, status_code=status.HTTP_201_CREATED)
def create_schedule(
    schedule_data: schemas.ScheduleCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.require_role(models.UserRole.ADMIN, models.UserRole.DEPT_ADMIN))
):
    if not can_manage_user(current_user, schedule_data.user_id, db):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权管理该员工的排班"
        )
    
    user = db.query(models.User).filter(
        models.User.id == schedule_data.user_id
    ).first()
    if user is None:
        raise HTTPException(status_code=404, detail="员工不存在")
    
    work_shift = db.query(models.WorkShift).filter(
        models.WorkShift.id == schedule_data.work_shift_id
    ).first()
    if work_shift is None:
        raise HTTPException(status_code=404, detail="班次不存在")
    
    existing = check_schedule_conflict(db, schedule_data.user_id, schedule_data.schedule_date, schedule_data.work_shift_id)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"该员工在 {schedule_data.schedule_date} 已有排班或时间重叠"
        )
    
    has_capacity, current_count, max_staff = check_shift_capacity(db, schedule_data.work_shift_id, schedule_data.schedule_date)
    if not has_capacity:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"班次 '{work_shift.name}' 在 {schedule_data.schedule_date} 已满（当前: {current_count}, 最大: {max_staff}）"
        )
    
    db_schedule = models.Schedule(
        user_id=schedule_data.user_id,
        work_shift_id=schedule_data.work_shift_id,
        schedule_date=schedule_data.schedule_date
    )
    db.add(db_schedule)
    db.commit()
    db.refresh(db_schedule)
    
    log_info(
        message=f"管理员 [{current_user.id}] 为员工 [{schedule_data.user_id}] 创建排班: {schedule_data.schedule_date}",
        action="SCHEDULE_CREATED",
        tourist_id=current_user.id
    )
    
    return db_schedule


@attendance_router.post("/schedules/batch", response_model=schemas.BatchScheduleResponse)
def create_batch_schedules(
    batch_data: schemas.BatchScheduleCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.require_role(models.UserRole.ADMIN, models.UserRole.DEPT_ADMIN))
):
    from datetime import datetime, timedelta
    
    work_shift = db.query(models.WorkShift).filter(
        models.WorkShift.id == batch_data.work_shift_id
    ).first()
    if work_shift is None:
        raise HTTPException(status_code=404, detail="班次不存在")
    
    if not batch_data.user_ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="员工ID列表不能为空"
        )
    
    for user_id in batch_data.user_ids:
        if not can_manage_user(current_user, user_id, db):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"无权管理员工 {user_id} 的排班"
            )
    
    invalid_users = []
    for user_id in batch_data.user_ids:
        user = db.query(models.User).filter(models.User.id == user_id).first()
        if user is None:
            invalid_users.append(user_id)
    
    if invalid_users:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"以下员工ID不存在: {invalid_users}"
        )
    
    try:
        start_dt = datetime.strptime(batch_data.start_date, "%Y-%m-%d")
        end_dt = datetime.strptime(batch_data.end_date, "%Y-%m-%d")
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="日期格式错误，请使用 YYYY-MM-DD 格式"
        )
    
    if start_dt > end_dt:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="开始日期不能晚于结束日期"
        )
    
    dates_to_schedule = []
    current_dt = start_dt
    while current_dt <= end_dt:
        if batch_data.exclude_weekends:
            if current_dt.weekday() < 5:
                dates_to_schedule.append(current_dt.strftime("%Y-%m-%d"))
        else:
            dates_to_schedule.append(current_dt.strftime("%Y-%m-%d"))
        current_dt += timedelta(days=1)
    
    created_count = 0
    conflict_dates = []
    conflicts = []
    capacity_issues = []
    
    for schedule_date in dates_to_schedule:
        date_scheduled_count = 0
        
        for user_id in batch_data.user_ids:
            existing = check_schedule_conflict(db, user_id, schedule_date, batch_data.work_shift_id)
            if existing:
                conflict_info = f"员工 {user_id} 在 {schedule_date} 已有排班或时间重叠"
                if conflict_info not in conflicts:
                    conflicts.append(conflict_info)
                    if schedule_date not in conflict_dates:
                        conflict_dates.append(schedule_date)
                continue
            
            has_capacity, current_count, max_staff = check_shift_capacity(
                db, batch_data.work_shift_id, schedule_date, date_scheduled_count
            )
            if not has_capacity:
                capacity_info = f"班次 '{work_shift.name}' 在 {schedule_date} 已满（当前: {current_count}, 最大: {max_staff}）"
                if capacity_info not in capacity_issues:
                    capacity_issues.append(capacity_info)
                continue
            
            db_schedule = models.Schedule(
                user_id=user_id,
                work_shift_id=batch_data.work_shift_id,
                schedule_date=schedule_date
            )
            db.add(db_schedule)
            created_count += 1
            date_scheduled_count += 1
    
    db.commit()
    
    log_info(
        message=f"管理员 [{current_user.id}] 批量排班: 创建 {created_count} 条, 冲突 {len(conflicts)} 条, 容量问题 {len(capacity_issues)} 条",
        action="BATCH_SCHEDULE_CREATED",
        tourist_id=current_user.id
    )
    
    if conflicts or capacity_issues:
        all_issues = conflicts + capacity_issues
        return schemas.BatchScheduleResponse(
            success=False,
            message=f"批量排班完成，部分日期存在问题。已创建 {created_count} 条排班，{len(conflicts)} 个冲突，{len(capacity_issues)} 个容量问题",
            created_count=created_count,
            conflict_dates=list(set(conflict_dates))
        )
    
    return schemas.BatchScheduleResponse(
        success=True,
        message=f"批量排班成功，共创建 {created_count} 条排班记录",
        created_count=created_count,
        conflict_dates=[]
    )


@attendance_router.get("/schedules/check-conflict", response_model=schemas.ScheduleConflictCheck)
def check_conflict(
    user_id: int,
    schedule_date: str,
    work_shift_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_active_user)
):
    existing = check_schedule_conflict(db, user_id, schedule_date, work_shift_id)
    
    return schemas.ScheduleConflictCheck(
        user_id=user_id,
        schedule_date=schedule_date,
        has_conflict=existing is not None,
        existing_schedule=existing
    )


@attendance_router.delete("/schedules/{schedule_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_schedule(
    schedule_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.require_role(models.UserRole.ADMIN, models.UserRole.DEPT_ADMIN))
):
    db_schedule = db.query(models.Schedule).filter(
        models.Schedule.id == schedule_id
    ).first()
    if db_schedule is None:
        raise HTTPException(status_code=404, detail="排班记录不存在")
    
    if not can_manage_user(current_user, db_schedule.user_id, db):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权删除该排班"
        )
    
    db.delete(db_schedule)
    db.commit()
    
    log_info(
        message=f"管理员 [{current_user.id}] 删除排班: ID={schedule_id}",
        action="SCHEDULE_DELETED",
        tourist_id=current_user.id
    )
    
    return None


def calculate_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    import math
    
    R = 6371000.0
    
    lat1_rad = math.radians(lat1)
    lon1_rad = math.radians(lon1)
    lat2_rad = math.radians(lat2)
    lon2_rad = math.radians(lon2)
    
    dlat = lat2_rad - lat1_rad
    dlon = lon2_rad - lon1_rad
    
    a = math.sin(dlat / 2) ** 2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    
    return R * c


def is_within_geofence(
    check_lat: float,
    check_lon: float,
    spot_lat: Optional[float],
    spot_lon: Optional[float],
    spot_radius: Optional[float]
) -> tuple:
    if spot_lat is None or spot_lon is None or spot_radius is None:
        return (True, 0.0)
    
    distance = calculate_distance(check_lat, check_lon, spot_lat, spot_lon)
    is_within = distance <= spot_radius
    return (is_within, distance)


def get_or_create_attendance_record(
    db: Session,
    user_id: int,
    attendance_date: str,
    schedule: Optional[models.Schedule] = None
) -> models.AttendanceRecord:
    record = db.query(models.AttendanceRecord).filter(
        models.AttendanceRecord.user_id == user_id,
        models.AttendanceRecord.attendance_date == attendance_date
    ).first()
    
    if record is None:
        record = models.AttendanceRecord(
            user_id=user_id,
            attendance_date=attendance_date,
            schedule_id=schedule.id if schedule else None,
            attendance_status=models.AttendanceStatus.ABSENT
        )
        db.add(record)
        db.commit()
        db.refresh(record)
    
    return record


def calculate_attendance_status(
    check_in_time: Optional[datetime],
    check_out_time: Optional[datetime],
    shift_start_time: Optional[str],
    shift_end_time: Optional[str],
    attendance_date: str
) -> models.AttendanceStatus:
    from datetime import datetime, timedelta
    
    if check_in_time is None:
        return models.AttendanceStatus.ABSENT
    
    if shift_start_time is None or shift_end_time is None:
        return models.AttendanceStatus.NORMAL
    
    try:
        date_dt = datetime.strptime(attendance_date, "%Y-%m-%d")
        shift_start_dt = datetime.combine(date_dt.date(), datetime.strptime(shift_start_time, "%H:%M").time())
        shift_end_dt = datetime.combine(date_dt.date(), datetime.strptime(shift_end_time, "%H:%M").time())
        
        if shift_end_dt <= shift_start_dt:
            shift_end_dt += timedelta(days=1)
        
        late_threshold = shift_start_dt + timedelta(minutes=15)
        
        is_late = check_in_time > late_threshold
        
        if check_out_time is not None:
            early_leave_threshold = shift_end_dt - timedelta(minutes=15)
            is_early_leave = check_out_time < early_leave_threshold
        else:
            is_early_leave = False
        
        if is_late and is_early_leave:
            return models.AttendanceStatus.LATE
        elif is_late:
            return models.AttendanceStatus.LATE
        elif is_early_leave:
            return models.AttendanceStatus.EARLY_LEAVE
        else:
            return models.AttendanceStatus.NORMAL
            
    except Exception as e:
        return models.AttendanceStatus.NORMAL


def update_attendance_record_status(
    db: Session,
    record: models.AttendanceRecord,
    schedule: Optional[models.Schedule] = None
) -> models.AttendanceRecord:
    if schedule is None and record.schedule_id:
        schedule = db.query(models.Schedule).filter(
            models.Schedule.id == record.schedule_id
        ).first()
    
    if schedule is None:
        if record.check_in_time is not None:
            record.attendance_status = models.AttendanceStatus.NORMAL
        db.commit()
        db.refresh(record)
        return record
    
    work_shift = schedule.work_shift
    if work_shift is None:
        if record.check_in_time is not None:
            record.attendance_status = models.AttendanceStatus.NORMAL
        db.commit()
        db.refresh(record)
        return record
    
    new_status = calculate_attendance_status(
        check_in_time=record.check_in_time,
        check_out_time=record.check_out_time,
        shift_start_time=work_shift.start_time,
        shift_end_time=work_shift.end_time,
        attendance_date=record.attendance_date
    )
    
    if not record.is_approved:
        record.attendance_status = new_status
    
    db.commit()
    db.refresh(record)
    return record


@attendance_router.post("/check-in", response_model=schemas.AttendanceRecordWithDetails)
def check_in(
    check_in_data: schemas.CheckInCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_active_user)
):
    from datetime import datetime
    
    today = datetime.now().strftime("%Y-%m-%d")
    now = datetime.now()
    
    schedule = db.query(models.Schedule).filter(
        models.Schedule.user_id == current_user.id,
        models.Schedule.schedule_date == today
    ).first()
    
    scenic_spot = None
    if check_in_data.scenic_spot_id is not None:
        scenic_spot = db.query(models.ScenicSpot).filter(
            models.ScenicSpot.id == check_in_data.scenic_spot_id
        ).first()
    
    location_status = models.AttendanceLocationStatus.NORMAL
    distance = 0.0
    
    if scenic_spot and scenic_spot.latitude is not None and scenic_spot.longitude is not None:
        is_within, distance = is_within_geofence(
            check_lat=check_in_data.latitude,
            check_lon=check_in_data.longitude,
            spot_lat=scenic_spot.latitude,
            spot_lon=scenic_spot.longitude,
            spot_radius=scenic_spot.geofence_radius
        )
        if not is_within:
            location_status = models.AttendanceLocationStatus.OUT_OF_RANGE
    
    record = get_or_create_attendance_record(db, current_user.id, today, schedule)
    
    if record.check_in_time is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="今日已打卡上班"
        )
    
    record.check_in_time = now
    record.check_in_latitude = check_in_data.latitude
    record.check_in_longitude = check_in_data.longitude
    record.check_in_location_status = location_status
    record.scenic_spot_id = check_in_data.scenic_spot_id
    
    if schedule:
        record.schedule_id = schedule.id
    
    record = update_attendance_record_status(db, record, schedule)
    
    log_info(
        message=f"员工 [{current_user.id}] 上班打卡: 时间={now}, 位置状态={location_status}, 距离={distance:.2f}米",
        action="CHECK_IN",
        tourist_id=current_user.id
    )
    
    return record


@attendance_router.post("/check-out", response_model=schemas.AttendanceRecordWithDetails)
def check_out(
    check_out_data: schemas.CheckOutCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_active_user)
):
    from datetime import datetime
    
    today = datetime.now().strftime("%Y-%m-%d")
    now = datetime.now()
    
    record = db.query(models.AttendanceRecord).filter(
        models.AttendanceRecord.user_id == current_user.id,
        models.AttendanceRecord.attendance_date == today
    ).first()
    
    if record is None or record.check_in_time is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="今日未打卡上班，无法打卡下班"
        )
    
    if record.check_out_time is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="今日已打卡下班"
        )
    
    scenic_spot = None
    if check_out_data.scenic_spot_id is not None:
        scenic_spot = db.query(models.ScenicSpot).filter(
            models.ScenicSpot.id == check_out_data.scenic_spot_id
        ).first()
    
    location_status = models.AttendanceLocationStatus.NORMAL
    distance = 0.0
    
    if scenic_spot and scenic_spot.latitude is not None and scenic_spot.longitude is not None:
        is_within, distance = is_within_geofence(
            check_lat=check_out_data.latitude,
            check_lon=check_out_data.longitude,
            spot_lat=scenic_spot.latitude,
            spot_lon=scenic_spot.longitude,
            spot_radius=scenic_spot.geofence_radius
        )
        if not is_within:
            location_status = models.AttendanceLocationStatus.OUT_OF_RANGE
    
    record.check_out_time = now
    record.check_out_latitude = check_out_data.latitude
    record.check_out_longitude = check_out_data.longitude
    record.check_out_location_status = location_status
    
    schedule = None
    if record.schedule_id:
        schedule = db.query(models.Schedule).filter(
            models.Schedule.id == record.schedule_id
        ).first()
    
    record = update_attendance_record_status(db, record, schedule)
    
    log_info(
        message=f"员工 [{current_user.id}] 下班打卡: 时间={now}, 位置状态={location_status}, 距离={distance:.2f}米",
        action="CHECK_OUT",
        tourist_id=current_user.id
    )
    
    return record


@attendance_router.get("/attendance-records", response_model=List[schemas.AttendanceRecordWithDetails])
def get_attendance_records(
    user_id: Optional[int] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    attendance_status: Optional[schemas.AttendanceStatus] = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_active_user)
):
    query = db.query(models.AttendanceRecord)
    
    managed_user_ids = get_managed_user_ids(current_user, db)
    
    if current_user.role == models.UserRole.STAFF:
        query = query.filter(models.AttendanceRecord.user_id == current_user.id)
    else:
        query = query.filter(models.AttendanceRecord.user_id.in_(managed_user_ids))
    
    if user_id is not None:
        if current_user.role != models.UserRole.ADMIN and user_id not in managed_user_ids:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="无权查看该员工的考勤记录"
            )
        query = query.filter(models.AttendanceRecord.user_id == user_id)
    
    if start_date is not None:
        query = query.filter(models.AttendanceRecord.attendance_date >= start_date)
    if end_date is not None:
        query = query.filter(models.AttendanceRecord.attendance_date <= end_date)
    
    if attendance_status is not None:
        query = query.filter(models.AttendanceRecord.attendance_status == attendance_status)
    
    records = query.order_by(
        models.AttendanceRecord.attendance_date.desc(),
        models.AttendanceRecord.check_in_time.desc()
    ).offset(skip).limit(limit).all()
    
    return records


@attendance_router.get("/attendance-alerts", response_model=List[schemas.AttendanceAlertResponse])
def get_attendance_alerts(
    date: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.require_role(models.UserRole.ADMIN, models.UserRole.DEPT_ADMIN))
):
    from datetime import datetime
    
    if date is None:
        date = datetime.now().strftime("%Y-%m-%d")
    
    query = db.query(models.AttendanceRecord).filter(
        models.AttendanceRecord.attendance_date == date
    )
    
    managed_user_ids = get_managed_user_ids(current_user, db)
    query = query.filter(models.AttendanceRecord.user_id.in_(managed_user_ids))
    
    abnormal_records = query.filter(
        models.AttendanceRecord.attendance_status != models.AttendanceStatus.NORMAL
    ).all()
    
    result = []
    for record in abnormal_records:
        username = record.user.username if record.user else "Unknown"
        result.append(schemas.AttendanceAlertResponse(
            record_id=record.id,
            user_id=record.user_id,
            username=username,
            attendance_date=record.attendance_date,
            attendance_status=record.attendance_status,
            check_in_location_status=record.check_in_location_status,
            check_out_location_status=record.check_out_location_status,
            check_in_time=record.check_in_time,
            check_out_time=record.check_out_time,
            is_approved=record.is_approved,
            remark=record.remark
        ))
    
    return result


@attendance_router.post("/attendance-approve", response_model=schemas.AttendanceRecordWithDetails)
def approve_attendance(
    approve_data: schemas.AttendanceManualApprove,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.require_role(models.UserRole.ADMIN, models.UserRole.DEPT_ADMIN))
):
    from datetime import datetime
    
    record = db.query(models.AttendanceRecord).filter(
        models.AttendanceRecord.id == approve_data.record_id
    ).first()
    
    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="考勤记录不存在"
        )
    
    if not can_manage_user(current_user, record.user_id, db):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权审批该员工的考勤"
        )
    
    record.attendance_status = approve_data.new_status
    record.is_approved = True
    record.approved_by = current_user.id
    record.approved_at = datetime.now()
    record.remark = approve_data.remark
    
    db.commit()
    db.refresh(record)
    
    log_info(
        message=f"管理员 [{current_user.id}] 审批考勤记录: 记录ID={record.id}, 新状态={approve_data.new_status}",
        action="ATTENDANCE_APPROVED",
        tourist_id=current_user.id
    )
    
    return record


@attendance_router.get("/attendance-records/{record_id}", response_model=schemas.AttendanceRecordWithDetails)
def get_attendance_record(
    record_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_active_user)
):
    record = db.query(models.AttendanceRecord).filter(
        models.AttendanceRecord.id == record_id
    ).first()
    
    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="考勤记录不存在"
        )
    
    if current_user.role == models.UserRole.STAFF:
        if record.user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="无权查看该考勤记录"
            )
    else:
        if not can_manage_user(current_user, record.user_id, db):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="无权查看该考勤记录"
            )
    
    return record


finance_router = APIRouter(prefix="/finance", tags=["财务核算与对账中心"])


@finance_router.get("/statistics", response_model=schemas.FinanceStatistics)
def get_finance_statistics(
    start_date: Optional[str] = Query(None, description="开始日期，格式: YYYY-MM-DD"),
    end_date: Optional[str] = Query(None, description="结束日期，格式: YYYY-MM-DD"),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.require_role(models.UserRole.ADMIN, models.UserRole.STAFF))
):
    from sqlalchemy import func
    from datetime import datetime
    
    query = db.query(models.FinancialLog)
    
    if start_date:
        try:
            start_dt = datetime.strptime(start_date, "%Y-%m-%d")
            start_dt = start_dt.replace(hour=0, minute=0, second=0)
            query = query.filter(models.FinancialLog.transaction_time >= start_dt)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="开始日期格式错误，请使用 YYYY-MM-DD 格式"
            )
    
    if end_date:
        try:
            end_dt = datetime.strptime(end_date, "%Y-%m-%d")
            end_dt = end_dt.replace(hour=23, minute=59, second=59)
            query = query.filter(models.FinancialLog.transaction_time <= end_dt)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="结束日期格式错误，请使用 YYYY-MM-DD 格式"
            )
    
    total_income = query.filter(
        models.FinancialLog.transaction_type == models.TransactionType.INCOME
    ).with_entities(func.sum(models.FinancialLog.amount)).scalar() or 0.0
    
    total_distribution_expense = query.filter(
        models.FinancialLog.transaction_type == models.TransactionType.DISTRIBUTION_EXPENSE
    ).with_entities(func.sum(models.FinancialLog.amount)).scalar() or 0.0
    
    total_refund = query.filter(
        models.FinancialLog.transaction_type == models.TransactionType.REFUND
    ).with_entities(func.sum(models.FinancialLog.amount)).scalar() or 0.0
    
    total_transactions = query.count()
    
    net_profit = total_income - total_distribution_expense - total_refund
    
    log_info(
        message=f"财务统计查询: 总收入={total_income}, 总分销支出={total_distribution_expense}, 净利润={net_profit}",
        action="FINANCE_STATISTICS_QUERIED",
        tourist_id=current_user.id
    )
    
    return schemas.FinanceStatistics(
        total_income=round(total_income, 2),
        total_distribution_expense=round(total_distribution_expense, 2),
        total_refund=round(total_refund, 2),
        net_profit=round(net_profit, 2),
        total_transactions=total_transactions
    )


@finance_router.get("/logs", response_model=schemas.FinanceListResponse)
def get_financial_logs(
    start_date: Optional[str] = Query(None, description="开始日期，格式: YYYY-MM-DD"),
    end_date: Optional[str] = Query(None, description="结束日期，格式: YYYY-MM-DD"),
    transaction_type: Optional[schemas.TransactionType] = Query(None, description="交易类型筛选"),
    skip: int = Query(0, ge=0, description="跳过数量"),
    limit: int = Query(100, ge=1, le=1000, description="返回数量限制"),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.require_role(models.UserRole.ADMIN, models.UserRole.STAFF))
):
    from sqlalchemy import func
    from datetime import datetime
    
    query = db.query(models.FinancialLog)
    
    if start_date:
        try:
            start_dt = datetime.strptime(start_date, "%Y-%m-%d")
            start_dt = start_dt.replace(hour=0, minute=0, second=0)
            query = query.filter(models.FinancialLog.transaction_time >= start_dt)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="开始日期格式错误，请使用 YYYY-MM-DD 格式"
            )
    
    if end_date:
        try:
            end_dt = datetime.strptime(end_date, "%Y-%m-%d")
            end_dt = end_dt.replace(hour=23, minute=59, second=59)
            query = query.filter(models.FinancialLog.transaction_time <= end_dt)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="结束日期格式错误，请使用 YYYY-MM-DD 格式"
            )
    
    if transaction_type:
        query = query.filter(models.FinancialLog.transaction_type == transaction_type)
    
    total = query.count()
    
    logs = query.order_by(
        models.FinancialLog.transaction_time.desc(),
        models.FinancialLog.id.desc()
    ).offset(skip).limit(limit).all()
    
    stats_query = db.query(models.FinancialLog)
    
    if start_date:
        start_dt = datetime.strptime(start_date, "%Y-%m-%d")
        start_dt = start_dt.replace(hour=0, minute=0, second=0)
        stats_query = stats_query.filter(models.FinancialLog.transaction_time >= start_dt)
    
    if end_date:
        end_dt = datetime.strptime(end_date, "%Y-%m-%d")
        end_dt = end_dt.replace(hour=23, minute=59, second=59)
        stats_query = stats_query.filter(models.FinancialLog.transaction_time <= end_dt)
    
    total_income = stats_query.filter(
        models.FinancialLog.transaction_type == models.TransactionType.INCOME
    ).with_entities(func.sum(models.FinancialLog.amount)).scalar() or 0.0
    
    total_distribution_expense = stats_query.filter(
        models.FinancialLog.transaction_type == models.TransactionType.DISTRIBUTION_EXPENSE
    ).with_entities(func.sum(models.FinancialLog.amount)).scalar() or 0.0
    
    total_refund = stats_query.filter(
        models.FinancialLog.transaction_type == models.TransactionType.REFUND
    ).with_entities(func.sum(models.FinancialLog.amount)).scalar() or 0.0
    
    net_profit = total_income - total_distribution_expense - total_refund
    
    log_info(
        message=f"财务流水查询: 共 {total} 条记录, 跳过 {skip}, 限制 {limit}",
        action="FINANCE_LOGS_QUERIED",
        tourist_id=current_user.id
    )
    
    return schemas.FinanceListResponse(
        total=total,
        items=logs,
        statistics=schemas.FinanceStatistics(
            total_income=round(total_income, 2),
            total_distribution_expense=round(total_distribution_expense, 2),
            total_refund=round(total_refund, 2),
            net_profit=round(net_profit, 2),
            total_transactions=total
        )
    )


@finance_router.get("/logs/{log_id}", response_model=schemas.FinancialLogWithDetails)
def get_financial_log(
    log_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.require_role(models.UserRole.ADMIN, models.UserRole.STAFF))
):
    log = db.query(models.FinancialLog).filter(
        models.FinancialLog.id == log_id
    ).first()
    
    if log is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="财务流水记录不存在"
        )
    
    return log


@finance_router.post("/reconciliation", response_model=schemas.ReconciliationResult, tags=["财务核算与对账中心"])
def check_reconciliation(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.require_role(models.UserRole.ADMIN, models.UserRole.STAFF))
):
    from sqlalchemy import func
    
    paid_orders_total = db.query(func.sum(models.TicketOrder.total_price)).filter(
        models.TicketOrder.status == models.OrderStatus.PAID
    ).scalar() or 0.0
    
    refunded_orders = db.query(func.sum(models.TicketOrder.total_price)).filter(
        models.TicketOrder.status == models.OrderStatus.REFUNDED
    ).scalar() or 0.0
    
    order_total_income = paid_orders_total
    order_total_refund = refunded_orders
    
    financial_income = db.query(func.sum(models.FinancialLog.amount)).filter(
        models.FinancialLog.transaction_type == models.TransactionType.INCOME
    ).scalar() or 0.0
    
    financial_refund = db.query(func.sum(models.FinancialLog.amount)).filter(
        models.FinancialLog.transaction_type == models.TransactionType.REFUND
    ).scalar() or 0.0
    
    expected_income = order_total_income - order_total_refund
    actual_income = financial_income - financial_refund
    
    difference = round(abs(expected_income - actual_income), 2)
    is_balanced = difference < 0.01
    
    log_info(
        message=f"对账检查: 订单收入={order_total_income}, 订单退款={order_total_refund}, 财务收入={financial_income}, 财务退款={financial_refund}, 差额={difference}, 平衡={is_balanced}",
        action="FINANCE_RECONCILIATION_CHECKED",
        tourist_id=current_user.id
    )
    
    return schemas.ReconciliationResult(
        is_balanced=is_balanced,
        order_total_income=round(order_total_income, 2),
        financial_log_income=round(financial_income, 2),
        order_total_refund=round(order_total_refund, 2),
        financial_log_refund=round(financial_refund, 2),
        difference=difference,
        message="账目平衡" if is_balanced else f"账目不平衡，差额: {difference} 元",
        details={
            "paid_orders_count": db.query(models.TicketOrder).filter(
                models.TicketOrder.status == models.OrderStatus.PAID
            ).count(),
            "refunded_orders_count": db.query(models.TicketOrder).filter(
                models.TicketOrder.status == models.OrderStatus.REFUNDED
            ).count(),
            "financial_logs_count": db.query(models.FinancialLog).count(),
            "expected_net_income": round(expected_income, 2),
            "actual_net_income": round(actual_income, 2)
        }
    )


@finance_router.get("/export/csv", tags=["财务核算与对账中心"])
def export_financial_logs_csv(
    start_date: Optional[str] = Query(None, description="开始日期，格式: YYYY-MM-DD"),
    end_date: Optional[str] = Query(None, description="结束日期，格式: YYYY-MM-DD"),
    transaction_type: Optional[schemas.TransactionType] = Query(None, description="交易类型筛选"),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.require_role(models.UserRole.ADMIN, models.UserRole.STAFF))
):
    from datetime import datetime
    from fastapi.responses import StreamingResponse
    import io
    
    query = db.query(models.FinancialLog).options(
        joinedload(models.FinancialLog.distributor)
    )
    
    if start_date:
        try:
            start_dt = datetime.strptime(start_date, "%Y-%m-%d")
            start_dt = start_dt.replace(hour=0, minute=0, second=0)
            query = query.filter(models.FinancialLog.transaction_time >= start_dt)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="开始日期格式错误，请使用 YYYY-MM-DD 格式"
            )
    
    if end_date:
        try:
            end_dt = datetime.strptime(end_date, "%Y-%m-%d")
            end_dt = end_dt.replace(hour=23, minute=59, second=59)
            query = query.filter(models.FinancialLog.transaction_time <= end_dt)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="结束日期格式错误，请使用 YYYY-MM-DD 格式"
            )
    
    if transaction_type:
        query = query.filter(models.FinancialLog.transaction_type == transaction_type)
    
    logs = query.order_by(
        models.FinancialLog.transaction_time.desc(),
        models.FinancialLog.id.desc()
    ).all()
    
    output = io.StringIO()
    
    headers = ["流水ID", "交易时间", "交易类型", "订单号", "金额", "交易摘要", "关联分销商ID", "分销商姓名"]
    output.write(",".join(headers) + "\n")
    
    for log in logs:
        row = [
            str(log.id),
            log.transaction_time.strftime("%Y-%m-%d %H:%M:%S") if log.transaction_time else "",
            log.transaction_type,
            log.order_no or "",
            f"{log.amount:.2f}",
            (log.summary or "").replace(",", "，").replace("\n", " "),
            str(log.related_distributor_id) if log.related_distributor_id else "",
            log.distributor.user.username if log.distributor and log.distributor.user else (log.distributor.id if log.distributor else "")
        ]
        output.write(",".join(row) + "\n")
    
    output.seek(0)
    
    log_info(
        message=f"导出财务流水 CSV，共 {len(logs)} 条记录",
        action="FINANCE_LOGS_EXPORTED",
        tourist_id=current_user.id
    )
    
    filename = f"financial_logs_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv; charset=utf-8-sig",
        headers={
            "Content-Disposition": f"attachment; filename={filename}",
            "Access-Control-Expose-Headers": "Content-Disposition"
        }
    )


@app.post("/tickets/orders/{order_id}/refund", response_model=schemas.RefundResponse, tags=["门票支付"])
@security.rate_limit("10/minute")
async def refund_ticket_order(
    request: Request,
    order_id: int,
    refund_data: Optional[schemas.RefundRequest] = None,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.require_role(models.UserRole.ADMIN, models.UserRole.STAFF))
):
    from datetime import datetime
    from sqlalchemy.orm import joinedload
    
    order = db.query(models.TicketOrder).options(
        joinedload(models.TicketOrder.distributor)
    ).filter(
        models.TicketOrder.id == order_id
    ).first()
    
    if order is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="订单不存在"
        )
    
    if order.status == models.OrderStatus.REFUNDED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="该订单已退款"
        )
    
    if order.status != models.OrderStatus.PAID:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="只有已支付的订单才能退款"
        )
    
    refund_amount = order.total_price
    if refund_data and refund_data.refund_amount is not None:
        if refund_data.refund_amount > order.total_price:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="退款金额不能大于订单金额"
            )
        if refund_data.refund_amount < 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="退款金额不能为负数"
            )
        refund_amount = refund_data.refund_amount
    
    reason = refund_data.reason if refund_data else "管理员操作退款"
    
    try:
        original_status = order.status
        
        order.status = models.OrderStatus.REFUNDED
        
        refund_log = models.FinancialLog(
            transaction_type=models.TransactionType.REFUND,
            order_no=order.order_no,
            amount=refund_amount,
            transaction_time=datetime.utcnow(),
            summary=f"订单退款，订单号: {order.order_no}, 原订单金额: {order.total_price}元, 退款金额: {refund_amount}元, 原因: {reason}",
            related_distributor_id=order.distributor_id
        )
        db.add(refund_log)
        
        if order.distributor and order.commission_amount and order.commission_amount > 0:
            reverse_commission_log = models.FinancialLog(
                transaction_type=models.TransactionType.DISTRIBUTION_EXPENSE,
                order_no=order.order_no,
                amount=-order.commission_amount,
                transaction_time=datetime.utcnow(),
                summary=f"退款冲抵分销佣金，订单号: {order.order_no}, 原佣金金额: {order.commission_amount}元",
                related_distributor_id=order.distributor_id
            )
            db.add(reverse_commission_log)
        
        db.commit()
        db.refresh(order)
        
        log_info(
            message=f"订单退款成功: 订单号={order.order_no}, 原金额={order.total_price}, 退款金额={refund_amount}, 原状态={original_status}",
            action="ORDER_REFUNDED",
            order_id=order.order_no,
            tourist_id=current_user.id,
            scenic_spot_id=order.scenic_spot_id
        )
        
        audit_manager = security.get_audit_log_manager()
        audit_manager.log_action(
            user_id=current_user.id,
            module=models.AuditLogModule.FINANCE,
            action=models.AuditLogAction.UPDATE,
            target_id=order_id,
            target_type="TicketOrder",
            details=f"管理员 {current_user.username} 对订单 {order.order_no} 执行退款操作: 原金额={order.total_price}, 退款金额={refund_amount}, 原因={reason}",
            ip_address=request.client.host if request.client else None
        )
        
        return schemas.RefundResponse(
            success=True,
            order_no=order.order_no,
            refund_amount=round(refund_amount, 2),
            message=f"订单退款成功，退款金额: {refund_amount} 元"
        )
        
    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        log_error(
            message=f"订单退款失败: 订单ID={order_id}, 错误={str(e)}",
            action="ORDER_REFUND_FAILED",
            order_id=order_id,
            tourist_id=current_user.id,
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="退款操作失败，请稍后重试"
        )


app.include_router(finance_router)
app.include_router(attendance_router)


analytics_router = APIRouter(prefix="/analytics", tags=["智能大数据分析"])


@analytics_router.get("/overview", response_model=schemas.AnalyticsOverview)
def get_analytics_overview(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.require_role(models.UserRole.ADMIN, models.UserRole.STAFF))
):
    from sqlalchemy import func
    from datetime import datetime, timedelta
    
    now = datetime.utcnow()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    today_end = today_start + timedelta(days=1)
    
    month_start = today_start.replace(day=1)
    month_end = (month_start + timedelta(days=32)).replace(day=1)
    
    today_sales_total = db.query(func.sum(models.TicketOrder.total_price)).filter(
        models.TicketOrder.status == models.OrderStatus.PAID,
        models.TicketOrder.paid_at >= today_start,
        models.TicketOrder.paid_at < today_end
    ).scalar() or 0.0
    
    today_visitor_count = db.query(func.sum(models.TouristFlow.entry_count)).filter(
        models.TouristFlow.record_time >= today_start,
        models.TouristFlow.record_time < today_end
    ).scalar() or 0
    
    all_recent_flows = db.query(models.TouristFlow).filter(
        models.TouristFlow.record_time >= today_start - timedelta(hours=24)
    ).all()
    
    current_in_scenic_count = sum(flow.entry_count for flow in all_recent_flows)
    
    month_income = db.query(func.sum(models.FinancialLog.amount)).filter(
        models.FinancialLog.transaction_type == models.TransactionType.INCOME,
        models.FinancialLog.transaction_time >= month_start,
        models.FinancialLog.transaction_time < month_end
    ).scalar() or 0.0
    
    month_distribution = db.query(func.sum(models.FinancialLog.amount)).filter(
        models.FinancialLog.transaction_type == models.TransactionType.DISTRIBUTION_EXPENSE,
        models.FinancialLog.transaction_time >= month_start,
        models.FinancialLog.transaction_time < month_end
    ).scalar() or 0.0
    
    month_refund = db.query(func.sum(models.FinancialLog.amount)).filter(
        models.FinancialLog.transaction_type == models.TransactionType.REFUND,
        models.FinancialLog.transaction_time >= month_start,
        models.FinancialLog.transaction_time < month_end
    ).scalar() or 0.0
    
    month_total_profit = month_income - month_distribution - month_refund
    
    total_users = db.query(models.User).count()
    member_users = db.query(models.User).filter(
        models.User.member_level != models.MemberLevel.NORMAL
    ).count()
    
    member_conversion_rate = (member_users / total_users * 100) if total_users > 0 else 0.0
    
    log_info(
        message=f"大数据概览查询: 今日销售额={today_sales_total}, 今日入园={today_visitor_count}, 当前在园={current_in_scenic_count}, 本月利润={month_total_profit}, 会员转化率={member_conversion_rate}%",
        action="ANALYTICS_OVERVIEW_QUERIED",
        tourist_id=current_user.id
    )
    
    return schemas.AnalyticsOverview(
        today_sales_total=round(today_sales_total, 2),
        today_visitor_count=today_visitor_count,
        current_in_scenic_count=current_in_scenic_count,
        month_total_profit=round(month_total_profit, 2),
        member_conversion_rate=round(member_conversion_rate, 2),
        updated_at=now
    )


@analytics_router.get("/sales-trend", response_model=schemas.SalesTrendResponse)
def get_sales_trend(
    days: int = Query(7, ge=1, le=30, description="查询天数，默认7天"),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.require_role(models.UserRole.ADMIN, models.UserRole.STAFF))
):
    from sqlalchemy import func
    from datetime import datetime, timedelta
    
    now = datetime.utcnow()
    period_end = now.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
    period_start = period_end - timedelta(days=days)
    
    results = db.query(
        func.date(models.TicketOrder.paid_at).label('order_date'),
        func.count(models.TicketOrder.id).label('order_count'),
        func.sum(models.TicketOrder.total_price).label('total_income')
    ).filter(
        models.TicketOrder.status == models.OrderStatus.PAID,
        models.TicketOrder.paid_at >= period_start,
        models.TicketOrder.paid_at < period_end
    ).group_by(
        func.date(models.TicketOrder.paid_at)
    ).order_by(
        'order_date'
    ).all()
    
    daily_data = {}
    for row in results:
        date_str = str(row.order_date)
        daily_data[date_str] = {
            'order_count': row.order_count or 0,
            'income': row.total_income or 0.0
        }
    
    trend_data = []
    current_date = period_start
    while current_date < period_end:
        date_str = current_date.strftime('%Y-%m-%d')
        day_data = daily_data.get(date_str, {'order_count': 0, 'income': 0.0})
        trend_data.append(schemas.DailySalesData(
            date=date_str,
            order_count=day_data['order_count'],
            income=round(day_data['income'], 2)
        ))
        current_date += timedelta(days=1)
    
    log_info(
        message=f"销售趋势查询: 天数={days}, 数据点={len(trend_data)}",
        action="ANALYTICS_SALES_TREND_QUERIED",
        tourist_id=current_user.id
    )
    
    return schemas.SalesTrendResponse(
        data=trend_data,
        period_start=period_start.strftime('%Y-%m-%d'),
        period_end=(period_end - timedelta(days=1)).strftime('%Y-%m-%d')
    )


@analytics_router.get("/tourist-source", response_model=schemas.TouristSourceResponse)
def get_tourist_source(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.require_role(models.UserRole.ADMIN, models.UserRole.STAFF))
):
    from collections import Counter
    
    users = db.query(models.User).all()
    
    source_counts = Counter()
    for user in users:
        source = "直接注册"
        if user.member_level == models.MemberLevel.GOLD:
            source = "黄金会员"
        elif user.member_level == models.MemberLevel.SILVER:
            source = "白银会员"
        source_counts[source] += 1
    
    distributors = db.query(models.Distributor).all()
    if distributors:
        source_counts["分销渠道"] = len(distributors)
    
    total_count = sum(source_counts.values())
    
    source_data = []
    for source, count in source_counts.most_common():
        percentage = (count / total_count * 100) if total_count > 0 else 0.0
        source_data.append(schemas.TouristSourceData(
            source=source,
            count=count,
            percentage=round(percentage, 2)
        ))
    
    log_info(
        message=f"游客来源统计: 总数={total_count}, 来源类别={len(source_data)}",
        action="ANALYTICS_TOURIST_SOURCE_QUERIED",
        tourist_id=current_user.id
    )
    
    return schemas.TouristSourceResponse(
        data=source_data,
        total_count=total_count
    )


@analytics_router.get("/dashboard", tags=["智能大数据分析"])
def get_dashboard_page():
    dashboard_path = os.path.join(STATIC_DIR, "dashboard.html")
    if os.path.exists(dashboard_path):
        return FileResponse(dashboard_path)
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="数据大屏页面不存在"
    )


@analytics_router.get("/flow-prediction", response_model=schemas.FlowPredictionResponse, tags=["智能大数据分析"])
def get_flow_prediction(
    days: int = Query(7, ge=1, le=30, description="历史数据天数，默认7天"),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.require_role(models.UserRole.ADMIN, models.UserRole.STAFF))
):
    from sqlalchemy import func
    from datetime import datetime, timedelta
    import statistics
    
    now = datetime.utcnow()
    current_hour = now.hour
    period_end = now
    period_start = period_end - timedelta(days=days)
    
    hourly_data = db.query(
        func.strftime('%H', models.TouristFlow.record_time).label('hour'),
        func.strftime('%Y-%m-%d', models.TouristFlow.record_time).label('date'),
        func.sum(models.TouristFlow.entry_count).label('total_visitors')
    ).filter(
        models.TouristFlow.record_time >= period_start,
        models.TouristFlow.record_time < period_end
    ).group_by(
        func.strftime('%Y-%m-%d', models.TouristFlow.record_time),
        func.strftime('%H', models.TouristFlow.record_time)
    ).order_by(
        'date', 'hour'
    ).all()
    
    hourly_stats = {}
    for row in hourly_data:
        hour = int(row.hour)
        if hour not in hourly_stats:
            hourly_stats[hour] = []
        hourly_stats[hour].append(row.total_visitors)
    
    daily_data = db.query(
        func.date(models.TouristFlow.record_time).label('flow_date'),
        func.sum(models.TouristFlow.entry_count).label('daily_visitors')
    ).filter(
        models.TouristFlow.record_time >= period_start,
        models.TouristFlow.record_time < period_end
    ).group_by(
        func.date(models.TouristFlow.record_time)
    ).order_by(
        'flow_date'
    ).all()
    
    daily_visitors = [row.daily_visitors for row in daily_data] if daily_data else [0]
    
    if len(daily_visitors) >= 2:
        recent_avg = sum(daily_visitors[-3:]) / len(daily_visitors[-3:]) if len(daily_visitors) >= 3 else daily_visitors[-1]
        older_avg = sum(daily_visitors[:-3]) / len(daily_visitors[:-3]) if len(daily_visitors) > 3 else daily_visitors[0] if daily_visitors else 0
        
        if recent_avg > older_avg * 1.1:
            trend_direction = "上升"
        elif recent_avg < older_avg * 0.9:
            trend_direction = "下降"
        else:
            trend_direction = "平稳"
    else:
        trend_direction = "平稳"
    
    hourly_predictions = []
    peak_hour = 14
    peak_visitors = 0
    
    base_hourly_pattern = {
        8: 0.5, 9: 0.7, 10: 0.9, 11: 0.95, 12: 0.85,
        13: 0.75, 14: 1.0, 15: 0.95, 16: 0.9, 17: 0.8,
        18: 0.6, 19: 0.4, 20: 0.2, 21: 0.1, 22: 0.05,
        0: 0.02, 1: 0.01, 2: 0.01, 3: 0.01, 4: 0.01,
        5: 0.02, 6: 0.05, 7: 0.3
    }
    
    avg_daily_visitors = sum(daily_visitors) / len(daily_visitors) if daily_visitors else 100
    
    for hour_offset in range(24):
        prediction_hour = (current_hour + hour_offset) % 24
        
        historical_values = hourly_stats.get(prediction_hour, [])
        if historical_values:
            avg_value = statistics.mean(historical_values)
            if len(historical_values) > 1:
                std_dev = statistics.stdev(historical_values)
                confidence = max(0.5, 1.0 - (std_dev / (avg_value + 1)) * 0.5)
            else:
                confidence = 0.7
        else:
            pattern_factor = base_hourly_pattern.get(prediction_hour, 0.3)
            avg_value = avg_daily_visitors * pattern_factor / 24 * 2
            confidence = 0.5
        
        if prediction_hour >= 9 and prediction_hour <= 11:
            trend_factor = 1.1 if trend_direction == "上升" else (0.9 if trend_direction == "下降" else 1.0)
            predicted_visitors = int(avg_value * trend_factor)
        elif prediction_hour >= 13 and prediction_hour <= 16:
            trend_factor = 1.15 if trend_direction == "上升" else (0.85 if trend_direction == "下降" else 1.0)
            predicted_visitors = int(avg_value * trend_factor)
        else:
            predicted_visitors = int(avg_value)
        
        predicted_visitors = max(0, predicted_visitors)
        
        hourly_predictions.append(schemas.HourlyPrediction(
            hour=prediction_hour,
            predicted_visitors=predicted_visitors,
            confidence=round(confidence, 2)
        ))
        
        if predicted_visitors > peak_visitors:
            peak_visitors = predicted_visitors
            peak_hour = prediction_hour
    
    total_predicted_24h = sum(h.predicted_visitors for h in hourly_predictions)
    
    log_info(
        message=f"客流预测查询: 基于{days}天历史数据, 预测峰值={peak_visitors}人({peak_hour}时), 趋势={trend_direction}",
        action="ANALYTICS_FLOW_PREDICTION_QUERIED",
        tourist_id=current_user.id
    )
    
    return schemas.FlowPredictionResponse(
        peak_hour=peak_hour,
        peak_visitors=peak_visitors,
        total_predicted_24h=total_predicted_24h,
        hourly_data=hourly_predictions,
        prediction_basis_days=days,
        trend_direction=trend_direction,
        updated_at=now
    )


@analytics_router.get("/member-analysis", response_model=schemas.MemberAnalysisResponse, tags=["智能大数据分析"])
def get_member_analysis(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.require_role(models.UserRole.ADMIN, models.UserRole.STAFF))
):
    from sqlalchemy import func
    from datetime import datetime, timedelta
    from sqlalchemy.orm import joinedload
    
    now = datetime.utcnow()
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    month_end = (month_start + timedelta(days=32)).replace(day=1)
    
    all_users = db.query(models.User).all()
    
    level_user_count = {
        models.MemberLevel.GOLD: 0,
        models.MemberLevel.SILVER: 0,
        models.MemberLevel.NORMAL: 0
    }
    
    for user in all_users:
        level_user_count[user.member_level] += 1
    
    order_stats = db.query(
        models.User.member_level,
        func.count(models.TicketOrder.id).label('order_count'),
        func.sum(models.TicketOrder.total_price).label('total_spent')
    ).join(
        models.TicketOrder, models.User.id == models.TicketOrder.user_id
    ).filter(
        models.TicketOrder.status == models.OrderStatus.PAID,
        models.TicketOrder.paid_at >= month_start,
        models.TicketOrder.paid_at < month_end
    ).group_by(
        models.User.member_level
    ).all()
    
    level_order_stats = {}
    for row in order_stats:
        level_order_stats[row.member_level] = {
            'order_count': row.order_count or 0,
            'total_spent': row.total_spent or 0.0
        }
    
    financial_income = db.query(func.sum(models.FinancialLog.amount)).filter(
        models.FinancialLog.transaction_type == models.TransactionType.INCOME,
        models.FinancialLog.transaction_time >= month_start,
        models.FinancialLog.transaction_time < month_end
    ).scalar() or 0.0
    
    financial_distribution = db.query(func.sum(models.FinancialLog.amount)).filter(
        models.FinancialLog.transaction_type == models.TransactionType.DISTRIBUTION_EXPENSE,
        models.FinancialLog.transaction_time >= month_start,
        models.FinancialLog.transaction_time < month_end
    ).scalar() or 0.0
    
    financial_refund = db.query(func.sum(models.FinancialLog.amount)).filter(
        models.FinancialLog.transaction_type == models.TransactionType.REFUND,
        models.FinancialLog.transaction_time >= month_start,
        models.FinancialLog.transaction_time < month_end
    ).scalar() or 0.0
    
    total_profit = financial_income - financial_distribution - financial_refund
    
    profit_margin = 0.70
    
    by_level = []
    total_profit_contribution = 0.0
    
    level_order = [models.MemberLevel.GOLD, models.MemberLevel.SILVER, models.MemberLevel.NORMAL]
    level_names = {
        models.MemberLevel.GOLD: "黄金会员",
        models.MemberLevel.SILVER: "白银会员",
        models.MemberLevel.NORMAL: "普通用户"
    }
    
    for level in level_order:
        stats = level_order_stats.get(level, {'order_count': 0, 'total_spent': 0.0})
        user_count = level_user_count.get(level, 0)
        
        if stats['order_count'] > 0:
            avg_order_value = stats['total_spent'] / stats['order_count']
        else:
            avg_order_value = 0.0
        
        profit_contribution = stats['total_spent'] * profit_margin
        total_profit_contribution += profit_contribution
        
        by_level.append(schemas.MemberLevelStats(
            member_level=level_names[level],
            user_count=user_count,
            total_orders=stats['order_count'],
            total_spent=round(stats['total_spent'], 2),
            avg_order_value=round(avg_order_value, 2),
            profit_contribution=round(profit_contribution, 2),
            profit_contribution_ratio=0.0
        ))
    
    for level_stat in by_level:
        if total_profit_contribution > 0:
            level_stat.profit_contribution_ratio = round(
                level_stat.profit_contribution / total_profit_contribution * 100, 2
            )
    
    total_users = len(all_users)
    total_members = level_user_count[models.MemberLevel.GOLD] + level_user_count[models.MemberLevel.SILVER]
    conversion_rate = (total_members / total_users * 100) if total_users > 0 else 0.0
    
    log_info(
        message=f"会员分析查询: 总用户={total_users}, 会员={total_members}, 转化率={conversion_rate:.1f}%, 本月利润={total_profit:.2f}",
        action="ANALYTICS_MEMBER_ANALYSIS_QUERIED",
        tourist_id=current_user.id
    )
    
    return schemas.MemberAnalysisResponse(
        total_users=total_users,
        total_members=total_members,
        conversion_rate=round(conversion_rate, 2),
        by_level=by_level,
        total_profit=round(total_profit, 2),
        updated_at=now
    )


@analytics_router.get("/inventory-alerts", response_model=schemas.InventoryAlertResponse, tags=["智能大数据分析"])
def get_inventory_alerts(
    threshold: float = Query(0.10, ge=0.01, le=0.50, description="告警阈值比例，默认10%"),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.require_role(models.UserRole.ADMIN, models.UserRole.STAFF))
):
    from datetime import datetime
    
    now = datetime.utcnow()
    
    all_spots = db.query(models.ScenicSpot).all()
    
    alerts = []
    total_estimated_loss = 0.0
    
    for spot in all_spots:
        if spot.total_inventory == 0:
            inventory_ratio = 0.0
        else:
            inventory_ratio = spot.remained_inventory / spot.total_inventory
        
        if inventory_ratio <= threshold:
            sold_tickets = spot.total_inventory - spot.remained_inventory
            
            if sold_tickets > 0:
                avg_daily_sales = sold_tickets / 30
                days_to_depletion = spot.remained_inventory / avg_daily_sales if avg_daily_sales > 0 else 0
                
                if inventory_ratio <= 0.05 or days_to_depletion <= 3:
                    alert_level = "紧急"
                elif inventory_ratio <= 0.10 or days_to_depletion <= 7:
                    alert_level = "警告"
                else:
                    alert_level = "注意"
            else:
                alert_level = "注意" if inventory_ratio <= 0.10 else "警告"
            
            estimated_revenue_loss = (spot.total_inventory - spot.remained_inventory) * spot.price * 0.1
            
            total_estimated_loss += estimated_revenue_loss
            
            alerts.append(schemas.InventoryAlertItem(
                spot_id=spot.id,
                spot_name=spot.name,
                total_inventory=spot.total_inventory,
                remained_inventory=spot.remained_inventory,
                inventory_ratio=round(inventory_ratio, 4),
                price_per_ticket=round(spot.price, 2),
                estimated_revenue_loss=round(estimated_revenue_loss, 2),
                alert_level=alert_level
            ))
    
    alerts.sort(key=lambda x: x.inventory_ratio)
    
    log_info(
        message=f"库存预警查询: 阈值={threshold*100:.0f}%, 告警数量={len(alerts)}, 预估营收损失={total_estimated_loss:.2f}",
        action="ANALYTICS_INVENTORY_ALERTS_QUERIED",
        tourist_id=current_user.id
    )
    
    return schemas.InventoryAlertResponse(
        has_alerts=len(alerts) > 0,
        alert_count=len(alerts),
        total_estimated_loss=round(total_estimated_loss, 2),
        alerts=alerts,
        threshold=threshold,
        updated_at=now
    )


@analytics_router.get("/smart-overview", response_model=schemas.SmartAnalyticsOverview, tags=["智能大数据分析"])
def get_smart_overview(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.require_role(models.UserRole.ADMIN, models.UserRole.STAFF))
):
    from datetime import datetime, timedelta
    from sqlalchemy import func
    
    now = datetime.utcnow()
    
    overview_data = get_analytics_overview.__wrapped__ if hasattr(get_analytics_overview, '__wrapped__') else get_analytics_overview
    try:
        overview = overview_data(db=db, current_user=current_user)
    except:
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        today_end = today_start + timedelta(days=1)
        month_start = today_start.replace(day=1)
        month_end = (month_start + timedelta(days=32)).replace(day=1)
        
        today_sales_total = db.query(func.sum(models.TicketOrder.total_price)).filter(
            models.TicketOrder.status == models.OrderStatus.PAID,
            models.TicketOrder.paid_at >= today_start,
            models.TicketOrder.paid_at < today_end
        ).scalar() or 0.0
        
        today_visitor_count = db.query(func.sum(models.TouristFlow.entry_count)).filter(
            models.TouristFlow.record_time >= today_start,
            models.TouristFlow.record_time < today_end
        ).scalar() or 0
        
        all_recent_flows = db.query(models.TouristFlow).filter(
            models.TouristFlow.record_time >= today_start - timedelta(hours=24)
        ).all()
        current_in_scenic_count = sum(flow.entry_count for flow in all_recent_flows)
        
        month_income = db.query(func.sum(models.FinancialLog.amount)).filter(
            models.FinancialLog.transaction_type == models.TransactionType.INCOME,
            models.FinancialLog.transaction_time >= month_start,
            models.FinancialLog.transaction_time < month_end
        ).scalar() or 0.0
        
        month_distribution = db.query(func.sum(models.FinancialLog.amount)).filter(
            models.FinancialLog.transaction_type == models.TransactionType.DISTRIBUTION_EXPENSE,
            models.FinancialLog.transaction_time >= month_start,
            models.FinancialLog.transaction_time < month_end
        ).scalar() or 0.0
        
        month_refund = db.query(func.sum(models.FinancialLog.amount)).filter(
            models.FinancialLog.transaction_type == models.TransactionType.REFUND,
            models.FinancialLog.transaction_time >= month_start,
            models.FinancialLog.transaction_time < month_end
        ).scalar() or 0.0
        
        month_total_profit = month_income - month_distribution - month_refund
        
        total_users = db.query(models.User).count()
        member_users = db.query(models.User).filter(
            models.User.member_level != models.MemberLevel.NORMAL
        ).count()
        member_conversion_rate = (member_users / total_users * 100) if total_users > 0 else 0.0
        
        overview = schemas.AnalyticsOverview(
            today_sales_total=round(today_sales_total, 2),
            today_visitor_count=today_visitor_count,
            current_in_scenic_count=current_in_scenic_count,
            month_total_profit=round(month_total_profit, 2),
            member_conversion_rate=round(member_conversion_rate, 2),
            updated_at=now
        )
    
    prediction_data = get_flow_prediction.__wrapped__ if hasattr(get_flow_prediction, '__wrapped__') else get_flow_prediction
    try:
        prediction = prediction_data(days=7, db=db, current_user=current_user)
    except:
        prediction = schemas.FlowPredictionResponse(
            peak_hour=14,
            peak_visitors=0,
            total_predicted_24h=0,
            hourly_data=[],
            prediction_basis_days=7,
            trend_direction="平稳",
            updated_at=now
        )
    
    member_data = get_member_analysis.__wrapped__ if hasattr(get_member_analysis, '__wrapped__') else get_member_analysis
    try:
        member_analysis = member_data(db=db, current_user=current_user)
    except:
        member_analysis = schemas.MemberAnalysisResponse(
            total_users=0,
            total_members=0,
            conversion_rate=0.0,
            by_level=[],
            total_profit=0.0,
            updated_at=now
        )
    
    inventory_data = get_inventory_alerts.__wrapped__ if hasattr(get_inventory_alerts, '__wrapped__') else get_inventory_alerts
    try:
        inventory_alerts = inventory_data(threshold=0.10, db=db, current_user=current_user)
    except:
        inventory_alerts = schemas.InventoryAlertResponse(
            has_alerts=False,
            alert_count=0,
            total_estimated_loss=0.0,
            alerts=[],
            threshold=0.10,
            updated_at=now
        )
    
    log_info(
        message="智能概览聚合查询完成",
        action="ANALYTICS_SMART_OVERVIEW_QUERIED",
        tourist_id=current_user.id
    )
    
    return schemas.SmartAnalyticsOverview(
        overview=overview,
        prediction=prediction,
        member_analysis=member_analysis,
        inventory_alerts=inventory_alerts,
        updated_at=now
    )


app.include_router(analytics_router)


system_dashboard_router = APIRouter(prefix="/system", tags=["系统监控"])


@system_dashboard_router.get("/health", response_model=schemas.SystemHealthResponse)
async def get_system_health(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.require_role(models.UserRole.ADMIN))
):
    now = datetime.now()
    
    try:
        db.execute(text("SELECT 1"))
        database_status = "健康"
    except Exception:
        database_status = "异常"
    
    try:
        import psutil
        process = psutil.Process()
        memory_info = process.memory_info()
        memory_usage_mb = memory_info.rss / 1024 / 1024
        cpu_usage_percent = process.cpu_percent(interval=0.1)
    except ImportError:
        memory_usage_mb = 0.0
        cpu_usage_percent = 0.0
    
    return schemas.SystemHealthResponse(
        database_status=database_status,
        api_status="运行中",
        active_connections=0,
        uptime_seconds=get_uptime_seconds(),
        memory_usage_mb=round(memory_usage_mb, 2),
        cpu_usage_percent=round(cpu_usage_percent, 2),
        updated_at=now
    )


@system_dashboard_router.get("/performance", response_model=schemas.PerformanceStatsResponse)
async def get_performance_stats(
    minutes: int = Query(5, ge=1, le=60, description="统计时间范围（分钟）"),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.require_role(models.UserRole.ADMIN))
):
    monitor = security.get_performance_monitor()
    stats = monitor.get_stats(minutes)
    
    endpoint_stats_list = []
    for endpoint, data in stats.get('endpoint_stats', {}).items():
        endpoint_stats_list.append(schemas.EndpointPerformanceStats(
            endpoint=endpoint,
            requests=data.get('requests', 0),
            avg_duration_ms=data.get('avg_duration_ms', 0.0),
            min_duration_ms=data.get('min_duration_ms', 0.0),
            max_duration_ms=data.get('max_duration_ms', 0.0)
        ))
    
    error_logs_list = []
    for error in stats.get('recent_errors', []):
        error_logs_list.append(schemas.ErrorLogEntry(
            timestamp=error.get('timestamp', datetime.now()),
            endpoint=error.get('endpoint', ''),
            error_message=error.get('error_message', ''),
            status_code=error.get('status_code', 500)
        ))
    
    return schemas.PerformanceStatsResponse(
        total_requests=stats.get('total_requests', 0),
        average_response_time_ms=stats.get('average_response_time_ms', 0.0),
        endpoint_stats=endpoint_stats_list,
        recent_errors=error_logs_list,
        updated_at=datetime.now()
    )


@system_dashboard_router.get("/audit-logs", response_model=schemas.AuditLogListResponse)
async def get_audit_logs(
    module: Optional[str] = Query(None, description="模块名称"),
    action: Optional[str] = Query(None, description="操作类型"),
    user_id: Optional[int] = Query(None, description="用户ID"),
    limit: int = Query(100, ge=1, le=1000, description="返回数量限制"),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.require_role(models.UserRole.ADMIN))
):
    query = db.query(models.AuditLog)
    
    if module:
        try:
            module_enum = models.AuditLogModule(module)
            query = query.filter(models.AuditLog.module == module_enum)
        except ValueError:
            pass
    
    if action:
        try:
            action_enum = models.AuditLogAction(action)
            query = query.filter(models.AuditLog.action == action_enum)
        except ValueError:
            pass
    
    if user_id:
        query = query.filter(models.AuditLog.user_id == user_id)
    
    total = query.count()
    logs = query.order_by(models.AuditLog.timestamp.desc()).limit(limit).all()
    
    return schemas.AuditLogListResponse(
        total=total,
        items=logs,
        module=module,
        action=action,
        user_id=user_id
    )


@system_dashboard_router.get("/doctor", response_model=schemas.SystemDoctorDashboard)
async def get_system_doctor_dashboard(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.require_role(models.UserRole.ADMIN))
):
    health = await get_system_health(db=db, current_user=current_user)
    performance = await get_performance_stats(minutes=5, db=db, current_user=current_user)
    
    recent_logs = db.query(models.AuditLog).order_by(
        models.AuditLog.timestamp.desc()
    ).limit(10).all()
    
    return schemas.SystemDoctorDashboard(
        performance=performance,
        health=health,
        recent_audit_logs=recent_logs,
        updated_at=datetime.now()
    )


@system_dashboard_router.get("/doctor-page")
async def get_system_doctor_page(
    current_user: models.User = Depends(auth.require_role(models.UserRole.ADMIN))
):
    doctor_page_path = os.path.join(STATIC_DIR, "system-doctor.html")
    if os.path.exists(doctor_page_path):
        return FileResponse(doctor_page_path)
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="系统医生页面不存在"
    )


app.include_router(system_dashboard_router)


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
