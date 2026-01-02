"""EVE Online SSO Authentication"""
import requests
import secrets
import webbrowser
from urllib.parse import urlencode
import http.server
import socketserver
from threading import Thread
import importlib


def _get_settings():
    """Reload and get settings"""
    import settings
    importlib.reload(settings)
    return settings


class EVESSO:
    """EVE Online SSO Authentication Handler"""

    # EVE SSO endpoints
    AUTHORIZE_URL = "https://login.eveonline.com/v2/oauth/authorize"
    TOKEN_URL = "https://login.eveonline.com/v2/oauth/token"
    VERIFY_URL = "https://esi.evetech.net/verify/"

    # Local callback server settings
    CALLBACK_HOST = "localhost"
    CALLBACK_PORT = 8888
    CALLBACK_URL = f"http://{CALLBACK_HOST}:{CALLBACK_PORT}/callback"

    def __init__(self):
        settings = _get_settings()
        self.client_id = settings.EVE_CLIENT_ID
        self.client_secret = settings.EVE_CLIENT_SECRET
        self.scopes = settings.EVE_SCOPES

        self.state = None
        self.auth_code = None
        self.callback_server = None
        self.callback_thread = None

    def start_login(self, callback_func=None):
        """Start the EVE SSO login process

        Args:
            callback_func: Function to call when authentication is complete.
                          Receives character_data dict as parameter.
        """
        # Generate state for CSRF protection
        self.state = secrets.token_urlsafe(32)

        # Start local callback server
        self._start_callback_server(callback_func)

        # Build authorization URL
        params = {
            'response_type': 'code',
            'redirect_uri': self.CALLBACK_URL,
            'client_id': self.client_id,
            'state': self.state,
            'scope': self.scopes  # Use scopes from settings.py
        }

        auth_url = f"{self.AUTHORIZE_URL}?{urlencode(params)}"

        # Open browser for user to authorize
        webbrowser.open(auth_url)

        print(f"Opening browser for EVE Online authentication...")
        print(f"Waiting for callback at {self.CALLBACK_URL}")

    def _start_callback_server(self, callback_func):
        """Start local HTTP server to handle OAuth callback"""

        class CallbackHandler(http.server.SimpleHTTPRequestHandler):
            sso_instance = self

            def do_GET(handler_self):
                """Handle GET request from OAuth callback"""
                if handler_self.path.startswith('/callback'):
                    # Parse query parameters
                    from urllib.parse import urlparse, parse_qs
                    query = urlparse(handler_self.path).query
                    params = parse_qs(query)

                    # Check state
                    if params.get('state', [''])[0] != self.state:
                        handler_self.send_error(400, "Invalid state parameter")
                        return

                    # Get authorization code
                    auth_code = params.get('code', [''])[0]

                    if auth_code:
                        # Send success response to browser
                        handler_self.send_response(200)
                        handler_self.send_header('Content-type', 'text/html')
                        handler_self.end_headers()
                        handler_self.wfile.write(b"""
                            <html>
                            <body>
                                <h2>Authentication Successful!</h2>
                                <p>You can close this window and return to the application.</p>
                                <script>window.close();</script>
                            </body>
                            </html>
                        """)

                        # Exchange code for tokens
                        character_data = self._exchange_code_for_tokens(auth_code)

                        # Stop server
                        Thread(target=self._stop_server).start()

                        # Call callback function
                        if callback_func and character_data:
                            callback_func(character_data)
                    else:
                        handler_self.send_error(400, "No authorization code received")

            def log_message(handler_self, format, *args):
                """Suppress server logs"""
                pass

        # Start server in separate thread
        self.callback_server = socketserver.TCPServer(
            (self.CALLBACK_HOST, self.CALLBACK_PORT),
            CallbackHandler
        )

        self.callback_thread = Thread(target=self.callback_server.serve_forever, daemon=True)
        self.callback_thread.start()

    def _stop_server(self):
        """Stop the callback server"""
        if self.callback_server:
            self.callback_server.shutdown()
            self.callback_server.server_close()

    def _exchange_code_for_tokens(self, auth_code):
        """Exchange authorization code for access and refresh tokens

        Returns:
            dict: Character data including tokens and character info
        """
        try:
            # Request tokens
            data = {
                'grant_type': 'authorization_code',
                'code': auth_code,
                'client_id': self.client_id,
                'client_secret': self.client_secret
            }

            response = requests.post(self.TOKEN_URL, data=data, timeout=10)
            response.raise_for_status()

            tokens = response.json()
            access_token = tokens.get('access_token')
            refresh_token = tokens.get('refresh_token')

            # Verify token and get character info
            headers = {
                'Authorization': f'Bearer {access_token}'
            }

            verify_response = requests.get(self.VERIFY_URL, headers=headers, timeout=10)
            verify_response.raise_for_status()

            character_info = verify_response.json()

            # Get character portrait
            character_id = character_info.get('CharacterID')
            portrait_url = f"https://images.evetech.net/characters/{character_id}/portrait?size=128"

            return {
                'character_id': character_id,
                'character_name': character_info.get('CharacterName'),
                'character_portrait_url': portrait_url,
                'access_token': access_token,
                'refresh_token': refresh_token,
                'token_expiry': None  # TODO: Calculate expiry from expires_in
            }

        except requests.exceptions.RequestException as e:
            print(f"Error exchanging code for tokens: {e}")
            return None
        except Exception as e:
            print(f"Unexpected error during token exchange: {e}")
            return None
