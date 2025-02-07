#!/usr/bin/env python3

'''
> recipes - Service for fetching and exposing IBA cocktail recipes.

Example usage:

GET /api/list : Return list of cocktail recipes.
GET /api/list?filter=God : Return list of recipes with name containg "God".
GET / : Health/Readiness end-point.

Listens for HTTP on port 1338/TCP by default.
Settings configurable using environment variables:

"APP_DEBUG_LOGGING":
If set to "enabled", debug log messages are included.
If set to "disabled", debug log messages are excluded.
Default:
"disabled"

"APP_SOURCE_URL":
Source HTTP(S) URL to IBA cocktail recipes in JSON format.
Default:
"http://raw.githubusercontent.com/teijo/iba-cocktails/master/recipes.json"

"APP_FIGLET_PATH":
Filesystem path to "Figlet" binary for ASCII art generation.
Default:
"/usr/bin/figlet"

"APP_EXCLUDED_INGREDIENTS":
Exclude cocktail recipes containing specific ingredient, separated by comma.
Default:
"Galliano,DiSaronno"
'''

import os
import sys
import random
import platform
import subprocess
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
# Reads environment variable "APP_SOURCE_URL" and validates that its value
# starts with either "http://" or "https://"
SOURCE_URL = os.getenv(
    'APP_SOURCE_URL',
    'http://raw.githubusercontent.com/teijo/iba-cocktails/master/recipes.json')

log.debug(
    f'Checking that cocktail source data URL "{SOURCE_URL} is using HTTP(S)')

if not (SOURCE_URL.startswith('http://') or SOURCE_URL.startswith('https://')):
    log.error(
        f'The specified cocktail source data URL "{SOURCE_URL}" does not '
        'start with "http://" or "https://" as required - exiting!')

    sys.exit(1)

# -----------------------------------------------------------------------------
# Validate third-party executable/non-Python dependency -
# Reads environment variable "APP_FIGLET_PATH" and validates that the specified
# file path both exists and is executable/runnable as an application
FIGLET_PATH = os.getenv('APP_FIGLET_PATH', '/usr/bin/figlet')
log.debug(
    f'Checking if "figlet" application exist/is executable at "{FIGLET_PATH}"')

if not (os.path.isfile(FIGLET_PATH) and os.access(FIGLET_PATH, os.X_OK)):
    log.error(
        'The third-party "figlet" application does not exist or '
        f'can not be executed from the path "{FIGLET_PATH}" - exiting!')

    sys.exit(1)

# -----------------------------------------------------------------------------
# Extract excluded ingredients -
# Reads environment variable "APP_EXCLUDED_INGREDIENTS"
EXCLUDED_INGREDIENTS = os.getenv(
    'APP_EXCLUDED_INGREDIENTS', 'Galliano,DiSaronno').lower().split(',')

# -----------------------------------------------------------------------------
# Extract information about runtime environment for debugging
HOST_NAME = platform.node()
K8S_NODE_NAME = os.getenv('K8S_NODE_NAME')
VERSION = os.getenv('APP_VERSION')

if K8S_NODE_NAME:
    HOST_STRING = f'pod {HOST_NAME} on node {K8S_NODE_NAME}'

else:
    HOST_STRING = f'host {HOST_NAME}'

if VERSION:
    HOST_STRING += f' (app {VERSION})'

# -----------------------------------------------------------------------------
# Import third-party Python dependencies -
# Tries to load required Python modules that not included in standard library
log.debug('Trying to load/import third-party Python dependencies')

try:
    from flask import Flask, request, jsonify
    from requests import get as http_get

except Exception as error_message:
    log.error(f'Failed to import third-party Python module: {error_message}')
    sys.exit(1)

# -----------------------------------------------------------------------------
log.info(f'Fetching cocktail recipe data from "{SOURCE_URL}"')

try:
    RECIPES = http_get(SOURCE_URL).json()
    log.info(f'Downloaded recipies for {len(RECIPES)} cocktails')

except Exception as error_message:
    log.error(
        f'Failed to fetch recipe data from "{SOURCE_URL}": "{error_message}"')

    sys.exit(1)

# -----------------------------------------------------------------------------
log.info('Filtering recipes for excluded ingredients')

for recipe in RECIPES:
    for item in recipe['ingredients']:
        if not 'ingredient' in item.keys():
            continue

        if not item['ingredient'].lower() in EXCLUDED_INGREDIENTS:
            continue

        log.info(
            f'Excluding recipe "{recipe["name"]}" as it contains ' +
            f'ingredient "{item["ingredient"]}"')

        RECIPES.remove(recipe)

# -----------------------------------------------------------------------------
log.info('Generating ASCII art for recipe names using Figlet')

try:
    for recipe in RECIPES:
        recipe['figlet_name'] = subprocess.run(
            [FIGLET_PATH, '-w', '120'], input=recipe['name'],
            capture_output=True, text=True, check=True).stdout

except Exception as error_message:
    log.error(f'Failed to generate ASCII art for recipe: {error_message}')
    sys.exit(1)

# -----------------------------------------------------------------------------
log.debug('Setting up Flask application')
app = Flask('recipes')

    
# -----------------------------------------------------------------------------
@app.after_request
def append_debug_headers(response):
    response.headers['X-Provided-By'] = HOST_STRING
    return response


# -----------------------------------------------------------------------------
@app.route('/')
def return_health():
    return f'Hello from recipes API server on {HOST_STRING}!\n'


# -----------------------------------------------------------------------------
@app.route('/api/list')
def return_cocktails():
    filter = request.args.get('filter')
    
    if filter:
        log.info(
            'Handling cocktail list request for recipies matching filter: ' +
            filter)

    else:
        log.info('Handling cocktail list request for all recipes')

    response_cocktails = []

    for recipe in random.sample(RECIPES, len(RECIPES)):
        if filter and not filter in cocktail['name']:
            continue

        response_cocktails.append(recipe)

    log.info(f'Returning list containing {len(response_cocktails)} cocktails')
    return jsonify(response_cocktails)


# -----------------------------------------------------------------------------
# If run as a program, start web server
if __name__ == '__main__':
    log.info('Starting recipes web server on ' + HOST_STRING)
    
    app.run(host='0.0.0.0', port=1338)
