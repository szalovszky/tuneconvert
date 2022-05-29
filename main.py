__name__ = "tuneconvert"
__version__ = '0.0.2'
__author__ = 'Szalovszky David'

import random
import string
import time
import logging
import argparse
import os
import shutil
import json
import sys
import traceback

import yt_dlp
import ffmpeg

import constants
from platforms import ddg_platform, startpage_platform, deezer_platform, youtube_platform, shazam_platform
from utils import data, music_data, file, output, audio, music
import settings
from checks import deezer_check, startpage_check, duckduckgo_check, shazam_check, external_check

# TODO: Fix this
# Supress Asyncio deprecation warning
import warnings
warnings.filterwarnings("ignore", category=DeprecationWarning) 

# Add arguments
parser = argparse.ArgumentParser(description="yt2deezer", formatter_class=argparse.ArgumentDefaultsHelpFormatter)

parser.add_argument("--force-year", default=False, help="Don't filter year out of metadata", action='store_true')
parser.add_argument("--force-emojis", default=False, help="Don't filter emojis out of metadata", action='store_true')
parser.add_argument("--force-unicode", default=False, help="Don't filter Unicode text out of metadata", action='store_true')

parser.add_argument("--experimental-search-ranking", default=False, help="[EXPERIMENTAL] Rank searches when querying", action='store_true')
parser.add_argument("--experimental-ddg", default=False, help="[EXPERIMENTAL] Enable DuckDuckGo as a source", action='store_true')
parser.add_argument("--experimental-bpm", default=False, help="[EXPERIMENTAL] Check source BPM and compare result's BPM", action='store_true')
parser.add_argument("--experimental-mix", default=False, help="[EXPERIMENTAL] If provided source is detected to be a mix, try to parse each song in it", action='store_true')

parser.add_argument("--no-shazam", default=False, help="Disable Shazam as a source", action='store_true')
parser.add_argument("--no-links", default=False, help="Disable DescriptionLinkParse as a source", action='store_true')
parser.add_argument("--no-deezertrack", default=False, help="Disable DeezerTrack as a source", action='store_true')
parser.add_argument("--no-deezeralbum", default=False, help="Disable DeezerAlbum as a source", action='store_true')
parser.add_argument("--no-startpage", default=False, help="Disable Startpage as a source", action='store_true')

parser.add_argument("--hook", default=False, help="Special argument", action='store_true')

parser.add_argument("URL", help="Source Playlist/Song")
parser.add_argument("destination", help="Target Platform to sync to")

args = parser.parse_args()
config = vars(args)

settings.settings = args

# Generate unique run ID
run_id = str(int(time.time())).encode('utf-8') + str(''.join(random.choices(string.ascii_uppercase + string.digits, k=8))).encode('utf-8')
run_id = data.hash(run_id)

settings.output_dir = "output/"
settings.working_dir = f"{settings.output_dir}{run_id}/"
settings.temp_dir = settings.working_dir + ".temp/"

# Create output directory
if(not os.path.exists(settings.output_dir)):
    os.mkdir(settings.output_dir)
os.mkdir(settings.working_dir)
os.mkdir(settings.temp_dir)

logging.basicConfig(filename=settings.working_dir + 'log.txt', filemode='w', encoding='utf-8', format='%(asctime)s %(message)s', level=logging.DEBUG)
settings.logger = logging.getLogger()
settings.logger.setLevel(logging.INFO)

# Create & open output files
file_overview = open(settings.working_dir + 'output.html', 'w', encoding="utf-8")
file_output = open(settings.working_dir + 'output.txt', 'w', encoding="utf-8")
file_output_json = open(settings.working_dir + 'output.json', 'w', encoding="utf-8")

json_index = 0
output_json = {}

file_fail = open(settings.working_dir + 'failed.txt', 'w', encoding="utf-8")
file_unavailable = open(settings.working_dir + 'unavailable.txt', 'w', encoding="utf-8")
file_options = open(settings.working_dir + 'options.json', 'w', encoding="utf-8")

last_video_id = ""

class info_logger:
    def debug(self, msg):
        # For compatibility with youtube-dl
        if msg.startswith('[debug] '):
            pass
        else:
            self.info(msg)

    def info(self, msg):
        current_video_id = data.text_between(msg, "[youtube]] ", ": Downloading webpage")
        if(current_video_id is not None):
            last_video_id = current_video_id
            data.prnt(f"Fetching {current_video_id}...")
        if((": Downloading " not in msg)):
            if(("[download] Downloading video " in msg) and (" of " in msg)):
                data.prnt(f"[{msg.replace('[download] Downloading video ', '')}] ", end='')
            else:
                data.prnt(msg)

    def warning(self, msg):
        data.prnt(msg)

    def error(self, msg):
        if(("removed" in msg) or ("unavailable" in msg)):
            file_unavailable.write(msg + "\n")
        data.prnt(msg)
