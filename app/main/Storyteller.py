import time
import secrets
import logging
import re
import pickle
import json
import base64
import os
import requests

from datetime import datetime
from collections import deque

from google.cloud import firestore, storage
from google.api_core.exceptions import GoogleAPIError, DeadlineExceeded
from google.cloud.exceptions import NotFound
from google.cloud import texttospeech

import vertexai
from vertexai.preview.vision_models import ImageGenerationModel
from vertexai.language_models import TextGenerationModel
from vertexai.generative_models import GenerativeModel, Part, SafetySetting
from vertexai.preview.vision_models import ImageGenerationResponse


from openai import OpenAI
from openai import OpenAIError

from .VideoComposer import VideoComposer
import traceback
from .LoggerManager import LoggerManager

#Google Cloud Storage Info
GC_PROJECT_ID = "storyteller3"
STORY_COLLECTION_NAME = "dotes"
QUEUE_COLLECTION_NAME = "queue"

GCS_MEDIA_BUCKET_NAME = "storyteller-media"
GCS_AGENT_BUCKET_NAME = "storyteller-agent-store"

#AI MODEL CONFIG
DEFAULT_TEXT_MODEL_CONFIG_NAME = "google-text-basic"
DEFAULT_IMAGE_MODEL_CONFIG_NAME = "google-image-basic"
DEFAULT_SPEECH_MODEL_CONFIG_NAME = "google-speech-basic"

#Document Defaults
DEFAULT_FORMAT_NAME = ""
STORY_SUBDOCUMENT_KEY = "dote_story"

logger = logging.getLogger(__name__)  
logger.setLevel(logging.INFO)

# Step 2: Configure loggers
LoggerManager.setup_loggers()  # This applies your preferred log levels

class StorageClient:
    _client = None

    @staticmethod
    def get_client():
        if not StorageClient._client:
            StorageClient._client = storage.Client(project=GC_PROJECT_ID)
        return StorageClient._client

class FirestoreClient:
    _client = None

    @classmethod
    def get_client(cls, project=None):
        # Check if the environment is development
        if os.getenv('FLASK_ENV') == 'development':
            # Connect to the emulator
            os.environ["FIRESTORE_EMULATOR_HOST"] = "localhost:4000"  # Adjust port if needed
            # Create the client, which will automatically connect to the emulator
            if cls._client is None:
                cls._client = firestore.Client()  # No need to pass a project for emulator
        else:
            # Connect to Firestore in production (or other environments)
            if cls._client is None:
                if project:
                    cls._client = firestore.Client(project=project)
                else:
                    cls._client = firestore.Client()  # Default client without specifying a project
        return cls._client

