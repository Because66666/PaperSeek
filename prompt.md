一、论文检索与阅读的工程化方法
1.1 检索策略:漏斗式过滤
第一层:经典奠基文献 (必读精读)

LoRA原论文: "LoRA: Low-Rank Adaptation of Large Language Models" (ICLR 2022)
QLoRA: "QLoRA: Efficient Finetuning of Quantized LLMs" (Dettmers et al., 2023)
AdaLoRA: "Adaptive LoRA: Parameter-Efficient Fine-Tuning via Adaptive Rank Allocation" (Zhang et al., 2023)

第二层:综述与理论分析 (快速建立框架)

清华唐杰团队2026年综述:"Parameter-Efficient Fine-Tuning for Foundation Models"
"A Survey on Parameter-Efficient Fine-Tuning for Foundation Models in Federated Learning"
"Look Within or Look Beyond? A Theoretical Comparison Between Parameter-Efficient and Full Fine-Tuning" (2026)

第三层:前沿改进工作 (创新灵感来源)

数学改进: OD-LoRA(解决权重表示与梯度近似的两难)、Dual LoRA(幅度与方向分离)
结构改进: GraLoRA(细粒度分块)、SeLoRA(谱编码)、BSLoRA(跨层共享)
自适应方法: AutoLoRA(元学习自动调秩)、GeLoRA(几何自适应秩)

1.2 高效阅读法:从粗到精
第一遍:快速扫描(1-2小时/篇)

目的: 判断文献价值
必看: 摘要→引言→结论→图表
记录: 核心创新点、实验结果、与baseline的差异

第二遍:深度精读(半天-1天/篇)

数学推导: 逐行推导关键公式
实验设计: 分析数据集、指标、消融实验
局限性挖掘: 作者承认的不足+你自己发现的不足

第三遍:对比思考(1-2天/组)

横向对比: 同一问题的不同解决方案
纵向对比: 该方法的改进脉络
跨域借鉴: 其他领域有无类似思路

二、论文内容提炼的标准化框架
我建议你建立一个结构化笔记系统,每篇论文按以下模板记录:
2.1 核心要素提取表
表格维度内容问题定义该方法试图解决LoRA的哪个具体问题?数学建模关键公式、优化目标、约束条件核心创新技术突破点(≤3个关键词)理论保证是否有理论分析(如收敛性、复杂度)实验设计数据集、Baseline、评价指标量化效果相对提升(如"+2.3%")、效率改进局限性作者承认的+你发现的可改进点你的创新思路(≥3个)
2.2 数学原理的深度梳理
对于LoRA核心数学原理,你要能从三个层面理解:
层面1:矩阵分解视角

原始更新: ΔW ∈ R^(d×k),参数量 dk
LoRA分解: ΔW = BA,其中 B ∈ R^(d×r), A ∈ R^(r×k), r ≪ min(d,k)
参数量缩减: 从 dk → r(d+k)

层面2:优化视角

梯度流分析: ∂L/∂A = B^T·(∂L/∂h)·x^T, ∂L/∂B = (∂L/∂h)·(Ax)^T
训练动态: 初始阶段对齐奇异向量方向,后续调整幅度

层面3:理论局限视角

表征能力: LoRA是全量微调的严格子集,存在理论上界
鲁棒性: 增量权重分布更陡峭,对抗扰动更敏感
收敛边际: PEFT的数据驱动增益上限低于全量微调

检索30-50篇相关论文(经典+前沿)
精读10-15篇核心论文
建立Excel/Notion文献库,按"改进方向"分类标注
