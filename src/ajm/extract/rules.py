"""命名规则族：截止日期正则 + 分类/字段模板（题面任务 2）。

每条规则具名登记（Evidence.rule_name 可回溯到此处），命中输出原文片段。
规则只做"正则 + 显式锚词"，禁止宽泛兜底（K5：命中不了就 pending）。

日期语义纪律：
- ` deadline_iso / deadline_cn_ymd / deadline_chinese_until` 为**绝对日期**，
  命中即 verified；
- `deadline_relative_from_now`（"自发布之日起 X 天"）为**相对日期**，
  只产出原文片段，日期解析需发布日基准且"之日"起点本身有歧义，
  统一落 pending（证据链保留，不臆测具体日期，K6）。
"""

from __future__ import annotations

import re
from dataclasses import dataclass


# 一条截止日期规则 = 具名正则；命名规范 `deadline_<格式语义>`（plan/06 登记）。
@dataclass(frozen=True, slots=True)
class DeadlineRule:
    name: str
    pattern: re.Pattern[str]
    # 是否可解析为绝对日期（verified）；False 则只留证据、字段 pending。
    absolute: bool = True


_CN_YMD = (
    r"(?P<y>20\d{2})\s*[年./-]\s*(?P<m>1[0-2]|0?[1-9])\s*[月./-]"
    r"\s*(?P<d>3[01]|[12]\d|0?[1-9])\s*日?"
)


def _cn_ymd(suffix: str) -> str:
    """带序号后缀的日期组（同一 pattern 多处内联时避免组名冲突）。"""
    return _CN_YMD.replace("<y>", f"<y{suffix}>").replace("<m>", f"<m{suffix}>").replace(
        "<d>", f"<d{suffix}>"
    )

# 登记顺序即试跑顺序（确定性）：结构化日期 > 显式锚词中文 > 宽松锚词。
RULES: tuple[DeadlineRule, ...] = (
    DeadlineRule(
        name="deadline_iso",
        pattern=re.compile(
            r"(?:报名|申请|投递|简历)?(?:截止|截至)(?:时间|日期)?[：:]?\s*(?P<date>\d{4}-\d{1,2}-\d{1,2})"
            r"|(?P<date2>\d{4}-\d{1,2}-\d{1,2})\s*(?:前|之前|截止)"
        ),
    ),
    DeadlineRule(
        name="deadline_cn_ymd",
        pattern=re.compile(
            r"(?:报名|申请|投递|简历)?(?:截止|截至)(?:时间|日期)?[：:]?\s*" + _cn_ymd("1")
            + r"|" + _cn_ymd("2") + r"\s*(?:前|之前|截止)"
        ),
    ),
    DeadlineRule(
        name="deadline_chinese_until",
        pattern=re.compile(r"即[日时]起\s*至\s*" + _CN_YMD),
    ),
    DeadlineRule(
        # 相对期限：证据保留但日期 pending（起点歧义，K6 不臆测）。
        name="deadline_relative_from_now",
        pattern=re.compile(
            r"(?:自|从)?(?:发布|公布|刊发)之[日时]起\s*\d{1,3}\s*(?:个)?月内|"
            r"(?:自|从)?(?:发布|公布|刊发)之[日时]起\s*\d{1,3}\s*日内|长期有效"
        ),
        absolute=False,
    ),
)


# -- 招聘/非招聘分类模板（pku/nju 首页混入非招聘公告的判定，题面任务 2 职责）---

# 命中任一关键词即视为招聘类公告（证据 rule_name="recruit_keyword"）。
RECRUIT_KEYWORDS: tuple[str, ...] = (
    "招聘",
    "应聘",
    "诚聘",
    "启事",
    "招录",
    "招纳",
    "博士后",
    "岗位聘用",
    "公开招聘",
)

# 显式排除：行政通知类（命中即非招聘，证据 rule_name="non_recruit_keyword"）。
NON_RECRUIT_KEYWORDS: tuple[str, ...] = (
    "通知",
    "培训",
    "评定",
    "认定",
    "申报",
    "名单",
    "反馈",
    "年检",
    "报表",
    "问卷",
)


# -- 字段模板（正文/标题显式锚定；未命中 pending，不猜）-----------------------

# 单位：标题显式后缀锚（"XX大学招聘/启事"句式中的机构名）。
# 贪心量词：复合机构名（"复旦大学全球史研究院"）取最长后缀词 span，不拆成
# "复旦大学"+"全球史研究院"两候选；机构名与招聘锚之间允许夹岗位类别词
# （"2026年北京大学教学科研岗位招聘启事"，类别词 ≤10 字，bench 真值实证句式）。
ORG_TITLE_RE = re.compile(
    r"(?P<org>[\u4e00-\u9fa5A-Za-z0-9（）()]{2,30}(?:大学|学院|研究院|研究所|医院|实验室|中心|学校|集团))"
    r"(?=[，,、\s]*(?:面向|面向社会)?(?:公开)?(?:招聘|2026|20\d{2}|诚聘|人才|启事)"
    r"|[^\u4e00-\u9fa5A-Za-z0-9（）()]{0,6}[\u4e00-\u9fa5A-Za-z0-9（）()]{0,10}?(?:岗位)?(?:公开)?(?:招聘|诚聘|启事|公告))"
)

# 标题句式"2026年度XX大学招聘公告"中的年份前缀不是机构名组成部分。
_ORG_YEAR_PREFIX = re.compile(r"^20\d{2}\s*年度?")


def strip_org_year_prefix(value: str) -> str:
    return _ORG_YEAR_PREFIX.sub("", value).strip() or value

# 学科方向：锚词 + 领域词（限显式锚定，不做宽泛名词兜底）。
# "学科"排除复合词内部命中（"教学科研""跨学科""学科建设"类）；
# "专业/方向"同理防"非专业"类否定语境。
DISCIPLINE_RE = re.compile(
    r"(?:(?<![教本跨])学科|(?:所学|最高学历对应的)?专业(?![课户])|(?:研究)?方向|研究领域)"
    r"(?![建设目录组设置带头审核评估认可])+[为：:\s]*"
    r"(?P<disc>[\u4e00-\u9fa5A-Za-z0-9/、与－\-]{2,40})"
)
# 学科捕获值不得以"岗位招聘/启事/公告"等公告套话结尾（"教学科研岗位"误报源头）。
_DISC_TAIL_TRIM = re.compile(r"(?:岗位)?(?:招聘)?(?:启事|公告)$")

# 待遇：待遇锚词 + 数值/面议。
COMPENSATION_RE = re.compile(
    r"(?:年薪|薪酬|待遇|薪资)[：:\s]*(?P<comp>[^，。;；\s]{1,40})"
    r"|(?:年薪|待遇)[^，。;；\s]{0,6}[为是]?\s*(?P<comp2>[^，。;；\s]{2,40}?)(?:[，。;；]|$)"
)

# 岗位名称：标题锚（"招聘XX""诚聘XX""聘XX"）；排除"聘用/聘任/解聘/返聘"
# （行政人事动作，非岗位名，"岗位聘用工作的通知"误报源头）；
# "招聘"后跟"启事/公告/邮箱"属公告句式而非岗位名，不取。
POSITION_TITLE_RE = re.compile(
    r"(?:招聘|诚聘|(?<![聘解返])聘(?!用|任))[：:]?\s*"
    r"(?!(?:启事|公告|时间|流程|范围|条件|岗位))"
    r"(?P<pos>[\u4e00-\u9fa5A-Za-z0-9/、（）()\-]{2,30})"
)
