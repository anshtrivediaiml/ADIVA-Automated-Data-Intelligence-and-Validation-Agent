"""
HTML Exporter

Export extraction results to formatted HTML reports.
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
        """Initialize HTML exporter with template"""
        self.template = self._get_template()
    
    def export(self, extraction_result: Dict[str, Any], output_path: str = None) -> str:
        """
        Export extraction result to HTML
        
        Args:
            extraction_result: Complete extraction result dictionary
            output_path: Optional custom output path
            
        Returns:
            Path to created HTML file
        """
        if not output_path:
            output_path = config.get_output_filename("extracted", ".html")
        
        output_path = Path(output_path)
        
        # Prepare template data
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
        
        # Render HTML
        html_content = self.template.render(**template_data)
        
        # Save to file
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(html_content)
        
        logger.info(f"Exported to HTML: {output_path.name}")
        return str(output_path)
    
    def _get_template(self) -> Template:
        """Get Jinja2 template for HTML report"""
        template_str = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ADIVA Extraction Report</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            padding: 20px;
            min-height: 100vh;
        }
        
        .container {
            max-width: 1200px;
            margin: 0 auto;
            background: white;
            border-radius: 12px;
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
            overflow: hidden;
        }
        
        .header {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 40px;
            text-align: center;
        }
        
        .header h1 {
            font-size: 2.5em;
            margin-bottom: 10px;
        }
        
        .header p {
            font-size: 1.1em;
            opacity: 0.9;
        }
        
        .content {
            padding: 40px;
        }
        
        .section {
            margin-bottom: 40px;
        }
        
        .section-title {
            font-size: 1.8em;
            color: #667eea;
            margin-bottom: 20px;
            padding-bottom: 10px;
            border-bottom: 3px solid #667eea;
        }
        
        .badge {
            display: inline-block;
            padding: 8px 16px;
            border-radius: 20px;
            font-weight: bold;
            margin: 5px;
        }
        
        .badge-success {
            background: #10b981;
            color: white;
        }
        
        .badge-warning {
            background: #f59e0b;
            color: white;
        }
        
        .badge-info {
            background: #3b82f6;
            color: white;
        }
        
        .info-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }
        
        .info-card {
            background: #f9fafb;
            padding: 20px;
            border-radius: 8px;
            border-left: 4px solid #667eea;
        }
        
        .info-label {
            font-weight: bold;
            color: #6b7280;
            margin-bottom: 8px;
            text-transform: uppercase;
            font-size: 0.85em;
        }
        
        .info-value {
            font-size: 1.15em;
            color: #1f2937;
        }
        
        .confidence-bar {
            background: #e5e7eb;
            height: 30px;
            border-radius: 15px;
            overflow: hidden;
            margin: 10px 0;
        }
        
        .confidence-fill {
            height: 100%;
            background: linear-gradient(90deg, #10b981 0%, #059669 100%);
            display: flex;
            align-items: center;
            padding: 0 15px;
            color: white;
            font-weight: bold;
            transition: width 0.3s;
        }
        
        .confidence-fill.medium {
            background: linear-gradient(90deg, #f59e0b 0%, #d97706 100%);
        }
        
        .confidence-fill.low {
            background: linear-gradient(90deg, #ef4444 0%, #dc2626 100%);
        }
        
        table {
            width: 100%;
            border-collapse: collapse;
            margin: 20px 0;
        }
        
        th, td {
            padding: 12px;
            text-align: left;
            border-bottom: 1px solid #e5e7eb;
        }
        
        th {
            background: #667eea;
            color: white;
            font-weight: bold;
        }
        
        tr:hover {
            background: #f9fafb;
        }
        
        .log-entry {
            padding: 10px;
            margin: 5px 0;
            background: #f3f4f6;
            border-radius: 6px;
            font-family: 'Courier New', monospace;
            font-size: 0.9em;
        }
        
        .metric-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 15px;
            margin: 20px 0;
        }
        
        .metric-card {
            background: #f9fafb;
            padding: 20px;
            border-radius: 8px;
            text-align: center;
        }
        
        .metric-value {
            font-size: 2em;
            font-weight: bold;
            color: #667eea;
        }
        
        .metric-label {
            color: #6b7280;
            margin-top: 8px;
            text-transform: uppercase;
            font-size: 0.85em;
        }
        
        .footer {
            background: #f3f4f6;
            padding: 20px;
            text-align: center;
            color: #6b7280;
            font-size: 0.9em;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>📄 ADIVA Extraction Report</h1>
            <p>Intelligent Document Analysis & Extraction</p>
        </div>
        
        <div class="content">
            <!-- Classification Section -->
            {% if classification %}
            <div class="section">
                <h2 class="section-title">🤖 AI Classification</h2>
                <div class="info-grid">
                    <div class="info-card">
                        <div class="info-label">Document Type</div>
                        <div class="info-value">{{ classification.document_type|upper }}</div>
                    </div>
                    <div class="info-card">
                        <div class="info-label">Confidence</div>
                        <div class="info-value">{{ (classification.confidence * 100)|round(1) }}%</div>
                    </div>
                </div>
                {% if classification.reasoning %}
                <div class="info-card">
                    <div class="info-label">Reasoning</div>
                    <div class="info-value">{{ classification.reasoning }}</div>
                </div>
                {% endif %}
            </div>
            {% endif %}
            
            <!-- Confidence Metrics -->
            {% if confidence %}
            <div class="section">
                <h2 class="section-title">📊 Quality Metrics</h2>
                <div class="metric-grid">
                    <div class="metric-card">
                        <div class="metric-value">{{ (confidence.overall_confidence * 100)|round(1) }}%</div>
                        <div class="metric-label">Overall Confidence</div>
                    </div>
                    <div class="metric-card">
                        <div class="metric-value">{{ confidence.grade }}</div>
                        <div class="metric-label">Quality Grade</div>
                    </div>
                </div>
                
                <h3 style="margin: 20px 0 10px 0;">Detailed Metrics</h3>
                {% for metric, value in confidence.metrics.items() %}
                <div style="margin: 10px 0;">
                    <strong>{{ metric|replace('_', ' ')|title }}:</strong>
                    <div class="confidence-bar">
                        <div class="confidence-fill {% if value < 0.7 %}low{% elif value < 0.85 %}medium{% endif %}" 
                             style="width: {{ (value * 100)|round(0) }}%">
                            {{ (value * 100)|round(1) }}%
                        </div>
                    </div>
                </div>
                {% endfor %}
                
                {% if confidence.explanations %}
                <h3 style="margin: 20px 0 10px 0;">Analysis</h3>
                {% for explanation in confidence.explanations %}
                <div class="log-entry">{{ explanation }}</div>
                {% endfor %}
                {% endif %}
            </div>
            {% endif %}
            
            <!-- Structured Data -->
            {% if structured_data %}
            <div class="section">
                <h2 class="section-title">📋 Extracted Data</h2>
                
                {% if doc_type == 'invoice' %}
                    <h3>Invoice Information</h3>
                    <div class="info-grid">
                        <div class="info-card">
                            <div class="info-label">Invoice Number</div>
                            <div class="info-value">{{ structured_data.invoice_number }}</div>
                        </div>
                        <div class="info-card">
                            <div class="info-label">Invoice Date</div>
                            <div class="info-value">{{ structured_data.invoice_date }}</div>
                        </div>
                        <div class="info-card">
                            <div class="info-label">Total Amount</div>
                            <div class="info-value">{{ structured_data.currency }} {{ structured_data.total }}</div>
                        </div>
                    </div>
                    
                    {% if structured_data.line_items %}
                    <h3 style="margin-top: 30px;">Line Items</h3>
                    <table>
                        <thead>
                            <tr>
                                <th>Description</th>
                                <th>Quantity</th>
                                <th>Unit Price</th>
                                <th>Total</th>
                            </tr>
                        </thead>
                        <tbody>
                            {% for item in structured_data.line_items %}
                            <tr>
                                <td>{{ item.description }}</td>
                                <td>{{ item.quantity }}</td>
                                <td>{{ item.unit_price }}</td>
                                <td>{{ item.total }}</td>
                            </tr>
                            {% endfor %}
                        </tbody>
                    </table>
                    {% endif %}
                    
                {% elif doc_type == 'resume' %}
                    {% if structured_data.personal_info %}
                    <h3>Personal Information</h3>
                    <div class="info-grid">
                        <div class="info-card">
                            <div class="info-label">Name</div>
                            <div class="info-value">{{ structured_data.personal_info.name }}</div>
                        </div>
                        <div class="info-card">
                            <div class="info-label">Email</div>
                            <div class="info-value">{{ structured_data.personal_info.email }}</div>
                        </div>
                    </div>
                    {% endif %}
                    
                    {% if structured_data.experience %}
                    <h3 style="margin-top: 30px;">Work Experience</h3>
                    <table>
                        <thead>
                            <tr>
                                <th>Company</th>
                                <th>Position</th>
                                <th>Duration</th>
                            </tr>
                        </thead>
                        <tbody>
                            {% for exp in structured_data.experience %}
                            <tr>
                                <td>{{ exp.company }}</td>
                                <td>{{ exp.position }}</td>
                                <td>{{ exp.duration }}</td>
                            </tr>
                            {% endfor %}
                        </tbody>
                    </table>
                    {% endif %}
                {% endif %}
            </div>
            {% endif %}
            
            <!-- Metadata -->
            <div class="section">
                <h2 class="section-title">ℹ️ Document Metadata</h2>
                <div class="info-grid">
                    <div class="info-card">
                        <div class="info-label">Filename</div>
                        <div class="info-value">{{ metadata.filename }}</div>
                    </div>
                    <div class="info-card">
                        <div class="info-label">File Type</div>
                        <div class="info-value">{{ metadata.file_type|upper }}</div>
                    </div>
                    <div class="info-card">
                        <div class="info-label">Processing Time</div>
                        <div class="info-value">{{ metadata.processing_time_seconds }}s</div>
                    </div>
                    <div class="info-card">
                        <div class="info-label">Word Count</div>
                        <div class="info-value">{{ text.word_count }}</div>
                    </div>
                </div>
            </div>
            
            <!-- Extraction Log -->
            {% if extraction_log %}
            <div class="section">
                <h2 class="section-title">📝 Processing Log</h2>
                {% for entry in extraction_log %}
                <div class="log-entry">{{ entry }}</div>
                {% endfor %}
            </div>
            {% endif %}
        </div>
        
        <div class="footer">
            Generated by ADIVA on {{ generated_at }}
        </div>
    </div>
</body>
</html>
        """
        return Template(template_str)