class Storyteller:
	"""
	Manages content generation and storage for a Story document.

	Attributes:
		story_id (str): The ID of the active Story document.
		story (Story): The Story object representing the document.
		publisher (Publisher): Publishes content updates.
		format (Format): Defines the document's structure.
	"""
	def __init__(self,story_id):
		self.story_id = story_id
		self.story = Story(story_id)
		self.publisher = Publisher(story_id)
		if DEFAULT_FORMAT_NAME:
			self.format = Format(story_id, DEFAULT_FORMAT_NAME)
		else:
			self.format = Format(story_id)

	def get_content_for_id(self,content_id):
		"""
		Retrieves content for the specified content ID.

		Args:
			content_id (str): The ID of the content to retrieve.

		Returns:
			str: The data associated with the content ID or None if the ID is not found.
		"""
		logger.debug(f"Getting content for id {content_id}")
		content_data= self.story.get_content(content_id)
		if content_data:
			return content_data
		else:
			logger.warning(f"No content found for id {content_id}")
			return None

	def get_contents(self):
		"""
		Retrieves all content items from the Story.

		Returns:
			list: List of Content objects with ID, data, and type.
		"""
		logger.info("Getting all contents in the story document.")
		content_list = self.story.get_all_content()
		for content_item in content_list:
			if not content_item.id.startswith("_"):
				content_item.type = self.format.get_content_type(content_item.id)
			else:
				content_item.type = "sys"
		return content_list

	def generate_content_for_id(self, content_id):
		"""
		Generates content for a given ID, handling dependencies and agent states.
		
		Args:
			content_id (str): The ID of the content to generate.
		
		Returns:
			bool or None: True if generation successful, False if failed, None if no generation attempted.
				Publishes content updates and error messages via the Publisher.
		"""

		try:
			# 1. Check if the content ID is in the format
			if not self.format.get_content_type(content_id):
				error_message = f"Invalid content ID: '{content_id}' not found in format."
				logger.error(error_message)
				self.publisher.push_content(Content(content_id, error_message, "error"))
				return None

			# 2. Log the generation request
			logger.info(f"Generate request received for content ID: {content_id}")

			# 3. Get or create the Agent for this content
			# Check if the agent is already stored in GCS
			agent = Agent(self.story_id, content_id)
			if not agent.type:
				# If agent is not loaded, build it from the format and store it in the store
				agent = self.build_agent_for_id(content_id)
				if not agent:
					#This means an agent defition wasn't found in the Format, so we can't build this content
					error_message = f"Invalid content ID: '{content_id}' not found in format."
					logger.error(error_message)
					self.publisher.push_content(Content(content_id, error_message, "error"))
					return None
				else:
					agent.store()
					logger.info(f"Existing Agent for '{content_id}' was found in Agent Store. Created new Agent from Format.")

			# 4. Handle "set" type agents
			if agent.type == "set":
				set_success = []
				self.publisher.push_content(Content(content_id, "generating", "restate"))
				agent.state = "generating"
				agent.store()
				for sub_item in agent.prompts:
					sub_item = sub_item.replace("§", "")
					success_check = self.generate_content_for_id(sub_item)  # Recursive call for each value
					set_success.append(success_check)
				if all(set_success):
					agent.state = "done"
					agent.store()
					self.publisher.push_content(Content(content_id, "done", "restate"))
					return True
				else:
					agent.state = "invalid"
					agent.store()
					self.publisher.push_content(Content(content_id, "invalid", "restate"))
					return False      

			# 5. Check existing states and handle states which cannot transition to "generating"
			#Already generating
			if agent.state == "generating":
				logger.info(f"Content for '{content_id}' is already generating.")
				return None
			#Get the current content
			current_content = self.get_content_for_id(content_id)			
			#Content is locked
			if agent.state == "locked":
				# Publish the existing content and return
				logger.info(f"Content for '{content_id}' is locked. Republishing existing content.")
				self.publisher.push_content(Content(content_id, current_content, agent.type))
				return True
			#special handling for agents who "copy" their data from another agent
			if agent.data == "copy":
				copied_data = None
				copy_target = None
				try:
					#copy items use their first prompt string to store a reference to the item they should copy
					copy_target = re.findall(r'§(.*?)§', agent.prompts[0])[0]
					logger.info(f"Data being copied from: {copy_target}")
					if copy_target:
						copied_data = self.get_content_for_id(copy_target)
				except Exception as e:
					logger.error(f"Could not copy data from: {agent.content_id} due to exception {e}")
					self.publisher.push_content(Content(content_id, "Content could not be copied.", agent.type))
					return False
				#if there's no content to be copied, try to generate it.
				if not copied_data and copy_target:
					gen_response = self.generate_content_for_id(copy_target)
					if gen_response: copied_data = self.get_content_for_id(copy_target)
				#ok, there's data, so copy it
				if copied_data:
					self.story.update_content(content_id, copied_data)
					self.publisher.push_content(Content(content_id, copied_data, agent.type))
					logger.info(f"Content data from {agent.data} copied to new content id: {agent.content_id}.")
					return True
				else:
					logger.error(f"Could not copy empty content from: {copy_target} into new agent: {agent.content_id}")
					self.publisher.push_content(Content(content_id, "Content could not be copied.", "error"))
					return False
			### At first creation time, the agent data should be used to populate the content if state is done
			if not current_content and agent.state == "done":
					self.story.update_content(content_id, agent.data)
					self.publisher.push_content(Content(content_id, agent.data, agent.type))
					logger.info(f"Content for '{content_id}' marked in format as 'done'. Using Agent's default content.")
					return True

			# 6. Convert prompts and memories to Message objects
			resolved_prompts = []
			if agent.prompts:
				#resolve prompt variables
				for prompt in agent.prompts:
					resolved_prompts.extend(self._resolve_content_variables(prompt)) 
	
			prompt_messages = [Message(prompt) for prompt in resolved_prompts]
			memory_messages = [Message(memory) for memory in agent.memories]

			# 7. Combine all messages into a single message list and that into a single string
			all_messages = prompt_messages + memory_messages
			full_text_prompt = " ".join([message.text for message in all_messages])
			if full_text_prompt == "": full_text_prompt = "Storyteller"

			# 8. Load the model configuration if specified, otherwise use the default
			if agent.model: model_config_name = agent.model
			else:

				if agent.type == "txt": model_config_name = DEFAULT_TEXT_MODEL_CONFIG_NAME
				elif agent.type == "img": model_config_name = DEFAULT_IMAGE_MODEL_CONFIG_NAME
				elif agent.type == "audio": model_config_name = DEFAULT_SPEECH_MODEL_CONFIG_NAME
				else: model_config_name = DEFAULT_TEXT_MODEL_CONFIG_NAME



			model_config = ModelConfig(model_config_name)
			if agent.system: model_config.system += agent.system


			# 9. Set the agent State to generating and Publish the change, don't store this change as this state should always complete in a single call or revert to the existing value if it can't be resolved to an invalid or done state in time
			agent.state = "generating"
			self.publisher.push_content(Content(content_id, "generating", "restate"))

			# 10. Special video handling (for now) or create a ModelInterface and use it to generate a response for other media
			if agent.type == "video":
				return self._generate_video_content(content_id)

			generator_model = ModelInterface(model_config)


			
			content_response = generator_model.generate(full_text_prompt, agent.type)
			if content_response:
				self.story.update_content(content_id, content_response)
				logger.info(f"New value stored for {content_id}: {content_response}")
				self.publisher.push_content(Content(content_id, content_response, agent.type))
				agent.state = "done"
				self.publisher.push_content(Content(content_id, "done", "restate"))
				agent.store()
				return True
			else:
				agent.state = "invalid"
				self.publisher.push_content(Content(content_id, "invalid", "restate"))
				self.publisher.push_content(Content(content_id, f"Error generating content: {content_id} using model config: {model_config_name}", "error"))
				agent.store()
				return False
		except Exception as e:

			tb = traceback.extract_tb(e.__traceback__)
			last_trace = tb[-1]  # Get the last traceback entry
			file_name = last_trace.filename  # Get the filename where the exception occurred
			line_number = last_trace.lineno  # Get the line number of the exception
			function_name = last_trace.name  # Get the function name where the exception occurred

			logger.error(f"Error in {function_name} in {file_name} (line {line_number}): {e}")
			self.publisher.push_content(Content(content_id, f"Error generating content: {e}", "error"))

			return False

	def update_content_for_id(self,content_id,content_data):
		"""Updates content for a given ID, handling media uploads and validation.

		Args:
			content_id (str): The ID of the content to update.
			content_data: The new content data.

		Returns:
			None. Publishes updated content or error events.
		"""
		logger.info(f"Updating content for id {content_id}")
		if not content_data:
			content_event = Content(content_id,"No useable content provided for key.","error")
			self.publisher.push_content(content_event)
			logger.error(f"No useable content provided for key {content_id}")
			return
		else:
			format_content_type = self.format.get_content_type(content_id)
			if format_content_type in ["img","video","audio"]:
				file_type = MediaStore.get_media_type(content_data)
				logger.debug(f"Uplaoded content type: {file_type}")
				if file_type != format_content_type:
					content_data = f"File type {file_type} doesn't match expected content type {format_content_type}"
					content_type = "error"
					logger.error(content_data)
					self.publisher.push_content(Content(content_id,content_data,content_type))
					return
				else:
					content_data = MediaStore.upload_base64_file(content_data)
					if not content_data: 
						content_data = "Media could not be uploaded to media storage."
						content_type = "error"
						logger.error(content_data)
						content_event = Content(content_id,content_data,content_type)
						self.publisher.push_content(content_event)
						return
			elif format_content_type == "set":
					content_data = "Content item is a set and connot be directly updated."
					content_type = "error"
					logger.error(content_data)
					content_event = Content(content_id,content_data,content_type)
					self.publisher.push_content(content_event)
					return
			if content_data:
				content_event = Content(content_id,content_data,format_content_type)
				content_agent = Agent(self.story_id,content_id)
				if not content_agent.type:
					content_agent = self.build_agent_for_id(content_id)
				content_agent.state = "locked"
				content_agent.store()
				self.story.update_content(content_id,content_data)
				logger.info(f"Content updated for {content_id}")
				self.publisher.push_content(content_event)
				self.publisher.push_content(Content(content_id,"locked","restate"))
				self.invalidate_dependent_content(content_id)

	def build_agent_for_id(self, content_id):
		"""Builds an Agent object from format data.

		Args:
			content_id (str): The content ID for the agent.

		Returns:
			Agent or None: The built Agent if successful, None otherwise.
		"""
		try:
			# Get the format data from Firestore
			format_data = self.format.document.get().to_dict().get(self.format.formatKey, {})

			# Get the agent data from the format
			agent_data = format_data.get('AGENTS', {}).get(content_id)

			if agent_data:
				# Create an Agent object and populate its attributes
				agent = Agent(self.story_id, content_id)
				agent.desc = agent_data.get("DESC", "")
				agent.display_name = agent_data.get("DISPLAY_NAME", "")
				agent.data = agent_data.get("DATA", "")
				agent.type = agent_data.get("TYPE", "")
				agent.state = agent_data.get("STATE", "")
				agent.prompts = agent_data.get("PROMPTS", [])
				agent.memories = agent_data.get("MEMORIES", [])
				agent.model = agent_data.get("MODEL", "")
				agent.system = agent_data.get("SYSTEM", "")
				agent.depends_on = agent_data.get("DEPENDS_ON", [])
				agent.dependents = agent_data.get("DEPENDENTS", [])
				return agent
			else:
				logger.warning(f"While building agent for Content ID '{content_id}' it was not found in format.")
				return None

		except Exception as e:
			logger.error(f"Error building agent for content ID '{content_id}': {e}")
			return None

	def _resolve_content_variables(self, template_prompt):
		"""
		Resolves template variables in a prompt string, replacing them with content data.

		Args:
			template_prompt (str): Prompt string with variables like §content_id§.

		Returns:
			list: List of resolved prompt strings and media URLs.
		"""
		# Find all template variables in the prompt
		template_variables = re.findall(r'§(.*?)§', template_prompt)
		# If no template variables are found, return the original prompt in a list
		if not template_variables:
			return [template_prompt]

		resolved_prompts = []
		for var in template_variables:
			content_value = self.story.get_content(var)
			if content_value:
				#if the content being inserted is a media type:
				if self.format.get_content_type(var) in ["img","video","audio"]:
					#append media urls as resolved prompt items
					resolved_prompts.append(content_value)
					#make the content value the file name for multimodal model undestanding
					file_name = os.path.basename(content_value)
					template_prompt = template_prompt.replace(f"§{var}§", file_name)
				else:
					template_prompt = template_prompt.replace(f"§{var}§", content_value)
			else:
				# Remove the template variable if no content is found
				template_prompt = template_prompt.replace(f"§{var}§", "")
		resolved_prompts.append(template_prompt)
		return resolved_prompts
	
	def invalidate_dependent_content(self, content_id):
		"""
		Invalidates content dependent on the given ID using BFS to handle cycles.

		Args:
			content_id (str): The ID of the content whose dependents should be invalidated.
		"""
		visited = set()  # Keep track of visited nodes to prevent cycles
		queue = deque([content_id])  # Start with the initial content_id

		if not self.format.dependents_map:
			self.format.build_edge_links()
			self.format.populate_edge_maps()

		while queue:
			node_id = queue.popleft()
			visited.add(node_id)

			for dependent_id in  self.format.dependents_map.get(node_id, []):
				if dependent_id not in visited:
					queue.append(dependent_id)  # Add dependent to the queue

			if node_id != content_id:
				current_agent = Agent(self.story_id, node_id)
				if current_agent.state: 
					if current_agent.state != "locked" and current_agent.state != "invalid":
						logger.info(f"Invalidating {current_agent.content_id} because of content id: {content_id}")
						current_agent.state = "invalid"
						self.publisher.push_content(Content(current_agent.content_id, "invalid", "restate"))
						current_agent.store()

	def invalidate_content_this_content_depends_on(self, root_id):
		"""
		Invalidates content that the given ID depends on using DFS.

		Args:
			root_id (str): The ID of the content whose dependencies should be invalidated.
		"""

		visited = set()

		if not self.format.depends_on_map:
			self.format.build_edge_links()
			self.format.populate_edge_maps()

		#Nested recursive function for following edges and marking active agents invalid, unless locked
		def dfs_invalidate(content_id):
			if content_id != root_id:
				current_agent = Agent(self.story_id, content_id)
				if current_agent.state:
					if current_agent.state != "invalid" and current_agent.state != "locked":
						logger.info(f"Invalidating {current_agent.content_id} because content id {self.story.get_content('_current_content')} depends on it.")
					current_agent.state = "invalid"
					self.publisher.push_content(Content(current_agent.content_id, "invalid", "restate"))
					current_agent.store()
			visited.add(content_id)
			for dependent_id in self.format.depends_on_map.get(content_id, []):
				if dependent_id not in visited:
					dfs_invalidate(dependent_id)
		
		#Start the traversal
		dfs_invalidate(root_id)

	def generate_context_then_content(self, content_id):
		"""
		Generates content dependencies recursively (DFS) before generating target content.

		Args:
			content_id (str): The ID of the content to generate (after its dependencies).

		Returns:
			bool: True if all generations were successful, False otherwise.
		"""
		visited = set()
		success_checks = []

		if not self.format.depends_on_map:  # Ensure edge maps are populated
			self.format.build_edge_links()
			self.format.populate_edge_maps()

		def dfs_generate(content_id):
			visited.add(content_id)  # Mark as visited *before* recursive calls

			# Use depends_on_map here for correct DFS traversal
			for dependency_id in self.format.depends_on_map.get(content_id, []):  # Correct map
				if dependency_id not in visited:
					dfs_generate(dependency_id)

			success_checks.append(self.generate_content_for_id(content_id))


		dfs_generate(content_id)
		return all(success_checks)

	def generate_content_then_dependents(self, content_id):
		"""
		Generates content for an ID and its dependents using BFS.

		Args:
			content_id (str): The ID to generate content for, followed by its dependents.

		Returns:
			bool: True if all generations were successful, False otherwise.
		"""

		visited = set()  # Keep track of visited nodes to prevent cycles
		success_checks = []
		queue = deque([content_id])  # Start with the initial content_id

		while queue:
			node_id = queue.popleft()
			visited.add(node_id)

			current_agent = Agent(self.story_id, node_id)
			if not current_agent.type:
				current_agent = self.build_agent_for_id(node_id)
				current_agent.store()

			for dependent_id in current_agent.dependents:
				if dependent_id not in visited:
					queue.append(dependent_id)  # Add dependent to the queue

			success_checks.append(self.generate_content_for_id(node_id))  # Generate content after processing dependents for this level
		return all(success_checks)
	
	def _validate_content(self, content_list):
		"""
		Validates and generates content for a list of IDs if needed.

		Args:
			content_list (list): List of content IDs to validate.

		Returns:
			bool: True if all validations/generations successful, False otherwise.
		"""
		logger.info(f"Validating content for content ids: {content_list}")
		gen_results = []
		for content_id in content_list:
			if not self.format.get_content_type(content_id):
				continue
			content_agent = Agent(self.story_id, content_id)
			if not content_agent.state or content_agent.state in ["needed","invalid"]:
				success_check = self.generate_content_for_id(content_id)
				gen_results.append(success_check)
		return all(gen_results)

	def _generate_video_content(self, content_id):
		"""
		Generates video content from a list of image URLs or content IDs.

		Args:
			content_id (str): ID to store the generated video URL.
			prompts (list): List of image URLs or content IDs.

		Returns:
			bool: True if generation, upload, and storage successful, False otherwise.
		"""
		tmp_video_url = ""
		gcs_video_url = ""
	
		content_list = []
			#check if the story content needs to be generated, copied or regenerated

		video_agent = Agent(self.story_id, content_id)
		if not video_agent.type:
			# If agent is not loaded, build it from the format and store it in the store
			video_agent = self.build_agent_for_id(content_id)
			video_agent.store()
		
		#build this list of video content objects from the video agent's data

		video_content_ids = [content_id.strip() for content_id in video_agent.data.split(",")]

		self._validate_content(video_content_ids)
		logger.info(f"Video content being gathered from content ids:"+str(video_content_ids))

		for content_item in video_agent.prompts:
			content_item = content_item.replace("§", "")
			#this is super inefficient. instead get the format and story dictionaries in full and populate from there
			item_content = self.get_content_for_id(content_item)
			item_type = self.format.get_content_type(content_item)
			if not item_content or not item_type:
				continue
			content_object = Content(content_item, self.get_content_for_id(content_item), self.format.get_content_type(content_item))
			content_list.append(content_object)
		if len(content_list) == 0:
			logger.error(f"No useable content found for {content_id}")
			self.publisher.push_content(Content(content_id, "Failed to generate video.", "error"))
			return False
		if content_id == "dote.video":
			logger.warning("_generate_video_content: creating special dote video.")
			tmp_video_url = VideoComposer.create_dote_video(content_list)
		elif content_id == "beacon":
			logger.warning("_generate_video_content: creating special beacon video.")

			tmp_video_url = VideoComposer.create_beacon_video(content_list)
		else:
			logger.warning("_generate_video_content: creating regular video.")
			tmp_video_url = VideoComposer.create_video(content_list)

		if tmp_video_url:
			with open(tmp_video_url, 'rb') as video_file:
				video_data = video_file.read()
				gcs_video_url = MediaStore.upload_base64_file(
					base64.b64encode(video_data).decode('utf-8'),
					use_type="video/mp4"
				)
			if gcs_video_url is None:
				logger.warning("Failed to upload video to Google Cloud Storage.")
				return False
			else:
				# Update the story content and publish the result
				self.story.update_content(content_id, gcs_video_url)
				logger.info(f"New video URL stored for {content_id}: {gcs_video_url}")
				self.publisher.push_content(Content(content_id, gcs_video_url, "video"))
				return True
		else:
			logger.error(f"Failed to generate video for {content_id}")
			self.publisher.push_content(Content(content_id, "Failed to generate video.", "error"))
			return False


