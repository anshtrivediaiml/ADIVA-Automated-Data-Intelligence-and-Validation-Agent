"""
HTML Exporter — All 21 Document Types

Export extraction results to formatted HTML reports.
Uses Jinja2 templates with type-specific sections.
"""

from pathlib import Path
from typing import Dict, Any
from jinja2 import Template
from logger import logger
import config
from datetime import datetime


class HTMLExporter:
    """Export structured data to HTML report"""

    def __init__(self):
        self.template = self._get_template()

    def export(self, extraction_result: Dict[str, Any], output_path: str = None) -> str:
        if not output_path:
            output_path = config.get_output_filename("extracted", ".html")

        output_path = Path(output_path)

        template_data = {
            'result': extraction_result,
            'metadata': extraction_result.get('metadata', {}),
            'classification': extraction_result.get('classification', {}),
            'structured_data': extraction_result.get('structured_data', {}),
            'confidence': extraction_result.get('comprehensive_confidence', {}),
            'text': extraction_result.get('text', {}),
            'tables': extraction_result.get('tables', []),
            'extraction_log': extraction_result.get('extraction_log', []),
            'generated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'doc_type': extraction_result.get('classification', {}).get('document_type', 'unknown')
        }

        html_content = self.template.render(**template_data)

        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(html_content)

        logger.info(f"Exported to HTML: {output_path.name}")
        return str(output_path)

    def _get_template(self) -> Template:
        template_str = r"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ADIVA Extraction Report</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            padding: 20px; min-height: 100vh;
        }
        .container { max-width: 1200px; margin: 0 auto; background: white; border-radius: 12px; box-shadow: 0 20px 60px rgba(0,0,0,0.3); overflow: hidden; }
        .header { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 40px; text-align: center; }
        .header h1 { font-size: 2.5em; margin-bottom: 10px; }
        .header p { font-size: 1.1em; opacity: 0.9; }
        .content { padding: 40px; }
        .section { margin-bottom: 40px; }
        .section-title { font-size: 1.8em; color: #667eea; margin-bottom: 20px; padding-bottom: 10px; border-bottom: 3px solid #667eea; }
        .sub-title { font-size: 1.2em; font-weight: bold; color: #374151; margin: 20px 0 10px 0; }
        .info-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 16px; margin-bottom: 24px; }
        .info-card { background: #f9fafb; padding: 16px 20px; border-radius: 8px; border-left: 4px solid #667eea; }
        .info-label { font-weight: bold; color: #6b7280; margin-bottom: 6px; text-transform: uppercase; font-size: 0.8em; letter-spacing: 0.04em; }
        .info-value { font-size: 1.05em; color: #1f2937; word-break: break-word; }
        .info-value.large { font-size: 1.4em; font-weight: bold; color: #4338ca; }
        .kv-table { width: 100%; border-collapse: collapse; margin: 12px 0; }
        .kv-table td { padding: 9px 14px; border-bottom: 1px solid #e5e7eb; vertical-align: top; }
        .kv-table td:first-child { font-weight: 600; color: #374151; width: 35%; background: #f9fafb; white-space: nowrap; }
        .kv-table td:last-child { color: #1f2937; }
        table { width: 100%; border-collapse: collapse; margin: 16px 0; }
        th, td { padding: 11px 14px; text-align: left; border-bottom: 1px solid #e5e7eb; }
        th { background: #667eea; color: white; font-weight: 600; }
        tr:nth-child(even) td { background: #f9fafb; }
        tr:hover td { background: #eef2ff; }
        .badge { display: inline-block; padding: 5px 14px; border-radius: 20px; font-weight: 600; font-size: 0.9em; }
        .badge-success { background: #d1fae5; color: #065f46; }
        .badge-warning { background: #fef3c7; color: #92400e; }
        .badge-danger  { background: #fee2e2; color: #991b1b; }
        .badge-info    { background: #dbeafe; color: #1e40af; }
        .confidence-bar { background: #e5e7eb; height: 26px; border-radius: 13px; overflow: hidden; margin: 8px 0; }
        .confidence-fill { height: 100%; display: flex; align-items: center; padding: 0 14px; color: white; font-weight: bold; font-size: 0.9em; }
        .c-high   { background: linear-gradient(90deg, #10b981, #059669); }
        .c-medium { background: linear-gradient(90deg, #f59e0b, #d97706); }
        .c-low    { background: linear-gradient(90deg, #ef4444, #dc2626); }
        .metric-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 14px; margin: 16px 0; }
        .metric-card { background: #f9fafb; padding: 20px; border-radius: 8px; text-align: center; }
        .metric-value { font-size: 2em; font-weight: bold; color: #4338ca; }
        .metric-label { color: #6b7280; margin-top: 6px; text-transform: uppercase; font-size: 0.8em; }
        .log-entry { padding: 8px 12px; margin: 4px 0; background: #f3f4f6; border-radius: 5px; font-family: 'Courier New', monospace; font-size: 0.88em; color: #374151; }
        .tag { display: inline-block; background: #dbeafe; color: #1e40af; padding: 3px 10px; border-radius: 4px; font-size: 0.9em; margin: 2px; }
        .highlight { background: #fef9c3; border-left: 4px solid #ca8a04; padding: 12px 18px; border-radius: 6px; margin: 10px 0; }
        .footer { background: #f3f4f6; padding: 18px; text-align: center; color: #6b7280; font-size: 0.88em; }
        .doc-icon { font-size: 3em; margin-bottom: 10px; }
        @media print { body { background: white; padding: 0; } .container { box-shadow: none; } }
    </style>
</head>
<body>
<div class="container">
  <div class="header">
    <div class="doc-icon">
      {% if doc_type == 'invoice' %}🧾
      {% elif doc_type == 'resume' %}👤
      {% elif doc_type == 'contract' %}📝
      {% elif doc_type == 'prescription' %}💊
      {% elif doc_type in ('birth_certificate','death_certificate','certificate') %}📋
      {% elif doc_type == 'bank_statement' %}🏦
      {% elif doc_type == 'marksheet' %}📊
      {% elif doc_type == 'ration_card' %}🍚
      {% elif doc_type == 'utility_bill' %}⚡
      {% elif doc_type == 'aadhar_card' %}🪪
      {% elif doc_type == 'pan_card' %}💳
      {% elif doc_type == 'driving_licence' %}🚗
      {% elif doc_type == 'passport' %}✈️
      {% elif doc_type == 'cheque' %}🏧
      {% elif doc_type == 'form_16' %}📑
      {% elif doc_type == 'insurance_policy' %}🛡️
      {% elif doc_type == 'gst_certificate' %}🏢
      {% elif doc_type == 'land_record' %}🌾
      {% elif doc_type == 'nrega_card' %}🛠️
      {% else %}📄
      {% endif %}
    </div>
    <h1>ADIVA Extraction Report</h1>
    <p>{{ doc_type | replace('_', ' ') | upper }} &nbsp;·&nbsp; Intelligent Document Analysis</p>
  </div>

  <div class="content">

    <!-- Classification -->
    {% if classification %}
    <div class="section">
      <h2 class="section-title">🤖 AI Classification</h2>
      <div class="info-grid">
        <div class="info-card">
          <div class="info-label">Document Type</div>
          <div class="info-value large">{{ classification.document_type | replace('_',' ') | title }}</div>
        </div>
        <div class="info-card">
          <div class="info-label">Confidence</div>
          <div class="info-value large">{{ (classification.confidence * 100) | round(1) }}%</div>
        </div>
        {% if classification.alternative_type %}
        <div class="info-card">
          <div class="info-label">Alternative Type</div>
          <div class="info-value">{{ classification.alternative_type }}</div>
        </div>
        {% endif %}
      </div>
      {% if classification.reasoning %}
      <div class="highlight">{{ classification.reasoning }}</div>
      {% endif %}
    </div>
    {% endif %}

    <!-- Quality Metrics -->
    {% if confidence %}
    <div class="section">
      <h2 class="section-title">📊 Quality Metrics</h2>
      <div class="metric-grid">
        <div class="metric-card">
          <div class="metric-value">{{ (confidence.overall_confidence * 100) | round(1) }}%</div>
          <div class="metric-label">Overall Confidence</div>
        </div>
        <div class="metric-card">
          <div class="metric-value">{{ confidence.grade }}</div>
          <div class="metric-label">Quality Grade</div>
        </div>
      </div>
      <div class="sub-title">Detailed Metrics</div>
      {% for metric, value in confidence.metrics.items() %}
      <div style="margin:8px 0">
        <strong>{{ metric | replace('_',' ') | title }}</strong>
        <div class="confidence-bar">
          <div class="confidence-fill {% if value >= 0.85 %}c-high{% elif value >= 0.65 %}c-medium{% else %}c-low{% endif %}"
               style="width:{{ (value * 100) | round(0) }}%">{{ (value * 100) | round(1) }}%</div>
        </div>
      </div>
      {% endfor %}
      {% if confidence.explanations %}
      <div class="sub-title">Analysis</div>
      {% for exp in confidence.explanations %}<div class="log-entry">{{ exp }}</div>{% endfor %}
      {% endif %}
      {% if confidence.recommendations %}
      <div class="sub-title">Recommendations</div>
      {% for rec in confidence.recommendations %}<div class="log-entry">💡 {{ rec }}</div>{% endfor %}
      {% endif %}
    </div>
    {% endif %}

    <!-- Structured Data — type-specific sections -->
    {% if structured_data %}
    <div class="section">
      <h2 class="section-title">📋 Extracted Data</h2>

      {# ═══════════════════ INVOICE ═══════════════════ #}
      {% if doc_type == 'invoice' %}
        <div class="info-grid">
          <div class="info-card"><div class="info-label">Invoice No.</div><div class="info-value large">{{ structured_data.get('invoice_number','—') }}</div></div>
          <div class="info-card"><div class="info-label">Date</div><div class="info-value">{{ structured_data.get('invoice_date','—') }}</div></div>
          <div class="info-card"><div class="info-label">Total Amount</div><div class="info-value large">{{ structured_data.get('currency','') }} {{ structured_data.get('total','—') }}</div></div>
        </div>
        {% if structured_data.get('line_items') %}
        <div class="sub-title">Line Items</div>
        <table><thead><tr><th>Description</th><th>Qty</th><th>Unit Price</th><th>Total</th></tr></thead>
        <tbody>{% for item in structured_data.line_items %}<tr>
          <td>{{ item.get('description','') }}</td><td>{{ item.get('quantity','') }}</td>
          <td>{{ item.get('unit_price','') }}</td><td>{{ item.get('total','') }}</td>
        </tr>{% endfor %}</tbody></table>
        <table style="width:40%;float:right"><tbody>
          <tr><td><strong>Subtotal</strong></td><td>{{ structured_data.get('subtotal','') }}</td></tr>
          <tr><td><strong>Tax</strong></td><td>{{ structured_data.get('tax','') }}</td></tr>
          <tr><td><strong>TOTAL</strong></td><td><strong>{{ structured_data.get('total','') }}</strong></td></tr>
        </tbody></table><div style="clear:both"></div>
        {% endif %}

      {# ═══════════════════ RESUME ═══════════════════ #}
      {% elif doc_type == 'resume' %}
        {% set pi = structured_data.get('personal_info', {}) %}
        <div class="info-grid">
          <div class="info-card"><div class="info-label">Name</div><div class="info-value large">{{ pi.get('name','—') }}</div></div>
          <div class="info-card"><div class="info-label">Email</div><div class="info-value">{{ pi.get('email','—') }}</div></div>
          <div class="info-card"><div class="info-label">Phone</div><div class="info-value">{{ pi.get('phone','—') }}</div></div>
        </div>
        {% if structured_data.get('experience') %}
        <div class="sub-title">Work Experience</div>
        <table><thead><tr><th>Company</th><th>Position</th><th>Duration</th><th>Location</th></tr></thead>
        <tbody>{% for e in structured_data.experience %}<tr>
          <td>{{ e.get('company','') }}</td><td>{{ e.get('position','') }}</td>
          <td>{{ e.get('duration','') }}</td><td>{{ e.get('location','') }}</td>
        </tr>{% endfor %}</tbody></table>
        {% endif %}
        {% if structured_data.get('education') %}
        <div class="sub-title">Education</div>
        <table><thead><tr><th>Institution</th><th>Degree</th><th>Year</th><th>GPA</th></tr></thead>
        <tbody>{% for e in structured_data.education %}<tr>
          <td>{{ e.get('institution','') }}</td><td>{{ e.get('degree','') }}</td>
          <td>{{ e.get('graduation_date',e.get('year','')) }}</td><td>{{ e.get('gpa','') }}</td>
        </tr>{% endfor %}</tbody></table>
        {% endif %}
        {% if structured_data.get('skills') %}
        <div class="sub-title">Skills</div>
        {% for s in structured_data.skills %}<span class="tag">{{ s }}</span>{% endfor %}
        {% endif %}

      {# ═══════════════════ AADHAAR ═══════════════════ #}
      {% elif doc_type == 'aadhar_card' %}
        <div class="highlight" style="font-size:1.4em;font-weight:bold;letter-spacing:0.12em">
          UID: {{ structured_data.get('uid_number','—') }}
        </div>
        <div class="info-grid">
          <div class="info-card"><div class="info-label">Name</div><div class="info-value large">{{ structured_data.get('name','—') }}</div></div>
          <div class="info-card"><div class="info-label">Date of Birth</div><div class="info-value">{{ structured_data.get('dob','—') }}</div></div>
          <div class="info-card"><div class="info-label">Gender</div><div class="info-value">{{ structured_data.get('gender','—') }}</div></div>
          {% if structured_data.get('relation_name') %}<div class="info-card"><div class="info-label">Relation</div><div class="info-value">{{ structured_data.relation_name }}</div></div>{% endif %}
        </div>
        {% set addr = structured_data.get('address', {}) %}
        {% if addr %}
        <div class="sub-title">Address</div>
        <table class="kv-table"><tbody>
          {% for k, v in addr.items() %}{% if v %}<tr><td>{{ k | replace('_',' ') | title }}</td><td>{{ v }}</td></tr>{% endif %}{% endfor %}
        </tbody></table>
        {% endif %}

      {# ═══════════════════ PAN CARD ═══════════════════ #}
      {% elif doc_type == 'pan_card' %}
        <div class="highlight" style="font-size:1.6em;font-weight:bold;letter-spacing:0.18em;font-family:monospace">
          {{ structured_data.get('pan_number','—') }}
        </div>
        <table class="kv-table"><tbody>
          <tr><td>Name</td><td><strong>{{ structured_data.get('name','—') }}</strong></td></tr>
          <tr><td>Father's Name</td><td>{{ structured_data.get('father_name','—') }}</td></tr>
          <tr><td>Date of Birth</td><td>{{ structured_data.get('dob','—') }}</td></tr>
          <tr><td>Card Type</td><td>{{ structured_data.get('card_type','—') }}</td></tr>
          <tr><td>Issuing Authority</td><td>{{ structured_data.get('issuing_authority','—') }}</td></tr>
        </tbody></table>

      {# ═══════════════════ DRIVING LICENCE ═══════════════════ #}
      {% elif doc_type == 'driving_licence' %}
        <div class="info-grid">
          <div class="info-card"><div class="info-label">DL Number</div><div class="info-value large">{{ structured_data.get('dl_number','—') }}</div></div>
          <div class="info-card"><div class="info-label">Name</div><div class="info-value large">{{ structured_data.get('name','—') }}</div></div>
          <div class="info-card"><div class="info-label">DOB</div><div class="info-value">{{ structured_data.get('dob','—') }}</div></div>
          <div class="info-card"><div class="info-label">Blood Group</div><div class="info-value">{{ structured_data.get('blood_group','—') }}</div></div>
        </div>
        {% if structured_data.get('vehicle_classes') %}
        <div class="sub-title">Vehicle Classes</div>
        <table><thead><tr><th>Class</th><th>Valid From</th><th>Valid To</th></tr></thead>
        <tbody>{% for vc in structured_data.vehicle_classes %}<tr>
          <td><strong>{{ vc.get('class','') }}</strong></td><td>{{ vc.get('valid_from','') }}</td><td>{{ vc.get('valid_to','') }}</td>
        </tr>{% endfor %}</tbody></table>
        {% endif %}

      {# ═══════════════════ PASSPORT ═══════════════════ #}
      {% elif doc_type == 'passport' %}
        <div class="highlight" style="font-size:1.5em;font-weight:bold;letter-spacing:0.15em;font-family:monospace">
          {{ structured_data.get('passport_number','—') }} &nbsp;·&nbsp; Expires: {{ structured_data.get('expiry_date','—') }}
        </div>
        <div class="info-grid">
          <div class="info-card"><div class="info-label">Surname</div><div class="info-value large">{{ structured_data.get('surname','—') }}</div></div>
          <div class="info-card"><div class="info-label">Given Names</div><div class="info-value large">{{ structured_data.get('given_names','—') }}</div></div>
          <div class="info-card"><div class="info-label">DOB</div><div class="info-value">{{ structured_data.get('dob','—') }}</div></div>
          <div class="info-card"><div class="info-label">Sex</div><div class="info-value">{{ structured_data.get('sex','—') }}</div></div>
          <div class="info-card"><div class="info-label">Nationality</div><div class="info-value">{{ structured_data.get('nationality','—') }}</div></div>
          <div class="info-card"><div class="info-label">Place of Issue</div><div class="info-value">{{ structured_data.get('place_of_issue','—') }}</div></div>
        </div>
        {% if structured_data.get('mrz_line1') %}
        <div class="sub-title">Machine Readable Zone</div>
        <div style="background:#1e293b;color:#a5f3fc;font-family:monospace;font-size:1.1em;padding:14px 20px;border-radius:8px;letter-spacing:0.05em;margin:10px 0">
          {{ structured_data.mrz_line1 }}<br>{{ structured_data.mrz_line2 }}
        </div>
        {% endif %}

      {# ═══════════════════ CHEQUE ═══════════════════ #}
      {% elif doc_type == 'cheque' %}
        <div class="info-grid">
          <div class="info-card"><div class="info-label">Cheque No.</div><div class="info-value large">{{ structured_data.get('cheque_number','—') }}</div></div>
          <div class="info-card"><div class="info-label">Payee</div><div class="info-value large">{{ structured_data.get('payee_name','—') }}</div></div>
          <div class="info-card"><div class="info-label">Amount</div><div class="info-value large">₹ {{ structured_data.get('amount_figures','—') }}</div></div>
          <div class="info-card"><div class="info-label">Date</div><div class="info-value">{{ structured_data.get('date','—') }}</div></div>
        </div>
        <div class="highlight">{{ structured_data.get('amount_words','—') }}</div>
        <table class="kv-table"><tbody>
          <tr><td>Bank</td><td>{{ structured_data.get('bank_name','—') }}</td></tr>
          <tr><td>Branch</td><td>{{ structured_data.get('branch_name','—') }}</td></tr>
          <tr><td>IFSC</td><td>{{ structured_data.get('ifsc_code','—') }}</td></tr>
          <tr><td>MICR</td><td>{{ structured_data.get('micr_code','—') }}</td></tr>
          <tr><td>Account No.</td><td>{{ structured_data.get('account_number','—') }}</td></tr>
          <tr><td>Drawer</td><td>{{ structured_data.get('drawer_name','—') }}</td></tr>
          <tr><td>Type</td><td>{{ structured_data.get('cheque_type','—') }}</td></tr>
          <tr><td>Crossed</td><td>{{ 'Yes' if structured_data.get('crossed') else 'No' }}</td></tr>
        </tbody></table>

      {# ═══════════════════ FORM 16 ═══════════════════ #}
      {% elif doc_type == 'form_16' %}
        <div class="info-grid">
          <div class="info-card"><div class="info-label">Assessment Year</div><div class="info-value large">{{ structured_data.get('assessment_year','—') }}</div></div>
          <div class="info-card"><div class="info-label">Form Part</div><div class="info-value">{{ structured_data.get('form_part','—') }}</div></div>
          <div class="info-card"><div class="info-label">Total TDS</div><div class="info-value large">₹ {{ (structured_data.get('tax') or {}).get('total_tds_deducted','—') }}</div></div>
        </div>
        {% set emp = structured_data.get('employer',{}) %}{% set empl = structured_data.get('employee',{}) %}
        <div class="sub-title">Employer</div>
        <table class="kv-table"><tbody>
          <tr><td>Name</td><td>{{ emp.get('name','—') }}</td></tr>
          <tr><td>TAN</td><td>{{ emp.get('tan','—') }}</td></tr>
          <tr><td>PAN</td><td>{{ emp.get('pan','—') }}</td></tr>
        </tbody></table>
        <div class="sub-title">Employee</div>
        <table class="kv-table"><tbody>
          <tr><td>Name</td><td>{{ empl.get('name','—') }}</td></tr>
          <tr><td>PAN</td><td>{{ empl.get('pan','—') }}</td></tr>
        </tbody></table>
        {% set tax = structured_data.get('tax',{}) %}
        {% if tax %}
        <div class="sub-title">Tax Summary</div>
        <table class="kv-table"><tbody>
          {% for k, v in tax.items() %}{% if v is not none %}<tr><td>{{ k | replace('_',' ') | title }}</td><td>₹ {{ v }}</td></tr>{% endif %}{% endfor %}
        </tbody></table>
        {% endif %}

      {# ═══════════════════ INSURANCE POLICY ═══════════════════ #}
      {% elif doc_type == 'insurance_policy' %}
        <div class="info-grid">
          <div class="info-card"><div class="info-label">Policy No.</div><div class="info-value large">{{ structured_data.get('policy_number','—') }}</div></div>
          <div class="info-card"><div class="info-label">Type</div><div class="info-value">{{ structured_data.get('policy_type','—') }}</div></div>
          <div class="info-card"><div class="info-label">Sum Assured</div><div class="info-value large">₹ {{ structured_data.get('sum_assured','—') }}</div></div>
          <div class="info-card"><div class="info-label">Premium</div><div class="info-value">₹ {{ structured_data.get('premium_amount','—') }} / {{ structured_data.get('premium_frequency','—') }}</div></div>
          <div class="info-card"><div class="info-label">Start Date</div><div class="info-value">{{ structured_data.get('policy_start_date','—') }}</div></div>
          <div class="info-card"><div class="info-label">End Date</div><div class="info-value">{{ structured_data.get('policy_end_date','—') }}</div></div>
        </div>
        {% set ins = structured_data.get('insured',{}) %}{% set nom = structured_data.get('nominee',{}) %}
        <div class="sub-title">Insured Person</div>
        <table class="kv-table"><tbody>
          <tr><td>Name</td><td>{{ ins.get('name','—') }}</td></tr>
          <tr><td>DOB</td><td>{{ ins.get('dob','—') }}</td></tr>
          <tr><td>Mobile</td><td>{{ ins.get('mobile','—') }}</td></tr>
        </tbody></table>
        <div class="sub-title">Nominee</div>
        <table class="kv-table"><tbody>
          <tr><td>Name</td><td>{{ nom.get('name','—') }}</td></tr>
          <tr><td>Relation</td><td>{{ nom.get('relation','—') }}</td></tr>
          <tr><td>Share</td><td>{{ nom.get('share_percentage','—') }}%</td></tr>
        </tbody></table>

      {# ═══════════════════ GST CERTIFICATE ═══════════════════ #}
      {% elif doc_type == 'gst_certificate' %}
        <div class="highlight" style="font-size:1.5em;font-weight:bold;font-family:monospace;letter-spacing:0.12em">
          GSTIN: {{ structured_data.get('gstin','—') }}
        </div>
        <table class="kv-table"><tbody>
          <tr><td>Legal Name</td><td><strong>{{ structured_data.get('legal_name','—') }}</strong></td></tr>
          <tr><td>Trade Name</td><td>{{ structured_data.get('trade_name','—') }}</td></tr>
          <tr><td>Constitution</td><td>{{ structured_data.get('constitution','—') }}</td></tr>
          <tr><td>Registration Date</td><td>{{ structured_data.get('registration_date','—') }}</td></tr>
          <tr><td>Status</td><td><span class="badge {% if structured_data.get('status') == 'Active' %}badge-success{% else %}badge-danger{% endif %}">{{ structured_data.get('status','—') }}</span></td></tr>
        </tbody></table>
        {% set ppb = structured_data.get('principal_place_of_business',{}) %}
        {% if ppb %}
        <div class="sub-title">Principal Place of Business</div>
        <table class="kv-table"><tbody>{% for k, v in ppb.items() %}{% if v %}<tr><td>{{ k | title }}</td><td>{{ v }}</td></tr>{% endif %}{% endfor %}</tbody></table>
        {% endif %}

      {# ═══════════════════ BIRTH CERTIFICATE ═══════════════════ #}
      {% elif doc_type == 'birth_certificate' %}
        <div class="info-grid">
          <div class="info-card"><div class="info-label">Registration No.</div><div class="info-value large">{{ structured_data.get('registration_number','—') }}</div></div>
          <div class="info-card"><div class="info-label">Child Name</div><div class="info-value large">{{ structured_data.get('child_name','—') }}</div></div>
          <div class="info-card"><div class="info-label">Date of Birth</div><div class="info-value">{{ structured_data.get('dob','—') }}</div></div>
          <div class="info-card"><div class="info-label">Gender</div><div class="info-value">{{ structured_data.get('gender','—') }}</div></div>
        </div>
        {% set pob = structured_data.get('place_of_birth',{}) %}
        {% if pob %}<div class="sub-title">Place of Birth</div>
        <table class="kv-table"><tbody>{% for k, v in pob.items() %}{% if v %}<tr><td>{{ k | replace('_',' ') | title }}</td><td>{{ v }}</td></tr>{% endif %}{% endfor %}</tbody></table>{% endif %}
        {% set fa = structured_data.get('father',{}) %}{% set mo = structured_data.get('mother',{}) %}
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:20px;margin-top:16px">
          <div><div class="sub-title">Father</div>
          <table class="kv-table"><tbody>{% for k, v in fa.items() %}{% if v %}<tr><td>{{ k | title }}</td><td>{{ v }}</td></tr>{% endif %}{% endfor %}</tbody></table></div>
          <div><div class="sub-title">Mother</div>
          <table class="kv-table"><tbody>{% for k, v in mo.items() %}{% if v %}<tr><td>{{ k | title }}</td><td>{{ v }}</td></tr>{% endif %}{% endfor %}</tbody></table></div>
        </div>

      {# ═══════════════════ DEATH CERTIFICATE ═══════════════════ #}
      {% elif doc_type == 'death_certificate' %}
        <div class="info-grid">
          <div class="info-card"><div class="info-label">Registration No.</div><div class="info-value large">{{ structured_data.get('registration_number','—') }}</div></div>
          <div class="info-card"><div class="info-label">Deceased Name</div><div class="info-value large">{{ structured_data.get('deceased_name','—') }}</div></div>
          <div class="info-card"><div class="info-label">Date of Death</div><div class="info-value">{{ structured_data.get('dod','—') }}</div></div>
          <div class="info-card"><div class="info-label">Age</div><div class="info-value">{{ structured_data.get('age','—') }} years</div></div>
        </div>
        <div class="highlight"><strong>Cause of Death:</strong> {{ structured_data.get('cause_of_death','—') }}</div>
        <table class="kv-table"><tbody>
          <tr><td>Gender</td><td>{{ structured_data.get('gender','—') }}</td></tr>
          <tr><td>Father / Husband</td><td>{{ structured_data.get('father_husband_name','—') }}</td></tr>
          <tr><td>Nationality</td><td>{{ structured_data.get('nationality','—') }}</td></tr>
          <tr><td>Religion</td><td>{{ structured_data.get('religion','—') }}</td></tr>
          <tr><td>Informant</td><td>{{ structured_data.get('informant_name','—') }} ({{ structured_data.get('informant_relation','—') }})</td></tr>
          <tr><td>Issuing Authority</td><td>{{ structured_data.get('issuing_authority','—') }}</td></tr>
        </tbody></table>

      {# ═══════════════════ LAND RECORD ═══════════════════ #}
      {% elif doc_type == 'land_record' %}
        <div class="info-grid">
          <div class="info-card"><div class="info-label">Record Type</div><div class="info-value large">{{ structured_data.get('record_type','—') }}</div></div>
          <div class="info-card"><div class="info-label">Survey No.</div><div class="info-value large">{{ structured_data.get('survey_number','—') }}</div></div>
          <div class="info-card"><div class="info-label">Village</div><div class="info-value">{{ structured_data.get('village','—') }}</div></div>
          <div class="info-card"><div class="info-label">Taluka / Tehsil</div><div class="info-value">{{ structured_data.get('taluka_tehsil','—') }}</div></div>
          <div class="info-card"><div class="info-label">District</div><div class="info-value">{{ structured_data.get('district','—') }}</div></div>
          <div class="info-card"><div class="info-label">Land Type</div><div class="info-value">{{ structured_data.get('land_type','—') }}</div></div>
        </div>
        {% set area = structured_data.get('total_area',{}) %}
        {% if area %}<div class="highlight"><strong>Total Area:</strong> {{ area.get('value','') }} {{ area.get('unit','') }}</div>{% endif %}
        {% if structured_data.get('owners') %}
        <div class="sub-title">Land Owners</div>
        <table><thead><tr><th>Name</th><th>Father's Name</th><th>Share</th><th>Type</th></tr></thead>
        <tbody>{% for own in structured_data.owners %}<tr>
          <td><strong>{{ own.get('name','') }}</strong></td><td>{{ own.get('father_name','') }}</td>
          <td>{{ own.get('share','') }}</td><td>{{ own.get('ownership_type','') }}</td>
        </tr>{% endfor %}</tbody></table>
        {% endif %}

      {# ═══════════════════ NREGA CARD ═══════════════════ #}
      {% elif doc_type == 'nrega_card' %}
        <div class="highlight" style="font-size:1.3em;font-weight:bold;font-family:monospace">
          Job Card No.: {{ structured_data.get('job_card_number','—') }}
        </div>
        <div class="info-grid">
          {% set hh = structured_data.get('household_head',{}) %}
          <div class="info-card"><div class="info-label">Head of Household</div><div class="info-value large">{{ hh.get('name','—') }}</div></div>
          <div class="info-card"><div class="info-label">Gram Panchayat</div><div class="info-value">{{ structured_data.get('gram_panchayat','—') }}</div></div>
          <div class="info-card"><div class="info-label">Block</div><div class="info-value">{{ structured_data.get('block','—') }}</div></div>
          <div class="info-card"><div class="info-label">District</div><div class="info-value">{{ structured_data.get('district','—') }}</div></div>
        </div>
        {% if structured_data.get('job_seekers') %}
        <div class="sub-title">Family Members</div>
        <table><thead><tr><th>Name</th><th>Gender</th><th>Age</th><th>Relation</th></tr></thead>
        <tbody>{% for js in structured_data.job_seekers %}<tr>
          <td>{{ js.get('name','') }}</td><td>{{ js.get('gender','') }}</td>
          <td>{{ js.get('age','') }}</td><td>{{ js.get('relation','') }}</td>
        </tr>{% endfor %}</tbody></table>
        {% endif %}
        {% if structured_data.get('work_entries') %}
        <div class="sub-title">Work Entries</div>
        <table><thead><tr><th>Muster No.</th><th>Work Name</th><th>From</th><th>To</th><th>Days</th><th>Amount (₹)</th></tr></thead>
        <tbody>{% for we in structured_data.work_entries %}<tr>
          <td>{{ we.get('muster_roll_number','') }}</td><td>{{ we.get('work_name','') }}</td>
          <td>{{ we.get('date_from','') }}</td><td>{{ we.get('date_to','') }}</td>
          <td>{{ we.get('days_worked','') }}</td><td>{{ we.get('amount_earned','') }}</td>
        </tr>{% endfor %}</tbody></table>
        <div class="info-grid" style="margin-top:12px">
          <div class="info-card"><div class="info-label">Total Days Worked</div><div class="info-value large">{{ structured_data.get('total_days_worked','—') }}</div></div>
          <div class="info-card"><div class="info-label">Total Wages (₹)</div><div class="info-value large">{{ structured_data.get('total_wages_earned','—') }}</div></div>
        </div>
        {% endif %}

      {# ═════ MARKSHEET ═════ #}
      {% elif doc_type == 'marksheet' %}
        <div class="info-grid">
          <div class="info-card"><div class="info-label">Student</div><div class="info-value large">{{ structured_data.get('student_name','—') }}</div></div>
          <div class="info-card"><div class="info-label">Roll No.</div><div class="info-value">{{ structured_data.get('roll_number','—') }}</div></div>
          <div class="info-card"><div class="info-label">Class</div><div class="info-value">{{ structured_data.get('class_standard','—') }}</div></div>
          <div class="info-card"><div class="info-label">Board</div><div class="info-value">{{ structured_data.get('board','—') }}</div></div>
          <div class="info-card"><div class="info-label">Percentage</div><div class="info-value large">{{ structured_data.get('percentage','—') }}%</div></div>
          <div class="info-card"><div class="info-label">Result</div>
            <div class="info-value"><span class="badge {% if structured_data.get('result','').upper() == 'PASS' %}badge-success{% else %}badge-danger{% endif %}">{{ structured_data.get('result','—') }}</span></div></div>
        </div>
        {% if structured_data.get('subjects') %}
        <table><thead><tr><th>Subject</th><th>Max</th><th>Obtained</th><th>Grade</th><th>Pass/Fail</th></tr></thead>
        <tbody>{% for subj in structured_data.subjects %}<tr>
          <td>{{ subj.get('name','') }}</td><td>{{ subj.get('max_marks','') }}</td>
          <td>{{ subj.get('marks_obtained','') }}</td><td>{{ subj.get('grade','') }}</td>
          <td><span class="badge {% if subj.get('pass_fail','').upper() == 'PASS' %}badge-success{% else %}badge-danger{% endif %}">{{ subj.get('pass_fail','') }}</span></td>
        </tr>{% endfor %}</tbody></table>
        {% endif %}

      {# ═════ PRESCRIPTION ═════ #}
      {% elif doc_type == 'prescription' %}
        {% set doc = structured_data.get('doctor',{}) %}{% set pat = structured_data.get('patient',{}) %}
        <div class="info-grid">
          <div class="info-card"><div class="info-label">Doctor</div><div class="info-value large">{{ doc.get('name','—') }}</div></div>
          <div class="info-card"><div class="info-label">Patient</div><div class="info-value large">{{ pat.get('name','—') }}</div></div>
          <div class="info-card"><div class="info-label">Date</div><div class="info-value">{{ structured_data.get('prescription_date','—') }}</div></div>
          <div class="info-card"><div class="info-label">Diagnosis</div><div class="info-value">{{ structured_data.get('diagnosis','—') }}</div></div>
        </div>
        {% if structured_data.get('medicines') %}
        <div class="sub-title">Medicines Prescribed</div>
        <table><thead><tr><th>Medicine</th><th>Dosage</th><th>Frequency</th><th>Duration</th><th>Instructions</th></tr></thead>
        <tbody>{% for med in structured_data.medicines %}<tr>
          <td><strong>{{ med.get('name','') }}</strong></td><td>{{ med.get('dosage','') }}</td>
          <td>{{ med.get('frequency','') }}</td><td>{{ med.get('duration','') }}</td><td>{{ med.get('instructions','') }}</td>
        </tr>{% endfor %}</tbody></table>
        {% endif %}

      {# ═════ BANK STATEMENT ═════ #}
      {% elif doc_type == 'bank_statement' %}
        <div class="info-grid">
          <div class="info-card"><div class="info-label">Account Holder</div><div class="info-value large">{{ structured_data.get('account_holder','—') }}</div></div>
          <div class="info-card"><div class="info-label">Account No.</div><div class="info-value">{{ structured_data.get('account_number','—') }}</div></div>
          <div class="info-card"><div class="info-label">Bank</div><div class="info-value">{{ structured_data.get('bank_name','—') }}</div></div>
          <div class="info-card"><div class="info-label">Opening Balance</div><div class="info-value">₹ {{ structured_data.get('opening_balance','—') }}</div></div>
          <div class="info-card"><div class="info-label">Closing Balance</div><div class="info-value large">₹ {{ structured_data.get('closing_balance','—') }}</div></div>
        </div>
        {% if structured_data.get('transactions') %}
        <div class="sub-title">Transactions</div>
        <table><thead><tr><th>Date</th><th>Description</th><th>Debit</th><th>Credit</th><th>Balance</th></tr></thead>
        <tbody>{% for txn in structured_data.transactions %}<tr>
          <td>{{ txn.get('date','') }}</td><td>{{ txn.get('description','') }}</td>
          <td>{{ txn.get('debit_amount','') }}</td><td>{{ txn.get('credit_amount','') }}</td><td>{{ txn.get('balance','') }}</td>
        </tr>{% endfor %}</tbody></table>
        {% endif %}

      {# ═════ RATION CARD ═════ #}
      {% elif doc_type == 'ration_card' %}
        <div class="info-grid">
          <div class="info-card"><div class="info-label">Card No.</div><div class="info-value large">{{ structured_data.get('card_number','—') }}</div></div>
          <div class="info-card"><div class="info-label">Card Type</div><div class="info-value">{{ structured_data.get('card_type','—') }}</div></div>
          <div class="info-card"><div class="info-label">State</div><div class="info-value">{{ structured_data.get('issuing_state','—') }}</div></div>
        </div>
        {% set hof = structured_data.get('head_of_family',{}) %}
        {% if hof %}<div class="sub-title">Head of Family</div>
        <table class="kv-table"><tbody>{% for k, v in hof.items() %}{% if v %}<tr><td>{{ k | replace('_',' ') | title }}</td><td>{{ v }}</td></tr>{% endif %}{% endfor %}</tbody></table>{% endif %}
        {% if structured_data.get('family_members') %}
        <div class="sub-title">Family Members</div>
        <table><thead><tr><th>S.No</th><th>Name</th><th>Age</th><th>Relation</th></tr></thead>
        <tbody>{% for m in structured_data.family_members %}<tr>
          <td>{{ m.get('serial_number','') }}</td><td>{{ m.get('name','') }}</td>
          <td>{{ m.get('age','') }}</td><td>{{ m.get('relation','') }}</td>
        </tr>{% endfor %}</tbody></table>
        {% endif %}

      {# ═════ UTILITY BILL ═════ #}
      {% elif doc_type == 'utility_bill' %}
        <div class="info-grid">
          <div class="info-card"><div class="info-label">Bill Type</div><div class="info-value">{{ structured_data.get('bill_type','—') }}</div></div>
          <div class="info-card"><div class="info-label">Consumer</div><div class="info-value large">{{ structured_data.get('consumer_name','—') }}</div></div>
          <div class="info-card"><div class="info-label">Consumer No.</div><div class="info-value">{{ structured_data.get('consumer_number','—') }}</div></div>
          <div class="info-card"><div class="info-label">Units Consumed</div><div class="info-value">{{ structured_data.get('units_consumed','—') }}</div></div>
          <div class="info-card"><div class="info-label">Amount Due</div><div class="info-value large">₹ {{ structured_data.get('total_amount','—') }}</div></div>
          <div class="info-card"><div class="info-label">Due Date</div><div class="info-value">{{ structured_data.get('due_date','—') }}</div></div>
        </div>

      {# ════ CONTRACT ═══ #}
      {% elif doc_type == 'contract' %}
        <div class="info-grid">
          <div class="info-card"><div class="info-label">Title</div><div class="info-value large">{{ structured_data.get('contract_title','—') }}</div></div>
          <div class="info-card"><div class="info-label">Type</div><div class="info-value">{{ structured_data.get('contract_type','—') }}</div></div>
          <div class="info-card"><div class="info-label">Effective Date</div><div class="info-value">{{ structured_data.get('effective_date','—') }}</div></div>
          <div class="info-card"><div class="info-label">Expiration Date</div><div class="info-value">{{ structured_data.get('expiration_date','—') }}</div></div>
        </div>
        {% if structured_data.get('parties') %}
        <div class="sub-title">Parties</div>
        <table><thead><tr><th>Name</th><th>Role</th><th>Address</th></tr></thead>
        <tbody>{% for p in structured_data.parties %}<tr>
          <td><strong>{{ p.get('name','') }}</strong></td><td>{{ p.get('role','') }}</td><td>{{ p.get('address','') }}</td>
        </tr>{% endfor %}</tbody></table>
        {% endif %}

      {# ════ CERTIFICATE (GENERIC) ═══ #}
      {% elif doc_type == 'certificate' %}
        <div class="info-grid">
          <div class="info-card"><div class="info-label">Certificate Type</div><div class="info-value large">{{ structured_data.get('certificate_type','—') }}</div></div>
          <div class="info-card"><div class="info-label">Certificate No.</div><div class="info-value">{{ structured_data.get('certificate_number','—') }}</div></div>
          <div class="info-card"><div class="info-label">Issue Date</div><div class="info-value">{{ structured_data.get('issue_date','—') }}</div></div>
          <div class="info-card"><div class="info-label">Event Date</div><div class="info-value">{{ structured_data.get('event_date','—') }}</div></div>
        </div>
        {% set pp = structured_data.get('primary_person',{}) %}
        {% if pp %}<div class="sub-title">Primary Person</div>
        <table class="kv-table"><tbody>{% for k, v in pp.items() %}{% if v %}<tr><td>{{ k | replace('_',' ') | title }}</td><td>{{ v }}</td></tr>{% endif %}{% endfor %}</tbody></table>{% endif %}
        {% set sp = structured_data.get('secondary_person',{}) %}
        {% if sp %}<div class="sub-title">Secondary Person</div>
        <table class="kv-table"><tbody>{% for k, v in sp.items() %}{% if v %}<tr><td>{{ k | replace('_',' ') | title }}</td><td>{{ v }}</td></tr>{% endif %}{% endfor %}</tbody></table>{% endif %}
        <div class="sub-title">Issuing Authority</div>
        <table class="kv-table"><tbody>
          <tr><td>Authority</td><td>{{ structured_data.get('issuing_authority','—') }}</td></tr>
          <tr><td>Registrar</td><td>{{ structured_data.get('registrar_name','—') }}</td></tr>
        </tbody></table>

      {# ════ FALLBACK ═══ #}
      {% else %}
        <p><em>Detailed view not available for document type <strong>{{ doc_type }}</strong>. Showing raw extracted fields:</em></p>
        <table class="kv-table"><tbody>
        {% for k, v in structured_data.items() %}
          {% if v is not none and v != '' %}
          <tr><td>{{ k | replace('_',' ') | title }}</td>
          <td>{% if v is mapping %}{{ v | tojson(indent=2) }}{%elif v is iterable and v is not string %}{{ v | join(', ') }}{% else %}{{ v }}{% endif %}</td></tr>
          {% endif %}
        {% endfor %}
        </tbody></table>
      {% endif %}

    </div>
    {% endif %}

    <!-- Metadata -->
    <div class="section">
      <h2 class="section-title">ℹ️ Document Metadata</h2>
      <div class="info-grid">
        <div class="info-card"><div class="info-label">Filename</div><div class="info-value">{{ metadata.get('filename','') }}</div></div>
        <div class="info-card"><div class="info-label">File Type</div><div class="info-value">{{ (metadata.get('file_type','') or '') | upper }}</div></div>
        <div class="info-card"><div class="info-label">Processing Time</div><div class="info-value">{{ metadata.get('processing_time_seconds','') }}s</div></div>
        <div class="info-card"><div class="info-label">Word Count</div><div class="info-value">{{ text.get('word_count','') }}</div></div>
        {% if metadata.get('detected_language') %}<div class="info-card"><div class="info-label">Language</div><div class="info-value">{{ metadata.detected_language }}</div></div>{% endif %}
        {% if metadata.get('extractor_used') %}<div class="info-card"><div class="info-label">Extractor</div><div class="info-value">{{ metadata.extractor_used }}</div></div>{% endif %}
      </div>
    </div>

    <!-- Processing Log -->
    {% if extraction_log %}
    <div class="section">
      <h2 class="section-title">📝 Processing Log</h2>
      {% for entry in extraction_log %}
      <div class="log-entry">{{ loop.index }}. {{ entry }}</div>
      {% endfor %}
    </div>
    {% endif %}

  </div>

  <div class="footer">
    Generated by ADIVA &nbsp;·&nbsp; {{ generated_at }}
  </div>
</div>
</body>
</html>"""
        return Template(template_str)
