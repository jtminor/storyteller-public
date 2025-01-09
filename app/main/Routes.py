from flask import render_template
from flask import request, stream_with_context, abort, jsonify, render_template
from flask import current_app as app

import logging
import time

from app.main.Storyteller import Storyteller, Content, Publisher, Agent, AgentStore

# Configure the root logger
logging.basicConfig(
	level=logging.INFO,  # Set the default logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
	format='STORYTELLER3 - %(asctime)s - %(name)s - %(levelname)s - %(message)s' 
)

#get the logger for API route logging
logger = logging.getLogger(__name__) 


@app.route('/')
def home():
	"""Returns the status of the Storyteller application and its version.

	Returns:
		str: A message indicating the application's status and version.
	"""
	# ... (function implementation remains unchanged)

	
	logger.info("GET request received for root route.")

	# Set a default version
	version = "unknown"

	# Attempt to read version.txt, handle any errors
	try:
		with open("version.txt") as f:
			version = f.read().strip()
	except Exception as e:
		logger.error(f"Error reading version.txt: {e}")

	return f"Storyteller ({version}) is live."


@app.route('/<string:doc_id>/test', methods=['GET'])
def test_api(doc_id):
	"""Tests the Storyteller API by updating and retrieving content from a test document.

	Args:
		doc_id (str): The ID of the document to test (use "test2_doc" for testing).

	Query Parameters:
		test_content_id (str, optional): The ID of the content to test with. 
			Defaults to "test.value".

	Returns:
		str: The retrieved content data after the update, confirming API functionality.
	"""
	TEST_FORMAT_NAME = "test.0.0.2"
	try:
		logger.info(f"GET request received for test with document id {doc_id} ")
		if not doc_id:  # Example: Check if doc_id is not empty
			abort(400, description="Missing 'doc_id' parameter")
			logger.warning("Missing 'doc_id' parameter in test request.") 
		this_storyteller = Storyteller(doc_id)

		#format the document as a test doc
		this_storyteller.format.build_format_from_json(TEST_FORMAT_NAME)

	   # --- Test Content Update and Get ---
		test_value = request.args.get('test_content_id')
		if not test_value: test_value = "test.value" 
		test_key = "test.id"
		this_storyteller.update_content_for_id(test_key, test_value)
		stored_value = this_storyteller.get_content_for_id(test_key)
		return stored_value
	
	except Exception as e:
		logger.error(f"An unexpected error occurred: {e}")
		abort(500, description="Internal Server Error")

@app.route("/<string:doc_id>/updatecontent", methods=['POST'])
def update_content(doc_id):
	"""Updates content within the specified Storyteller document.

	Args:
		doc_id (str): The ID of the document to update.

	Request Body (Form Data):
		Key-value pairs where keys are content IDs and values are the corresponding new content data.

	Returns:
		str: "True" if all content updates were successful.

	Raises:
		400 Bad Request: If 'doc_id' is missing or no form data is provided.
		404 Not Found: If a content ID is not found in the document.
	"""
	logger.info(f"POST request received for udatecontent with document id {doc_id} ")
	if not doc_id:  # Example: Check if doc_id is not empty
		abort(400, description="Missing 'doc_id' parameter") 
		logger.warning("Missing 'doc_id' parameter in updateconent request.") 
	this_storyteller = Storyteller(doc_id) 
	form_data = request.form
	if len(form_data.keys()) == 0:
		abort(400,description="No form data.")
		logger.warning("No form data in updatecontent request.")
	for this_content_id in form_data.keys():	
		this_storyteller.update_content_for_id(this_content_id,form_data.get(this_content_id))
		logger.info(f"Content value updated for id {this_content_id}")
	return str(True)

