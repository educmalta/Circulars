import os
import sys
# ensure repo on path
sys.path.insert(0, os.getcwd())
from sharepoint_client import sync_sharepoint_folder

remote = 'Circulars/2026'
local = os.path.join(os.getcwd(), 'sharepoint_downloads', 'Circulars_2026')
os.makedirs(local, exist_ok=True)
print('Starting SharePoint sync for remote path:', remote)
print('Local target folder:', local)
print('Note: this will prompt for device-code sign-in. Follow the printed URL and code to authenticate.')
files = sync_sharepoint_folder(remote, local)
print('\nDownloaded_count:', len(files))
for f in files[:200]:
    print(f)

# trigger a local scan of the downloaded folder
try:
    from processor import scan_folder, DB_PATH
    scan_folder([local], DB_PATH)
    print('\nRescan complete.')
except Exception as e:
    print('Rescan failed:', e)
