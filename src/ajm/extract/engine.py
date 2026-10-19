"""确定性抽取引擎：RawItem → JobPosting（题面任务 2）。

确定性契约：
- 同一输入恒定输出：规则按 rules.RULES 登记序试跑，结构化字段映射优先于正文正则；
- 未命中 → ExtractedField.unextracted（status=pending），绝不臆测（K6）；
- 多候选 → candidates 全保留 + ambiguous，不静默取第一个；
- 每个非 pending 字段必带 Evidence(rule_name, snippet)。
"""

from __future__ import annotations

import re
from datetime import date

from ajm.config import FieldStatus, SourceId  # noqa: F401  (SourceId 复导出给编排层)
from ajm.models import (
    Evidence,
    ExtractedField,
    JobPosting,
    RawItem,
    content_hash,
    strip_update_suffix,
)

from . import rules

_SNIPPET_RADIUS = 30  # 证据片段：命中位置前后各保留的字符数


def _snippet(text: str, start: int, end: int) -> str:
    lo = max(0, start - _SNIPPET_RADIUS)
    hi = min(len(text), end + _SNIPPET_RADIUS)
    return text[lo:hi].replace("\n", " ").strip()


# 标题句式"招聘<N>名<岗位名>"中的招聘人数前缀不是岗位名组成部分（真值标注口径）。
_HEADCOUNT_PREFIX = re.compile(r"^\d+\s*名")


def _strip_headcount(value: str) -> str:
    return _HEADCOUNT_PREFIX.sub("", value).strip(" ：:，,、") or value


def _resolve_date(m: str) -> date | None:
    """归一化 Y/M/D 为 date；非法组合（如 13 月）返回 None → pending，不臆测。"""
    parts = re.split(r"[-/.]", m) if "-" in m or "/" in m or "." in m else []
    if parts:
        y, mo, d = (int(p) for p in parts)
    else:
        return None
    try:
        return date(y, mo, d)
    except ValueError:
        return None


def _resolve_cn_date(match: re.Match[str]) -> date | None:
    """中文日期组解析：优先 y1/m1/d1（截止锚在前），回退 y2/m2/d2（日期在前），
    deadline_chinese_until 用 y/m/d。缺失组名安全跳过（groupdict 而非 group）。"""
    gd = match.groupdict()
    for suffix in ("1", "2", ""):
        y, m, d = gd.get(f"y{suffix}"), gd.get(f"m{suffix}"), gd.get(f"d{suffix}")
        if y is not None:
            try:
                return date(int(y), int(m or "1"), int(d or "1"))
            except ValueError:
                return None  # 非法日期（如 2 月 30 日）不臆测
    return None


def _deadline_from_text(text: str) -> ExtractedField:
    for rule in rules.RULES:
        if not rule.absolute:
            match = rule.pattern.search(text)
            if match is not None:
                # 相对期限：证据保留，日期 pending（起点歧义，K6）。
                return ExtractedField(
                    name="deadline",
                    status=FieldStatus.PENDING,
                    evidence=Evidence(
                        rule_name=rule.name, snippet=_snippet(text, match.start(), match.end())
                    ),
                )
            continue
        hits: list[tuple[date, re.Match[str]]] = []
        for match in rule.pattern.finditer(text):
            groups = match.groupdict()
            raw = groups.get("date") or groups.get("date2") or ""
            value = _resolve_date(raw) if raw else _resolve_cn_date(match)
            if value is not None:
                hits.append((value, match))
            # 非法日期（如 2 月 30 日）→ 跳过该命中，继续找
        if not hits:
            continue
        values = sorted({v.isoformat() for v, _ in hits})
        evidence = Evidence(
            rule_name=rule.name, snippet=_snippet(text, hits[0][1].start(), hits[-1][1].end())
        )
        if len(values) == 1:
            return ExtractedField(
                name="deadline",
                status=FieldStatus.VERIFIED,
                value=values[0],
                evidence=evidence,
            )
        # 多候选并存 → 全保留 + ambiguous，不静默取第一个（题面纪律）
        return ExtractedField(
            name="deadline",
            status=FieldStatus.VERIFIED,
            value=None,
            candidates=values,
            ambiguous=True,
            evidence=evidence,
        )
    return ExtractedField.unextracted("deadline")


def _unique(candidates: list[str]) -> list[str]:
    seen: set[str] = set()
    out = []
    for c in candidates:
        if c not in seen:
            seen.add(c)
            out.append(c)
    return out


def _from_candidates(
    name: str, candidates: list[str], rule_name: str, snippet: str
) -> ExtractedField:
    """多候选全保留：1 个 → verified；多个 → 全保留 + ambiguous（不静默取第一个）。"""
    uniq = _unique(candidates)
    if not uniq:
        return ExtractedField.unextracted(name)
    if len(uniq) == 1:
        return ExtractedField(
            name=name,
            status=FieldStatus.VERIFIED,
            value=uniq[0],
            evidence=Evidence(rule_name=rule_name, snippet=snippet),
        )
    return ExtractedField(
        name=name,
        status=FieldStatus.VERIFIED,
        value=None,
        candidates=uniq,
        ambiguous=True,
        evidence=Evidence(rule_name=rule_name, snippet=snippet),
    )


