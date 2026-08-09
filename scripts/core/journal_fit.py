"""journal_fit.py - 中文期刊（C刊/北大核心等）投稿适配自查。

脚本负责确定性的投稿适配信号计算（篇幅/摘要/关键词/参考文献）与匿名化泄露
扫描；Agent 负责据信号给修改建议、做匿名化删改判断（脚本不自动改写正文）。
"""
from __future__ import annotations

import copy
import re
from typing import Any, Dict, List, Optional

SCHEMA_VERSION = "1.0"

DEFAULT_PROFILE: Dict[str, Any] = {
    "schema_version": SCHEMA_VERSION,
    "name": "通用中文期刊投稿要求（内置默认）",
    "journal_system": "CSSCI",  # 提示用，取值见 references/core-journals.md
    "length": {"min_chars": 8000, "max_chars": 15000, "scope": "body_only"},
    "abstract": {"min_chars": 200, "max_chars": 300, "require_en": True},
    "keywords": {"min": 3, "max": 8},
    "references": {"min": 10, "style": "gbt7714"},
    "anonymous": True,  # 是否匿名送审（盲审），True 时泄露项视为 error
}


def build_template() -> Dict[str, Any]:
    """返回可直接编辑的投稿要求模板（深拷贝默认值，含说明）。"""
    tpl = copy.deepcopy(DEFAULT_PROFILE)
    tpl["_README"] = ("由 Agent 按目标期刊《投稿须知》填写：length 正文字数区间、"
                      "abstract 摘要字数区间与是否需英文摘要、keywords 关键词数区间、"
                      "references 参考文献数下限与体例、anonymous 是否匿名送审。"
                      "字段含义见 static/fragments/task/journal-fit.md。下划线字段为说明，校验时忽略。")
    return tpl


