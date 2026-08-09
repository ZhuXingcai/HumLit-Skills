"""theory_catalog.py - 人文社科常用理论框架检索库。

脚本提供 curated 理论库的确定性检索与关键词匹配（可查、可列），Agent 负责
理论适配判断、框架搭建、与研究问题的对接（理论选择是学术判断，非脚本能定）。

内置库为常用理论精选（非穷举），数据与 references/theory-frameworks.md 同步；
用户可用 --library 叠加自定义条目。
"""
from __future__ import annotations

import copy
from typing import Any, Dict, List, Optional

DISCIPLINES = [
    "社会学", "政治学", "传播学", "教育学", "管理学",
    "经济学", "心理学", "人类学", "法学", "哲学",
]

REQUIRED_THEORY_FIELDS = ("id", "name", "discipline", "keywords", "summary")

THEORIES: List[Dict[str, Any]] = [
    {"id": "social_capital", "name": "社会资本理论", "proposer": "布迪厄/科尔曼/帕特南",
     "discipline": "社会学",
     "concepts": ["社会网络", "信任", "互惠", "公民参与"],
     "keywords": ["社会资本", "社会网络", "信任", "互惠", "公民参与", "社团"],
     "summary": "个体或群体通过社会关系网络获取的资源，强调信任与互惠规范对集体行动的促进。",
     "key_refs": ["Bourdieu 1986《资本的形式》", "Putnam 2000《独自打保龄》"]},
    {"id": "weak_ties", "name": "弱关系/嵌入性理论", "proposer": "格兰诺维特",
     "discipline": "社会学",
     "concepts": ["弱关系", "强关系", "结构洞", "嵌入性"],
     "keywords": ["弱关系", "强关系", "嵌入性", "结构洞", "求职", "信息流动"],
     "summary": "弱关系在信息传递与机会获取中常比强关系更有效；经济行为嵌入于社会关系网络。",
     "key_refs": ["Granovetter 1973《弱关系的力量》", "Granovetter 1985《嵌入性》"]},
    {"id": "field_habitus", "name": "场域-惯习理论", "proposer": "布迪厄",
     "discipline": "社会学",
     "concepts": ["场域", "惯习", "文化资本", "符号暴力"],
     "keywords": ["场域", "惯习", "文化资本", "符号暴力", "区隔", "再生产"],
     "summary": "社会空间由相对自主的场域构成，行动者的惯习与各类资本共同塑造实践与社会区隔。",
     "key_refs": ["Bourdieu 1984《区分》"]},
    {"id": "structuration", "name": "结构化理论", "proposer": "吉登斯",
     "discipline": "社会学",
     "concepts": ["结构二重性", "能动性", "规则与资源"],
     "keywords": ["结构化", "结构二重性", "能动性", "结构", "规则", "资源"],
     "summary": "结构既是行动的中介也是结果（结构二重性），调和了能动与结构的二元对立。",
     "key_refs": ["Giddens 1984《社会的构成》"]},
    {"id": "risk_society", "name": "风险社会理论", "proposer": "贝克",
     "discipline": "社会学",
     "concepts": ["风险社会", "自反性现代化", "个体化"],
     "keywords": ["风险社会", "风险", "自反性", "现代化", "个体化", "不确定性"],
     "summary": "现代化自身制造出难以计算的系统性风险，社会进入自反性现代化阶段。",
     "key_refs": ["Beck 1992《风险社会》"]},
    {"id": "labeling", "name": "标签理论", "proposer": "贝克尔/莱默特",
     "discipline": "社会学",
     "concepts": ["越轨", "污名", "标签", "次级越轨"],
     "keywords": ["标签", "越轨", "污名", "犯罪", "社会控制", "身份"],
     "summary": "越轨并非行为本身固有，而是社会施加标签的结果，标签会催生次级越轨。",
     "key_refs": ["Becker 1963《局外人》"]},
    {"id": "social_construction", "name": "社会建构主义", "proposer": "伯格/卢克曼",
     "discipline": "社会学",
     "concepts": ["社会建构", "知识社会学", "制度化"],
     "keywords": ["社会建构", "建构主义", "知识社会学", "现实", "制度化", "意义"],
     "summary": "现实与知识经由社会互动被建构并制度化，强调意义的协商性。",
     "key_refs": ["Berger & Luckmann 1966《现实的社会建构》"]},

    {"id": "institutionalism", "name": "新制度主义", "proposer": "迪马吉奥/鲍威尔/诺斯",
     "discipline": "政治学",
     "concepts": ["制度同形", "路径依赖", "正式与非正式制度"],
     "keywords": ["制度", "新制度主义", "同形", "路径依赖", "制度变迁", "合法性"],
     "summary": "制度（规则、规范、认知）塑造组织与行为；组织趋于制度同形，变迁具路径依赖。",
     "key_refs": ["DiMaggio & Powell 1983《铁笼重访》", "North 1990《制度》"]},
    {"id": "policy_streams", "name": "多源流理论", "proposer": "金登",
     "discipline": "政治学",
     "concepts": ["问题流", "政策流", "政治流", "政策之窗"],
     "keywords": ["多源流", "政策之窗", "议程设置", "政策企业家", "问题流", "政策流"],
     "summary": "问题、政策、政治三股源流在政策之窗开启时耦合，推动议题进入议程。",
     "key_refs": ["Kingdon 1984《议程、备选方案与公共政策》"]},
    {"id": "advocacy_coalition", "name": "倡议联盟框架", "proposer": "萨巴蒂尔",
     "discipline": "政治学",
     "concepts": ["倡议联盟", "信念体系", "政策取向学习"],
     "keywords": ["倡议联盟", "信念体系", "政策学习", "政策子系统", "政策变迁"],
     "summary": "政策子系统内不同信念体系的倡议联盟相互竞争，政策变迁源于学习与外部冲击。",
     "key_refs": ["Sabatier 1988"]},
    {"id": "governance", "name": "治理理论", "proposer": "罗茨/罗西瑙",
     "discipline": "政治学",
     "concepts": ["多中心治理", "网络治理", "无政府的治理"],
     "keywords": ["治理", "多中心", "网络治理", "公共治理", "协同", "善治"],
     "summary": "公共事务由政府、市场、社会多元主体通过网络协同处理，超越单一科层。",
     "key_refs": ["Rhodes 1997", "Rosenau 1992"]},

    {"id": "agenda_setting", "name": "议程设置理论", "proposer": "麦库姆斯/肖",
     "discipline": "传播学",
     "concepts": ["议程设置", "属性议程", "媒介显著性"],
     "keywords": ["议程设置", "媒介", "舆论", "属性议程", "显著性", "新闻"],
     "summary": "媒介通过对议题的报道强度影响公众认为哪些议题重要（告诉你想什么）。",
     "key_refs": ["McCombs & Shaw 1972"]},
    {"id": "framing", "name": "框架理论", "proposer": "戈夫曼/恩特曼",
     "discipline": "传播学",
     "concepts": ["框架", "框架化", "凸显与遮蔽"],
     "keywords": ["框架", "框架化", "新闻框架", "话语", "凸显", "归因"],
     "summary": "传播通过选择与凸显特定方面建构意义框架，影响受众的理解与归因。",
     "key_refs": ["Goffman 1974《框架分析》", "Entman 1993"]},
    {"id": "uses_gratifications", "name": "使用与满足理论", "proposer": "卡茨/布卢姆勒",
     "discipline": "传播学",
     "concepts": ["主动受众", "媒介需求", "满足"],
     "keywords": ["使用与满足", "受众", "媒介使用", "需求", "满足", "动机"],
     "summary": "受众主动选择媒介以满足信息、娱乐、社交、认同等需求。",
     "key_refs": ["Katz, Blumler & Gurevitch 1973"]},
    {"id": "spiral_silence", "name": "沉默的螺旋", "proposer": "诺依曼",
     "discipline": "传播学",
     "concepts": ["意见气候", "从众", "孤立恐惧"],
     "keywords": ["沉默的螺旋", "舆论", "意见气候", "从众", "孤立", "民意"],
     "summary": "个体因惧怕孤立而在感知到自己属少数意见时趋于沉默，强化优势意见。",
     "key_refs": ["Noelle-Neumann 1974"]},

    {"id": "constructivism_learning", "name": "建构主义学习理论", "proposer": "皮亚杰/维果茨基",
     "discipline": "教育学",
     "concepts": ["最近发展区", "同化顺应", "支架"],
     "keywords": ["建构主义", "最近发展区", "支架", "同化", "顺应", "学习"],
     "summary": "学习是学习者主动建构知识的过程，社会互动与支架促进发展。",
     "key_refs": ["Vygotsky 1978", "Piaget"]},
    {"id": "self_determination", "name": "自我决定理论", "proposer": "德西/瑞安",
     "discipline": "心理学",
     "concepts": ["自主", "胜任", "归属", "内在动机"],
     "keywords": ["自我决定", "内在动机", "自主", "胜任", "归属", "动机"],
     "summary": "满足自主、胜任、归属三种基本心理需要可增强内在动机与幸福感。",
     "key_refs": ["Deci & Ryan 1985"]},
    {"id": "planned_behavior", "name": "计划行为理论", "proposer": "阿杰恩",
     "discipline": "心理学",
     "concepts": ["行为态度", "主观规范", "知觉行为控制", "行为意向"],
     "keywords": ["计划行为", "行为意向", "态度", "主观规范", "行为控制", "意向"],
     "summary": "态度、主观规范与知觉行为控制共同决定行为意向，进而预测行为。",
     "key_refs": ["Ajzen 1991"]},
    {"id": "social_cognitive", "name": "社会认知理论", "proposer": "班杜拉",
     "discipline": "心理学",
     "concepts": ["自我效能", "观察学习", "三元交互"],
     "keywords": ["社会认知", "自我效能", "观察学习", "榜样", "三元交互", "效能感"],
     "summary": "人通过观察学习与自我效能信念，在个人、行为、环境的三元交互中能动地行动。",
     "key_refs": ["Bandura 1986"]},

    {"id": "resource_based_view", "name": "资源基础观", "proposer": "巴尼/沃纳菲尔特",
     "discipline": "管理学",
     "concepts": ["VRIN资源", "持续竞争优势", "异质性"],
     "keywords": ["资源基础", "竞争优势", "核心能力", "异质性", "VRIN", "资源"],
     "summary": "企业持续竞争优势源于有价值、稀缺、难模仿、不可替代的异质性资源。",
     "key_refs": ["Barney 1991", "Wernerfelt 1984"]},
    {"id": "dynamic_capabilities", "name": "动态能力理论", "proposer": "蒂斯",
     "discipline": "管理学",
     "concepts": ["感知", "捕获", "重构"],
     "keywords": ["动态能力", "感知", "重构", "组织变革", "创新", "能力"],
     "summary": "企业在快速变化环境中感知机会、捕获价值并重构资源以维持优势。",
     "key_refs": ["Teece, Pisano & Shuen 1997"]},
    {"id": "stakeholder", "name": "利益相关者理论", "proposer": "弗里曼",
     "discipline": "管理学",
     "concepts": ["利益相关者", "利益平衡", "企业责任"],
     "keywords": ["利益相关者", "利益平衡", "企业社会责任", "治理", "相关者"],
     "summary": "企业应平衡股东之外各利益相关者的诉求，而非仅追求股东价值最大化。",
     "key_refs": ["Freeman 1984"]},
    {"id": "tam", "name": "技术接受模型", "proposer": "戴维斯",
     "discipline": "管理学",
     "concepts": ["感知有用性", "感知易用性", "使用意向"],
     "keywords": ["技术接受", "感知有用性", "感知易用性", "采纳", "使用意向", "信息系统"],
     "summary": "感知有用性与感知易用性决定用户对信息技术的接受与使用意向。",
     "key_refs": ["Davis 1989"]},

    {"id": "principal_agent", "name": "委托代理理论", "proposer": "詹森/麦克林",
     "discipline": "经济学",
     "concepts": ["信息不对称", "道德风险", "激励相容"],
     "keywords": ["委托代理", "信息不对称", "道德风险", "逆向选择", "激励", "代理成本"],
     "summary": "委托人与代理人目标不一致且信息不对称，引发道德风险，需激励相容的契约设计。",
     "key_refs": ["Jensen & Meckling 1976"]},
    {"id": "transaction_cost", "name": "交易成本理论", "proposer": "科斯/威廉姆森",
     "discipline": "经济学",
     "concepts": ["交易成本", "资产专用性", "纵向一体化"],
     "keywords": ["交易成本", "资产专用性", "科层", "市场", "一体化", "契约"],
     "summary": "交易成本（搜寻、谈判、履约）决定经济活动在市场还是科层组织内进行。",
     "key_refs": ["Coase 1937", "Williamson 1985"]},
    {"id": "rational_choice", "name": "理性选择理论", "proposer": "奥尔森/科尔曼",
     "discipline": "经济学",
     "concepts": ["效用最大化", "集体行动", "搭便车"],
     "keywords": ["理性选择", "效用最大化", "集体行动", "搭便车", "公共物品", "理性人"],
     "summary": "行动者在约束下追求效用最大化；集体行动因搭便车困境难以自发达成。",
     "key_refs": ["Olson 1965《集体行动的逻辑》"]},

    {"id": "thick_description", "name": "深描/解释人类学", "proposer": "格尔茨",
     "discipline": "人类学",
     "concepts": ["深描", "文化解释", "地方性知识"],
     "keywords": ["深描", "文化解释", "民族志", "地方性知识", "象征", "意义之网"],
     "summary": "文化是意义之网，人类学应通过深描解释行为背后的地方性意义。",
     "key_refs": ["Geertz 1973《文化的解释》"]},
    {"id": "gift_exchange", "name": "礼物交换理论", "proposer": "莫斯",
     "discipline": "人类学",
     "concepts": ["互惠", "总体性呈现", "义务"],
     "keywords": ["礼物", "交换", "互惠", "义务", "馈赠", "总体性呈现"],
     "summary": "礼物交换包含给予、接受、回报三重义务，是维系社会关系的总体性社会事实。",
     "key_refs": ["Mauss 1925《礼物》"]},
    {"id": "practice_theory", "name": "实践理论", "proposer": "布迪厄/夏茨基",
     "discipline": "社会学",
     "concepts": ["实践", "身体技术", "日常惯例"],
     "keywords": ["实践理论", "实践", "日常", "惯例", "身体", "操演"],
     "summary": "聚焦日常实践的逻辑与惯例，将社会秩序理解为实践的持续操演。",
     "key_refs": ["Bourdieu 1977", "Schatzki 1996"]},

    {"id": "legal_pluralism", "name": "法律多元主义", "proposer": "格里菲斯/摩尔",
     "discipline": "法学",
     "concepts": ["法律多元", "半自治社会场域", "民间法"],
     "keywords": ["法律多元", "民间法", "国家法", "半自治", "习惯法", "规范"],
     "summary": "同一社会空间中并存国家法与多种非国家规范秩序，法律并非国家垄断。",
     "key_refs": ["Griffiths 1986", "Moore 1973"]},
]


