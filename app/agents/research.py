from app.agents.base import ModelAgent


class ResearchAgent(ModelAgent):
    role = "research"
    allowed_tools = frozenset({"calculator"})
