import time
import hashlib
import threading
from typing import Dict, Any, Optional, Callable
from functools import wraps
from fastapi import Request, HTTPException, status
from datetime import datetime, timedelta
from collections import defaultdict
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.backends import default_backend
import base64
import re

ENCRYPTION_KEY = b"smart-tourism-2024-very-secure-encryption-key-here"
SALT = b"smart_tourism_salt_2024"


def get_fernet_key() -> bytes:
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=SALT,
        iterations=100000,
        backend=default_backend(),
    )
    key = base64.urlsafe_b64encode(kdf.derive(ENCRYPTION_KEY))
    return key


_fernet_instance = None
_fernet_lock = threading.Lock()


def get_fernet() -> Fernet:
    global _fernet_instance
    if _fernet_instance is None:
        with _fernet_lock:
            if _fernet_instance is None:
                _fernet_instance = Fernet(get_fernet_key())
    return _fernet_instance


def encrypt_data(data: str) -> str:
    if not data:
        return data
    try:
        fernet = get_fernet()
        encrypted = fernet.encrypt(data.encode('utf-8'))
        return encrypted.decode('utf-8')
    except Exception:
        return data


def decrypt_data(encrypted_data: str) -> str:
    if not encrypted_data:
        return encrypted_data
    try:
        fernet = get_fernet()
        decrypted = fernet.decrypt(encrypted_data.encode('utf-8'))
        return decrypted.decode('utf-8')
    except Exception:
        return encrypted_data


def mask_phone(phone: Optional[str]) -> Optional[str]:
    if not phone:
        return phone
    phone = str(phone).strip()
    if len(phone) == 11:
        return phone[:3] + "****" + phone[7:]
    elif len(phone) > 4:
        return phone[:2] + "****" + phone[-2:]
    return phone


def mask_id_card(id_card: Optional[str]) -> Optional[str]:
    if not id_card:
        return id_card
    id_card = str(id_card).strip()
    if len(id_card) == 18:
        return id_card[:6] + "********" + id_card[-4:]
    elif len(id_card) == 15:
        return id_card[:6] + "*******" + id_card[-4:]
    elif len(id_card) > 8:
        return id_card[:4] + "****" + id_card[-4:]
    return id_card


def mask_email(email: Optional[str]) -> Optional[str]:
    if not email:
        return email
    email = str(email).strip()
    if '@' in email:
        parts = email.split('@')
        if len(parts[0]) > 2:
            return parts[0][:2] + "***" + "@" + parts[1]
        return "*" + "@" + parts[1]
    return email


def mask_bank_account(account: Optional[str]) -> Optional[str]:
    if not account:
        return account
    account = str(account).strip()
    if len(account) > 8:
        return account[:4] + "****" + account[-4:]
    return account


def mask_location(location: Optional[str]) -> Optional[str]:
    if not location:
        return location
    location = str(location).strip()
    if len(location) > 6:
        return location[:3] + "***" + location[-3:] if len(location) > 6 else location
    return location


def mask_sensitive_data(data: Any, fields: Dict[str, str] = None) -> Any:
    if fields is None:
        fields = {
            'phone': 'phone',
            'id_card': 'id_card',
            'email': 'email',
            'bank_account': 'bank_account',
            'location': 'location',
            'mobile': 'phone',
            'telephone': 'phone',
            'idcard': 'id_card',
            'id_no': 'id_card',
            'identity': 'id_card',
        }
    
    if data is None:
        return None
    
    if isinstance(data, dict):
        result = {}
        for key, value in data.items():
            key_lower = key.lower()
            if key_lower in fields:
                field_type = fields[key_lower]
                if field_type == 'phone':
                    result[key] = mask_phone(value)
                elif field_type == 'id_card':
                    result[key] = mask_id_card(value)
                elif field_type == 'email':
                    result[key] = mask_email(value)
                elif field_type == 'bank_account':
                    result[key] = mask_bank_account(value)
                elif field_type == 'location':
                    result[key] = mask_location(value)
                else:
                    result[key] = mask_sensitive_data(value, fields)
            else:
                result[key] = mask_sensitive_data(value, fields)
        return result
    elif isinstance(data, list):
        return [mask_sensitive_data(item, fields) for item in data]
    elif hasattr(data, 'model_dump'):
        try:
            data_dict = data.model_dump()
            masked_dict = mask_sensitive_data(data_dict, fields)
            for key, value in masked_dict.items():
                if hasattr(data, key):
                    try:
                        setattr(data, key, value)
                    except Exception:
                        pass
            return data
        except Exception:
            pass
    elif hasattr(data, '__dict__'):
        try:
            obj_dict = dict(data.__dict__)
            masked_dict = mask_sensitive_data(obj_dict, fields)
            for key, value in masked_dict.items():
                if hasattr(data, key) and not key.startswith('_'):
                    try:
                        setattr(data, key, value)
                    except Exception:
                        pass
            return data
        except Exception:
            pass
    return data


