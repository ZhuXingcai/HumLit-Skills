from __future__ import annotations

from cli._common import _output


def cmd_data_table(args):
    """实证/实验数据确定性制表（纯标准库计算，绝不捏造任何数值）。"""
    from core.research_tools import cmd_data_table as _run_data_table

    _run_data_table(args, output_fn=_output)


def cmd_rebuttal(args):
    """审稿意见结构化拆解、原稿段落定位与点对点回复函脚手架（需作者审核定稿）。"""
    from core.research_tools import cmd_rebuttal as _run_rebuttal

    _run_rebuttal(args, output_fn=_output)


def add_parser(sub):
    p_dt = sub.add_parser(
        "data-table",
        help="将实证 CSV/TSV/JSON 生成出版级三线统计表、相关矩阵、回归表或对比表（Markdown/LaTeX/Word）",
    )
    p_dt.add_argument("filepath", help="输入数据文件路径（.csv / .tsv / .json）")
    p_dt.add_argument(
        "--type", "--mode", dest="type",
        choices=["auto", "summary", "corr", "regression", "comparison"],
        default="auto",
        help="表格类型: auto/summary/corr/regression/comparison",
    )
    p_dt.add_argument("--columns", help="指定参与计算的列名（逗号分隔）")
    p_dt.add_argument("--digits", type=int, default=None, help="保留小数位数")
    p_dt.add_argument("--lang", choices=["zh", "en"], default="zh", help="表头与表注语言（zh/en）")
    p_dt.add_argument("--caption", help="自定义表题")
    p_dt.add_argument("--format", choices=["markdown", "latex", "docx"], default="markdown", help="输出格式")
    p_dt.add_argument("-o", "--output", help="输出文件路径")
    p_dt.add_argument("--raw", action="store_true", help="直接输出纯文本表格代码")
    p_dt.set_defaults(func=cmd_data_table)

    p_reb = sub.add_parser(
        "rebuttal",
        help="拆解审稿意见、定位原稿段落锚点并生成点对点回复函与 patch-docx 补丁模板",
    )
    p_reb.add_argument("filepath", help="审稿意见文件（.txt / .md / .docx）")
    p_reb.add_argument("--manuscript", help="原稿文件（.docx / .md），用于匹配段落锚点 [Pn]")
    p_reb.add_argument("--title", help="论文标题")
    p_reb.add_argument("--lang", choices=["auto", "zh", "en"], default="auto", help="回复函语言")
    p_reb.add_argument("--format", choices=["markdown", "docx"], default="markdown", help="输出格式")
    p_reb.add_argument("-o", "--output", help="输出 Response Letter 路径")
    p_reb.add_argument("--init-patch", help="输出可供 patch-docx 使用的修订补丁模板 JSON 路径")
    p_reb.add_argument("--raw", action="store_true", help="直接输出 Markdown 回复函")
    p_reb.set_defaults(func=cmd_rebuttal)
