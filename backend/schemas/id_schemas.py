"""
ADIVA - ID Document Schemas

Schemas for Indian government-issued identity documents:
  - Aadhaar Card
  - PAN Card
  - Driving Licence
  - Passport
"""

from typing import Dict, Any
from schemas.base_schema import BaseSchema


class AadharCardSchema(BaseSchema):
    """Schema for Aadhaar Card (front and/or back)"""

    def get_schema(self) -> Dict[str, Any]:
        return {
            "uid_number": "string (12-digit UID, format: XXXX XXXX XXXX)",
            "name": "string",
            "dob": "string (YYYY-MM-DD or DD/MM/YYYY as printed)",
            "gender": "string (Male / Female / Third Gender)",
            "address": {
                "house": "string",
                "street": "string",
                "landmark": "string",
                "village_town": "string",
                "district": "string",
                "state": "string",
                "pin_code": "string (6-digit)"
            },
            "relation_name": "string (father/husband name if printed, e.g. 'C/O Ram Kumar')",
            "mobile_linked": "string (last 4 digits if visible, else null)",
            "enrollment_number": "string (EID if visible, else null)",
            "issue_date": "string (YYYY-MM-DD or null if not printed)",
            "qr_data_summary": "string (any text decoded near QR, or null)"
        }

    def get_prompt_instructions(self) -> str:
        return """
You are extracting data from an AADHAAR CARD issued by UIDAI (Unique Identification Authority of India).
The card may be in English, Hindi, or Gujarati.

IMPORTANT INSTRUCTIONS:
1. The 12-digit UID is the most important field — extract it carefully including spaces.
2. DOB may appear as 'Year of Birth' if exact date is not shown — use YYYY format in that case.
3. Address fields are often multi-line — combine them correctly.
4. Gender is printed in English on all cards.
5. The back side contains full address — if only front is visible, address may be partial.
6. For missing fields use null.

FIELD DETAILS:
- uid_number: The unique 12-digit number (e.g., "1234 5678 9012")
- name: Full name as printed on card
- dob: Date of birth or year of birth
- gender: As printed (Male/Female/Transgender)
- address: Break address into components as best as possible
- relation_name: "C/O", "S/O", "D/O", "W/O" prefix and name
- mobile_linked: Last 4 digits of registered mobile if printed

Extract all information visible on the card.
"""

    def get_required_fields(self) -> list:
        return ['uid_number', 'name', 'dob', 'gender']


class PanCardSchema(BaseSchema):
    """Schema for PAN Card issued by Income Tax Department of India"""

    def get_schema(self) -> Dict[str, Any]:
        return {
            "pan_number": "string (10-character alphanumeric, e.g. ABCDE1234F)",
            "name": "string (name of cardholder)",
            "father_name": "string (father's name as printed)",
            "dob": "string (date of birth, YYYY-MM-DD or DD/MM/YYYY)",
            "signature_present": "boolean",
            "card_type": "string ('Individual', 'Company', 'HUF', etc.)",
            "issuing_authority": "string (Income Tax Department of India)"
        }

    def get_prompt_instructions(self) -> str:
        return """
You are extracting data from a PAN CARD (Permanent Account Number Card) issued by
the Income Tax Department of India.

IMPORTANT INSTRUCTIONS:
1. PAN number is a 10-character code (5 letters + 4 digits + 1 letter, e.g. ABCDE1234F).
2. Extract PAN number exactly as printed — it is always uppercase.
3. Father's name is printed below the cardholder's name.
4. DOB is printed in DD/MM/YYYY format — convert to YYYY-MM-DD.
5. Card type can be inferred from 4th character of PAN (P=Person, C=Company, H=HUF).
6. Use null for any missing fields.

Extract all text visible on the card precisely.
"""

    def get_required_fields(self) -> list:
        return ['pan_number', 'name', 'dob']


