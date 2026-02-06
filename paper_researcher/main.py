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
from core.analyzer import PaperAnalyzer, generate_keywords_for_topic
from utils.pdf_handler import PDFHandler
from utils.exporter import ReportExporter

console = Console()


def print_banner():
    """打印程序横幅"""
    banner = """
    ╔══════════════════════════════════════════════════════════╗
    ║           学术论文智能检索与分析系统                     ║
    ║           Academic Paper Research Assistant              ║
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
@click.option('--keywords', '-k', multiple=True, required=False, help='手动指定检索关键词（可选），如 -k "LoRA" -k "Low Rank"')
@click.option('--auto-keywords', '-ak', is_flag=True, default=True, help='使用AI自动生成检索关键词（默认开启）')
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
    auto_keywords: bool,
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
        1. AI根据研究主题自动生成英文检索关键词
        2. 第一层漏斗: 检索上限(max-search) → 泛读筛选
        3. 第二层漏斗: 精读上限(max-analysis) → 深度分析
    
    示例:
        # 默认模式：AI自动生成关键词
        python main.py run -t "LoRA改进方法"
        
        # 手动指定关键词（覆盖自动生成）
        python main.py run -t "LoRA改进方法" -k "LoRA" -k "Low Rank Adaptation" --auto-keywords=False
        
        # 检索100篇，筛选后精读分析最相关的20篇
        python main.py run -t "LoRA改进方法" -ms 100 -ma 20
        
        # 检索50篇，精读分析前10篇（相关度>70）
        python main.py run -t "LoRA改进方法" -ms 50 -ma 10 -rt 70
    """
    print_banner()
    
    # 检查API配置
    from core.config import DOUBAO_API_KEY
    if not DOUBAO_API_KEY:
        console.print("[red]错误: 未配置API密钥，请在.env文件中设置DOUBAO_API_KEY")
        return
    
    # 处理关键词：自动生成或手动指定
    if keywords:
        # 用户手动指定了关键词
        keywords_list = list(keywords)
        console.print(f"[blue]使用手动指定的关键词: {', '.join(keywords_list)}")
    elif auto_keywords:
        # 使用AI自动生成关键词
        console.print(f"[blue]正在根据研究主题生成检索关键词...")
        try:
            keywords_list = asyncio.run(generate_keywords_for_topic(topic))
            if not keywords_list:
                console.print("[yellow]关键词生成失败，使用主题本身作为关键词")
                keywords_list = [topic]
        except Exception as e:
            console.print(f"[red]关键词生成出错: {e}")
            keywords_list = [topic]
    else:
        # 没有指定关键词且关闭自动生成
        console.print("[red]错误: 未指定关键词且未开启自动生成，请使用 -k 指定关键词或开启 --auto-keywords")
        return
    
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
    
    # 创建共享的analyzer实例用于Token统计
    analyzer = PaperAnalyzer()
    
    # 步骤1 & 2: 循环检索 + 摘要筛选（漏斗式检索）
    if not skip_search:
        console.print("\n[bold cyan]步骤 1-2: 循环检索 + 摘要筛选（漏斗式检索）...")
        
        # 初始化检索参数
        current_offset = 0
        batch_size = max_search  # 每批检索数量
        max_total_search = 500  # 最多检索总数（防止无限循环）
        relevant_target = max_analysis  # 第二层漏斗目标
        
        total_searched = 0
        iteration = 0
        relevant_count = 0  # 初始化相关论文计数
        
        while True:
            iteration += 1
            console.print(f"\n[bold yellow]=== 第 {iteration} 轮检索 ===")
            console.print(f"[blue]当前偏移量: {current_offset}, 本轮检索: {batch_size}篇")
            
            # 步骤1: 检索一批论文
            papers = search_papers(keywords_list, session_id, batch_size, current_offset)
            total_searched += len(papers)
            
            if len(papers) == 0:
                console.print("[yellow]没有更多新论文，停止检索")
                break
            
            console.print(f"[green]本轮检索到 {len(papers)} 篇新论文")
            
            # 步骤2: 摘要筛选（刚检索到的论文）
            if not skip_screening:
                console.print(f"[blue]对本轮 {len(papers)} 篇论文进行摘要筛选...")
                asyncio.run(analyzer.process_abstract_screening(papers, research_topic))
            
            # 检查当前相关论文数量
            all_relevant = db.get_papers_by_status('relevant', session_id)
            relevant_count = len(all_relevant)
            console.print(f"[green]当前相关论文总数: {relevant_count}/{relevant_target}")
            
            # 判断是否达到目标
            if relevant_count >= relevant_target:
                console.print(f"[bold green]✓ 已达到第二层漏斗目标 ({relevant_count} >= {relevant_target})")
                break
            
            # 检查是否超过最大检索限制
            if total_searched >= max_total_search:
                console.print(f"[yellow]⚠ 已达到最大检索限制 ({max_total_search})，停止检索")
                break
            
            # 更新偏移量，准备下一轮
            current_offset += batch_size
            console.print(f"[blue]相关论文不足，继续下一轮检索...")
        
        console.print(f"\n[bold green]检索完成: 共检索 {total_searched} 篇，筛选出 {relevant_count} 篇相关论文")
    else:
        console.print("\n[yellow]跳过检索步骤")
        if not skip_screening:
            console.print("\n[bold cyan]步骤 2: 摘要筛选（已有数据）...")
            papers_to_screen = db.get_papers_by_status('discovered', session_id)
            if papers_to_screen:
                asyncio.run(analyzer.process_abstract_screening(papers_to_screen, research_topic))
            else:
                console.print("[yellow]没有需要筛选的论文")
    
    # 步骤3: 下载PDF（第二层漏斗 - 只下载进入精读的论文）
    # 注意：获取所有会话中与当前研究主题匹配的relevant论文
    if not skip_download:
        console.print("\n[bold cyan]步骤 3: 下载PDF（第二层漏斗 - 精读上限）...")
        # 获取所有会话中与当前研究主题匹配的相关论文
        all_relevant = db.get_papers_by_status('relevant', research_topic=research_topic)
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
        
        console.print(f"[blue]主题'{research_topic[:30]}...'的相关论文: {len(all_relevant)}篇, 超过阈值({relevance_threshold}): {len(filtered)}篇, 进入精读: {len(papers_to_download)}篇")
        
        if papers_to_download:
            asyncio.run(download_pdfs_for_papers(papers_to_download))
        else:
            console.print("[yellow]没有需要下载的论文")
    else:
        console.print("\n[yellow]跳过PDF下载")
    
    # 步骤4: 深度分析
    # 注意：获取所有会话中与当前研究主题匹配的已下载PDF论文
    if not skip_analysis:
        console.print("\n[bold cyan]步骤 4: 深度分析...")
        # 获取所有已下载PDF且与当前研究主题匹配的论文
        all_downloaded = db.get_papers_by_status('pdf_downloaded')
        papers_to_analyze = [p for p in all_downloaded if p.get('research_topic') == research_topic]
        if papers_to_analyze:
            console.print(f"[blue]共 {len(papers_to_analyze)} 篇论文需要深度分析")
            asyncio.run(analyzer.process_full_analysis(papers_to_analyze, research_topic))
        else:
            console.print("[yellow]没有需要分析的论文")
    else:
        console.print("\n[yellow]跳过深度分析")
    
    # 更新会话统计
    db.update_session_stats(session_id)
    
    # 获取并保存Token使用统计
    token_stats = analyzer.get_token_stats()
    db.update_session_token_stats(session_id, token_stats)
    
    # 打印统计
    console.print("\n[bold cyan]处理统计:")
    print_statistics(session_id)
    
    # 打印Token使用统计
    console.print("\n[bold cyan]Token使用统计:")
    token_table = Table(show_header=True, header_style="bold magenta")
    token_table.add_column("指标", style="cyan")
    token_table.add_column("数量", style="green")
    token_table.add_row("API调用次数", f"{token_stats['api_calls']:,}")
    token_table.add_row("输入Tokens (Prompt)", f"{token_stats['prompt_tokens']:,}")
    token_table.add_row("输出Tokens (Completion)", f"{token_stats['completion_tokens']:,}")
    token_table.add_row("总Tokens", f"{token_stats['total_tokens']:,}")
    console.print(token_table)
    
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
