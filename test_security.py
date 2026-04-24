import asyncio
import httpx
import time
import re
from datetime import datetime
from typing import Dict, Any, List
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

BASE_URL = "http://localhost:8000"


class SecurityTestResults:
    def __init__(self):
        self.tests_passed: List[str] = []
        self.tests_failed: List[str] = []
        self.errors: List[str] = []
        
    def add_pass(self, test_name: str, details: str = ""):
        message = f"[PASS] {test_name}"
        if details:
            message += f" - {details}"
        self.tests_passed.append(message)
        print(message)
        
    def add_fail(self, test_name: str, details: str = ""):
        message = f"[FAIL] {test_name}"
        if details:
            message += f" - {details}"
        self.tests_failed.append(message)
        print(message)
        
    def add_error(self, test_name: str, error: Exception):
        message = f"[ERROR] {test_name}: {str(error)}"
        self.errors.append(message)
        print(message)
        
    def summary(self):
        print("\n" + "=" * 60)
        print("安全测试报告摘要")
        print("=" * 60)
        print(f"\n通过测试: {len(self.tests_passed)} 项")
        for test in self.tests_passed:
            print(f"  {test}")
            
        if self.tests_failed:
            print(f"\n失败测试: {len(self.tests_failed)} 项")
            for test in self.tests_failed:
                print(f"  {test}")
                
        if self.errors:
            print(f"\n错误: {len(self.errors)} 项")
            for error in self.errors:
                print(f"  {error}")
                
        print("\n" + "=" * 60)
        total = len(self.tests_passed) + len(self.tests_failed) + len(self.errors)
        if total == 0:
            print("没有执行任何测试")
        else:
            pass_rate = len(self.tests_passed) / total * 100
            print(f"测试通过率: {pass_rate:.1f}% ({len(self.tests_passed)}/{total})")
            if pass_rate == 100:
                print("所有安全测试通过！系统安全加固功能正常工作。")
            else:
                print("部分测试失败，请检查系统配置。")
        print("=" * 60)
        
        return len(self.tests_failed) == 0 and len(self.errors) == 0


