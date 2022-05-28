__name__ = "tuneconvert"
__version__ = '0.0.1'
__author__ = 'Szalovszky David'

import random
import string
import time
import logging
import argparse
import os
import hashlib
import shutil
import json
import asyncio
import sys
import traceback

import yt_dlp
import ffmpeg

import constants
from platforms import ddg_platform, startpage_platform, deezer_platform, youtube_platform, shazam_platform
from utils import data, music_data, file, output, audio
import settings

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
h = hashlib.new('md5')
h.update(run_id)
run_id = h.hexdigest()

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


def parse_video(video, forceMethod=0):
    if(video is None):
        return None
    if(forceMethod == 0):
        # Get Artist and Title field from YouTube
        if("artist" not in video):
            # No copyright field, try to parse it from video title
            x = video['title'].lower().split(" - ")
            if(len(x) > 1):
                artist = x[0]
                title = x[1]
            else:
                artist = ""
                title = x[0]
        else:
            # There is a copyright field on the video, use that
            artist = video['artist'].lower()
            title = video['track'].lower()
    elif(forceMethod == 1):
        artist = video['uploader']
        title = video['title']
    elif(forceMethod == 2):
        artist = ""
        title = video['title']

    return music_data.filter_data(
            artist=artist, title=title, filter_list=constants.dontneed, 
            filter_word_list=constants.dontneed_wholeword)


loop = asyncio.get_event_loop()

total = 1
success = 0
not_found = 0

