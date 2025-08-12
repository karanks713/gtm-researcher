from FunctionTools.tavily_batch import process_tavily_from_urls, generate_questions
from elsai_core.model.azure_openai_connector import AzureOpenAIConnector
from FunctionTools.perplexity import process_perplexity_in_batches
from FunctionTools.version_one.optimized import enhanced_research
from tavily import TavilyClient
from typing import List
import os
from dotenv import load_dotenv 
load_dotenv()

tavily = TavilyClient(api_key=os.getenv("TAVILY_API_KEY"))
connector = AzureOpenAIConnector()
llm = connector.connect_azure_open_ai("gpt-4o-mini")


def common_structure(company_name: str = None, 
                     country: str = None, 
                     search_queries: List[str] = None, 
                     prompt: str = None, 
                     support_urls: List[str] = None,
                     enable_validation: bool = True) -> dict:
    """
    Enhanced version of the original common_structure function
    
    Args:
        company_name: Company name
        country: Country name  
        search_queries: Optional search queries
        prompt: Final processing prompt
        support_urls: Optional support URLs
        enable_validation: Whether to use enhanced validation features
    
    Returns:
        dict: Research results (enhanced or original based on enable_validation)
    """
    if prompt is None:
                raise ValueError("required parameter prompt is missing")
    if search_queries is None:
        search_queries = generate_questions(company_name, prompt)['questions']
    
    if enable_validation:
        # Use enhanced research (now synchronous)
        return enhanced_research(
            company_name=company_name,
            country=country,
            search_queries=search_queries,
            prompt=prompt,
            support_urls=support_urls
        )
    else:
        # Use original approach
        try:
            print(f"Searching for {company_name} company in {country}...")
            
            def get_response(prompt: str):
                return llm.invoke(prompt)
            
            context_one_dict = process_perplexity_in_batches(
                company_name=company_name,
                country=country,
                search_queries=search_queries,
                batch_size=2,
                delay_between_batches=2
            )
            
            context = context_one_dict['content']
            
            if support_urls is not None:
                tavily_support_results = process_tavily_from_urls(
                    tavily_client=tavily, 
                    urls=support_urls, 
                    company_name=company_name
                )
                context = tavily_support_results + "\n" + context
            
            response = get_response(prompt + "\n\nContext:\n" + context)  

            response_data = {
                "company_name": company_name,
                "country": country,
                "support_urls": support_urls,
                "prompt": prompt,
                "enhanced_features": {
                    "validation_enabled": False
                },
                "final_data": {
                    "web_response": response.content,
                    "total_tokens": context_one_dict['total_tokens'],
                    "total_cost": context_one_dict['total_cost'],
                    "citations": context_one_dict['citations'],
                    "research_phases": {
                        "initial_queries": search_queries
                    }
                }
            }
            
            return response_data
        except Exception as e:
            raise RuntimeError(f"Function Error: {str(e)}")