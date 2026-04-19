import sys
import os
from datetime import datetime
from typing import List, Dict, Any

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import models
from database import Base, SQLALCHEMY_DATABASE_URL

TEST_DATABASE_URL = "sqlite:///:memory:"


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
            "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
    
    def generate_markdown_report(self, low_inventory_spots: List[Dict[str, Any]], 
                                   statistics: Dict[str, Any]) -> str:
        today_date = datetime.now().strftime("%Y-%m-%d")
        
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
            report_lines.append(f"| 景点ID | 景点名称 | 总库存 | 剩余库存 | 剩余比例 | 状态 |")
            report_lines.append(f"|--------|----------|--------|----------|----------|------|")
            
            for spot in low_inventory_spots:
                status = "[严重预警]" if spot["inventory_ratio"] < 0.05 else "[低库存预警]"
                report_lines.append(
                    f"| {spot['id']} | {spot['name']} | {spot['total_inventory']} | "
                    f"{spot['remained_inventory']} | {spot['inventory_ratio']:.2%} | {status} |"
                )
        else:
            report_lines.append(f"## 预警状态")
            report_lines.append(f"")
            report_lines.append(f"**当前所有景点库存充足，无预警景点。**")
            report_lines.append(f"")
        
        report_lines.append(f"")
        report_lines.append(f"---")
        report_lines.append(f"")
        report_lines.append(f"**备注**: 库存比例低于 10% 时触发预警，低于 5% 时标记为严重预警。")
        report_lines.append(f"")
        
        return "\n".join(report_lines)
    
    def save_report(self, report_content: str) -> str:
        today_date = datetime.now().strftime("%Y-%m-%d")
        filename = f"daily_report_{today_date}.md"
        filepath = os.path.join(os.path.dirname(os.path.abspath(__file__)), filename)
        
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(report_content)
        
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
    print("=" * 60)
    print("智慧旅游库存预警报告生成器")
    print("=" * 60)
    print()
    
    print("[步骤1] 使用内存数据库进行测试...")
    generator = InventoryReportGenerator(db_url=TEST_DATABASE_URL)
    print("   内存数据库已初始化")
    print()
    
    print("[步骤2] 添加测试数据...")
    test_spots = get_test_spots()
    generator.add_test_data(test_spots)
    print(f"   已添加 {len(test_spots)} 个测试景点数据")
    print()
    
    print("[步骤3] 查询低库存景点...")
    low_inventory_spots = generator.get_low_inventory_spots()
    print(f"   找到 {len(low_inventory_spots)} 个预警景点")
    print()
    
    print("[步骤4] 计算统计数据...")
    statistics = generator.calculate_statistics(low_inventory_spots)
    print(f"   预警景点总数: {statistics['total_count']}")
    print(f"   平均剩余库存比例: {statistics['avg_inventory_ratio']:.2%}")
    print()
    
    print("[步骤5] 生成 Markdown 报告...")
    report_content = generator.generate_markdown_report(low_inventory_spots, statistics)
    print()
    
    print("[步骤6] 保存报告文件...")
    filepath = generator.save_report(report_content)
    print(f"   报告已保存至: {filepath}")
    print()
    
    print("=" * 60)
    print("报告生成完成！")
    print("=" * 60)
    print()
    print("报告预览:")
    print("-" * 60)
    print(report_content)
    print("-" * 60)
    print()
    print("使用说明:")
    print("1. 默认使用内存数据库进行测试，不影响现有数据")
    print("2. 若要使用真实数据库，请修改 InventoryReportGenerator 的 db_url 参数")
    print("3. 报告文件已生成在当前目录下")


if __name__ == "__main__":
    main()
