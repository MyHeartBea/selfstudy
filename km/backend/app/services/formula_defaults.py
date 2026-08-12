"""公式背诵库的默认内容。"""

DEFAULT_FORMULAS = [
    (
        "高等数学",
        "常用导数公式表",
        """## 基本导数公式
| 函数 | 导数 |
|---|---|
| $x^n$ | $n x^{n-1}$ |
| $\\sqrt{x}$ | $\\dfrac{1}{2\\sqrt{x}}$ |
| $\\dfrac{1}{x}$ | $-\\dfrac{1}{x^2}$ |
| $e^x$ | $e^x$ |
| $a^x$ | $a^x \\ln a$ |
| $\\ln x$ | $\\dfrac{1}{x}$ |
| $\\log_a x$ | $\\dfrac{1}{x\\ln a}$ |
| $\\sin x$ | $\\cos x$ |
| $\\cos x$ | $-\\sin x$ |
| $\\tan x$ | $\\sec^2 x$ |
| $\\cot x$ | $-\\csc^2 x$ |
| $\\sec x$ | $\\sec x\\tan x$ |
| $\\csc x$ | $-\\csc x\\cot x$ |
| $\\arcsin x$ | $\\dfrac{1}{\\sqrt{1-x^2}}$ |
| $\\arccos x$ | $-\\dfrac{1}{\\sqrt{1-x^2}}$ |
| $\\arctan x$ | $\\dfrac{1}{1+x^2}$ |
| $\\operatorname{arccot} x$ | $-\\dfrac{1}{1+x^2}$ |
| $\\sinh x$ | $\\cosh x$ |
| $\\cosh x$ | $\\sinh x$ |
| $\\tanh x$ | $\\operatorname{sech}^2 x$ |
| $uv$ | $u'v+uv'$ |
| $\\dfrac{u}{v}$ | $\\dfrac{u'v-uv'}{v^2}$ |
| $f(g(x))$ | $f'(g(x))g'(x)$ |
| $x^x$ | $x^x(\\ln x+1)$ |

## 备注
- 复合函数从外到内逐层求导。
- 分段点处优先用导数定义判断。""",
    ),
    (
        "高等数学",
        "基本积分表",
        """## 常用不定积分
| 被积函数 | 原函数 |
|---|---|
| $x^n\\,(n\\neq-1)$ | $\\dfrac{x^{n+1}}{n+1}+C$ |
| $\\dfrac{1}{x}$ | $\\ln\\lvert x\\rvert+C$ |
| $e^x$ | $e^x+C$ |
| $a^x$ | $\\dfrac{a^x}{\\ln a}+C$ |
| $e^{ax}$ | $\\dfrac{e^{ax}}{a}+C$ |
| $\\sin x$ | $-\\cos x+C$ |
| $\\cos x$ | $\\sin x+C$ |
| $\\tan x$ | $\\ln\\lvert\\sec x\\rvert+C$ |
| $\\cot x$ | $\\ln\\lvert\\sin x\\rvert+C$ |
| $\\sec x$ | $\\ln\\lvert\\sec x+\\tan x\\rvert+C$ |
| $\\csc x$ | $\\ln\\lvert\\csc x-\\cot x\\rvert+C$ |
| $\\sec^2 x$ | $\\tan x+C$ |
| $\\csc^2 x$ | $-\\cot x+C$ |
| $\\sec x\\tan x$ | $\\sec x+C$ |
| $\\csc x\\cot x$ | $-\\csc x+C$ |
| $\\dfrac{1}{1+x^2}$ | $\\arctan x+C$ |
| $\\dfrac{1}{\\sqrt{1-x^2}}$ | $\\arcsin x+C$ |
| $\\dfrac{1}{a^2+x^2}$ | $\\dfrac{1}{a}\\arctan\\dfrac{x}{a}+C$ |
| $\\dfrac{1}{a^2-x^2}$ | $\\dfrac{1}{2a}\\ln\\left\\lvert\\dfrac{a+x}{a-x}\\right\\rvert+C$ |
| $\\dfrac{1}{x^2-a^2}$ | $\\dfrac{1}{2a}\\ln\\left\\lvert\\dfrac{x-a}{x+a}\\right\\rvert+C$ |
| $\\dfrac{1}{\\sqrt{a^2-x^2}}$ | $\\arcsin\\dfrac{x}{a}+C$ |
| $\\dfrac{1}{\\sqrt{x^2+a^2}}$ | $\\ln\\left(x+\\sqrt{x^2+a^2}\\right)+C$ |
| $\\dfrac{1}{\\sqrt{x^2-a^2}}$ | $\\ln\\left\\lvert x+\\sqrt{x^2-a^2}\\right\\rvert+C$ |
| $\\sqrt{a^2-x^2}$ | $\\dfrac{x}{2}\\sqrt{a^2-x^2}+\\dfrac{a^2}{2}\\arcsin\\dfrac{x}{a}+C$ |
| $\\ln x$ | $x\\ln x-x+C$ |
| $x e^x$ | $(x-1)e^x+C$ |
| $x\\sin x$ | $-x\\cos x+\\sin x+C$ |
| $x\\cos x$ | $x\\sin x+\\cos x+C$ |
| $\\sin^2 x$ | $\\dfrac{x}{2}-\\dfrac{\\sin 2x}{4}+C$ |
| $\\cos^2 x$ | $\\dfrac{x}{2}+\\dfrac{\\sin 2x}{4}+C$ |
| $\\tan^2 x$ | $\\tan x-x+C$ |
| $\\sinh x$ | $\\cosh x+C$ |
| $\\cosh x$ | $\\sinh x+C$ |
| $\\dfrac{1}{x\\ln x}$ | $\\ln\\lvert\\ln x\\rvert+C$ |
| $\\sec^3 x$ | $\\dfrac{1}{2}\\left(\\sec x\\tan x+\\ln\\lvert\\sec x+\\tan x\\rvert\\right)+C$ |
| $\\arctan x$ | $x\\arctan x-\\dfrac{1}{2}\\ln(1+x^2)+C$ |
| $\\arcsin x$ | $x\\arcsin x+\\sqrt{1-x^2}+C$ |

## 使用提示
- 分式、根式先改写为幂函数再积分。
- 遇到三角函数乘积优先考虑积化和差。""",
    ),
    (
        "高等数学",
        "泰勒公式表",
        """## 泰勒展开
$$f(x)=f(a)+f'(a)(x-a)+\\frac{f''(a)}{2!}(x-a)^2+\\cdots+\\frac{f^{(n)}(a)}{n!}(x-a)^n+R_n$$
## 常用麦克劳林展开
| 函数 | 展开式 |
|---|---|
| $e^x$ | $1+x+\\dfrac{x^2}{2!}+\\dfrac{x^3}{3!}+\\dfrac{x^4}{4!}+\\cdots$ |
| $\\ln(1+x)$ | $x-\\dfrac{x^2}{2}+\\dfrac{x^3}{3}-\\dfrac{x^4}{4}+\\cdots$ |
| $\\ln(1-x)$ | $-x-\\dfrac{x^2}{2}-\\dfrac{x^3}{3}-\\cdots$ |
| $\\sin x$ | $x-\\dfrac{x^3}{3!}+\\dfrac{x^5}{5!}-\\dfrac{x^7}{7!}+\\cdots$ |
| $\\cos x$ | $1-\\dfrac{x^2}{2!}+\\dfrac{x^4}{4!}-\\dfrac{x^6}{6!}+\\cdots$ |
| $\\tan x$ | $x+\\dfrac{x^3}{3}+\\dfrac{2x^5}{15}+\\cdots$ |
| $\\arctan x$ | $x-\\dfrac{x^3}{3}+\\dfrac{x^5}{5}-\\dfrac{x^7}{7}+\\cdots$ |
| $\\arcsin x$ | $x+\\dfrac{x^3}{6}+\\dfrac{3x^5}{40}+\\cdots$ |
| $\\dfrac{1}{1-x}$ | $1+x+x^2+x^3+x^4+\\cdots$ |
| $\\dfrac{1}{1+x}$ | $1-x+x^2-x^3+x^4-\\cdots$ |
| $(1+x)^\\alpha$ | $1+\\alpha x+\\dfrac{\\alpha(\\alpha-1)}{2!}x^2+\\dfrac{\\alpha(\\alpha-1)(\\alpha-2)}{3!}x^3+\\cdots$ |
| $\\sinh x$ | $x+\\dfrac{x^3}{3!}+\\dfrac{x^5}{5!}+\\cdots$ |
| $\\cosh x$ | $1+\\dfrac{x^2}{2!}+\\dfrac{x^4}{4!}+\\cdots$ |

## 注意
- 展开点不同公式不同，题目要求在哪点展开就在哪点展开。
- 求极限时先展开到不能抵消的最低阶。""",
    ),
    (
        "高等数学",
        "常用极限与等价无穷小",
        """## 常用极限
$$\\lim_{x\\to0}\\frac{\\sin x}{x}=1$$
$$\\lim_{x\\to0}\\frac{1-\\cos x}{x^2}=\\frac12$$
$$\\lim_{x\\to0}\\frac{\\ln(1+x)}{x}=1$$
$$\\lim_{x\\to0}\\frac{e^x-1}{x}=1$$
$$\\lim_{x\\to0}\\frac{a^x-1}{x}=\\ln a$$
$$\\lim_{x\\to\\infty}\\left(1+\\frac{1}{x}\\right)^x=e$$
$$\\lim_{x\\to0}(1+x)^{\\frac1x}=e$$

## 等价无穷小（$x\\to0$）
| 表达式 | 等价 |
|---|---|
| $\\sin x$ | $x$ |
| $\\tan x$ | $x$ |
| $\\arcsin x$ | $x$ |
| $\\arctan x$ | $x$ |
| $\\ln(1+x)$ | $x$ |
| $e^x-1$ | $x$ |
| $a^x-1$ | $x\\ln a$ |
| $1-\\cos x$ | $\\dfrac{x^2}{2}$ |
| $(1+x)^\\alpha-1$ | $\\alpha x$ |
| $\\sqrt[n]{1+x}-1$ | $\\dfrac{x}{n}$ |
| $x-\\sin x$ | $\\dfrac{x^3}{6}$ |
| $\\tan x-x$ | $\\dfrac{x^3}{3}$ |
| $\\arcsin x-x$ | $\\dfrac{x^3}{6}$ |
| $\\arctan x-x$ | $-\\dfrac{x^3}{3}$ |
| $\\ln(1+x)-x$ | $-\\dfrac{x^2}{2}$ |
| $e^x-1-x$ | $\\dfrac{x^2}{2}$ |

## 注意
- 加减项不能随意整体替换，要判断主部。
- 乘除项可以直接使用等价无穷小。""",
    ),
    (
        "高等数学",
        "三角函数恒等式",
        """## 平方关系
$$\\sin^2 x+\\cos^2 x=1,\\quad 1+\\tan^2 x=\\sec^2 x,\\quad 1+\\cot^2 x=\\csc^2 x$$

## 和差角公式
| 公式 |
|---|
| $\\sin(a+b)=\\sin a\\cos b+\\cos a\\sin b$ |
| $\\sin(a-b)=\\sin a\\cos b-\\cos a\\sin b$ |
| $\\cos(a+b)=\\cos a\\cos b-\\sin a\\sin b$ |
| $\\cos(a-b)=\\cos a\\cos b+\\sin a\\sin b$ |
| $\\tan(a+b)=\\dfrac{\\tan a+\\tan b}{1-\\tan a\\tan b}$ |
| $\\tan(a-b)=\\dfrac{\\tan a-\\tan b}{1+\\tan a\\tan b}$ |

## 倍角与半角
| 公式 |
|---|
| $\\sin 2x=2\\sin x\\cos x$ |
| $\\cos 2x=\\cos^2 x-\\sin^2 x=1-2\\sin^2 x=2\\cos^2 x-1$ |
| $\\tan 2x=\\dfrac{2\\tan x}{1-\\tan^2 x}$ |
| $\\sin^2\\dfrac{x}{2}=\\dfrac{1-\\cos x}{2}$ |
| $\\cos^2\\dfrac{x}{2}=\\dfrac{1+\\cos x}{2}$ |
| $\\tan\\dfrac{x}{2}=\\dfrac{\\sin x}{1+\\cos x}$ |

## 和差化积
| 公式 |
|---|
| $\\sin A+\\sin B=2\\sin\\dfrac{A+B}{2}\\cos\\dfrac{A-B}{2}$ |
| $\\sin A-\\sin B=2\\cos\\dfrac{A+B}{2}\\sin\\dfrac{A-B}{2}$ |
| $\\cos A+\\cos B=2\\cos\\dfrac{A+B}{2}\\cos\\dfrac{A-B}{2}$ |
| $\\cos A-\\cos B=-2\\sin\\dfrac{A+B}{2}\\sin\\dfrac{A-B}{2}$ |

## 积化和差
| 公式 |
|---|
| $\\sin A\\cos B=\\dfrac{1}{2}\\left[\\sin(A+B)+\\sin(A-B)\\right]$ |
| $\\cos A\\sin B=\\dfrac{1}{2}\\left[\\sin(A+B)-\\sin(A-B)\\right]$ |
| $\\cos A\\cos B=\\dfrac{1}{2}\\left[\\cos(A+B)+\\cos(A-B)\\right]$ |
| $\\sin A\\sin B=-\\dfrac{1}{2}\\left[\\cos(A+B)-\\cos(A-B)\\right]$ |""",
    ),
    (
        "线性代数",
        "行列式与矩阵常用公式",
        """## 行列式
$$\\begin{vmatrix} a & b \\\\ c & d \\end{vmatrix}=ad-bc$$
$$\\begin{vmatrix} a_1 & a_2 & a_3 \\\\ b_1 & b_2 & b_3 \\\\ c_1 & c_2 & c_3 \\end{vmatrix}=a_1b_2c_3+a_2b_3c_1+a_3b_1c_2-a_3b_2c_1-a_2b_1c_3-a_1b_3c_2$$

## 伴随矩阵与逆矩阵
$$AA^*=A^*A=\\lvert A\\rvert I,\\quad A^{-1}=\\frac{1}{\\lvert A\\rvert}A^*$$

## 常用运算
| 情形 | 公式 |
|---|---|
| 转置 | $(A+B)^T=A^T+B^T$ |
| 转置 | $(AB)^T=B^T A^T$ |
| 逆矩阵 | $(AB)^{-1}=B^{-1}A^{-1}$ |
| 逆矩阵 | $(A^T)^{-1}=(A^{-1})^T$ |
| 行列式 | $\\lvert AB\\rvert=\\lvert A\\rvert\\lvert B\\rvert$ |
| 行列式 | $\\lvert A^T\\rvert=\\lvert A\\rvert$ |
| 行列式 | $\\lvert kA\\rvert=k^n\\lvert A\\rvert$ |
| 行列式 | $\\lvert A^{-1}\\rvert=\\dfrac{1}{\\lvert A\\rvert}$ |
| 秩 | $r(A+B)\\le r(A)+r(B)$ |
| 秩 | $r(AB)\\le\\min(r(A),r(B))$ |
| 秩 | $r(A)=r(A^T)$ |

## 特征值与相似
- $A\\xi=\\lambda\\xi$，特征方程为 $\\lvert A-\\lambda I\\rvert=0$。
- $A$ 可相似对角化的充要条件：有 $n$ 个线性无关的特征向量。
- $A\\sim B$ 时，$\\lvert A\\rvert=\\lvert B\\rvert$，$r(A)=r(B)$，迹与特征值相同。""",
    ),
    (
        "概率统计",
        "概率统计常用公式",
        """## 概率基本公式
| 公式 | 含义 |
|---|---|
| $P(A\\cup B)=P(A)+P(B)-P(AB)$ | 加法公式 |
| $P(B\\mid A)=\\dfrac{P(AB)}{P(A)}$ | 条件概率 |
| $P(AB)=P(A)P(B\\mid A)$ | 乘法公式 |
| $P(A)=P(A\\mid B)P(B)+P(A\\mid \\bar B)P(\\bar B)$ | 全概率公式 |
| $P(B_i\\mid A)=\\dfrac{P(A\\mid B_i)P(B_i)}{\\sum_j P(A\\mid B_j)P(B_j)}$ | 贝叶斯公式 |

## 期望与方差
| 公式 | 含义 |
|---|---|
| $E(aX+b)=aE(X)+b$ | 线性性质 |
| $E(X+Y)=E(X)+E(Y)$ | 可加性 |
| $E(XY)=E(X)E(Y)$ | $X,Y$ 独立 |
| $D(aX+b)=a^2D(X)$ | 方差性质 |
| $D(X)=E(X^2)-(E(X))^2$ | 方差公式 |
| $D(X\\pm Y)=D(X)+D(Y)\\pm 2\\operatorname{Cov}(X,Y)$ | 协方差 |
| $\\operatorname{Cov}(X,Y)=E(XY)-E(X)E(Y)$ | 协方差定义 |
| $\\rho_{XY}=\\dfrac{\\operatorname{Cov}(X,Y)}{\\sqrt{D(X)D(Y)}}$ | 相关系数 |

## 常用分布
| 分布 | 期望 | 方差 |
|---|---|---|
| 0-1 分布 $B(1,p)$ | $p$ | $p(1-p)$ |
| 二项分布 $B(n,p)$ | $np$ | $np(1-p)$ |
| 泊松分布 $P(\\lambda)$ | $\\lambda$ | $\\lambda$ |
| 均匀分布 $U(a,b)$ | $\\dfrac{a+b}{2}$ | $\\dfrac{(b-a)^2}{12}$ |
| 指数分布 $E(\\lambda)$ | $\\dfrac{1}{\\lambda}$ | $\\dfrac{1}{\\lambda^2}$ |
| 正态分布 $N(\\mu,\\sigma^2)$ | $\\mu$ | $\\sigma^2$ |""",
    ),
    (
        "高等数学",
        "微分方程常用公式",
        """## 一阶方程
| 类型 | 形式 | 解法 |
|---|---|---|
| 可分离变量 | $\\dfrac{dy}{dx}=f(x)g(y)$ | 分离变量后积分 |
| 齐次方程 | $\\dfrac{dy}{dx}=\\varphi\\left(\\dfrac{y}{x}\\right)$ | 令 $u=\\dfrac{y}{x}$ |
| 一阶线性 | $y'+P(x)y=Q(x)$ | $y=e^{-\\int P dx}\\left(\\int Q e^{\\int P dx}dx+C\\right)$ |
| 伯努利 | $y'+P(x)y=Q(x)y^n$ | 令 $u=y^{1-n}$ |

## 二阶常系数线性
特征方程 $r^2+pr+q=0$：
| 根的情况 | 齐次通解 |
|---|---|
| 两个不同实根 | $C_1e^{r_1x}+C_2e^{r_2x}$ |
| 重根 | $(C_1+C_2x)e^{rx}$ |
| 共轭复根 | $e^{\\alpha x}(C_1\\cos\\beta x+C_2\\sin\\beta x)$ |

## 可降阶方程
- $y''=f(x)$：连续积分两次。
- $y''=f(x,y')$：令 $p=y'$。
- $y''=f(y,y')$：令 $p=y'$，把 $y$ 看成自变量。""",
    ),
    (
        "英语背诵",
        "作文常用句型",
        """## 开头句型
| 句型 | 用途 |
|---|---|
| It is widely acknowledged that... | 公认观点 |
| There is a growing concern over... | 表达关注 |
| Recently, the issue of ... has aroused public attention. | 引出话题 |
| As is vividly shown in the picture, ... | 图画作文开头 |
| The chart above reflects a noticeable trend in ... | 图表作文开头 |

## 论证与衔接
| 句型 | 用途 |
|---|---|
| First and foremost, ... What is more, ... | 递进论证 |
| On the one hand, ... On the other hand, ... | 对比论证 |
| For one thing, ... For another, ... | 列举理由 |
| It is undeniable that ... | 承认事实 |
| A case in point is ... | 举例 |
| Consequently, ... / As a result, ... | 表示结果 |

## 结尾句型
| 句型 | 用途 |
|---|---|
| In conclusion, ... | 总结 |
| From my perspective, ... | 个人观点 |
| Only in this way can we ... | 倒装结尾 |
| It is high time that we took effective measures to ... | 呼吁行动 |
| To sum up, the advantages far outweigh the disadvantages. | 利弊总结 |""",
    ),
    (
        "政治背诵",
        "马原核心原理句",
        """## 唯物论
| 原理 | 核心句 |
|---|---|
| 物质与意识 | 物质决定意识，意识对物质具有能动反作用 |
| 客观规律 | 规律是客观的，不以人的意志为转移，要尊重规律 |
| 主观能动性 | 发挥主观能动性要以尊重客观规律为前提 |

## 辩证法
| 原理 | 核心句 |
|---|---|
| 联系 | 世界是普遍联系的，要用联系的观点看问题 |
| 发展 | 发展的实质是新事物代替旧事物 |
| 矛盾 | 矛盾具有普遍性和特殊性，要具体问题具体分析 |
| 主要矛盾 | 抓主要矛盾，同时不忽视次要矛盾 |
| 量变质变 | 量变是质变的必要准备，质变是量变的必然结果 |
| 否定之否定 | 事物发展是前进性与曲折性的统一 |

## 认识论
| 原理 | 核心句 |
|---|---|
| 实践与认识 | 实践是认识的基础、来源、动力和检验标准 |
| 认识过程 | 认识具有反复性、无限性、上升性 |
| 真理 | 真理是客观的、具体的、有条件的 |

## 历史唯物主义
| 原理 | 核心句 |
|---|---|
| 社会存在与社会意识 | 社会存在决定社会意识，社会意识具有相对独立性 |
| 人民群众 | 人民群众是历史的创造者 |
| 生产力与生产关系 | 生产力决定生产关系，生产关系反作用于生产力 |""",
    ),
]
