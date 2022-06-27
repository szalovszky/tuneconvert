import requests
import traceback
import json

import constants
import settings
from utils import data

headers = {'User-Agent': '-/tuneconvert/uninitialized'}

def status():
    online_status = False
    try:
        r = requests.get(url=f"{constants.api}{settings.srv_version}", headers=headers, timeout=10)
        if(not r.ok):
            raise requests.RequestException
        else:
            response = json.loads(r.text)
            if(response['status'] != "online"):
                online_status = False
            else:
                online_status = True
    except Exception:
        online_status = False
    if(not online_status):
        data.prnt("⚠️  Tuneconvert Online is unreachable. Submission and getting cached data may not be available.")
    return online_status

def submit_result(source, result, submitter):
    if(not settings.settings.no_submission):
        try:
            source = source.__dict__ if source != None else source
            result = result.__dict__ if result != None else result
            submitter = submitter.__dict__ if submitter != None else submitter
            submission_data = {'source': source, 'result': result, 'submitter': submitter}
            r = requests.post(url=f"{constants.api}{settings.srv_version}/submit/result", json=submission_data, headers=headers)
            if(not r.ok):
                raise requests.RequestException
            else:
                response = json.loads(r.text)
                if(response['result'] != "ok"): raise Exception(f"Submission denied. Server status: {response['result']}")
        except Exception:
            data.prnt(traceback.format_exc())

def get_song(source, submitter):
    if(not settings.settings.no_submission):
        try:
            source = source.__dict__ if source != None else source
            submitter = submitter.__dict__ if submitter != None else submitter
            submission_data = {'source': source, 'submitter': submitter}
            r = requests.post(url=f"{constants.api}{settings.srv_version}/get/song", json=submission_data, headers=headers)
            if(not r.ok):
                raise requests.RequestException
            else:
                response = json.loads(r.text)
                if(response['result'] != "ok"): raise Exception(f"Get denied. Server status: {response['result']}")
                return response
        except Exception:
            data.prnt(traceback.format_exc())