settings.info_logger = info_logger()


class download_logger:
    def debug(self, msg):
        # For compatibility with youtube-dl, both debug and info are passed into debug
        # You can distinguish them by the prefix '[debug] '
        if msg.startswith('[debug] '):
            pass
        else:
            self.info(msg)

    def info(self, msg):
        if(not msg.startswith("[youtube] ") and ("Deleting original file" not in msg) and (not msg.startswith("[SponsorBlock] ")) and ("mismatch." not in msg) and (not msg.startswith("[ModifyChapters] SponsorBlock information")) and ("Skipping ModifyChapters" not in msg) and (not msg.startswith("[generic] "))):
            if(not msg.startswith("[download] ")):
                data.prnt(msg)
            else:
                data.prnt(msg, end='\r')

    def warning(self, msg):
        data.prnt(msg)

    def error(self, msg):
        data.prnt(msg)
settings.download_logger = download_logger()


def add_to_json(**objects):
    global output_json, json_index
    output_json[json_index] = json.loads(json.dumps(objects))
    json_index += 1


def add_result(results, result):
    if(result is not None):
        id = data.hash(result['result'][1]['id'])
        if(id in results):
            results[id]['score'] += 1.0
        else:
            results[id] = result
            results[id]['score'] += result['result'][0]
    return results


total = 1
success = 0
not_found = 0

def find(source):
    global success, not_found

    if(settings.settings.experimental_bpm):
        data.hookout(type="status", status="checking_bpm")
        data.prnt("Detecting source BPM... ", end='')
        audio.cut_leading_silence(source.filename)
        source.bpm = audio.detect_bpm(source.filename)
        data.prnt(str(source.bpm))
        data.hookout(type="bpm", bpm=source.bpm)

    results = {}
    
    add_result(results, deezer_check.track(source.title))
    add_result(results, external_check.links(source.title, source.description))
    add_result(results, startpage_check.search(source.title))
    add_result(results, deezer_check.album(source.title))
    add_result(results, shazam_check.search(source.title, source.filename))
    add_result(results, duckduckgo_check.search(source.title))

    if(len(results.items()) > 0):
        # Sort results
        results = dict(sorted(results.items(), key=lambda x: (x[1]['score'])))
        top_result = list(results.items())[-1] if len(results.items()) > 0 else [0, [0, None]]
        top_result = top_result[1]
        # Output & save result
        score = "%.2f" % top_result['score']
        result = music(title=f"{top_result['result'][1]['artist']['name']} - {top_result['result'][1]['title']}", link=top_result['result'][1]['link'])
        data.prnt(f"[SUCCESS] [{score}pts] {result.title}")
        success += 1
        data.hookout(type="status", status="found")
        add_to_json(status="found", score=score, original=source.link, found=result.link, query=source.title)
        file_overview.write(
            output.table_row(status="Success", score=score, original=source.link, original_title=source.name, found=result.link, found_title=result.title, query=source.title))
    else:
        data.prnt(f"[ERROR] Not found {source.name}")
        not_found += 1
        result = source
        file_fail.write(f"notfound:{source.link}\n")
        file_overview.write(
            output.table_row(status="Not found", original=source.link, original_title=source.name, query=source.title))
    file_output.write(f"{source.link}\n")


