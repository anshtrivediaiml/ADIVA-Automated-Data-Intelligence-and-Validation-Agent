"""
Test API Endpoints

Simple test to verify API is working.
"""

import requests
import time
from pathlib import Path

# API base URL
BASE_URL = "http://localhost:8000"


def test_health():
    """Test health endpoint"""
    print("\n" + "=" * 70)
    print("Testing Health Check")
    print("=" * 70)
    
    response = requests.get(f"{BASE_URL}/api/health")
    print(f"Status Code: {response.status_code}")
    print(f"Response: {response.json()}")
    assert response.status_code == 200


def test_status():
    """Test status endpoint"""
    print("\n" + "=" * 70)
    print("Testing API Status")
    print("=" * 70)
    
    response = requests.get(f"{BASE_URL}/api/status")
    print(f"Status Code: {response.status_code}")
    print(f"Response: {response.json()}")
    assert response.status_code == 200


def test_extract():
    """Test single document extraction"""
    print("\n" + "=" * 70)
    print("Testing Document Extraction")
    print("=" * 70)
    
    # Use sample file
    sample_file = Path("data/samples/FunctionalSample.pdf")
    
    if not sample_file.exists():
        print(f"Sample file not found: {sample_file}")
        return
    
    with open(sample_file, 'rb') as f:
        files = {'file': ('resume.pdf', f, 'application/pdf')}
        response = requests.post(f"{BASE_URL}/api/extract", files=files)
    
    print(f"Status Code: {response.status_code}")
    
    if response.status_code == 200:
        data = response.json()
        print(f"Extraction ID: {data['extraction_id']}")
        print(f"Document Type: {data['document_type']}")
        print(f"Confidence: {data['confidence']}")
        print(f"Processing Time: {data['processing_time']}s")
        print(f"Files: {data['files']}")
        return data['extraction_id']
    else:
        print(f"Error: {response.text}")


def test_get_results(extraction_id):
    """Test getting results"""
    print("\n" + "=" * 70)
    print(f"Testing Get Results: {extraction_id}")
    print("=" * 70)
    
    response = requests.get(f"{BASE_URL}/api/results/{extraction_id}")
    print(f"Status Code: {response.status_code}")
    
    if response.status_code == 200:
        data = response.json()
        print(f"Status: {data.get('status')}")
        print(f"Document Type: {data.get('classification', {}).get('document_type')}")
        print("Results retrieved successfully!")


def test_download(extraction_id, format='json'):
    """Test file download"""
    print("\n" + "=" * 70)
    print(f"Testing Download: {extraction_id}.{format}")
    print("=" * 70)
    
    response = requests.get(f"{BASE_URL}/api/download/{extraction_id}/{format}")
    print(f"Status Code: {response.status_code}")
    
    if response.status_code == 200:
        print(f"File size: {len(response.content)} bytes")
        print("Download successful!")


def test_list_extractions():
    """Test listing extractions"""
    print("\n" + "=" * 70)
    print("Testing List Extractions")
    print("=" * 70)
    
    response = requests.get(f"{BASE_URL}/api/extractions?page=1&page_size=5")
    print(f"Status Code: {response.status_code}")
    
    if response.status_code == 200:
        data = response.json()
        print(f"Total extractions: {data['total']}")
        print(f"Showing page: {data['page']}")
        print(f"Results: {len(data['extractions'])}")
        
        for item in data['extractions'][:3]:
            print(f"  - {item['extraction_id']}: {item.get('document_type', 'unknown')}")


if __name__ == "__main__":
    print("\n" + "=" * 70)
    print("ADIVA API Test Suite")
    print("=" * 70)
    print("\nMake sure API is running: python backend/api/main.py")
    print("Or: uvicorn api.main:app --reload --app-dir backend")
    print("\nWaiting for API to be ready...")
    
    # Wait for API
    for i in range(10):
        try:
            requests.get(f"{BASE_URL}/api/health", timeout=1)
            print("✓ API is ready!\n")
            break
        except:
            time.sleep(1)
    else:
        print("✗ API not responding. Please start the API first.")
        exit(1)
    
    try:
        # Run tests
        test_health()
        test_status()
        
        extraction_id = test_extract()
        
        if extraction_id:
            time.sleep(1)  # Give it a moment
            test_get_results(extraction_id)
            test_download(extraction_id, 'json')
            test_download(extraction_id, 'csv')
        
        test_list_extractions()
        
        print("\n" + "=" * 70)
        print("✓ All tests passed!")
        print("=" * 70)
    
    except AssertionError as e:
        print(f"\n✗ Test failed: {e}")
    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()
