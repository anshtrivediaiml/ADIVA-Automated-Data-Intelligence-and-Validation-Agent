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
The document may be in English, Hindi, or Gujarati language.

Document types to choose from (choose the MOST SPECIFIC match):

── General Documents ──────────────────────────────────────────────────────────
- invoice: Tax invoices, GST bills, receipts (कर चालान, GST बिल, केवटे / ઇન્વૉઇ, GST ચલણ)
- resume: CV, resume, biodata, job application (बायोडाटा / બાયોડેટા)
- contract: Service agreements, NDAs, rental agreements (सेवा अनुबंध, किरायानामा / ભાડા કરાર)
- prescription: Doctor prescription with medicine name+dosage (पर्चा, दवा / દવા)
- certificate: Marriage/educational/completion certificate with registration number and official seal (प्रमाण पत्र / પ્રમાણ પત્ર) — only use if not birth/death/GST/driving certificate
- bank_statement: Bank passbook, account statement with debit/credit transactions (बैंक पासबुक, खाता विवरण / બૅન્ક પાસ-બૂક)
- marksheet: Exam result sheet, report card, mark list (अंकसूची, परिणाम पत्र / માર્કશીટ)
- ration_card: Ration card with family members and ration shop (राशन कार्ड / રેશન કાર્ડ)
- utility_bill: Electricity/water/gas bill with meter reading and due date (विद्युत बिल, पानी बिल / વીજ બિલ, ગૅસ બિલ)

── Identity Documents ──────────────────────────────────────────────────────────
- aadhar_card: Aadhaar card with 12-digit UID, UIDAI logo (आधार, UID / આઘાર, UID)
- pan_card: PAN card with 10-char PAN number, Income Tax Department (पैन कार्ड / પૅન કાર્ડ)
- driving_licence: Driving licence with vehicle class (LMV/MCWG/HMV), RTO (ड्राइविंग लाइसेंस / ડ્રાઇવિંગ લાઇસન્સ)
- passport: Indian passport with passport number (P<IND), MRZ lines, Republic of India (पासपोर्ट / પાસ-પ-ોર્ટ)

── Financial Documents ─────────────────────────────────────────────────────────
- cheque: Bank cheque or demand draft with MICR band, payee name, amount (चेक, बैंक ड्राफ्ट / ચૅક, ડ્રાફ્ટ)
- form_16: Form 16 TDS certificate with TAN, Assessment Year, employer/employee (फॉर्म 16, टीडीएस / ફૉ-ર્મ 16)
- insurance_policy: Insurance policy/cover note with policy number, sum assured, premium, nominee (बीमा पॉलिसी / વીમો)
- gst_certificate: GST registration certificate with GSTIN 15-char code (जीएसटी प्रमाण पत्र / GST પ્રમાણ પત્ર)

── Civil / Government Records ──────────────────────────────────────────────────
- birth_certificate: Birth certificate with child's name, date of birth, hospital/place of birth, parents (जन्म प्रमाण पत्र / જન્મ દાખલો)
- death_certificate: Death certificate with deceased name, date of death, cause of death (मृत्यु प्रमाण पत्र / મૃત્યુ દાખલો)
- land_record: Land record — 7/12 Utara, Khatauni, Jamabandi — with survey/khasra/gut number and owner list (7/12 उतारा, खसरा / 7/12 ઉતારો)
- nrega_card: NREGA/MGNREGA job card with job card number, gram panchayat, work entries (नरेगा जॉब कार्ड / નરેગા-જૉબ-કાર્ડ)

── Fallback ────────────────────────────────────────────────────────────────────
- form: Generic application forms, questionnaires not fitting above categories
- other: Document that doesn't fit any above category

Document excerpt:
{sample}

