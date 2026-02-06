"""
论文检索与分析系统 - 主程序

使用方法:
    python main.py --topic "LoRA改进方法" --keywords "LoRA" "Low Rank Adaptation" --max-papers 50
"""
import asyncio
import click
import sys
from pathlib import Path
from typing import List
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

# 添加项目根目录到路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from core.config import MAX_PAPERS_PER_SEARCH, MAX_PAPERS_FOR_ANALYSIS, RELEVANCE_SCORE_THRESHOLD
from core.db import db
from core.searcher import search_papers
from core.analyzer import PaperAnalyzer
from utils.pdf_handler import PDFHandler
from utils.exporter import ReportExporter

console = Console()


def print_banner():
    """打印程序横幅"""
    banner = """
    ╔══════════════════════════════════════════════════════════╗
    ║           学术论文智能检索与分析系统                      ║
    ║              Academic Paper Research Assistant           ║
    ╚══════════════════════════════════════════════════════════╝
    """
    console.print(Panel(banner, style="bold blue"))


def print_statistics(session_id: int):
    """打印统计信息"""
    stats = db.get_statistics(session_id)
    
    table = Table(title="处理统计")
    table.add_column("状态", style="cyan")
    table.add_column("数量", style="magenta")
    
    status_names = {
        'discovered': '已发现',
        'abstract_screening': '摘要筛选中',
        'relevant': '相关（待下载）',
        'irrelevant': '不相关',
        'pdf_downloading': 'PDF下载中',
        'pdf_downloaded': 'PDF已下载',
        'pdf_failed': 'PDF下载失败',
        'analyzing': '深度分析中',
        'analyzed': '分析完成',
        'analysis_failed': '分析失败'
    }
    
    for status, count in stats.items():
        name = status_names.get(status, status)
        table.add_row(name, str(count))
    
    console.print(table)


async def download_pdfs_for_papers(papers: List[dict]):
    """为论文下载PDF"""
    pdf_handler = PDFHandler()
    
    console.log(f"[blue]开始下载 {len(papers)} 篇论文的PDF...")
    
    tasks = []
    for paper in papers:
        if paper.get('pdf_url'):
            task = pdf_handler.download_pdf(paper['arxiv_id'], paper['pdf_url'])
            tasks.append(task)
    
    # 并发下载
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    success_count = sum(1 for r in results if r is not None and not isinstance(r, Exception))
    console.log(f"[green]PDF下载完成: {success_count}/{len(tasks)} 成功")


