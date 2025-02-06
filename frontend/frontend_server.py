#!/usr/bin/env python3

'''
> frontend - Provides a beautiful web app for access cocktail recipes.

Example usage:

GET /gui : Returns HTML page.
GET / : Health/Readiness end-point.

Listens for HTTP on port 8000/TCP by default.
Settings configurable using environment variables:

"APP_DEBUG_LOGGING":
If set to "enabled", debug log messages are included.
If set to "disabled", debug log messages are excluded.
Default:
"disabled"

"APP_RECIPES_URL":
Mandatory base HTTP(S) URL to "recipes" API without path.

"APP_ANALYTICS_URL":
Base HTTP(S) URL to "recipes" API without path.

"APP_FAVORITES_URL":
Base HTTP(S) URL to "favorites" API without path.

"APP_FAVORITES_ACCESS_KEY":
Access key for "favorites" API.

"APP_AUTHENTICATION_URL":
Base HTTP(S) URL to "authentication" API without path.

"APP_AUTHENTICATION_REDIRECT_URL":
(Relative) URL used for redirection of unauthenticated clients.
'''

import os
import sys
import platform
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
# Validate base URLs
APIS = ['recipes', 'analytics', 'favorites', 'authentication']
BASE_URL = {}

for api in APIS:
    log.debug('Checking if feature is "enabled": ' + api)
    base_url = os.getenv('APP_' + api.upper() + '_URL')

    if not base_url:
        log.debug('Feature is not "enabled": ' + api)
        BASE_URL[api] = ''
        continue

    log.debug('Checking if base URL for service is valid: ' + api)

    if not (base_url.startswith('http://') or base_url.startswith('https://')):
        log.error(
            f'The specified base URL "{base_url}" for the "{api}" API ' +
            'does not start with "http://" or "https://" as required')

        sys.exit(1)

    BASE_URL[api] = base_url

# -----------------------------------------------------------------------------
# Checking mandatory and "dependency" options
if not BASE_URL['recipes']:
    log.error('Missing mandatory environment variable "APP_RECIPES_URL"')
    sys.exit(1)

if BASE_URL['favorites']:
    log.debug('Validating variable for favorites API access key')
    FAVORITES_ACCESS_KEY = os.getenv('APP_FAVORITES_ACCESS_KEY')

    if not FAVORITES_ACCESS_KEY:
        log.error('Missing environment variable "APP_FAVORITES_ACCESS_KEY"')
        sys.exit(1)

if BASE_URL['authentication']:
    log.debug('Validating variable for authentication redirect URL')
    AUTHENTICATION_REDIRECT_URL = os.getenv('APP_AUTHENTICATION_REDIRECT_URL')

    if not AUTHENTICATION_REDIRECT_URL:
        log.error(
            'Missing environment variable "APP_AUTHENTICATION_REDIRECT_URL"')

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
    from flask import Flask, redirect, request, render_template, g as context
    from requests import get as http_get, post as http_post

except Exception as error_message:
    log.error(f'Failed to import third-party Python module: {error_message}')
    sys.exit(1)

# -----------------------------------------------------------------------------
log.debug('Setting up Flask application')
app = Flask('frontend')
app.url_map.strict_slashes = False
app.jinja_env.lstrip_blocks = True
app.jinja_env.trim_blocks = True

    
# -----------------------------------------------------------------------------
@app.after_request
def append_debug_headers(response):
    response.headers['X-Provided-By'] = HOST_STRING
    return response


# -----------------------------------------------------------------------------
@app.before_request
def check_authentication():
    if request.path == '/':
        return

    if not BASE_URL['authentication']:
        log.debug('User authentication is not enabled')

        context.user = 'unknown'
        return

    log.debug('Checking value of user authentication cookie')
    user_token = request.cookies.get('user_token')

    if not user_token:
        log.info(
            'No authentication cookie provided - redirecting to: ' +
            AUTHENTICATION_REDIRECT_URL)
        
        return render_template(
            'authentication_redirect.html.jinja',
            redirect_url=AUTHENTICATION_REDIRECT_URL)

    try:
        user_response = http_get(
            BASE_URL['authentication'] + '/api/check/' + user_token)

        user_response.raise_for_status()
        user = user_response.json()

    except Exception as error_message:
        log.warning(
            f'Failed to validate user authentication token: "{error_message}"')

        return 'Failed to validate user authentication token', 500

    if user:
        log.debug('Validate authentication token for user: ' + user)

        context.user = user
        return
    
    log.warning(
        'Failed to identify user - redirecting to authentication URL: ' +
        AUTHENTICATION_REDIRECT_URL)

    return render_template(
        'authentication_redirect.html.jinja',
        redirect_url=AUTHENTICATION_REDIRECT_URL)


# -----------------------------------------------------------------------------
@app.route('/')
def return_health():
    return f'Hello from frontend server on {HOST_STRING}!\n'


# -----------------------------------------------------------------------------
@app.route('/gui/add_favorite/<drink_name>')
def add_favorite(drink_name):
    log.info(f'Adding "{drink_name}" as favorite for user "{context.user}"')

    try:
        favorites_response = http_post(
            BASE_URL['favorites'] + '/api/favorites/' + context.user,
            headers={'X-Access-Key': FAVORITES_ACCESS_KEY}, json=drink_name)

        favorites_response.raise_for_status()

    except Exception as error_message:
        log.warning(
            f'Failed to add favorite drink: "{error_message}"')

        return 'Failed to add favorite', 500

    return redirect('../')


# -----------------------------------------------------------------------------
@app.route('/gui')
def return_gui():
    log.info('Rendering HTML page for cocktails GUI')

    template_data = {
        'user': context.user, 'top_ingredients': [],
        'favorites_enabled': False, 'favorites': []}

    log.debug('Fetching cocktail recipes')

    try:
        recipes_response = http_get(
            BASE_URL['recipes'] + '/api/list')

        recipes_response.raise_for_status()
        template_data['recipes'] = recipes_response.json()
        
    except Exception as error_message:
        log.warning(
            f'Failed to fetch recipe data : "{error_message}"')

        return 'Failed to fetch recipe data', 500

    if BASE_URL['analytics']:
        log.debug('Fetching analytics data')
        
        try:
            top_ingredients_response = http_get(
                BASE_URL['analytics'] + '/api/top/5')

            top_ingredients_response.raise_for_status()
            template_data['top_ingredients'] = top_ingredients_response.json()
            
        except Exception as error_message:
            log.warning(
                f'Failed to fetch analytics data : "{error_message}"')

            return 'Failed to fetch analytics data', 500
        
    if BASE_URL['favorites']:
        log.debug(f'Fetching favorites for user "{context.user}"')
        template_data['favorites_enabled'] = True
        
        try:
            favorites_response = http_get(
                BASE_URL['favorites'] + '/api/favorites/' + context.user,
                headers={'X-Access-Key': FAVORITES_ACCESS_KEY})

            favorites_response.raise_for_status()
            template_data['favorites'] = favorites_response.json()
            
        except Exception as error_message:
            log.warning(
                f'Failed to fetch favorites data : "{error_message}"')

            return 'Failed to fetch favorites data', 500

    return render_template('gui.html.jinja', **template_data)


# -----------------------------------------------------------------------------
# If run as a program, start web server
if __name__ == '__main__':
    log.info('Starting frontend web server on ' + HOST_STRING)
    
    app.run(host='0.0.0.0', port=8000)
