def clean_text(text: str) -> str:
    """
    清理空白、异常字符和不适合检索的内容。
    保留 YAML 缩进、shell 引号、版本号中的点、连字符以及代码围栏。
    """
    return text.replace("\r\n", "\n").replace("\r", "\n").replace("\ufeff", "").replace("\x00", "")