def handle_res(video, i=0):
    global success, not_found
    global json_index
    try:
        res = parse_video(video)
        if(res is None):
            if(video is None):
                data.hookout(type="error", message="video_not_found")
                data.prnt("======")
                data.prnt("Video not found at index " + str(i))
                file_fail.write("fatalerror:" + str(i) + "\n")
                file_overview.write(output.table_row(status="Video not found"))
            else:
                data.hookout(type="error", message="general_error")
                file_fail.write("generror:https://youtu.be/" + video['id'] + ":" + video['title'] + "\n")
                file_overview.write(output.table_row(status="Res error", original="<a target='_blank' href='https://youtu.be/" + video['id'] + "'>" + video['title'] + "</a>"))
        else:
            data.hookout(type="status", status="checking", message=video['title'])
            data.prnt("\n=== " + video['title'] + " ===")
            src = 0
            src_bpm = 0
            tsuccess = False
            youtube_platform.download(f"https://youtu.be/{video['id']}", settings.temp_dir)
            if(settings.settings.experimental_bpm):
                data.hookout(type="status", status="checking_bpm")
                data.prnt("Detecting source BPM... ", end='')
                audio.cut_leading_silence(settings.temp_dir + "audio.wav")
                src_bpm = audio.detect_bpm(settings.temp_dir + "audio.wav")
                data.prnt(str(src_bpm))
                data.hookout(type="bpm", bpm=src_bpm)
            while(not tsuccess):
                if(src < len(constants.src_names)):
                    src_name = constants.src_name(src)
                featured_artist = False
                used_src = False
                if(src == 0):
                    if(not settings.settings.no_deezertrack):
                        data.prnt("[INFO] Searching using " + src_name + "...")
                        data.hookout(type="status", status="checking_src", message=src_name)
                        used_src = True
                        parsed_video = parse_video(video)
                        res = " ".join(parsed_video)
                        deezer_result = deezer_platform.search_track(res)
                        res = parsed_video
                        if(deezer_result is not None):
                            tsuccess = True
                elif(src == 1):
                    if(not settings.settings.no_deezertrack):
                        data.prnt("[INFO] Searching using " + src_name + "...")
                        data.hookout(type="status", status="checking_src", message=src_name)
                        used_src = True
                        parsed_video = parse_video(video)
                        res = " ".join(parsed_video)
                        deezer_result = deezer_platform.search_track(res)
                        res = parsed_video
                        featured_artist = True
                        if(deezer_result is not None):
                            tsuccess = True
                elif(src == 2):
                    if(not settings.settings.no_links):
                        data.prnt("[INFO] Searching using " + src_name + "...")
                        data.hookout(type="status", status="checking_src", message=src_name)
                        used_src = True
                        data.prnt("Please wait, this process might take a while...")
                        parsed_video = parse_video(video)
                        res = " ".join(parsed_video)
                        lres = music_data.check_links(video['description'].replace("\n", " "))
                        if(lres is not None):
                            if(lres[0] is not None):
                                lres = lres[0]
                                deezer_result = deezer_platform.trackid(lres)
                            elif(lres[1] is not None):
                                lres = lres[1]
                                deezer_result = deezer_platform.isrc(lres)
                            if(deezer_result is not None):
                                tsuccess = True
                elif(src == 3):
                    if(not settings.settings.no_startpage):
                        data.prnt("[INFO] Searching using " + src_name + "...")
                        data.hookout(type="status", status="checking_src", message=src_name)
                        used_src = True
                        parsed_video = parse_video(video)
                        res = " ".join(parsed_video)
                        startpage_result = startpage_platform.search_track(res, use_spotify=False)
                        if(startpage_result is not None):
                            deezer_result = deezer_platform.tracklink(startpage_result)
                            tsuccess = True
                elif(src == 4):
                    if(not settings.settings.no_deezertrack):
                        data.prnt("[INFO] Searching using " + src_name + "...")
                        data.hookout(type="status", status="checking_src", message=src_name)
                        used_src = True
                        parsed_video = parse_video(video, 1)
                        res = " ".join(parsed_video)
                        deezer_result = deezer_platform.search_track(res)
                        if(deezer_result is not None):
                            tsuccess = True
                elif(src == 5):
                    if(not settings.settings.no_deezertrack):
                        data.prnt("[INFO] Searching using " + src_name + "...")
                        data.hookout(type="status", status="checking_src", message=src_name)
                        used_src = True
                        parsed_video = parse_video(video, 2)
                        res = " ".join(parsed_video)
                        deezer_result = deezer_platform.search_track(res)
                        if(deezer_result is not None):
                            tsuccess = True
                elif(src == 6):
                    if(not settings.settings.no_deezeralbum):
                        data.prnt("[INFO] Searching using " + src_name + "...")
                        data.hookout(type="status", status="checking_src", message=src_name)
                        used_src = True
                        parsed_video = parse_video(video)
                        res = " ".join(parsed_video)
                        deezer_result = deezer_platform.search_album(res)
                        if(deezer_result is not None):
                            tsuccess = True
                elif(src == 7):
                    if(not settings.settings.no_shazam):
                        data.prnt("[INFO] Searching using " + src_name + "...")
                        data.hookout(type="status", status="checking_src", message=src_name)
                        used_src = True
                        data.prnt("Please wait, this process might take a while...")
                        parsed_video = parse_video(video)
                        res = " ".join(parsed_video)
                        shazam = loop.run_until_complete(shazam_platform.recognize(f"{settings.temp_dir}audio.wav"))
                        if(shazam is not None):
                            deezer_result = deezer_platform.isrc(shazam)
                            tsuccess = True
                elif(src == 8):
                    if(settings.settings.experimental_ddg):
                        data.prnt("[INFO] Searching using " + src_name + "...")
                        data.hookout(type="status", status="checking_src", message=src_name)
                        used_src = True
                        data.prnt("Please wait, this process might take a while...")
                        parsed_video = parse_video(video)
                        res = " ".join(parsed_video)
                        ddg_result = ddg_platform.search_track(res, use_spotify=False)
                        if(ddg_result is not None):
                            deezer_result = deezer_platform.tracklink(ddg_result)
                            tsuccess = True
                else:
                    tsuccess = True
                    data.prnt("[ERROR] Not found " + video['title'])
                    not_found += 1
                    file_fail.write("notfound:https://youtu.be/" + video['id'] + ":" + video['title'] + "\n")
                    file_output.write("https://youtu.be/" + video['id'] + "\n")
                    file_overview.write(
                        output.table_row(status="Not found", original="<a target='_blank' href='https://youtu.be/" + video['id'] + "'>" + video['title'] + "</a>", query=str(res)))
                    break
                if(tsuccess):
                    deezer_check = deezer_platform.check_yt_res(video, deezer_result, res, settings.settings.experimental_search_ranking, featured_artist)
                    if(deezer_check is None or not deezer_check):
                        tsuccess = False
                    else:
                        certainty = deezer_check[0]
                        deezer_res = deezer_check[1]
                        deezer_res = deezer_platform.trackid(str(deezer_res["id"])).as_dict()
                        deezer_platform.download(url=deezer_res['preview'], path=settings.temp_dir, isrc=deezer_res["isrc"])
                        formatted_certainty = str(round(certainty*100, 2))
                        if(certainty > constants.similarity_threshold):
                            data.prnt(f"[SUCCESS] [{formatted_certainty}% - {constants.src_name(src)}] {deezer_res['artist']['name']} - {deezer_res['title']}")
                            success += 1
                            file_output.write(deezer_res['link'] + "\n")
                            data.hookout(type="status", status="found")
                            add_to_json(status="found", engine=constants.src_name(src), certainty=formatted_certainty, original=f"https://youtu.be/{video['id']}", found=deezer_res['link'], query=str(res))
                            file_overview.write(
                                output.table_row(status="Success", engine=constants.src_name(src), certainty=formatted_certainty, original="<a target='_blank' href='https://youtu.be/""" + video['id'] + "'>""" + video['title'] + "</a>", found="<a target='_blank' href='" + deezer_res['link'] + "'>" + deezer_res['artist']['name'] + " - " + deezer_res['title'] + "</a>", query=str(res)))
                        else:
                            tsuccess = False
                if(not tsuccess):
                    if(src < len(constants.src_names) and used_src):
                        data.prnt("[WARN] Couldn't find using " + constants.src_name(src))
                    src += 1
            os.remove(settings.temp_dir + "audio.wav")
        data.hookout(type="progress", now=i+1, total=total, notfound=not_found)
    except Exception as e:
        data.prnt("Handling error at index " + str(i))
        data.prnt(traceback.format_exc())
        file_fail.write("handleerror:" + str(i) + "\n")
        data.hookout(type="error", message="handling_error")
        file_overview.write(
            output.table_row(status="Handling error", original="<a target='_blank' href='https://youtu.be/" + video['id'] + "'>""" + video['title'] + "</a>"))

def handle_yt(url):
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
                    handle_res(video, i)
            else:
                video = result
                handle_res(video)
    
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
<meta name="overview-version" content="1">
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
    <th>Engine</th>
    <th>Certainty</th>
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
    handle_yt(url)
else:
    data.prnt("Unsupported source platform")
    data.hookout(type="source_platform", platform="")
    sys.exit()
data.hookout(type="result", result=output_json)
file_output_json.write(json.dumps(output_json))
file_overview.write("</table>")
shutil.rmtree(settings.temp_dir)
data.hookout(type="status", status="end", id=run_id)