class Story:
	"""
	Represents a Story document in Firestore.

	Attributes:
		doc (firestore.DocumentReference): Firestore document reference.
		story_doc_name (str): Subcollection name for story content.
	"""
	def __init__(self,doc_id):
	

		fireStore = FirestoreClient.get_client(project=GC_PROJECT_ID)

	
		dotesCollection = fireStore.collection(STORY_COLLECTION_NAME)
		self.doc = dotesCollection.document(doc_id)
		self.story_doc_name = STORY_SUBDOCUMENT_KEY

		create_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
		self.update_content("_touched",create_time)

	def exists(self):
		return self.doc.get().exists  # Check for document existence

	def delete(self):
		self.doc.delete()
        
	def get_all_content(self):
		"""Gets all content from the Firestore document."""
		doc_snapshot = self.doc.get()
		if doc_snapshot:
			content_dict = doc_snapshot.to_dict().get(self.story_doc_name, {})
			content_object_list = []
			for content_id,content_data in content_dict.items():
				if content_id.startswith("_"):
					continue
				if not content_data:
					continue
				content_id = content_id.replace('`', '')
				content_object_list.append(Content(content_id,content_data,"REPLACE"))
			return content_object_list
	
	def get_content(self, content_id):
		"""
		Gets content for a specific ID.

		Args:
			content_id (str): The ID of the content to retrieve.

		Returns:
			Any: The content data or None if not found.
		"""
		content_key = f"`{content_id}`"  # Wrap content_id in backticks
		doc_snapshot = self.doc.get()
		content_data = doc_snapshot.to_dict().get(self.story_doc_name, {}).get(content_key)
		logger.debug(f"Getting content for {content_id} returned data: {content_data}")
		return content_data

	def update_content(self, content_id, content_data):
		"""
		Updates content in the Story document.

		Args:
			content_id (str): The ID of the content to update.
			content_data: The new content data.
		"""
		content_key = f"`{content_id}`"  # Wrap content_id in backticks
		self.doc.set({self.story_doc_name: {content_key: content_data}}, merge=True)  # Use set with merge=True	

	def clear_all_content(self):
		"""Clears all content from the Story document."""
		self.doc.set({self.story_doc_name: {}}, merge=True)  # Use set with merge=True



