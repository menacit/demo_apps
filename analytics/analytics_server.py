#!/usr/bin/env python3

'''
> analytics - Provides analytical insights into cocktail recipes.

Example usage:

GET /api/top/5 : Return a list of the five most common cocktail ingredients.
GET / : Health/Readiness end-point.

Listens for HTTP on port 1338/TCP by default.
Settings configurable using environment variables:

"APP_DEBUG_LOGGING":
If set to "enabled", debug log messages are included.
If set to "disabled", debug log messages are excluded.
Default:
"disabled"

"APP_RECIPES_URL":
Base HTTP(S) URL to "recipes" API without path.
'''

import os
import sys
import random
import platform
import collections
import logging as log

# -----------------------------------------------------------------------------
# Configure log level -
# Reads environment variable "APP_DEBUG_LOGGING" and validates that it contains
# an acceptable value (either "enabled" or "disabled")
log_format = '%(levelname)s: %(message)s'
debug_option = os.getenv('APP_DEBUG_LOGGING', 'disabled')

if debug_option == 'enabled':
    log.basicConfig(format=log_format, level=log.DEBUG)
    log.debug('Debug logging is enabled!')

elif debug_option != 'disabled':
    log.basicConfig(format=log_format, level=log.ERROR)
    log.error(
        'Value of environment variable "APP_DEBUG_LOGGING" '
        f'must be "enabled" or "disabled", not "{debug_option}" - exiting!')

    sys.exit(1)

else:
    log.basicConfig(format=log_format, level=log.INFO)

# -----------------------------------------------------------------------------
# Validate source URL -
# Reads environment variable "APP_RECIPES_URL" and validates that its value
# starts with either "http://" or "https://"
RECIPES_URL = os.getenv('APP_RECIPES_URL')

if not RECIPES_URL:
    log.error('Required environment variable "APP_RECIPES_URL" is not set')
    sys.exit(1)

log.debug(
    f'Checking that cocktail source data URL "{RECIPES_URL} is using HTTP(S)')

if not (
    RECIPES_URL.startswith('http://') or RECIPES_URL.startswith('https://')):

    log.error(
        f'The specified recipes base URL "{RECIPES_URL}" does not start ' +
        'with "http://" or "https://" as required - exiting!')

    sys.exit(1)

# -----------------------------------------------------------------------------
# Extract information about runtime environment for debugging
HOST_NAME = platform.node()
K8S_NODE_NAME = os.getenv('K8S_NODE_NAME')

if K8S_NODE_NAME:
    HOST_STRING = f'pod {HOST_NAME} on node {K8S_NODE_NAME}'

else:
    HOST_STRING = f'host {HOST_NAME}'

# -----------------------------------------------------------------------------
# Import third-party Python dependencies -
# Tries to load required Python modules that not included in standard library
log.debug('Trying to load/import third-party Python dependencies')

try:
    from flask import Flask, jsonify
    from requests import get as http_get

except Exception as error_message:
    log.error(f'Failed to import third-party Python module: {error_message}')
    sys.exit(1)

# -----------------------------------------------------------------------------
log.debug('Setting up Flask application')
app = Flask('analytics')

    
# -----------------------------------------------------------------------------
@app.after_request
def append_debug_headers(response):
    response.headers['X-Provided-By'] = HOST_STRING
    return response


# -----------------------------------------------------------------------------
@app.route('/')
def return_health():
    return f'Hello from analytics API server on {HOST_STRING}!\n'


# -----------------------------------------------------------------------------
@app.route('/api/top/<int:limit>')
def return_top_ingredients(limit):
    log.info(
        f'Handling analytics request for the {limit} most common ingredients')
    
    log.info(f'Fetching recipe data for analysis from "{RECIPES_URL}"')
    
    try:
        recipes_response = http_get(RECIPES_URL + '/api/list')
        recipes_response.raise_for_status()
        recipes = recipes_response.json()
        
    except Exception as error_message:
        log.error(
            f'Failed to fetch data from "{RECIPES_URL}": "{error_message}"')

        return jsonify('Failed to fetch recipe data for analysis'), 500

    all_ingredients = []

    for recipe in recipes:
        for item in recipe['ingredients']:
            if not 'ingredient' in item.keys():
                continue

            all_ingredients.append(item['ingredient'])

    most_common_ingredients = [
        i[0] for i in collections.Counter(all_ingredients).most_common(limit)]

    log.debug(
        f'Generated response for {limit} most common ingredients: ' +
        ', '.join(most_common_ingredients))
    
    return jsonify(most_common_ingredients)


# -----------------------------------------------------------------------------
# If run as a program, start web server
if __name__ == '__main__':
    log.info('Starting analytics web server on ' + HOST_STRING)
    
    app.run(host='0.0.0.0', port=1338)
