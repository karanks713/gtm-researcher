from FunctionTools.tavily_batch import process_tavily_from_urls, generate_questions
from elsai_core.model.azure_openai_connector import AzureOpenAIConnector
from FunctionTools.perplexity import process_perplexity_in_batches
from tavily import TavilyClient
from typing import List, Dict, Any
import os
from concurrent.futures import ThreadPoolExecutor
import time
import requests
import traceback
import asyncio
import json
from dataclasses import dataclass
from enum import Enum
import logging
from dotenv import load_dotenv 

load_dotenv()
logger = logging.getLogger(__name__)

# Import validation classes from smp.py
class ValidationLevel(Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"

@dataclass
class ValidationResult:
    is_valid: bool
    confidence_score: float
    issues: List[str]
    supporting_sources: List[str]
    contradictory_sources: List[str]

@dataclass
class RiskDataPoint:
    metric_name: str
    value: Any
    source: str
    timestamp: str
    confidence: float
    validation_result: ValidationResult

class RealTimeValidator:
    """Real-time validation logic for geographic risk data"""
    
    def __init__(self, llm, research_func):
        self.llm = llm
        self.research = research_func
        self.validation_cache = {}
    
    async def validate_claim(self, claim: str, context: Dict) -> ValidationResult:
        """Validate a specific claim with cross-referencing"""
        
        # Generate validation queries
        validation_queries = self._generate_validation_queries(claim, context)
        
        # Parallel validation searches
        validation_results = await self._parallel_validation_search(validation_queries)
        
        # Cross-reference analysis
        cross_ref_result = await self._cross_reference_analysis(claim, validation_results)
        
        # Temporal consistency check
        temporal_check = await self._temporal_consistency_check(claim, context)
        
        # Calculate final validation score
        return self._calculate_validation_score(cross_ref_result, temporal_check)
    
    def _generate_validation_queries(self, claim: str, context: Dict) -> List[str]:
        """Generate specific validation queries for fact-checking"""
        
        prompt = f"""
        Generate 4-5 specific search queries to validate this claim:
        CLAIM: {claim}
        CONTEXT: Company: {context.get('company_name')}, Country: {context.get('country')}
        
        Create queries that would:
        1. Find supporting evidence from official sources
        2. Find contradictory information
        3. Check recent updates or changes
        4. Verify numerical data from authoritative sources
        5. Cross-check with industry reports
        
        Return only the search queries, one per line.
        """
        
        response = self.llm.invoke(prompt)
        return [q.strip() for q in response.content.split('\n') if q.strip()]
    
    async def _parallel_validation_search(self, queries: List[str]) -> List[Dict]:
        """Execute validation searches in parallel"""
        
        async def search_query(query):
            try:
                result = self.research(query)
                return {
                    'query': query,
                    'result': result,
                    'success': True
                }
            except Exception as e:
                return {
                    'query': query,
                    'error': str(e),
                    'success': False
                }
        
        # Execute all searches concurrently
        tasks = [search_query(query) for query in queries]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        return [r for r in results if isinstance(r, dict) and r.get('success')]
    
    async def _cross_reference_analysis(self, claim: str, search_results: List[Dict]) -> Dict:
        """Analyze search results for cross-referencing"""
        
        combined_content = "\n\n".join([
            f"Query: {r['query']}\nResults: {r['result']['choices'][0]['message']['content']}"
            for r in search_results
        ])
        
        prompt = f"""
        You are a fact-checking analyst. Analyze the following search results to validate this claim:
        
        CLAIM TO VALIDATE: {claim}
        
        SEARCH RESULTS:
        {combined_content}
        
        Provide analysis in this JSON format:
        {{
            "supporting_evidence": ["list of supporting facts with sources"],
            "contradictory_evidence": ["list of contradictory facts with sources"],
            "confidence_score": 0.0-1.0,
            "reliability_assessment": "assessment of source quality",
            "consistency_check": "are the sources consistent with each other?",
            "recency_check": "how recent is the information?",
            "authority_check": "are sources authoritative and credible?"
        }}
        """
        
        response = self.llm.invoke(prompt)
        try:
            return json.loads(response.content)
        except json.JSONDecodeError:
            # Fallback parsing if JSON fails
            return self._parse_validation_response(response.content)
    
    def _parse_validation_response(self, content: str) -> Dict:
        """Fallback parser for validation response"""
        return {
            "supporting_evidence": [],
            "contradictory_evidence": [],
            "confidence_score": 0.5,
            "reliability_assessment": "Unable to parse",
            "consistency_check": "Unknown",
            "recency_check": "Unknown",
            "authority_check": "Unknown"
        }
    
    async def _temporal_consistency_check(self, claim: str, context: Dict) -> Dict:
        """Check if claim is consistent across time periods"""
        
        time_periods = [
            "2023-2024 recent data",
            "2022-2023 historical comparison", 
            "5-year trend analysis"
        ]
        
        temporal_queries = [
            f"{claim} {period} {context.get('company_name')} {context.get('country')}"
            for period in time_periods
        ]
        
        temporal_results = await self._parallel_validation_search(temporal_queries)
        
        prompt = f"""
        Analyze temporal consistency of this claim across different time periods:
        
        CLAIM: {claim}
        
        TEMPORAL DATA:
        {json.dumps(temporal_results, indent=2)}
        
        Return JSON:
        {{
            "temporal_consistency": 0.0-1.0,
            "trend_direction": "improving/declining/stable/volatile",
            "recent_changes": ["list of recent significant changes"],
            "consistency_issues": ["list of temporal inconsistencies found"]
        }}
        """
        
        response = self.llm.invoke(prompt)
        try:
            return json.loads(response.content)
        except json.JSONDecodeError:
            return {"temporal_consistency": 0.5, "trend_direction": "unknown", "recent_changes": [], "consistency_issues": []}
    
    def _calculate_validation_score(self, cross_ref: Dict, temporal: Dict) -> ValidationResult:
        """Calculate final validation score and result"""
        
        # Weighted scoring
        cross_ref_score = cross_ref.get('confidence_score', 0.5)
        temporal_score = temporal.get('temporal_consistency', 0.5)
        
        # Final confidence (weighted average)
        final_confidence = (cross_ref_score * 0.7) + (temporal_score * 0.3)
        
        # Determine validity
        is_valid = final_confidence >= 0.6
        
        # Compile issues
        issues = []
        if cross_ref.get('contradictory_evidence'):
            issues.extend(cross_ref['contradictory_evidence'])
        if temporal.get('consistency_issues'):
            issues.extend(temporal['consistency_issues'])
        
        return ValidationResult(
            is_valid=is_valid,
            confidence_score=final_confidence,
            issues=issues,
            supporting_sources=cross_ref.get('supporting_evidence', []),
            contradictory_sources=cross_ref.get('contradictory_evidence', [])
        )

class EnhancedDataCollector:
    """Enhanced data collection with iterative refinement"""
    
    def __init__(self, llm, research_func, validator: RealTimeValidator):
        self.llm = llm
        self.research = research_func
        self.validator = validator
        
    async def collect_comprehensive_data(self, company_name: str, country: str, 
                                       search_queries: List[str] = None) -> Dict:
        """Collect data with iterative refinement and validation"""
        
        # Phase 1: Initial research using existing queries or generate new ones
        if search_queries is None:
            search_queries = await self._generate_comprehensive_queries(company_name, country)
        
        initial_data = await self._initial_research_phase(company_name, country, search_queries)
        
        # Phase 2: Gap identification and targeted research
        gaps = await self._identify_data_gaps(initial_data, company_name, country)
        targeted_data = await self._targeted_research_phase(gaps, company_name, country)
        
        # Phase 3: Data validation and refinement
        validated_data = await self._validation_phase(initial_data, targeted_data, 
                                                    company_name, country)
        
        # Phase 4: Final synthesis
        final_data = await self._synthesis_phase(validated_data, company_name, country)
        
        return final_data
    
    async def _generate_comprehensive_queries(self, company_name: str, country: str) -> List[str]:
        """Generate comprehensive search queries"""
        
        prompt = f"""
        Generate 8-10 comprehensive search queries for researching {company_name} in {country}.
        Focus on different risk categories and data types.
        
        Categories to cover:
        1. Financial exposure and revenue breakdown
        2. Political and regulatory risks
        3. Economic indicators and stability
        4. Operational and infrastructure risks
        5. Historical events and precedents
        
        Return only the search queries, one per line.
        """
        
        response = self.llm.invoke(prompt)
        queries = [q.strip() for q in response.content.split('\n') if q.strip()]
        return queries[:10]  # Limit to 10 queries
    
    async def _initial_research_phase(self, company_name: str, country: str, 
                                    search_queries: List[str]) -> Dict:
        """Execute initial research phase with existing batch processing"""
        
        # Use existing process_perplexity_in_batches function
        try:
            context = process_perplexity_in_batches(
                company_name=company_name,
                country=country,
                search_queries=search_queries,
                batch_size=int(os.getenv('QUERY_BATCH_SIZE', '4')),
                delay_between_batches=int(os.getenv('DELAY_BETWEEN_BATCHES', '2'))
            )
            
            return {'batch_results': context, 'queries_used': search_queries}
            
        except Exception as e:
            logger.error(f"Initial research phase failed: {e}")
            return {'batch_results': '', 'queries_used': search_queries, 'error': str(e)}
    
    async def _identify_data_gaps(self, initial_data: Dict, company_name: str, country: str) -> List[str]:
        """Identify gaps in collected data"""
        
        prompt = f"""
        Analyze the research data below and identify specific gaps that need additional investigation for {company_name} in {country}.

        CURRENT DATA:
        {initial_data.get('batch_results', '')[:2000]}  # Truncate for analysis
        
        QUERIES USED:
        {initial_data.get('queries_used', [])}

        Identify 4-6 specific additional search queries needed to fill critical gaps:
        
        Focus on:
        1. Missing quantitative data (percentages, ratings, scores)
        2. Recent developments or changes
        3. Comparative analysis with competitors
        4. Regulatory or policy specifics
        
        Return only the search queries, one per line.
        """
        
        response = self.llm.invoke(prompt)
        gaps = [q.strip() for q in response.content.split('\n') if q.strip()]
        return gaps[:6]  # Limit to 6 additional queries
    
    async def _targeted_research_phase(self, gaps: List[str], company_name: str, country: str) -> Dict:
        """Execute targeted research to fill identified gaps"""
        
        if not gaps:
            return {'targeted_results': '', 'gap_queries': []}
        
        try:
            # Use existing research function for targeted queries
            targeted_context = process_perplexity_in_batches(
                company_name=company_name,
                country=country,
                search_queries=gaps,
                batch_size=int(os.getenv('QUERY_BATCH_SIZE', '4')),
                delay_between_batches=int(os.getenv('DELAY_BETWEEN_BATCHES', '2'))
            )
            
            return {'targeted_results': targeted_context, 'gap_queries': gaps}
            
        except Exception as e:
            logger.error(f"Targeted research phase failed: {e}")
            return {'targeted_results': '', 'gap_queries': gaps, 'error': str(e)}
    
    async def _validation_phase(self, initial_data: Dict, targeted_data: Dict, 
                              company_name: str, country: str) -> Dict:
        """Validate collected data using real-time validation"""
        
        # Extract key claims for validation
        all_content = initial_data.get('batch_results', '') + '\n' + targeted_data.get('targeted_results', '')
        key_claims = await self._extract_key_claims(all_content, company_name, country)
        
        # Validate each claim
        validation_results = {}
        context = {'company_name': company_name, 'country': country}
        
        # Limit validations to prevent overwhelming the system
        for claim in key_claims[:5]:  # Validate top 5 claims
            try:
                validation = await self.validator.validate_claim(claim, context)
                validation_results[claim] = validation
            except Exception as e:
                logger.error(f"Validation failed for claim '{claim}': {e}")
                validation_results[claim] = ValidationResult(
                    is_valid=False, confidence_score=0.0, issues=[str(e)],
                    supporting_sources=[], contradictory_sources=[]
                )
        
        return {
            'initial_data': initial_data,
            'targeted_data': targeted_data,
            'validations': validation_results
        }
    
    async def _extract_key_claims(self, content: str, company_name: str, country: str) -> List[str]:
        """Extract key factual claims that need validation"""
        
        prompt = f"""
        Extract 5-8 specific, factual claims about {company_name} in {country} that can be validated:

        CONTENT TO ANALYZE:
        {content[:3000]}  # Truncate content for analysis

        Return specific claims like:
        - "Company X derives 25% of revenue from Country Y"
        - "Country Z has a credit rating of BBB+ from S&P"
        - "Political stability index for Country A is 2.1 out of 10"
        
        Focus on:
        1. Numerical/quantitative claims
        2. Credit ratings and scores
        3. Revenue/financial exposure percentages  
        4. Regulatory status claims
        5. Risk assessment conclusions
        
        Return only the claims, one per line.
        """
        
        response = self.llm.invoke(prompt)
        claims = [claim.strip() for claim in response.content.split('\n') if claim.strip()]
        return claims[:8]
    
    async def _synthesis_phase(self, validated_data: Dict, company_name: str, country: str) -> Dict:
        """Final synthesis with confidence scoring"""
        
        validations_summary = {}
        for claim, validation in validated_data['validations'].items():
            validations_summary[claim] = {
                "valid": validation.is_valid,
                "confidence": validation.confidence_score,
                "issues": validation.issues[:2]  # Limit issues for readability
            }
        
        prompt = f"""
        Synthesize the validated research data into a comprehensive assessment for {company_name} in {country}.

        VALIDATION RESULTS:
        {json.dumps(validations_summary, indent=2)}

        ORIGINAL RESEARCH:
        {validated_data['initial_data'].get('batch_results', '')[:1500]}

        TARGETED RESEARCH:
        {validated_data['targeted_data'].get('targeted_results', '')[:1500]}

        Create a comprehensive synthesis that:
        1. Prioritizes high-confidence findings (confidence > 0.6)
        2. Flags low-confidence areas for manual review
        3. Provides overall assessment
        4. Includes data quality assessment
        
        Structure your response clearly with sections for validated findings, concerns, and recommendations.
        """
        
        response = self.llm.invoke(prompt)
        
        return {
            'synthesis': response.content,
            'data_quality_score': self._calculate_data_quality_score(validated_data),
            'high_confidence_claims': [
                claim for claim, validation in validated_data['validations'].items()
                if validation.confidence_score > 0.7
            ],
            'requires_manual_review': [
                claim for claim, validation in validated_data['validations'].items()
                if validation.confidence_score < 0.6
            ],
            'validation_summary': validations_summary
        }
    
    def _calculate_data_quality_score(self, validated_data: Dict) -> float:
        """Calculate overall data quality score"""
        validations = validated_data['validations']
        if not validations:
            return 0.0
        
        avg_confidence = sum(v.confidence_score for v in validations.values()) / len(validations)
        return round(avg_confidence, 2)

# Initialize global components
tavily = TavilyClient(api_key=os.getenv("TAVILY_API_KEY"))
connector = AzureOpenAIConnector()
llm = connector.connect_azure_open_ai("gpt-4o-mini")

def research(text):
    """Original research function"""
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
        raise Exception(f"Error in research: {e}")

# Initialize validator and enhanced collector
validator = RealTimeValidator(llm, research)
enhanced_collector = EnhancedDataCollector(llm, research, validator)

def process_perplexity_in_batches(company_name: str, country: str, search_queries: List[str], batch_size: int=4, delay_between_batches: int=2):
    """
    Process Perplexity queries in batches with threading (original function)
    """
    if company_name is None:
        raise ValueError(f"Company name not found. Please provide a valid company name.")
    
    def single_query(query, company_name, country):
        """Execute a single query"""
        try:
            print(f"Searching: {query}")
            
            perplexity_result = research(f"For {company_name} company located in {country}, Answer the following Question in detail: {query}.")
            
            content = perplexity_result['choices'][0]['message']['content']
            
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
                    all_results += result + "\n"
        
        print(f"[BATCH {batch_num}] Completed!")
        
        # Wait before next batch (except for the last batch)
        if i + batch_size < total_queries:
            print(f"Waiting {delay_between_batches} seconds before next batch...")
            time.sleep(delay_between_batches)
    
    return all_results

async def enhanced_research(company_name: str = None, 
                           country: str = None, 
                           search_queries: List[str] = None, 
                           prompt: str = None, 
                           support_urls: List[str] = None,
                           enable_validation: bool = True) -> dict:
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
        if prompt is None:
            raise ValueError("required parameter prompt is missing")
        
        print(f"Starting enhanced research for {company_name} in {country}...")
        
        # Generate search queries if not provided
        if search_queries is None:
            search_queries = generate_questions(company_name, prompt)['questions']
        
        if enable_validation:
            # Use enhanced data collection with validation
            enhanced_data = await enhanced_collector.collect_comprehensive_data(
                company_name=company_name,
                country=country,
                search_queries=search_queries
            )
            
            # Get context from enhanced data
            context = (enhanced_data['initial_data'].get('batch_results', '') + '\n' + 
                      enhanced_data['targeted_data'].get('targeted_results', ''))
            
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
                "support_urls": support_urls,
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
                    "research_phases": {
                        "initial_queries": enhanced_data['initial_data'].get('queries_used', []),
                        "gap_queries": enhanced_data['targeted_data'].get('gap_queries', [])
                    }
                }
            }
            
        else:
            # Use original research approach
            context = process_perplexity_in_batches(
                company_name=company_name,
                country=country,
                search_queries=search_queries,
                batch_size=int(os.getenv('QUERY_BATCH_SIZE', '4')),
                delay_between_batches=int(os.getenv('DELAY_BETWEEN_BATCHES', '2'))
            )
            
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
                "support_urls": support_urls,
                "prompt": prompt,
                "enhanced_features": {
                    "validation_enabled": False
                },
                "final_data": {
                    "web_response": final_response.content
                }
            }
        
        return response_data
        
    except Exception as e:
        raise RuntimeError(f"Enhanced research function error: {str(e)}")

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
    if enable_validation:
        # Use async enhanced research
        return asyncio.run(enhanced_research(
            company_name=company_name,
            country=country,
            search_queries=search_queries,
            prompt=prompt,
            support_urls=support_urls,
            enable_validation=True
        ))
    else:
        # Use original approach
        try:
            if prompt is None:
                raise ValueError("required parameter prompt is missing")
            if search_queries is None:
                search_queries = generate_questions(company_name, prompt)['questions']
            
            print(f"Searching for {company_name} company in {country}...")
            
            def get_response(prompt: str):
                return llm.invoke(prompt)
            
            context = process_perplexity_in_batches(
                company_name=company_name,
                country=country,
                search_queries=search_queries,
                batch_size=int(os.getenv('QUERY_BATCH_SIZE', '4')),
                delay_between_batches=int(os.getenv('DELAY_BETWEEN_BATCHES', '2'))
            )
            
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
                    "web_response": response.content
                }
            }
            
            return response_data
        except Exception as e:
            raise RuntimeError(f"Function Error: {str(e)}")