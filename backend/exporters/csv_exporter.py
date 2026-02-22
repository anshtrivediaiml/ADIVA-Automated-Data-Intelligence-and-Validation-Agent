"""
CSV Exporter — All 21 Document Types

Exports structured extraction results to CSV format.
Uses type-specific formatters for rich documents and a universal
flattener for everything else.
"""

import csv
from pathlib import Path
from typing import Dict, Any, List
from logger import logger
import config


class CSVExporter:
    """Export structured data to CSV"""

    # Types with a custom, specialized CSV layout
    _CUSTOM_TYPES = {
        'invoice', 'resume', 'contract',
        'prescription', 'certificate',
        'bank_statement', 'utility_bill', 'marksheet', 'ration_card',
        'aadhar_card', 'pan_card', 'driving_licence', 'passport',
        'cheque', 'form_16', 'insurance_policy', 'gst_certificate',
        'birth_certificate', 'death_certificate', 'land_record', 'nrega_card',
    }

    def export(self, extraction_result: Dict[str, Any], output_path: str = None) -> str:
        if not output_path:
            output_path = config.get_output_filename("extracted", ".csv")
        output_path = Path(output_path)

        if 'structured_data' in extraction_result:
            doc_type = extraction_result.get('classification', {}).get('document_type', 'unknown')
            method = getattr(self, f'_csv_{doc_type}', None)
            if method:
                return method(extraction_result, output_path)
        return self._export_generic(extraction_result, output_path)

    # ─────────────────────────────────────────────────────────
    # Shared helpers
    # ─────────────────────────────────────────────────────────

    @staticmethod
    def _open(path):
        return open(path, 'w', newline='', encoding='utf-8-sig')

    @staticmethod
    def _section(w, title):
        w.writerow([title])

    @staticmethod
    def _kv(w, key, value):
        w.writerow([key, value if value is not None else ''])

    @staticmethod
    def _blank(w):
        w.writerow([])

    def _flat_dict(self, w, d: dict, prefix=''):
        for k, v in (d or {}).items():
            label = f"{prefix}{k.replace('_', ' ').title()}"
            if isinstance(v, dict):
                self._flat_dict(w, v, prefix=label + ' > ')
            elif isinstance(v, list):
                self._kv(w, label, '; '.join(str(i) for i in v))
            else:
                self._kv(w, label, v)

    # ─────────────────────────────────────────────────────────
    # General Documents
    # ─────────────────────────────────────────────────────────

    def _csv_invoice(self, result, path):
        d = result['structured_data']
        with self._open(path) as f:
            w = csv.writer(f)
            self._section(w, 'Invoice Information')
            self._kv(w, 'Invoice Number', d.get('invoice_number'))
            self._kv(w, 'Invoice Date', d.get('invoice_date'))
            self._kv(w, 'Due Date', d.get('due_date'))
            self._kv(w, 'Currency', d.get('currency'))
            self._kv(w, 'Payment Terms', d.get('payment_terms'))
            self._blank(w)
            self._section(w, 'Vendor')
            self._flat_dict(w, d.get('vendor', {}))
            self._blank(w)
            self._section(w, 'Customer')
            self._flat_dict(w, d.get('customer', {}))
            self._blank(w)
            self._section(w, 'Line Items')
            w.writerow(['Description', 'Quantity', 'Unit Price', 'Total'])
            for item in d.get('line_items', []):
                w.writerow([item.get('description',''), item.get('quantity',''),
                            item.get('unit_price',''), item.get('total','')])
            self._blank(w)
            self._kv(w, 'Subtotal', d.get('subtotal'))
            self._kv(w, 'Tax', d.get('tax'))
            self._kv(w, 'TOTAL', d.get('total'))
        logger.info(f"Invoice CSV: {path.name}")
        return str(path)

    def _csv_resume(self, result, path):
        d = result['structured_data']
        with self._open(path) as f:
            w = csv.writer(f)
            self._section(w, 'Personal Information')
            self._flat_dict(w, d.get('personal_info', {}))
            self._blank(w)
            self._section(w, 'Work Experience')
            w.writerow(['Company', 'Position', 'Location', 'Start Date', 'End Date'])
            for exp in d.get('experience', []):
                w.writerow([exp.get('company',''), exp.get('position',''),
                            exp.get('location',''), exp.get('start_date',''), exp.get('end_date','')])
            self._blank(w)
            self._section(w, 'Education')
            w.writerow(['Institution', 'Degree', 'Field', 'Year', 'GPA'])
            for edu in d.get('education', []):
                w.writerow([edu.get('institution',''), edu.get('degree',''),
                            edu.get('field_of_study',''), edu.get('graduation_date',''), edu.get('gpa','')])
            self._blank(w)
            self._section(w, 'Skills')
            for s in d.get('skills', []):
                w.writerow([s])
        return str(path)

    def _csv_contract(self, result, path):
        d = result['structured_data']
        with self._open(path) as f:
            w = csv.writer(f)
            self._section(w, 'Contract Details')
            for key in ['contract_title','contract_type','contract_date','effective_date',
                        'expiration_date','term_duration','governing_law']:
                self._kv(w, key.replace('_',' ').title(), d.get(key))
            self._blank(w)
            self._section(w, 'Parties')
            w.writerow(['Name', 'Role', 'Address', 'Signatory'])
            for p in d.get('parties', []):
                w.writerow([p.get('name',''), p.get('role',''), p.get('address',''), p.get('signatory','')])
            self._blank(w)
            self._kv(w, 'Termination Clause', d.get('termination_clause'))
            self._kv(w, 'Confidentiality', d.get('confidentiality'))
            self._kv(w, 'Dispute Resolution', d.get('dispute_resolution'))
        return str(path)

    def _csv_prescription(self, result, path):
        d = result['structured_data']
        with self._open(path) as f:
            w = csv.writer(f)
            self._section(w, 'Doctor Information')
            self._flat_dict(w, d.get('doctor', {}))
            self._blank(w)
            self._section(w, 'Patient Information')
            self._flat_dict(w, d.get('patient', {}))
            self._blank(w)
            self._kv(w, 'Diagnosis', d.get('diagnosis'))
            self._kv(w, 'Prescription Date', d.get('prescription_date'))
            self._kv(w, 'Follow-up', d.get('follow_up'))
            self._blank(w)
            self._section(w, 'Medicines')
            w.writerow(['Medicine', 'Dosage', 'Frequency', 'Duration', 'Instructions'])
            for med in d.get('medicines', []):
                w.writerow([med.get('name',''), med.get('dosage',''), med.get('frequency',''),
                            med.get('duration',''), med.get('instructions','')])
        return str(path)

    def _csv_certificate(self, result, path):
        d = result['structured_data']
        with self._open(path) as f:
            w = csv.writer(f)
            self._section(w, 'Certificate Details')
            for key in ['certificate_type','certificate_number','issue_date','event_date','event_place']:
                self._kv(w, key.replace('_',' ').title(), d.get(key))
            self._blank(w)
            self._section(w, 'Primary Person')
            self._flat_dict(w, d.get('primary_person', {}))
            if d.get('secondary_person'):
                self._blank(w)
                self._section(w, 'Secondary Person')
                self._flat_dict(w, d.get('secondary_person', {}))
            self._blank(w)
            self._kv(w, 'Issuing Authority', d.get('issuing_authority'))
            self._kv(w, 'Registrar', d.get('registrar_name'))
            if d.get('witnesses'):
                self._blank(w)
                self._section(w, 'Witnesses')
                for wt in d.get('witnesses', []):
                    w.writerow([wt])
        return str(path)

    # ─────────────────────────────────────────────────────────
    # Civic / Government Documents
    # ─────────────────────────────────────────────────────────

    def _csv_bank_statement(self, result, path):
        d = result['structured_data']
        with self._open(path) as f:
            w = csv.writer(f)
            self._section(w, 'Account Information')
            for key in ['bank_name','branch_name','account_number','account_type','ifsc_code',
                        'account_holder','statement_period_from','statement_period_to',
                        'opening_balance','closing_balance','total_credits','total_debits']:
                self._kv(w, key.replace('_',' ').title(), d.get(key))
            self._blank(w)
            self._section(w, 'Transactions')
            w.writerow(['Date', 'Description', 'Debit', 'Credit', 'Balance', 'Reference'])
            for txn in d.get('transactions', []):
                w.writerow([txn.get('date',''), txn.get('description',''), txn.get('debit_amount',''),
                            txn.get('credit_amount',''), txn.get('balance',''), txn.get('reference_number','')])
        return str(path)

    def _csv_utility_bill(self, result, path):
        d = result['structured_data']
        with self._open(path) as f:
            w = csv.writer(f)
            self._section(w, 'Consumer & Bill Details')
            for key in ['bill_type','provider_name','consumer_name','consumer_number','meter_number',
                        'billing_address','billing_period','bill_date','due_date',
                        'previous_reading','current_reading','units_consumed','total_amount','currency']:
                self._kv(w, key.replace('_',' ').title(), d.get(key))
            self._blank(w)
            self._section(w, 'Charges')
            self._flat_dict(w, d.get('charges', {}))
            self._blank(w)
            self._kv(w, 'Late Payment Info', d.get('late_payment_surcharge'))
            if d.get('payment_options'):
                self._kv(w, 'Payment Options', ', '.join(d.get('payment_options', [])))
        return str(path)

    def _csv_marksheet(self, result, path):
        d = result['structured_data']
        with self._open(path) as f:
            w = csv.writer(f)
            self._section(w, 'Student Information')
            for key in ['student_name','roll_number','class_standard','stream','school_name',
                        'board','exam_year','total_marks','marks_obtained_total',
                        'percentage','cgpa','result','division','rank']:
                self._kv(w, key.replace('_',' ').title(), d.get(key))
            self._blank(w)
            self._section(w, 'Subject-wise Marks')
            w.writerow(['Subject', 'Max Marks', 'Marks Obtained', 'Grade', 'Pass/Fail'])
            for subj in d.get('subjects', []):
                w.writerow([subj.get('name',''), subj.get('max_marks',''),
                            subj.get('marks_obtained',''), subj.get('grade',''), subj.get('pass_fail','')])
        return str(path)

    def _csv_ration_card(self, result, path):
        d = result['structured_data']
        with self._open(path) as f:
            w = csv.writer(f)
            self._section(w, 'Card Details')
            for key in ['card_type','card_number','issuing_state','issuing_department']:
                self._kv(w, key.replace('_',' ').title(), d.get(key))
            self._blank(w)
            self._section(w, 'Head of Family')
            self._flat_dict(w, d.get('head_of_family', {}))
            self._blank(w)
            self._section(w, 'Family Members')
            w.writerow(['S.No', 'Name', 'Age', 'Relation'])
            for m in d.get('family_members', []):
                w.writerow([m.get('serial_number',''), m.get('name',''),
                            m.get('age',''), m.get('relation','')])
            self._blank(w)
            self._section(w, 'Ration Shop')
            self._flat_dict(w, d.get('ration_shop', {}))
        return str(path)

    # ─────────────────────────────────────────────────────────
    # Identity Documents
    # ─────────────────────────────────────────────────────────

    def _csv_aadhar_card(self, result, path):
        d = result['structured_data']
        with self._open(path) as f:
            w = csv.writer(f)
            self._section(w, 'Aadhaar Card')
            for key in ['uid_number','name','dob','gender','relation_name',
                        'mobile_linked','enrollment_number','issue_date']:
                self._kv(w, key.replace('_',' ').title(), d.get(key))
            self._blank(w)
            self._section(w, 'Address')
            self._flat_dict(w, d.get('address', {}))
        return str(path)

    def _csv_pan_card(self, result, path):
        d = result['structured_data']
        with self._open(path) as f:
            w = csv.writer(f)
            self._section(w, 'PAN Card')
            for key in ['pan_number','name','father_name','dob','card_type',
                        'signature_present','issuing_authority']:
                self._kv(w, key.replace('_',' ').title(), d.get(key))
        return str(path)

    def _csv_driving_licence(self, result, path):
        d = result['structured_data']
        with self._open(path) as f:
            w = csv.writer(f)
            self._section(w, 'Driving Licence')
            for key in ['dl_number','name','dob','blood_group','father_husband_name',
                        'issuing_authority','issue_date','validity_nt','validity_t']:
                self._kv(w, key.replace('_',' ').title(), d.get(key))
            self._blank(w)
            self._section(w, 'Address')
            self._flat_dict(w, d.get('address', {}))
            self._blank(w)
            self._section(w, 'Vehicle Classes')
            w.writerow(['Class', 'Valid From', 'Valid To'])
            for vc in d.get('vehicle_classes', []):
                w.writerow([vc.get('class',''), vc.get('valid_from',''), vc.get('valid_to','')])
        return str(path)

    def _csv_passport(self, result, path):
        d = result['structured_data']
        with self._open(path) as f:
            w = csv.writer(f)
            self._section(w, 'Passport Details')
            for key in ['passport_number','surname','given_names','nationality','dob',
                        'place_of_birth','sex','issue_date','expiry_date','place_of_issue',
                        'file_number','father_name','mother_name','spouse_name',
                        'issuing_authority','address']:
                self._kv(w, key.replace('_',' ').title(), d.get(key))
            self._blank(w)
            self._section(w, 'MRZ')
            w.writerow([d.get('mrz_line1','')])
            w.writerow([d.get('mrz_line2','')])
        return str(path)

    # ─────────────────────────────────────────────────────────
    # Financial Documents
    # ─────────────────────────────────────────────────────────

    def _csv_cheque(self, result, path):
        d = result['structured_data']
        with self._open(path) as f:
            w = csv.writer(f)
            self._section(w, 'Cheque Details')
            for key in ['cheque_number','cheque_type','date','bank_name','branch_name',
                        'ifsc_code','micr_code','account_number','payee_name',
                        'amount_figures','amount_words','drawer_name','crossed','memo']:
                self._kv(w, key.replace('_',' ').title(), d.get(key))
        return str(path)

    def _csv_form_16(self, result, path):
        d = result['structured_data']
        with self._open(path) as f:
            w = csv.writer(f)
            self._section(w, 'Form 16 — TDS Certificate')
            for key in ['form_part','assessment_year','certificate_number']:
                self._kv(w, key.replace('_',' ').title(), d.get(key))
            self._blank(w)
            self._section(w, 'Employer')
            self._flat_dict(w, d.get('employer', {}))
            self._blank(w)
            self._section(w, 'Employee')
            self._flat_dict(w, d.get('employee', {}))
            self._blank(w)
            self._section(w, 'Income')
            self._flat_dict(w, d.get('income', {}))
            self._blank(w)
            self._section(w, 'Deductions')
            self._flat_dict(w, d.get('deductions', {}))
            self._blank(w)
            self._section(w, 'Tax')
            self._flat_dict(w, d.get('tax', {}))
            self._blank(w)
            if d.get('quarter_details'):
                self._section(w, 'Quarter-wise TDS')
                w.writerow(['Quarter', 'Amount Paid', 'TDS Deducted', 'Date of Deposit'])
                for q in d.get('quarter_details', []):
                    w.writerow([q.get('quarter',''), q.get('amount_paid',''),
                                q.get('tds_deducted',''), q.get('date_of_deposit','')])
        return str(path)

    def _csv_insurance_policy(self, result, path):
        d = result['structured_data']
        with self._open(path) as f:
            w = csv.writer(f)
            self._section(w, 'Policy Details')
            for key in ['policy_number','policy_type','insurer_name','insurer_license_number',
                        'sum_assured','premium_amount','premium_frequency',
                        'policy_term_years','premium_paying_term_years',
                        'policy_start_date','policy_end_date','next_premium_due',
                        'grace_period_days','agent_name','agent_code']:
                self._kv(w, key.replace('_',' ').title(), d.get(key))
            self._blank(w)
            self._section(w, 'Insured')
            self._flat_dict(w, d.get('insured', {}))
            self._blank(w)
            self._section(w, 'Nominee')
            self._flat_dict(w, d.get('nominee', {}))
            self._blank(w)
            if d.get('riders'):
                self._section(w, 'Riders')
                w.writerow(['Rider', 'Sum Assured', 'Premium'])
                for r in d.get('riders', []):
                    w.writerow([r.get('name',''), r.get('sum_assured',''), r.get('premium','')])
        return str(path)

    def _csv_gst_certificate(self, result, path):
        d = result['structured_data']
        with self._open(path) as f:
            w = csv.writer(f)
            self._section(w, 'GST Certificate')
            for key in ['gstin','legal_name','trade_name','constitution','registration_date',
                        'certificate_issue_date','status','cancellation_date']:
                self._kv(w, key.replace('_',' ').title(), d.get(key))
            self._blank(w)
            self._section(w, 'Principal Place of Business')
            self._flat_dict(w, d.get('principal_place_of_business', {}))
            self._blank(w)
            self._section(w, 'Jurisdiction')
            self._flat_dict(w, d.get('jurisdiction', {}))
            self._blank(w)
            self._section(w, 'Nature of Business')
            for nb in d.get('nature_of_business', []):
                w.writerow([nb])
            self._blank(w)
            self._section(w, 'Authorized Signatory')
            self._flat_dict(w, d.get('authorized_signatory', {}))
        return str(path)

    # ─────────────────────────────────────────────────────────
    # Civil Records
    # ─────────────────────────────────────────────────────────

    def _csv_birth_certificate(self, result, path):
        d = result['structured_data']
        with self._open(path) as f:
            w = csv.writer(f)
            self._section(w, 'Birth Details')
            for key in ['registration_number','child_name','gender','dob','time_of_birth',
                        'permanent_address','present_address','registration_date','issue_date']:
                self._kv(w, key.replace('_',' ').title(), d.get(key))
            self._blank(w)
            self._section(w, 'Place of Birth')
            self._flat_dict(w, d.get('place_of_birth', {}))
            self._blank(w)
            self._section(w, "Father's Details")
            self._flat_dict(w, d.get('father', {}))
            self._blank(w)
            self._section(w, "Mother's Details")
            self._flat_dict(w, d.get('mother', {}))
            self._blank(w)
            self._kv(w, 'Issuing Authority', d.get('issuing_authority'))
            self._kv(w, 'Registrar', d.get('registrar_name'))
        return str(path)

    def _csv_death_certificate(self, result, path):
        d = result['structured_data']
        with self._open(path) as f:
            w = csv.writer(f)
            self._section(w, 'Death Details')
            for key in ['registration_number','deceased_name','gender','age','dod',
                        'time_of_death','cause_of_death','nationality','religion','occupation',
                        'father_husband_name','mother_name','permanent_address',
                        'informant_name','informant_relation','registration_date',
                        'issue_date','issuing_authority','registrar_name']:
                self._kv(w, key.replace('_',' ').title(), d.get(key))
            self._blank(w)
            self._section(w, 'Place of Death')
            self._flat_dict(w, d.get('place_of_death', {}))
        return str(path)

    def _csv_land_record(self, result, path):
        d = result['structured_data']
        with self._open(path) as f:
            w = csv.writer(f)
            self._section(w, 'Land Details')
            for key in ['record_type','survey_number','sub_division_number','village',
                        'taluka_tehsil','district','state','land_type','mutation_number',
                        'issue_date','remarks']:
                self._kv(w, key.replace('_',' ').title(), d.get(key))
            if d.get('total_area'):
                self._kv(w, 'Total Area',
                    f"{d['total_area'].get('value','')} {d['total_area'].get('unit','')}")
            self._blank(w)
            self._section(w, 'Owners')
            w.writerow(['Name', "Father's Name", 'Share', 'Ownership Type', 'Address'])
            for own in d.get('owners', []):
                w.writerow([own.get('name',''), own.get('father_name',''), own.get('share',''),
                            own.get('ownership_type',''), own.get('address','')])
            self._blank(w)
            self._section(w, 'Cultivation Details')
            self._flat_dict(w, d.get('cultivation_details', {}))
            self._blank(w)
            if d.get('encumbrances'):
                self._section(w, 'Encumbrances')
                w.writerow(['Type', 'Description', 'Date'])
                for e in d.get('encumbrances', []):
                    w.writerow([e.get('type',''), e.get('description',''), e.get('date','')])
        return str(path)

    def _csv_nrega_card(self, result, path):
        d = result['structured_data']
        with self._open(path) as f:
            w = csv.writer(f)
            self._section(w, 'NREGA Job Card')
            for key in ['job_card_number','village','gram_panchayat','block','district',
                        'state','pin_code','registration_date',
                        'total_days_worked','total_wages_earned']:
                self._kv(w, key.replace('_',' ').title(), d.get(key))
            self._blank(w)
            self._section(w, 'Head of Household')
            self._flat_dict(w, d.get('household_head', {}))
            self._blank(w)
            self._section(w, 'Bank Account')
            self._flat_dict(w, d.get('bank_account', {}))
            self._blank(w)
            self._section(w, 'Job Seekers')
            w.writerow(['Name', 'Gender', 'Age', 'Relation'])
            for js in d.get('job_seekers', []):
                w.writerow([js.get('name',''), js.get('gender',''),
                            js.get('age',''), js.get('relation','')])
            self._blank(w)
            self._section(w, 'Work Entries')
            w.writerow(['Muster No.', 'Work Name', 'From', 'To', 'Days', 'Wage Rate (₹)', 'Amount (₹)'])
            for we in d.get('work_entries', []):
                w.writerow([we.get('muster_roll_number',''), we.get('work_name',''),
                            we.get('date_from',''), we.get('date_to',''),
                            we.get('days_worked',''), we.get('wage_rate',''), we.get('amount_earned','')])
        return str(path)

    # ─────────────────────────────────────────────────────────
    # Generic fallback
    # ─────────────────────────────────────────────────────────

    def _export_generic(self, result: Dict[str, Any], output_path: Path) -> str:
        with self._open(output_path) as f:
            w = csv.writer(f)
            self._section(w, 'Metadata')
            for key, value in result.get('metadata', {}).items():
                if not isinstance(value, (dict, list)):
                    w.writerow([key, value])
            self._blank(w)
            if 'structured_data' in result:
                self._section(w, 'Extracted Fields')
                self._flat_dict(w, result['structured_data'])
            else:
                self._section(w, 'Extracted Text')
                text = result.get('text', {}).get('raw', '')
                w.writerow([text[:1000] + '...' if len(text) > 1000 else text])
        logger.info(f"Generic CSV export: {output_path.name}")
        return str(output_path)