def handle_youtube_result(video, i=0):
    global json_index
    try:
        res = youtube_platform.parse(video, youtube_platform.parse_method.DEFAULT)
        source = music(name=video['title'], title=youtube_platform.parse(video, youtube_platform.parse_method.DEFAULT), description=video['description'], id=video['id'], link=f"https://youtu.be/{video['id']}")
        if(res is None):
            if(video is None):
                data.hookout(type="error", message="video_not_found")
                data.prnt("======")
                data.prnt(f"Video not found at index {str(i)}")
                file_fail.write(f"fatalerror:{str(i)}\n")
                file_overview.write(output.table_row(status="Video not found"))
            else:
                data.hookout(type="error", message="general_error")
                file_fail.write(f"generror:{source.link}:{source.name}\n")
                file_overview.write(output.table_row(status="Res error", original=source.link, original_title=source.name))
        else:
            data.hookout(type="status", status="checking", message=source.name)
            data.prnt("\n=== " + source.name + " ===")
            source.filename = f"{settings.temp_dir}audio.wav"
            youtube_platform.download(f"https://youtu.be/{video['id']}", source.filename)
            source.length = float(ffmpeg.probe(source.filename)['format']['duration']).__floor__()
            if(not youtube_platform.is_mix(video=video, length=source.length)):
                data.hookout(type="data_type", dataType="track")
                find(source)
            else:
                data.prnt("[WARN] Trying experimental method to get all songs of the mix...")
                data.hookout(type="data_type", dataType="mix")
            os.remove(settings.temp_dir + "audio.wav")
        data.hookout(type="progress", now=i+1, total=total, notfound=not_found)
    except Exception as e:
        data.prnt("[ERROR] Handling error at index " + str(i))
        data.prnt(traceback.format_exc())
        file_fail.write("handleerror:" + str(i) + "\n")
        data.hookout(type="error", message="handling_error")
        file_overview.write(
            output.table_row(status="Handling error", original=source.link, original_title=source.name))

def handle_youtube(url):
    global success, not_found, total
    global loop
    info_logger_instance = info_logger()
    ydl = yt_dlp.YoutubeDL({"ignoreerrors": True, 'logger': info_logger_instance})
    with ydl:
        data.hookout(type="status", status="fetching")
        result = ydl.extract_info(url, download=False)
        data.hookout(type="status", status="parsing")
        if(result is not None):
            if 'entries' in result:
                # This is a playlist or a list of videos
                video = result['entries']
                total = len(video)

                # Loops entries to grab each video
                for i, item in enumerate(video):
                    video = result['entries'][i]
                    handle_youtube_result(video, i)
            else:
                video = result
                handle_youtube_result(video)
    
    data.prnt('============================')
    data.prnt('Finished: ' + "{:.2f}".format((success/total)*100) + "% success (Total: " + str(total) + ", Not found: " + str(not_found) + ")")
    file_output.close()
    file_fail.close()
    file_unavailable.close()
    file_options.close()

data.hookout(type="status", status="start", id=run_id)
platform = settings.settings.destination
if("deezer" in platform):
    data.prnt("Using Deezer as Target Platform")
    data.hookout(type="target_platform", platform="deezer")
else:
    data.prnt("Unsupported destination platform")
    data.hookout(type="target_platform", platform="")
    sys.exit()

file_overview.write("""<style>
* {
    font-family: arial, sans-serif;
}
table {
    border-collapse: collapse;
    width: 100%;
}
td, th {
    border: 1px solid #dddddd;
    text-align: left;
    padding: 8px;
}
tr:nth-child(even) {
    background-color: #dddddd;
}
</style>
<title>Overview</title>
<meta charset="UTF-8">
<meta name="overview-version" content="2">
<meta name="app-name" content='""" + str(__name__) + """'>
<meta name="app-author" content='""" + str(__author__) + """'>
<meta name="app-version" content='""" + str(__version__) + """'>
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<h1>Result</h1>
<h3>Run ID: <code>""" + run_id + """</code></h3>
<a href='output.txt'>Output file</a> | 
<a href='output.json'>Output JSON</a> | 
<a href='failed.txt'>Failed</a> | 
<a href='unavailable.txt'>Unavailable</a> | 
<a href='options.json'>Settings</a> | 
<a href='log.txt'>Log</a><br />
<a href='data:text/plain;charset=UTF-8,out.txt' download='output.txt'><b>Download Output file</b></a> | 
<a href='data:text/plain;charset=UTF-8,out.json' download='output.json'><b>Download Output JSON</b></a> | 
<a href='data:text/plain;charset=UTF-8,options.json' download='settings.json'><b>Download Settings</b></a><br />
<table>
<tr>
    <th>Status</th>
    <th>Score</th>
    <th>Original</th>
    <th>Found</th>
    <th>Query</th>
</tr>""")
dict_settings = settings.settings.__dict__
dict_settings['name'] = __name__
dict_settings['author'] = __author__
dict_settings['version'] = __version__
file_options.write(json.dumps(dict_settings))
url = settings.settings.URL
if("youtu" in url):
    data.hookout(type="source_platform", platform="youtube")
    handle_youtube(url)
else:
    data.prnt("Unsupported source platform")
    data.hookout(type="source_platform", platform="")
    sys.exit()
data.hookout(type="result", result=output_json)
file_output_json.write(json.dumps(output_json))
file_overview.write("</table>")
shutil.rmtree(settings.temp_dir)
data.hookout(type="status", status="end", id=run_id)