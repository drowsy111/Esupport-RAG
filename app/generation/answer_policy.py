def clarification_needed(request):
    # Narrow initial rule; full environment extraction is a later phase.
    if "升级" in request.query and any(x in request.query for x in ("怎么", "如何", "步骤")):
        if not request.context.product_version:
            return "请提供当前软件版本、目标版本和部署方式，以确认升级说明的适用范围。"
    return None