class Content:
    "Core data encapsulation."
    
    def __init__(self, this_id, this_data, this_type):
        self.id = this_id
        self.data = this_data
        self.type = this_type
    
    def __str__(self):
        # String representation for print()
        return f"Content(id={self.id}, data={self.data}, type={self.type})"
    
    def __repr__(self):
        # Developer-friendly representation
        return f"Content(id={self.id}, data={self.data}, type={self.type})"

class Publisher:
	"""
	Manages publishing of content updates to a queue.

	Attributes:
		story_id (str): Story document ID.
		buffer (firestore.DocumentReference): Firestore queue document.
		buffer_key (str): Key for the queue in the document.
	"""

	def __init__(self, story_id):

		fireStore = FirestoreClient.get_client(project=GC_PROJECT_ID)


		queue_collection = fireStore.collection(QUEUE_COLLECTION_NAME)
		self.buffer = queue_collection.document(story_id)

		self.buffer_key = "queue"
		try:
			doc_snapshot = self.buffer.get()
		except DeadlineExceeded: 
			logger.warning(f"Document buffer request timed out.")
		if not doc_snapshot.exists:
			self.buffer.set({self.buffer_key: []})  # Create the document with an empty queue
		elif self.buffer_key not in doc_snapshot.to_dict():
			self.buffer.set({self.buffer_key: []}, merge=True)  # Create the queue if it doesn't exist
		
	def has_content(self):
		"""
		Checks if the queue has content.

		Returns:
			bool: True if queue has content, False otherwise.
		"""
		doc_snapshot = self.buffer.get()
		if not doc_snapshot.exists:
			return False
		content_queue = doc_snapshot.to_dict().get(self.buffer_key, [])
		return len(content_queue) > 0
	
	def push_content(self, content):
		"""
		Adds content to the queue.

		Args:
			content (Content): The Content object to add.
		"""
		content_dict = content.__dict__
		content_json = json.dumps(content_dict)

		# Get the existing queue from the document
		doc_snapshot = self.buffer.get()
		existing_queue = doc_snapshot.to_dict().get(self.buffer_key, [])  # Get existing queue or initialize as empty list
		
		# Use deque for efficient FIFO operations
		content_queue = deque(existing_queue)  
		content_queue.append(content_json)  # Add the new content to the end (newest)

		# Update the document with the modified queue
		self.buffer.update({self.buffer_key: list(content_queue)}) 

	def pop_content(self):
		"""
		Retrieves and removes content from the queue.

		Returns:
			Content or None: The popped Content object or None if queue empty.
		"""

		try:
			# Get the existing queue from the document
			try:
				start_time = time.time()
				doc_snapshot = self.buffer.get()
				end_time = time.time()
				logger.debug(f"Firestore query took {end_time - start_time} seconds")

			except DeadlineExceeded: 
				logger.warning(f"Document buffer request timed out.")
				return None
			if not doc_snapshot.exists:
				logger.warning(f"Document not found for story ID: {self.story_id}")
				return None

			try:
				content_queue = deque(doc_snapshot.to_dict().get(self.buffer_key, []))
			except Exception as e:
				logger.error(f"Error getting content queue: {e}")
				return None

			if len(content_queue) < 1: 
				return None

			popped_content_json = content_queue.popleft() if content_queue else None

			# Update the document with the modified queue AFTER popping
			try:
				self.buffer.set({self.buffer_key: list(content_queue)}, merge=True)
			except Exception as e:
				# Handle errors during the set() operation
				logger.error(f"Error updating document after popping content: {e}")
				# Consider adding retry logic here if necessary

			# Convert JSON back to Content object if something was popped
			if popped_content_json:
				popped_content_dict = json.loads(popped_content_json)
				return Content(popped_content_dict['id'], popped_content_dict['data'], popped_content_dict['type'])
			else:
				return None 

		except NotFound as e:
			# Handle the case where the document doesn't exist
			logger.error(f"Firestore document not found: {e}")
			# You might want to create the document here if it's expected to not exist sometimes
		except Exception as e:
			# Handle other potential Firestore or general exceptions
			logger.error(f"An error occurred while popping content: {e}")
			# Consider adding more specific exception handling if needed

	def clear_queue(self):
		"""Clears the content queue."""
		self.buffer.set({self.buffer_key: []}, merge=True)


