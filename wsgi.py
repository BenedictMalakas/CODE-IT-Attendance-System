import os
import sys

# This file sits at the root of the repository and helps Azure find the Django app
# located inside the SYSTEMPROJECT/ subdirectory.

# Add the SYSTEMPROJECT folder to the python path
path = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(path, 'SYSTEMPROJECT'))

# Import the WSGI application from the inner Django config
from config.wsgi import application
