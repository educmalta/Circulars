"""Microsoft Graph device-code client to download files from a SharePoint/OneDrive folder (recursive).

Usage:
- Set GRAPH_CLIENT_ID (optional) and GRAPH_TENANT (optional) as env vars.
- Call sync_sharepoint_folder(remote_path, local_target_folder) to recursively download PDF/DOCX/DOC files from remote path and all subfolders.
- This uses device-code flow which needs interactive approval the first time.
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


def acquire_token_device():
    app = PublicClientApplication(client_id=CLIENT_ID or "", authority=GRAPH_AUTHORITY)
    flow = app.initiate_device_flow(scopes=GRAPH_SCOPES)
    if 'user_code' not in flow:
        raise RuntimeError('Failed to start device code flow: ' + json.dumps(flow))
    print('To sign in, open:', flow['verification_uri'])
    print('Enter code:', flow['user_code'])
    result = app.acquire_token_by_device_flow(flow)
    if 'access_token' in result:
        return result['access_token']
    raise RuntimeError('Failed to acquire token: ' + json.dumps(result))


def list_children(access_token, path=None):
    """Yield items directly under the specified path (handles pagination)."""
    if path:
        url = f"{GRAPH_API}/me/drive/root:/{path}:/children"
    else:
        url = f"{GRAPH_API}/me/drive/root/children"
    while url:
        resp = requests.get(url, headers={'Authorization': f'Bearer {access_token}'})
        resp.raise_for_status()
        data = resp.json()
        for item in data.get('value', []):
            yield item
        url = data.get('@odata.nextLink')


def list_drive_items_recursive(access_token, base_path=None):
    """Recursively yield (rel_path, item) for all items under base_path."""
    def _recurse(current_path, rel_prefix=''):
        for item in list_children(access_token, current_path):
            name = item.get('name')
            if item.get('folder'):
                new_path = f"{current_path}/{name}" if current_path else name
                new_rel = os.path.join(rel_prefix, name) if rel_prefix else name
                # yield folder marker
                yield (new_rel, item)
                yield from _recurse(new_path, new_rel)
            else:
                rel = os.path.join(rel_prefix, name) if rel_prefix else name
                yield (rel, item)
    start = base_path.strip('/') if base_path else ''
    yield from _recurse(start, '')


def download_item(access_token, download_url, target_path):
    headers = {'Authorization': f'Bearer {access_token}'}
    with requests.get(download_url, headers=headers, stream=True) as r:
        r.raise_for_status()
        os.makedirs(os.path.dirname(target_path), exist_ok=True)
        with open(target_path, 'wb') as f:
            for chunk in r.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)


def sync_sharepoint_folder(remote_path, local_target_folder):
    """Recursively download files from remote_path into local_target_folder, preserving folder structure."""
    os.makedirs(local_target_folder, exist_ok=True)
    token = acquire_token_device()
    downloaded = []
    for rel, item in list_drive_items_recursive(token, remote_path):
        # skip folders
        if item.get('folder'):
            continue
        name = item.get('name', '')
        if not name.lower().endswith(('.pdf', '.docx', '.doc')):
            continue
        dl = item.get('@microsoft.graph.downloadUrl')
        local_path = os.path.join(local_target_folder, rel)
        try:
            if dl:
                download_item(token, dl, local_path)
            else:
                drive_item_id = item.get('id')
                url = f"{GRAPH_API}/me/drive/items/{drive_item_id}/content"
                download_item(token, url, local_path)
            downloaded.append(local_path)
        except Exception as e:
            print('Failed to download', name, e)
    return downloaded


if __name__ == '__main__':
    if len(sys.argv) < 3:
        print('Usage: python sharepoint_client.py <remote_path> <local_target_folder>')
        sys.exit(1)
    remote = sys.argv[1]
    local = sys.argv[2]
    print('Syncing', remote, '->', local)
    files = sync_sharepoint_folder(remote, local)
    print('Downloaded', len(files), 'files')
