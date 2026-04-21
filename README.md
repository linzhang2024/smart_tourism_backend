# 智慧旅游后端系统

一个功能完整的智慧旅游后端管理系统，包含景点管理、门票购买、流量监控、库存管理等核心功能。

## 项目功能

### 核心功能模块

- **游客管理**：游客信息的增删改查
- **景点管理**：景点信息维护，支持库存管理
- **门票管理**：门票购买、订单管理
- **流量监控**：实时监控景区人流量，智能分析拥堵状况
- **库存预警**：库存不足时自动预警
- **支付系统**：支持门票在线支付，库存原子扣减
- **健康监控**：系统健康状态检查
- **数据分析**：流量序列分析，支持可视化展示

### 特色功能

- **5秒自动刷新**：实时流量数据自动更新
- **智能拥堵分析**：根据人流量自动判断拥堵等级（舒适/正常/拥挤）
- **流量趋势预测**：智能分析流量变化趋势
- **缓存机制**：景点信息缓存，提高访问速度
- **日志系统**：结构化日志记录，便于问题排查
- **API 鉴权**：关键接口 API Key 校验，保障系统安全

**本地运行**
pip install -r requirements.txt
python main.py

### 访问地址
- 主页面（流量监控看板）： http://localhost:8000/
- API 文档： http://localhost:8000/docs
- 备选文档： http://localhost:8000/redoc
  
### API 鉴权

## 技术栈

| 技术 | 版本 | 用途 |
|------|------|------|
| Python | 3.10+ | 核心编程语言 |
| FastAPI | 0.100+ | Web 框架，高性能异步 API |
| SQLAlchemy | 2.0+ | ORM 数据库框架 |
| Pydantic | 2.0+ | 数据验证和序列化 |
| SQLite | 内置 | 轻量级数据库 |
| ECharts | 5.4.3 | 前端数据可视化图表库 |
| Uvicorn | 0.22+ | ASGI 服务器 |
| Requests | 2.28+ | HTTP 客户端 |

## 项目结构

```
smart_tourism_backend/
├── main.py                 # 主程序入口，API 路由定义
├── models.py               # 数据库模型定义
├── schemas.py              # Pydantic 数据模型
├── database.py             # 数据库连接配置
├── analytics_report.py     # 分析报告生成
├── requirements.txt        # Python 依赖列表
├── Dockerfile              # Docker 镜像构建文件
├── static/
│   └── index.html          # 流量监控前端页面
├── reports/                # 分析报告存储目录
└── smart_tourism.db        # SQLite 数据库文件
```

## 快速开始

### 方式一：本地运行

#### 1. 环境准备

确保已安装 Python 3.10 或更高版本。

#### 2. 安装依赖

```bash
cd smart_tourism_backend
pip install -r requirements.txt
```

#### 3. 启动服务

```bash
python main.py
```

或者使用 uvicorn 直接启动：