class Format:
	"""Defines the structure and content types of a Story document.

	Attributes:
		story_id (str):  Story document ID.
		document (firestore.DocumentReference): Firestore document for format data.
		formatKey (str): Key for format data in the document.
		depends_on_map (dict):  Dependency graph (content ID -> dependencies).
		dependents_map (dict): Reverse dependency graph (content ID -> dependents).
	"""
	def __init__(self, story_id, format_name=""):

		fireStore = FirestoreClient.get_client(project=GC_PROJECT_ID)


		
		dotes_collection = fireStore.collection(STORY_COLLECTION_NAME)
		self.document = dotes_collection.document(story_id)

		self.formatKey = "format"

		# Check if the document has a format key already
		doc_snapshot = self.document.get()
		if self.formatKey not in doc_snapshot.to_dict():
			logger.info(f"No existing format found for story {story_id}. Building from JSON.")
			if format_name:
				self.build_format_from_json(format_name)
		else:
			logger.info(f"Existing format found for story {story_id}.")
		format_data = doc_snapshot.to_dict().get(self.formatKey, {})
		self.depends_on_map = format_data.get('DEPENDS_ON_MAP', {})
		self.dependents_map = format_data.get('DEPENDENTS_MAP', {})

	def build_format_from_json(self, format_name):
		"""Loads format data from a JSON file.

		Args:
			format_name (str): Name of the format JSON file.
		"""
		try:
			# Construct the path to the JSON file
			current_dir = os.path.dirname(__file__) 

			# Construct the path relative to Storyteller.py
			format_path = os.path.join(current_dir, "..", "static", "formats", f"{format_name}.json")

			# Load the JSON data
			with open(format_path, 'r', encoding='utf-8') as f:
				format_data = json.load(f)

			# Store the format data in Firestore
			self.document.set({self.formatKey: format_data}, merge=True)  # Use set with merge=True
			self.build_edge_links()
			logger.info(f"Format {format_name} loaded and stored for story.")
		except (FileNotFoundError, json.JSONDecodeError) as e:
			logger.error(f"Error loading or storing format {format_name}: {e}")
	
	def build_edge_links(self):
		"""Builds dependency maps between content items."""
		# Get the format data from Firestore
		doc_snapshot = self.document.get()
		format_data = doc_snapshot.to_dict().get(self.formatKey, {})

		# Get the AGENTS data from the format
		agents_data = format_data.get('AGENTS', {})
		dependents_map = {}
		depends_on_map = {}
		# Iterate through each AGENT in the format document
		for agent_id, agent_data in agents_data.items():
			# Initialize depends_on and dependents lists for the current agent
			depends_on_map[agent_id] = []
			# Iterate through each prompt in the AGENT's PROMPTS
			for prompt in agent_data.get("PROMPTS", []):
				# Find all target_ids within the prompt string
				target_ids = re.findall(r'§(.*?)§', prompt) 
				logger.debug(f"Extracted target_ids: {target_ids} from prompt: {prompt}")
				for target_id in target_ids:
					# Add target_id to depends_on list of the current agent
					if agent_id in depends_on_map:
						depends_on_map[agent_id].append(target_id)
					else:
						depends_on_map[agent_id] = [target_id]
					# Add current agent's ID to dependents list of the target_id
					if target_id in dependents_map:
						dependents_map[target_id].append(agent_id)
					else:
						dependents_map[target_id] = [agent_id]
		
		# Update the format document with depends_on and dependents for each agent
		logger.debug(f"Depends egdes found: {depends_on_map}")
		logger.debug(f"Dependents egdes found: {dependents_map}")
		format_data['DEPENDS_ON_MAP'] = depends_on_map
		format_data['DEPENDENTS_MAP'] = dependents_map


		for agent_id in agents_data:
			if agent_id in depends_on_map:
				agents_data[agent_id]['DEPENDS_ON'] = depends_on_map[agent_id]
			else:
				agents_data[agent_id]['DEPENDS_ON'] = []
			if agent_id in dependents_map:
				agents_data[agent_id]['DEPENDENTS'] = dependents_map[agent_id]
			else:
				agents_data[agent_id]['DEPENDENTS'] = []
		
		
		# Update the document with the modified agents_data
		self.document.set({self.formatKey: format_data}, merge=True)

		logger.info("Edge links built and stored in format.")

	def populate_edge_maps(self):
		"""Populates the dependency maps."""
		try:
			# Get the format data from Firestore
			doc_snapshot = self.document.get()
			format_data = doc_snapshot.to_dict().get(self.formatKey, {})

			self.depends_on_map = format_data.get('DEPENDS_ON_MAP', {})
			self.dependents_map = format_data.get('DEPENDENTS_MAP', {})

		except Exception as e:
			logger.error(f"Error populating dependencies for agent {self.content_id}: {e}")

	def debug_content_type(format_data, content_id):
		"""
		Debug function to retrieve and log issues when accessing the TYPE field.

		Parameters:
		- format_data (dict): The data structure containing AGENTS and their details.
		- content_id (str): The specific content ID to retrieve data for.

		Returns:
		- str or None: The TYPE value if found; otherwise, None.
		"""
		# Step 1: Check if 'AGENTS' exists
		agents = format_data.get('AGENTS', None)
		if agents is None:
			logger.warning("'AGENTS' key is missing in format_data.")
			return None
		# logger.warning(f"'AGENTS' value: {agents}")

		# Step 2: Check if content_id exists in 'AGENTS'
		content_data = agents.get(content_id, None)
		if content_data is None:
			logger.warning(f"Content ID '{content_id}' is missing in 'AGENTS'.")
			return None
		# logger.warning(f"Data for content ID '{content_id}': {content_data}")

		# Step 3: Check if 'TYPE' exists in the content_data
		content_type = content_data.get("TYPE", None)
		if content_type is None:
			logger.warning(f"'TYPE' key is missing for content ID '{content_id}'.")
			return None
		# logger.warning(f"'TYPE' value for content ID '{content_id}': {content_type}")

		return content_type

	def get_content_type(self, content_id):
		"""
		Gets the type of content for a given ID.

		Args:
			content_id (str): The ID of the content.

		Returns:
			str or None: The content type (e.g., "txt", "img") or None if not found.
		"""
		try:
			# Get the format data from Firestore
			doc_snapshot = self.document.get()
			format_data = doc_snapshot.to_dict().get(self.formatKey, {})
			if format_data is None:
				logger.warning(f"No format data found for content ID: {content_id}")	
				return None

			# content_type = format_data.get('AGENTS', {}).get(content_id, {}).get("TYPE")
			content_type = Format.debug_content_type(format_data, content_id)
			if content_type is None:
				logger.warning(f"No content type found for content ID: {content_id}")
			return content_type

		except Exception as e:
			logger.error(f"Error getting content type for {content_id}: {e}")
			return None

	def get_content_index(self):
		"""
		Gets an index of all content IDs and their descriptions.

		Returns:
			list: List of Content objects with ID, description, and type.
		"""
		try:
			# Get the format data from Firestore
			doc_snapshot = self.document.get()
			format_data = doc_snapshot.to_dict().get(self.formatKey, {})

			# Get the AGENTS data from the format
			agents_data = format_data.get('AGENTS', {})

			# Create the content index list
			content_index = []
			for content_id, content_data in agents_data.items():
				content_object = Content(
					content_id,
					content_data.get("DESC", ""),
					content_data.get("TYPE", "")
				)
				content_index.append(content_object)

			return content_index

		except Exception as e:
			logger.error(f"Error getting content index: {e}")
			return []  # Return an empty list in case of error
	
	def delete(self):
		"""Deletes the Format document."""
		self.document.delete()



class Message:
	"""Encapsulates a message with text, role, and optional name.

	Attributes:
		text (str): The message content.
		role (str): The role of the message sender (e.g., "agent", "user").
		name (str): Optional name of the sender.
	"""
	def __init__(self,message):
		self.text = message
		self.role = "agent"
		self.name = ""

class Agent:
	"""
	Represents an agent capable of generating content.

	Attributes:
		story_id (str):  Story document ID.
		content_id (str): ID of the content this agent generates.
		desc (str):  Description of the content.
		display_name (str): Agent's display name.
		data (str): Default content data (if applicable).
		type (str): Type of content generated (e.g., "txt", "img").
		state (str):  Agent's current state (e.g., "active", "done").
		prompts (list):  Prompts used for generation.
		memories (list): Agent's memories.
		depends_on (list): Content IDs this agent depends on.
		dependents (list): Content IDs dependent on this agent.
	"""
	valid_states = ["none", "needed", "queued", "generating", "done", "locked", "invalid"]

	def __init__(self, story_id, content_id):
		self.story_id = story_id
		self.content_id = content_id
		self.desc = ""
		self.display_name = ""
		self.data = ""
		self.type = ""
		self.state = ""
		self.model = ""
		self.system = ""
		self.prompts = []
		self.memories = []
		self.depends_on = [] #content ids used in the prompts
		self.dependents = [] #content ids where this content id is used in the prompts
		# Attempt to load from storage on initialization
		self.load()

	def ask(self, message):
		#future: generate a response in the media type of self.media using the agent's resolved prompts, memories and message as the combined prompt
		response = f"You asked {message}"
		return response
	
	def tell(self, memory):
		#store the memory
		self.memories.append(memory)

	def store(self):
		"""Stores the Agent instance in Google Cloud Storage."""
		AgentStore.store_agent(self)

	def load(self):
		"""Loads the Agent instance from Google Cloud Storage."""
		loaded_agent = AgentStore.load_agent(self.story_id ,self.content_id)
		if loaded_agent:
			# Update this instance's attributes
			self.__dict__.update(loaded_agent.__dict__)
	

