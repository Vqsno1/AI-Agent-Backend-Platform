from abc import ABC, abstractmethod


class BaseAgent(ABC):
    role: str
    allowed_tools: frozenset[str] = frozenset()

    @abstractmethod
    def run(self, client, context):
        raise NotImplementedError


class ModelAgent(BaseAgent):
    def run(self, client, context):
        return client.generate_structured(self.role, context)