```bash
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

#### 4. 访问系统

服务启动后，可通过以下地址访问：

| 地址 | 描述 |
|------|------|
| http://localhost:8000/ | 主页面（流量监控看板） |
| http://localhost:8000/docs | API 文档（Swagger UI） |
| http://localhost:8000/redoc | 备选 API 文档 |

### 方式二：Docker 运行

#### 1. 构建镜像

```bash
cd smart_tourism_backend
docker build -t smart-tourism-backend .
```

#### 2. 运行容器

```bash
docker run -d -p 8000:8000 --name smart-tourism smart-tourism-backend
```

#### 3. 访问系统

与本地运行相同，访问 http://localhost:8000/

## API 接口

### 核心接口列表

#### 游客管理
- `POST /tourists/` - 创建游客
- `GET /tourists/` - 获取游客列表
- `GET /tourists/{tourist_id}` - 获取单个游客详情
- `PUT /tourists/{tourist_id}` - 更新游客信息
- `DELETE /tourists/{tourist_id}` - 删除游客

#### 景点管理
- `POST /scenic-spots/` - 创建景点
- `GET /scenic-spots/` - 获取景点列表
- `GET /scenic-spots/{spot_id}` - 获取单个景点详情
- `PUT /scenic-spots/{spot_id}` - 更新景点信息
- `DELETE /scenic-spots/{spot_id}` - 删除景点

#### 库存管理
- `GET /scenic-spots/low-alert` - 获取库存预警景点列表
- `GET /scenic-spots/{spot_id}/inventory-status` - 获取景点库存状态

#### 门票管理
- `POST /tickets/` - 创建门票
- `GET /tickets/` - 获取门票列表
- `GET /tickets/{ticket_id}` - 获取门票详情
- `PUT /tickets/{ticket_id}` - 更新门票
- `DELETE /tickets/{ticket_id}` - 删除门票

#### 流量监控
- `POST /traffic/record` - 记录流量数据
- `GET /traffic/analytics/{spot_id}` - 获取流量分析数据
- `GET /analytics/traffic-series` - 获取流量序列数据（需 API Key）

#### 门票支付
- `POST /tickets/purchase` - 购买门票
- `GET /tickets/orders/` - 获取订单列表
- `GET /tickets/orders/{order_id}` - 获取订单详情

#### 系统监控
- `GET /system/health` - 系统健康检查（需 API Key）

### API 鉴权

部分敏感接口需要 API Key 校验，当前 API Key 为：`admin123`

需要鉴权的接口：
- `GET /system/health`
- `GET /analytics/traffic-series`

请求时需在 Header 中添加：
```
X-API-Key: admin123
```

若 API Key 无效，返回 403 错误：
```json
{
  "detail": "无效的 API Key"
}
```

## 流量监控看板

系统提供了一个美观的实时流量监控看板，功能包括：

### 核心功能

1. **实时数据展示**
   - 景点名称显示
   - 当前平均入园人数
   - 拥堵等级（舒适/正常/拥挤）
   - 流量趋势（上升/下降/持平）

2. **可视化图表**
   - 实时流量走势图（ECharts 折线图）
   - 最近流量记录表格

3. **自动刷新**
   - 5秒自动刷新数据
   - 手动刷新按钮

### 使用方法

1. 启动服务后访问 http://localhost:8000/
2. 在输入框中输入景点 ID（如：1）
3. 点击"获取实时分析"按钮
4. 系统将显示该景点的实时流量数据

## 数据库模型

### 主要数据表

| 表名 | 描述 |
|------|------|
| tourists | 游客信息表 |
| scenic_spots | 景点信息表（含库存） |
| tickets | 门票信息表 |
| tourist_flows | 流量记录表 |
| ticket_orders | 订单记录表 |

### 核心字段说明

#### scenic_spots（景点表）
- `id`: 景点 ID
- `name`: 景点名称
- `description`: 景点描述
- `location`: 位置
- `rating`: 评分
- `price`: 门票价格
- `total_inventory`: 总库存
- `remained_inventory`: 剩余库存

#### tourist_flows（流量表）
- `id`: 记录 ID
- `scenic_spot_id`: 景点 ID
- `entry_count`: 入园人数
- `record_time`: 记录时间

## 测试数据

项目提供了测试数据生成脚本，可用于快速填充测试数据：

```bash
python create_test_data.py
```

## 开发说明

### 添加新接口

1. 在 `main.py` 中定义路由
2. 在 `schemas.py` 中定义请求/响应模型
3. 在 `models.py` 中定义数据库模型（如需要）

### 修改 API Key

在 `main.py` 中修改 `API_KEY` 常量：
```python
API_KEY = "your_new_key"
```

同时需要修改 `static/index.html` 中的 `API_KEY` 常量：
```javascript
const API_KEY = "your_new_key";
```

## 部署建议

### 生产环境配置

1. **修改 API Key**：使用强密码替代默认的 `admin123`
2. **数据库迁移**：考虑使用 PostgreSQL 或 MySQL 替代 SQLite
3. **HTTPS**：配置 SSL 证书，使用 HTTPS 协议
4. **CORS 配置**：根据实际需求修改允许的域名
5. **日志管理**：配置集中化日志收集
6. **监控告警**：添加系统监控和告警机制

### Docker 部署优化

```dockerfile
# 多阶段构建示例
FROM python:3.10-slim as builder
WORKDIR /app
COPY requirements.txt .
RUN pip install --user --no-cache-dir -r requirements.txt

FROM python:3.10-slim
WORKDIR /app
COPY --from=builder /root/.local /root/.local
COPY . .
ENV PATH=/root/.local/bin:$PATH
EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

## 许可证

MIT License

## 联系方式

如有问题或建议，请提交 Issue 或 Pull Request。