class AgentStore:
	"""Manages storage and retrieval of Agent objects in GCS."""
	@classmethod
	def store_agent(cls, agent):
		"""Stores an Agent in GCS.

		Args:
			agent (Agent): The Agent object to store.
		"""
		try:
			storage_client = StorageClient.get_client()
			bucket = storage_client.bucket(GCS_AGENT_BUCKET_NAME)

			# Construct the full blob name (folder path + agent_id) - No need to create folder explicitly
			blob_name = f"{agent.story_id}/agent_{agent.content_id}" 
			blob = bucket.blob(blob_name)

			# Serialize the Agent object using pickle
			pickled_agent = pickle.dumps(agent)
			
			# Upload the pickled data to GCS
			blob.upload_from_string(pickled_agent)
			logger.info(f"Agent stored in GCS: {blob_name}") # Add logging for success

		except GoogleAPIError as e:
			logger.error(f"Error storing agent in GCS: {e}")
			# Handle the error appropriately (e.g., raise an exception, retry, etc.)


	@classmethod
	def load_agent(cls, story_id, content_id):
		"""
		Uploads a base64 encoded file to GCS.

		Args:
			base64_file_data:  Base64 encoded file data.
			use_type (str, optional):  Explicit media type (e.g., "image/png").

		Returns:
			str or None: Public URL of the uploaded file, or None if upload fails.
		"""
		try:
			storage_client = StorageClient.get_client()
			bucket = storage_client.bucket(GCS_AGENT_BUCKET_NAME)

			# Construct the full blob name (folder path + agent_id)
			blob_name = f"{story_id}/agent_{content_id}" 
			blob = bucket.blob(blob_name)
			
			if blob.exists():
				# Download the pickled data from GCS
				pickled_agent = blob.download_as_bytes()

				# Deserialize the data back into an Agent object
				agent = pickle.loads(pickled_agent)
				logger.debug(f"Agent loaded from GCS: {blob_name}") # Add logging for success
				# Return the loaded agent
				return agent
			else:
				return None  # Agent not found
		except GoogleAPIError as e:
			logger.error(f"Error loading agent from GCS: {e}")
			# Handle the error (e.g., return None, raise an exception, etc.)
			return None 
		
	def delete_agents(story_id):
		"""Deletes all the stored agents for a story.

		Args:
			story_id (str):  Story document ID.
		"""
		try:
			agent_bucket = storage.Client().get_bucket(GCS_AGENT_BUCKET_NAME) 
			blobs = list(agent_bucket.list_blobs(prefix=story_id))  # Iterate through iterator. A single item means blobs exist
			agent_bucket.delete_blobs(blobs)
			logger.info(f"Deleted all agent blobs for story '{story_id}'") # Log success
		except Exception as e: # Add more specific exception handling if needed
			logger.error(f"Error deleting agent blobs for '{story_id}': {e}")



class ModelConfig:
	"""Stores configuration for a specific AI model."""

	# Default configurations if loading from JSON fails
	default_config = {"service": "vertexai", "model_name": "text-bison@001", "secret_name":"","parameters": { "gc_project" : GC_PROJECT_ID, "location" : "us-central1"}}
	config_filepath = os.path.join(os.path.dirname(__file__), ".", "model_configs.json")  # Path to config file


	@classmethod
	def available_configs(cls):
		"""Loads all available model configuration names from the JSON file."""
		try:
			with open(cls.config_filepath, 'r', encoding='utf-8') as f:
				config_data = json.load(f)
				return list(config_data.keys()) # Return list of config names
		except (FileNotFoundError, json.JSONDecodeError) as e:
			logger.error(f"Error loading model configurations from JSON: {e}")
			return [] # Return empty list if error

	def __init__(self, model_config_name):
		configs = self._load_model_configs_from_json() #load from json
		if configs and model_config_name in configs:
			model_config = configs[model_config_name]
			self.service = model_config.get("service", "")
			self.model_name = model_config.get("model_name", "")
			self.secret_name = model_config.get("secret_name", "")
			self.parameters = model_config.get("parameters", {})
			self.system = model_config.get("system", "")
		else: #if it fails revert to a default
			logger.error(f"Error loading model configuration {model_config_name}. Check the JSON file. Loading default.")
			self.service = ModelConfig.default_config["service"]
			self.model_name = ModelConfig.default_config["model_name"]
			self.secret_name = ModelConfig.default_config["secret_name"]
			self.parameters = ModelConfig.default_config["parameters"]
			self.system = ""


	def _load_model_configs_from_json(self): #helper function to load configs
		"""Loads model configurations from JSON file. Returns a dictionary or None."""

		try:
			with open(self.config_filepath, 'r', encoding='utf-8') as f:
				config_data = json.load(f)
				return config_data

		except (FileNotFoundError, json.JSONDecodeError) as e:
			logger.error(f"Error loading or parsing model configuration JSON: {e}")
			return None

