"""
PDF下载和解析模块
"""
import os
import aiohttp
import aiofiles
import fitz  # PyMuPDF
from typing import Optional
from pathlib import Path
from rich.console import Console
from tenacity import retry, stop_after_attempt, wait_exponential

from core.config import PDF_DOWNLOAD_PATH
from core.db import db

console = Console()


class PDFHandler:
    """PDF处理器"""
    
    def __init__(self, download_path: Path = None):
        self.download_path = download_path or PDF_DOWNLOAD_PATH
        self.download_path.mkdir(parents=True, exist_ok=True)
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10)
    )
    async def download_pdf(self, arxiv_id: str, pdf_url: str) -> Optional[Path]:
        """
        异步下载PDF文件
        
        Args:
            arxiv_id: arXiv ID
            pdf_url: PDF下载链接
        
        Returns:
            下载后的文件路径，失败返回None
        """
        # 更新状态为下载中
        db.update_paper(arxiv_id, {'status': 'pdf_downloading'})
        
        pdf_filename = f"{arxiv_id}.pdf"
        pdf_path = self.download_path / pdf_filename
        
        # 如果文件已存在，直接返回
        if pdf_path.exists():
            console.log(f"[yellow]PDF已存在: {pdf_filename}")
            db.update_paper(arxiv_id, {
                'status': 'pdf_downloaded',
                'pdf_path': str(pdf_path)
            })
            return pdf_path
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(pdf_url, timeout=aiohttp.ClientTimeout(total=120)) as response:
                    if response.status != 200:
                        raise Exception(f"HTTP {response.status}")
                    
                    # 异步写入文件
                    async with aiofiles.open(pdf_path, 'wb') as f:
                        async for chunk in response.content.iter_chunked(8192):
                            await f.write(chunk)
            
            # 验证文件
            if pdf_path.exists() and pdf_path.stat().st_size > 0:
                console.log(f"[green]PDF下载成功: {pdf_filename}")
                db.update_paper(arxiv_id, {
                    'status': 'pdf_downloaded',
                    'pdf_path': str(pdf_path)
                })
                return pdf_path
            else:
                raise Exception("文件为空或不存在")
                
        except Exception as e:
            console.log(f"[red]PDF下载失败 {arxiv_id}: {e}")
            db.update_paper(arxiv_id, {'status': 'pdf_failed'})
            # 清理失败的文件
            if pdf_path.exists():
                pdf_path.unlink()
            return None
    
    def extract_text(self, pdf_path) -> str:
        """
        从PDF提取文本
        
        Args:
            pdf_path: PDF文件路径（Path对象或字符串）
        
        Returns:
            提取的文本内容
        """
        # 确保 pdf_path 是 Path 对象
        if isinstance(pdf_path, str):
            pdf_path = Path(pdf_path)
        
        try:
            text = ""
            with fitz.open(str(pdf_path)) as doc:
                for page_num, page in enumerate(doc):
                    text += f"\n--- Page {page_num + 1} ---\n"
                    text += page.get_text()
            
            # 清理文本
            text = self._clean_text(text)
            
            console.log(f"[green]PDF解析成功: {pdf_path.name} ({len(text)} 字符)")
            return text
            
        except Exception as e:
            console.log(f"[red]PDF解析失败 {pdf_path}: {e}")
            return ""
    
    def _clean_text(self, text: str) -> str:
        """清理提取的文本"""
        # 移除多余的空白字符
        lines = text.split('\n')
        cleaned_lines = []
        
        for line in lines:
            line = line.strip()
            # 跳过空行，但保留段落分隔
            if line:
                cleaned_lines.append(line)
        
        return '\n'.join(cleaned_lines)
    
    def get_paper_text(self, arxiv_id: str) -> Optional[str]:
        """
        获取论文文本（下载+解析）
        
        Args:
            arxiv_id: arXiv ID
        
        Returns:
            论文文本内容
        """
        # 检查是否已下载
        paper = db.get_paper_by_arxiv_id(arxiv_id)
        if not paper:
            console.log(f"[red]论文不存在: {arxiv_id}")
            return None
        
        # 如果已有PDF路径，直接解析
        if paper.get('pdf_path') and Path(paper['pdf_path']).exists():
            return self.extract_text(Path(paper['pdf_path']))
        
        # 否则需要先下载
        console.log(f"[yellow]PDF未下载，需要先下载: {arxiv_id}")
        return None
    
    def delete_pdf(self, arxiv_id: str):
        """删除PDF文件"""
        pdf_path = self.download_path / f"{arxiv_id}.pdf"
        if pdf_path.exists():
            pdf_path.unlink()
            console.log(f"[yellow]已删除PDF: {pdf_path.name}")


# 便捷函数
async def download_paper_pdf(arxiv_id: str, pdf_url: str) -> Optional[Path]:
    """
    便捷函数：下载论文PDF
    
    Args:
        arxiv_id: arXiv ID
        pdf_url: PDF下载链接
    
    Returns:
        下载后的文件路径
    """
    handler = PDFHandler()
    return await handler.download_pdf(arxiv_id, pdf_url)


def extract_paper_text(pdf_path: Path) -> str:
    """
    便捷函数：提取论文文本
    
    Args:
        pdf_path: PDF文件路径
    
    Returns:
        提取的文本内容
    """
    handler = PDFHandler()
    return handler.extract_text(pdf_path)