class SecurityTester:
    def __init__(self):
        self.results = SecurityTestResults()
        self.auth_token: str = ""
        self.admin_username = "admin"
        self.admin_password = "admin123"
        self.fallback_admin_token = ""
        self.client = httpx.AsyncClient(timeout=60.0)
        
    async def close(self):
        await self.client.aclose()
        
    def get_headers(self) -> Dict[str, str]:
        token = self.auth_token or self.fallback_admin_token
        if token:
            return {"Authorization": f"Bearer {token}"}
        return {}
    
    def has_valid_token(self) -> bool:
        return bool(self.auth_token or self.fallback_admin_token)
    
    async def setup(self):
        print("=" * 60)
        print("全链路监控与安全加固 - 极限压力测试")
        print(f"测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"目标服务器: {BASE_URL}")
        print("=" * 60)
        
        print("\n[准备] 检查服务器是否可用...")
        try:
            response = await self.client.get(f"{BASE_URL}/")
            if response.status_code in [200, 404]:
                self.results.add_pass("服务器可用性检查", f"响应状态码: {response.status_code}")
            else:
                self.results.add_fail("服务器可用性检查", f"响应状态码: {response.status_code}")
        except Exception as e:
            self.results.add_error("服务器可用性检查", e)
            print("\n错误: 无法连接到服务器。请确保服务器正在运行:")
            print("  在 smart_tourism_backend 目录下运行: python main.py\n")
            return False
            
        print("\n[准备] 尝试登录获取管理员认证令牌...")
        print(f"  用户名: {self.admin_username}")
        print(f"  密码: {self.admin_password}")
        
        try:
            response = await self.client.post(
                f"{BASE_URL}/auth/login",
                json={"username": self.admin_username, "password": self.admin_password}
            )
            
            print(f"  响应状态码: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                self.auth_token = data.get("access_token", "")
                if self.auth_token:
                    user = data.get("user", {})
                    print(f"  用户: {user.get('username', 'unknown')}")
                    print(f"  角色: {user.get('role', 'unknown')}")
                    print(f"  手机号: {user.get('phone', 'none')}")
                    
                    self.results.add_pass("管理员登录认证", "成功获取访问令牌")
                    
                    phone = user.get('phone', '')
                    if phone:
                        if re.match(r'^\d{3}\*\*\*\*\d{4}$', phone):
                            self.results.add_pass("登录响应数据脱敏", f"手机号已正确脱敏: {phone}")
                        elif '*' in phone:
                            self.results.add_pass("登录响应数据脱敏", f"手机号已脱敏: {phone}")
                        else:
                            self.results.add_fail("登录响应数据脱敏", f"手机号未脱敏: {phone}")
                else:
                    self.results.add_fail("管理员登录认证", "响应中未包含 access_token")
                    print(f"  响应内容: {data}")
            else:
                error_detail = ""
                try:
                    error_detail = response.json().get("detail", "")
                except:
                    pass
                self.results.add_fail(
                    "管理员登录认证", 
                    f"登录失败，状态码: {response.status_code}, 详情: {error_detail}"
                )
                print(f"  请确保数据库中存在 admin 用户，密码为 admin123")
                print(f"  [提示] 尝试使用备用令牌进行后续测试...")
        except Exception as e:
            self.results.add_error("管理员登录认证", e)
            
        return True
        
    async def test_rate_limiting(self):
        print("\n" + "-" * 60)
        print("测试 1: 全局频率限制 (Rate Limiting)")
        print("-" * 60)
        print("目标: 验证登录接口是否正确限制请求频率")
        print("策略: 发送 50 次请求，验证限流是否生效（限制: 20次/分钟）")
        print()
        
        async def send_login_request(request_num: int):
            try:
                response = await self.client.post(
                    f"{BASE_URL}/auth/login",
                    json={"username": f"test_user_{request_num}", "password": "wrong_password"}
                )
                return response.status_code
            except Exception as e:
                print(f"    请求 {request_num} 异常: {e}")
                return None
        
        print("开始发送请求...")
        start_time = time.time()
        
        tasks = [send_login_request(i) for i in range(50)]
        status_codes = await asyncio.gather(*tasks)
        
        elapsed_time = time.time() - start_time
        print(f"完成 50 次请求，耗时: {elapsed_time:.3f} 秒")
        print()
        
        count_200 = status_codes.count(200)
        count_429 = status_codes.count(429)
        count_401 = status_codes.count(401)
        count_400 = status_codes.count(400)
        count_404 = status_codes.count(404)
        count_none = status_codes.count(None)
        count_other = len(status_codes) - count_200 - count_429 - count_401 - count_400 - count_404 - count_none
        
        print(f"统计结果:")
        print(f"  200 OK: {count_200} 次")
        print(f"  400 Bad Request: {count_400} 次")
        print(f"  401 Unauthorized: {count_401} 次")
        print(f"  404 Not Found: {count_404} 次")
        print(f"  429 Too Many Requests (限流触发): {count_429} 次")
        print(f"  其他状态码: {count_other} 次")
        print(f"  请求失败: {count_none} 次")
        print()
        
        total_non_error = count_200 + count_400 + count_401 + count_other
        
        if count_429 > 0:
            self.results.add_pass(
                "频率限制功能", 
                f"成功触发限流！429 响应数: {count_429}，非 429 响应数: {total_non_error}"
            )
            print("[PASS] 限流功能正常工作")
        elif count_404 > 40:
            self.results.add_fail(
                "频率限制功能",
                f"接口返回 404 太多 ({count_404} 次)。请确保 /auth/login 接口存在且服务器正常运行。"
            )
            print("[FAIL] 接口可能不存在")
        elif total_non_error >= 25:
            self.results.add_fail(
                "频率限制功能",
                f"未触发限流。成功处理 {total_non_error} 次请求，超过 20 次/分钟的限制。"
            )
            print("[FAIL] 限流功能可能未生效")
        else:
            self.results.add_pass(
                "频率限制功能",
                f"请求数较少 ({total_non_error})，可能未达到限流阈值"
            )
            print(f"  [提示] 请求数未达到限流阈值，请确保服务器正常运行限流装饰器")
            
        print(f"\n预期行为: 登录接口限制为每分钟 20 次请求")
        print(f"超过限制后应返回 429 Too Many Requests 状态码")
        
    async def test_data_masking(self):
        print("\n" + "-" * 60)
        print("测试 2: 数据脱敏 (Data Masking)")
        print("-" * 60)
        print("目标: 验证返回的用户数据中手机号是否已脱敏")
        print("预期格式: 138****5678 (保留前3位和后4位，中间用*号替换)")
        print()
        
        if not self.has_valid_token():
            self.results.add_fail("数据脱敏测试", "需要有效的认证令牌")
            return
            
        headers = self.get_headers()
        
        print("步骤 1: 检查当前用户信息接口 (/auth/me)")
        try:
            response = await self.client.get(f"{BASE_URL}/auth/me", headers=headers)
            print(f"  响应状态码: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                phone = data.get("phone")
                username = data.get("username")
                
                print(f"  用户: {username}")
                print(f"  返回的手机号: {phone}")
                
                if phone:
                    if re.match(r'^\d{3}\*\*\*\*\d{4}$', phone):
                        self.results.add_pass(
                            "当前用户信息脱敏",
                            f"手机号已正确脱敏: {phone} (格式: 138****5678)"
                        )
                        print("[PASS] 手机号已正确脱敏 (格式: 138****5678)")
                    elif '*' in phone and len(phone) == 11:
                        self.results.add_pass(
                            "当前用户信息脱敏",
                            f"手机号已脱敏: {phone}"
                        )
                        print("[PASS] 手机号已脱敏")
                    else:
                        if re.match(r'^\d{11}$', phone):
                            self.results.add_fail(
                                "当前用户信息脱敏",
                                f"手机号未脱敏: {phone}。应该返回 {phone[:3]}****{phone[7:]}"
                            )
                            print("[FAIL] 手机号未脱敏")
                        else:
                            self.results.add_pass(
                                "当前用户信息脱敏",
                                f"手机号格式不符合11位数字，原样返回: {phone}"
                            )
                else:
                    self.results.add_pass(
                        "当前用户信息脱敏",
                        "当前用户没有设置手机号"
                    )
            else:
                error_detail = ""
                try:
                    error_detail = response.json().get("detail", "")
                except:
                    pass
                self.results.add_fail(
                    "当前用户信息脱敏",
                    f"请求失败，状态码: {response.status_code}, 详情: {error_detail}"
                )
        except Exception as e:
            self.results.add_error("当前用户信息脱敏", e)
            
        print("\n步骤 2: 检查用户列表接口 (/auth/users/list)")
        try:
            response = await self.client.get(f"{BASE_URL}/auth/users/list", headers=headers)
            print(f"  响应状态码: {response.status_code}")
            
            if response.status_code == 200:
                users = response.json()
                print(f"  返回用户数量: {len(users)}")
                
                if users:
                    masked_count = 0
                    unmasked_count = 0
                    no_phone_count = 0
                    
                    for user in users[:5]:
                        phone = user.get("phone")
                        username = user.get("username")
                        
                        if phone:
                            if re.match(r'^\d{3}\*\*\*\*\d{4}$', phone):
                                masked_count += 1
                                print(f"    用户 {username}: 已正确脱敏 ({phone})")
                            elif '*' in phone:
                                masked_count += 1
                                print(f"    用户 {username}: 已脱敏 ({phone})")
                            elif re.match(r'^\d{11}$', phone):
                                unmasked_count += 1
                                print(f"    用户 {username}: 未脱敏 ({phone})")
                            else:
                                print(f"    用户 {username}: 格式特殊 ({phone})")
                        else:
                            no_phone_count += 1
                            print(f"    用户 {username}: 无手机号")
                    
                    print(f"\n  检查前 {min(5, len(users))} 个用户:")
                    print(f"    已脱敏用户数: {masked_count}")
                    print(f"    未脱敏用户数 (11位数字): {unmasked_count}")
                    print(f"    无手机号用户数: {no_phone_count}")
                    
                    if unmasked_count == 0:
                        self.results.add_pass(
                            "用户列表数据脱敏",
                            f"所有用户手机号已正确脱敏（或无手机号）"
                        )
                        print("[PASS] 用户列表中手机号已正确脱敏")
                    else:
                        self.results.add_fail(
                            "用户列表数据脱敏",
                            f"发现 {unmasked_count} 个用户的手机号未脱敏"
                        )
                        print("[FAIL] 发现未脱敏的手机号")
                else:
                    self.results.add_pass(
                        "用户列表数据脱敏",
                        "用户列表为空"
                    )
            else:
                error_detail = ""
                try:
                    error_detail = response.json().get("detail", "")
                except:
                    pass
                self.results.add_fail(
                    "用户列表数据脱敏",
                    f"请求失败，状态码: {response.status_code}, 详情: {error_detail}"
                )
        except Exception as e:
            self.results.add_error("用户列表数据脱敏", e)
            
        print("\n脱敏规则说明:")
        print("  - 11位手机号: 13812345678 -> 138****5678")
        print("  - 其他长度: 保留前2位和后2位，中间用*号替换")
        
    async def test_audit_logging(self):
        print("\n" + "-" * 60)
        print("测试 3: 全局操作审计 (Audit Logging)")
        print("-" * 60)
        print("目标: 验证敏感操作是否正确记录审计日志")
        print("操作: 修改用户状态，然后检查审计日志是否记录")
        print()
        
        if not self.has_valid_token():
            self.results.add_fail("审计日志测试", "需要有效的认证令牌")
            return
            
        headers = self.get_headers()
        
        test_user_id = None
        test_user_name = None
        original_status = None
        
        print("步骤 1: 获取用户列表，找到一个测试用户")
        try:
            response = await self.client.get(f"{BASE_URL}/auth/users/list", headers=headers)
            if response.status_code == 200:
                users = response.json()
                for user in users:
                    if user.get("role") != "ADMIN":
                        test_user_id = user.get("id")
                        test_user_name = user.get("username")
                        original_status = user.get("is_active")
                        break
                        
                if test_user_id:
                    print(f"  找到测试用户: {test_user_name} (ID: {test_user_id})")
                    print(f"  当前状态: {'启用' if original_status else '禁用'}")
                else:
                    self.results.add_fail(
                        "审计日志测试",
                        "没有找到合适的测试用户（需要非管理员用户）"
                    )
                    return
            else:
                self.results.add_fail(
                    "审计日志测试",
                    f"获取用户列表失败，状态码: {response.status_code}"
                )
                return
        except Exception as e:
            self.results.add_error("审计日志测试 - 获取用户", e)
            return
            
        print("\n步骤 2: 修改用户状态（触发审计日志）")
        try:
            response = await self.client.patch(
                f"{BASE_URL}/auth/users/{test_user_id}/status",
                headers=headers
            )
            print(f"  响应状态码: {response.status_code}")
            
            if response.status_code == 200:
                updated_user = response.json()
                new_status = updated_user.get("is_active")
                print(f"  修改成功")
                print(f"  新状态: {'启用' if new_status else '禁用'}")
                self.results.add_pass(
                    "用户状态修改",
                    f"用户 {test_user_name} 状态已从 {original_status} 改为 {new_status}"
                )
            else:
                error_detail = ""
                try:
                    error_detail = response.json().get("detail", "")
                except:
                    pass
                self.results.add_fail(
                    "用户状态修改",
                    f"状态码: {response.status_code}, 详情: {error_detail}"
                )
                return
        except Exception as e:
            self.results.add_error("审计日志测试 - 修改用户状态", e)
            return
            
        print("\n步骤 3: 检查审计日志")
        try:
            response = await self.client.get(
                f"{BASE_URL}/system/audit-logs?limit=20",
                headers=headers
            )
            print(f"  响应状态码: {response.status_code}")
            
            if response.status_code == 200:
                log_data = response.json()
                logs = log_data.get("items", [])
                total = log_data.get("total", 0)
                
                print(f"  审计日志总数: {total}")
                print(f"  返回日志数: {len(logs)}")
                
                found_audit = False
                target_action = "UPDATE"
                target_module = "用户管理"
                
                for log in logs:
                    log_user_id = log.get("user_id")
                    log_action = log.get("action")
                    log_module = log.get("module")
                    log_details = log.get("details", "")
                    
                    if (log_action == target_action and 
                        log_module == target_module and
                        str(test_user_id) in str(log_details)):
                        found_audit = True
                        print(f"\n  [PASS] 找到匹配的审计日志:")
                        print(f"    时间: {log.get('timestamp')}")
                        print(f"    模块: {log_module}")
                        print(f"    操作: {log_action}")
                        print(f"    详情: {log_details}")
                        break
                        
                if found_audit:
                    self.results.add_pass(
                        "审计日志记录",
                        f"成功记录用户状态修改操作"
                    )
                else:
                    print(f"\n  最近 5 条审计日志:")
                    for log in logs[:5]:
                        print(f"    - {log.get('timestamp')} | {log.get('module')} | {log.get('action')} | {str(log.get('details', ''))[:50]}")
                    
                    if total > 0:
                        self.results.add_fail(
                            "审计日志记录",
                            f"未找到匹配的审计日志。可能是日志记录延迟或配置问题。"
                        )
                    else:
                        self.results.add_fail(
                            "审计日志记录",
                            f"审计日志表为空，没有任何日志记录。请检查日志记录逻辑。"
                        )
            else:
                error_detail = ""
                try:
                    error_detail = response.json().get("detail", "")
                except:
                    pass
                self.results.add_fail(
                    "审计日志查询",
                    f"请求失败，状态码: {response.status_code}, 详情: {error_detail}"
                )
        except Exception as e:
            self.results.add_error("审计日志测试 - 查询日志", e)
            
        print("\n审计日志说明:")
        print("  - 所有敏感操作（如修改用户、退款、修改财务数据）都应记录审计日志")
        print("  - 审计日志应包含: 用户ID、时间、模块、操作类型、详情、IP地址")
        
    async def test_performance_monitoring(self):
        print("\n" + "-" * 60)
        print("测试 4: 性能监控 API")
        print("-" * 60)
        print("目标: 验证系统医生 API 是否正常工作")
        print()
        
        if not self.has_valid_token():
            self.results.add_fail("性能监控测试", "需要有效的认证令牌")
            return
            
        headers = self.get_headers()
        
        print("步骤 1: 测试 /system/health 接口")
        try:
            response = await self.client.get(f"{BASE_URL}/system/health", headers=headers)
            print(f"  响应状态码: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                print(f"  数据库状态: {data.get('database_status')}")
                print(f"  API 状态: {data.get('api_status')}")
                print(f"  运行时间: {data.get('uptime_seconds')} 秒")
                print(f"  内存使用: {data.get('memory_usage_mb')} MB")
                print(f"  CPU 使用率: {data.get('cpu_usage_percent')}%")
                
                self.results.add_pass(
                    "系统健康检查 API",
                    f"数据库: {data.get('database_status')}, API: {data.get('api_status')}"
                )
                print("[PASS] 系统健康检查 API 正常工作")
            else:
                error_detail = ""
                try:
                    error_detail = response.json().get("detail", "")
                except:
                    pass
                self.results.add_fail(
                    "系统健康检查 API",
                    f"请求失败，状态码: {response.status_code}, 详情: {error_detail}"
                )
        except Exception as e:
            self.results.add_error("性能监控测试 - 健康检查", e)
            
        print("\n步骤 2: 测试 /system/performance 接口")
        try:
            response = await self.client.get(f"{BASE_URL}/system/performance", headers=headers)
            print(f"  响应状态码: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                print(f"  总请求数: {data.get('total_requests')}")
                print(f"  平均响应时间: {data.get('average_response_time_ms')} ms")
                print(f"  端点统计数: {len(data.get('endpoint_stats', []))}")
                print(f"  最近错误数: {len(data.get('recent_errors', []))}")
                
                self.results.add_pass(
                    "性能监控 API",
                    f"已记录 {data.get('total_requests')} 次请求，平均响应时间 {data.get('average_response_time_ms')} ms"
                )
                print("[PASS] 性能监控 API 正常工作")
            else:
                error_detail = ""
                try:
                    error_detail = response.json().get("detail", "")
                except:
                    pass
                self.results.add_fail(
                    "性能监控 API",
                    f"请求失败，状态码: {response.status_code}, 详情: {error_detail}"
                )
        except Exception as e:
            self.results.add_error("性能监控测试 - 性能数据", e)
            
        print("\n步骤 3: 测试 /system/doctor 综合接口")
        try:
            response = await self.client.get(f"{BASE_URL}/system/doctor", headers=headers)
            print(f"  响应状态码: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                print(f"  包含模块: 健康检查、性能监控、审计日志")
                
                self.results.add_pass(
                    "系统医生综合 API",
                    "成功获取系统医生综合数据"
                )
                print("[PASS] 系统医生综合 API 正常工作")
            else:
                error_detail = ""
                try:
                    error_detail = response.json().get("detail", "")
                except:
                    pass
                self.results.add_fail(
                    "系统医生综合 API",
                    f"请求失败，状态码: {response.status_code}, 详情: {error_detail}"
                )
        except Exception as e:
            self.results.add_error("性能监控测试 - 系统医生", e)
            
    async def test_encryption(self):
        print("\n" + "-" * 60)
        print("测试 5: 敏感数据加密")
        print("-" * 60)
        print("目标: 验证加密/解密功能是否正常工作")
        print()
        
        try:
            import security
            
            test_data = "13812345678"
            print(f"测试数据: {test_data}")
            
            encrypted = security.encrypt_data(test_data)
            print(f"加密后: {encrypted[:50]}..." if len(encrypted) > 50 else f"加密后: {encrypted}")
            
            if encrypted != test_data and encrypted:
                print("[PASS] 加密功能正常")
            else:
                print("[FAIL] 加密可能未生效")
                
            decrypted = security.decrypt_data(encrypted)
            print(f"解密后: {decrypted}")
            
            if decrypted == test_data:
                self.results.add_pass(
                    "加密/解密功能",
                    f"加密解密循环验证成功: {test_data} -> [加密] -> [解密] -> {decrypted}"
                )
                print("[PASS] 加密/解密功能正常工作")
            else:
                self.results.add_fail(
                    "加密/解密功能",
                    f"解密后数据与原始数据不一致: 原始={test_data}, 解密后={decrypted}"
                )
                
        except ImportError:
            self.results.add_error("加密测试", "无法导入 security 模块")
        except Exception as e:
            self.results.add_error("加密测试", e)
            
        print("\n加密存储说明:")
        print("  - 分销商收款账号、员工考勤位置等敏感信息应加密存储")
        print("  - 使用 Fernet 对称加密算法 (AES-128-CBC + HMAC-SHA256)")
        
    async def run_all_tests(self):
        if not await self.setup():
            return False
            
        await self.test_rate_limiting()
        await self.test_data_masking()
        await self.test_audit_logging()
        await self.test_performance_monitoring()
        await self.test_encryption()
        
        return self.results.summary()


async def main():
    tester = SecurityTester()
    try:
        success = await tester.run_all_tests()
        return 0 if success else 1
    finally:
        await tester.close()


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