def validate_library(theories: Any) -> List[Dict[str, str]]:
    """校验自定义理论库条目，返回可 JSON 序列化的错误列表。"""
    errors: List[Dict[str, str]] = []
    if not isinstance(theories, list):
        return [{"field": "<root>", "message": "理论库必须是列表"}]

    seen = set()
    valid_disciplines = set(DISCIPLINES)
    for i, theory in enumerate(theories):
        if not isinstance(theory, dict):
            errors.append({"field": f"theories[{i}]", "message": "每条理论必须是对象"})
            continue

        valid_strings = {}
        for field in REQUIRED_THEORY_FIELDS:
            if field == "keywords":
                continue
            value = theory.get(field)
            valid_strings[field] = isinstance(value, str) and bool(value.strip())
            if not valid_strings[field]:
                message = f"缺少 {field}" if value is None or isinstance(value, str) else f"{field} 必须是非空字符串"
                errors.append({"field": f"theories[{i}].{field}", "message": message})

        keywords = theory.get("keywords")
        if (
            not isinstance(keywords, list)
            or not keywords
            or not all(isinstance(item, str) and item.strip() for item in keywords)
        ):
            errors.append({"field": f"theories[{i}].keywords", "message": "keywords 必须是非空字符串列表"})

        if valid_strings["id"]:
            theory_id = theory["id"].strip()
            if theory_id in seen:
                errors.append({"field": f"theories[{i}].id", "message": f"id 重复: {theory_id}"})
            seen.add(theory_id)

        if valid_strings["discipline"] and theory["discipline"].strip() not in valid_disciplines:
            errors.append({
                "field": f"theories[{i}].discipline",
                "message": f"discipline 必须是 {DISCIPLINES} 之一",
            })

    return errors


