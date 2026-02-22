"""
ADIVA - Bank Statement Schema

Schema for bank passbook pages and account statements.
Supports English, Hindi, and Gujarati.
"""

from typing import Dict, Any, List
from schemas.base_schema import BaseSchema


class BankStatementSchema(BaseSchema):
    """Schema for bank passbook pages and account statements"""

    def get_schema(self) -> Dict[str, Any]:
        return {
            "bank_name": "string - Name of the bank",
            "branch_name": "string - Branch name or null",
            "account_holder": "string - Account holder's full name",
            "account_number": "string - Account number",
            "ifsc_code": "string - IFSC code or null",
            "account_type": "string - Savings/Current/etc. or null",
            "statement_period": {
                "from_date": "string - Start date (YYYY-MM-DD) or null",
                "to_date": "string - End date (YYYY-MM-DD) or null"
            },
            "opening_balance": "number - Opening balance amount or null",
            "closing_balance": "number - Closing balance amount or null",
            "currency": "string - Currency code, default INR",
            "transactions": [
                {
                    "date": "string - Transaction date (YYYY-MM-DD)",
                    "description": "string - Transaction description/narration",
                    "debit": "number - Amount debited or null",
                    "credit": "number - Amount credited or null",
                    "balance": "number - Running balance after transaction or null"
                }
            ]
        }

    def get_prompt_instructions(self) -> str:
        return """You are extracting structured data from a bank passbook or account statement.
The document may be in English, Hindi, or Gujarati.

Instructions:
- Extract ALL transactions visible in the document as a list
- debit = money going OUT (withdrawal, Dr); credit = money coming IN (deposit, Cr)
- Preserve transaction descriptions as written (may be in Hindi/Gujarati)
- opening_balance = balance at the start of the statement period
- closing_balance = balance at the end / last entry
- If dates are in Indian format (DD/MM/YYYY), convert to YYYY-MM-DD
- account_number may be partially masked — extract what is visible"""

    def get_required_fields(self) -> List[str]:
        return ['bank_name', 'account_holder', 'account_number', 'transactions']


class UtilityBillSchema(BaseSchema):
    """Schema for utility bills (electricity, water, gas)"""

    def get_schema(self) -> Dict[str, Any]:
        return {
            "bill_type": "string - Electricity/Water/Gas/etc.",
            "provider_name": "string - Utility company name",
            "consumer_name": "string - Consumer/account holder name",
            "consumer_number": "string - Consumer/account number",
            "meter_number": "string - Meter number or null",
            "billing_address": "string - Consumer's address",
            "billing_period": "string - Billing period (e.g. February 2026)",
            "bill_date": "string - Bill issue date (YYYY-MM-DD) or null",
            "due_date": "string - Payment due date (YYYY-MM-DD)",
            "previous_reading": "number - Previous meter reading or null",
            "current_reading": "number - Current meter reading or null",
            "units_consumed": "number - Units consumed or null",
            "charges": {
                "energy_charge": "number - Energy/unit charge or null",
                "fixed_charge": "number - Fixed/demand charge or null",
                "taxes": "number - Total taxes or null",
                "other_charges": "number - Any other charges or null"
            },
            "total_amount": "number - Total amount payable",
            "currency": "string - Currency, default INR",
            "payment_options": ["string - Available payment methods"],
            "late_payment_surcharge": "string - Late payment penalty info or null"
        }

    def get_prompt_instructions(self) -> str:
        return """You are extracting structured data from a utility bill (electricity/water/gas).
The document may be in English, Hindi, or Gujarati.

Instructions:
- Identify the bill type from context (electricity = विद्युत/વીજ, water = जल/પાણી, gas = गैस/ગેસ)
- Extract meter readings if visible (previous and current)
- units_consumed = current_reading - previous_reading
- Extract all charge components separately if listed
- total_amount = the final amount to be paid
- due_date is critical — extract carefully
- payment_options = list of ways to pay (online, bank counter, etc.)"""

    def get_required_fields(self) -> List[str]:
        return ['provider_name', 'consumer_name', 'consumer_number', 'due_date', 'total_amount']