def mask_response_content(content: Any) -> Any:
    return mask_sensitive_data(content)


class RateLimiter:
    def __init__(self, default_rate: str = "60/minute"):
        self.default_rate = default_rate
        self.request_counts: Dict[str, Dict[str, Any]] = defaultdict(lambda: {
            'count': 0,
            'start_time': time.time()
        })
        self._lock = threading.Lock()
    
    def _parse_rate(self, rate: str) -> tuple:
        parts = rate.lower().split('/')
        if len(parts) != 2:
            raise ValueError(f"Invalid rate format: {rate}")
        
        count = int(parts[0].strip())
        period = parts[1].strip()
        
        if period == 'second' or period == 's':
            seconds = 1
        elif period == 'minute' or period == 'min' or period == 'm':
            seconds = 60
        elif period == 'hour' or period == 'h':
            seconds = 3600
        elif period == 'day' or period == 'd':
            seconds = 86400
        else:
            match = re.match(r'(\d+)(s|m|h|d)?', period)
            if match:
                num = int(match.group(1))
                unit = match.group(2) or 's'
                if unit == 's':
                    seconds = num
                elif unit == 'm':
                    seconds = num * 60
                elif unit == 'h':
                    seconds = num * 3600
                elif unit == 'd':
                    seconds = num * 86400
                else:
                    seconds = num
            else:
                raise ValueError(f"Invalid period: {period}")
        
        return count, seconds
    
    def check_rate_limit(self, key: str, rate: str = None) -> tuple:
        if rate is None:
            rate = self.default_rate
        
        max_requests, window_seconds = self._parse_rate(rate)
        current_time = time.time()
        
        with self._lock:
            request_data = self.request_counts[key]
            
            if current_time - request_data['start_time'] > window_seconds:
                request_data['count'] = 0
                request_data['start_time'] = current_time
            
            request_data['count'] += 1
            
            if request_data['count'] > max_requests:
                remaining = window_seconds - (current_time - request_data['start_time'])
                return False, max_requests, remaining
            
            return True, max_requests, 0


_global_rate_limiter = None
_rate_limiter_lock = threading.Lock()


def get_global_rate_limiter() -> RateLimiter:
    global _global_rate_limiter
    if _global_rate_limiter is None:
        with _rate_limiter_lock:
            if _global_rate_limiter is None:
                _global_rate_limiter = RateLimiter()
    return _global_rate_limiter


