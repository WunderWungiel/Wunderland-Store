import json
import os

config = json.loads(open(os.path.join(os.path.dirname(os.path.realpath(__file__)), "..", "config.json"), "r").read())
