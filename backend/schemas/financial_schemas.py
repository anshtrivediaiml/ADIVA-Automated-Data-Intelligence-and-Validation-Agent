"""
ADIVA - Financial Document Schemas

Schemas for financial documents:
  - Bank Cheque / Demand Draft
  - Form 16 (TDS Certificate)
  - Insurance Policy
  - GST Registration Certificate
"""

from typing import Dict, Any
from schemas.base_schema import BaseSchema


class ChequeSchema(BaseSchema):
    """Schema for Bank Cheque or Demand Draft"""

    def get_schema(self) -> Dict[str, Any]:
        return {
            "cheque_number": "string (6-digit number printed at bottom left)",
            "cheque_type": "string ('Bearer Cheque', 'Account Payee', 'Demand Draft', 'Pay Order')",
            "bank_name": "string",
            "branch_name": "string",
            "branch_address": "string",
            "ifsc_code": "string",
            "micr_code": "string (9-digit MICR code at bottom)",
            "account_number": "string (account number of drawer)",
            "payee_name": "string (name written after 'Pay')",
            "amount_figures": "number (amount in digits, e.g. 50000.00)",
            "amount_words": "string (amount written in words)",
            "date": "string (YYYY-MM-DD — cheque date)",
            "drawer_name": "string (account holder / signatory if visible)",
            "memo": "string (any memo/note written on cheque, else null)",
            "crossed": "boolean (true if '||' crossing lines are present)"
        }

    def get_prompt_instructions(self) -> str:
        return """
You are extracting data from a BANK CHEQUE or DEMAND DRAFT.

IMPORTANT INSTRUCTIONS:
1. Cheque number is the 6-digit number in the MICR band at bottom left.
2. MICR code is the 9-digit code between the cheque number and account number at bottom.
3. Payee name is the name written on the "Pay" line.
4. Amount in figures is the number in the box (₹ amount).
5. Amount in words is the text on the "Rupees" line — extract exactly.
6. Date may be written in DD/MM/YYYY or in boxes — convert to YYYY-MM-DD.
7. "Account Payee" or "A/C Payee" crossing means crossed=true.
8. For Demand Drafts, drawer_name may be the issuing bank.
9. Use null for any field not visible.

Extract all fields precisely — especially cheque_number, amount, and payee.
"""

    def get_required_fields(self) -> list:
        return ['cheque_number', 'bank_name', 'payee_name', 'amount_figures', 'date']


class Form16Schema(BaseSchema):
    """Schema for Form 16 / TDS Certificate (Part A and/or Part B)"""

    def get_schema(self) -> Dict[str, Any]:
        return {
            "form_part": "string ('Part A', 'Part B', 'Both')",
            "assessment_year": "string (e.g. '2025-26')",
            "certificate_number": "string (unique certificate number)",
            "employer": {
                "name": "string",
                "tan": "string (Tax Deduction Account Number, format: AAAA99999A)",
                "address": "string",
                "pan": "string"
            },
            "employee": {
                "name": "string",
                "pan": "string",
                "designation": "string (if available)",
                "period_of_employment": {
                    "from": "string (YYYY-MM-DD)",
                    "to": "string (YYYY-MM-DD)"
                }
            },
            "income": {
                "gross_salary": "number",
                "allowances_exempt": "number",
                "net_taxable_salary": "number",
                "other_income": "number",
                "gross_total_income": "number"
            },
            "deductions": {
                "chapter_vi_a": "number (80C, 80D etc. total)",
                "section_80c": "number",
                "section_80d": "number",
                "section_80g": "number",
                "other_deductions": "number",
                "total_deductions": "number"
            },
            "tax": {
                "taxable_income": "number",
                "tax_on_income": "number",
                "rebate_87a": "number",
                "surcharge": "number",
                "health_education_cess": "number",
                "total_tax_payable": "number",
                "total_tds_deducted": "number",
                "tds_deposited": "number"
            },
            "quarter_details": [
                {
                    "quarter": "string (Q1/Q2/Q3/Q4)",
                    "amount_paid": "number",
                    "tds_deducted": "number",
                    "date_of_deposit": "string (YYYY-MM-DD)"
                }
            ]
        }

    def get_prompt_instructions(self) -> str:
        return """
You are extracting data from FORM 16 — the TDS (Tax Deducted at Source) Certificate
issued by an employer to an employee in India under the Income Tax Act.

IMPORTANT INSTRUCTIONS:
1. Form 16 has two parts: Part A (TDS details) and Part B (salary breakup).
2. The Assessment Year is typically the year after the financial year (e.g. FY 2024-25 → AY 2025-26).
3. TAN is the employer's 10-character Tax Deduction Account Number.
4. Extract ALL salary components and deductions under Chapter VI-A.
5. Quarter details (Q1=Apr-Jun, Q2=Jul-Sep, Q3=Oct-Dec, Q4=Jan-Mar) from Part A.
6. All amounts are in INR — extract as numbers without currency symbols.
7. Use null for any field not visible in the document.

This is a complex multi-section document — be thorough in extracting all financial fields.
"""

    def get_required_fields(self) -> list:
        return [
            'assessment_year', 'employer.name', 'employer.tan',
            'employee.name', 'employee.pan', 'tax.total_tds_deducted'
        ]


