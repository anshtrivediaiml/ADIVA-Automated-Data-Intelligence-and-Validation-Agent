"""
ADIVA - Contract Schema

Schema definition for contract documents.
Defines the structure for extracting data from contracts and agreements.
"""

from typing import Dict, Any
from schemas.base_schema import BaseSchema


class ContractSchema(BaseSchema):
    """
    Schema for contract/agreement documents
    """
    
    def get_schema(self) -> Dict[str, Any]:
        """Get contract schema structure"""
        return {
            "contract_title": "string",
            "contract_type": "string (e.g., Employment, Service, NDA, etc.)",
            "contract_number": "string",
            "contract_date": "string (YYYY-MM-DD)",
            "parties": [
                {
                    "name": "string",
                    "role": "string (e.g., Employer, Contractor, Vendor, Client)",
                    "address": "string",
                    "contact": "string",
                    "signatory": "string (person signing)"
                }
            ],
            "effective_date": "string (YYYY-MM-DD)",
            "expiration_date": "string (YYYY-MM-DD)",
            "term_duration": "string (e.g., '12 months', 'Indefinite')",
            "scope_of_work": "string (description of services/work)",
            "deliverables": ["string"],
            "payment_terms": {
                "amount": "number",
                "currency": "string",
                "schedule": "string (e.g., 'Monthly', 'Upon completion')",
                "method": "string (e.g., 'Bank transfer', 'Check')"
            },
            "obligations": {
                "party_1": ["string"],
                "party_2": ["string"]
            },
            "confidentiality": "string (confidentiality terms)",
            "termination_clause": "string (conditions for termination)",
            "dispute_resolution": "string (arbitration, mediation, etc.)",
            "governing_law": "string (jurisdiction)",
            "special_conditions": ["string"],
            "signatures": [
                {
                    "party": "string",
                    "signed_by": "string",
                    "date": "string (YYYY-MM-DD)"
                }
            ]
        }
    
    def get_prompt_instructions(self) -> str:
        """Get extraction instructions for contracts"""
        return """
You are extracting data from a CONTRACT or AGREEMENT document.

IMPORTANT INSTRUCTIONS:
1. Extract ALL key contract terms and conditions
2. Identify all parties involved and their roles
3. For missing information, use null
4. For dates, use ISO format (YYYY-MM-DD)
5. Extract obligations for each party separately
6. Identify payment terms including amount, schedule, and method
7. Extract termination conditions
8. Note any special provisions or conditions

FIELD DETAILS:
- contract_title: The name/title of the contract
- contract_type: Type of agreement (Employment, Service, etc.)
- parties: All entities/people involved in the contract
- effective_date: When the contract becomes active
- expiration_date: When the contract ends (if applicable)
- scope_of_work: What services/work is being contracted
- payment_terms: Financial arrangements
- obligations: What each party must do
- termination_clause: How the contract can be terminated
- governing_law: Which jurisdiction's laws apply
- special_conditions: Any unique terms or conditions

Focus on key legal and business terms. Be precise and thorough.
"""
    
    def get_required_fields(self) -> list:
        """Get list of required fields"""
        return [
            'contract_title',
            'parties',
            'effective_date'
        ]
