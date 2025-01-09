import logging

class LoggerManager:
    def __init__(self):
        # Set up a default level for all loggers
        self.default_level = logging.WARNING
        logging.basicConfig(level=self.default_level)  # Basic configuration

    def list_loggers(self):
        # Retrieve and print all existing loggers
        logger_dict = logging.root.manager.loggerDict
        for logger_name, logger_obj in logger_dict.items():
            if isinstance(logger_obj, logging.Logger):
                effective_level = logger_obj.getEffectiveLevel()
                print(f"Logger: {logger_name}, Level: {logging.getLevelName(effective_level)}")

    def set_log_level(self, module_name, level):
        # Set log level for a specific module
        logger = logging.getLogger(module_name)
        logger.setLevel(level)
        # print(f"Set log level for {module_name} to {logging.getLevelName(level)}")

    @staticmethod
    def setup_loggers():
        # Instantiate LoggerManager
        logger_manager = LoggerManager()

        # Set log levels explicitly for noisy modules and their submodules
        noisy_modules = [
            "urllib3", "urllib3.connection", "urllib3.connectionpool", "urllib3.response",
            "google.auth", "google.cloud", "google.api_core"
        ]
        for module in noisy_modules:
            logger_manager.set_log_level(module, logging.WARNING)  # Set to WARNING to reduce noise

        # List loggers after setting levels
        # print("\nUpdated logger setup:")
        # logger_manager.list_loggers()

# Run the test program to see logger configurations
if __name__ == "__main__":
    LoggerManager.setup_loggers()