""" Test the routes of the application """
# pylint: disable=redefined-outer-name, wrong-import-position, import-error

import os
import sys
import json
import pytest
import secrets

# Adjust the import to correctly locate the app module
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from app import create_app

# Define a test document ID
TEST_DOC_ID = secrets.token_urlsafe(16)
TEST_FORMAT_NAME = "test"



@pytest.fixture
def test_client():
	""" Create a test client for the application """
	with create_app().test_client() as client:
		yield client

def test_home_page(test_client):
	""" Test the home page route """
	response = test_client.get('/')
	assert response.status_code == 200
	version = "unknown"

	# Attempt to read version.txt, handle any errors
	version_file = os.path.join("..","..","version.txt")
	if os.path.exists(version_file):
		with open(version_file) as f:
			version = f.read().strip()

	assert response.data.decode('utf-8') == f"Storyteller ({version}) is live."

def test_fomatcontent(test_client):
	""" Test formatting content """
	format_name = TEST_FORMAT_NAME
	response = test_client.post(f'/{TEST_DOC_ID}/formatcontent', json=format_name)
	assert response.status_code == 200
	assert response.data.decode('utf-8') == "Content formatted successfully."

def test_testapi(test_client):
	""" Test the test API route """
	test_value = "test_replaced_value"
	response = test_client.get(f'/{TEST_DOC_ID}/test', query_string={'test_content_id': test_value})
	assert response.status_code == 200
	assert response.data.decode('utf-8') == test_value

def test_updatecontent(test_client):
	""" Test updating content """
	test_content_id = "test.id"
	test_content_data = "updated_value"
	response = test_client.post(f'/{TEST_DOC_ID}/updatecontent', data={test_content_id: test_content_data})
	assert response.status_code == 200
	assert response.data.decode('utf-8') == "True"

def test_getcontent(test_client):
	""" Test retrieving content """
	test_content_id = "test.id"
	response = test_client.get(f'/{TEST_DOC_ID}/getcontent?content_ids={test_content_id}')
	assert response.status_code == 200
	data = json.loads(response.data.decode('utf-8'))
	assert isinstance(data, list)
	assert len(data) > 0

def test_generatecontent(test_client):
	""" Test generating content """
	test_content_ids = ["test.id"]
	response = test_client.post(f'/{TEST_DOC_ID}/generatecontent', json=test_content_ids)
	assert response.status_code == 200
	assert response.data.decode('utf-8') == "True"

def test_indexcontent(test_client):
	test_doc_id = "test_doc_id"  # Replace with a valid doc_id
	response = test_client.get(f"/{test_doc_id}/indexcontent")

	assert response.status_code == 200
	assert response.content_type == "application/json"

	content_index = json.loads(response.data)
	assert isinstance(content_index, list)
	
	# Add assertions to check for 'data' field
	for content_item in content_index:
		assert "id" in content_item
		assert "data" in content_item  # Check if 'data' field exists
		assert "type" in content_item

def test_getcontentstate(test_client):
	""" Test retrieving content state """
	test_content_id = "test.id"
	response = test_client.get(f'/{TEST_DOC_ID}/getcontentstate', query_string={'content_id': test_content_id})
	assert response.status_code == 200
	assert response.data.decode('utf-8') in ["none", "needed", "queued", "generating", "done", "locked", "invalid"]

def test_setcontentstate(test_client):
	""" Test setting content state """
	test_content_id = "test.id"
	test_state = "needed"
	response = test_client.post(f'/{TEST_DOC_ID}/setcontentstate', json={'content_id': test_content_id, 'state': test_state})
	assert response.status_code == 200
	assert response.data.decode('utf-8') == f"Content state for '{test_content_id}' set to '{test_state}' successfully."


def test_streamcontent(test_client):
	""" Test streaming content (check for successful connection) """
	response = test_client.get(f'/{TEST_DOC_ID}/streamcontent', headers={'Accept': 'text/event-stream'})
	assert response.status_code == 200
	assert response.headers['Content-Type'] == 'text/event-stream; charset=utf-8'

def test_delete_document(test_client):
	""" Test deleting a document """
	response = test_client.delete(f'/{TEST_DOC_ID}/delete')
	assert response.status_code == 200
	assert response.data.decode('utf-8') == f"Document '{TEST_DOC_ID}' deleted successfully."