class ModelInterface:
	"""Class to provide uniform access to AI models. Uses a ModelConfig instance to set up the service context and model parameters, and the prompt_string to generate a response of the specified media_type."""

	def __init__(self, model_config):
		self.model_config = model_config
		#verify API secrets are found if config has model_secret value
		#other service specific setup as needed

	def generate(self, prompt, media_type):
		if self.model_config.service == "vertexai":
			if media_type == "txt":
				return self._generate_text_using_vertexai(prompt)
			elif media_type == "img":
				return self._generate_image_using_vertexai(prompt)
			elif media_type == "audio":
				return self._generate_audio_using_vertexai(prompt)
			elif media_type == "loc":
				return self._generate_location_using_vertexai(prompt)
			else:
				logger.error(f"Unsupported media type for service vertexai: {media_type}")
				return None
		elif self.model_config.service == "test":
			if media_type == "txt":
				return prompt
			elif media_type == "img":
				return "https://storage.googleapis.com/storyteller-media/PtkRUJoA.png"
			elif media_type == "audio":
				return "https://storage.googleapis.com/storyteller-media/test.audio.mp3"
			elif media_type == "loc":
				return "37.773972,-122.431297"
			else:
				logger.error(f"Unsupported media type for service test: {media_type}")
				return None
		elif self.model_config.service == "openai":
			if media_type == "txt":
				return self._generate_text_using_openai(prompt)
			elif media_type == "img":
				return self._generate_image_using_openai(prompt)
			elif media_type == "audio":
				return self._generate_audio_using_openai(prompt)
			else:
				logger.error(f"Unsupported media type for service test: {media_type}")
				return None
		elif self.model_config.service == "ollama":
			if media_type == "txt":
				return self._generate_text_using_ollama(prompt)
			else:
				logger.error(f"Unsupported media type for service ollama: {media_type}")
				return None
		elif self.model_config.service == "huggingface":
			if media_type == "txt":
				return self._generate_text_using_huggingface(prompt)
			if media_type == "img":
				return self._generate_image_using_huggingface(prompt)
			else:
				logger.error(f"Unsupported media type for service huggingface: {media_type}")
				return None
		else:
			logger.error(f"Unsupported model service: {self.model_config.service}")
			return None

	def _generate_text_using_ollama(self, prompt):
		"""Generates text using Ollama."""
		try:
			logger.info(f"Making text generation request to Ollama with prompt: {prompt}")

			model_name = self.model_config.model_name  # Use model name from config
			
			# Extract parameters from model config or use defaults
			model_temp = self.model_config.parameters.get("temperature", 0.7)
			max_length = self.model_config.parameters.get("max_length", 1024)  # Adjust as needed

			# Ollama doesn't include a specific system prompt in the same way, so we add the system prompt to the user prompt
			if self.model_config.system:
				prompt = f"{self.model_config.system}\n{prompt}"



			# Prepare the request body
			request_body = {
				"model": model_name,
				"prompt": prompt,
				"temperature": model_temp,
				"max_tokens": max_length
			}

			# Make the request to the Ollama server
			ollama_url = "http://localhost:11434/api/generate"  # Ollama's default API endpoint
			response = requests.post(ollama_url, json=request_body, stream=True) #stream=True handles long responses efficiently

			response.raise_for_status()  # Raise an exception for HTTP errors (4xx or 5xx)


			#__FUTURE__: return the stream an move stream unpacking to the Storyteller so each chunk can be published 
			# Process the streamed response
			generated_text = ""
			for chunk in response.iter_lines():  # handles streamed response
				if chunk:
					decoded_chunk = chunk.decode('utf-8')
					try:
						json_chunk = json.loads(decoded_chunk)
						generated_text += json_chunk.get("response", "")
					except json.JSONDecodeError as e:
						logger.error(f"Error decoding JSON chunk from Ollama: {e}")
						# Handle the error as needed, e.g., skip the chunk or break the loop


			return generated_text.strip()


		except requests.exceptions.RequestException as e:
			logger.error(f"An error occurred during the Ollama request: {e}")
			return None
		except Exception as e:
			logger.error(f"An unexpected error occurred during Ollama text generation: {e}")
			return None
		
		
	def _generate_text_using_openai(self, prompt):
		"""Generates text using OpenAI."""
		try:
			logger.info(f"Making text generation request to OpenAI with prompt: {prompt}")

			if not self.model_config.model_name:
				model_name = "gpt-4o" # Default model if not specified
			else:
				model_name = self.model_config.model_name

			
			model_temp = self.model_config.parameters.get("temperature", 0.5)
			max_length = self.model_config.parameters.get("max_length", 100)

			message_list = [{"role": "user", "content": prompt}]
			if self.model_config.system:
				message_list.insert(0, {"role": "system", "content": self.model_config.system})


			client = OpenAI(
    			api_key=os.getenv(self.model_config.secret_name),  
			)
			chat_completion = client.chat.completions.create(
   				messages= message_list,
		    	model=model_name,
				temperature=model_temp,
				max_tokens=max_length
			)


			if chat_completion and chat_completion.choices:
				return chat_completion.choices[0].message.content.strip()
			else:
				logger.error(f"OpenAI text generation failed or returned empty response: {chat_completion}")
				return None

		except Exception as e:
			logger.error(f"An unexpected error occurred during OpenAI text generation: {e}")
			return None


	def _generate_image_using_openai(self, prompt):
		"""Generates an image using OpenAI."""
		try:
			logger.info(f"Making image generation request to OpenAI with prompt: {prompt}")

			config_model = self.model_config.model_name if self.model_config.model_name else "dall-e-3"
			config_size = self.model_config.parameters.get("size", "1024x1024")
			config_quality = self.model_config.parameters.get("quality", "standard")

			api_key = os.getenv(self.model_config.secret_name)

			client = OpenAI(api_key=api_key)

			image_data = client.images.generate(
  				model=config_model,
				prompt=prompt,
				quality=config_quality,
				n=1,
				size=config_size
			)

			if image_data and image_data.data and image_data.data[0].url:
				return MediaStore.upload_file_from_url(image_data.data[0].url)
			else:
				return None
			
		except OpenAIError as e:
			logger.error(f"OpenAI image generation failed: {e}")
			return None
		except Exception as e:
			logger.error(f"An unexpected error occurred during OpenAI image generation: {e}")
			return None
		

	def _generate_audio_using_openai(self, prompt):
		"""Generates audio using OpenAI."""
		try:
			logger.info(f"Making audio generation request to OpenAI with prompt: {prompt}")

			api_key = os.getenv(self.model_config.secret_name)

			config_model = self.model_config.model_name if self.model_config.model_name else "tts-1"
			config_voice = self.model_config.parameters.get("voice", "alloy")
			config_speed = self.model_config.parameters.get("speed", 1)

			client = OpenAI(api_key=api_key)

			speech_data = client.audio.speech.create(
				model=config_model,
				voice=config_voice,
				input=prompt,
				speed=config_speed
			)

			if speech_data:
				tmp_audio_file = os.path.join("/tmp", f"{secrets.token_urlsafe(8)}.mp3")  # Create a temporary file path
				speech_data.write_to_file(tmp_audio_file)  # Write audio to the temporary file

				with open(tmp_audio_file, 'rb') as audio_file:
					audio_data = audio_file.read()
					gcs_audio_url = MediaStore.upload_base64_file(
						base64.b64encode(audio_data).decode('utf-8'),
						use_type="audio/mp3"  # Or the correct MIME type
					)

				os.remove(tmp_audio_file) #remove the tmp file

				if gcs_audio_url is None:
					logger.warning("Failed to upload audio to Google Cloud Storage.")
					return None # Or handle the failure appropriately
				else:
					return gcs_audio_url
			else:
				return None
		except Exception as e:
			logger.error(f"Error generating audio with OpenAI: {e}")
			return None


	def _generate_text_using_huggingface(self, prompt):
		"""Generates text using Hugging Face."""
		try:
			logger.info(f"Making text generation request to Hugging Face with prompt: {prompt}")
			# Add your Hugging Face text generation code here
			# ...
			return "Hugging Face text generation result"  # Replace with actual result
		except Exception as e:
			logger.error(f"Error generating text with Hugging Face: {e}")
			return None

	def _generate_image_using_huggingface(self, prompt):
		"""Generates an image using Hugging Face."""
		try:
			logger.info(f"Making image generation request to Hugging Face with prompt: {prompt}")
			# Add your Hugging Face image generation code here
			# ...
			return "Hugging Face image generation result"  # Replace with actual result
		except Exception as e:
			logger.error(f"Error generating image with Hugging Face: {e}")
			return None



	def _generate_text_using_vertexai(self, prompt):
		"""Generates text using Vertex AI."""
		try:
			logger.info(f"Making text generation request to Vertex AI with prompt: {prompt}")

			gc_proj_name = self.model_config.parameters.get("gc_project", GC_PROJECT_ID)
			gc_region = self.model_config.parameters.get("location", "us-central1")

			system_prompt = self.model_config.system if self.model_config.system else ""

			generation_config = {
				"max_output_tokens": self.model_config.parameters.get("max_output_tokens",1024),
				"temperature": self.model_config.parameters.get("temperature",0.3),
				"top_p": 0.95,
			}

			safety_settings = [
				SafetySetting(
					category=SafetySetting.HarmCategory.HARM_CATEGORY_HATE_SPEECH,
					threshold=SafetySetting.HarmBlockThreshold.OFF
				),
				SafetySetting(
					category=SafetySetting.HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT,
					threshold=SafetySetting.HarmBlockThreshold.OFF
				),
				SafetySetting(
					category=SafetySetting.HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT,
					threshold=SafetySetting.HarmBlockThreshold.OFF
				),
				SafetySetting(
					category=SafetySetting.HarmCategory.HARM_CATEGORY_HARASSMENT,
					threshold=SafetySetting.HarmBlockThreshold.OFF
				),
			]

			vertexai.init(project=gc_proj_name, location=gc_region)
			model = GenerativeModel(
        		self.model_config.model_name,
				system_instruction=system_prompt
    		)
			response = model.generate_content(
				[prompt],
				generation_config=generation_config,
				safety_settings=safety_settings
			)
			if response and response.text:
				return response.text
			else:
				logger.error(f"Vertex AI text generation failed or returned empty response: {response}")
				return None
		except Exception as e:
			logger.error(f"Error generating text with Vertex AI: {e}")
			return None
	
	def _generate_image_using_vertexai(self, prompt):
		"""Generates an image using Vertex AI."""
		try:
			logger.info(f"Making image generation request to Vertex AI with prompt: {prompt}")

			gc_proj_name = self.model_config.parameters.get("gc_project", GC_PROJECT_ID)
			gc_region = self.model_config.parameters.get("location", "us-central1")

			config_aspect_ratio = self.model_config.parameters.get("aspect", "16:9")
			config_lang = self.model_config.parameters.get("lang", "en")
			config_guidance = self.model_config.parameters.get("guidance", "4")
			config_safety = self.model_config.parameters.get("safety", "block_some")
			config_person = self.model_config.parameters.get("person", "dont_allow")

			vertexai.init(project=gc_proj_name, location=gc_region)
			generation_model = ImageGenerationModel.from_pretrained(self.model_config.model_name)
			
			image = generation_model.generate_images(
				prompt=prompt,
				number_of_images=1,
				aspect_ratio=config_aspect_ratio,
				language=config_lang,
				guidance_scale=config_guidance,
				safety_filter_level=config_safety,
				person_generation=config_person
			)

			logger.info(f"Image result type: {type(image)}, value: {image}")

			generated_image = None

			if isinstance(image, ImageGenerationResponse):
				if not hasattr(image, 'images') or not image.images:
					logger.error(f"No images found in ImageGenerationResponse! Value: {image}")
					return None
				generated_image = image.images[0]
				logger.info(f"Generated image extracted from ImageGenerationResponse: {generated_image}")
			
			elif isinstance(image, list):
				if not image:
					logger.error(f"No images found in list! Value: {image}")
					return None
				generated_image = image[0]
				logger.info(f"Generated image extracted from list: {generated_image}")
			
			else:
				logger.error(f"Unexpected image type: {type(image)}. Value: {image}")
				return None

			if not generated_image:
				logger.error("Failed to extract an image from the response.")
				return None

			try:
				image_url = MediaStore.upload_base64_file(
					base64.b64encode(generated_image._image_bytes).decode('utf-8'),
					use_type="image/png"
				)
			except Exception as e:
				logger.error(f"Error while uploading the generated image to MediaStore: {e}")
				return None

			if image_url is None: 
				logger.error("Couldn't upload generated image to GCS.")
				return None
			else:
				logger.info(f"Successfully uploaded image to GCS. URL: {image_url}")
				return image_url

		except Exception as e:
			logger.error(f"Error in Vertex AI image generation: {e}")
			logger.error(f"Traceback: {traceback.format_exc()}")
			return None

	def _generate_audio_using_vertexai(self, prompt):
		"""Generates audio using Vertex AI's text-to-speech."""
		try:
			gc_proj_name = self.model_config.parameters.get("gc_project", GC_PROJECT_ID)
			gc_region = self.model_config.parameters.get("location", "us-central1")
			config_lang = self.model_config.parameters.get("lang","en-US")
			config_voice = self.model_config.parameters.get("voice","en-US-Wavenet-C")
			config_gender = self.model_config.parameters.get("gender","female")

			if config_gender == "FEMALE":
				config_gender = texttospeech.SsmlVoiceGender.FEMALE
			elif config_gender == "MALE":
				config_gender = texttospeech.SsmlVoiceGender.MALE
			else:
				config_gender = texttospeech.SsmlVoiceGender.NEUTRAL



			vertexai.init(project=gc_proj_name, location=gc_region)
			client = texttospeech.TextToSpeechClient()  # Vertex AI's TTS client
			synthesis_input = texttospeech.SynthesisInput(text=prompt)

								
			# Build the voice request, selecting the language code ("en-US") and the ssml
			# voice gender ("neutral")
			voice = texttospeech.VoiceSelectionParams(
				language_code=config_lang,
				name=config_voice,
				ssml_gender=config_gender,
			)

			# Select the type of audio file you want returned
			audio_config = texttospeech.AudioConfig(
				audio_encoding=texttospeech.AudioEncoding.MP3
			)

			# Perform the text-to-speech request on the text input with the selected
			# voice parameters and audio file type
			response = client.synthesize_speech(
				input=synthesis_input, voice=voice, audio_config=audio_config
			)

			# Validate the response (check for errors or empty audio)
			if not response or not response.audio_content:
				logger.warning(f"Audio generation failed with response: {response}")
				return False
			
			# Upload the audio data to MediaStore
			audio_url = MediaStore.upload_base64_file(
				base64.b64encode(response.audio_content).decode('utf-8'),
				use_type="audio/mp3"
			)
			if audio_url is None:
				logger.warning("Failed to upload audio to Google Cloud Storage.")
				return False
			else:
				return audio_url

		except Exception as e:
			logger.error(f"Error in Vertex AI audio generation: {e}")
			return False

	
	def _generate_location_using_vertexai(self, prompt):
		"""Generates location data (similar to text generation)."""
		loc_prompt = " Generate the GPS latitude and longitude AS DECIMAL DEGREES of the following location:" + prompt + "ONLY GENERATE A GPS, DECIMAL DEGREES formatted response. Do not include any other text."
		return self._generate_text_using_vertexai(loc_prompt) # Reuse the text method



