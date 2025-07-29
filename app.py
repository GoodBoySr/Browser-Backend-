from flask import Flask, request, Response, stream_with_context
from flask_cors import CORS
import requests
import os

app = Flask(__name__)

# IMPORTANT: For production, change this to your Vercel frontend domain!
# Example: CORS(app, origins=["https://your-vercel-app.vercel.app"])
CORS(app) 

# Health check endpoint for Railway
@app.route('/')
def health_check():
    return "Python Proxy server is running!"

# Proxy endpoint
@app.route('/proxy', methods=['GET', 'POST', 'PUT', 'DELETE'])
def proxy():
    target_url = request.args.get('url')

    if not target_url:
        return "Missing target URL. Please provide a `url` query parameter.", 400

    # Ensure the URL has a protocol, default to https if missing
    if not target_url.startswith('http://') and not target_url.startswith('https://'):
        target_url = f"https://{target_url}"

    print(f"Proxying request for: {target_url}")

    try:
        # Prepare headers to forward, excluding hop-by-hop headers and potentially problematic ones
        headers = {key: value for key, value in request.headers if key.lower() not in [
            'host', 'connection', 'keep-alive', 'proxy-authenticate',
            'proxy-authorization', 'te', 'trailers', 'transfer-encoding', 'upgrade',
            'x-forwarded-for', 'x-real-ip', # Proxy itself will add these or similar
            'cookie' # Removed cookies as they often cause issues with simple proxies unless explicitly handled
        ]}

        # Perform the request to the target URL
        resp = requests.request(
            method=request.method,
            url=target_url,
            headers=headers,
            data=request.get_data(),
            params=request.args,
            stream=True,
            allow_redirects=True,
            timeout=30 # Increased timeout for potentially slow sites
            # verify=False # Uncomment only if absolutely necessary and you understand the security risks
        )

        # Create a Flask Response object
        response = Response(stream_with_context(resp.iter_content(chunk_size=8192)), status=resp.status_code)

        # Copy all headers from the target response to our response
        excluded_headers = [
            'content-encoding', 'content-length', 'transfer-encoding', 'connection',
            'set-cookie' # Handle set-cookie headers carefully, often needs re-writing
        ]
        for header, value in resp.headers.items():
            if header.lower() not in excluded_headers:
                response.headers[header] = value
        
        # Explicitly remove X-Frame-Options and Content-Security-Policy to allow embedding
        # This is critical for most websites to load in an iframe via a proxy.
        if 'X-Frame-Options' in response.headers:
            del response.headers['X-Frame-Options']
        if 'Content-Security-Policy' in response.headers:
            del response.headers['Content-Security-Policy']

        return response

    except requests.exceptions.RequestException as e:
        print(f"Proxy request error: {e}")
        return f"Proxy Error: Could not reach the target website or an internal error occurred: {e}", 500
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        return f"An unexpected error occurred: {e}", 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True) # debug=True is for local development. Railway handles this differently.
      
