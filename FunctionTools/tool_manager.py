from FunctionTools.version_one.common import common_structure
class ToolManager:
    """
    ToolManager is responsible for managing and loading function tools.
    It provides a method to load a specific function tool based on its name.
    """
    
    # Define tools dictionary as a class attribute to avoid duplication
    _TOOLS = {
                
                "COMMON_STRUCTURE": common_structure
            }
   
    @classmethod
    def get(cls, function_name: str):
        try:
            return cls._TOOLS[function_name]
        except KeyError:
            raise ValueError(f"Unknown function tool: {function_name}")
    
    @classmethod
    def get_available_tools(cls):
        """
        Returns a list of all available tool names.
        """
        return list(cls._TOOLS.keys())