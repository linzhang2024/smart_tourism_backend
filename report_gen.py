import sys
import os
import json
from datetime import datetime
from typing import List, Dict, Any, Optional

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    import httpx
    HAS_HTTPX = True
except ImportError:
    HAS_HTTPX = False

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import models
from database import Base, SQLALCHEMY_DATABASE_URL

TEST_DATABASE_URL = "sqlite:///:memory:"
API_CHECK_URL = "http://127.0.0.1:8000/docs"
LOW_ALERT_API_URL = "http://127.0.0.1:8000/scenic-spots/low-alert"


def generate_progress_bar(ratio: float, total_blocks: int = 10) -> str:
    filled_blocks = int(round(ratio * total_blocks))
    empty_blocks = total_blocks - filled_blocks
    filled_char = "="
    empty_char = "-"
    return f"[{filled_char * filled_blocks}{empty_char * empty_blocks}]"


def check_api_available() -> bool:
    if not HAS_HTTPX:
        return False
    
    try:
        with httpx.Client(timeout=2.0) as client:
            response = client.get(API_CHECK_URL)
            return response.status_code == 200
    except Exception:
        return False


def get_low_inventory_from_api() -> Optional[List[Dict[str, Any]]]:
    if not HAS_HTTPX:
        return None
    
    try:
        with httpx.Client(timeout=5.0) as client:
            response = client.get(LOW_ALERT_API_URL)
            if response.status_code == 200:
                return response.json()
            else:
                return None
    except Exception:
        return None


def get_reports_dir() -> str:
    script_dir = os.path.dirname(os.path.abspath(__file__))
    reports_dir = os.path.join(script_dir, "reports")
    
    if not os.path.exists(reports_dir):
        os.makedirs(reports_dir)
    
    return reports_dir


