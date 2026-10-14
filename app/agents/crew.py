from crewai import Agent, Crew, LLM, Process, Task
from app.config import get_settings
from app.schemas import CrewFinding
from app.tools.registry import tool_registry


def _llm() -> LLM:
    settings = get_settings()
    kwargs = {"model": settings.openai_model_name, "api_key": settings.openai_api_key or None}
    # A Gemini key must stay on the OpenAI-compatible base URL. A bare
    # "gemini-*" model name is otherwise sent to api.openai.com.
    if settings.openai_api_base:
        kwargs["provider"] = "openai"
        kwargs["base_url"] = settings.openai_api_base
    return LLM(**kwargs)


def build_crew(scenario: str, context: str = "") -> Crew:
    settings = get_settings()
    tools = tool_registry()
    llm = _llm()
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
        description=(
            f"As Chief DBA, synthesize the CPU/Workload and Memory/Database findings for '{scenario}'. "
            "Return only the structured diagnosis: root causes with confidence from 0 to 1, "
            "advisory recommendations, and a short summary. Use the tool evidence and supplied context. "
            "Do not execute mutations and do not claim that any change was applied. "
            f"Context: {context}"
        ),
        expected_output="Structured root causes, advisory recommendations, and a summary grounded in the gathered evidence.",
        agent=chief,
        context=[cpu_task, memory_task],
        output_pydantic=CrewFinding,
    )
    return Crew(
        agents=[cpu, memory, chief],
        tasks=[cpu_task, memory_task, chief_task],
        process=Process.sequential,
        verbose=False,
    )