@app.route("/<string:doc_id>/getcontent", methods=['GET'])
def get_content(doc_id):
	"""Retrieves content from the specified Storyteller document.

	Args:
		doc_id (str): The ID of the document.

	Query Parameters:
		content_ids (str, optional): A comma-separated list of content IDs to retrieve. 
			If not provided, all content in the document is returned.

	Returns:
		json: A list of JSON objects, each representing a content item with 'id', 'data', and 'type' fields.

	Raises:
		400 Bad Request: If 'doc_id' is missing or the 'content_ids' parameter is invalid.
		404 Not Found: If any specified content ID is not found.
	"""
	logger.info(f"GET request received for getcontent with document id {doc_id}")
	if not doc_id:
		abort(400, description="Missing 'doc_id' parameter")
		logger.warning("Missing 'doc_id' parameter in getcontent request.")
	try:
		this_storyteller = Storyteller(doc_id)
		content_list = []
		content_ids_string = request.args.get('content_ids')
		if not content_ids_string:
			content_list = this_storyteller.get_contents()
			return jsonify([content.__dict__ for content in content_list])
		else:
			content_ids = content_ids_string.split(',')
			for content_id in content_ids:
				if this_storyteller.format.get_content_type(content_id) == "set":
					content_list.append(Content(content_id, "", "set").__dict__)
				else:
					content_data = this_storyteller.get_content_for_id(content_id)
					if content_data:
						content_type = this_storyteller.format.get_content_type(content_id)
						content_list.append(Content(content_id, content_data, content_type).__dict__)
					else:
						logger.error(f"Content ID not found: {content_id}")
						abort(404, description=f"Content ID not found: {content_id}")
			return jsonify(content_list)

	except (TypeError, ValueError) as e:
		logger.error(f"Error processing getcontent request: {e}")
		abort(400, description=str(e))


@app.route("/<string:doc_id>/generatecontent", methods=['POST'])
def generate_content(doc_id):
	"""Generates content for the specified IDs in the Storyteller document.

	Args:
		doc_id (str): The ID of the document.

	Request Body (JSON):
		A list of content IDs. IDs ending with '*' generate content for the ID and its dependents.
		IDs ending with '^' generate content for the ID and its dependencies.

	Returns:
		str: "True" if all generation requests were successful.

	Raises:
		400 Bad Request: If 'doc_id' is missing or the request body is invalid.
		404 Not Found: If any specified content ID is not found.
	"""
	if not doc_id: 
		abort(400, description="Missing 'doc_id' parameter") 
	this_storyteller = Storyteller(doc_id) 
	needed_content_ids = request.json

	# Check if neededContentIds is a list
	if not isinstance(needed_content_ids, list):
		abort(400, description="Request body must be a JSON list of content IDs.")
		logger.warning("Request body must be a JSON list of content IDs.")

	result_checks = []
	for this_content_id in needed_content_ids:
		if this_content_id.startswith("_"):
			result_checks.append(False)
			continue
		elif this_content_id.endswith("*"):
			this_content_id = this_content_id[:-1]
			if this_storyteller.format.get_content_type(this_content_id):
				result = this_storyteller.generate_content_then_dependents(this_content_id)
				result_checks.append(result)
		elif this_content_id.endswith("^"):
			this_content_id = this_content_id[:-1]
			if this_storyteller.format.get_content_type(this_content_id):
				result = this_storyteller.generate_context_then_content(this_content_id)
				result_checks.append(result)
		elif this_storyteller.format.get_content_type(this_content_id) or this_content_id.startswith("test"):
			result = this_storyteller.generate_content_for_id(this_content_id)
			result_checks.append(result)
		else:
			logger.error(f"Content ID not found: {this_content_id}")
			abort(404, description=f"Content ID not found: {this_content_id}")
	return str(all(result_checks))


@app.route("/<string:doc_id>/getcontentstate", methods=['GET'])
def get_content_state(doc_id):
	"""Retrieves the generation state of a content item.

	Args:
		doc_id (str): The document ID.

	Query Parameters:
		content_id (str): The ID of the content item.

	Returns:
		str: The state of the content, which can be one of the following:
			- "none": The content ID doesn't exist or has no state.
			- "needed": Content generation is needed for this ID.
			- "generating": Content generation is currently in progress.
			- "done": Content generation is complete, and content is available.
			- "locked": The content is locked and cannot be regenerated.
			- "invalid": The content is potentially out of date and needs to be regenerated.

	Raises:
		400 Bad Request: If 'doc_id' or 'content_id' are missing.
		500 Internal Server Error: If an unexpected error occurs during state retrieval.
	"""
	logger.info(f"GET request received for getcontentstate with document id {doc_id}")
	if not doc_id:
		abort(400, description="Missing 'doc_id' parameter")
		logger.warning("Missing 'doc_id' parameter in getcontentstate request.")
	content_id = request.args.get('content_id')
	if not content_id:
		abort(400, description="Missing 'content_id' parameter")
		logger.warning("Missing 'content_id' parameter in getcontentstate request.")

	try:
		content_agent = Agent(doc_id,content_id)
		if content_agent.state:
			content_state = content_agent.state
		else:
			content_state = "none"
		return content_state
	except Exception as e:
		logger.error(f"An error occurred while getting content state: {e}")
		abort(500, description="Internal Server Error")