class InventoryReportGenerator:
    def __init__(self, db_url: str = SQLALCHEMY_DATABASE_URL):
        self.engine = create_engine(
            db_url,
            connect_args={"check_same_thread": False},
            poolclass=StaticPool if ":memory:" in db_url else None
        )
        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
        
        Base.metadata.create_all(bind=self.engine)
    
    def get_low_inventory_spots(self) -> List[Dict[str, Any]]:
        db = self.SessionLocal()
        try:
            spots = db.query(models.ScenicSpot).all()
            low_inventory_spots = []
            
            for spot in spots:
                if spot.total_inventory == 0:
                    inventory_ratio = 0.0
                else:
                    inventory_ratio = spot.remained_inventory / spot.total_inventory
                
                if inventory_ratio < 0.10:
                    low_inventory_spots.append({
                        "id": spot.id,
                        "name": spot.name,
                        "total_inventory": spot.total_inventory,
                        "remained_inventory": spot.remained_inventory,
                        "inventory_ratio": round(inventory_ratio, 4),
                        "is_low_inventory": True
                    })
            
            return low_inventory_spots
        finally:
            db.close()
    
    def calculate_statistics(self, low_inventory_spots: List[Dict[str, Any]]) -> Dict[str, Any]:
        total_count = len(low_inventory_spots)
        
        if total_count == 0:
            avg_ratio = 0.0
        else:
            total_ratio = sum(spot["inventory_ratio"] for spot in low_inventory_spots)
            avg_ratio = total_ratio / total_count
        
        return {
            "total_count": total_count,
            "avg_inventory_ratio": round(avg_ratio, 4),
            "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "generated_date": datetime.now().strftime("%Y-%m-%d")
        }
    
    def generate_markdown_report(self, low_inventory_spots: List[Dict[str, Any]], 
                                   statistics: Dict[str, Any]) -> str:
        today_date = statistics.get("generated_date", datetime.now().strftime("%Y-%m-%d"))
        
        report_lines = []
        report_lines.append(f"# 智慧旅游库存预警日报")
        report_lines.append(f"")
        report_lines.append(f"**生成日期**: {today_date}")
        report_lines.append(f"**生成时间**: {statistics['generated_at']}")
        report_lines.append(f"")
        report_lines.append(f"## 统计概览")
        report_lines.append(f"")
        report_lines.append(f"| 指标 | 数值 |")
        report_lines.append(f"|------|------|")
        report_lines.append(f"| 预警景点总数 | {statistics['total_count']} 个 |")
        report_lines.append(f"| 平均剩余库存比例 | {statistics['avg_inventory_ratio']:.2%} |")
        report_lines.append(f"")
        
        if statistics['total_count'] > 0:
            report_lines.append(f"## 预警景点详情")
            report_lines.append(f"")
            report_lines.append(f"| 景点ID | 景点名称 | 总库存 | 剩余库存 | 剩余比例 | 进度条 | 状态 |")
            report_lines.append(f"|--------|----------|--------|----------|----------|--------|------|")
            
            sorted_spots = sorted(low_inventory_spots, key=lambda x: x["inventory_ratio"])
            
            for spot in sorted_spots:
                progress_bar = generate_progress_bar(spot["inventory_ratio"])
                status = "[严重预警]" if spot["inventory_ratio"] < 0.05 else "[低库存预警]"
                report_lines.append(
                    f"| {spot['id']} | {spot['name']} | {spot['total_inventory']} | "
                    f"{spot['remained_inventory']} | {spot['inventory_ratio']:.2%} | {progress_bar} | {status} |"
                )
        else:
            report_lines.append(f"## 预警状态")
            report_lines.append(f"")
            report_lines.append(f"**当前所有景点库存充足，无预警景点。**")
            report_lines.append(f"")
        
        report_lines.append(f"")
        report_lines.append(f"---")
        report_lines.append(f"")
        report_lines.append(f"**备注**:")
        report_lines.append(f"- 库存比例低于 10% 时触发预警，低于 5% 时标记为严重预警")
        report_lines.append(f"- 进度条说明: `=` 表示剩余库存，`-` 表示已使用库存")
        report_lines.append(f"- 进度条越短（= 越少），表示库存越紧张")
        report_lines.append(f"")
        
        return "\n".join(report_lines)
    
    def save_report(self, report_content: str) -> str:
        today_date = datetime.now().strftime("%Y-%m-%d")
        filename = f"daily_report_{today_date}.md"
        reports_dir = get_reports_dir()
        filepath = os.path.join(reports_dir, filename)
        
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(report_content)
        
        return filepath
    
    def generate_json_summary(self, low_inventory_spots: List[Dict[str, Any]], 
                               statistics: Dict[str, Any]) -> Dict[str, Any]:
        sorted_spots = sorted(low_inventory_spots, key=lambda x: x["inventory_ratio"])
        
        summary = {
            "report_type": "inventory_alert",
            "generated_at": statistics["generated_at"],
            "generated_date": statistics["generated_date"],
            "summary": {
                "total_alert_spots": statistics["total_count"],
                "avg_inventory_ratio": statistics["avg_inventory_ratio"],
                "avg_inventory_ratio_percent": f"{statistics['avg_inventory_ratio']:.2%}"
            },
            "alert_spots": []
        }
        
        for spot in sorted_spots:
            summary["alert_spots"].append({
                "id": spot["id"],
                "name": spot["name"],
                "total_inventory": spot["total_inventory"],
                "remained_inventory": spot["remained_inventory"],
                "inventory_ratio": spot["inventory_ratio"],
                "inventory_ratio_percent": f"{spot['inventory_ratio']:.2%}",
                "alert_level": "critical" if spot["inventory_ratio"] < 0.05 else "low",
                "progress_bar": generate_progress_bar(spot["inventory_ratio"])
            })
        
        return summary
    
    def save_json_summary(self, json_summary: Dict[str, Any]) -> str:
        today_date = datetime.now().strftime("%Y-%m-%d")
        filename = f"report_summary_{today_date}.json"
        reports_dir = get_reports_dir()
        filepath = os.path.join(reports_dir, filename)
        
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(json_summary, f, ensure_ascii=False, indent=2)
        
        return filepath
    
    def add_test_data(self, test_spots: List[Dict[str, Any]]):
        db = self.SessionLocal()
        try:
            for spot_data in test_spots:
                existing = db.query(models.ScenicSpot).filter(
                    models.ScenicSpot.name == spot_data["name"]
                ).first()
                
                if existing:
                    existing.total_inventory = spot_data["total_inventory"]
                    existing.remained_inventory = spot_data["remained_inventory"]
                else:
                    db_spot = models.ScenicSpot(**spot_data)
                    db.add(db_spot)
            
            db.commit()
        finally:
            db.close()


