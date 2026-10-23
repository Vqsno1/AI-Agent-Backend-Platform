from app.agents.analyst import AnalystAgent
from app.agents.planner import PlannerAgent
from app.agents.research import ResearchAgent
from app.agents.summarizer import SummarizerAgent


class AgentOrchestrator:
    agents = (PlannerAgent(), ResearchAgent(), AnalystAgent(), SummarizerAgent())

    def create_plan(self, max_steps):
        if max_steps < len(self.agents):
            raise ValueError("step_limit_exceeded")
        return self.agents
