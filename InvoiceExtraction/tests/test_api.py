"""
Test cases for Invoice OCR API endpoints
"""

import pytest
import json
import os
import io
from unittest.mock import patch, MagicMock
from flask import Flask

from app import create_app
from config import TestingConfig


@pytest.fixture
def app():
    """Create test application."""
    app = create_app()
    app.config.from_object(TestingConfig)
    return app


@pytest.fixture
def client(app):
    """Create test client."""
    return app.test_client()


@pytest.fixture
def auth_headers(client):
    """Get authentication headers for testing."""
    # Mock authentication for testing
    with patch('blueprints.api_v1.get_redis_client') as mock_redis:
        mock_redis.return_value.hgetall.return_value = {
            'user_id': 'test_user',
            'status': 'completed'
        }
        mock_redis.return_value.get.return_value = json.dumps({
            'detected_texts': ['Test invoice text'],
            'all_text': 'Test invoice text',
            'processing_time': 1.0,
            'pages_processed': 1
        })
        
        response = client.post('/api/v1/auth/token', 
                             json={'api_key': 'test-api-key'})
        
        if response.status_code == 200:
            token = response.json['data']['access_token']
            return {'Authorization': f'Bearer {token}'}
        else:
            # Fallback for testing without proper auth setup
            return {'Authorization': 'Bearer test-token'}


class TestHealthEndpoint:
    """Test health check endpoint."""
    
    def test_health_check(self, client):
        """Test health check endpoint."""
        response = client.get('/api/v1/health')
        assert response.status_code == 200
        
        data = response.json
        assert data['success'] is True
        assert 'data' in data
        assert 'status' in data['data']


class TestAuthentication:
    """Test authentication endpoints."""
    
    def test_auth_token_success(self, client):
        """Test successful authentication."""
        with patch('auth.os.environ.get') as mock_env:
            mock_env.return_value = 'test-api-key'
            
            response = client.post('/api/v1/auth/token', 
                                 json={'api_key': 'test-api-key'})
            
            assert response.status_code == 200
            data = response.json
            assert data['success'] is True
            assert 'access_token' in data['data']
            assert 'refresh_token' in data['data']
    
    def test_auth_token_invalid_key(self, client):
        """Test authentication with invalid API key."""
        with patch('auth.os.environ.get') as mock_env:
            mock_env.return_value = 'valid-api-key'
            
            response = client.post('/api/v1/auth/token', 
                                 json={'api_key': 'invalid-key'})
            
            assert response.status_code == 401
            data = response.json
            assert data['success'] is False
            assert 'Invalid API key' in data['message']


class TestOCREndpoints:
    """Test OCR processing endpoints."""
    
    def test_ocr_process_no_file(self, client, auth_headers):
        """Test OCR processing without file."""
        response = client.post('/api/v1/ocr/process', headers=auth_headers)
        assert response.status_code == 400
        data = response.json
        assert data['success'] is False
        assert 'No file provided' in data['message']
    
    def test_ocr_process_invalid_file_type(self, client, auth_headers):
        """Test OCR processing with invalid file type."""
        data = {'file': (io.BytesIO(b'test content'), 'test.txt')}
        
        response = client.post('/api/v1/ocr/process', 
                             headers=auth_headers,
                             data=data,
                             content_type='multipart/form-data')
        
        assert response.status_code == 400
        data = response.json
        assert data['success'] is False
        assert 'Unsupported file type' in data['message']
    
    @patch('blueprints.api_v1.process_ocr')
    def test_ocr_process_success(self, mock_process_ocr, client, auth_headers):
        """Test successful OCR processing."""
        mock_process_ocr.return_value = ['Test OCR text']
        
        data = {'file': (io.BytesIO(b'test content'), 'test.pdf')}
        
        with patch('blueprints.api_v1.get_redis_client') as mock_redis:
            mock_redis.return_value.hset.return_value = True
            
            response = client.post('/api/v1/ocr/process', 
                                 headers=auth_headers,
                                 data=data,
                                 content_type='multipart/form-data')
            
            assert response.status_code == 202
            data = response.json
            assert data['success'] is True
            assert 'task_id' in data['data']
            assert data['data']['status'] == 'processing'
    
    def test_ocr_status_not_found(self, client, auth_headers):
        """Test OCR status for non-existent task."""
        with patch('blueprints.api_v1.get_redis_client') as mock_redis:
            mock_redis.return_value.hgetall.return_value = {}
            
            response = client.get('/api/v1/ocr/status/non-existent-task', 
                                headers=auth_headers)
            
            assert response.status_code == 404
            data = response.json
            assert data['success'] is False
            assert 'Task not found' in data['message']
    
    def test_ocr_status_success(self, client, auth_headers):
        """Test successful OCR status retrieval."""
        with patch('blueprints.api_v1.get_redis_client') as mock_redis:
            mock_redis.return_value.hgetall.return_value = {
                'task_id': 'test-task',
                'status': 'completed',
                'user_id': 'test_user'
            }
            
            response = client.get('/api/v1/ocr/status/test-task', 
                                headers=auth_headers)
            
            assert response.status_code == 200
            data = response.json
            assert data['success'] is True
            assert data['data']['status'] == 'completed'