@app.route("/<string:doc_id>/setcontentstate", methods=['POST'])
def setContentState(doc_id):
	"""Sets the generation state of a content item.

	Args:
		doc_id (str): The document ID.

	Request Body (JSON):
		{
			"content_id": (str) The ID of the content item.
			"state": (str) The new state ("none", "needed", "generating", "done", "locked", "invalid").
		}

	Returns:
		str: A success message.

	Raises:
		400 Bad Request: If 'doc_id', 'content_id', or 'state' are missing or invalid.
		500 Internal Server Error: If an unexpected error occurs during state setting.
	"""
	logger.info(f"POST request received for setContentState with document id {doc_id}")
	if not doc_id:
		abort(400, description="Missing 'doc_id' parameter")
		logger.warning("Missing 'doc_id' parameter in setContentState request.")

	try:
		request_data = request.get_json()
		content_id = request_data.get('content_id')
		new_state = request_data.get('state')

		if not content_id or not new_state:
			abort(400, description="Missing 'content_id' or 'state' in request body.")
			logger.warning("Missing 'content_id' or 'state' in setContentState request body.")

		
		if new_state not in Agent.valid_states:
			abort(400, description=f"Invalid 'state' provided. Valid states are: {', '.join(Agent.valid_states)}")
			logger.warning(f"Invalid 'state' provided in setContentState request: {new_state}")

		content_agent = Agent(doc_id, content_id)
		if content_agent.state:
			content_agent.state = new_state
		content_agent.store()

		Publisher(doc_id).push_content(Content(content_id, new_state, "restate"))

		return f"Content state for '{content_id}' set to '{new_state}' successfully."

	except Exception as e:
		logger.error(f"An error occurred while setting content state: {e}")
		abort(500, description="Internal Server Error")


@app.route("/<string:doc_id>/indexcontent", methods=['GET'])
def get_content_index(doc_id):
	"""Retrieves an index of all content items in the document.

	Args:
		doc_id (str): The document ID.

	Returns:
		A JSON list of content objects ordered by their id, each with:
			- id (str): The content ID.
			- data (str): A short human readable description of the content.
			- type (str): The content type (e.g., "txt", "img").
	Raises:
		400 Bad Request: If 'doc_id' is missing.
		500 Internal Server Error: If an unexpected error occurs during index retrieval.
	"""

	logger.info(f"GET request received for indexcontent with document id {doc_id}")
	if not doc_id:
		abort(400, description="Missing 'doc_id' parameter")
		logger.warning("Missing 'doc_id' parameter in indexcontent request.")

	try:
		this_storyteller = Storyteller(doc_id)
		content_index = this_storyteller.format.get_content_index()
		# Convert Content objects to dictionaries for JSON serialization
		content_index_list = [content.__dict__ for content in content_index]
		content_index_list.sort(key=lambda x: x['id'])
		return jsonify(content_index_list)

	except Exception as e:
		logger.error(f"Error processing indexcontent request: {e}")
		abort(500, description="Internal Server Error")

@app.route("/<string:doc_id>/formatcontent", methods=['POST'])
def setFormat(doc_id):
	"""Applies a format to the Storyteller document. This loads the new format's Agents but, does not overwrite overwrite any existing format.

	Args:
		doc_id (str): The ID of the Storyteller document.

	Request Body (JSON):
		str: The name of the format to apply.

	Returns:
		str: A success message.

	Raises:
		400 Bad Request: If 'doc_id' is missing or the request body is invalid.
	"""
	logger.info(f"POST request received for setFormat with document id {doc_id}")
	if not doc_id:
		abort(400, description="Missing 'doc_id' parameter")
		logger.warning("Missing 'doc_id' parameter in setFormat request.")

	try:
		format_name = request.json

		this_storyteller = Storyteller(doc_id)
		this_storyteller.format.build_format_from_json(format_name)  # Assuming format_name is the format name
		return "Content formatted successfully."

	except Exception as e:
		logger.error(f"Error processing setFormat request: {e}")
		abort(400, description=str(e))