def get_test_spots() -> List[Dict[str, Any]]:
    return [
        {
            "name": "故宫博物院",
            "description": "中国明清两代的皇家宫殿",
            "location": "北京市东城区",
            "price": 60.0,
            "total_inventory": 100,
            "remained_inventory": 8
        },
        {
            "name": "八达岭长城",
            "description": "中国古代的军事防御工程",
            "location": "北京市延庆区",
            "price": 40.0,
            "total_inventory": 200,
            "remained_inventory": 15
        },
        {
            "name": "颐和园",
            "description": "中国清朝时期皇家园林",
            "location": "北京市海淀区",
            "price": 30.0,
            "total_inventory": 150,
            "remained_inventory": 5
        },
        {
            "name": "天坛公园",
            "description": "明清两代皇帝祭祀皇天、祈五谷丰登的场所",
            "location": "北京市东城区",
            "price": 15.0,
            "total_inventory": 100,
            "remained_inventory": 50
        }
    ]


def main():
    print("=" * 70)
    print("智慧旅游库存预警报告生成器 v2.0")
    print("=" * 70)
    print()
    
    api_available = False
    use_api = False
    
    if HAS_HTTPX:
        print("[检查] 检测后台 API 服务状态...")
        api_available = check_api_available()
        
        if not api_available:
            print("[警告] 检测到后台服务未启动，将切换至离线模拟数据模式")
            print("   提示：如需使用真实数据，请先启动后台服务：python main.py")
            print()
        else:
            print("   API 服务正常运行")
            use_api = True
            print()
    else:
        print("[提示] httpx 模块未安装，将使用离线模拟数据模式")
        print("   安装命令：pip install httpx")
        print()
    
    generator = None
    low_inventory_spots = None
    
    if use_api:
        print("[步骤1] 从 API 获取低库存景点数据...")
        low_inventory_spots = get_low_inventory_from_api()
        
        if low_inventory_spots is None:
            print("   API 调用失败，切换至离线模式...")
            use_api = False
        else:
            print(f"   从 API 找到 {len(low_inventory_spots)} 个预警景点")
            print()
    
    if not use_api:
        print("[步骤1] 使用内存数据库（离线模式）...")
        generator = InventoryReportGenerator(db_url=TEST_DATABASE_URL)
        print("   内存数据库已初始化")
        print()
        
        print("[步骤2] 添加模拟测试数据...")
        test_spots = get_test_spots()
        generator.add_test_data(test_spots)
        print(f"   已添加 {len(test_spots)} 个测试景点数据")
        print()
        
        print("[步骤3] 查询低库存景点...")
        low_inventory_spots = generator.get_low_inventory_spots()
        print(f"   找到 {len(low_inventory_spots)} 个预警景点")
        print()
    
    if generator is None:
        generator = InventoryReportGenerator(db_url=TEST_DATABASE_URL)
    
    print("[步骤4] 计算统计数据...")
    statistics = generator.calculate_statistics(low_inventory_spots)
    print(f"   预警景点总数: {statistics['total_count']}")
    print(f"   平均剩余库存比例: {statistics['avg_inventory_ratio']:.2%}")
    print()
    
    print("[步骤5] 生成 Markdown 报告...")
    report_content = generator.generate_markdown_report(low_inventory_spots, statistics)
    print()
    
    print("[步骤6] 保存 Markdown 报告文件...")
    md_filepath = generator.save_report(report_content)
    print(f"   报告已保存至: {md_filepath}")
    print()
    
    print("[步骤7] 生成 JSON 摘要...")
    json_summary = generator.generate_json_summary(low_inventory_spots, statistics)
    print()
    
    print("[步骤8] 保存 JSON 摘要文件...")
    json_filepath = generator.save_json_summary(json_summary)
    print(f"   JSON 摘要已保存至: {json_filepath}")
    print()
    
    print("=" * 70)
    print("报告生成完成！")
    print("=" * 70)
    print()
    print("报告预览:")
    print("-" * 70)
    print(report_content)
    print("-" * 70)
    print()
    print("JSON 摘要预览:")
    print("-" * 70)
    print(json.dumps(json_summary, ensure_ascii=False, indent=2))
    print("-" * 70)
    print()
    print("使用说明:")
    print("1. 默认自动检测 API 服务状态")
    print("2. API 可用时从 /scenic-spots/low-alert 获取真实数据")
    print("3. API 不可用时使用内存数据库的模拟数据")
    print("4. 报告文件保存在 reports/ 目录下")
    print("5. 进度条说明: [=---------] 中 = 越少表示库存越紧张")


if __name__ == "__main__":
    main()