class LibraryValidationError(ValueError):
    """Raised when a custom library JSON document has an invalid shape."""

    def __init__(self, errors: List[Dict[str, str]]):
        self.errors = errors
        super().__init__("自定义理论库结构非法")


def load_library(path: str) -> List[Dict[str, Any]]:
    """读自定义理论库 JSON：支持 list 或 {theories:[...]}。"""
    import json
    from pathlib import Path
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    if isinstance(raw, dict):
        if "theories" not in raw:
            raise LibraryValidationError([{"field": "<root>", "message": "理论库对象必须包含 theories"}])
        raw = raw["theories"]
        if not isinstance(raw, list):
            raise LibraryValidationError([{"field": "theories", "message": "theories 必须是列表"}])
    elif not isinstance(raw, list):
        raise LibraryValidationError([{"field": "<root>", "message": "理论库必须是列表或含 theories 列表的对象"}])
    return raw


def merge_libraries(base: List[Dict[str, Any]], extra: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """合并理论库：同 id 以 extra 覆盖，新 id 追加。"""
    out = copy.deepcopy(base)
    index = {t.get("id"): i for i, t in enumerate(out) if t.get("id")}
    for t in extra:
        tid = t.get("id")
        if tid and tid in index:
            out[index[tid]] = t
        else:
            out.append(t)
    return out


def _theory_text(t: Dict[str, Any]) -> str:
    parts = [str(t.get("name", "")), str(t.get("summary", "")), str(t.get("proposer", ""))]
    parts += [str(x) for x in (t.get("keywords") or [])]
    parts += [str(x) for x in (t.get("concepts") or [])]
    return " ".join(parts)


def list_theories(theories: List[Dict[str, Any]], discipline: Optional[str] = None,
                  query: Optional[str] = None) -> List[Dict[str, Any]]:
    """按学科/关键词过滤理论库。"""
    out = theories
    if discipline:
        out = [t for t in out if t.get("discipline") == discipline]
    if query:
        q = query.strip()
        out = [t for t in out if q in _theory_text(t)]
    return list(out)


def _match_terms(t: Dict[str, Any]) -> List[str]:
    terms = [str(t.get("name", ""))]
    terms += [str(x) for x in (t.get("keywords") or [])]
    terms += [str(x) for x in (t.get("concepts") or [])]
    return terms


def match_theories(theories: List[Dict[str, Any]], keywords: List[str],
                   top: int = 8) -> List[Dict[str, Any]]:
    """据用户关键词与每条理论的 name/keywords/concepts 重叠打分排序。"""
    kws = [k.strip() for k in keywords if k and k.strip()]
    if not kws:
        return []
    scored = []
    for t in theories:
        terms = _match_terms(t)
        matched = []
        for k in kws:
            if any(k in term or term in k for term in terms):
                matched.append(k)
        if matched:
            r = {kk: t.get(kk) for kk in
                 ("id", "name", "proposer", "discipline", "concepts", "summary", "key_refs")}
            r["score"] = len(matched)
            r["matched"] = matched
            scored.append(r)
    scored.sort(key=lambda x: x["score"], reverse=True)
    return scored[: top if top and top > 0 else len(scored)]