@app.route("/<string:doc_id>/streamcontent",methods=['GET'])
def stream_content(doc_id):
	"""Streams content updates using Server-Sent Events (SSE).

	Args:
		doc_id (str): The ID of the Storyteller document.

	Returns:
		SSE stream: A stream of events with content updates.

	Raises:
		400 Bad Request: If 'doc_id' is missing.
	"""
	def message_generator():
		

		logger.info(f"Event stream intial request made from {doc_id}.")

		while True:
			this_content = None
			if publisher.has_content:
				this_content = publisher.pop_content()
			if not this_content:
				retry_delay = 5000
				wait_message = f"event: WAIT\n"
				wait_message += f"retry: {retry_delay}\n"
				wait_message += f"data: NO CONTENT IN BUFFER\n"
				wait_message += f"id: NONE\n\n"
				yield wait_message
				time.sleep(1)  # sleep for one second to avoid spinning
			else:
				next_message = ""
				event_type = ""
				retry_delay = 300 #the speed in miliseconds to ask for the next content, based on the content type
				match this_content.type:
					case "":
						# ?this shouldn't happen
						event_type = "WAIT"
					case "error":
						event_type = "ERROR"
					case "end":
						event_type = "END"
						break
					case "restate":
						event_type = "RESTATE"
					case "txt":
						event_type = "REPLACE"
					case "loc":
						event_type = "REPLACE"
					case "chunk":
						event_type = "ADD"
						retry_delay = 100
					case "img" | "video" | "audio" | "set":
						event_type = "REPLACE"
					case "new":
						event_type = "NEW"
						retry_delay = 100
					case _:  # Default case if none of the above match
						event_type = "WAIT" 
						# Handle the unexpected type, maybe log an error
						retry_delay = 3000
				clean_data = this_content.data.replace("\n", " ")
				next_message += f"event: {event_type}\n"
				next_message += f"retry: {retry_delay}\n"
				next_message += f"data: {clean_data}\n"
				next_message += f"id: {this_content.id}\n\n"
				logger.info(f"Content Event sent for document {doc_id} with content id {this_content.id} and type {this_content.type}")
				yield next_message		
	
	logger.info(f"GET request received for streamcontent with document id {doc_id} ")
	if not doc_id:  # Example: Check if doc_id is not empty
		abort(400, description="Missing 'doc_id' parameter") 
		logger.warning("Missing 'doc_id' parameter in streamcontent request.") 
	publisher = Publisher(doc_id) 
	if publisher.has_content:
		publisher.push_content(Content("_start","Start the queue.","START"))
	logger.info("Event stream started.")
	return app.response_class(stream_with_context(message_generator()),mimetype='text/event-stream')


