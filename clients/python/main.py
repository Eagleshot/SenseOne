# TODO Make a python library to interact with the API that can get the config, upload images, upload sensor data.

import requests


class EagleshotAPI:
    """A simple Python library to interact with the Eagleshot API."""
    def __init__(self, username: str, password: str, url: str = "https://api.eagleshot.org"):
        self.username = username
        self.password = password
        self.url = url

    # Get config
    # Upload images
    # Upload sensor data



if __name__ == "__main__":
    # Example usage
    api = EagleshotAPI("username", "password")
