"""英语生词/短语的收录过滤规则（可复用）。

用户要求：
  · 不要收录**简单词**（system / easy / include / outcome / path / multiple / existing / legally …）
  · 不要把**整句**当短语（"who would make some money and then go home" 这种是句子）
  · 短语应该是**固定搭配**或**词的特殊用法**

设计取舍（说明为什么这么做）：
  · 判断"简单词"最准确的做法是查词频表（如 COCA 前 3000 词）。
    但本机没有词频表、也无法联网下载，所以用**两条保守规则**：
      1) 常见基础词停用表（人工整理，覆盖 the/be/have/go/make 这类与四六级以下常用词）
      2) 长度 <= 4 且不含连字符 —— 对考研词汇来说基本没有收录价值
    规则**宁可漏判也不误杀**：误杀会丢掉学生真正需要的词，代价更高。
  · 判断"句子"用三条：
      1) 词数 > 4（真正需要记的搭配很少超过 4 个词）
      2) 含 "..."（省略号 —— 说明是从原文截断的句子残片）
      3) 首字母大写且 >= 4 词（句子特征）
  · 另外过滤"半截搭配"：以介词开头却没有宾语的（如 "a blessing to" 可以用，
    但 "give up the chance for" 后面缺宾语 —— 这类保留，因为形态上仍像搭配）。
"""

import re

# ── 常见基础词停用表（考研价值低）──────────────────────────────────────
# 说明：这是**保守**清单，只收最基础的高频词，避免误杀真正需要记的词。
BASIC_WORDS = set(
    """
    a an the this that these those i you he she it we they me him her us them my your his its our their
    am is are was were be been being do does did done doing have has had having
    will would shall should can could may might must ought need dare
    and or but so yet for nor if then than as because while when where why how
    in on at to of by with from into onto upon about above below under over between among
    up down out off away back again further once here there all any both each few more most other
    some such no not only own same too very just now also even still already always never
    one two three four five six seven eight nine ten first second third last next
    day days week weeks month months year years time times way ways thing things man men woman women
    people person part parts place places work works life lives world worlds
    go goes going went gone come comes coming came get gets getting got gotten
    make makes making made take takes taking took taken give gives giving gave given
    see sees seeing saw seen look looks looking looked want wants wanted use uses using used
    find finds finding found know knows knowing knew known think thinks thinking thought
    say says saying said tell tells telling told ask asks asking asked
    try tries trying tried call calls calling called keep keeps keeping kept
    let lets letting put puts putting mean means meaning meant
    become becomes becoming became show shows showing showed shown
    hear hears hearing heard play plays playing played run runs running ran
    move moves moving moved live lives living lived believe believes believed
    hold holds holding held bring brings bringing brought happen happens happened
    write writes writing wrote written provide provides providing provided
    sit sits sitting sat stand stands standing stood lose loses losing lost
    pay pays paying paid meet meets meeting met include includes including included
    continue continues continuing continued set sets setting learn learns learning learned
    change changes changing changed lead leads leading led understand understands understood
    watch watches watching watched follow follows following followed stop stops stopped
    create creates creating created speak speaks speaking spoke spoken
    read reads reading remember remembers remembered consider considers considered
    appear appears appeared buy buys buying bought wait waits waiting waited
    serve serves serving served send sends sending sent expect expects expected
    build builds building built stay stays staying stayed fall falls falling fell fallen
    cut cuts cutting reach reaches reaching reached kill kills killing killed
    remain remains remained suggest suggests suggested raise raises raised
    pass passes passing passed sell sells selling sold require requires required
    report reports reported decide decides decided pull pulls pulled
    large small big little long short high low old new young good bad great
    same different important possible able easy hard difficult simple clear sure
    many much more most less least enough several various certain
    system systems easy path paths multiple existing legally accomplish include outcome
    thing problem problems question questions answer answers idea ideas fact facts
    number numbers group groups country countries city cities school schools
    student students teacher teachers friend friends family families
    home homes house houses room rooms door doors hand hands head heads eye eyes
    face faces body bodies mind minds heart hearts water air land
    money job jobs book books word words name names kind kinds type types
    case cases point points end ends side sides line lines course courses
    state states area areas form forms power powers force forces
    begin begins beginning began begun the of to
    """.split()
)

