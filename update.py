import json
import traceback
import requests

from utils import data

def get_latest(releases_api_url):
    try:
        headers = {'User-Agent': 'update-checker'}
        r = requests.get(url=releases_api_url, headers=headers, timeout=10)
        if(not r.ok):
            raise requests.RequestException
        else:
            response = json.loads(r.text)
            return [response[0]['tag_name'], response[0]['html_url']]
    except Exception:
        data.prnt(f"[WARN] Couldn't check updates!: {traceback.format_exc()}")