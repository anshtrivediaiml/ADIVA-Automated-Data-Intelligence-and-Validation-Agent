# How to Run the ADIVA API

## 🚀 Quick Start

### **Start the API:**

```powershell
# Option 1: Direct Python
cd C:\Users\AnshTrivedi\Documents\ADIVA
python backend/api/main.py

# Option 2: Using uvicorn (recommended for development)
uvicorn api.main:app --reload --app-dir backend

# Option 3: Using uvicorn with custom port
uvicorn api.main:app --reload --app-dir backend --port 8000 --host 0.0.0.0
```

### **Access the API:**

- **API Root:** http://localhost:8000/
- **Swagger Docs:** http://localhost:8000/docs
- **ReDoc:** http://localhost:8000/redoc
- **Health Check:** http://localhost:8000/api/health

---

## 📚 API Endpoints

### **Health & Status**

#### GET /api/health
Check API health and dependencies.

```bash
curl http://localhost:8000/api/health
```

#### GET /api/status
Get detailed API status.

```bash
curl http://localhost:8000/api/status
```

---

### **Document Extraction**

#### POST /api/extract
Extract from single document.

```bash
# Using curl
curl -X POST "http://localhost:8000/api/extract" \
  -H "Content-Type: multipart/form-data" \
  -F "file=@invoice.pdf"

# Using PowerShell
$file = Get-Item "invoice.pdf"
$form = @{ file = $file }
Invoke-RestMethod -Method Post -Uri "http://localhost:8000/api/extract" -Form $form
```

**Response:**
```json
{
  "status": "success",
  "extraction_id": "20260204_180000_invoice",
  "document_type": "invoice",
  "confidence": 0.885,
  "extraction_folder": "outputs/extracted/20260204_180000_invoice",
  "files": {
    "json": "extraction.json",
    "csv": "extraction.csv",
    "excel": "extraction.xlsx",
    "html": "extraction.html"
  },
  "processing_time": 8.5
}
```

#### POST /api/extract/batch
Batch extraction from multiple documents.

```bash
# Using curl
curl -X POST "http://localhost:8000/api/extract/batch" \
  -F "files=@invoice1.pdf" \
  -F "files=@invoice2.pdf" \
  -F "files=@resume.pdf"
```

---

### **Results Management**

#### GET /api/results/{extraction_id}
Get extraction results.

```bash
curl http://localhost:8000/api/results/20260204_180000_invoice
```

#### GET /api/download/{extraction_id}/{format}
Download file in specific format.

```bash
# Download JSON
curl -O http://localhost:8000/api/download/20260204_180000_invoice/json

# Download CSV
curl -O http://localhost:8000/api/download/20260204_180000_invoice/csv

# Download Excel
curl -O http://localhost:8000/api/download/20260204_180000_invoice/xlsx

# Download HTML
curl -O http://localhost:8000/api/download/20260204_180000_invoice/html
```

#### GET /api/extractions
List all extractions with pagination.

```bash
# First page
curl "http://localhost:8000/api/extractions?page=1&page_size=20"

# Filter by document type
curl "http://localhost:8000/api/extractions?document_type=invoice"
```

#### DELETE /api/extractions/{extraction_id}
Delete extraction.

```bash
curl -X DELETE http://localhost:8000/api/delete/20260204_180000_invoice
```

---

## 🧪 Testing the API

### **Run Test Suite:**

```powershell
# Start API first (in one terminal)
python backend/api/main.py

# Run tests (in another terminal)
python test_api.py
```

### **Manual Testing with Swagger:**

1. Start the API
2. Open http://localhost:8000/docs
3. Try out endpoints interactively
4. Upload files and see responses

---

## 📦 Production Deployment

### **Using Gunicorn (Linux):**

```bash
pip install gunicorn
gunicorn api.main:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000
```

### **Using Docker:**

Create `Dockerfile`:
```dockerfile
FROM python:3.10-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY backend/ ./backend/
COPY data/ ./data/

CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000", "--app-dir", "backend"]
```

Build and run:
```bash
docker build -t adiva-api .
docker run -p 8000:8000 adiva-api
```

---

## ⚙️ Configuration

### **Environment Variables:**

```env
# .env file
MISTRAL_API_KEY=your_key_here
LOG_LEVEL=INFO
MAX_UPLOAD_SIZE=10485760
```

### **API Settings:**

Edit `backend/api/routes/extraction.py`:
```python
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB
ALLOWED_EXTENSIONS = {'.pdf', '.docx', '.png', '.jpg'}
```

---

## 🔒 Security (Production)

### **Add Authentication:**

```python
from fastapi import Header, HTTPException

async def verify_api_key(x_api_key: str = Header(...)):
    if x_api_key != "your-secret-key":
        raise HTTPException(status_code=401, detail="Invalid API Key")

@router.post("/extract", dependencies=[Depends(verify_api_key)])
async def extract_document(...):
    ...
```

### **Rate Limiting:**

```bash
pip install slowapi

from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter

@router.post("/extract")
@limiter.limit("10/minute")
async def extract_document(...):
    ...
```

---

## 📊 Monitoring

### **Check Logs:**

```powershell
# View recent logs
Get-Content logs/app_*.log -Tail 50

# Follow logs
Get-Content logs/app_*.log -Wait
```

### **Health Monitoring:**

```bash
# Simple uptime check
while true; do
  curl -s http://localhost:8000/api/health | jq
  sleep 60
done
```

---

## 🐛 Troubleshooting

### **API won't start:**

```powershell
# Check if port 8000 is in use
netstat -ano | findstr :8000

# Use different port
uvicorn api.main:app --reload --app-dir backend --port 8080
```

### **Import errors:**

```powershell
# Verify paths
python -c "import sys; sys.path.insert(0, 'backend'); import extractor; print('OK')"
```

### **Upload fails:**

- Check file size (max 10MB by default)
- Check file type (PDF, DOCX, images only)
- Check temp directory permissions

---

## 📋 API Response Codes

| Code | Meaning |
|------|---------|
| 200 | Success |
| 400 | Bad Request (invalid file, etc.) |
| 404 | Not Found (extraction_id doesn't exist) |
| 413 | File Too Large |
| 500 | Server Error |

---

**API is ready to use!** 🎉

Visit http://localhost:8000/docs for interactive documentation.
