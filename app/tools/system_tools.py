import json
import os
import psutil
from typing import Type
from pydantic import BaseModel
from crewai.tools import BaseTool

class EmptyInput(BaseModel):
    pass

class SystemMetricsTool(BaseTool):
    name: str = "get_system_metrics"
    description: str = "Read host CPU, memory, load average and process count metrics."
    args_schema: Type[BaseModel] = EmptyInput
    def _run(self) -> str:
        data = {
            "cpu_percent": psutil.cpu_percent(interval=0.2),
            "memory_percent": psutil.virtual_memory().percent,
            "load_average": os.getloadavg() if hasattr(os, "getloadavg") else None,
            "cpu_count": psutil.cpu_count(),
            "process_count": len(psutil.pids()),
        }
        return json.dumps(data, default=str)
