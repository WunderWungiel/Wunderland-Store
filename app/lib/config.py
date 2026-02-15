import yaml
import os

path = os.path.join(os.path.dirname(os.path.realpath(__file__)), "..", "config.yaml")

with open(path, "r") as f:
    config = yaml.safe_load(f.read())
