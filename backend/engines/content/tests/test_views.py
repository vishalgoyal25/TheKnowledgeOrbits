"""
Content Engine - View Tests

Tests for Document, Chunk, Embedding viewsets.
"""

import pytest
from unittest.mock import patch, MagicMock
from rest_framework.test import APIClient
from rest_framework import status
from django.core.files.uploadedfile import SimpleUploadedFile
from engines.content.models import Document, Chunk
from engines.auth.models import User, Role, RoleAssignment


@pytest.fixture
def api_client():
    """API client fixture."""
    return APIClient()


@pytest.fixture
def admin_user():
    """Create admin user."""
    user = User.objects.create_user(email='admin@test.com', password='pass')
    user.is_verified = True
    user.save()
    role, _ = Role.objects.get_or_create(name='admin')
    RoleAssignment.objects.create(user=user, role=role)
    return user


@pytest.fixture
def authenticated_admin(api_client, admin_user):
    """Authenticated admin client."""
    api_client.force_authenticate(user=admin_user)
    return api_client, admin_user


@pytest.mark.django_db
class TestDocumentViewSet:
    """Test Document viewset."""
    
    def test_list_documents(self, authenticated_admin):
        """Test listing documents."""
        client, user = authenticated_admin
        
        Document.objects.create(
            title='Doc 1',
            file_path='/test1.pdf',
            source_type='static'
        )
        Document.objects.create(
            title='Doc 2',
            file_path='/test2.pdf',
            source_type='static'
        )
        
        response = client.get('/api/v1/content/documents/')
        
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data['results']) == 2
    
    def test_filter_by_source_type(self, authenticated_admin):
        """Test filtering documents by source_type."""
        client, user = authenticated_admin
        
        Document.objects.create(
            title='Static Doc',
            file_path='/static.pdf',
            source_type='static'
        )
        Document.objects.create(
            title='Dynamic Doc',
            file_path='/dynamic.pdf',
            source_type='dynamic'
        )
        
        response = client.get('/api/v1/content/documents/?source_type=static')
        
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data['results']) == 1
        assert response.data['results'][0]['source_type'] == 'static'
    
    @patch('engines.content.services.ingestion_service.IngestionService.ingest_document')
    def test_upload_document(self, mock_ingest, authenticated_admin):
        """Test document upload."""
        client, user = authenticated_admin
        
        mock_ingest.return_value = {
            'document_id': 'test-doc-id',
            'chunks_created': 10,
            'status': 'completed'
        }
        
        pdf_file = SimpleUploadedFile(
            "test.pdf",
            b"PDF content here",
            content_type="application/pdf"
        )
        
        data = {
            'file': pdf_file,
            'title': 'Test Upload',
            'source_type': 'static'
        }
        
        response = client.post(
            '/api/v1/content/documents/upload/',
            data,
            format='multipart'
        )
        
        assert response.status_code == status.HTTP_201_CREATED
        assert 'document_id' in response.data


@pytest.mark.django_db
class TestChunkViewSet:
    """Test Chunk viewset."""
    
    def test_list_chunks(self, authenticated_admin):
        """Test listing chunks."""
        client, user = authenticated_admin
        
        doc = Document.objects.create(
            title='Test Doc',
            file_path='/test.pdf',
            source_type='static'
        )
        
        Chunk.objects.create(
            chunk_text='Chunk 1',
            chunk_index=0,
            source_type='static',
            document=doc
        )
        Chunk.objects.create(
            chunk_text='Chunk 2',
            chunk_index=1,
            source_type='static',
            document=doc
        )
        
        response = client.get('/api/v1/content/chunks/')
        
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data['results']) == 2
    
    def test_filter_chunks_by_document(self, authenticated_admin):
        """Test filtering chunks by document."""
        client, user = authenticated_admin
        
        doc1 = Document.objects.create(
            title='Doc 1',
            file_path='/doc1.pdf',
            source_type='static'
        )
        doc2 = Document.objects.create(
            title='Doc 2',
            file_path='/doc2.pdf',
            source_type='static'
        )
        
        Chunk.objects.create(
            chunk_text='Chunk from doc1',
            chunk_index=0,
            source_type='static',
            document=doc1
        )
        Chunk.objects.create(
            chunk_text='Chunk from doc2',
            chunk_index=0,
            source_type='static',
            document=doc2
        )
        
        response = client.get(f'/api/v1/content/chunks/?document_id={doc1.id}')
        
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data['results']) == 1
