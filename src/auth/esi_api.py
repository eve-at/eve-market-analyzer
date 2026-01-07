"""ESI API Client for EVE Online"""
import requests
from datetime import datetime, timedelta
import importlib


def _get_settings():
    """Reload and get settings"""
    import settings
    importlib.reload(settings)
    return settings


class ESIAPI:
    """ESI API Client for EVE Online"""

    TOKEN_URL = "https://login.eveonline.com/v2/oauth/token"
    ESI_BASE_URL = "https://esi.evetech.net/latest"

    def __init__(self):
        settings = _get_settings()
        self.client_id = settings.EVE_CLIENT_ID
        self.client_secret = settings.EVE_CLIENT_SECRET

    def refresh_access_token(self, refresh_token):
        """Refresh access token using refresh token

        Args:
            refresh_token: Refresh token from database

        Returns:
            dict: {
                'access_token': str,
                'expires_in': int,
                'token_expiry': datetime
            } or None if failed
        """
        try:
            response = requests.post(
                self.TOKEN_URL,
                auth=(self.client_id, self.client_secret),
                data={
                    'grant_type': 'refresh_token',
                    'refresh_token': refresh_token
                },
                headers={'Content-Type': 'application/x-www-form-urlencoded'}
            )

            if response.status_code == 200:
                data = response.json()
                expires_in = data.get('expires_in', 1200)  # Default 20 minutes
                token_expiry = datetime.now() + timedelta(seconds=expires_in)

                return {
                    'access_token': data['access_token'],
                    'expires_in': expires_in,
                    'token_expiry': token_expiry
                }
            else:
                print(f"Failed to refresh token: {response.status_code} - {response.text}")
                return None

        except Exception as e:
            print(f"Error refreshing access token: {e}")
            return None

    def get_character_orders_history(self, character_id, access_token, page=1):
        """Get character order history from ESI API

        Args:
            character_id: Character ID
            access_token: Valid access token
            page: Page number (default 1)

        Returns:
            tuple: (orders_list, has_more_pages) or (None, False) if failed
        """
        try:
            url = f"{self.ESI_BASE_URL}/characters/{character_id}/orders/history/"
            headers = {
                'Authorization': f'Bearer {access_token}'
            }
            params = {
                'page': page
            }

            response = requests.get(url, headers=headers, params=params)

            if response.status_code == 200:
                orders = response.json()
                # Check if there are more pages by looking at X-Pages header
                total_pages = int(response.headers.get('X-Pages', 1))
                has_more_pages = page < total_pages
                return (orders, has_more_pages)
            elif response.status_code == 404:
                # Page doesn't exist - no more data
                return ([], False)
            else:
                print(f"Failed to fetch orders history: {response.status_code} - {response.text}")
                return (None, False)

        except Exception as e:
            print(f"Error fetching character orders history: {e}")
            return (None, False)

    def fetch_all_character_orders_history(self, character_id, access_token, progress_callback=None):
        """Fetch all pages of character order history

        Args:
            character_id: Character ID
            access_token: Valid access token
            progress_callback: Optional callback function(page, total_orders, inserted, skipped)

        Returns:
            list: All orders from all pages
        """
        all_orders = []
        page = 1
        total_inserted = 0
        total_skipped = 0

        while True:
            if progress_callback:
                progress_callback(page, len(all_orders), total_inserted, total_skipped, f"Fetching page {page}...")

            orders, has_more = self.get_character_orders_history(character_id, access_token, page)

            if orders is None:
                # Error occurred
                if progress_callback:
                    progress_callback(page, len(all_orders), total_inserted, total_skipped, f"Error fetching page {page}")
                break

            if not orders:
                # No more data
                if progress_callback:
                    progress_callback(page, len(all_orders), total_inserted, total_skipped, "Completed!")
                break

            all_orders.extend(orders)

            if progress_callback:
                progress_callback(page, len(all_orders), total_inserted, total_skipped, f"Fetched {len(orders)} orders from page {page}")

            if not has_more:
                if progress_callback:
                    progress_callback(page, len(all_orders), total_inserted, total_skipped, "Completed!")
                break

            page += 1

        return all_orders
