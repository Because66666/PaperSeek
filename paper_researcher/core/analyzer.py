"""
AI分析模块 - 使用豆包API进行论文分析
"""
import json
import asyncio
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from openai import AsyncOpenAI
from rich.console import Console
from rich.progress import Progress
from tenacity import retry, stop_after_attempt, wait_exponential

from core.config import (
    DOUBAO_API_KEY, 
    DOUBAO_BASE_URL, 
    DOUBAO_MODEL_NAME,
    MAX_CONCURRENT_REQUESTS,
    IMPROVEMENT_CATEGORIES
)
from core.db import db
from utils.pdf_handler import PDFHandler

console = Console()


@dataclass
class PaperAnalysis:
    """论文分析结果数据结构"""
    problem_definition: str
    mathematical_modeling: str
    core_innovation: str
    theoretical_guarantee: str
    experimental_design: str
    quantitative_results: str
    limitations: str
    innovation_ideas: str
    improvement_category: str
    relevance_score: float
    relevance_reason: str


class PaperAnalyzer:
    """论文分析器"""
    
    def __init__(self):
        self.client = AsyncOpenAI(
            api_key=DOUBAO_API_KEY,
            base_url=DOUBAO_BASE_URL
        )
        self.model = DOUBAO_MODEL_NAME
        self.semaphore = asyncio.Semaphore(MAX_CONCURRENT_REQUESTS)
        # Token 使用统计
        self.token_stats = {
            'prompt_tokens': 0,
            'completion_tokens': 0,
            'total_tokens': 0,
            'api_calls': 0
        }
    
    def get_token_stats(self) -> Dict[str, int]:
        """获取Token使用统计"""
        return self.token_stats.copy()
    
    def reset_token_stats(self):
        """重置Token统计"""
        self.token_stats = {
            'prompt_tokens': 0,
            'completion_tokens': 0,
            'total_tokens': 0,
            'api_calls': 0
        }
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10)
    )
    async def _call_api(self, messages: List[Dict[str, str]], temperature: float = 0.3) -> tuple:
        """
        调用豆包API
        
        Args:
            messages: 消息列表
            temperature: 温度参数
        
        Returns:
            (API响应文本, usage统计字典)
        """
        async with self.semaphore:
            try:
                response = await self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=4000
                )
                
                # 提取文本内容
                content = response.choices[0].message.content
                
                # 提取Token使用统计
                usage = {}
                if hasattr(response, 'usage') and response.usage:
                    usage = {
                        'prompt_tokens': response.usage.prompt_tokens or 0,
                        'completion_tokens': response.usage.completion_tokens or 0,
                        'total_tokens': response.usage.total_tokens or 0
                    }
                    # 累加到总计
                    self.token_stats['prompt_tokens'] += usage['prompt_tokens']
                    self.token_stats['completion_tokens'] += usage['completion_tokens']
                    self.token_stats['total_tokens'] += usage['total_tokens']
                    self.token_stats['api_calls'] += 1
                
                return content, usage
            except Exception as e:
                console.log(f"[red]API调用失败: {e}")
                raise
    
    async def screen_abstract(self, title: str, abstract: str, research_topic: str) -> Dict[str, Any]:
        """
        摘要筛选 - 判断论文是否与主题相关
        
        Args:
            title: 论文标题
            abstract: 论文摘要
            research_topic: 研究主题
        
        Returns:
            筛选结果字典
        """
        prompt = f"""你是一个学术论文筛选助手。请判断以下论文是否与主题"{research_topic}"相关。

论文标题: {title}

论文摘要: {abstract}

请按以下JSON格式输出你的判断:
{{
    "relevance_score": 0-100的整数,  // 相关度分数，100表示完全相关
    "is_relevant": true/false,  // 是否与主题相关（分数>60视为相关）
    "reason": "简要说明判断理由（2-3句话）"
}}

注意：只输出JSON，不要输出其他内容。"""

        messages = [
            {"role": "system", "content": "你是一个专业的学术论文筛选助手，擅长判断论文与特定研究主题的相关性。"},
            {"role": "user", "content": prompt}
        ]
        
        try:
            response, _ = await self._call_api(messages, temperature=0.3)
            
            # 解析JSON响应
            result = json.loads(response)
            return {
                'relevance_score': float(result.get('relevance_score', 0)),
                'is_relevant': result.get('is_relevant', False),
                'relevance_reason': result.get('reason', '')
            }
        except Exception as e:
            console.log(f"[red]摘要筛选解析失败: {e}")
            return {
                'relevance_score': 0,
                'is_relevant': False,
                'relevance_reason': f'解析失败: {str(e)}'
            }
    
    async def analyze_full_paper(self, title: str, content: str, research_topic: str) -> PaperAnalysis:
        """
        深度分析论文全文
        
        Args:
            title: 论文标题
            content: 论文全文内容
            research_topic: 研究主题
        
        Returns:
            论文分析结果
        """
        # 截断内容以适应上下文限制（保留前30000字符，约10-15页）
        truncated_content = content[:30000] if len(content) > 30000 else content
        
        prompt = f"""你是一位专业的学术论文分析专家。请对以下论文进行深度分析，提取核心要素。

研究主题: {research_topic}

论文标题: {title}

论文内容:
{truncated_content}

请按以下JSON格式输出分析结果:
{{
    "problem_definition": "该方法试图解决的具体问题（1-2句话）",
    "mathematical_modeling": "关键公式、优化目标、约束条件（简要描述）",
    "core_innovation": "核心创新点（不超过3个关键词或短语）",
    "theoretical_guarantee": "是否有理论分析（如收敛性、复杂度），简要说明",
    "experimental_design": "数据集、Baseline、评价指标",
    "quantitative_results": "相对提升（如'+2.3%'）、效率改进等量化效果",
    "limitations": "作者承认的局限性+你可以发现的可改进点",
    "innovation_ideas": "基于该论文，你可以提出的创新思路（至少3个）",
    "improvement_category": "改进方向分类，必须是以下之一: 数学改进、结构改进、自适应方法、理论分析、应用扩展、效率优化、其他"
}}

注意：
1. 只输出JSON格式，不要输出其他内容
2. 如果某部分信息在论文中未明确提及，填写"未明确提及"
3. improvement_category必须从给定列表中选择"""

        messages = [
            {"role": "system", "content": "你是一位专业的学术论文分析专家，擅长提取论文的核心要素和创新点。"},
            {"role": "user", "content": prompt}
        ]
        
        try:
            response, _ = await self._call_api(messages, temperature=0.3)
            
            # 清理响应，提取JSON部分
            response = response.strip()
            if response.startswith('```json'):
                response = response[7:]
            if response.startswith('```'):
                response = response[3:]
            if response.endswith('```'):
                response = response[:-3]
            response = response.strip()
            
            result = json.loads(response)
            
            # 验证改进方向分类
            category = result.get('improvement_category', '其他')
            if category not in IMPROVEMENT_CATEGORIES:
                category = '其他'
            
            return PaperAnalysis(
                problem_definition=result.get('problem_definition', '未明确提及'),
                mathematical_modeling=result.get('mathematical_modeling', '未明确提及'),
                core_innovation=result.get('core_innovation', '未明确提及'),
                theoretical_guarantee=result.get('theoretical_guarantee', '未明确提及'),
                experimental_design=result.get('experimental_design', '未明确提及'),
                quantitative_results=result.get('quantitative_results', '未明确提及'),
                limitations=result.get('limitations', '未明确提及'),
                innovation_ideas=result.get('innovation_ideas', '未明确提及'),
                improvement_category=category,
                relevance_score=0,
                relevance_reason=''
            )
            
        except Exception as e:
            console.log(f"[red]论文分析解析失败: {e}")
            # 返回默认分析结果
            return PaperAnalysis(
                problem_definition=f'分析失败: {str(e)}',
                mathematical_modeling='分析失败',
                core_innovation='分析失败',
                theoretical_guarantee='分析失败',
                experimental_design='分析失败',
                quantitative_results='分析失败',
                limitations='分析失败',
                innovation_ideas='分析失败',
                improvement_category='其他',
                relevance_score=0,
                relevance_reason=''
            )
    
    async def process_abstract_screening(self, papers: List[Dict[str, Any]], research_topic: str):
        """
        批量处理摘要筛选
        
        Args:
            papers: 论文列表
            research_topic: 研究主题
        """
        console.log(f"[blue]开始对 {len(papers)} 篇论文进行摘要筛选...")
        
        async def process_one(paper):
            arxiv_id = paper['arxiv_id']
            
            # 更新状态
            db.update_paper(arxiv_id, {'status': 'abstract_screening'})
            
            # 进行筛选
            result = await self.screen_abstract(
                paper['title'],
                paper['abstract'],
                research_topic
            )
            
            # 更新数据库
            updates = {
                'relevance_score': result['relevance_score'],
                'relevance_reason': result['relevance_reason'],
                'research_topic': research_topic
            }
            
            if result['is_relevant']:
                updates['status'] = 'relevant'
                console.log(f"[green]✓ 相关: {paper['title'][:50]}... (分数: {result['relevance_score']})")
            else:
                updates['status'] = 'irrelevant'
                console.log(f"[yellow]✗ 不相关: {paper['title'][:50]}... (分数: {result['relevance_score']})")
            
            db.update_paper(arxiv_id, updates)
        
        # 并发处理
        await asyncio.gather(*[process_one(paper) for paper in papers])
        console.log("[green]摘要筛选完成")
    
    async def process_full_analysis(self, papers: List[Dict[str, Any]], research_topic: str):
        """
        批量处理论文深度分析
        
        Args:
            papers: 论文列表
            research_topic: 研究主题
        """
        console.log(f"[blue]开始对 {len(papers)} 篇论文进行深度分析...")
        pdf_handler = PDFHandler()
        
        async def process_one(paper):
            arxiv_id = paper['arxiv_id']
            
            # 更新状态
            db.update_paper(arxiv_id, {'status': 'analyzing'})
            
            try:
                # 获取PDF路径
                pdf_path = paper.get('pdf_path')
                if not pdf_path:
                    console.log(f"[red]PDF路径不存在: {arxiv_id}")
                    db.update_paper(arxiv_id, {'status': 'analysis_failed'})
                    return
                
                # 提取文本
                content = pdf_handler.extract_text(pdf_path)
                if not content:
                    console.log(f"[red]PDF文本提取失败: {arxiv_id}")
                    db.update_paper(arxiv_id, {'status': 'analysis_failed'})
                    return
                
                # 进行深度分析
                analysis = await self.analyze_full_paper(
                    paper['title'],
                    content,
                    research_topic
                )
                
                # 更新数据库
                db.update_paper(arxiv_id, {
                    'status': 'analyzed',
                    'problem_definition': analysis.problem_definition,
                    'mathematical_modeling': analysis.mathematical_modeling,
                    'core_innovation': analysis.core_innovation,
                    'theoretical_guarantee': analysis.theoretical_guarantee,
                    'experimental_design': analysis.experimental_design,
                    'quantitative_results': analysis.quantitative_results,
                    'limitations': analysis.limitations,
                    'innovation_ideas': analysis.innovation_ideas,
                    'improvement_category': analysis.improvement_category,
                    'analysis_result': json.dumps({
                        'problem_definition': analysis.problem_definition,
                        'mathematical_modeling': analysis.mathematical_modeling,
                        'core_innovation': analysis.core_innovation,
                        'theoretical_guarantee': analysis.theoretical_guarantee,
                        'experimental_design': analysis.experimental_design,
                        'quantitative_results': analysis.quantitative_results,
                        'limitations': analysis.limitations,
                        'innovation_ideas': analysis.innovation_ideas,
                        'improvement_category': analysis.improvement_category
                    }, ensure_ascii=False)
                })
                
                console.log(f"[green]✓ 分析完成: {paper['title'][:50]}...")
                
            except Exception as e:
                console.log(f"[red]分析失败 {arxiv_id}: {e}")
                db.update_paper(arxiv_id, {'status': 'analysis_failed'})
        
        # 并发处理
        await asyncio.gather(*[process_one(paper) for paper in papers])
        console.log("[green]深度分析完成")


    async def generate_search_keywords(self, research_topic: str) -> List[str]:
        """
        根据研究主题生成arXiv检索关键词（英文）
        
        Args:
            research_topic: 研究主题（可以是中文或英文）
        
        Returns:
            英文关键词列表
        """
        prompt = f"""你是一位专业的学术论文检索专家。请根据以下研究主题，生成适合在arXiv上检索的英文关键词。

研究主题: "{research_topic}"

要求：
1. 生成英文关键词或短语
2. 关键词应该覆盖主题的核心概念
3. 考虑使用同义词或相关术语
4. 优先使用学术界常用的术语
5. 如果主题是中文，请准确翻译为英文学术术语
6. 覆盖与核心概念强关联的同领域技术 / 方法术语
7. 包含核心方法 / 技术的变体、改进型、衍生型术语
8. 涵盖支撑核心概念的底层理论 / 数学基础术语
9. 补充 arXiv 对应学科的领域通用术语
10. 包含核心技术的关键参数 / 核心模块术语


请按以下JSON格式输出：
{{
    "keywords": ["keyword1", "keyword2", "keyword3"]
}}

注意：
- 只输出JSON格式
- 关键词必须是英文
- 不要包含解释性文字"""

        messages = [
            {"role": "system", "content": "你是一位专业的学术论文检索专家，擅长将研究主题转化为有效的检索关键词。"},
            {"role": "user", "content": prompt}
        ]
        
        try:
            response, _ = await self._call_api(messages, temperature=0.3)
            
            # 清理响应
            response = response.strip()
            if response.startswith('```json'):
                response = response[7:]
            if response.startswith('```'):
                response = response[3:]
            if response.endswith('```'):
                response = response[:-3]
            response = response.strip()
            
            result = json.loads(response)
            keywords = result.get('keywords', [])
            
            # 确保返回的是列表
            if not isinstance(keywords, list):
                keywords = [str(keywords)]
            
            # 过滤空字符串
            keywords = [k.strip() for k in keywords if k and k.strip()]
            
            console.log(f"[green]生成检索关键词: {', '.join(keywords)}")
            return keywords
            
        except Exception as e:
            console.log(f"[red]生成关键词失败: {e}")
            # 如果生成失败，返回主题本身作为关键词
            return [research_topic]


# 便捷函数
async def screen_papers_by_abstract(papers: List[Dict[str, Any]], research_topic: str):
    """便捷函数：批量摘要筛选"""
    analyzer = PaperAnalyzer()
    await analyzer.process_abstract_screening(papers, research_topic)


async def analyze_papers_full(papers: List[Dict[str, Any]], research_topic: str):
    """便捷函数：批量深度分析"""
    analyzer = PaperAnalyzer()
    await analyzer.process_full_analysis(papers, research_topic)


async def generate_keywords_for_topic(research_topic: str) -> List[str]:
    """便捷函数：为研究主题生成检索关键词"""
    analyzer = PaperAnalyzer()
    return await analyzer.generate_search_keywords(research_topic)
