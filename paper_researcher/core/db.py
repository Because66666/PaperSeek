"""
数据库模型和操作
"""
import sqlite3
import json
from datetime import datetime
from typing import List, Optional, Dict, Any
from contextlib import contextmanager
from core.config import DATABASE_PATH, PaperStatus


class Database:
    """数据库管理类"""
    
    def __init__(self, db_path: str = None):
        self.db_path = str(db_path or DATABASE_PATH)
        self._init_db()
    
    @contextmanager
    def _get_connection(self):
        """获取数据库连接上下文管理器"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()
    
    def _init_db(self):
        """初始化数据库表结构"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # 论文表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS papers (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    arxiv_id TEXT NOT NULL,
                    title TEXT NOT NULL,
                    authors TEXT,
                    abstract TEXT,
                    published_date TEXT,
                    arxiv_url TEXT,
                    pdf_url TEXT,
                    pdf_path TEXT,
                    status TEXT DEFAULT 'discovered',

                    -- 筛选相关
                    research_topic TEXT,
                    relevance_score REAL,
                    relevance_reason TEXT,

                    -- 分类
                    improvement_category TEXT,

                    -- 深度分析结果（JSON格式存储）
                    analysis_result TEXT,

                    -- 核心要素
                    problem_definition TEXT,
                    mathematical_modeling TEXT,
                    core_innovation TEXT,
                    theoretical_guarantee TEXT,
                    experimental_design TEXT,
                    quantitative_results TEXT,
                    limitations TEXT,
                    innovation_ideas TEXT,

                    -- 时间戳
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,

                    -- 检索会话
                    search_session_id INTEGER,

                    -- 复合唯一约束：同一主题下论文不能重复
                    UNIQUE(arxiv_id, search_session_id)
                )
            """)
            
            # 检索会话表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS search_sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    research_topic TEXT NOT NULL,
                    keywords TEXT,
                    total_found INTEGER DEFAULT 0,
                    relevant_count INTEGER DEFAULT 0,
                    analyzed_count INTEGER DEFAULT 0,
                    -- Token使用统计
                    api_calls INTEGER DEFAULT 0,
                    prompt_tokens INTEGER DEFAULT 0,
                    completion_tokens INTEGER DEFAULT 0,
                    total_tokens INTEGER DEFAULT 0,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    completed_at TEXT
                )
            """)
            
            # 创建索引
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_papers_status ON papers(status)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_papers_arxiv_id ON papers(arxiv_id)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_papers_session ON papers(search_session_id)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_papers_topic ON papers(research_topic)
            """)

            conn.commit()
    
    # ==================== 论文操作 ====================
    
    def paper_exists(self, arxiv_id: str, session_id: int = None) -> bool:
        """检查论文是否已存在
        
        Args:
            arxiv_id: arXiv ID
            session_id: 检索会话ID，如果指定则检查该主题下是否存在
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            if session_id:
                cursor.execute(
                    "SELECT 1 FROM papers WHERE arxiv_id = ? AND search_session_id = ?",
                    (arxiv_id, session_id)
                )
            else:
                cursor.execute(
                    "SELECT 1 FROM papers WHERE arxiv_id = ?",
                    (arxiv_id,)
                )
            return cursor.fetchone() is not None
    
    def add_paper(self, paper_data: Dict[str, Any]) -> int:
        """添加新论文"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            fields = []
            values = []
            for key, value in paper_data.items():
                fields.append(key)
                values.append(value)
            
            placeholders = ', '.join(['?' for _ in values])
            fields_str = ', '.join(fields)
            
            cursor.execute(
                f"INSERT INTO papers ({fields_str}) VALUES ({placeholders})",
                values
            )
            
            return cursor.lastrowid
    
    def update_paper(self, arxiv_id: str, updates: Dict[str, Any]):
        """更新论文信息"""
        updates['updated_at'] = datetime.now().isoformat()
        
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            set_clause = ', '.join([f"{k} = ?" for k in updates.keys()])
            values = list(updates.values()) + [arxiv_id]
            
            cursor.execute(
                f"UPDATE papers SET {set_clause} WHERE arxiv_id = ?",
                values
            )
    
    def get_paper_by_arxiv_id(self, arxiv_id: str) -> Optional[Dict[str, Any]]:
        """通过arXiv ID获取论文"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM papers WHERE arxiv_id = ?",
                (arxiv_id,)
            )
            row = cursor.fetchone()
            return dict(row) if row else None
    
    def get_papers_by_status(self, status: str, session_id: int = None, research_topic: str = None) -> List[Dict[str, Any]]:
        """获取指定状态的论文
        
        Args:
            status: 论文状态
            session_id: 检索会话ID（可选）
            research_topic: 研究主题（可选），用于跨会话获取相同主题的论文
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            if research_topic:
                # 按研究主题查询（跨会话）
                cursor.execute(
                    "SELECT * FROM papers WHERE status = ? AND research_topic = ?",
                    (status, research_topic)
                )
            elif session_id:
                cursor.execute(
                    "SELECT * FROM papers WHERE status = ? AND search_session_id = ?",
                    (status, session_id)
                )
            else:
                cursor.execute(
                    "SELECT * FROM papers WHERE status = ?",
                    (status,)
                )
            
            return [dict(row) for row in cursor.fetchall()]
    
    def get_all_analyzed_papers(self, session_id: int = None) -> List[Dict[str, Any]]:
        """获取所有已分析的论文"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            if session_id:
                cursor.execute(
                    """SELECT * FROM papers 
                       WHERE status = 'analyzed' AND search_session_id = ?
                       ORDER BY published_date DESC""",
                    (session_id,)
                )
            else:
                cursor.execute(
                    """SELECT * FROM papers 
                       WHERE status = 'analyzed'
                       ORDER BY published_date DESC"""
                )
            
            return [dict(row) for row in cursor.fetchall()]
    
    # ==================== 检索会话操作 ====================
    
    def create_search_session(self, research_topic: str, keywords: List[str]) -> int:
        """创建新的检索会话"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO search_sessions (research_topic, keywords) VALUES (?, ?)",
                (research_topic, json.dumps(keywords, ensure_ascii=False))
            )
            return cursor.lastrowid
    
    def update_session_stats(self, session_id: int):
        """更新会话统计信息"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # 统计相关论文数量
            cursor.execute(
                "SELECT COUNT(*) FROM papers WHERE search_session_id = ? AND status IN ('relevant', 'pdf_downloading', 'pdf_downloaded', 'analyzing', 'analyzed')",
                (session_id,)
            )
            relevant_count = cursor.fetchone()[0]
            
            # 统计已分析论文数量
            cursor.execute(
                "SELECT COUNT(*) FROM papers WHERE search_session_id = ? AND status = 'analyzed'",
                (session_id,)
            )
            analyzed_count = cursor.fetchone()[0]
            
            cursor.execute(
                """UPDATE search_sessions 
                   SET relevant_count = ?, analyzed_count = ?
                   WHERE id = ?""",
                (relevant_count, analyzed_count, session_id)
            )
    
    def complete_session(self, session_id: int):
        """完成检索会话"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE search_sessions SET completed_at = ? WHERE id = ?",
                (datetime.now().isoformat(), session_id)
            )

    def update_session_token_stats(self, session_id: int, token_stats: dict):
        """更新会话Token使用统计

        Args:
            session_id: 会话ID
            token_stats: Token统计信息，包含 api_calls, prompt_tokens, completion_tokens, total_tokens
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """UPDATE search_sessions
                   SET api_calls = ?, prompt_tokens = ?, completion_tokens = ?, total_tokens = ?
                   WHERE id = ?""",
                (
                    token_stats.get('api_calls', 0),
                    token_stats.get('prompt_tokens', 0),
                    token_stats.get('completion_tokens', 0),
                    token_stats.get('total_tokens', 0),
                    session_id
                )
            )
    
    def get_session(self, session_id: int) -> Optional[Dict[str, Any]]:
        """获取会话信息"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM search_sessions WHERE id = ?",
                (session_id,)
            )
            row = cursor.fetchone()
            if row:
                result = dict(row)
                result['keywords'] = json.loads(result['keywords'])
                return result
            return None
    
    # ==================== 统计信息 ====================
    
    def get_statistics(self, session_id: int = None) -> Dict[str, int]:
        """获取统计信息"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            if session_id:
                cursor.execute(
                    """SELECT status, COUNT(*) as count 
                       FROM papers WHERE search_session_id = ?
                       GROUP BY status""",
                    (session_id,)
                )
            else:
                cursor.execute(
                    """SELECT status, COUNT(*) as count 
                       FROM papers GROUP BY status"""
                )
            
            stats = {row['status']: row['count'] for row in cursor.fetchall()}
            return stats


# 全局数据库实例
db = Database()
