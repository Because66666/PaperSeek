# 学术论文智能检索与分析系统

基于arXiv和豆包AI的自动化论文检索、筛选、分析与报告生成工具。

## 功能特性

- **智能检索**: 从arXiv自动检索相关论文
- **漏斗式筛选**: AI辅助摘要筛选，只保留相关论文
- **自动下载**: 批量下载PDF文件
- **深度分析**: AI阅读全文，提取核心要素
- **报告生成**: 自动生成Excel文献库和Markdown综述报告
- **增量更新**: 支持断点续传和增量更新
- **多主题支持**: 同一论文可在不同研究主题下独立记录，分别评估相关度
- **Token统计**: 自动统计API调用次数和Token使用量

## 项目结构

```
paper_researcher/
├── core/                   # 核心模块
│   ├── config.py          # 配置文件
│   ├── db.py              # 数据库操作
│   ├── searcher.py        # arXiv检索
│   └── analyzer.py        # AI分析
├── utils/                  # 工具模块
│   ├── pdf_handler.py     # PDF下载和解析
│   └── exporter.py        # 报告导出
├── data/                   # 数据存储
│   └── papers.db          # SQLite数据库
├── papers_output/          # 输出目录
│   ├── pdfs/              # 下载的PDF文件
│   ├── *.xlsx             # Excel文献库
│   └── *.md               # Markdown综述报告
├── main.py                 # 主程序入口
├── requirements.txt        # 依赖包
├── .env.example           # 环境变量示例
└── README.md              # 使用说明
```

## 安装

1. 克隆或下载项目

2. 安装依赖
```bash
pip install -r requirements.txt
```

3. 配置环境变量
```bash
cp .env.example .env
# 编辑 .env 文件，填入你的API密钥
```

## 配置

编辑 `.env` 文件：

```env
# 豆包API配置
DOUBAO_API_KEY=your_api_key_here
DOUBAO_BASE_URL=https://ark.cn-beijing.volces.com/api/v3
DOUBAO_MODEL_NAME=doubao-1.5-pro-32k-250115

# 检索配置 - 漏斗式过滤
MAX_CONCURRENT_REQUESTS=20

# 第一层漏斗：检索上限（泛读）
MAX_PAPERS_PER_SEARCH=100

# 第二层漏斗：精读上限（只分析最相关的N篇）
MAX_PAPERS_FOR_ANALYSIS=20

# 相关度分数阈值（低于此分数不进入精读）
RELEVANCE_SCORE_THRESHOLD=60

# 数据存储路径
DATABASE_PATH=data/papers.db
PDF_DOWNLOAD_PATH=papers_output/pdfs
```

## 使用方法

### 漏斗式工作流程

本系统采用**漏斗式过滤**策略：

```
1. AI智能生成关键词: 根据研究主题自动生成英文检索关键词
    ↓
2. 第一层漏斗（泛读）: 检索上限 --max-search 篇
    ↓ AI摘要筛选
3. 第二层漏斗（精读）: 取最相关的 --max-analysis 篇（相关度>--relevance-threshold）
    ↓ PDF下载 + 深度分析
4. 最终报告
```

### 完整流程（检索 → 筛选 → 下载 → 分析 → 导出）

**默认模式（推荐）：AI自动生成关键词**

```bash
# 最简单的用法：只需提供研究主题
python main.py run -t "LoRA改进方法"

# 指定漏斗参数
python main.py run -t "LoRA改进方法" -ms 100 -ma 20

# 中文主题也支持
python main.py run -t "大语言模型微调技术"
```

**高级用法：手动指定关键词**

```bash
# 手动指定关键词（覆盖自动生成）
python main.py run -t "LoRA改进方法" -k "LoRA" -k "Low Rank Adaptation" --auto-keywords=False

# 同时使用自动生成和手动关键词
python main.py run -t "LoRA改进方法" -k "QLoRA" -k "AdaLoRA"
```

