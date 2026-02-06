"""
导出模块 - 生成Excel和Markdown报告
"""
import json
from typing import List, Dict, Any
from datetime import datetime
from pathlib import Path
import pandas as pd
from rich.console import Console

from core.config import OUTPUT_PATH
from core.db import db

console = Console()


class ReportExporter:
    """报告导出器"""
    
    def __init__(self, output_dir: Path = None):
        self.output_dir = output_dir or OUTPUT_PATH
        self.output_dir.mkdir(parents=True, exist_ok=True)
    
    def export_to_excel(self, papers: List[Dict[str, Any]], filename: str = None) -> Path:
        """
        导出论文数据到Excel
        
        Args:
            papers: 论文列表
            filename: 输出文件名
        
        Returns:
            输出文件路径
        """
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"papers_analysis_{timestamp}.xlsx"
        
        output_path = self.output_dir / filename
        
        # 准备数据
        data = []
        for paper in papers:
            row = {
                '论文标题': paper.get('title', ''),
                'arXiv ID': paper.get('arxiv_id', ''),
                '论文地址': paper.get('arxiv_url', ''),
                '发布时间': paper.get('published_date', ''),
                '作者': paper.get('authors', ''),
                '论文摘要': paper.get('abstract', ''),
                '改进方向分类': paper.get('improvement_category', ''),
                '相关度分数': paper.get('relevance_score', 0),
                
                # 核心要素
                '问题定义': paper.get('problem_definition', ''),
                '数学建模': paper.get('mathematical_modeling', ''),
                '核心创新': paper.get('core_innovation', ''),
                '理论保证': paper.get('theoretical_guarantee', ''),
                '实验设计': paper.get('experimental_design', ''),
                '量化效果': paper.get('quantitative_results', ''),
                '局限性': paper.get('limitations', ''),
                '创新思路': paper.get('innovation_ideas', ''),
                
                # 元信息
                '处理状态': paper.get('status', ''),
                '筛选理由': paper.get('relevance_reason', ''),
            }
            data.append(row)
        
        # 创建DataFrame
        df = pd.DataFrame(data)
        
        # 导出到Excel，使用openpyxl引擎以支持更多格式
        with pd.ExcelWriter(output_path, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='论文分析')
            
            # 获取工作表以调整列宽
            worksheet = writer.sheets['论文分析']
            
            # 调整列宽
            for column in worksheet.columns:
                max_length = 0
                column_letter = column[0].column_letter
                
                for cell in column:
                    try:
                        if cell.value:
                            max_length = max(max_length, len(str(cell.value)))
                    except:
                        pass
                
                # 设置列宽，最大50
                adjusted_width = min(max_length + 2, 50)
                worksheet.column_dimensions[column_letter].width = adjusted_width
        
        console.log(f"[green]Excel导出成功: {output_path}")
        return output_path
    
    def generate_markdown_report(
        self, 
        papers: List[Dict[str, Any]], 
        research_topic: str,
        session_id: int = None,
        filename: str = None
    ) -> Path:
        """
        生成Markdown综述报告
        
        Args:
            papers: 论文列表
            research_topic: 研究主题
            session_id: 检索会话ID
            filename: 输出文件名
        
        Returns:
            输出文件路径
        """
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"literature_review_{timestamp}.md"
        
        output_path = self.output_dir / filename
        
        # 获取会话信息
        session_info = db.get_session(session_id) if session_id else None
        
        # 生成报告内容
        lines = []
        
        # 标题
        lines.append(f"# 文献综述报告：{research_topic}")
        lines.append("")
        lines.append(f"**生成时间**: {datetime.now().strftime('%Y年%m月%d日 %H:%M')}")
        lines.append("")
        
        # 概述
        lines.append("## 一、检索概述")
        lines.append("")
        
        if session_info:
            lines.append(f"- **研究主题**: {session_info['research_topic']}")
            lines.append(f"- **检索关键词**: {', '.join(session_info['keywords'])}")
            lines.append(f"- **检索时间**: {session_info['created_at']}")
        
        lines.append(f"- **分析论文总数**: {len(papers)} 篇")
        lines.append("")
        
        # 分类统计
        lines.append("### 改进方向分布")
        lines.append("")
        
        category_count = {}
        for paper in papers:
            cat = paper.get('improvement_category', '其他')
            category_count[cat] = category_count.get(cat, 0) + 1
        
        for cat, count in sorted(category_count.items(), key=lambda x: x[1], reverse=True):
            lines.append(f"- {cat}: {count} 篇")
        lines.append("")
        
        # 论文详细分析
        lines.append("## 二、论文详细分析")
        lines.append("")
        
        for i, paper in enumerate(papers, 1):
            lines.append(f"### {i}. {paper.get('title', '无标题')}")
            lines.append("")
            lines.append(f"**作者**: {paper.get('authors', '未知')}")
            lines.append("")
            lines.append(f"**发布时间**: {paper.get('published_date', '未知')}")
            lines.append("")
            lines.append(f"**arXiv链接**: {paper.get('arxiv_url', '')}")
            lines.append("")
            lines.append(f"**改进方向**: {paper.get('improvement_category', '未分类')}")
            lines.append("")
            
            # 核心要素
            lines.append("#### 核心要素")
            lines.append("")
            lines.append(f"**问题定义**: {paper.get('problem_definition', '未分析')}")
            lines.append("")
            lines.append(f"**数学建模**: {paper.get('mathematical_modeling', '未分析')}")
            lines.append("")
            lines.append(f"**核心创新**: {paper.get('core_innovation', '未分析')}")
            lines.append("")
            lines.append(f"**理论保证**: {paper.get('theoretical_guarantee', '未分析')}")
            lines.append("")
            lines.append(f"**实验设计**: {paper.get('experimental_design', '未分析')}")
            lines.append("")
            lines.append(f"**量化效果**: {paper.get('quantitative_results', '未分析')}")
            lines.append("")
            lines.append(f"**局限性**: {paper.get('limitations', '未分析')}")
            lines.append("")
            lines.append(f"**创新思路**: {paper.get('innovation_ideas', '未分析')}")
            lines.append("")
            
            # 摘要
            lines.append("#### 摘要")
            lines.append("")
            lines.append(paper.get('abstract', '无摘要'))
            lines.append("")
            lines.append("---")
            lines.append("")
        
        # 总结与展望
        lines.append("## 三、总结与展望")
        lines.append("")
        
        # 按分类汇总创新点
        lines.append("### 各方向核心创新汇总")
        lines.append("")
        
        for category in sorted(category_count.keys()):
            cat_papers = [p for p in papers if p.get('improvement_category') == category]
            if cat_papers:
                lines.append(f"#### {category}")
                lines.append("")
                for p in cat_papers:
                    lines.append(f"- **{p.get('title', '无标题')}**: {p.get('core_innovation', '未分析')}")
                lines.append("")
        
        # 潜在研究方向
        lines.append("### 潜在研究方向")
        lines.append("")
        
        all_ideas = []
        for paper in papers:
            ideas = paper.get('innovation_ideas', '')
            if ideas and ideas != '未明确提及' and ideas != '分析失败':
                all_ideas.append(f"- 来自《{paper.get('title', '无标题')}》: {ideas}")
        
        if all_ideas:
            lines.extend(all_ideas[:20])  # 最多显示20个
        else:
            lines.append("- 待进一步分析...")
        
        lines.append("")
        
        # 写入文件
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(lines))
        
        console.log(f"[green]Markdown报告生成成功: {output_path}")
        return output_path
    
    def export_session_results(self, session_id: int) -> tuple:
        """
        导出会话的所有结果
        
        Args:
            session_id: 检索会话ID
        
        Returns:
            (excel路径, markdown路径)
        """
        # 获取会话信息
        session = db.get_session(session_id)
        if not session:
            console.log(f"[red]会话不存在: {session_id}")
            return None, None
        
        # 获取已分析的论文
        papers = db.get_all_analyzed_papers(session_id)
        if not papers:
            console.log("[yellow]该会话没有已分析的论文")
            return None, None
        
        console.log(f"[blue]导出 {len(papers)} 篇论文的分析结果...")
        
        # 生成文件名前缀
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # 导出Excel
        excel_path = self.export_to_excel(
            papers, 
            filename=f"papers_{session_id}_{timestamp}.xlsx"
        )
        
        # 生成Markdown报告
        md_path = self.generate_markdown_report(
            papers,
            session['research_topic'],
            session_id,
            filename=f"report_{session_id}_{timestamp}.md"
        )
        
        return excel_path, md_path


# 便捷函数
def export_papers_to_excel(papers: List[Dict[str, Any]], filename: str = None) -> Path:
    """便捷函数：导出论文到Excel"""
    exporter = ReportExporter()
    return exporter.export_to_excel(papers, filename)


def generate_literature_review(
    papers: List[Dict[str, Any]], 
    research_topic: str,
    filename: str = None
) -> Path:
    """便捷函数：生成文献综述"""
    exporter = ReportExporter()
    return exporter.generate_markdown_report(papers, research_topic, filename=filename)