def rate_limit(rate: str = "60/minute"):
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            request: Optional[Request] = None
            for arg in args:
                if isinstance(arg, Request):
                    request = arg
                    break
            
            if request is None:
                for key, value in kwargs.items():
                    if isinstance(value, Request):
                        request = value
                        break
            
            if request is None:
                return await func(*args, **kwargs)
            
            client_ip = request.client.host if request.client else "unknown"
            path = request.url.path
            key = f"{client_ip}:{path}"
            
            limiter = get_global_rate_limiter()
            allowed, max_requests, remaining = limiter.check_rate_limit(key, rate)
            
            if not allowed:
                audit_manager = get_audit_log_manager()
                audit_manager.log_action(
                    user_id=None,
                    module="SYSTEM",
                    action="RATE_LIMIT_BLOCKED",
                    target_id=None,
                    target_type="RateLimit",
                    details=f"限流触发: 路径 {path}, 限制 {rate}, 剩余等待 {int(remaining)} 秒",
                    ip_address=client_ip
                )
                
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail=f"请求过于频繁，请在 {int(remaining)} 秒后重试。限制: {rate}",
                    headers={
                        "X-RateLimit-Limit": str(max_requests),
                        "X-RateLimit-Remaining": "0",
                        "Retry-After": str(int(remaining))
                    }
                )
            
            return await func(*args, **kwargs)
        
        return wrapper
    return decorator


class PerformanceMonitor:
    def __init__(self):
        self.response_times: Dict[str, list] = defaultdict(list)
        self.error_logs: list = []
        self._lock = threading.Lock()
        self._max_logs = 100
        self._max_times = 1000
    
    def record_response_time(self, endpoint: str, duration_ms: float):
        with self._lock:
            self.response_times[endpoint].append({
                'timestamp': datetime.now(),
                'duration_ms': duration_ms
            })
            if len(self.response_times[endpoint]) > self._max_times:
                self.response_times[endpoint] = self.response_times[endpoint][-self._max_times:]
    
    def record_error(self, endpoint: str, error_message: str, status_code: int = 500):
        with self._lock:
            self.error_logs.append({
                'timestamp': datetime.now(),
                'endpoint': endpoint,
                'error_message': error_message,
                'status_code': status_code
            })
            if len(self.error_logs) > self._max_logs:
                self.error_logs = self.error_logs[-self._max_logs:]
    
    def get_average_response_time(self, minutes: int = 5) -> float:
        with self._lock:
            cutoff_time = datetime.now() - timedelta(minutes=minutes)
            total_duration = 0.0
            total_count = 0
            
            for endpoint, times in self.response_times.items():
                for record in times:
                    if record['timestamp'] >= cutoff_time:
                        total_duration += record['duration_ms']
                        total_count += 1
            
            return round(total_duration / total_count, 2) if total_count > 0 else 0.0
    
    def get_recent_errors(self, limit: int = 10) -> list:
        with self._lock:
            return list(self.error_logs[-limit:])
    
    def get_stats(self, minutes: int = 5) -> Dict[str, Any]:
        cutoff_time = datetime.now() - timedelta(minutes=minutes)
        
        with self._lock:
            total_requests = 0
            total_duration = 0.0
            endpoint_stats = {}
            
            for endpoint, times in self.response_times.items():
                recent_times = [t for t in times if t['timestamp'] >= cutoff_time]
                if recent_times:
                    durations = [t['duration_ms'] for t in recent_times]
                    avg_duration = sum(durations) / len(durations)
                    endpoint_stats[endpoint] = {
                        'requests': len(recent_times),
                        'avg_duration_ms': round(avg_duration, 2),
                        'min_duration_ms': round(min(durations), 2),
                        'max_duration_ms': round(max(durations), 2)
                    }
                    total_requests += len(recent_times)
                    total_duration += sum(durations)
            
            return {
                'total_requests': total_requests,
                'average_response_time_ms': round(total_duration / total_requests, 2) if total_requests > 0 else 0.0,
                'endpoint_stats': endpoint_stats,
                'recent_errors': self.get_recent_errors(10)
            }


_performance_monitor = None
_monitor_lock = threading.Lock()


def get_performance_monitor() -> PerformanceMonitor:
    global _performance_monitor
    if _performance_monitor is None:
        with _monitor_lock:
            if _performance_monitor is None:
                _performance_monitor = PerformanceMonitor()
    return _performance_monitor


