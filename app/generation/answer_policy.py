import re

_GREETINGS = {"你好", "您好", "嗨", "哈喽", "hello", "hi", "hey", "早上好", "上午好", "下午好", "晚上好"}
_THANKS = {"谢谢", "谢谢你", "多谢", "感谢", "thanks", "thank you"}
_FAREWELLS = {"再见", "拜拜", "回头见", "bye", "goodbye"}


def smalltalk_response(query: str) -> str | None:
    normalized = re.sub(r"[\s，,。.!！?？~～…]+$", "", query.casefold().strip()).strip()
    if not normalized or re.fullmatch(r"[\W_]+", normalized):
        return "请描述你遇到的企业软件问题，例如产品版本、部署方式或故障现象。"
    if normalized in _GREETINGS:
        return "你好！我是企业软件交付与技术支持助手，可以帮你查询部署、配置和故障处理资料。"
    if normalized in _THANKS:
        return "不客气！有企业软件部署、配置或故障问题，随时告诉我。"
    if normalized in _FAREWELLS:
        return "再见！需要排查企业软件问题时，欢迎随时来问。"
    return None


def clarification_needed(request):
    # Narrow initial rule; full environment extraction is a later phase.
    if "升级" in request.query and any(x in request.query for x in ("怎么", "如何", "步骤")):
        if not request.context.product_version:
            return "请提供当前软件版本、目标版本和部署方式，以确认升级说明的适用范围。"
    return None