class DrivingLicenceSchema(BaseSchema):
    """Schema for Indian Driving Licence"""

    def get_schema(self) -> Dict[str, Any]:
        return {
            "dl_number": "string (state code + district code + year + sequence)",
            "name": "string",
            "dob": "string (YYYY-MM-DD)",
            "blood_group": "string (A+/A-/B+/B-/O+/O-/AB+/AB- or null)",
            "address": {
                "line1": "string",
                "line2": "string",
                "city": "string",
                "state": "string",
                "pin_code": "string"
            },
            "issuing_authority": "string (RTO name and code)",
            "issue_date": "string (YYYY-MM-DD)",
            "vehicle_classes": [
                {
                    "class": "string (LMV, MCWG, HMV, etc.)",
                    "valid_from": "string (YYYY-MM-DD)",
                    "valid_to": "string (YYYY-MM-DD)"
                }
            ],
            "validity_nt": "string (non-transport validity date, YYYY-MM-DD)",
            "validity_t": "string (transport validity date, YYYY-MM-DD or null)",
            "father_husband_name": "string (S/O or W/O name)"
        }

    def get_prompt_instructions(self) -> str:
        return """
You are extracting data from an INDIAN DRIVING LICENCE.
Driving licences in India are issued by RTOs (Regional Transport Offices).
The document may be in English, Hindi, or regional languages.

IMPORTANT INSTRUCTIONS:
1. DL Number format is typically: SS-DD-YYYY-XXXXXXX (SS=state, DD=district, YYYY=year).
2. Vehicle classes include: MCWG (motorcycle with gear), LMV (light motor vehicle), HMV, etc.
3. Extract validity dates for ALL vehicle classes listed.
4. Blood group is printed on newer DLs — use null if not visible.
5. Issuing authority is the RTO (Regional Transport Office).
6. Father/husband name appears as S/O (Son of) or W/O (Wife of).

Extract all fields visible on the licence precisely.
"""

    def get_required_fields(self) -> list:
        return ['dl_number', 'name', 'dob', 'vehicle_classes']


class PassportSchema(BaseSchema):
    """Schema for Indian Passport (bio-data page)"""

    def get_schema(self) -> Dict[str, Any]:
        return {
            "passport_number": "string (e.g. A1234567 — 1 letter + 7 digits)",
            "surname": "string",
            "given_names": "string",
            "nationality": "string (INDIAN)",
            "dob": "string (YYYY-MM-DD)",
            "place_of_birth": "string",
            "sex": "string (M / F)",
            "issue_date": "string (YYYY-MM-DD)",
            "expiry_date": "string (YYYY-MM-DD)",
            "place_of_issue": "string (city where issued)",
            "issuing_authority": "string",
            "file_number": "string (file/application number if visible)",
            "father_name": "string (if printed)",
            "mother_name": "string (if printed)",
            "spouse_name": "string (if applicable, else null)",
            "address": "string (address as printed on last page, if visible)",
            "mrz_line1": "string (Machine Readable Zone line 1)",
            "mrz_line2": "string (Machine Readable Zone line 2)"
        }

    def get_prompt_instructions(self) -> str:
        return """
You are extracting data from an INDIAN PASSPORT (bio-data / personal information page).

IMPORTANT INSTRUCTIONS:
1. Passport number is 1 uppercase letter followed by 7 digits (e.g. A1234567).
2. The MRZ (Machine Readable Zone) consists of 2 lines of 44 characters each at the bottom.
   Extract them exactly as printed including '<' filler characters.
3. Dates on Indian passports are in DD/MM/YYYY — convert to YYYY-MM-DD.
4. Given names = all names except surname.
5. Place of issue is the Passport Seva Kendra / Regional Passport Office city.
6. Father/Mother/Spouse names appear on the personal details page or last page.
7. Use null for fields not visible in the provided text.

Extract all fields precisely, especially passport_number and MRZ lines.
"""

    def get_required_fields(self) -> list:
        return ['passport_number', 'surname', 'given_names', 'dob', 'expiry_date']
