"""
ADIVA - Schemas Package

Document type schemas for structured extraction.
Supports 21 document types across Indian government, financial, and general categories.
"""

from schemas.base_schema import BaseSchema

# Original schemas
from schemas.invoice_schema import InvoiceSchema
from schemas.resume_schema import ResumeSchema
from schemas.contract_schema import ContractSchema
from schemas.prescription_schema import PrescriptionSchema
from schemas.certificate_schema import CertificateSchema

# Utility / civic schemas
from schemas.utility_schemas import (
    BankStatementSchema,
    UtilityBillSchema,
    MarksheetSchema,
    RationCardSchema,
)

# ID document schemas
from schemas.id_schemas import (
    AadharCardSchema,
    PanCardSchema,
    DrivingLicenceSchema,
    PassportSchema,
)

# Financial document schemas
from schemas.financial_schemas import (
    ChequeSchema,
    Form16Schema,
    InsurancePolicySchema,
    GSTCertificateSchema,
)

# Government / civil record schemas
from schemas.govt_schemas import (
    BirthCertificateSchema,
    DeathCertificateSchema,
    LandRecordSchema,
    NREGACardSchema,
)

# Schema registry — maps document_type → schema instance
SCHEMA_REGISTRY = {
    # ── General documents ──────────────────────────────────────────────
    'invoice':          InvoiceSchema(),
    'resume':           ResumeSchema(),
    'contract':         ContractSchema(),
    'prescription':     PrescriptionSchema(),
    'certificate':      CertificateSchema(),

    # ── Civic / government ─────────────────────────────────────────────
    'bank_statement':   BankStatementSchema(),
    'utility_bill':     UtilityBillSchema(),
    'marksheet':        MarksheetSchema(),
    'ration_card':      RationCardSchema(),

    # ── Identity documents ─────────────────────────────────────────────
    'aadhar_card':      AadharCardSchema(),
    'pan_card':         PanCardSchema(),
    'driving_licence':  DrivingLicenceSchema(),
    'passport':         PassportSchema(),

    # ── Financial documents ────────────────────────────────────────────
    'cheque':           ChequeSchema(),
    'form_16':          Form16Schema(),
    'insurance_policy': InsurancePolicySchema(),
    'gst_certificate':  GSTCertificateSchema(),

    # ── Civil records ──────────────────────────────────────────────────
    'birth_certificate':  BirthCertificateSchema(),
    'death_certificate':  DeathCertificateSchema(),
    'land_record':        LandRecordSchema(),
    'nrega_card':         NREGACardSchema(),
}


def get_schema(document_type: str) -> BaseSchema:
    """
    Get schema for a document type.

    Args:
        document_type: Type of document (any of 21 supported types)

    Returns:
        Schema instance or None if not found
    """
    return SCHEMA_REGISTRY.get(document_type.lower())


__all__ = [
    'BaseSchema',
    # Original
    'InvoiceSchema', 'ResumeSchema', 'ContractSchema',
    'PrescriptionSchema', 'CertificateSchema',
    # Utility / civic
    'BankStatementSchema', 'UtilityBillSchema', 'MarksheetSchema', 'RationCardSchema',
    # ID
    'AadharCardSchema', 'PanCardSchema', 'DrivingLicenceSchema', 'PassportSchema',
    # Financial
    'ChequeSchema', 'Form16Schema', 'InsurancePolicySchema', 'GSTCertificateSchema',
    # Civil records
    'BirthCertificateSchema', 'DeathCertificateSchema', 'LandRecordSchema', 'NREGACardSchema',
    # Registry
    'SCHEMA_REGISTRY', 'get_schema',
]
