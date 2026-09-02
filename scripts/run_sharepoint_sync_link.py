from sharepoint_client import sync_sharepoint_from_share_link
import os

SHARE_URL = "https://ilearnedu-my.sharepoint.com/:f:/g/personal/jeffrey_zammit_ilearn_edu_mt/IgAR57ARnWszRa-QUyi26ShuAeNmQJqDTNZ44GDArwGJDTg?e=YEVPet"
TARGET = os.path.join(os.getcwd(), 'sharepoint_downloads', 'Circulars_2026')

print('Syncing share link to', TARGET)
files = sync_sharepoint_from_share_link(SHARE_URL, TARGET)
print('Downloaded', len(files), 'files')
for f in files:
    print(f)