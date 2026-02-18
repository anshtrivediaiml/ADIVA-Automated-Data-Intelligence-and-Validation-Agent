"""
ADIVA - Schemas Package

Document type schemas for structured extraction.
"""

from schemas.base_schema import BaseSchema
from schemas.invoice_schema import InvoiceSchema
from schemas.resume_schema import ResumeSchema
from schemas.contract_schema import ContractSchema

# Schema registry
SCHEMA_REGISTRY = {
    'invoice': InvoiceSchema(),
    'resume': ResumeSchema(),
    'contract': ContractSchema(),
}

def get_schema(document_type: str) -> BaseSchema:
    """
    Get schema for a document type
    
    Args:
        document_type: Type of document (invoice, resume, contract)
        
    Returns:
        Schema instance
    """
    return SCHEMA_REGISTRY.get(document_type.lower())


__all__ = [
    'BaseSchema',
    'InvoiceSchema',
    'ResumeSchema',
    'ContractSchema',
    'SCHEMA_REGISTRY',
    'get_schema'
]
