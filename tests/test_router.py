from backend.core.router import Router, RouteDecision


def test_router_blocks_mode_not_allowed():
    r = Router(allowed_modes=["agent"])
    decision = r.decide("please search the web", mode="chat")
    assert decision.use_tool is False
    assert decision.rationale == "Mode not tool-enabled"


def test_router_blocks_tool_not_allowed():
    r = Router(allowed_tools=["file_loader"])
    out = r.run_tool("shell_exec", command="dir")
    assert "blocked" in out


def test_router_keyword_matches():
    r = Router()
    decision = r.decide("lÇ¬tfen sql sorgusu ÇõalŽñYtŽñr", mode="agent")
    assert decision.use_tool is True
    assert decision.tool_name == "sql_query"


def test_router_explicit_tool_request_respects_allowlist():
    r = Router(allowed_tools=["file_loader"])
    decision = r.decide("/tool python_exec: 1+1", mode="agent")
    assert decision.use_tool is False
    assert "not allowed" in decision.rationale


def test_router_explicit_tool_triggers_when_allowed():
    r = Router(allowed_tools=["python_exec"])
    decision = r.decide("tool: python_exec 1+1", mode="agent")
    assert decision.use_tool is True
    assert decision.tool_name == "python_exec"