def _structured_fields(item: RawItem) -> dict[str, ExtractedField]:
    """适配器在页面上直接看到的结构化值（extra）→ verified 字段。

    证据即页面原文：rule_name="structured_<key>"，snippet 为原值本身。
    """
    out: dict[str, ExtractedField] = {}
    mapping = {
        "position": "position",
        "org": "organization",
        "discipline": "discipline",
        "compensation": "compensation",
    }
    for key, field_name in mapping.items():
        value = item.extra.get(key, "").strip()
        if value:  # "面议"也是有效待遇值，照常收
            out[field_name] = ExtractedField(
                name=field_name,
                status=FieldStatus.VERIFIED,
                value=value,
                evidence=Evidence(rule_name=f"structured_{key}", snippet=value),
            )
    return out


def is_recruitment(item: RawItem) -> bool | None:
    """招聘/非招聘分类（pku/nju 首页混入通知的判定）。

    返回 None = 规则未命中（不可判定，调用方决定是否保留条目）。
    显式排除词优先于包含词（"招聘工作的通知"是非招聘）。
    """
    title = item.title
    for kw in rules.NON_RECRUIT_KEYWORDS:
        if kw in title:
            return False
    for kw in rules.RECRUIT_KEYWORDS:
        if kw in title:
            return True
    return None


def extract_posting(item: RawItem, body_text: str = "") -> JobPosting:
    """RawItem（+ 可选详情页正文）→ JobPosting。

    分类未判定（None）的条目照常抽取，字段照常走 pending 门控——
    分类语义交由调用方（snapshot 编排层）决定是否入库，引擎不丢数据。
    """
    title = item.title
    body = body_text or ""
    search_text = f"{title}\n{body}" if body else title

    structured = _structured_fields(item)

    # 岗位：extra 结构化 > 标题锚（岗位名是标题层信息；正文"招聘"词易误挂截止
    # 句式，bench 真值 dry-run 实证——position 锚不扫正文，M4 口径，plan/06 登记）。
    if "position" in structured:
        position = structured["position"]
    else:
        cands = [
            _strip_headcount(m.group("pos").strip(" ：:，,、"))
            for m in rules.POSITION_TITLE_RE.finditer(title)
        ]
        cands = [c for c in cands if len(c) >= 2]
        pos_span = rules.POSITION_TITLE_RE.search(title)
        position = (
            _from_candidates(
                "position", cands, "position_title_anchor",
                _snippet(title, pos_span.start(), pos_span.end()) if pos_span else "",
            )
            if cands
            else ExtractedField.unextracted("position")
        )

    # 单位：extra > 标题机构后缀锚（同为标题层信息，不扫正文；年份前缀剥离）
    if "organization" in structured:
        organization = structured["organization"]
    else:
        cands = [
            rules.strip_org_year_prefix(m.group("org"))
            for m in rules.ORG_TITLE_RE.finditer(title)
        ]
        org_span = rules.ORG_TITLE_RE.search(title)
        organization = (
            _from_candidates(
                "organization", cands, "org_title_anchor",
                _snippet(title, org_span.start(), org_span.end()) if org_span else "",
            )
            if cands
            else ExtractedField.unextracted("organization")
        )

    # 学科方向：extra > 正文/标题锚
    if "discipline" in structured:
        discipline = structured["discipline"]
    else:
        cands = [
            rules._DISC_TAIL_TRIM.sub("", m.group("disc")).strip(" ：:，。、")  # noqa: SLF001
            for m in rules.DISCIPLINE_RE.finditer(search_text)
        ]
        cands = [c for c in cands if len(c) >= 2]
        disc_span = rules.DISCIPLINE_RE.search(search_text)
        discipline = (
            _from_candidates(
                "discipline", cands, "discipline_anchor",
                _snippet(search_text, disc_span.start(), disc_span.end()) if disc_span else "",
            )
            if cands
            else ExtractedField.unextracted("discipline")
        )

    # 待遇：extra > 正文/标题锚
    if "compensation" in structured:
        compensation = structured["compensation"]
    else:
        cands = [
            (m.group("comp") or m.group("comp2") or "").strip(" ：:，。、")
            for m in rules.COMPENSATION_RE.finditer(search_text)
        ]
        cands = [c for c in cands if c]
        comp_span = rules.COMPENSATION_RE.search(search_text)
        compensation = (
            _from_candidates(
                "compensation", cands, "compensation_anchor",
                _snippet(search_text, comp_span.start(), comp_span.end()) if comp_span else "",
            )
            if cands
            else ExtractedField.unextracted("compensation")
        )

    # 截止日期：只走命名规则族（正文优先，标题次之）
    deadline = _deadline_from_text(search_text)

    # content_hash 基于归一化正文 + 剥离"（更新）"后的标题
    # （pku 边界：更新型条目的后缀不是内容变更，M1 预警口径）。
    hash_title = strip_update_suffix(title)
    hash_text = f"{hash_title}\n{body}".strip()
    posting = JobPosting(
        url=item.url,
        source=item.source,
        title=title,
        published_on=item.published_on,
        position=position,
        organization=organization,
        discipline=discipline,
        compensation=compensation,
        deadline=deadline,
        body_text=body,
        content_hash=content_hash(hash_text),
    )
    return posting
