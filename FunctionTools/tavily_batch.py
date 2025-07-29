from elsai_core.model.azure_openai_connector import AzureOpenAIConnector
from langchain_core.output_parsers import JsonOutputParser
from concurrent.futures import ThreadPoolExecutor
from tavily import TavilyClient
from typing import List
import time
import os
from dotenv import load_dotenv 
load_dotenv()

connector = AzureOpenAIConnector()
llm = connector.connect_azure_open_ai("gpt-4o-mini")
parser = JsonOutputParser()

DOMAINS = [
    "britannica.com",
    "smithsonianmag.com",
    "nationalgeographic.com",
    "scientificamerican.com",
    "nature.com",
    "pnas.org",
    "mit.edu",
    "stanford.edu",
    "harvard.edu",
    "brookings.edu",
    "pewresearch.org",
    "statista.com",
    "ourworldindata.org",
    "jstor.org",
    "crunchbase.com",
    "pitchbook.com",
    "cbinsights.com",
    "owler.com",
    "similarweb.com",
    "g2.com",
    "capterra.com",
    "trustpilot.com",
    "glassdoor.com",
    "linkedin.com",
    "zoominfo.com",
    "yelp.com",
    "bbb.org",
    "yellowpages.com",
    "manta.com",
    "marketresearch.com",
    "ibisworld.com",
    "gartner.com",
    "forrester.com",
    "idc.com",
    "grandviewresearch.com",
    "census.gov"
    "reuters.com",
    "apnews.com",
    "bbc.com",
    "npr.org",
    "cnn.com",
    "nytimes.com",
    "washingtonpost.com",
    "wsj.com",
    "theguardian.com",
    "axios.com",
    "politico.com",
    "abcnews.go.com",
    "cbsnews.com",
    "nbcnews.com",
    "usatoday.com",
    "law.com",
    "reuters.com/legal",
    "law360.com",
    "americanbar.org",
    "state.gov",
    "crisisgroup.org",
    "transparency.org",
    "freedomhouse.org",
    "esgtoday.com",
    "responsible-investor.com",
    "climateaction100.org"
    "bloomberg.com",
    "reuters.com/business",
    "wsj.com/news/markets",
    "marketwatch.com",
    "cnbc.com",
    "ft.com",
    "yahoo.com/finance",
    "investopedia.com",
    "sec.gov",
    "federalreserve.gov",
    "imf.org",
    "worldbank.org",
    "morningstar.com",
    "seekingalpha.com",
    "fool.com",
    "cftc.gov",
    "finra.org",
    "fdic.gov",
    "occ.gov",
    "consumerfinance.gov",
    "fca.org.uk",
    "esma.europa.eu",
    "eba.europa.eu",
    "bis.org",
    "iosco.org",
    "fincen.gov",
    "treasury.gov",
    "sanctionslist.ofac.treas.gov",
    "un.org",
    "europa.eu",
    "hm-treasury.gov.uk",
    "worldbank.org",
    "sam.gov",
    "fatf-gafi.org",
    "msci.com",
    "sustainalytics.com",
    "refinitiv.com",
    "spglobal.com",
    "cdp.net",
    "sasb.org",
    "globalreporting.org",
    "unglobalcompact.org",
    "tcfd-hub.org",
    "moodys.com",
    "standardandpoors.com",
    "fitchratings.com",
    "coface.com",
    "controlrisks.com",
    "courtlistener.com",
    "justia.com",
    "leagle.com",
    "casetext.com",
    "pacer.gov",
    "plainsite.org"
]

def process_tavily_from_urls(tavily_client: TavilyClient, urls: List[str], company_name: str=None):
    """
    Process Tavily queries from a list of URLs
    
    Args:
        tavily_client: Your Tavily client instance
        urls: List of URLs to search
    
    Returns:
        str: Combined results from all queries
    """
    try:
        print(f"Searching provide supporting links...")
        
        extract_response = tavily_client.extract(urls,extract_depth="advanced",timeout=180)
        extract_content = "\n".join(r['raw_content'] for r in extract_response['results'] if 'raw_content' in r)
        
        print(f"✓ Completed: {urls}")
        return extract_content
        
    except Exception as e:
        raise ValueError(f"Error in supporting links extraction: {e}")


def process_tavily_in_batches(tavily_client: TavilyClient, 
                              company_name: str,
                              country: str,
                              research_topic: str, 
                              search_queries: List[str], batch_size: int=4, delay_between_batches: int=2,
                              ):
    """
    Process Tavily queries in batches with threading
    
    Args:
        tavily_client: Your Tavily client instance
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
        """Execute a single Tavily query"""
        try:
            print(f"Searching: {query}")
            
            tavily_response = tavily_client.search(query=f"For {company_name} in {country}, {query}",
                                                   topic=research_topic,
                                                   search_depth="advanced",
                                                   max_results=os.getenv("TAVILY_MAX_RESULTS", 2),
                                                   time_range='year',
                                                   include_domains=DOMAINS,
                                                   timeout=180
                                                   )
            
            content = "\n".join(r['content'] for r in tavily_response['results'] if 'content' in r)
            
            print(f"✓ Completed: {query}")
            return content
            
        except Exception as e:
            print(f"✗ ERROR in query '{query}': {e}")
            raise RuntimeError(f"Error in query '{query}': {e}")
    
    all_results = ""
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
                    all_results += result + "\n\n"
        
        print(f"[BATCH {batch_num}] Completed!")
        
        # Wait before next batch (except for the last batch)
        if i + batch_size < total_queries:
            print(f"Waiting {delay_between_batches} seconds before next batch...")
            time.sleep(delay_between_batches)
    
    return all_results


def generate_questions(company_name, prompt):
    question_prompt = """
    Based on the following company name and user requirements, generate 10 specific question, 
    targeted search questions that would help gather comprehensive information to answer the user's requirements.

    Company Name: {company_name}

    User Requirements/Focus Area:
    {prompt}

    Understand the User Requirements/Focus Area and Generate 15 diverse search questions that cover different aspects of the topic. 
    Make the questions:
    1. Specific to the company name provided
    2. Relevant to the user's requirements
    3. Suitable for web search engines
    4. Cover different angles and perspectives
    5. Include both general and specific queries
    6. Mix of company-specific and industry/regulatory queries

    Format your response as a JSON object with a "questions" key containing an array of 10 questions.
    Do not include any explanations or additional text, just the numbered questions.

    Return the data in this exact JSON format and DO NOT include any other text:
    {{
        "questions": [
            "Question 1",
            "Question 2",
            ...
            "Question 10"
        ]
    }}
    """
    def get_response(prompt:str):
        return llm.invoke(prompt)
    formatted_prompt = question_prompt.format(company_name=company_name, prompt=prompt)
    final_unparsed = get_response(formatted_prompt)
    final_structured_data = parser.parse(final_unparsed.content)
    return final_structured_data