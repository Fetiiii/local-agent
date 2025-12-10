from backend.core.memory_manager import MemoryManager
from backend.core.types import AgentMessage


def test_memory_manager_saves_and_loads():
    mem = MemoryManager()
    mem.save(AgentMessage(role="user", content="hi"))
    assert len(mem.load_recent()) == 1
