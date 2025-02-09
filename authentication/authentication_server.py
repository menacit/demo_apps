#!/usr/bin/env python3

'''
> authentication - Faux user authentication service.

Example usage:

GET /api/check/<TOKEN> : Returns username for validated tokens. 
GET /login?redirect=/test : Displays user selection page.
GET /login?redirect=/test&user=bob Authenticates client as Bob.
GET /healthz : Health/Readiness end-point.

Listens for HTTP on port 8000/TCP by default.
Settings configurable using environment variables:

"APP_DEBUG_LOGGING":
If set to "enabled", debug log messages are included.
If set to "disabled", debug log messages are excluded.
Default:
"disabled"

"APP_SIGNING_SECRET":
Passphrase used to sign authentication tokens.
'''

USERS=['alice', 'bob', 'charlie']

import os
import sys
import time
import platform
import urllib.parse
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
SIGNING_SECRET = os.getenv('APP_SIGNING_SECRET')

if not SIGNING_SECRET:
    log.error('Required environment variable "APP_SIGNING_SECRET" is not set')
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
    import jwt
    from flask import (
        Flask, request, redirect, jsonify, render_template, make_response)

except Exception as error_message:
    log.error(f'Failed to import third-party Python module: {error_message}')
    sys.exit(1)

# -----------------------------------------------------------------------------
log.debug('Setting up Flask application')
app = Flask('authentication')

    
# -----------------------------------------------------------------------------
@app.after_request
def append_debug_headers(response):
    response.headers['X-Provided-By'] = HOST_STRING
    return response


# -----------------------------------------------------------------------------
@app.route('/healthz')
def return_health():
    return f'Hello from authentication server on {HOST_STRING}!\n'


# -----------------------------------------------------------------------------
@app.route('/login')
def return_gui():
    log.info('Generating redirect or HTML page for authentication GUI')

    redirect_url = request.args.get('redirect_url')
    user = request.args.get('user')

    if not redirect_url:
        return 'Request missing mandatory URL parameter "redirect_url"', 400

    if user:
        log.info(f'Redirecting user "{user}" to "{redirect_url}"')

        token = jwt.encode(
            {'user': user, 'exp': int(time.time()) + 900},
            SIGNING_SECRET, algorithm='HS256')

        response = make_response(redirect(redirect_url))
        response.set_cookie('user_token', value=token, max_age=780)
        return response

    log.debug('Generating template data for authentication HTML page')
    template_data = []

    for user in USERS:
        query_parameters = urllib.parse.urlencode(
            {'redirect_url': redirect_url, 'user': user})
        
        template_data.append(
            {'name': user, 'target_url': '?' + query_parameters})

    return render_template('gui.html.jinja', users=template_data)


# -----------------------------------------------------------------------------
@app.route('/api/check/<token>')
def check_token(token):
    log.info('Handling authentication token validation request')

    if not token:
        log.info('Received an empty token - treating as invalid')
        return jsonify('')

    log.debug('Decoding token as JWT')
    
    try:
        payload = jwt.decode(token, SIGNING_SECRET, algorithms=['HS256'])
        extracted_user = payload['user']

    except jwt.ExpiredSignatureError:
        log.info('Received an expired token - treating as invalid')
        return jsonify('')
        
    except Exception as error_message:
        log.warning(
            f'Failed to validate authentication token: "{error_message}"')

        return jsonify('Failed to validate authentication token'), 500

    log.info(f'Extracted user "{extracted_user}" from authentication token') 
    return jsonify(extracted_user)


# -----------------------------------------------------------------------------
# If run as a program, start web server
if __name__ == '__main__':
    log.info('Starting authentication web server on ' + HOST_STRING)
    
    app.run(host='0.0.0.0', port=8000)