# 明确"句子特征"的助动词/代词（用于判定多词条目是否为句子）
SENTENCE_MARKERS = {
    'i', 'you', 'he', 'she', 'it', 'we', 'they',
    'who', 'which', 'that', 'what', 'when', 'where', 'why', 'how',
    'is', 'are', 'was', 'were', 'be', 'been',
    'will', 'would', 'can', 'could', 'should', 'must', 'may', 'might',
    'do', 'does', 'did', 'have', 'has', 'had',
}

MAX_PHRASE_WORDS = 4


def normalize(text: str) -> str:
    return re.sub(r'\s+', ' ', (text or '').strip())


def is_simple_word(text: str) -> tuple[bool, str]:
    """判断是否为"太简单、不值得收录"的单词。返回 (是否简单, 原因)"""
    w = normalize(text).lower()
    if not w:
        return True, '空'
    if ' ' in w:
        return False, ''  # 多词交给 is_sentence_like
    if w in BASIC_WORDS:
        return True, '基础词停用表'
    # 注意：这里**刻意不做"长度 <= 4 就删"**的判定。
    # 试运行时它误杀了 hurt / tend / lack / rate 这些有价值的考研词；
    # 而 easy / path / system 这类已被上面的停用表覆盖，长度规则并不必要。
    # 过滤规则的原则：**宁可漏判，也不误杀** —— 误杀会丢掉学生真正需要的词。
    return False, ''


def is_sentence_like(text: str) -> tuple[bool, str]:
    """判断多词条目是否其实是**句子**（而不是搭配）。返回 (是否句子, 原因)"""
    t = normalize(text)
    if ' ' not in t:
        return False, ''
    words = t.split()
    # 1) 词数过多
    if len(words) > MAX_PHRASE_WORDS:
        return True, f'词数 {len(words)} > {MAX_PHRASE_WORDS}'
    # 注意：这里**刻意不判省略号**。
    # 试运行时 "hail ... as ..." / "divide ... into ..." / "no less...than" 都被误杀 ——
    # 这些省略号表示**空槽位**，是结构搭配（把…称为…、把…分成…），
    # 恰恰是学生最该记的。用户要清的是**整句**，不是这些模式。
    # 3) 首字母大写且 >= 4 词（句子特征）
    if len(words) >= 4 and t[0].isupper() and t[0].isalpha():
        return True, '首字母大写且 >=4 词（句子特征）'
    # 4) 含句末标点
    # (?<!\.) 排除省略号：否则 "hail ... as ..." 末尾那个点会被当成句末标点
    # （试运行时确实误杀过这一条，它是结构搭配）
    if re.search(r'(?<!\.)[.!?]$', t):
        return True, '含句末标点'
    return False, ''


def is_all_basic(text: str) -> bool:
    """短语里**所有词都是基础词** -> 太简单（如 "go home"、"a lot of"）"""
    words = [re.sub(r'[^a-z]', '', w.lower()) for w in normalize(text).split()]
    words = [w for w in words if w]
    return bool(words) and all(w in BASIC_WORDS for w in words)


def should_reject(word: str, kind: str = '') -> tuple[bool, str]:
    """统一入口：是否应拒绝收录。返回 (是否拒绝, 原因)"""
    t = normalize(word)
    if not t:
        return True, '空'
    if ' ' in t or kind == 'phrase':
        # 这里**刻意不判"整条都是基础词"**：试运行时它误杀了
        # hold up / call out / come down to / all but / in short 这些真正的搭配与习语，
        # 而这些恰恰是最该收录的。宁可漏判，也不误杀。
        return is_sentence_like(t)
    return is_simple_word(t)


if __name__ == '__main__':
    # 自测：确认规则在示例上的判断符合预期
    cases = [
        ('system', 'word'), ('easy', 'word'), ('path', 'word'),
        ('accomplish', 'word'), ('legally', 'word'), ('existing', 'word'),
        ('go home', 'phrase'),
        ('who would make some money and then go home', 'phrase'),
        ('have a job in one place and a family in another', 'phrase'),
        ('change the way we think about categories', 'phrase'),
        ('in one place and ... in another', 'phrase'),
        ('account for', 'phrase'), ('a series of', 'phrase'),
        ('be much more rigid about', 'phrase'),
        ('take into account', 'phrase'),
        ('be subject to', 'phrase'),
    ]
    print(f"{'条目':52s} {'判定':6s} 原因")
    for w, k in cases:
        rej, why = should_reject(w, k)
        print(f'{w[:50]:52s} {"拒绝" if rej else "保留":6s} {why}')
