# ADIVA - Autonomous Data Intelligence & Verification Agent

## 🎯 Overview

ADIVA is an AI-powered backend system designed to process documents, extract information, and validate data using advanced language models.

## 🚀 Features

- **Document Processing**: Supports PDF and DOCX file formats
- **Text Extraction**: Automated extraction of text content from documents
- **AI-Powered Analysis**: Integration with Mistral AI for intelligent document understanding
- **Data Validation**: Structured data validation and quality checks
- **Comprehensive Logging**: Detailed logging of all processing steps

## 📁 Project Structure

```
adiva/
│
├── backend/
│   ├── main.py          # FastAPI application entry point
│   ├── config.py        # Configuration and environment variables
│   ├── extractor.py     # Document text extraction module
│   ├── ai_agent.py      # Mistral AI integration module
│   ├── validator.py     # Data validation module
│   └── routes.py        # API routes and endpoints
│
├── outputs/
│   ├── extracted/       # Extracted text files
│   ├── validated/       # Validated data outputs
│   └── logs/            # Processing logs
│
├── data/
│   └── samples/         # Sample documents for testing
│
├── requirements.txt     # Python dependencies
└── README.md           # This file
```

## 🔧 Installation

1. **Clone the repository** (or navigate to the project directory)

2. **Create a virtual environment**:
   ```bash
   python -m venv venv
   ```

3. **Activate the virtual environment**:
   - Windows:
     ```bash
     venv\Scripts\activate
     ```
   - Linux/Mac:
     ```bash
     source venv/bin/activate
     ```

4. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

5. **Set up environment variables**:
   - Copy the example environment file:
     ```bash
     copy .env.example .env
     ```
   - Edit `.env` and add your Mistral API key:
     ```
     MISTRAL_API_KEY=your_actual_api_key_here
     PROJECT_NAME=ADIVA
     LOG_LEVEL=INFO
     ```
   - Get your API key from: https://console.mistral.ai/

## 🏃‍♂️ Running the Application

Use the unified API entry point:

```bash
cd backend
python -m uvicorn api.main:app --reload
```

The API will be available at `http://localhost:8000`

## 📚 API Documentation

Once the server is running, access the interactive API documentation at:
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

## 🆔 Extraction IDs

The API now returns a **UUID** as `extraction_id`. Use that UUID for:
- `GET /api/results/{extraction_id}`
- `GET /api/download/{extraction_id}/{format}`
- `DELETE /api/extractions/{extraction_id}`

## 🧪 Testing

Place sample PDF or DOCX files in the `data/samples/` directory for testing.

## 🗄️ Database (Supabase Postgres)

This project uses PostgreSQL for persistence. Supabase is recommended for hosted Postgres.

### Supabase Setup
1. Create a new Supabase project.
2. In the Supabase dashboard, go to **Project Settings → Database**.
3. Copy the **Connection string** (Postgres) and set it in `.env`:
   ```
   DATABASE_URL=postgresql+psycopg://postgres:YOUR_PASSWORD@db.YOUR_PROJECT_REF.supabase.co:5432/postgres?sslmode=require
   ```

### Run Migrations
```bash
alembic upgrade head
```

This will create the core tables:
`users`, `documents`, `extractions`, `extraction_results`, `extraction_outputs`, `validation_reports`, `audit_logs`.

### Seed Admin User
Set these in `.env`:
```
ADMIN_EMAIL=admin@example.com
ADMIN_PASSWORD=change_me
ADMIN_NAME=Admin
ADMIN_USERNAME=admin
ADMIN_ROLE=admin
```

Then run:
```bash
python backend/db/seed_admin.py
```

### Reset Admin User (Optional)
To delete an existing admin and seed a new one, set these in `.env`:
```
ADMIN_DELETE_EMAILS=old@example.com
ADMIN_EMAIL=new@example.com
ADMIN_PASSWORD=your_secure_password
ADMIN_NAME=Your Name
ADMIN_USERNAME=yourusername
ADMIN_ROLE=admin
```

Then run:
```bash
python backend/db/reset_admin.py
```

## 📝 Development Status

**Phase 1: Project Setup & Structure** ✅ COMPLETE
- Project structure created
- Placeholder files added
- Dependencies defined

**Phase 2: Configuration & Environment** ✅ COMPLETE
- Environment variable loading implemented
- Configuration validation added
- .env template created
- Path management configured

**Phase 3: Centralized Logging System** ✅ COMPLETE
- Loguru integration complete
- Console and file logging configured
- Utility logging functions created
- All modules connected to logger
- Log rotation and retention configured

**Next Phases**:
- Phase 4: Document Extraction Implementation
- Phase 5: AI Agent Integration
- Phase 6: Validation System
- Phase 7: API Endpoints & Testing

## 🛠️ Technology Stack

- **Framework**: FastAPI
- **Document Processing**: pdfplumber, python-docx
- **AI/LLM**: Mistral AI
- **Data Handling**: pandas
- **Logging**: loguru
- **Configuration**: python-dotenv

## 📄 License

To be determined

## 👥 Contributors

- Development Team

---

**ADIVA** - Transforming documents into actionable intelligence
