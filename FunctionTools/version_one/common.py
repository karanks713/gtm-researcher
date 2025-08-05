from FunctionTools.tavily_batch import process_tavily_from_urls, generate_questions
from elsai_core.model.azure_openai_connector import AzureOpenAIConnector
from FunctionTools.perplexity import process_perplexity_in_batches
from tavily import TavilyClient
from typing import List
import os
from dotenv import load_dotenv 
load_dotenv()

tavily = TavilyClient(api_key=os.getenv("TAVILY_API_KEY"))
connector = AzureOpenAIConnector()
llm = connector.connect_azure_open_ai("gpt-4o-mini")

# Domain lists for TavilyClient research topics


def common_structure(company_name:str = None, 
                     country:str = None, 
                     # research_topic:str = None, 
                     search_queries: List[str] = None, 
                     prompt:str = None, 
                     support_urls:List[str] = None) -> dict:
    try:
        if prompt is None:
            raise ValueError("required parameter prompt is missing")
        if search_queries is None:
            search_queries = generate_questions(company_name, prompt)['questions']
        print(f"Searching for {company_name} company in {country}...")
        def get_response(prompt:str):
            return llm.invoke(prompt)
        
        context = process_perplexity_in_batches(
            company_name=company_name,
            country=country,
            search_queries=search_queries,
            batch_size=os.getenv('QUERY_BATCH_SIZE'),
            delay_between_batches=os.getenv('DELAY_BETWEEN_BATCHES')
        )
        
        if support_urls is not None:
            tavily_support_results = process_tavily_from_urls(tavily_client=tavily, urls=support_urls, company_name=company_name)
            context = tavily_support_results + "\n" + context
        
        response = get_response(prompt + "\n\nContext:\n" + context)  

        response_data = {"company_name": company_name,
                         "country": country,
                         # "search_queries": search_queries,
                         "support_urls": support_urls,
                         "prompt": prompt,
                         "final_data":{"web_response": response.content}}
        
        return response_data
    except Exception as e:
        raise RuntimeError(f"Function Error: {str(e)}")