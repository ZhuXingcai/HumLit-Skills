"""zh_polish.py - 中文学术表达诊断（句级可度量信号）。

脚本只诊断、不改写；Agent 据信号做实际润色，保学术原意、不杜撰。
"""
from __future__ import annotations

import re
from typing import Any, Dict, List

# 口语/非正式词（学术写作宜避免）
_COLLOQUIAL = [
    "其实", "的话", "然后", "挺", "搞", "弄", "东西", "很多很多", "差不多",
    "一下子", "好多", "之类的", "什么的", "反正", "总之就是", "说白了", "其实吧",
]
# 主观第一人称
_SUBJECTIVE = ["我觉得", "我认为", "我想", "我相信", "笔者觉得", "我个人认为", "依我看"]
# 段首逻辑连接/过渡词
_TRANSITIONS = [
    "因此", "然而", "此外", "综上", "首先", "其次", "再次", "最后", "另外",
    "总之", "由此", "进而", "相反", "与此同时", "一方面", "可见", "不过",
    "据此", "基于此", "总体而言", "具体而言", "换言之",
]

_SENT_SPLIT_RE = re.compile(r"[^。！？；!?;]*[。！？；!?;]")
_CJK_RE = re.compile(r"[\u4e00-\u9fff]")
# 中文字符之间夹英文标点（含半角逗号/句号/分号/冒号）
_PUNCT_MIX_RE = re.compile(r"[\u4e00-\u9fff]\s*[,.;:]\s*[\u4e00-\u9fff]")


def split_paragraphs(text: str) -> List[str]:
    parts = re.split(r"\n\s*\n|\n", text or "")
    return [p.strip() for p in parts if p.strip()]


def split_sentences(text: str) -> List[str]:
    sents = [m.group(0).strip() for m in _SENT_SPLIT_RE.finditer(text or "")]
    tail = _SENT_SPLIT_RE.sub("", text or "").strip()
    if tail:
        sents.append(tail)
    return [s for s in sents if s]


def _cjk_len(s: str) -> int:
    return len(_CJK_RE.findall(s))


def _excerpt(s: str, n: int = 40) -> str:
    s = s.strip()
    return s if len(s) <= n else s[:n] + "…"


def diagnose(text: str, max_sentence: int = 80) -> Dict[str, Any]:
    paragraphs = split_paragraphs(text)
    issues: List[Dict[str, Any]] = []
    total_sentences = 0

    for pi, para in enumerate(paragraphs, 1):
        sents = split_sentences(para)
        total_sentences += len(sents)

        # 段首缺逻辑连接（仅多段时提示，首段不强求）
        if pi > 1 and sents:
            first = sents[0]
            if not any(first.lstrip("　 ").startswith(t) for t in _TRANSITIONS):
                issues.append(_issue("weak_transition", f"第{pi}段", _excerpt(sents[0]),
                                     "段首未使用逻辑连接词，段落衔接可能偏弱"))

        # 段内实词重复（≥2 字、出现 ≥4 次）
        words = re.findall(r"[\u4e00-\u9fff]{2,4}", para)
        freq: Dict[str, int] = {}
        for w in words:
            freq[w] = freq.get(w, 0) + 1
        repeated = sorted([w for w, c in freq.items() if c >= 4], key=lambda w: -freq[w])
        if repeated:
            issues.append(_issue("repetition", f"第{pi}段", _excerpt(para),
                                 f"实词高频重复：{('、'.join(repeated[:3]))}（各≥4次）"))

        for si, sent in enumerate(sents, 1):
            loc = f"第{pi}段第{si}句"
            if _cjk_len(sent) > max_sentence:
                issues.append(_issue("long_sentence", loc, _excerpt(sent),
                                     f"句长 {_cjk_len(sent)} 字，超过 {max_sentence}，建议拆分"))
            hit_col = [w for w in _COLLOQUIAL if w in sent]
            if hit_col:
                issues.append(_issue("colloquial", loc, _excerpt(sent),
                                     f"口语词：{('、'.join(hit_col))}"))
            hit_sub = [w for w in _SUBJECTIVE if w in sent]
            if hit_sub:
                issues.append(_issue("subjective", loc, _excerpt(sent),
                                     f"主观表述：{('、'.join(hit_sub))}，学术宜客观"))
            if _PUNCT_MIX_RE.search(sent):
                issues.append(_issue("punct_mix", loc, _excerpt(sent),
                                     "中文句中混用英文标点（,.;:）"))

    by_type: Dict[str, int] = {}
    for i in issues:
        by_type[i["type"]] = by_type.get(i["type"], 0) + 1

    return {
        "summary": {
            "sentences": total_sentences,
            "paragraphs": len(paragraphs),
            "issues": len(issues),
            "by_type": by_type,
        },
        "issues": issues,
    }


def _issue(itype: str, locator: str, excerpt: str, detail: str) -> Dict[str, Any]:
    return {"type": itype, "severity": "warning", "locator": locator,
            "excerpt": excerpt, "detail": detail, "fixable_by_agent": True}
