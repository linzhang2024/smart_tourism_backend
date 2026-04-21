import json
import os
from collections import defaultdict
from typing import Dict, List, Any, Optional


class AnalyticsReport:
    def __init__(self, log_file_path: str = "app.log"):
        self.log_file_path = log_file_path
        self.logs: List[Dict[str, Any]] = []
        self.total_requests: int = 0
        self.paid_orders: int = 0
        self.error_counts: Dict[int, int] = defaultdict(int)
        self.spot_order_counts: Dict[int, int] = defaultdict(int)
        self.spot_names: Dict[int, str] = {}
        
    def load_logs(self) -> bool:
        if not os.path.exists(self.log_file_path):
            return False
        
        try:
            with open(self.log_file_path, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    
                    try:
                        log_entry = json.loads(line)
                        if isinstance(log_entry, dict):
                            self.logs.append(log_entry)
                    except json.JSONDecodeError:
                        continue
            return True
        except (IOError, OSError, Exception):
            return False
    
    def analyze_logs(self):
        for log in self.logs:
            level = log.get("level", "")
            action = log.get("action", "")
            scenic_spot_id = log.get("scenic_spot_id")
            
            if action == "PURCHASE_REQUEST":
                self.total_requests += 1
            
            if action == "PAYMENT_SUCCESS":
                self.paid_orders += 1
                if scenic_spot_id is not None:
                    self.spot_order_counts[scenic_spot_id] += 1
            
            if level == "ERROR" and scenic_spot_id is not None:
                self.error_counts[scenic_spot_id] += 1
    
    def get_success_rate(self) -> float:
        if self.total_requests == 0:
            return 0.0
        return round(self.paid_orders / self.total_requests * 100, 2)
    
    def get_error_frequency(self) -> Dict[int, int]:
        return dict(self.error_counts)
    
    def get_top_spots(self) -> List[Dict[str, Any]]:
        sorted_spots = sorted(
            self.spot_order_counts.items(),
            key=lambda x: x[1],
            reverse=True
        )
        
        result = []
        for spot_id, count in sorted_spots:
            result.append({
                "scenic_spot_id": spot_id,
                "order_count": count
            })
        
        return result
    
    def generate_report(self) -> Dict[str, Any]:
        logs_loaded = self.load_logs()
        
        if not logs_loaded:
            return {
                "status": "error",
                "message": "日志文件不存在或无法读取",
                "data": None
            }
        
        if not self.logs:
            return {
                "status": "warning",
                "message": "日志文件中没有有效的JSON日志记录",
                "data": {
                    "success_rate": 0.0,
                    "total_requests": 0,
                    "paid_orders": 0,
                    "error_frequency": {},
                    "top_spots": []
                }
            }
        
        self.analyze_logs()
        
        return {
            "status": "success",
            "message": "分析完成",
            "data": {
                "success_rate": self.get_success_rate(),
                "total_requests": self.total_requests,
                "paid_orders": self.paid_orders,
                "error_frequency": self.get_error_frequency(),
                "top_spots": self.get_top_spots()
            }
        }


def get_analytics_report(log_file_path: str = "app.log") -> Dict[str, Any]:
    analyzer = AnalyticsReport(log_file_path)
    return analyzer.generate_report()


if __name__ == "__main__":
    report = get_analytics_report()
    print(json.dumps(report, ensure_ascii=False, indent=2))