class AuditLogManager:
    def __init__(self):
        self._db_session = None
        self._lock = threading.Lock()
    
    def set_db_session(self, db_session):
        with self._lock:
            self._db_session = db_session
    
    def _get_new_session(self):
        try:
            from database import SessionLocal
            return SessionLocal()
        except Exception:
            return None
    
    def log_action(
        self,
        user_id: Optional[int],
        module: str,
        action: str,
        target_id: Optional[int] = None,
        target_type: Optional[str] = None,
        details: Optional[str] = None,
        ip_address: Optional[str] = None
    ):
        with self._lock:
            try:
                import models
                
                db = self._get_new_session()
                if db is None:
                    db = self._db_session
                
                if db is not None:
                    try:
                        module_enum = module
                        if isinstance(module, str):
                            try:
                                module_enum = models.AuditLogModule(module)
                            except ValueError:
                                module_enum = models.AuditLogModule.SYSTEM
                        
                        action_enum = action
                        if isinstance(action, str):
                            try:
                                action_enum = models.AuditLogAction(action)
                            except ValueError:
                                action_enum = models.AuditLogAction.OTHER
                        
                        audit_log = models.AuditLog(
                            user_id=user_id,
                            module=module_enum,
                            action=action_enum,
                            target_id=target_id,
                            target_type=target_type,
                            details=details,
                            ip_address=ip_address,
                            timestamp=datetime.utcnow()
                        )
                        db.add(audit_log)
                        db.commit()
                        db.refresh(audit_log)
                    except Exception as e:
                        if db is not None and db != self._db_session:
                            db.rollback()
                        raise
                    finally:
                        if db is not None and db != self._db_session:
                            db.close()
            except Exception as e:
                print(f"[审计日志警告] 记录日志失败: {e}")
                pass
    
    def get_audit_logs(
        self,
        module: Optional[str] = None,
        user_id: Optional[int] = None,
        action: Optional[str] = None,
        limit: int = 100
    ):
        with self._lock:
            if self._db_session is None:
                return []
            import models
            query = self._db_session.query(models.AuditLog)
            
            if module:
                query = query.filter(models.AuditLog.module == module)
            if user_id:
                query = query.filter(models.AuditLog.user_id == user_id)
            if action:
                query = query.filter(models.AuditLog.action == action)
            
            return query.order_by(models.AuditLog.timestamp.desc()).limit(limit).all()


_audit_log_manager = None
_audit_lock = threading.Lock()


def get_audit_log_manager() -> AuditLogManager:
    global _audit_log_manager
    if _audit_log_manager is None:
        with _audit_lock:
            if _audit_log_manager is None:
                _audit_log_manager = AuditLogManager()
    return _audit_log_manager


def audit_log(
    module: str,
    action: str,
    target_id_param: Optional[str] = None,
    target_type: Optional[str] = None
):
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            import inspect
            from fastapi import Depends
            
            user_id = None
            ip_address = None
            target_id = None
            
            for arg in args:
                if hasattr(arg, 'id') and hasattr(arg, 'role'):
                    user_id = arg.id
            
            if target_id_param and target_id_param in kwargs:
                target_id = kwargs[target_id_param]
            
            for arg in args:
                if isinstance(arg, Request):
                    ip_address = arg.client.host if arg.client else None
                    break
            
            for key, value in kwargs.items():
                if isinstance(value, Request):
                    ip_address = value.client.host if value.client else None
                    break
            
            try:
                result = await func(*args, **kwargs)
                
                audit_manager = get_audit_log_manager()
                audit_manager.log_action(
                    user_id=user_id,
                    module=module,
                    action=action,
                    target_id=target_id,
                    target_type=target_type,
                    details=f"操作成功: {func.__name__}",
                    ip_address=ip_address
                )
                
                return result
            except Exception as e:
                audit_manager = get_audit_log_manager()
                audit_manager.log_action(
                    user_id=user_id,
                    module=module,
                    action=f"{action}_FAILED",
                    target_id=target_id,
                    target_type=target_type,
                    details=f"操作失败: {func.__name__}, 错误: {str(e)}",
                    ip_address=ip_address
                )
                raise
        
        return wrapper
    return decorator
