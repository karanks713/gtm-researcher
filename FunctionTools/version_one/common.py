from FunctionTools.tavily_batch import process_tavily_in_batches, process_tavily_from_urls, generate_questions
from elsai_core.model.azure_openai_connector import AzureOpenAIConnector
from tavily import TavilyClient
from typing import List
import os
from dotenv import load_dotenv 
load_dotenv()

tavily = TavilyClient(api_key=os.getenv("TAVILY_API_KEY"))
connector = AzureOpenAIConnector()
llm = connector.connect_azure_open_ai("gpt-4o-mini")

# Domain lists for TavilyClient research topics


def common_structure(company_name:str, 
                     country:str, research_topic:str, 
                     search_queries:List[str], prompt:str, 
                     support_urls:List[str]) -> dict:
    try:
        if prompt is None:
            raise ValueError("required parameter prompt is missing")
        if search_queries is None:
            search_queries = generate_questions(company_name, prompt)
        print(f"Searching for {company_name} company in {country}...")
        def get_response(prompt:str):
            return llm.invoke(prompt)
        
        tavily_results = process_tavily_in_batches(
            tavily_client=tavily,
            company_name=company_name,
            country=country,
            research_topic=research_topic,
            search_queries=search_queries,
            batch_size=2,
            delay_between_batches=2
        )
        
        context = tavily_results
        if support_urls is not None:
            tavily_support_results = process_tavily_from_urls(tavily_client=tavily, urls=support_urls, company_name=company_name)
            context = tavily_support_results + "\n" + tavily_results
        
        response = get_response(prompt + "\n\nContext:\n" + context)  

        response_data = {"company_name": company_name,
                         "country": country,
                         "search_queries": search_queries,
                         "support_urls": support_urls,
                         "prompt": prompt,
                         "final_data":{"web_response": response.content}}
        
        return response_data
    except Exception as e:
        raise RuntimeError(f"Function Error: {str(e)}")