class MediaStore:
	"""Class to manage the storage and retrieval of media files in Google Cloud Storage."""
	def upload_base64_file(base64_file_data,use_type=None):
		"""
		Uploads a base64 encoded file to Google Cloud Storage, 
		determining the file type from the data header.
	
		Args:
			base64_file_data: The base64 encoded file data.
	
		Returns:
			The public URL of the uploaded file, or None if upload fails.
		"""
		try:
			logger.info("Uploading file to GCS")
	
			# Extract file type and data
			if use_type:
				media_type = use_type
				file_extension = media_type.split(';')[0].split('/')[-1] 
			elif base64_file_data.startswith('data:'):
				media_type, base64_file_data = base64_file_data.split(',', 1)
				file_extension = media_type.split(';')[0].split('/')[-1]  # e.g., "png", "jpeg", "mp3"
			else:
				logger.error("Invalid base64 file data format.")
				return None
	
			# Decode the base64 data
			file_data = base64.b64decode(base64_file_data)
	
			# Generate a unique file ID
			file_id = secrets.token_urlsafe(6)
			blob_name = f"{file_id}.{file_extension}"
	
			# Upload to GCS
			storage_client = StorageClient.get_client()
			bucket = storage_client.bucket(GCS_MEDIA_BUCKET_NAME)
			blob = bucket.blob(blob_name)
			blob.upload_from_string(file_data, content_type=media_type)
	
			# Construct and return the public URL
			file_url = f"https://storage.googleapis.com/{GCS_MEDIA_BUCKET_NAME}/{blob_name}"
			logger.info(f"File uploaded to GCS: {file_url}")
			return file_url
	
		except Exception as e:
			logger.error(f"Failed to upload file to GCS: {e}")
			return None 
	

	def upload_file_from_url(source_url):
		"""Uploads a file from a URL to Google Cloud Storage.

		Args:
			source_url (str): URL of the file to upload.

		Returns:
			str or None: Public URL of the uploaded file or None on failure.
		"""
		try:
			response = requests.get(source_url, stream=True, timeout=30)  # Add timeout
			response.raise_for_status()

			
			file_extension = os.path.splitext(source_url)[1]
			content_type = response.headers.get('content-type')
			destination_blob_name = secrets.token_urlsafe(6) + file_extension

			storage_client = storage.Client()
			bucket = storage_client.bucket(GCS_MEDIA_BUCKET_NAME)
			blob = bucket.blob(destination_blob_name)
			blob.upload_from_string(response.content, content_type=content_type)

			file_url = blob.public_url
			logger.info(f"File uploaded from {source_url} to GCS: {file_url}")
			return file_url

		except requests.exceptions.RequestException as e:
			logger.error(f"Error downloading file: {e}")
			return None
		except Exception as e:  # Catch GCS errors
			logger.error(f"Error uploading to GCS: {e}")
			return None



	def get_media_type(base64_data):
		"""
		Determines media type from base64 data header.

		Args:
			base64_data (str): Base64 encoded data.

		Returns:
			str: "video", "audio", "img", or "unknown".
		"""

		if base64_data.startswith('data:video'):
			return "video"
		elif base64_data.startswith('data:audio'):
			return "audio"
		elif base64_data.startswith('data:image'):
			return "img"
		else:
			return "unknown"