Respond ONLY with valid JSON in this exact format:
{{
  "document_type": "one of the exact type keys above",
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
        Extract structured data based on document type schema.
        Case 7: For long documents (> 8000 chars), uses chunked extraction
        with overlap and merges results for complete coverage.
        """
        try:
            schema = get_schema(document_type)
            if not schema:
                logger.warning(f"No schema found for document type: {document_type}")
                return {}

            schema_dict = schema.get_schema()
            instructions = schema.get_prompt_instructions()

            # Case 7: Chunked extraction for long documents
            CHUNK_SIZE = 4000
            OVERLAP = 500

            if len(full_text) > CHUNK_SIZE * 2:
                logger.info(
                    f"Long document ({len(full_text)} chars) — using chunked extraction "
                    f"(chunks={CHUNK_SIZE}, overlap={OVERLAP})"
                )
                return self._extract_chunked(
                    full_text, document_type, schema_dict, instructions,
                    chunk_size=CHUNK_SIZE, overlap=OVERLAP
                )

            # Normal single-pass extraction
            prompt = self._create_extraction_prompt(full_text, document_type, schema_dict, instructions)
            logger.info(f"Calling Mistral AI for {document_type} data extraction")
            response = self.client.chat.complete(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=self.temperature,
                max_tokens=self.max_tokens
            )
            response_text = response.choices[0].message.content
            log_ai_response(len(prompt), len(response_text), self.model)

            extracted_data = self._parse_json_response(response_text)
            if not extracted_data:
                raise ValueError("Failed to parse extraction response")

            is_valid, issues = schema.validate_extracted_data(extracted_data)
            if not is_valid:
                logger.warning(f"Validation issues: {issues}")

            logger.info(f"Successfully extracted {len(extracted_data)} top-level fields")
            return extracted_data

        except Exception as e:
            log_error("StructuredExtraction", str(e), f"Document type: {document_type}")
            return {}

    def _extract_chunked(
        self, full_text: str, document_type: str,
        schema_dict: dict, instructions: str,
        chunk_size: int = 4000, overlap: int = 500
    ) -> Dict[str, Any]:
        """
        Extract structured data from a long document by chunking.
        Merges results: later chunks fill in null fields from earlier chunks.
        """
        # Build chunks with overlap
        chunks = []
        start = 0
        while start < len(full_text):
            end = min(start + chunk_size, len(full_text))
            chunks.append(full_text[start:end])
            if end == len(full_text):
                break
            start = end - overlap

        logger.info(f"Chunked extraction: {len(chunks)} chunks for {document_type}")

        merged = {}
        for i, chunk in enumerate(chunks):
            logger.info(f"Extracting chunk {i+1}/{len(chunks)} ({len(chunk)} chars)")
            try:
                prompt = self._create_extraction_prompt(
                    chunk, document_type, schema_dict, instructions
                )
                response = self.client.chat.complete(
                    model=self.model,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=self.temperature,
                    max_tokens=self.max_tokens
                )
                chunk_data = self._parse_json_response(response.choices[0].message.content)
                if chunk_data:
                    merged = self._merge_extraction_results(merged, chunk_data)
            except Exception as e:
                logger.warning(f"Chunk {i+1} extraction failed: {e}")
                continue

        merged['_chunked_extraction'] = True
        merged['_chunks_processed'] = len(chunks)
        return merged

    def _merge_extraction_results(self, base: dict, update: dict) -> dict:
        """
        Merge two extraction result dicts.
        Rule: update values override base values ONLY if base value is null/empty.
        Lists are extended (not replaced) to accumulate items across chunks.
        """
        if not base:
            return dict(update)

        result = dict(base)
        for key, val in update.items():
            if key not in result or result[key] is None or result[key] == '':
                result[key] = val
            elif isinstance(result[key], list) and isinstance(val, list):
                # Extend lists (e.g. transactions, line_items, family_members)
                existing_strs = {str(item) for item in result[key]}
                for item in val:
                    if str(item) not in existing_strs:
                        result[key].append(item)
            elif isinstance(result[key], dict) and isinstance(val, dict):
                result[key] = self._merge_extraction_results(result[key], val)
        return result


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
