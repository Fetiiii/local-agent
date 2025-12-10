from backend.core.agent import Agent, AgentConfig
from backend.core.types import AgentMessage
from backend.core.context_manager import ContextManager
from backend.core.router import Router
from backend.core.model_client import ModelClient


class DummyModelClient(ModelClient):
    def __init__(self) -> None:
        super().__init__(base_url="http://127.0.0.1:0")

    def generate(self, messages, mode=None):
        return "dummy-response"


def test_agent_handles_message():
    context = ContextManager()
    model = DummyModelClient()
    router = Router()
    agent = Agent(model_client=model, context_manager=context, router=router, config=AgentConfig())

    reply = agent.handle_user_message("hello", mode="chat")
    assert isinstance(reply, AgentMessage)
    assert reply.content == "dummy-response"