class MarksheetSchema(BaseSchema):
    """Schema for school/college mark sheets and report cards"""

    def get_schema(self) -> Dict[str, Any]:
        return {
            "institution_name": "string - School/college name",
            "exam_name": "string - Name of examination (e.g. Annual Exam 2025-26)",
            "student_name": "string - Student's full name",
            "roll_number": "string - Roll/registration number or null",
            "class_grade": "string - Class/grade (e.g. 10th, B.Sc. 2nd Year)",
            "academic_year": "string - Academic year (e.g. 2025-26)",
            "date_of_birth": "string - Student's DOB (YYYY-MM-DD) or null",
            "subjects": [
                {
                    "name": "string - Subject name",
                    "max_marks": "number - Maximum marks or null",
                    "marks_obtained": "number - Marks obtained",
                    "grade": "string - Grade/letter grade or null"
                }
            ],
            "total_marks": "number - Total marks obtained or null",
            "max_total_marks": "number - Maximum total marks or null",
            "percentage": "number - Percentage scored or null",
            "result": "string - Pass/Fail/Distinction or equivalent",
            "class_teacher": "string - Class teacher name or null",
            "principal": "string - Principal name or null",
            "issue_date": "string - Date of issue (YYYY-MM-DD) or null"
        }

    def get_prompt_instructions(self) -> str:
        return """You are extracting structured data from a school or college mark sheet / report card.
The document may be in English, Hindi, or Gujarati.

Instructions:
- Extract ALL subjects with their marks as a list
- Subject names may be in Hindi/Gujarati — preserve as written
- max_marks = पूर्णांक / total marks for that subject
- marks_obtained = प्राप्तांक / marks scored
- result = उत्तीर्ण (Pass) / अनुत्तीर्ण (Fail) / प्रथम श्रेणी (First Division)
- percentage = calculate if not explicitly stated: (total_marks/max_total_marks)*100
- Extract teacher and principal names from signature lines"""

    def get_required_fields(self) -> List[str]:
        return ['institution_name', 'student_name', 'exam_name', 'subjects', 'result']


class RationCardSchema(BaseSchema):
    """Schema for government ration cards and identity cards"""

    def get_schema(self) -> Dict[str, Any]:
        return {
            "card_type": "string - APL/BPL/Antyodaya/AAY or equivalent",
            "card_number": "string - Ration card number",
            "issuing_state": "string - State that issued the card",
            "issuing_department": "string - Department name",
            "head_of_family": {
                "name": "string - Head of family name",
                "father_husband_name": "string - Father's or husband's name or null",
                "address": "string - Full address",
                "district": "string - District or null",
                "pin_code": "string - PIN code or null"
            },
            "family_members": [
                {
                    "serial_number": "number - Serial number",
                    "name": "string - Member name",
                    "age": "number - Age or null",
                    "relation": "string - Relation to head of family"
                }
            ],
            "ration_shop": {
                "dealer_name": "string - Ration shop dealer name or null",
                "shop_number": "string - Shop number or null"
            },
            "issue_date": "string - Date of issue (YYYY-MM-DD) or null",
            "valid_until": "string - Validity date or null"
        }

    def get_prompt_instructions(self) -> str:
        return """You are extracting structured data from a government ration card.
The document may be in English, Hindi, or Gujarati.

Instructions:
- card_type: APL = Above Poverty Line, BPL = Below Poverty Line, Antyodaya/AAY = poorest families
- Extract ALL family members listed in the table
- relation examples: self/स्वयं, wife/पत्नी, son/पुत्र, daughter/पुत्री
- head_of_family = the primary card holder (usually listed first)
- Extract ration shop details if present
- card_number is usually prominently displayed at the top"""

    def get_required_fields(self) -> List[str]:
        return ['card_number', 'card_type', 'head_of_family.name', 'head_of_family.address', 'family_members']
