from typing import TypedDict, Any, Optional, Union, List
from datetime import date

class State(TypedDict):
    company_name: str
    state: Optional[str]
    country: str
    search_queries: Optional[List[str]]
    support_urls: Optional[List[str]]
    prompt: Optional[str]
    from_date: Optional[Union[date, str]]
    to_date: Optional[Union[date, str]]    # End of Input parameters
    web_content: Optional[str] 
    structured_data: Optional[dict]
    source_list: Optional[Any]
    final_data: Optional[dict]