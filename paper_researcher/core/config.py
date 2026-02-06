"""
配置文件管理
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# 项目根目录
PROJECT_ROOT = Path(__file__).parent.parent.absolute()

# API配置
DOUBAO_API_KEY = os.getenv("DOUBAO_API_KEY", "")
DOUBAO_BASE_URL = os.getenv("DOUBAO_BASE_URL", "https://ark.cn-beijing.volces.com/api/v3")
DOUBAO_MODEL_NAME = os.getenv("DOUBAO_MODEL_NAME", "doubao-1.5-pro-32k-250115")

# 检索配置 - 漏斗式过滤
MAX_CONCURRENT_REQUESTS = int(os.getenv("MAX_CONCURRENT_REQUESTS", "20"))

# 第一层：检索上限（泛读）
MAX_PAPERS_PER_SEARCH = int(os.getenv("MAX_PAPERS_PER_SEARCH", "100"))

# 第二层：精读上限（只分析最相关的N篇）
MAX_PAPERS_FOR_ANALYSIS = int(os.getenv("MAX_PAPERS_FOR_ANALYSIS", "20"))

# 相关度分数阈值（可选，低于此分数不进入精读）
RELEVANCE_SCORE_THRESHOLD = float(os.getenv("RELEVANCE_SCORE_THRESHOLD", "60"))

# 数据存储路径
DATABASE_PATH = PROJECT_ROOT / os.getenv("DATABASE_PATH", "data/papers.db")
PDF_DOWNLOAD_PATH = PROJECT_ROOT / os.getenv("PDF_DOWNLOAD_PATH", "papers_output/pdfs")
OUTPUT_PATH = PROJECT_ROOT / "papers_output"

# 确保目录存在
DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
PDF_DOWNLOAD_PATH.mkdir(parents=True, exist_ok=True)
OUTPUT_PATH.mkdir(parents=True, exist_ok=True)

# 论文处理状态
class PaperStatus:
    DISCOVERED = "discovered"          # 刚检索到
    ABSTRACT_SCREENING = "abstract_screening"  # 摘要筛选中
    RELEVANT = "relevant"              # 摘要筛选通过
    IRRELEVANT = "irrelevant"          # 摘要筛选不通过
    PDF_DOWNLOADING = "pdf_downloading"  # PDF下载中
    PDF_DOWNLOADED = "pdf_downloaded"    # PDF已下载
    PDF_FAILED = "pdf_failed"          # PDF下载失败
    ANALYZING = "analyzing"            # 深度分析中
    ANALYZED = "analyzed"              # 分析完成
    ANALYSIS_FAILED = "analysis_failed"  # 分析失败

# 改进方向分类
IMPROVEMENT_CATEGORIES = [
    "数学改进",
    "结构改进", 
    "自适应方法",
    "理论分析",
    "应用扩展",
    "效率优化",
    "其他"
]
