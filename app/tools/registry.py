from .postgres_tools import all_tools
from .system_tools import SystemMetricsTool

def tool_registry():
    return all_tools() + [SystemMetricsTool()]

def tool_metadata():
    return [{"name": tool.name, "description": tool.description} for tool in tool_registry()]