class InsurancePolicySchema(BaseSchema):
    """Schema for Insurance Policy document or Cover Note"""

    def get_schema(self) -> Dict[str, Any]:
        return {
            "policy_number": "string",
            "policy_type": "string ('Life', 'Health', 'Motor', 'Home', 'Travel', 'Term', 'Endowment', 'ULIP')",
            "insurer_name": "string (insurance company name)",
            "insurer_license_number": "string (IRDAI license number if visible)",
            "insured": {
                "name": "string",
                "dob": "string (YYYY-MM-DD)",
                "age": "number",
                "address": "string",
                "mobile": "string",
                "email": "string"
            },
            "nominee": {
                "name": "string",
                "relation": "string",
                "dob": "string (YYYY-MM-DD or null)",
                "share_percentage": "number"
            },
            "sum_assured": "number (in INR)",
            "premium_amount": "number (in INR)",
            "premium_frequency": "string ('Monthly', 'Quarterly', 'Half-yearly', 'Annually', 'Single')",
            "policy_term_years": "number",
            "premium_paying_term_years": "number",
            "policy_start_date": "string (YYYY-MM-DD)",
            "policy_end_date": "string (YYYY-MM-DD)",
            "next_premium_due": "string (YYYY-MM-DD)",
            "grace_period_days": "number",
            "riders": [
                {
                    "name": "string (e.g. 'Accidental Death Benefit')",
                    "sum_assured": "number",
                    "premium": "number"
                }
            ],
            "agent_name": "string (insurance agent if visible)",
            "agent_code": "string"
        }

    def get_prompt_instructions(self) -> str:
        return """
You are extracting data from an INSURANCE POLICY document or Cover Note.
This may be a Life, Health, Motor, or other type of insurance.

IMPORTANT INSTRUCTIONS:
1. Policy number is the unique identifier for this policy.
2. Policy type: identify from document content (Life/Health/Motor/Term/ULIP etc.)
3. Sum Assured is the coverage amount — the amount paid on claim.
4. Premium is the periodic payment amount.
5. Premium frequency: how often premium is paid (monthly/yearly etc.)
6. Nominee details are critical — extract carefully.
7. Riders are additional benefits attached to the main policy.
8. Insurer is the insurance company; Insured is the policyholder.
9. All dates in YYYY-MM-DD format.
10. Amounts in INR as numbers without currency symbols.
11. Use null for any field not visible.
"""

    def get_required_fields(self) -> list:
        return [
            'policy_number', 'policy_type', 'insurer_name',
            'insured.name', 'sum_assured', 'premium_amount',
            'policy_start_date', 'policy_end_date'
        ]


class GSTCertificateSchema(BaseSchema):
    """Schema for GST Registration Certificate"""

    def get_schema(self) -> Dict[str, Any]:
        return {
            "gstin": "string (15-character GST Identification Number)",
            "legal_name": "string (legal name of business)",
            "trade_name": "string (trade name if different from legal name, else null)",
            "constitution": "string ('Proprietorship', 'Partnership', 'Private Ltd', 'LLP', 'Trust', etc.)",
            "registration_date": "string (YYYY-MM-DD — effective date of GST registration)",
            "certificate_issue_date": "string (YYYY-MM-DD)",
            "cancellation_date": "string (YYYY-MM-DD or null if active)",
            "status": "string ('Active', 'Cancelled', 'Suspended')",
            "principal_place_of_business": {
                "address": "string",
                "city": "string",
                "state": "string",
                "pin_code": "string",
                "nature": "string (Own/Rented/Leased)"
            },
            "additional_places": [
                {
                    "address": "string",
                    "state": "string"
                }
            ],
            "nature_of_business": ["string (list of business activities)"],
            "authorized_signatory": {
                "name": "string",
                "designation": "string"
            },
            "jurisdiction": {
                "state": "string",
                "zone": "string",
                "division": "string",
                "range": "string"
            }
        }

    def get_prompt_instructions(self) -> str:
        return """
You are extracting data from a GST REGISTRATION CERTIFICATE issued by the
Goods and Services Tax (GST) Department of India.

IMPORTANT INSTRUCTIONS:
1. GSTIN is a 15-character code: first 2 = state code, next 10 = PAN, 13th = entity count,
   14th = 'Z' default, 15th = checksum. Example: 27AABCU9603R1ZX
2. Legal name is the officially registered business name.
3. Constitution is the type of business entity.
4. Registration date is when GST registration became effective.
5. Nature of business may list multiple activities.
6. Jurisdiction details are in the header of the certificate.
7. Extract state from 2-digit state code in GSTIN if not printed:
   27=Maharashtra, 24=Gujarat, 07=Delhi, 33=Tamil Nadu, etc.
8. Use null for any field not visible.

Extract all registration details precisely — GSTIN is the most critical field.
"""

    def get_required_fields(self) -> list:
        return ['gstin', 'legal_name', 'constitution', 'registration_date']
