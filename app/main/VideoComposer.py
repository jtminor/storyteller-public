import requests
from urllib.parse import urlparse
from io import BytesIO

import numpy as np
from PIL import Image
import cv2

from moviepy.editor import *
import tempfile
import logging

import math
from PIL import ImageFilter

import random

logger = logging.getLogger(__name__) 
logger.setLevel(logging.INFO)


class VideoComposer:
	"""Interface for moviepy service to make videos from content items using a hand coded template."""

	video_size = (1920,1080)
	snowflakes = []  # Class attribute to store snowflake positions

	def process_background(background_path, scene_duration, zoom_ratio=0.04, max_blur_radius=10):
		"""
		Processes the background image and applies zoom-in effects.

		Parameters:
		- background_path (str): Path to the background image file.
		- scene_duration (float): Duration of the scene in seconds.
		- zoom_ratio (float): The ratio for the zoom-in effect.
		- max_blur_radius (int): Maximum blur radius for the effect.

		Returns:
		- slide (ImageClip): Processed video clip with applied effects.
		"""
		logger.info(f'process_background: {background_path}')
		
		# Load and resize the image to fit the video size
		slide = ImageClip(background_path).set_duration(scene_duration)
		slide = slide.resize(newsize=VideoComposer.video_size)  # Resize to fit the video frame
		
		# Apply zoom-in effects
		effects = VideoEffects(zoom_ratio=zoom_ratio, max_blur_radius=max_blur_radius)
		return effects.zoom_in_effect(slide)

	def create_text_clip(caption, scene_duration, start_delay=0, 
						text_size=48, title_font='Liberation-Sans', title_color='yellow'):
		"""
		Creates a text clip with specified properties.

		Parameters:
		- caption (str): The text to display.
		- scene_duration (float): Duration of the scene in seconds.
		- start_delay (float): Delay before the text appears, in seconds.
		- text_size (int): Font size of the text.
		- title_font (str): Font used for the text.
		- title_color (str): Color of the text.

		Returns:
		- TextClip: The configured text clip.
		"""
		logger.info(f'Creating text clip with caption: {caption}')

		txt_clip = TextClip(
			caption,
			font=title_font,
			fontsize=text_size,
			color=title_color,
			method="label"
		)
		txt_clip = txt_clip.set_position((50,50))
		txt_clip = txt_clip.set_start(start_delay)
		txt_clip = txt_clip.set_duration(scene_duration)

		logger.info(f"create_text_clip: text clip size is {txt_clip.size}")

		return txt_clip
	
	def transform_list_to_script(content_list):
		"""
		Transforms a list of Content objects into a nested dictionary structure.
		
		If the `id` field in a Content object contains a "scene#" prefix (e.g., "scene1.key"),
		the resulting dictionary will nest keys under that scene. If no prefix is present, 
		the key will be placed at the top level of the dictionary.
		
		Args:
			content_list (list): A list of Content objects, where each object has `id`, 
								`data`, and `type` attributes. Pass 'None' for a preset list for testing

		Returns:
			dict: A nested dictionary with scene keys as top-level entries and their associated
				properties. Keys without a scene prefix are placed at the top level.
		"""
		nested_dict = {}

		if (content_list == None):
			nested_dict = {
				'scene3': {
					'polaroid': {
						'data': 'https://storage.googleapis.com/storyteller-media/rS5uM41t.png',
						'type': 'img'
					},
					'background': {
						'data': 'https://storage.googleapis.com/storyteller-media/wm8o66XM.png',
						'type': 'img'
					},
					'caption': {
						'data': 'Enjoy the beautiful winter weather in Kona, Hawaii!',
						'type': 'txt'
					}
				},
				'scene2': {
					'polaroid': {
						'data': 'https://storage.googleapis.com/storyteller-media/zbOAG225.png',
						'type': 'img'
					},
					'background': {
						'data': 'https://storage.googleapis.com/storyteller-media/EoVsQDt-.png',
						'type': 'img'
					},
					'caption': {
						'data': 'Wishing you were here on the beautiful beaches of Waikiki, Hawaii!',
						'type': 'txt'
					}
				},
				'scene1': {
					'polaroid': {
						'data': 'https://storage.googleapis.com/storyteller-media/XPdEo9EZ.jpeg',
						'type': 'img'
					},
					'background': {
						'data': 'https://storage.googleapis.com/storyteller-media/-yzPzIds.png',
						'type': 'img'
					},
					'caption': {
						'data': 'A family of four enjoys a beautiful day in Hawaii.',
						'type': 'txt'
					}
				}
			}

			logger.info(f"create_beacon_video: returning debug data-structure")
			return nested_dict

		for content in content_list:
			parts = content.id.split(".")
			if len(parts) == 2:
				scene, key = parts
				if scene not in nested_dict:
					nested_dict[scene] = {}
				nested_dict[scene][key] = {"data": content.data, "type": content.type}
			else:
				key = parts[0]
				nested_dict[key] = {"data": content.data, "type": content.type}

		# logger.info(nested_dict)

		return nested_dict
	
	def create_slideshow_video(image_list):
		"""Creates a slideshow video from a list of image URLs."""
		
		image_urls = [img_url for img_url in image_list if urlparse(img_url).scheme in ('http', 'https')]
		if not image_urls:
			raise ValueError("No valid image URLs found in prompts.")
		clips = []
		
		# Load images as ImageClips
		for frame_url in image_urls:
			if frame_url == '': continue
			response = requests.get(frame_url)
			response.raise_for_status()  # Raise an error for bad status codes

			image = Image.open(BytesIO(response.content))
			image_np = np.array(image)
			slide = ImageClip(image_np).set_duration(4)
			clips.append(slide)

		# Concatenate clips into a single video
		final_clip = CompositeVideoClip([slides_clip]+text_clips)

		with tempfile.NamedTemporaryFile(suffix=".webm", delete=False) as temp_video_file:
			slides_clip.write_videofile(temp_video_file.name, fps=24, codec='libvpx')
			slides_clip.close()
			temp_video_path = temp_video_file.name
		return temp_video_path

	def create_video(content_list):
		"""Creates a video from a list of content items."""
		audio_list = []
		images_list = []
		text_list = []

		title_font = 'Liberation-Sans'
		title_color = 'yellow'

		for content_item in content_list:
			if content_item.data == None: continue
			if content_item.type == "img":
				images_list.append(content_item.data)
			elif content_item.type == "txt":
				text_list.append(content_item.data)
			elif content_item.type == "audio":
				audio_list.append(content_item.data)

		audio_clips = []
		for audio_url in audio_list:
			try:
			# Download the audio file to a temporary location
				if audio_url == '': continue
				response = requests.get(audio_url)
				response.raise_for_status()  # Raise an error for bad status codes

				with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as temp_audio:
					temp_audio.write(response.content)
					temp_audio_path = temp_audio.name
					temp_audio.close()

				# Create AudioFileClip from the temporary file
				audio_clip = AudioFileClip(temp_audio_path)
				audio_clips.append(audio_clip)

			except Exception as e:
				logger.error(f"Error loading or processing audio from {audio_url}: {e}")

		video_length = len(images_list) * 4
		logger.warning(f"create_video: {video_length} video length")

		final_audio = None

		if audio_clips:
			final_audio = CompositeAudioClip(audio_clips)
			video_length = final_audio.duration

		# Create the slideshow
		clips = []
		slide_duration = video_length / (len(images_list) ) if video_length else 1

		for frame_url in images_list:
			if frame_url == '': continue
			response = requests.get(frame_url)
			response.raise_for_status()  # Raise an error for bad status codes

			image = Image.open(BytesIO(response.content))
			image_np = np.array(image)
	
			clip_duration = slide_duration
			slide = ImageClip(image_np).set_duration(clip_duration)

			# Create an instance of VideoEffects with custom settings
			effects = VideoEffects(zoom_ratio=0.04, max_blur_radius=10)

			# Apply the zoom-in effect with gradual blur
			output_clip = effects.zoom_in_effect(slide)
			
			# clips.append(slide)
			clips.append(output_clip)

			image_size = image.size

			polaroid = PolaroidFrame(target_height=VideoComposer.video_size[1], border_size=20).create("https://storage.googleapis.com/storyteller-media/c93bLZpn.png")
			polaroid = polaroid.rotate(27, expand=True)  # Rotate with expansion to fit rotated bounds

			# # Convert the PIL image to an ImageClip and set its duration
			polaroid = ImageClip(np.array(polaroid)).set_duration(slide_duration+2)
			start_delay = slide_duration * 1.5
			polaroid = polaroid.set_start(start_delay)
			polaroid = polaroid.set_position((825,175))

		# Concatenate clips into a single video (audio added below)
		slides_clip = concatenate_videoclips(clips + [polaroid], method="compose")

		# Create text clips
		text_clips = []
		text_duration = video_length / (len(text_list) ) if video_length else 1
		start_delay = 0
		text_size = 48

		for text_content in text_list:

			if text_content == "":
				logger.warning(f"create_video: skipping blank text_content")
				continue

			# breakpoint()

			txt_clip = TextClip(text_content, 
					   # position in upper left hand corner
						size=(VideoComposer.video_size[0]//2, VideoComposer.video_size[1]//2),
						font=title_font, 
						fontsize=text_size,
						color=title_color,
						align='NorthWest',
						method="caption"
						)
			
			txt_clip = txt_clip.set_position(("left", "top"))
			txt_clip = txt_clip.set_start(start_delay)
			txt_clip = txt_clip.set_duration(text_duration)

			start_delay = start_delay + text_duration
			text_clips.append(txt_clip)
		
		if not text_clips and not slides_clip:
			logger.error("No content found for video.")
			return None

		final_clip = CompositeVideoClip([slides_clip]+text_clips)

		if final_audio:	
			final_clip.audio = final_audio
		
		with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as temp_video_file:
			final_clip.write_videofile(temp_video_file.name, 
							  audio=True, 
							  fps=24, 
							  codec='libx264', 
							  audio_codec='aac',
							  preset='ultrafast',  # Use a fast preset for debugging
							  ffmpeg_params=['-pix_fmt', 'yuva420p']) # Ensure alpha is handled)
			final_clip.close()
			temp_video_path = temp_video_file.name

		return temp_video_path

	
	def getStyleConfigFromName(style_name):
		"""Selects font, color, and overlay based on style name."""
		logger.debug(f"Getting style config for {style_name}")
		style_configs = {
			"default": ("Liberation-Sans", "white", None),
			"Summer Sun": ("Liberation-Sans", "yellow", None),
			"Winter Holidays": ("Liberation-Sans", "white", "snow"),
			"Spring Flowers": ("Liberation-Sans", "pink", None),
			"Autumnal": ("Liberation-Sans", "orange", None),
			"Friendly Celebration": ("Liberation-Sans", "yellow", None),
			"Family Feelings": ("Liberation-Sans", "purple", None)
		}
		return style_configs.get(style_name, style_configs["default"])

class VideoEffects:
    def __init__(self, zoom_ratio=0.04, max_blur_radius=10):
        self.zoom_ratio = zoom_ratio
        self.max_blur_radius = max_blur_radius

    def zoom_in_effect(self, clip):
        # Inner function to apply zoom and blur effect
        def effect(get_frame, t):
            img = Image.fromarray(get_frame(t))
            base_size = img.size

            # Calculate the gradual blur based on time `t`
            blur_radius = self.max_blur_radius * (t / clip.duration)

            # Apply Gaussian blur
            img = img.filter(ImageFilter.GaussianBlur(radius=blur_radius))

            # Calculate new size for the zoom effect
            new_size = [
                math.ceil(img.size[0] * (1 + (self.zoom_ratio * t))),
                math.ceil(img.size[1] * (1 + (self.zoom_ratio * t)))
            ]

            # Ensure new dimensions are even
            new_size[0] = new_size[0] + (new_size[0] % 2)
            new_size[1] = new_size[1] + (new_size[1] % 2)

            # Resize and crop to create zoom effect
            img = img.resize(new_size, Image.LANCZOS)
            x = math.ceil((new_size[0] - base_size[0]) / 2)
            y = math.ceil((new_size[1] - base_size[1]) / 2)
            img = img.crop([
                x, y, new_size[0] - x, new_size[1] - y
            ]).resize(base_size, Image.LANCZOS)

            # Convert back to a numpy array
            result = np.array(img)
            img.close()

            return result

        # Apply the effect to the clip
        return clip.fl(effect)
