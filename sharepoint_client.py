"""Minimal Microsoft Graph device-code client to download files from a SharePoint/OneDrive folder.

Usage:
- Set environment variable GRAPH_CLIENT_ID to a registered app's client id (public client). If not set, the code will still attempt MSAL device flow but some tenants require a client id.
- Call sync_sharepoint_folder(site_drive_path, local_target_folder) to download matching PDF/DOCX files from the target path to local folder.

Notes:
- This is optional; the recommended approach remains to sync the SharePoint folder locally with OneDrive and point CIRCULAR_RAW_FOLDERS to that local path.
- Device code flow will prompt the operator to open a URL and enter a code to grant the app permissions.
"""
import os
import sys
import json
import time
import requests
from msal import PublicClientApplication

GRAPH_SCOPES = ["Files.Read.All", "offline_access"]

CLIENT_ID = os.environ.get('GRAPH_CLIENT_ID')
TENANT = os.environ.get('GRAPH_TENANT', 'common')

GRAPH_AUTHORITY = f"https://login.microsoftonline.com/{TENANT}"
GRAPH_API = "https://graph.microsoft.com/v1.0"

# Helper: perform device-code flow and return access token
def acquire_token_device():
    app = PublicClientApplication(client_id=CLIENT_ID or "", authority=GRAPH_AUTHORITY)
    flow = app.initiate_device_flow(scopes=GRAPH_SCOPES)
    if 'user_code' not in flow:
        raise RuntimeError('Failed to start device code flow: ' + json.dumps(flow))
    print('To sign in, open', flow['verification_uri'], 'and enter code:', flow['user_code'])
    # poll
    result = app.acquire_token_by_device_flow(flow)
    if 'access_token' in result:
        return result['access_token']
    raise RuntimeError('Failed to acquire token: ' + json.dumps(result))


def list_drive_items_by_path(access_token, drive_id=None, site_id=None, path=None):
    headers = {'Authorization': f'Bearer {access_token}'}
    # If site_id provided, use /sites/{site_id}/drive/root:/path:/children
    if site_id:
        url = f"{GRAPH_API}/sites/{site_id}/drive/root:/{path}:/children"
    elif drive_id:
        url = f"{GRAPH_API}/drives/{drive_id}/root:/{path}:/children"
    else:
        url = f"{GRAPH_API}/me/drive/root:/{path}:/children"
    resp = requests.get(url, headers=headers)
    resp.raise_for_status()
    return resp.json().get('value', [])


def download_item(access_token, download_url, target_path):
    headers = {'Authorization': f'Bearer {access_token}'}
    with requests.get(download_url, headers=headers, stream=True) as r:
        r.raise_for_status()
        with open(target_path, 'wb') as f:
            for chunk in r.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)


def sync_sharepoint_folder(remote_path, local_target_folder):
    """Sync files from a SharePoint/OneDrive remote folder path (relative) into a local folder.

    remote_path: like 'Documents/Circulars/2026' or 'Circulars/2026'
    local_target_folder: local folder to save files
    """
    os.makedirs(local_target_folder, exist_ok=True)
    token = acquire_token_device()
    # list items
    items = list_drive_items_by_path(token, path=remote_path)
    downloaded = []
    for item in items:
        if item.get('folder'):
            continue
        name = item.get('name', '')
        if not name.lower().endswith(('.pdf', '.docx', '.doc')):
            continue
        # get downloadUrl if provided in @microsoft.graph.downloadUrl
        dl = item.get('@microsoft.graph.downloadUrl')
        target = os.path.join(local_target_folder, name)
        try:
            if dl:
                download_item(token, dl, target)
                downloaded.append(target)
            else:
                # fallback: use content endpoint
                drive_item_id = item.get('id')
                url = f"{GRAPH_API}/me/drive/items/{drive_item_id}/content"
                download_item(token, url, target)
                downloaded.append(target)
        except Exception as e:
            print('Failed to download', name, e)
    return downloaded


if __name__ == '__main__':
    # quick CLI for manual sync
    if len(sys.argv) < 3:
        print('Usage: python sharepoint_client.py <remote_path> <local_target_folder>')
        sys.exit(1)
    remote = sys.argv[1]
    local = sys.argv[2]
    print('Syncing', remote, '->', local)
    files = sync_sharepoint_folder(remote, local)
    print('Downloaded', len(files), 'files')