@app.route('/<string:doc_id>/inspect', methods=['GET'])
def inspect_document(doc_id):
	"""Renders a document inspector interface for testing and development.

	Args:
		doc_id (str): The document ID.

	Returns:
		html: The rendered inspector interface.

	Raises:
		400 Bad Request: If 'doc_id' is missing.
	"""
	logger.info(f"GET request received for inspector interface with document id {doc_id}")
	if not doc_id:
		abort(400, description="Missing 'doc_id' parameter")
		logger.warning("Missing 'doc_id' parameter in inspector request.")

	storyteller = Storyteller(doc_id)
	format_map = {}
	agent_state_map = {}
	if not storyteller.format.dependents_map:
		storyteller.format.build_edge_links()
		storyteller.format.populate_edge_maps()
	for content_id, agent_data in storyteller.format.document.get().to_dict().get(storyteller.format.formatKey, {}).get('AGENTS', {}).items():
   	# Create a dictionary for each agent
		agent_dict = {
			'content_id': content_id,
			'initial_data': agent_data.get('DATA', ''),  
			'initial_state' : agent_data.get('STATE', ''),
			'prompts': agent_data.get('PROMPTS', []),
			'media_type': agent_data.get('TYPE', ''),
			'description': agent_data.get('DESC', ''),
			
		}
		
		format_map[content_id] = agent_dict

	sorted_agents = sorted(format_map.keys())

	story_map = {k.replace('`', ''): v for k, v in storyteller.story.doc.get().to_dict().get(storyteller.story.story_doc_name, {}).items()}
	sorted_keys = sorted([k for k in story_map.keys() if not k.startswith('_')])
	
	
	for content_key in sorted_agents:
		content_agent = Agent(doc_id, content_key)
		if content_agent.state:
			agent_state_map[content_key] = content_agent.state
		else:
			agent_state_map[content_key] = format_map[content_key]['initial_state']

	return render_template('inspector.html', 
						story_id=storyteller.story_id,
						sorted_agents=sorted_agents,
						format_map=format_map,
						agent_state_map=agent_state_map,
						graph_dependents_map=storyteller.format.dependents_map, 
						graph_depends_on_map=storyteller.format.depends_on_map,
						story_map=story_map,
						sorted_keys=sorted_keys)

@app.route('/<string:doc_id>/visualize', methods=['GET'])
def visualize_graph(doc_id):
	"""Renders a graph visualization of content dependencies.

	Args:
		doc_id (str): The document ID.

	Returns:
		html: The rendered graph visualization.

	Raises:
		400 Bad Request: If 'doc_id' is missing.
	"""
	logger.info(f"GET request received for studio interface with document id {doc_id}")
	if not doc_id:
		abort(400, description="Missing 'doc_id' parameter")
		logger.warning("Missing 'doc_id' parameter in studio request.")
	storyteller = Storyteller(doc_id)
	content_index = storyteller.format.get_content_index()
	content_ids = [content.id for content in content_index]

	if not storyteller.format.dependents_map:
		storyteller.format.build_edge_links()
		storyteller.format.populate_edge_maps()

	content_objects = storyteller.story.get_all_content()
	content_map = {}
	for content_item in content_objects:
		if content_item.id.startswith("_"):
			continue
		elif content_item.data.startswith("http"):
			content_map[content_item.id] = content_item.data
	# Add all keys from dependents_map and depends_on_map to content_ids as a backwards compability hack
	content_ids.extend(storyteller.format.dependents_map.keys())
	content_ids.extend(storyteller.format.depends_on_map.keys())
	# Dedupe the list
	content_ids = list(set(content_ids))


	return render_template('visualizer.html', doc_id=doc_id, content_map=content_map,node_list=content_ids, graph_dependents_map=storyteller.format.dependents_map, graph_depends_on_map=storyteller.format.depends_on_map)


@app.route("/<string:doc_id>/delete", methods=['DELETE'])
def delete_document(doc_id):
	"""Deletes the specified Storyteller document and associated data.

	Args:
		doc_id (str): The ID of the document to delete.

	Returns:
		str: A success message if the document was deleted successfully.

	Raises:
		400 Bad Request: If 'doc_id' is missing.
		404 Not Found: If the document does not exist.
		500 Internal Server Error: If an unexpected error occurs during deletion.
	"""

	logger.info(f"DELETE request received for delete_document with document id {doc_id}")
	if not doc_id:
		abort(400, description="Missing 'doc_id' parameter")
		logger.warning("Missing 'doc_id' parameter in delete_document request.")

	try:
		storyteller = Storyteller(doc_id)
		if not storyteller.story.exists():  # Use the Story's exists() method
			abort(404, description=f"Document '{doc_id}' not found.")
			logger.warning(f"Document '{doc_id}' not found for deletion.")
		storyteller.story.delete()  # Call the Story's delete method
		storyteller.format.delete() # Call the Format's delete method
		storyteller.publisher.clear_queue()  # Clear the publishing queue
		AgentStore.delete_agents(doc_id)  # Use a class method to delete all stored Agents

		return f"Document '{doc_id}' deleted successfully."

	except Exception as e:
		logger.error(f"Error deleting document '{doc_id}': {e}")
		abort(500, description=f"Error deleting document: {e}")
