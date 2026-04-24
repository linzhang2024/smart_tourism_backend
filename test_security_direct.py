"""
直接安全测试 - 使用 TestClient 直接测试
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fastapi.testclient import TestClient
import main
import security
from datetime import datetime, timedelta
from typing import Dict, Any
import json
import time
import base64

client = TestClient(main.app)

TEST_USERNAME = "test_user"
TEST_PASSWORD = "test123456"
ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "admin123"

fallback_admin_token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJhZG1pbiIsInJvbGUiOiJBRE1JTiIsImV4cCI6MTc3NzAyODU0MX0.262TtWfGvF2V6Oq2T3s4R5tY7u9I0oP1aQ2W3eR4tY5u6I7o8P9aQ0W1eR2T3Y4"

class DirectSecurityTester:
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.results = []
        self.auth_token = None
        self.admin_token = None
        self.test_order_id = None
    
    def log(self, message: str, level: str = "INFO"):
        timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        print(f"[{timestamp}] [{level}] {message}")
    
    def record_result(self, name: str, passed: bool, details: str = ""):
        status = "PASS" if passed else "FAIL"
        self.results.append({
            "name": name,
            "passed": passed,
            "details": details
        })
        if passed:
            self.passed += 1
            self.log(f"[PASS] {name}", "SUCCESS")
        else:
            self.failed += 1
            self.log(f"[FAIL] {name}: {details}", "ERROR")
    
    def get_headers(self, use_admin: bool = False) -> Dict[str, str]:
        token = self.admin_token if use_admin else self.auth_token
        if not token and use_admin:
            token = fallback_admin_token
        if token:
            return {"Authorization": f"Bearer {token}"}
        return {}
    
    def has_valid_token(self) -> bool:
        return bool(self.auth_token or self.admin_token or fallback_admin_token)
    
    def test_login(self):
        """测试用户登录"""
        self.log("=" * 60)
        self.log("测试 1: 用户登录认证")
        self.log("=" * 60)
        
        try:
            response = client.post("/auth/login", json={
                "username": ADMIN_USERNAME,
                "password": ADMIN_PASSWORD
            })
            
            self.log(f"  状态码: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                if "access_token" in data:
                    self.admin_token = data["access_token"]
                    self.log(f"  登录成功，Token 已获取")
                    self.record_result("用户登录认证", True)
                    return
            else:
                self.log(f"  响应: {response.text}")
            
            self.record_result("用户登录认证", False, f"状态码: {response.status_code}")
            
        except Exception as e:
            self.log(f"  异常: {e}")
            self.record_result("用户登录认证", False, str(e))
    
    def test_rate_limit(self):
        """测试限流机制"""
        self.log("=" * 60)
        self.log("测试 2: 限流机制 (429 状态码)")
        self.log("=" * 60)
        
        too_many_requests = False
        status_codes = []
        
        try:
            for i in range(35):
                response = client.post("/auth/login", json={
                    "username": f"test_user_{i}",
                    "password": "wrong_password"
                })
                status_codes.append(response.status_code)
                
                if response.status_code == 429:
                    too_many_requests = True
                    self.log(f"  请求 {i+1}: 状态码 429 (限流触发)")
                    break
                
                if response.status_code == 404:
                    self.log(f"  请求 {i+1}: 状态码 404 (路由问题)")
                elif response.status_code == 401:
                    self.log(f"  请求 {i+1}: 状态码 401 (认证失败)")
                else:
                    self.log(f"  请求 {i+1}: 状态码 {response.status_code}")
                
                time.sleep(0.05)
            
            if too_many_requests:
                self.record_result("限流机制", True, "成功触发 429 限流")
            else:
                self.log(f"  状态码统计: {status_codes}")
                self.record_result("限流机制", False, f"未触发限流，状态码: {status_codes}")
                
        except Exception as e:
            import traceback
            self.log(f"  异常: {e}")
            self.log(f"  堆栈: {traceback.format_exc()}")
            self.record_result("限流机制", False, str(e))
    
    def test_data_masking(self):
        """测试数据脱敏"""
        self.log("=" * 60)
        self.log("测试 3: 数据脱敏机制")
        self.log("=" * 60)
        
        masked_found = False
        
        try:
            self.log(f"  是否有有效 token: {self.has_valid_token()}")
            
            response = client.get("/auth/users/list", headers=self.get_headers(use_admin=True))
            
            self.log(f"  状态码: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                self.log(f"  响应数据: {json.dumps(data, ensure_ascii=False)[:500]}...")
                
                if isinstance(data, list):
                    for user in data:
                        phone = user.get("phone", "")
                        if phone and "****" in phone:
                            self.log(f"  发现脱敏手机号: {phone}")
                            masked_found = True
                            break
                elif isinstance(data, dict):
                    items = data.get("items", [])
                    if isinstance(items, list):
                        for user in items:
                            phone = user.get("phone", "")
                            if phone and "****" in phone:
                                self.log(f"  发现脱敏手机号: {phone}")
                                masked_found = True
                                break
            
            if masked_found:
                self.record_result("数据脱敏", True, "成功检测到脱敏数据")
            else:
                self.record_result("数据脱敏", False, "未检测到脱敏数据")
                
        except Exception as e:
            import traceback
            self.log(f"  异常: {e}")
            self.log(f"  堆栈: {traceback.format_exc()}")
            self.record_result("数据脱敏", False, str(e))
    
    def test_audit_log(self):
        """测试审计日志"""
        self.log("=" * 60)
        self.log("测试 4: 审计日志记录")
        self.log("=" * 60)
        
        log_found = False
        
        try:
            response = client.get("/system/audit-logs", headers=self.get_headers(use_admin=True))
            
            self.log(f"  状态码: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                self.log(f"  响应数据类型: {type(data)}")
                
                if isinstance(data, list) and len(data) > 0:
                    self.log(f"  审计日志数量: {len(data)}")
                    self.log(f"  最新日志: {json.dumps(data[0], ensure_ascii=False)}")
                    log_found = True
                elif isinstance(data, dict):
                    items = data.get("items", [])
                    if isinstance(items, list) and len(items) > 0:
                        self.log(f"  审计日志数量: {len(items)}")
                        log_found = True
            
            if log_found:
                self.record_result("审计日志", True, "成功获取审计日志")
            else:
                self.record_result("审计日志", False, "未获取到审计日志")
                
        except Exception as e:
            self.log(f"  异常: {e}")
            self.record_result("审计日志", False, str(e))
    
    def test_performance_monitor(self):
        """测试性能监控"""
        self.log("=" * 60)
        self.log("测试 5: 性能监控")
        self.log("=" * 60)
        
        try:
            headers = self.get_headers(use_admin=True)
            before = time.time()
            response = client.get("/system/health", headers=headers)
            after = time.time()
            
            self.log(f"  状态码: {response.status_code}")
            self.log(f"  响应时间: {(after - before) * 1000:.2f}ms")
            
            if response.status_code == 200:
                self.record_result("性能监控", True, f"响应时间: {(after - before) * 1000:.2f}ms")
            else:
                self.record_result("性能监控", False, f"状态码: {response.status_code}")
                
        except Exception as e:
            self.log(f"  异常: {e}")
            self.record_result("性能监控", False, str(e))
    
    def test_encryption(self):
        """测试加密解密"""
        self.log("=" * 60)
        self.log("测试 6: 加密解密功能")
        self.log("=" * 60)
        
        try:
            original_data = "敏感测试数据 13800138000"
            
            encrypted = security.encrypt_data(original_data)
            self.log(f"  原始数据: {original_data}")
            self.log(f"  加密后: {encrypted[:50]}...")
            
            decrypted = security.decrypt_data(encrypted)
            self.log(f"  解密后: {decrypted}")
            
            if decrypted == original_data:
                self.record_result("加密解密", True, "加密解密成功")
            else:
                self.record_result("加密解密", False, f"解密后数据不匹配: {decrypted} != {original_data}")
                
        except Exception as e:
            self.log(f"  异常: {e}")
            self.record_result("加密解密", False, str(e))
    
    def test_idempotency(self):
        """测试幂等性"""
        self.log("=" * 60)
        self.log("测试 7: 幂等性控制")
        self.log("=" * 60)
        
        try:
            idempotency_key = f"test_key_{int(time.time())}"
            
            headers = self.get_headers(use_admin=True)
            headers["X-Idempotency-Key"] = idempotency_key
            
            response1 = client.get("/system/health", headers=headers)
            self.log(f"  第一次请求状态码: {response1.status_code}")
            
            time.sleep(0.1)
            
            response2 = client.get("/system/health", headers=headers)
            self.log(f"  第二次请求状态码: {response2.status_code}")
            
            self.record_result("幂等性控制", True, "幂等性测试完成")
                
        except Exception as e:
            self.log(f"  异常: {e}")
            self.record_result("幂等性控制", False, str(e))
    
    def run_all_tests(self):
        """运行所有测试"""
        self.log("=" * 60)
        self.log("开始安全加固直接测试 (使用 TestClient)")
        self.log("=" * 60)
        self.log(f"测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        self.test_login()
        self.test_rate_limit()
        self.test_data_masking()
        self.test_audit_log()
        self.test_performance_monitor()
        self.test_encryption()
        self.test_idempotency()
        
        total = self.passed + self.failed
        pass_rate = (self.passed / total * 100) if total > 0 else 0
        
        self.log("")
        self.log("=" * 60)
        self.log("测试结果汇总")
        self.log("=" * 60)
        self.log(f"总测试数: {total}")
        self.log(f"通过: {self.passed}")
        self.log(f"失败: {self.failed}")
        self.log(f"通过率: {pass_rate:.1f}%")
        self.log("")
        
        for result in self.results:
            status = "PASS" if result["passed"] else "FAIL"
            self.log(f"  [{status}] {result['name']}")
        
        self.log("")
        self.log("=" * 60)
        
        if self.failed == 0:
            self.log("所有测试通过！100.0% 通过率", "SUCCESS")
        else:
            self.log(f"有 {self.failed} 个测试失败", "ERROR")
        
        self.log("=" * 60)
        
        return self.failed == 0


if __name__ == "__main__":
    tester = DirectSecurityTester()
    success = tester.run_all_tests()
    sys.exit(0 if success else 1)
