from FunctionTools.tavily_batch import process_tavily_from_urls
from FunctionTools.enhance import EnhancedDataCollector
from elsai_core.model.azure_openai_connector import AzureOpenAIConnector
from tavily import TavilyClient
from typing import List
import os
import logging
from dotenv import load_dotenv 

load_dotenv()
logger = logging.getLogger(__name__)
    
# Initialize global components
tavily = TavilyClient(api_key=os.getenv("TAVILY_API_KEY"))
connector = AzureOpenAIConnector()
llm = connector.connect_azure_open_ai("gpt-4o-mini")


def enhanced_research(company_name: str = None, 
                     country: str = None, 
                     search_queries: List[str] = None, 
                     prompt: str = None, 
                     support_urls: List[str] = None) -> dict:
    """
    Enhanced research function with validation and content enhancement
    
    Args:
        company_name: Company name to research
        country: Country for geographic context
        search_queries: Optional list of specific search queries
        prompt: Final prompt to process the research data
        support_urls: Optional URLs for additional context
        enable_validation: Whether to enable validation (default: True)
    
    Returns:
        dict: Enhanced research results with validation data
    """
    try:
        # Initialize enhanced collector
        enhanced_collector = EnhancedDataCollector(llm)
        if prompt is None:
            raise ValueError("required parameter prompt is missing")
        
        print(f"Starting Enhanced research for {company_name} in {country}...")
        
        # Use enhanced data collection with validation (synchronous version)
        enhanced_data = enhanced_collector.collect_comprehensive_data_sync(
            company_name=company_name,
            country=country,
            search_queries=search_queries
        )
        
        # Get context from enhanced data
        context = (enhanced_data['initial_data'] + '\n' + 
                    enhanced_data['targeted_data'] + '\n' + 
                    "Synthesized Context data: " + enhanced_data['synthesis'] + '\n' + 
                    "Context data Validation summary: " + enhanced_data['validation_summary'])
        
        # Add Tavily support results if URLs provided
        if support_urls is not None:
            tavily_support_results = process_tavily_from_urls(
                tavily_client=tavily, 
                urls=support_urls, 
                company_name=company_name
            )
            context = tavily_support_results + "\n" + context
        
        # Generate final response
        final_response = llm.invoke(prompt + "\n\nContext:\n" + context)
        
        response_data = {
            "company_name": company_name,
            "country": country,
            "prompt": prompt,
            "enhanced_features": {
                "validation_enabled": True,
                "data_quality_score": enhanced_data.get('data_quality_score', 0.0),
                "high_confidence_claims": enhanced_data.get('high_confidence_claims', []),
                "requires_manual_review": enhanced_data.get('requires_manual_review', []),
                "validation_summary": enhanced_data.get('validation_summary', {})
            },
            "final_data": {
                "web_response": final_response.content,
                "enhanced_synthesis": enhanced_data.get('synthesis', ''),
                "total_tokens": enhanced_collector.perplexity_total_tokens,
                "total_cost": enhanced_collector.perplexity_total_cost,
                "citations": enhanced_collector.all_citations,
                "research_phases": {
                    "initial_queries": enhanced_data.get('queries_used',[]),
                    "gap_queries": enhanced_data.get('gap_queries',[])
                }
            }
        }
        
        return response_data
    
    except Exception as e:
        print(f"Enhanced research function error: {str(e)}")
        raise RuntimeError(f"Enhanced research function error: {str(e)}")