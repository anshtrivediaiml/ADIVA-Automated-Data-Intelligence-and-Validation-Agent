"""
ADIVA - Government Document Schemas

Schemas for Indian government-issued civil records:
  - Birth Certificate
  - Death Certificate
  - Land Record (7/12 Utara / Khatauni)
  - NREGA Job Card
"""

from typing import Dict, Any
from schemas.base_schema import BaseSchema


class BirthCertificateSchema(BaseSchema):
    """Schema for Birth Certificate issued by Indian municipal/government authority"""

    def get_schema(self) -> Dict[str, Any]:
        return {
            "registration_number": "string",
            "child_name": "string (null if not yet named at time of registration)",
            "gender": "string (Male / Female / Third Gender)",
            "dob": "string (YYYY-MM-DD — date of birth)",
            "time_of_birth": "string (HH:MM format or null)",
            "place_of_birth": {
                "hospital_name": "string (if born in hospital)",
                "village_town": "string",
                "district": "string",
                "state": "string"
            },
            "father": {
                "name": "string",
                "nationality": "string",
                "occupation": "string",
                "education": "string",
                "religion": "string",
                "aadhar": "string (if printed)"
            },
            "mother": {
                "name": "string",
                "nationality": "string",
                "occupation": "string",
                "education": "string",
                "religion": "string",
                "aadhar": "string (if printed)"
            },
            "permanent_address": "string",
            "present_address": "string",
            "registration_date": "string (YYYY-MM-DD — date of registration)",
            "issuing_authority": "string (municipality / gram panchayat / hospital)",
            "issue_date": "string (YYYY-MM-DD — date certificate was issued)",
            "registrar_name": "string"
        }

    def get_prompt_instructions(self) -> str:
        return """
You are extracting data from a BIRTH CERTIFICATE issued by an Indian government authority
(Municipal Corporation, Gram Panchayat, or Hospital).
The document may be in English, Hindi, or Gujarati.

IMPORTANT INSTRUCTIONS:
1. Registration number is the unique ID assigned at time of registration.
2. Child name may be absent if registered soon after birth — use null.
3. Date of birth and date of registration may differ.
4. Place of birth should distinguish hospital vs. home birth.
5. Both father and mother details are typically present.
6. Extract religion and nationality if printed.
7. Issuing authority is the municipal body that issued the certificate.
8. Use null for any field not visible.

Extract all fields precisely — registration_number, dob, and parents' names are critical.
"""

    def get_required_fields(self) -> list:
        return ['registration_number', 'dob', 'gender', 'father.name', 'mother.name']


class DeathCertificateSchema(BaseSchema):
    """Schema for Death Certificate issued by Indian municipal/government authority"""

    def get_schema(self) -> Dict[str, Any]:
        return {
            "registration_number": "string",
            "deceased_name": "string",
            "gender": "string (Male / Female / Third Gender)",
            "age": "number (age at time of death, in years)",
            "dod": "string (YYYY-MM-DD — date of death)",
            "time_of_death": "string (HH:MM or null)",
            "place_of_death": {
                "hospital_name": "string (if died in hospital)",
                "village_town": "string",
                "district": "string",
                "state": "string"
            },
            "cause_of_death": "string (primary cause as medical term or description)",
            "father_husband_name": "string (S/O or H/O relation)",
            "mother_name": "string (if printed)",
            "nationality": "string",
            "religion": "string",
            "occupation": "string",
            "permanent_address": "string",
            "informant_name": "string (person who reported the death)",
            "informant_relation": "string (relation to deceased)",
            "registration_date": "string (YYYY-MM-DD)",
            "issuing_authority": "string",
            "issue_date": "string (YYYY-MM-DD)",
            "registrar_name": "string"
        }

    def get_prompt_instructions(self) -> str:
        return """
You are extracting data from a DEATH CERTIFICATE issued by an Indian government authority.
The document may be in English, Hindi, or Gujarati.

IMPORTANT INSTRUCTIONS:
1. Registration number is the unique ID for this death registration.
2. Date of death (DOD) and date of registration may differ.
3. Cause of death may be in medical terminology or plain language.
4. Father/husband name appears as S/O (Son of) or H/O (Husband of).
5. Informant is the person who reported the death to the authority.
6. Place of death: extract hospital name if died in hospital.
7. Age at time of death in years.
8. Use null for any field not visible.

Extract all fields precisely — registration_number, deceased_name, and dod are critical.
"""

    def get_required_fields(self) -> list:
        return ['registration_number', 'deceased_name', 'dod', 'cause_of_death']


