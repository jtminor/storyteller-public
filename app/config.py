""" This module contains the configuration settings for the application. """
import os

class Config: # pylint: disable=too-few-public-methods
    ''' The config.py file is used to store the configuration settings for the application.'''
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'can-never-be-used'

class DevelopmentConfig(Config): # pylint: disable=too-few-public-methods
    ''' The DevelopmentConfig class is a subclass of the Config class and used for dev region.'''
    DEBUG = True

class TestingConfig(Config): # pylint: disable=too-few-public-methods
    ''' The TestingConfig class is a subclass of the Config class and used for test region.'''
    TESTING = True

class ProductionConfig(Config): # pylint: disable=too-few-public-methods
    ''' The ProductionConfig class is a subclass of the Config class and used for live region.'''
    DEBUG = False
