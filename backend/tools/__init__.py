from typing import Any, Dict, Optional, Protocol

# 1. Standart Arayüz (Her tool buna uymak zorunda)
class BaseTool(Protocol):
    name: str
    description: str

    def run(self, **kwargs: Any) -> Any:
        ...

# 2. Yönetici Sınıf (Registry)
class ToolRegistry:
    def __init__(self):
        self._tools: Dict[str, BaseTool] = {}

    def register(self, tool: BaseTool):
        """Tool'u ismine göre kaydeder."""
        if not hasattr(tool, 'name'):
            raise ValueError(f"Tool {tool} must have a 'name' attribute.")
        
        # print(f"🔧 Tool Registered: {tool.name}") # İsteğe bağlı log
        self._tools[tool.name] = tool

    def get(self, name: str) -> Optional[BaseTool]:
        """İsmi verilen tool'u döndürür."""
        return self._tools.get(name)

    def list_tools(self):
        """Kayıtlı tool listesini verir."""
        return list(self._tools.keys())
