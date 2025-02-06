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

#1
def test_formatcontent(test_client):
    """ Tests /formatcontent """
    response = test_client.post(f"/{TEST_DOC_ID}/formatcontent", json=TEST_FORMAT_NAME)
    print(f"Tests running on document {TEST_DOC_ID} with format {TEST_FORMAT_NAME}")
    assert response.status_code == 200, f"formatcontent failed with: {response.data}"

#2
def test_indexcontent(test_client):
    """ Tests /indexcontent """
    response = test_client.get(f"/{TEST_DOC_ID}/indexcontent")
    assert response.status_code == 200 and len(response.json) > 0 , f"indexcontent failed with: {response.data}"

#3
def test_generatecontent_initial(test_client):
    """ Tests initial /generatecontent for 'test' """
    response = test_client.post(f"/{TEST_DOC_ID}/generatecontent", json=["test"])
    assert response.status_code == 200 and response.data == b"True", f"generatecontent for 'test' failed with: {response.data}"

#4
def test_updatecontent(test_client):
    """ Tests /updatecontent """
    response = test_client.post(f"/{TEST_DOC_ID}/updatecontent", data={"test.id": "storyteller"})
    assert response.status_code == 200 and response.data == b"True", f"updatecontent failed with: {response.data}"

#5
def test_getcontent(test_client):
    """ Tests /getcontent """
    response = test_client.get(f"/{TEST_DOC_ID}/getcontent?content_ids=test.id")
    assert response.status_code == 200 and response.json[0]['data'] == "storyteller", f"getcontent failed with: {response.data}"

#6
def test_getcontentstate_locked(test_client):
    """ Tests /getcontentstate for locked content """
    response = test_client.get(f"/{TEST_DOC_ID}/getcontentstate?content_id=test.id")
    assert response.status_code == 200 and response.data == b"locked", f"getcontentstate for locked content failed: {response.data}"

#7
def test_setcontentstate(test_client):
    """ Tests /setcontentstate """
    response = test_client.post(f"/{TEST_DOC_ID}/setcontentstate", json={"content_id": "test.id", "state": "needed"})
    assert response.status_code == 200, f"setcontentstate failed with: {response.data}"

#8
def test_getcontentstate_invalid(test_client):
    """ Tests /getcontentstate for dependent, invalid content """
    response = test_client.get(f"/{TEST_DOC_ID}/getcontentstate?content_id=test")
    assert response.status_code == 200 and response.data == b"invalid", f"getcontentstate for dependent content failed: {response.data}"

#9
def test_generatecontent_image(test_client):
    """ Tests /generatecontent for 'test.image^' """
    response = test_client.post(f"/{TEST_DOC_ID}/generatecontent", json=["test.image^"])
    assert response.status_code == 200 and response.data == b"True", f"generatecontent for 'test.image^' failed with: {response.data}"

#10
def test_getcontent_changed(test_client):
    """ Tests /getcontent for changed content """
    response = test_client.get(f"/{TEST_DOC_ID}/getcontent?content_ids=test.id")
    assert response.status_code == 200 and response.json[0]['data'] != "storyteller", f"getcontent failed: {response.data}"

#11
location_change_check = ""
def test_generatecontent_id_star(test_client):
	""" Tests /getcontent for 'test.location' to store it prior to changes."""
	response = test_client.get(f"/{TEST_DOC_ID}/getcontent?content_ids=test.location")
	assert response.status_code == 200
	location_change_check = response.json[0]['data']

#12
def test_generatecontent_id_star(test_client):
	""" Tests /generatecontent for 'test.id*' """
	response = test_client.post(f"/{TEST_DOC_ID}/generatecontent", json=["test.id*"])
	assert response.status_code == 200 and response.data == b"True", f"generatecontent for 'test.id*' failed with: {response.data}"

#13
def test_dependents_changed(test_client):
	response = test_client.get(f"/{TEST_DOC_ID}/getcontent?content_ids=test.location")
	assert response.status_code == 200 and response.json[0]['data'] != location_change_check, f"getcontent after dependent generation failed: {response.data}"

#14
def test_getcontentstate_done(test_client):
    """ Tests /getcontentstate for 'done' content """
    response = test_client.get(f"/{TEST_DOC_ID}/getcontentstate?content_id=test.location")
    assert response.status_code == 200 and response.data == b"done", f"getcontentstate failed: {response.data}"

#15
def test_getcontent(test_client):
	""" Tests /getcontent for video complex format."""
	response = test_client.get(f"/{TEST_DOC_ID}/getcontent?content_ids=test.video")
	assert response.status_code == 200, f"getcontent failed: {response.data}"
	print(f"Video created for document {TEST_DOC_ID}: {response.data}")
    