def _deep_merge(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    out = dict(base)
    for k, v in override.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def load_profile(path: str) -> Dict[str, Any]:
    """读 profile JSON 并用默认值补齐缺省字段（宽进严出）。"""
    import json
    from pathlib import Path
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("profile 顶层必须是 JSON 对象")
    return _deep_merge(copy.deepcopy(DEFAULT_PROFILE), raw)


def _check_range(d: Any, lo_key: str, hi_key: str, field: str, errors: List[Dict[str, str]]) -> None:
    if not isinstance(d, dict):
        return
    lo, hi = d.get(lo_key), d.get(hi_key)
    if isinstance(lo, (int, float)) and isinstance(hi, (int, float)) and lo > hi:
        errors.append({"field": field, "message": f"{lo_key} 不得大于 {hi_key}"})


def validate_profile(p: Any) -> List[Dict[str, str]]:
    """校验 profile，返回错误列表（空列表即合法）。下划线字段忽略。"""
    errors: List[Dict[str, str]] = []
    if not isinstance(p, dict):
        return [{"field": "<root>", "message": "profile 顶层必须是 JSON 对象"}]
    if not p.get("schema_version"):
        errors.append({"field": "schema_version", "message": "缺少 schema_version"})

    _check_range(p.get("length"), "min_chars", "max_chars", "length", errors)
    _check_range(p.get("abstract"), "min_chars", "max_chars", "abstract", errors)
    _check_range(p.get("keywords"), "min", "max", "keywords", errors)

    anon = p.get("anonymous")
    if anon is not None and not isinstance(anon, bool):
        errors.append({"field": "anonymous", "message": "anonymous 必须是 true/false"})

    return errors


# ── 计数与抽取 ───────────────────────────────────────────

_CJK_RE = re.compile(r"[\u4e00-\u9fff]")
_ALNUM_RE = re.compile(r"[A-Za-z0-9]")


def count_chars(text: str) -> int:
    """统计中文字符 + 英文字母 + 阿拉伯数字（不含空白与标点）。"""
    if not text:
        return 0
    return len(_CJK_RE.findall(text)) + len(_ALNUM_RE.findall(text))


_ABSTRACT_HEAD_RE = re.compile(r"^\s*#*\s*(摘\s*要|内容摘要)\s*[:：]?\s*", re.MULTILINE)
_EN_ABSTRACT_HEAD_RE = re.compile(r"^\s*#*\s*(abstract)\s*[:：]?\s*", re.IGNORECASE | re.MULTILINE)
_KEYWORDS_HEAD_RE = re.compile(r"^\s*#*\s*(关\s*键\s*词|关键字)\s*[:：]?\s*", re.MULTILINE)
_EN_KEYWORDS_HEAD_RE = re.compile(r"^\s*#*\s*(key\s*words?)\s*[:：]?\s*", re.IGNORECASE | re.MULTILINE)
_SECTION_BREAK_RE = re.compile(r"\n\s*\n|\n\s*#")


def _slice_after(text: str, head_match) -> str:
    """从某标题匹配结束位置切到下一个空行/标题/结尾。"""
    start = head_match.end()
    rest = text[start:]
    brk = _SECTION_BREAK_RE.search(rest)
    return (rest[:brk.start()] if brk else rest).strip()


def extract_abstract(text: str) -> Dict[str, Any]:
    """抽取中文摘要正文与是否含英文摘要。返回 {text, chars, has_en}。"""
    zh = ""
    m = _ABSTRACT_HEAD_RE.search(text or "")
    if m:
        zh = _slice_after(text, m)
    has_en = bool(_EN_ABSTRACT_HEAD_RE.search(text or ""))
    return {"text": zh, "chars": count_chars(zh), "has_en": has_en}


def extract_keywords(text: str) -> List[str]:
    """抽取中文关键词条目列表（按；;，,/ 空白切分）。"""
    m = _KEYWORDS_HEAD_RE.search(text or "")
    if not m:
        return []
    seg = _slice_after(text, m)
    parts = re.split(r"[；;，,、/\s]+", seg)
    return [p.strip() for p in parts if p.strip()]


def count_references(model: Any) -> int:
    """复用 DocModel.references 计数；无则 0。"""
    refs = getattr(model, "references", None)
    return len(refs) if refs else 0


_REFERENCE_HEADING = r"参\s*考\s*文\s*献|References?"
_ACK_HEADING = r"致\s*谢|Acknowledgements?"
_APPENDIX_HEADING = r"附\s*录|Appendix"
_NUMBERED_HEADING_PREFIX = r"(?:[一二三四五六七八九十\d]+[、.．]\s*)?"
_CN_HEADING_SUFFIX = r"(?:\s*[:：].*|\s*[（(].*[）)]|\s+[\u4e00-\u9fff].*)?"
_EN_HEADING_SUFFIX = r"(?:\s*[:：].*|\s*[（(].*[）)]|\s+(?:cited|list|bibliography|section|appendix)\b.*)?"
_REFERENCE_OR_ACK_HEADING = (
    rf"(?:致\s*谢|参\s*考\s*文\s*献){_CN_HEADING_SUFFIX}|"
    rf"(?:References?|Acknowledgements?){_EN_HEADING_SUFFIX}"
)
_APPENDIX_HEADING_FULL = (
    rf"附\s*录\s*[A-Za-z一二三四五六七八九十\d]*.*|"
    rf"Appendix(?:\s+(?:[A-Za-z]|\d+)(?:\s*[:：].*|\s+.*|\s*)|\s*[:：].*|\s*[（(].*[）)]|\s*$)"
)
_STOP_HEADING = (
    rf"{_NUMBERED_HEADING_PREFIX}(?:"
    rf"{_REFERENCE_OR_ACK_HEADING}|"
    rf"{_APPENDIX_HEADING_FULL}"
    rf")"
)
_SECTION_LINE_RE = re.compile(
    rf"^\s*#*\s*(摘\s*要|内容摘要|Abstract|ABSTRACT|关\s*键\s*词|关键字|目\s*录|{_STOP_HEADING})\s*[:：]?\s*$",
    re.IGNORECASE | re.MULTILINE,
)
_METADATA_LINE_RE = re.compile(
    r"^\s*#*\s*(摘\s*要|内容摘要|Abstract|ABSTRACT|关\s*键\s*词|关键字|key\s*words?|目\s*录)\s*[:：].*$",
    re.IGNORECASE,
)
_FRONT_MATTER_HEAD_RE = re.compile(
    r"^\s*#*\s*(摘\s*要|内容摘要|Abstract|ABSTRACT|关\s*键\s*词|关键字|key\s*words?)\s*[:：]?",
    re.IGNORECASE | re.MULTILINE,
)
_NON_BODY_HEADING = (
    r"(?:摘\s*要|内容摘要|Abstract|ABSTRACT|关\s*键\s*词|关键字|key\s*words?|"
    rf"目\s*录|{_STOP_HEADING})"
)
_UNNUMBERED_BODY_HEADING = r"引言|绪论|研究方法|材料与方法|方法|结果|讨论|结论|正文"
_BODY_START_RE = re.compile(
    rf"^\s*#*\s*(?!(?:{_NON_BODY_HEADING})\s*$)"
    rf"(?:"
    rf"(?:[一二三四五六七八九十]+、|\d+[.．、])\s*(?!(?:{_NON_BODY_HEADING})\s*$).+"
    rf"|[（(][一二三四五六七八九十\d]+[）)]\s*(?!(?:{_NON_BODY_HEADING})\s*$).+"
    rf"|第[一二三四五六七八九十\d]+[章节篇](?:\s*.+)?"
    rf"|(?:{_UNNUMBERED_BODY_HEADING})(?:\s*[:：].*|\s+.*)?"
    rf")\s*$",
    re.IGNORECASE | re.MULTILINE,
)
_BODY_STOP_RE = re.compile(
    rf"^\s*#*\s*(?:{_STOP_HEADING})$",
    re.IGNORECASE | re.MULTILINE,
)


def _line_end(text: str, start: int) -> int:
    end = text.find("\n", start)
    return len(text) if end == -1 else end


def _next_line_start(text: str, line_end: int) -> int:
    return line_end if line_end >= len(text) else line_end + 1


def _front_matter_block_end(text: str, head_match) -> int:
    line_end = _line_end(text, head_match.start())
    if text[head_match.end():line_end].strip():
        return _next_line_start(text, line_end)

    pos = _next_line_start(text, line_end)
    while pos < len(text):
        end = _line_end(text, pos)
        line = text[pos:end].strip()
        if not line:
            return _next_line_start(text, end)
        if _FRONT_MATTER_HEAD_RE.match(line) or _SECTION_LINE_RE.match(line):
            return pos
        pos = _next_line_start(text, end)
    return len(text)


def _fallback_body_start(text: str) -> int:
    start = 0
    for match in _FRONT_MATTER_HEAD_RE.finditer(text):
        start = max(start, _front_matter_block_end(text, match))
    return start


def extract_body_text(text: str) -> str:
    """抽取投稿正文字段，默认排除摘要、关键词、致谢、参考文献和附录。"""
    text = text or ""
    start_match = _BODY_START_RE.search(text)
    start = start_match.start() if start_match else _fallback_body_start(text)
    rest = text[start:]
    stop_match = _BODY_STOP_RE.search(rest)
    if stop_match:
        rest = rest[:stop_match.start()]

    lines = []
    skip_next = False
    for line in rest.splitlines():
        stripped = line.strip()
        if _SECTION_LINE_RE.match(stripped):
            skip_next = True
            continue
        if _METADATA_LINE_RE.match(stripped):
            continue
        if skip_next:
            skip_next = False
            continue
        lines.append(line)
    return "\n".join(lines).strip()


# ── 匿名化泄露扫描 ───────────────────────────────────────

_GRANT_PAREN_RE = re.compile(r"[（(]\s*([0-9A-Za-z][0-9A-Za-z\-]{3,})\s*[）)]")
_GRANT_NO_RE = re.compile(r"\b[Nn]o\.?\s*([0-9A-Za-z\-]{4,})")
_FUND_KW_RE = re.compile(r"(基金|资助|grant|funded|supported by)", re.IGNORECASE)
_FUND_KW2_RE = re.compile(r"(项目|课题|计划|批准号|编号|项目号|基金号)")
_ACK_HEAD_RE = re.compile(r"(^|\n)\s*#*\s*致\s*谢")
_ACK_NAMED_RE = re.compile(r"感\s*谢[^，。；！\n]{0,12}(教授|老师|先生|导师|研究员|博士|院士)")
_AUTHOR_INFO_RE = re.compile(r"(作者简介|作者单位|通讯作者|通信作者|第一作者[:：])")
_SELF_INST_RE = re.compile(
    r"(本人|笔者|本文作者|我校)[^。；\n]{0,10}(所在|就读|任职|供职|来自)?[^。；\n]{0,12}(大学|学院|研究所|研究院|学校)"
)


def _has_digit_and_alpha(s: str) -> bool:
    return bool(re.search(r"[0-9]", s)) and bool(re.search(r"[A-Za-z]", s))


def _excerpt(text: str, start: int, end: int, pad: int = 12) -> str:
    a = max(0, start - pad)
    b = min(len(text), end + pad)
    snippet = text[a:b].replace("\n", " ").strip()
    return ("…" if a > 0 else "") + snippet + ("…" if b < len(text) else "")


def _find_grant_code(text: str):
    for m in _GRANT_PAREN_RE.finditer(text):
        if _has_digit_and_alpha(m.group(1)):
            return m
    for m in _GRANT_NO_RE.finditer(text):
        if re.search(r"[0-9]", m.group(1)):
            return m
    return None


def detect_anonymity_leaks(text: str) -> List[Dict[str, Any]]:
    """扫描匿名送审需移除的自我指认信息。返回泄露清单（不含 severity，由上层据 anonymous 赋值）。"""
    text = text or ""
    leaks: List[Dict[str, Any]] = []

    grant = _find_grant_code(text)
    fund_kw = _FUND_KW_RE.search(text) and _FUND_KW2_RE.search(text)
    if grant or fund_kw:
        m = grant or _FUND_KW_RE.search(text)
        leaks.append({"type": "fund_leak", "locator": "全文",
                      "excerpt": _excerpt(text, m.start(), m.end()),
                      "detail": "疑似基金项目号/资助信息，匿名送审需移除", "fixable_by_agent": True})

    m = _ACK_NAMED_RE.search(text) or _ACK_HEAD_RE.search(text)
    if m:
        leaks.append({"type": "ack_named", "locator": "全文",
                      "excerpt": _excerpt(text, m.start(), m.end()),
                      "detail": "疑似具名致谢，匿名送审需移除或匿名化", "fixable_by_agent": True})

    m = _AUTHOR_INFO_RE.search(text)
    if m:
        leaks.append({"type": "author_info", "locator": "全文",
                      "excerpt": _excerpt(text, m.start(), m.end()),
                      "detail": "疑似作者简介/单位/通讯作者信息，匿名送审需移除", "fixable_by_agent": True})

    m = _SELF_INST_RE.search(text)
    if m:
        leaks.append({"type": "self_institution", "locator": "全文",
                      "excerpt": _excerpt(text, m.start(), m.end()),
                      "detail": "疑似自我指认所在机构，匿名送审需改为中性表述", "fixable_by_agent": True})

    return leaks


# ── 汇总 ─────────────────────────────────────────────────

def _range_metric(value: int, lo, hi) -> Dict[str, Any]:
    ok = True
    if isinstance(lo, (int, float)) and value < lo:
        ok = False
    if isinstance(hi, (int, float)) and value > hi:
        ok = False
    out: Dict[str, Any] = {"value": value, "ok": ok}
    if lo is not None:
        out["min"] = lo
    if hi is not None:
        out["max"] = hi
    return out


def check_journal_fit(text: str, model: Any, profile: Dict[str, Any]) -> Dict[str, Any]:
    """汇总投稿适配 metrics + issues + 匿名泄露。"""
    text = text or ""
    length_cfg = profile.get("length") or {}
    abs_cfg = profile.get("abstract") or {}
    kw_cfg = profile.get("keywords") or {}
    ref_cfg = profile.get("references") or {}
    anonymous = bool(profile.get("anonymous"))

    total_chars = count_chars(text)
    length_scope = (length_cfg.get("scope") or "body_only").lower()
    body_text = text if length_scope == "total" else extract_body_text(text)
    body_chars = count_chars(body_text)
    abstract = extract_abstract(text)
    keywords = extract_keywords(text)
    refs = count_references(model)

    length_m = _range_metric(body_chars, length_cfg.get("min_chars"), length_cfg.get("max_chars"))
    length_m["scope"] = length_scope
    abstract_m = _range_metric(abstract["chars"], abs_cfg.get("min_chars"), abs_cfg.get("max_chars"))
    abstract_m["has_en"] = abstract["has_en"]
    keywords_m = _range_metric(len(keywords), kw_cfg.get("min"), kw_cfg.get("max"))
    references_m = _range_metric(refs, ref_cfg.get("min"), None)

    issues: List[Dict[str, Any]] = []

    def add(t: str, detail: str):
        issues.append({"type": t, "severity": "warning", "detail": detail, "fixable_by_agent": True})

    if isinstance(length_cfg.get("min_chars"), (int, float)) and body_chars < length_cfg["min_chars"]:
        add("length_below_min", f"正文 {body_chars} 字，低于下限 {length_cfg['min_chars']} 字")
    if isinstance(length_cfg.get("max_chars"), (int, float)) and body_chars > length_cfg["max_chars"]:
        add("length_above_max", f"正文 {body_chars} 字，超过上限 {length_cfg['max_chars']} 字")
    if isinstance(abs_cfg.get("min_chars"), (int, float)) and abstract["chars"] < abs_cfg["min_chars"]:
        add("abstract_below_min", f"摘要 {abstract['chars']} 字，低于下限 {abs_cfg['min_chars']} 字")
    if isinstance(abs_cfg.get("max_chars"), (int, float)) and abstract["chars"] > abs_cfg["max_chars"]:
        add("abstract_above_max", f"摘要 {abstract['chars']} 字，超过上限 {abs_cfg['max_chars']} 字")
    if abs_cfg.get("require_en") and not abstract["has_en"]:
        add("abstract_missing_en", "要求含英文摘要（Abstract）但未检出")
    if isinstance(kw_cfg.get("min"), (int, float)) and len(keywords) < kw_cfg["min"]:
        add("keywords_below_min", f"关键词 {len(keywords)} 个，低于下限 {kw_cfg['min']} 个")
    if isinstance(kw_cfg.get("max"), (int, float)) and len(keywords) > kw_cfg["max"]:
        add("keywords_above_max", f"关键词 {len(keywords)} 个，超过上限 {kw_cfg['max']} 个")
    if isinstance(ref_cfg.get("min"), (int, float)) and refs < ref_cfg["min"]:
        add("references_below_min", f"参考文献 {refs} 条，低于下限 {ref_cfg['min']} 条")

    leaks = detect_anonymity_leaks(text)
    severity = "error" if anonymous else "warning"
    for lk in leaks:
        lk["severity"] = severity

    return {
        "summary": {
            "body_chars": body_chars, "total_chars": total_chars,
            "length_scope": length_scope,
            "abstract_chars": abstract["chars"],
            "keywords": len(keywords), "references": refs,
            "issues": len(issues), "leaks": len(leaks),
        },
        "metrics": {
            "length": length_m, "abstract": abstract_m,
            "keywords": keywords_m, "references": references_m,
        },
        "issues": issues,
        "anonymity": {"required": anonymous, "leaks": leaks},
    }
