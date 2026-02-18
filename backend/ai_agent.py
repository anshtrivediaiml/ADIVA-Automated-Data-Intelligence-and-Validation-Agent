"""
ADIVA - AI Agent Module

This module handles interaction with Mistral AI LLM:
- Document classification
- Schema-based structured data extraction
- Response parsing and validation
"""

import json
import re
from typing import Dict, Any, Optional
from mistralai import Mistral
import config
from schemas import get_schema, SCHEMA_REGISTRY
from logger import logger, log_ai_response, log_error


class AIAgent:
    """
    Manages interaction with Mistral AI for document intelligence
    """
    
    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize AI agent with Mistral API credentials
        
        Args:
            api_key: Mistral AI API key (optional, uses config if not provided)
        """
        self.api_key = api_key or config.MISTRAL_API_KEY
        
        if not self.api_key:
            raise ValueError("Mistral API key not provided")
        
        # Initialize Mistral client
        self.client = Mistral(api_key=self.api_key)
        self.model = config.MISTRAL_MODEL
        self.temperature = config.MISTRAL_TEMPERATURE
        self.max_tokens = config.MISTRAL_MAX_TOKENS
        
        logger.info(f"AIAgent initialized with model: {self.model}")
    
    def classify_document(self, text_sample: str, max_length: int = 2000) -> Dict[str, Any]:
        """
        Classify document type using Mistral AI
        
        Args:
            text_sample: Sample text from document
            max_length: Maximum characters to use for classification
            
        Returns:
            Classification result with type, confidence, and reasoning
        """
        try:
            # Truncate text sample
            sample = text_sample[:max_length]
            
            # Create classification prompt
            prompt = f"""Analyze the following document excerpt and classify its type.

Document types to choose from:
- invoice: Bills, invoices, receipts, payment documents
- resume: CVs, resumes, job applications, professional profiles
- contract: Agreements, contracts, legal documents, terms of service
- report: Business reports, analysis documents, white papers
- letter: Business letters, correspondence
- form: Application forms, questionnaires
- other: Any document that doesn't fit the above categories

Document excerpt:
{sample}

Respond ONLY with valid JSON in this exact format:
{{
  "document_type": "one of the types above",
  "confidence": 0.95,
  "reasoning": "brief explanation of why you chose this type",
  "alternative_type": "second most likely type or null"
}}"""

            # Call Mistral API
            logger.info("Calling Mistral AI for document classification")
            response = self.client.chat.complete(
                model=self.model,
                messages=[
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,  # Low temperature for consistent classification
                max_tokens=500
            )
            
            # Extract response
            response_text = response.choices[0].message.content
            log_ai_response(len(prompt), len(response_text), self.model)
            
            # Parse JSON response
            result = self._parse_json_response(response_text)
            
            if not result or 'document_type' not in result:
                raise ValueError("Invalid classification response format")
            
            logger.info(f"Document classified as: {result['document_type']} (confidence: {result.get('confidence', 0)})")
            return result
            
        except Exception as e:
            log_error("DocumentClassification", str(e))
            # Return default classification
            return {
                'document_type': 'other',
                'confidence': 0.0,
                'reasoning': f'Classification failed: {str(e)}',
                'alternative_type': None
            }
    
    def extract_structured_data(self, full_text: str, document_type: str) -> Dict[str, Any]:
        """
        Extract structured data based on document type schema
        
        Args:
            full_text: Complete document text
            document_type: Type of document (invoice, resume, contract)
            
        Returns:
            Extracted structured data matching the schema
        """
        try:
            # Get schema for document type
            schema = get_schema(document_type)
            
            if not schema:
                logger.warning(f"No schema found for document type: {document_type}")
                return {}
            
            # Get schema definition and instructions
            schema_dict = schema.get_schema()
            instructions = schema.get_prompt_instructions()
            
            # Create extraction prompt
            prompt = self._create_extraction_prompt(full_text, document_type, schema_dict, instructions)
            
            # Call Mistral API
            logger.info(f"Calling Mistral AI for {document_type} data extraction")
            response = self.client.chat.complete(
                model=self.model,
                messages=[
                    {"role": "user", "content": prompt}
                ],
                temperature=self.temperature,
                max_tokens=self.max_tokens
            )
            
            # Extract response
            response_text = response.choices[0].message.content
            log_ai_response(len(prompt), len(response_text), self.model)
            
            # Parse JSON response
            extracted_data = self._parse_json_response(response_text)
            
            if not extracted_data:
                raise ValueError("Failed to parse extraction response")
            
            # Validate against schema
            is_valid, issues = schema.validate_extracted_data(extracted_data)
            
            if not is_valid:
                logger.warning(f"Validation issues: {issues}")
            
            logger.info(f"Successfully extracted {len(extracted_data)} top-level fields")
            return extracted_data
            
        except Exception as e:
            log_error("StructuredExtraction", str(e), f"Document type: {document_type}")
            return {}
    
    def _create_extraction_prompt(self, text: str, doc_type: str, schema: dict, instructions: str) -> str:
        """
        Create prompt for structured extraction
        
        Args:
            text: Document text
            doc_type: Document type
            schema: Schema dictionary
            instructions: Extraction instructions
            
        Returns:
            Formatted prompt
        """
        schema_json = json.dumps(schema, indent=2)
        
        prompt = f"""{instructions}

SCHEMA TO EXTRACT:
{schema_json}

DOCUMENT TEXT:
{text}

CRITICAL INSTRUCTIONS:
1. Respond ONLY with valid JSON matching the schema structure
2. Use null for any missing fields
3. Ensure all dates are in the correct format
4. Extract ALL relevant information
5. Do NOT include any explanatory text outside the JSON

Extract the data now:"""

        return prompt
    
    def _parse_json_response(self, response_text: str) -> Optional[Dict[str, Any]]:
        """
        Parse JSON from LLM response, handling various formats
        
        Args:
            response_text: Raw response from LLM
            
        Returns:
            Parsed JSON dictionary or None
        """
        try:
            # Try direct JSON parse first
            return json.loads(response_text)
        except json.JSONDecodeError:
            # Try to extract JSON from markdown code blocks
            json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', response_text, re.DOTALL)
            if json_match:
                try:
                    return json.loads(json_match.group(1))
                except:
                    pass
            
            # Try to find JSON object in text
            json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
            if json_match:
                try:
                    return json.loads(json_match.group(0))
                except:
                    pass
            
            logger.error("Failed to parse JSON from response")
            return None
    
    def calculate_extraction_confidence(self, extracted_data: dict, schema_type: str) -> float:
        """
        Calculate confidence score for extracted data
        
        Args:
            extracted_data: Extracted data dictionary
            schema_type: Type of schema used
            
        Returns:
            Confidence score (0.0 to 1.0)
        """
        schema = get_schema(schema_type)
        if not schema:
            return 0.0
        
        required_fields = schema.get_required_fields()
        if not required_fields:
            return 1.0
        
        # Count how many required fields are present and non-null
        present_count = 0
        for field in required_fields:
            if '.' in field:
                # Nested field
                parts = field.split('.')
                current = extracted_data
                found = True
                for part in parts:
                    if isinstance(current, dict) and part in current and current[part] is not None:
                        current = current[part]
                    else:
                        found = False
                        break
                if found:
                    present_count += 1
            else:
                # Top-level field
                if field in extracted_data and extracted_data[field] is not None:
                    present_count += 1
        
        # Calculate confidence based on required field presence
        confidence = present_count / len(required_fields) if required_fields else 1.0
        return round(confidence, 2)
