from flask import Flask
from jinja2 import Environment, FileSystemLoader

try:
    env = Environment(loader=FileSystemLoader('website/templates'))
    env.get_template('landing.html')
    env.get_template('base.html')
    print("Templates parsed successfully")
except Exception as e:
    print(f"Error parsing templates: {e}")