class LandRecordSchema(BaseSchema):
    """Schema for Indian Land Record (7/12 Utara, Khatauni, Record of Rights)"""

    def get_schema(self) -> Dict[str, Any]:
        return {
            "record_type": "string ('7/12 Utara', 'Khatauni', 'Record of Rights', 'Jamabandi', 'Pahani', 'Chitta')",
            "survey_number": "string (gut/khasra/survey number)",
            "sub_division_number": "string (if applicable)",
            "village": "string",
            "taluka_tehsil": "string",
            "district": "string",
            "state": "string",
            "land_type": "string ('Agricultural', 'Non-Agricultural', 'Forest', 'Wasteland')",
            "total_area": {
                "value": "number",
                "unit": "string ('Hectare', 'Acre', 'Guntha', 'Square Feet')"
            },
            "owners": [
                {
                    "name": "string",
                    "father_name": "string",
                    "share": "string (fraction, e.g. '1/2')",
                    "address": "string",
                    "ownership_type": "string ('Owner', 'Co-owner', 'Tenant')"
                }
            ],
            "cultivation_details": {
                "irrigated_area": "number",
                "unirrigated_area": "number",
                "irrigation_source": "string",
                "crop_season": "string",
                "crop_details": "string"
            },
            "encumbrances": [
                {
                    "type": "string (Mortgage, Lease, Attachment)",
                    "description": "string",
                    "date": "string (YYYY-MM-DD)"
                }
            ],
            "mutation_number": "string (last mutation/transfer number)",
            "talathi_signature": "boolean",
            "issue_date": "string (YYYY-MM-DD or financial year if only year shown)",
            "remarks": "string (any special remarks or notes)"
        }

    def get_prompt_instructions(self) -> str:
        return """
You are extracting data from an INDIAN LAND RECORD document.
Common types include: 7/12 Utara (Maharashtra/Gujarat), Khatauni (UP/Bihar),
Jamabandi (Punjab/Haryana), Pahani (Karnataka), or Record of Rights.
The document may be in English, Hindi, Gujarati, or Marathi.

IMPORTANT INSTRUCTIONS:
1. Survey/gut/khasra number is the land parcel identifier — extract carefully.
2. Owner details may list multiple co-owners with fractional shares.
3. Area units vary by state: Hectare, Acre, Guntha, Square Feet.
4. Encumbrances are legal claims/mortgages against the land.
5. Cultivation details describe current agricultural use.
6. Mutation number is the record of the last ownership transfer.
7. Gujarat 7/12 has columns: Gut No., Name, Area, Encumbrances, Crop.
8. Use null for any field not visible.

Extract all owner names and land details precisely.
"""

    def get_required_fields(self) -> list:
        return ['survey_number', 'village', 'taluka_tehsil', 'district', 'state', 'owners']


class NREGACardSchema(BaseSchema):
    """Schema for NREGA (MGNREGA) Job Card"""

    def get_schema(self) -> Dict[str, Any]:
        return {
            "job_card_number": "string (state + district + block + GP + serial format)",
            "household_head": {
                "name": "string",
                "father_husband_name": "string",
                "category": "string ('SC', 'ST', 'OBC', 'General')",
                "gender": "string"
            },
            "village": "string",
            "gram_panchayat": "string",
            "block": "string",
            "district": "string",
            "state": "string",
            "pin_code": "string",
            "registration_date": "string (YYYY-MM-DD)",
            "bank_account": {
                "account_number": "string",
                "bank_name": "string",
                "branch_name": "string",
                "ifsc_code": "string"
            },
            "job_seekers": [
                {
                    "name": "string",
                    "gender": "string",
                    "age": "number",
                    "relation": "string (relation to head of family)"
                }
            ],
            "work_entries": [
                {
                    "muster_roll_number": "string",
                    "work_name": "string",
                    "date_from": "string (YYYY-MM-DD)",
                    "date_to": "string (YYYY-MM-DD)",
                    "days_worked": "number",
                    "wage_rate": "number",
                    "amount_earned": "number",
                    "payment_date": "string (YYYY-MM-DD)"
                }
            ],
            "total_days_worked": "number",
            "total_wages_earned": "number (in INR)"
        }

    def get_prompt_instructions(self) -> str:
        return """
You are extracting data from an NREGA / MGNREGA JOB CARD issued by the
Ministry of Rural Development, Government of India.
The document may be in Hindi, Gujarati, or English.

IMPORTANT INSTRUCTIONS:
1. Job Card Number is in format: StateCode/DistrictCode/BlockCode/GPCode/HouseholdNo
   (e.g. GJ/024/015/007/00123456)
2. Extract ALL job seekers listed on the card (all family members).
3. Work entries show employment records with dates and wages.
4. Bank account details are for direct benefit transfer of wages.
5. Category (SC/ST/OBC/General) of the household.
6. Sum up total days worked and total wages from all work entries if available.
7. Gram Panchayat, Block, and District are the administrative hierarchy.
8. Use null for any field not visible.

Extract all family member and employment details precisely.
"""

    def get_required_fields(self) -> list:
        return ['job_card_number', 'household_head.name', 'gram_panchayat', 'district', 'state']
