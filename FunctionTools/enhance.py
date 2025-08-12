from FunctionTools.perplexity import process_perplexity_in_batches
from typing import List, Dict
import json
from dataclasses import dataclass
import logging, traceback
from dotenv import load_dotenv 

load_dotenv()
logger = logging.getLogger(__name__)

@dataclass
class ValidationResult:
    is_valid: bool
    confidence_score: float
    issues: List[str]
    supporting_sources: List[str]
    contradictory_sources: List[str]


class EnhancedDataCollector:
    """Enhanced data collection with iterative refinement"""
    
    def __init__(self, llm):
        self.llm = llm
        self.perplexity_total_cost = 0
        self.perplexity_total_tokens = 0
        self.all_citations = []
        
    def collect_comprehensive_data_sync(self, company_name: str, country: str, 
                                      search_queries: List[str] = None) -> Dict:
        """Synchronous version of collect_comprehensive_data"""
        try:
        
            initial_data = self._initial_research_phase_sync(company_name, country, search_queries)
            
            # Phase 2: Gap identification and targeted research
            gaps = self._identify_data_gaps_sync(initial_data, company_name, country)
            targeted_data = self._targeted_research_phase_sync(gaps, company_name, country)
            
            # Phase 3: Data validation and refinement (simplified for sync)
            validated_data = self._validation_phase_sync(initial_data, targeted_data, 
                                                    company_name, country)
            
            # Phase 4: Final synthesis
            final_data = self._synthesis_phase_sync(validated_data, company_name, country)
            
            return final_data
            
        except Exception as e:
            logger.error(f"Enhanced data collection failed: {e}")
            raise RuntimeError(f"EnhancedDataCollector class failed: {traceback.format_exc()}")
    
    
    def _initial_research_phase_sync(self, company_name: str, country: str, 
                                   search_queries: List[str]) -> Dict:
        """Execute initial research phase with existing batch processing (synchronous)"""
        
        # Use existing process_perplexity_in_batches function
        try:
            context_dict = process_perplexity_in_batches(
                company_name=company_name,
                country=country,
                search_queries=search_queries,
                batch_size=2,
                delay_between_batches=2
            )
            
            context = context_dict['content']
            self.perplexity_total_tokens += context_dict['total_tokens']
            self.perplexity_total_cost += context_dict['total_cost']
            self.all_citations.extend(context_dict['citations'])
            
            
            return {'batch_results': context, 'queries_used': search_queries}
            
        except Exception as e:
            logger.error(f"Initial research phase failed: {e}")
            return {'batch_results': '', 'queries_used': search_queries, 'error': str(e)}
    
    def _identify_data_gaps_sync(self, initial_data: Dict, company_name: str, country: str) -> List[str]:
        """Identify gaps in collected data """
        
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
        5. Is the data is accurate
        
        Return only the search queries, one per line.
        """
        
        response = self.llm.invoke(prompt)
        gaps = [q.strip() for q in response.content.split('\n') if q.strip()]
        return gaps[:6]  # Limit to 6 additional queries
    
    def _targeted_research_phase_sync(self, gaps: List[str], company_name: str, country: str) -> Dict:
        """Execute targeted research to fill identified gaps (synchronous)"""
        
        if not gaps:
            return {'targeted_results': '', 'gap_queries': []}
        
        try:
            # Use existing research function for targeted queries
            context_dict = process_perplexity_in_batches(
                company_name=company_name,
                country=country,
                search_queries=gaps,
                batch_size=2,
                delay_between_batches=2
            )
            targeted_context = context_dict['content']
            self.perplexity_total_tokens += context_dict['total_tokens']
            self.perplexity_total_cost += context_dict['total_cost']
            self.all_citations.extend(context_dict['citations'])
            
            return {'targeted_results': targeted_context, 'gap_queries': gaps}
            
        except Exception as e:
            logger.error(f"Targeted research phase failed: {e}")
            return {'targeted_results': '', 'gap_queries': gaps, 'error': str(e)}
    
    def _validation_phase_sync(self, initial_data: Dict, targeted_data: Dict, 
                             company_name: str, country: str) -> Dict:
        """Validate collected data using simplified validation (synchronous)"""
        
        # Extract key claims for validation
        all_content = initial_data.get('batch_results', '') + '\n' + targeted_data.get('targeted_results', '')
        key_claims = self._extract_key_claims_sync(all_content, company_name, country)
        
        # Simplified validation using direct research calls (no async)
        validation_results = {}
        context = {'company_name': company_name, 'country': country}
        
        # Limit validations to prevent overwhelming the system
        for claim in key_claims[:10]:  # Validate top 10 claims only for sync version
            try:
                validation = self._validate_claim_sync(claim, context)
                validation_results[claim] = validation
            except Exception as e:
                logger.error(f"Validation failed for claim '{claim}': {e}")
                validation_results[claim] = ValidationResult(
                    is_valid=False, confidence_score=0.0, issues=[str(e)],
                    supporting_sources=[], contradictory_sources=[]
                )
        
        return {
            'initial_data': initial_data.get('batch_results', ''),
            'targeted_data': targeted_data.get('targeted_results', ''),
            'queries_used': initial_data.get('queries_used', []),
            'gap_queries': targeted_data.get('gap_queries', []),
            'validations': validation_results
        }
    
    def _extract_key_claims_sync(self, content: str, company_name: str, country: str) -> List[str]:
        """Extract key factual claims that need validation (synchronous)"""
        
        prompt = f"""
        Extract 8-10 specific, factual claims about {company_name} in {country} that needs to be validated:
        
        Most of the contents here are extracted from the initial research phase. to validate its accuracy and legitimacy
        You need findout areas that needs to be validated
        
        CONTENT TO ANALYZE:
        {content}  # Truncate content for analysis

        Return specific claims like example:
        - "Company {company_name} derives 25% of revenue from Country {country}"
        - "Country {country} has a credit rating of BBB+ from S&P"
        - "Political stability index for Country {country} is 2.1 out of 10"
        
        Focus on:
        1. Numerical/quantitative claims
        2. Credit ratings and scores
        3. Revenue/financial exposure percentages  
        4. Regulatory status claims
        5. Risk assessment conclusions
        
        Return only the claims that needs to be validated, one per line.
        """
        
        response = self.llm.invoke(prompt)
        claims = [claim.strip() for claim in response.content.split('\n') if claim.strip()]
        return claims[:10]  # Limit for sync version
    
    def _validate_claim_sync(self, claim: str, context: Dict) -> ValidationResult:
        """Simplified synchronous claim validation"""
        
        # Generate 2-3 validation queries (simplified)
        validation_queries = [
            f"Verify this claim: {claim} for {context.get('company_name')} in {context.get('country')}",
            f"Find contradictory evidence for: {claim} {context.get('company_name')} {context.get('country')}",
            f"Recent updates on: {claim} {context.get('company_name')} {context.get('country')}"
        ]
        
        supporting_evidence = []
        contradictory_evidence = []
        confidence_scores = []
        
        context_dict = process_perplexity_in_batches(
            company_name=context.get('company_name'),
            country=context.get('country'),
            search_queries=validation_queries,
            batch_size=2,
            delay_between_batches=2
        )
        
        content = context_dict['content']
        self.perplexity_total_tokens += context_dict['total_tokens']
        self.perplexity_total_cost += context_dict['total_cost']
        self.all_citations.extend(context_dict['citations'])
        
        try:
            # Simple analysis of validation content
            analysis_prompt = f"""
            Analyze if this content supports or contradicts the claim: "{claim}"
            
            CONTENT: {content}
            
            Respond with:
            SUPPORT_SCORE: 0.0-1.0 (how much it supports the claim)
            EVIDENCE_TYPE: supporting/contradictory/neutral
            KEY_POINT: one sentence summary
            """
            
            analysis = self.llm.invoke(analysis_prompt)
            analysis_content = analysis.content
            
            # Extract support score (simplified parsing)
            if "SUPPORT_SCORE:" in analysis_content:
                score_line = [line for line in analysis_content.split('\n') if "SUPPORT_SCORE:" in line][0]
                try:
                    score = float(score_line.split(':')[1].strip())
                    confidence_scores.append(score)
                except:
                    confidence_scores.append(0.5)
            
            # Categorize evidence
            if "supporting" in analysis_content.lower():
                supporting_evidence.append(content[:200] + "...")
            elif "contradictory" in analysis_content.lower():
                contradictory_evidence.append(content[:200] + "...")
        
        except Exception as e:
            logger.error(f"Validation query failed: {e}")
            confidence_scores.append(0.3)
        
        # Calculate final confidence
        avg_confidence = sum(confidence_scores) / len(confidence_scores) if confidence_scores else 0.5
        is_valid = avg_confidence >= 0.6
        
        return ValidationResult(
            is_valid=is_valid,
            confidence_score=avg_confidence,
            issues=contradictory_evidence,
            supporting_sources=supporting_evidence,
            contradictory_sources=contradictory_evidence
        )
    
    
    def _calculate_data_quality_score(self, validated_data: Dict) -> float:
        """Calculate overall data quality score"""
        validations = validated_data['validations']
        if not validations:
            return 0.0
        
        avg_confidence = sum(v.confidence_score for v in validations.values()) / len(validations)
        return round(avg_confidence, 2)
    
    
    def _synthesis_phase_sync(self, validated_data: Dict, company_name: str, country: str) -> Dict:
        """Final synthesis with confidence scoring (synchronous)"""
        # return {
            # 'initial_data': initial_data.get('batch_results', ''),
            # 'targeted_data': targeted_data.get('targeted_results', ''),
            # 'queries_used': initial_data.get('queries_used', []),
            # 'gap_queries': targeted_data.get('gap_queries', []),
            # 'validations': validation_results
            # }
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
        {validated_data['initial_data'][:3000]}

        TARGETED RESEARCH:
        {validated_data['targeted_data'][:3000]}

        Create a comprehensive synthesis that:
        1. Prioritizes high-confidence findings (confidence > 0.6)
        2. Flags low-confidence areas for manual review
        3. Provides overall assessment
        4. Includes data quality assessment
        
        Structure your response clearly with sections for validated findings, concerns, and recommendations.
        """
        
        response = self.llm.invoke(prompt)
        
        return {
            'initial_data': str(validated_data['initial_data'])[:3000],
            'targeted_data': str(validated_data['targeted_data'])[:3000],
            'queries_used': validated_data['queries_used'],
            'gap_queries': validated_data['gap_queries'],
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
            'validation_summary': json.dumps(validations_summary, indent=2)
        }
        
    async def collect_comprehensive_data(self, company_name: str, country: str, 
                                       search_queries: List[str] = None) -> Dict:
        """Async version - placeholder for future implementation"""
        # Using sync version for now to avoid event loop issues
        return self.collect_comprehensive_data_sync(company_name, country, search_queries)