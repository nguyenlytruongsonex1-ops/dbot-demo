from app.tools.registry import tool_registry

def test_tool_registry_is_read_only_demo_surface():
    tools = tool_registry()
    names = {tool.name for tool in tools}
    assert {"get_active_sessions", "get_locks", "get_slow_queries", "get_table_statistics", "explain_query"}.issubset(names)
    assert all(tool.description for tool in tools)