@click.command()
@click.option('--topic', '-t', required=True, help='研究主题，如 "LoRA改进方法"')
@click.option('--keywords', '-k', multiple=True, required=True, help='检索关键词，可多次使用，如 -k "LoRA" -k "Low Rank"')
@click.option('--max-search', '-ms', default=100, help=f'最大检索论文数（第一层漏斗-泛读），默认100')
@click.option('--max-analysis', '-ma', default=20, help=f'最大精读分析数（第二层漏斗-精读），默认20')
@click.option('--relevance-threshold', '-rt', default=60, help=f'相关度分数阈值，低于此分数不进入精读，默认60')
@click.option('--skip-search', is_flag=True, help='跳过检索，只处理已有数据')
@click.option('--skip-screening', is_flag=True, help='跳过摘要筛选')
@click.option('--skip-download', is_flag=True, help='跳过PDF下载')
@click.option('--skip-analysis', is_flag=True, help='跳过深度分析')
@click.option('--session-id', type=int, help='指定已有会话ID，用于增量更新')
@click.option('--export-only', is_flag=True, help='仅导出结果，不执行其他操作')
def main(
    topic: str,
    keywords: tuple,
    max_search: int,
    max_analysis: int,
    relevance_threshold: float,
    skip_search: bool,
    skip_screening: bool,
    skip_download: bool,
    skip_analysis: bool,
    session_id: int,
    export_only: bool
):
    """
    学术论文智能检索与分析系统 - 漏斗式过滤
    
    工作流程:
        第一层漏斗: 检索上限(max-search) → 泛读筛选
        第二层漏斗: 精读上限(max-analysis) → 深度分析
    
    示例:
        # 检索100篇，筛选后精读分析最相关的20篇
        python main.py run -t "LoRA改进方法" -k "LoRA" -ms 100 -ma 20
        
        # 检索50篇，精读分析前10篇（相关度>70）
        python main.py run -t "LoRA改进方法" -k "LoRA" -ms 50 -ma 10 -rt 70
    """
    print_banner()
    
    # 检查API配置
    from core.config import DOUBAO_API_KEY
    if not DOUBAO_API_KEY:
        console.print("[red]错误: 未配置API密钥，请在.env文件中设置DOUBAO_API_KEY")
        return
    
    keywords_list = list(keywords)
    
    # 如果指定了session_id，使用已有会话
    if session_id:
        session = db.get_session(session_id)
        if not session:
            console.print(f"[red]错误: 会话 {session_id} 不存在")
            return
        console.print(f"[blue]使用已有会话: {session_id}")
        research_topic = session['research_topic']
    else:
        # 创建新会话
        session_id = db.create_search_session(topic, keywords_list)
        research_topic = topic
        console.print(f"[green]创建新会话: {session_id}")
    
    console.print(f"[blue]研究主题: {research_topic}")
    console.print(f"[blue]检索关键词: {', '.join(keywords_list)}")
    console.print(f"[blue]漏斗配置: 检索上限={max_search}, 精读上限={max_analysis}, 相关度阈值={relevance_threshold}")
    
    # 仅导出模式
    if export_only:
        console.print("[blue]仅导出模式...")
        exporter = ReportExporter()
        excel_path, md_path = exporter.export_session_results(session_id)
        if excel_path and md_path:
            console.print(f"[green]导出成功!")
            console.print(f"  Excel: {excel_path}")
            console.print(f"  Markdown: {md_path}")
        return
    
    # 步骤1: 检索论文（第一层漏斗）
    if not skip_search:
        console.print("\n[bold cyan]步骤 1/4: 检索arXiv论文（第一层漏斗 - 泛读上限）...")
        papers = search_papers(keywords_list, session_id, max_search)
        console.print(f"[green]检索到 {len(papers)} 篇新论文（目标: {max_search}篇）")
    else:
        console.print("\n[yellow]跳过检索步骤")
        papers = db.get_papers_by_status('discovered', session_id)
    
    # 步骤2: 摘要筛选
    if not skip_screening:
        console.print("\n[bold cyan]步骤 2/4: 摘要筛选...")
        papers_to_screen = db.get_papers_by_status('discovered', session_id)
        if papers_to_screen:
            analyzer = PaperAnalyzer()
            asyncio.run(analyzer.process_abstract_screening(papers_to_screen, research_topic))
        else:
            console.print("[yellow]没有需要筛选的论文")
    else:
        console.print("\n[yellow]跳过摘要筛选")
    
    # 步骤3: 下载PDF（第二层漏斗 - 只下载进入精读的论文）
    if not skip_download:
        console.print("\n[bold cyan]步骤 3/4: 下载PDF（第二层漏斗 - 精读上限）...")
        # 获取相关论文，按相关度分数排序
        all_relevant = db.get_papers_by_status('relevant', session_id)
        # 过滤掉低于阈值的
        filtered = [p for p in all_relevant if p.get('relevance_score', 0) >= relevance_threshold]
        # 按分数排序，取前max_analysis篇
        sorted_papers = sorted(filtered, key=lambda x: x.get('relevance_score', 0), reverse=True)
        papers_to_download = sorted_papers[:max_analysis]
        
        # 标记不进入精读的论文
        excluded = sorted_papers[max_analysis:]
        for paper in excluded:
            db.update_paper(paper['arxiv_id'], {
                'status': 'irrelevant',
                'relevance_reason': paper.get('relevance_reason', '') + f' [未进入精读: 排名>{max_analysis}]'
            })
        
        console.print(f"[blue]相关论文: {len(all_relevant)}篇, 超过阈值({relevance_threshold}): {len(filtered)}篇, 进入精读: {len(papers_to_download)}篇")
        
        if papers_to_download:
            asyncio.run(download_pdfs_for_papers(papers_to_download))
        else:
            console.print("[yellow]没有需要下载的论文")
    else:
        console.print("\n[yellow]跳过PDF下载")
    
    # 步骤4: 深度分析
    if not skip_analysis:
        console.print("\n[bold cyan]步骤 4/4: 深度分析...")
        papers_to_analyze = db.get_papers_by_status('pdf_downloaded', session_id)
        if papers_to_analyze:
            analyzer = PaperAnalyzer()
            asyncio.run(analyzer.process_full_analysis(papers_to_analyze, research_topic))
        else:
            console.print("[yellow]没有需要分析的论文")
    else:
        console.print("\n[yellow]跳过深度分析")
    
    # 更新会话统计
    db.update_session_stats(session_id)
    
    # 打印统计
    console.print("\n[bold cyan]处理统计:")
    print_statistics(session_id)
    
    # 导出结果
    console.print("\n[bold cyan]导出结果...")
    exporter = ReportExporter()
    excel_path, md_path = exporter.export_session_results(session_id)
    
    if excel_path and md_path:
        console.print(f"[green]导出成功!")
        console.print(f"  Excel: {excel_path}")
        console.print(f"  Markdown: {md_path}")
    
    console.print("\n[bold green]处理完成!")


@click.command()
@click.option('--session-id', '-s', type=int, help='指定会话ID')
def stats(session_id: int):
    """查看统计信息"""
    print_statistics(session_id)


@click.command()
@click.option('--session-id', '-s', required=True, type=int, help='会话ID')
def export(session_id: int):
    """导出指定会话的结果"""
    console.print(f"[blue]导出会话 {session_id} 的结果...")
    
    exporter = ReportExporter()
    excel_path, md_path = exporter.export_session_results(session_id)
    
    if excel_path and md_path:
        console.print(f"[green]导出成功!")
        console.print(f"  Excel: {excel_path}")
        console.print(f"  Markdown: {md_path}")
    else:
        console.print("[red]导出失败")


@click.group()
def cli():
    """学术论文智能检索与分析系统"""
    pass


# 添加命令
cli.add_command(main, name='run')
cli.add_command(stats, name='stats')
cli.add_command(export, name='export')


if __name__ == '__main__':
    cli()
