"""
arXiv论文检索模块
"""
import arxiv
from typing import List, Dict, Any, Optional
from datetime import datetime
from rich.console import Console
from rich.progress import Progress, TaskID

from core.config import MAX_PAPERS_PER_SEARCH
from core.db import db

console = Console()


class ArxivSearcher:
    """arXiv论文检索器"""
    
    def __init__(self):
        self.client = arxiv.Client()
    
    def search_papers(
        self,
        keywords: List[str],
        session_id: int,
        max_results: int = None,
        offset: int = 0,
        sort_by: arxiv.SortCriterion = arxiv.SortCriterion.SubmittedDate,
        sort_order: arxiv.SortOrder = arxiv.SortOrder.Descending
    ) -> List[Dict[str, Any]]:
        """
        根据关键词检索arXiv论文
        
        Args:
            keywords: 关键词列表
            session_id: 检索会话ID
            max_results: 最大结果数
            offset: 检索偏移量（用于分页，跳过已检索的论文）
            sort_by: 排序方式
            sort_order: 排序顺序
        
        Returns:
            检索到的论文列表
        """
        max_results = max_results or MAX_PAPERS_PER_SEARCH
        
        # 构建查询字符串
        query = self._build_query(keywords)
        console.log(f"[blue]检索查询: {query} (偏移量: {offset}, 数量: {max_results})")
        
        # 创建搜索对象
        search = arxiv.Search(
            query=query,
            max_results=max_results,
            sort_by=sort_by,
            sort_order=sort_order
        )
        
        papers = []
        skipped_count = 0
        
        with Progress() as progress:
            task = progress.add_task("[cyan]检索arXiv论文...", total=None)
            
            try:
                for result in self.client.results(search):
                    # 跳过偏移量之前的论文
                    if skipped_count < offset:
                        skipped_count += 1
                        continue
                    
                    # 检查是否已存在
                    if db.paper_exists(result.entry_id.split('/')[-1]):
                        continue
                    
                    paper_data = self._parse_arxiv_result(result, session_id)
                    
                    # 保存到数据库
                    paper_id = db.add_paper(paper_data)
                    paper_data['id'] = paper_id
                    papers.append(paper_data)
                    
                    progress.update(task, advance=1)
                    console.log(f"[green]发现新论文: {result.title[:60]}...")
                    
            except Exception as e:
                console.log(f"[red]检索过程中出错: {e}")
        
        console.log(f"[green]共检索到 {len(papers)} 篇新论文")
        return papers
    
    def _build_query(self, keywords: List[str]) -> str:
        """
        构建arXiv查询字符串
        
        支持多种查询方式:
        - 简单关键词: "LoRA"
        - 短语: "\"Low Rank Adaptation\""
        - AND/OR组合
        """
        if not keywords:
            return ""
        
        # 如果只有一个关键词，直接返回
        if len(keywords) == 1:
            return keywords[0]
        
        # 多个关键词使用OR连接（只要匹配任意一个关键词即可）
        processed_keywords = []
        for kw in keywords:
            # 如果关键词包含空格，用引号包裹
            if ' ' in kw and not kw.startswith('"'):
                processed_keywords.append(f'"{kw}"')
            else:
                processed_keywords.append(kw)
        
        return " OR ".join(processed_keywords)
    
    def _parse_arxiv_result(self, result: arxiv.Result, session_id: int) -> Dict[str, Any]:
        """解析arXiv结果为字典格式"""
        # 提取arXiv ID
        arxiv_id = result.entry_id.split('/')[-1]
        if 'v' in arxiv_id:  # 移除版本号
            arxiv_id = arxiv_id.split('v')[0]
        
        return {
            'arxiv_id': arxiv_id,
            'title': result.title,
            'authors': ', '.join([author.name for author in result.authors]),
            'abstract': result.summary,
            'published_date': result.published.isoformat() if result.published else None,
            'arxiv_url': result.entry_id,
            'pdf_url': result.pdf_url,
            'status': 'discovered',
            'search_session_id': session_id
        }
    
    def search_by_ids(self, arxiv_ids: List[str]) -> List[Dict[str, Any]]:
        """
        根据arXiv ID列表检索特定论文
        
        Args:
            arxiv_ids: arXiv ID列表
        
        Returns:
            论文列表
        """
        papers = []
        
        for arxiv_id in arxiv_ids:
            try:
                # 构建ID查询
                search = arxiv.Search(id_list=[arxiv_id])
                results = list(self.client.results(search))
                
                if results:
                    result = results[0]
                    paper_data = self._parse_arxiv_result(result, None)
                    papers.append(paper_data)
                    
            except Exception as e:
                console.log(f"[red]检索ID {arxiv_id} 时出错: {e}")
        
        return papers


# 便捷函数
def search_papers(
    keywords: List[str],
    session_id: int,
    max_results: int = None,
    offset: int = 0
) -> List[Dict[str, Any]]:
    """
    便捷函数：检索arXiv论文
    
    Args:
        keywords: 关键词列表
        session_id: 检索会话ID
        max_results: 最大结果数
        offset: 检索偏移量（用于分页）
    
    Returns:
        检索到的论文列表
    """
    searcher = ArxivSearcher()
    return searcher.search_papers(keywords, session_id, max_results, offset)