class TestInvoiceExtraction:
    """Test invoice extraction endpoints."""
    
    def test_invoice_extract_invalid_task_id(self, client, auth_headers):
        """Test invoice extraction with invalid task ID."""
        response = client.post('/api/v1/invoice/extract', 
                             headers=auth_headers,
                             json={'task_id': 'invalid-task'})
        
        assert response.status_code == 404
        data = response.json
        assert data['success'] is False
        assert 'Task not found' in data['message']
    
    @patch('blueprints.api_v1.extract_structured_from_text')
    def test_invoice_extract_success(self, mock_extract, client, auth_headers):
        """Test successful invoice extraction."""
        mock_extract.return_value = {
            'invoice_number': '12345',
            'invoice_date': '2024-01-15',
            'vendor_name': 'Test Company',
            'customer_name': 'Test Customer',
            'total_amount': '$100.00',
            'tax_amount': '$10.00'
        }
        
        with patch('blueprints.api_v1.get_redis_client') as mock_redis:
            mock_redis.return_value.hgetall.return_value = {
                'task_id': 'test-task',
                'status': 'completed',
                'user_id': 'test_user'
            }
            mock_redis.return_value.get.return_value = json.dumps({
                'detected_texts': ['Test invoice text'],
                'all_text': 'Test invoice text'
            })
            
            response = client.post('/api/v1/invoice/extract', 
                                 headers=auth_headers,
                                 json={'task_id': 'test-task'})
            
            assert response.status_code == 200
            data = response.json
            assert data['success'] is True
            assert 'invoice_data' in data['data']
            assert len(data['data']['invoice_data']) == 1


class TestTaskManagement:
    """Test task management endpoints."""
    
    def test_list_tasks_success(self, client, auth_headers):
        """Test successful task listing."""
        with patch('blueprints.api_v1.get_redis_client') as mock_redis:
            mock_redis.return_value.keys.return_value = ['task:test-task']
            mock_redis.return_value.hgetall.return_value = {
                'task_id': 'test-task',
                'status': 'completed',
                'filename': 'test.pdf',
                'created_at': '2024-01-15T10:30:00Z',
                'language': 'en',
                'user_id': 'test_user'
            }
            
            response = client.get('/api/v1/tasks', headers=auth_headers)
            
            assert response.status_code == 200
            data = response.json
            assert data['success'] is True
            assert 'data' in data
            assert 'pagination' in data
    
    def test_delete_task_success(self, client, auth_headers):
        """Test successful task deletion."""
        with patch('blueprints.api_v1.get_redis_client') as mock_redis:
            mock_redis.return_value.hgetall.return_value = {
                'task_id': 'test-task',
                'user_id': 'test_user',
                'filename': 'test.pdf'
            }
            mock_redis.return_value.delete.return_value = True
            
            with patch('os.path.exists', return_value=True):
                with patch('os.remove') as mock_remove:
                    response = client.delete('/api/v1/tasks/test-task', 
                                           headers=auth_headers)
                    
                    assert response.status_code == 200
                    data = response.json
                    assert data['success'] is True
                    assert 'deleted successfully' in data['message']


class TestErrorHandling:
    """Test error handling."""
    
    def test_404_error(self, client):
        """Test 404 error handling."""
        response = client.get('/api/v1/non-existent-endpoint')
        assert response.status_code == 404
    
    def test_401_error(self, client):
        """Test 401 error handling."""
        response = client.get('/api/v1/ocr/process')
        assert response.status_code == 401
    
    def test_500_error(self, client, auth_headers):
        """Test 500 error handling."""
        with patch('blueprints.api_v1.get_redis_client') as mock_redis:
            mock_redis.side_effect = Exception('Redis connection failed')
            
            response = client.get('/api/v1/health')
            assert response.status_code == 500


if __name__ == '__main__':
    pytest.main([__file__])
