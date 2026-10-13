from crewai import Agent, Crew, Process, Task
from app.config import get_settings
from app.tools.registry import tool_registry


def build_crew(scenario: str, context: str = "") -> Crew:
    settings = get_settings()
    tools = tool_registry()
    llm = settings.openai_model_name
    common = "Use only evidence returned by tools. Never invent metrics. All recommendations are advisory and read-only."
    chief = Agent(
        role="Chief DBA",
        goal="Coordinate diagnosis of the database anomaly and produce an evidence-backed conclusion.",
        backstory=common,
        llm=llm,
        tools=tools,
        allow_delegation=False,
        max_iter=settings.dbot_max_iterations,
        verbose=False,
    )
    cpu = Agent(
        role="CPU and Workload DBA",
        goal="Analyze active sessions, wait events, query duration, and system load.",
        backstory=common,
        llm=llm,
        tools=tools,
        allow_delegation=False,
        max_iter=settings.dbot_max_iterations,
        verbose=False,
    )
    memory = Agent(
        role="Memory and Database DBA",
        goal="Analyze table statistics, dead tuples, locks, indexes, and query plans.",
        backstory=common,
        llm=llm,
        tools=tools,
        allow_delegation=False,
        max_iter=settings.dbot_max_iterations,
        verbose=False,
    )
    cpu_task = Task(
        description=f"Investigate scenario '{scenario}'. Gather relevant workload evidence and identify or rule out CPU, concurrency, and waiting causes. Context: {context}",
        expected_output="A concise finding with tool evidence and uncertainty.",
        agent=cpu,
    )
    memory_task = Task(
        description=f"Investigate scenario '{scenario}'. Gather database-level evidence from locks, table statistics, indexes, and plans. Context: {context}",
        expected_output="A concise finding with tool evidence and safe recommendations.",
        agent=memory,
    )
    chief_task = Task(
        description=f"As Chief DBA, synthesize the CPU/Workload and Memory/Database findings for '{scenario}'. State root causes, evidence, confidence, and advisory recommendations. Do not execute mutations.",
        expected_output="A final evidence-backed diagnosis.",
        agent=chief,
        context=[cpu_task, memory_task],
    )
    return Crew(
        agents=[cpu, memory, chief],
        tasks=[cpu_task, memory_task, chief_task],
        process=Process.sequential,
        verbose=False,
    )