参数说明：
- `-t, --topic`: 研究主题（**必需**）
- `-k, --keywords`: 手动指定检索关键词（可选，覆盖自动生成）
- `--auto-keywords`: 使用AI自动生成关键词（默认开启）
- `-ms, --max-search`: 第一层漏斗 - 最大检索论文数（泛读上限，默认100）
- `-ma, --max-analysis`: 第二层漏斗 - 最大精读分析数（默认20）
- `-rt, --relevance-threshold`: 相关度分数阈值（默认60，低于此分数不进入精读）

### 跳过某些步骤

```bash
# 只检索和筛选，不下载分析
python main.py run -t "LoRA改进方法" -k "LoRA" --skip-download --skip-analysis

# 只分析已下载的论文
python main.py run -t "LoRA改进方法" -k "LoRA" --skip-search --skip-screening --skip-download
```

### 增量更新

```bash
# 使用已有会话ID继续处理
python main.py run --session-id 1
```

### 仅导出结果

```bash
python main.py run --session-id 1 --export-only
```

### 查看统计信息

```bash
python main.py stats --session-id 1
```

### 导出指定会话

```bash
python main.py export --session-id 1
```

## 工作流程（漏斗式过滤）

```
┌─────────────────────────────────────────────────────────────┐
│  第一层漏斗（泛读）                                           │
│  ┌─────────────┐    max-search上限（如100篇）                 │
│  │  1. 检索论文  │  ← 从arXiv根据关键词检索                    │
│  └──────┬──────┘                                             │
│         ↓                                                    │
│  ┌─────────────┐                                             │
│  │  2. 摘要筛选  │  ← AI判断论文与主题相关性，给出分数          │
│  └──────┬──────┘                                             │
└─────────┼────────────────────────────────────────────────────┘
          ↓
┌─────────────────────────────────────────────────────────────┐
│  第二层漏斗（精读）                                           │
│  ┌─────────────┐    筛选条件：                               │
│  │  3. 选择论文  │  - 相关度分数 > relevance-threshold        │
│  │             │  - 取前max-analysis篇（如20篇）             │
│  └──────┬──────┘                                             │
│         ↓                                                    │
│  ┌─────────────┐                                             │
│  │  4. 下载PDF  │  ← 只下载进入精读的论文                     │
│  └──────┬──────┘                                             │
│         ↓                                                    │
│  ┌─────────────┐                                             │
│  │  5. 深度分析  │  ← AI阅读全文，提取核心要素                 │
│  └──────┬──────┘                                             │
└─────────┼────────────────────────────────────────────────────┘
          ↓
┌─────────────┐
│  6. 导出报告  │  ← 生成Excel文献库和Markdown综述报告
└─────────────┘
```

## 输出文件

### Excel文献库

包含以下字段：
- 论文标题
- arXiv ID
- 论文地址
- 发布时间
- 作者
- 论文摘要
- 改进方向分类
- 相关度分数
- 问题定义
- 数学建模
- 核心创新
- 理论保证
- 实验设计
- 量化效果
- 局限性
- 创新思路

### Markdown综述报告

包含以下内容：
- 检索概述
- 改进方向分布统计
- 论文详细分析（每篇论文的核心要素）
- 各方向核心创新汇总
- 潜在研究方向

## 数据库

使用SQLite存储所有数据，包括：
- 论文基本信息
- 处理状态
- 分析结果
- 检索会话记录
- Token使用统计

### 多主题支持

系统支持同一篇论文在不同研究主题下独立记录：
- 每个研究主题有独立的会话ID
- 同一论文在不同主题下可分别评估相关度
- 主题A判定为"相关"的论文，主题B可独立判定为"不相关"
- 数据库使用复合唯一约束 `(arxiv_id, search_session_id)` 确保同一主题内不重复

## 注意事项

1. **API密钥**: 请确保 `.env` 文件中的API密钥正确配置
2. **网络连接**: 需要稳定的网络连接访问arXiv和豆包API
3. **存储空间**: PDF文件会占用一定存储空间
4. **API调用限制**: 注意豆包API的调用频率限制

## 改进方向分类

系统会将论文自动分类到以下方向：
- 数学改进
- 结构改进
- 自适应方法
- 理论分析
- 应用扩展
- 效率优化
- 其他

## 许可证

MIT License
