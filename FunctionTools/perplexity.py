from concurrent.futures import ThreadPoolExecutor
import time
import requests
import traceback
import os
from typing import List, Dict, Any
from dotenv import load_dotenv
load_dotenv()

def research(text):
    try: 
        url = "https://api.perplexity.ai/chat/completions"
        
        payload = {
            "model": f"{os.getenv('PPLX_MODEL_NAME')}",
            "messages": [{"role": "user", "content": text}],
            "web_search_options": {"search_context_size": f"{os.getenv('PPLX_MODE')}"}
                }
        
        headers = {
            "Authorization": f"Bearer {os.getenv('PPLX_API_KEY')}",
            "Content-Type": "application/json"
        }

        response = requests.post(url, json=payload, headers=headers)
        return response.json()
    except Exception as e:
        traceback.print_exc()
        raise Exception(f"Error in deep_research: {e}")
    
    
def process_perplexity_in_batches(company_name: str, country: str, search_queries: List[str], batch_size: int=2, delay_between_batches: int=2) -> Dict[str, Any]:
    """
    Process Perplexity queries in batches with threading
    
    Args:
        company_name: Company name to search for
        search_queries: List of search queries
        batch_size: Number of queries to process simultaneously (default: 4)
        delay_between_batches: Seconds to wait between batches (default: 2)
    
    Returns:
        str: Combined results from all queries
    """
    if company_name is None:
        raise ValueError(f"Company name not found. Please provide a valid company name.")
    
    def single_query(query, company_name, country):
        """Execute a single query"""
        try:
            print(f"Searching: {query}")
            
            perplexity_result = research(f"For {company_name} company located in {country}, Answer the following Question in detail: \n{query}.")
            
            content = perplexity_result['choices'][0]['message']['content']
            tokens = perplexity_result['usage']['total_tokens']
            cost = perplexity_result['usage']['cost']['total_cost']
            source = perplexity_result['citations']
            
            print(f"✓ Completed: {query}")
            return {'content': content, 'tokens': tokens, 'cost': cost, 'source': source} 
            
        except Exception as e:
            print(f"✗ ERROR in query '{query}': {e}")
            raise RuntimeError(f"Error in query '{query}': {e}")
    
    all_results = ""
    total_cost = 0
    total_tokens = 0
    citations = []
    total_queries = len(search_queries)
    
    # Process queries in batches
    for i in range(0, total_queries, batch_size):
        batch = search_queries[i:i + batch_size]
        batch_num = (i // batch_size) + 1
        
        print(f"\n[BATCH {batch_num}] Processing {len(batch)} queries...")
        
        # Use ThreadPoolExecutor for current batch
        with ThreadPoolExecutor(max_workers=len(batch)) as executor:
            # Submit all queries in current batch
            futures = [executor.submit(single_query, query, company_name, country) for query in batch]
            
            # Collect results as they complete
            for future in futures:
                result = future.result()
                if result:  # Only add non-empty results
                    all_results += result['content'] + "\n"
                    total_tokens += result['tokens']
                    total_cost += result['cost']
                    citations.extend(result['source'])
        
        print(f"[BATCH {batch_num}] Completed!")
        
        # Wait before next batch (except for the last batch)
        if i + batch_size < total_queries:
            print(f"Waiting {delay_between_batches} seconds before next batch...")
            time.sleep(delay_between_batches)
    
    return {"content": all_results, "total_tokens": total_tokens, "total_cost": total_cost, "citations": citations}