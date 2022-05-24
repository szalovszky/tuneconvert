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
from shazamio import Shazam

import constants
from platforms import ddg_platform, startpage_platform, deezer_platform
from utils import data, music_data, file, output
import settings

# Supress Asyncio deprecation warning
import warnings
warnings.filterwarnings("ignore", category=DeprecationWarning) 

parser = argparse.ArgumentParser(description="yt2deezer", formatter_class=argparse.ArgumentDefaultsHelpFormatter)

parser.add_argument("--force-year", default=False, help="Don't filter year out of metadata", action='store_true')
parser.add_argument("--force-emojis", default=False, help="Don't filter emojis out of metadata", action='store_true')
parser.add_argument("--force-unicode", default=False, help="Don't filter Unicode text out of metadata", action='store_true')

parser.add_argument("--experimental-search-ranking", default=False, help="[EXPERIMENTAL] Rank searches when querying", action='store_true')
parser.add_argument("--experimental-ddg", default=False, help="[EXPERIMENTAL] Enable DuckDuckGo as a source", action='store_true')

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

run_id = str(int(time.time())).encode('utf-8') + str(''.join(random.choices(string.ascii_uppercase + string.digits, k=8))).encode('utf-8')
h = hashlib.new('md5')
h.update(run_id)
run_id = h.hexdigest()

output_dir = "output/"
working_dir = f"{output_dir}{run_id} /"
temp_dir = working_dir + ".temp/"

if(not os.path.exists(output_dir)):
    os.mkdir(output_dir)
os.mkdir(working_dir)
os.mkdir(temp_dir)

logging.basicConfig(filename=working_dir + 'log.txt', filemode='w', encoding='utf-8', format='%(asctime)s %(message)s', level=logging.DEBUG)
logger = logging.getLogger()
logger.setLevel(logging.INFO)

file_overview = open(working_dir + 'output.html', 'w', encoding="utf-8")
file_output = open(working_dir + 'output.txt', 'w', encoding="utf-8")
file_output_json = open(working_dir + 'output.json', 'w', encoding="utf-8")

file_fail = open(working_dir + 'failed.txt', 'w', encoding="utf-8")
file_unavailable = open(working_dir + 'unavailable.txt', 'w', encoding="utf-8")
file_options = open(working_dir + 'options.json', 'w', encoding="utf-8")


def prnt(string):
    global logger
    print(string)
    logger.info(string)


def hookout(string):
    if(settings.settings.hook):
        print(f"hook>{string}")


class normallogger:
    def debug(self, msg):
        # For compatibility with youtube-dl
        if msg.startswith('[debug] '):
            pass
        else:
            self.info(msg)

    def info(self, msg):
        prnt(msg)

    def warning(self, msg):
        prnt(msg)

    def error(self, msg):
        if(("removed" in msg) or ("unavailable" in msg)):
            file_unavailable.write(msg + "\n")
        prnt(msg)


class dllogger:
    def debug(self, msg):
        # For compatibility with youtube-dl, both debug and info are passed into debug
        # You can distinguish them by the prefix '[debug] '
        if msg.startswith('[debug] '):
            pass
        else:
            self.info(msg)

    def info(self, msg):
        pass

    def warning(self, msg):
        prnt(msg)

    def error(self, msg):
        prnt(msg)


def my_hook(d):
    if d['status'] == 'downloading':
        print("downloading " + str(round(float(d['downloaded_bytes'])/float(d['total_bytes'])*100,1))+"%")
    if d['status'] == 'finished':
        filename = d['filename']
        print(filename)


async def shazam_yt(url):
    ydl_opts = {
        'format': 'bestaudio/best',
        'postprocessors': [{
            'key': 'SponsorBlock',
            'categories': ['music_offtopic']
        }, {
            'key': 'ModifyChapters',
            'remove_sponsor_segments': ['music_offtopic']
        }],
        'outtmpl': temp_dir + 'audio.webm',
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ytdl:
        try:
            ytdl.download(url)
        except:
            return None
        try:
            shazam = Shazam()
            (ffmpeg
                .input(temp_dir + 'audio.webm')
                .output(temp_dir + 'audio%00005d.ogg',
                        c='copy', map='0', segment_time='00:00:30',
                        f='segment', reset_timestamps='1')
                .run())

            os.remove(temp_dir + "audio.webm")

            found_isrc = None
            last_isrc = "0"

            segment = 0
            search = True
            files = sorted(os.listdir(temp_dir))
            for file in files:
                if (file.startswith("audio")):
                    file = temp_dir + file
                    if (search):
                        if(file.endswith(".temp.concat")):
                            continue
                        if (int(file.replace("audio", "").replace(".ogg", "")
                                .replace(temp_dir, "")) % 2 == 0):
                            if(segment >= 12):
                                prnt(f"Giving up after {segment} tries")
                                break
                            segment += 1
                            prnt(f"Testing segment #{segment}...")
                            try:
                                out = await shazam.recognize_song(file)
                                isrc = out['track']['isrc']
                                if(last_isrc == isrc):
                                    found_isrc = isrc
                                    search = False
                                else:
                                    if(last_isrc != "0"):
                                        prnt("Different result, continuing...")
                                    last_isrc = isrc
                            except:
                                prnt("Segment not found.")
                    if os.path.exists(file):
                        os.remove(file)
                    else:
                        prnt(f"Somehow {file} doesn't exist?")
            
            return found_isrc
        except Exception as e:
            print(e)
            return None
loop = asyncio.get_event_loop()


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


total = 1
success = 0
not_found = 0


def handle_res(video, i=0):
    global success, not_found
    try:
        res = parse_video(video)
        if(res is None):
            if(video is None):
                hookout("error:video_not_found")
                prnt("======")
                prnt("Video not found at index " + str(i))
                file_fail.write("fatalerror:" + str(i) + "\n")
                file_overview.write(output.table_row(status="Video not found"))
            else:
                hookout("error:general_error")
                file_fail.write("generror:https://youtu.be/" + video['id'] + ":" + video['title'] + "\n")
                file_overview.write(output.table_row(status="Res error", original="<a target='_blank' href='https://youtu.be/" + video['id'] + "'>" + video['title'] + "</a>"))
        else:
            hookout(f"info:checking:{video['title']}")
            prnt("=== " + video['title'] + " ===")
            src = 0
            tsuccess = False
            while(not tsuccess):
                if(src < len(constants.src_names)):
                    src_name = constants.src_name(src)
                    prnt("[INFO] Searching using " + src_name + "...")
                    hookout(f"info:checking_src:{src_name}")
                featured_artist = False
                if(src == 0):
                    if(not settings.settings.no_deezertrack):
                        parsed_video = parse_video(video)
                        res = " ".join(parsed_video)
                        deezer_result = deezer_platform.search_track(res)
                        res = parsed_video
                        if(deezer_result is not None):
                            tsuccess = True
                    else:
                        prnt(f"Not using {src_name}, because it was manually turned off")
                elif(src == 1):
                    if(not settings.settings.no_deezertrack):
                        parsed_video = parse_video(video)
                        res = " ".join(parsed_video)
                        deezer_result = deezer_platform.search_track(res)
                        res = parsed_video
                        featured_artist = True
                        if(deezer_result is not None):
                            tsuccess = True
                    else:
                        prnt(f"Not using {src_name}, because it was manually turned off")
                elif(src == 2):
                    if(not settings.settings.no_links):
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
                    else:
                        prnt(f"Not using {src_name}, because it was manually turned off")
                elif(src == 3):
                    if(not settings.settings.no_startpage):
                        parsed_video = parse_video(video)
                        res = " ".join(parsed_video)
                        startpage_result = startpage_platform.search_track(res, use_spotify=False)
                        if(startpage_result is not None):
                            deezer_result = deezer_platform.tracklink(startpage_result)
                            tsuccess = True
                    else:
                        prnt(f"Not using {src_name}, because it was manually turned off")
                elif(src == 4):
                    if(not settings.settings.no_deezertrack):
                        parsed_video = parse_video(video, 1)
                        res = " ".join(parsed_video)
                        deezer_result = deezer_platform.search_track(res)
                        if(deezer_result is not None):
                            tsuccess = True
                    else:
                        prnt(f"Not using {src_name}, because it was manually turned off")
                elif(src == 5):
                    if(not settings.settings.no_deezertrack):
                        parsed_video = parse_video(video, 2)
                        res = " ".join(parsed_video)
                        deezer_result = deezer_platform.search_track(res)
                        if(deezer_result is not None):
                            tsuccess = True
                    else:
                        prnt(f"Not using {src_name}, because it was manually turned off")
                elif(src == 6):
                    if(not settings.settings.no_deezeralbum):
                        parsed_video = parse_video(video)
                        res = " ".join(parsed_video)
                        deezer_result = deezer_platform.search_album(res)
                        if(deezer_result is not None):
                            tsuccess = True
                    else:
                        prnt(f"Not using {src_name}, because it was manually turned off")
                elif(src == 7):
                    if(not settings.settings.no_shazam):
                        prnt("Please wait, this process might take a while...")
                        parsed_video = parse_video(video)
                        res = " ".join(parsed_video)
                        shazam = loop.run_until_complete(shazam_yt("https://youtu.be/" + video['id']))
                        if(shazam is not None):
                            deezer_result = deezer_platform.isrc(shazam)
                            tsuccess = True
                    else:
                        prnt(f"Not using {src_name}, because it was manually turned off")
                elif(src == 8):
                    if(settings.settings.experimental_ddg):
                        prnt("Please wait, this process might take a while...")
                        parsed_video = parse_video(video)
                        res = " ".join(parsed_video)
                        ddg_result = ddg_platform.search_track(res, use_spotify=False)
                        if(ddg_result is not None):
                            deezer_result = deezer_platform.tracklink(ddg_result)
                            tsuccess = True
                    else:
                        prnt(f"Not using {src_name}, because it was manually turned off")
                else:
                    tsuccess = True
                    prnt("[ERROR] Not found " + video['title'])
                    not_found += 1
                    file_fail.write("notfound:https://youtu.be/" + video['id'] + ":" + video['title'] + "\n")
                    file_output.write("https://youtu.be/" + video['id'] + "\n")
                    file_overview.write(
                        output.table_row(status="Not found", original="<a target='_blank' href='https://youtu.be/" + video['id'] + "'>" + video['title'] + "</a>", query=str(res)))
                    break
                if(tsuccess):
                    deezer_check = deezer_platform.check_yt_res(video, deezer_result, res, settings.settings.experimental_search_ranking, featured_artist)
                    if(deezer_check is None or not deezer_check):
                        prnt(deezer_check)
                        tsuccess = False
                    else:
                        certainty = deezer_check[0]
                        deezer_res = deezer_check[1]
                        formatted_certainty = str(round(certainty*100, 2))
                        if(certainty > constants.similarity_threshold):
                            prnt(f"[SUCCESS] [{formatted_certainty}% - {constants.src_name(src)}] {deezer_res['artist']['name']} - {deezer_res['title']}")
                            success += 1
                            file_output.write(deezer_res['link'] + "\n")
                            file_overview.write(
                                output.table_row(status="Success", engine=constants.src_name(src), certainty=formatted_certainty, original="<a target='_blank' href='https://youtu.be/""" + video['id'] + "'>""" + video['title'] + "</a>", found="<a target='_blank' href='" + deezer_res['link'] + "'>" + deezer_res['artist']['name'] + " - " + deezer_res['title'] + "</a>", query=str(res)))
                        else:
                            tsuccess = False
                if(not tsuccess):
                    if(src < len(constants.src_names)):
                        prnt("[WARN] Couldn't find using " + constants.src_name(src))
                    src += 1
        hookout(f"info:progress:{i+1}/{total};{not_found}")
    except Exception as e:
        prnt("Handling error at index " + str(i))
        prnt(traceback.format_exc())
        file_fail.write("handleerror:" + str(i) + "\n")
        hookout("error:handling_error")
        file_overview.write(
            output.table_row(status="Handling error", original="<a target='_blank' href='https://youtu.be/" + video['id'] + "'>""" + video['title'] + "</a>"))

def handle_yt(url):
    global success, not_found, total
    global loop
    ydl = yt_dlp.YoutubeDL({"ignoreerrors": True, 'logger': normallogger(), 'progress_hooks': [my_hook],})
    with ydl:
        hookout("info:fetching")
        result = ydl.extract_info(url, download=False)
        hookout("info:parsing")
        
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

    prnt('Finished: ' + "{:.2f}".format((success/total)*100) + "% success (Total: " + str(total) + ", Not found: " + str(not_found) + ")")
    file_output.close()
    file_fail.close()
    file_unavailable.close()
    file_options.close()

hookout(f"start:{run_id}")
platform = settings.settings.destination
if("deezer" in platform):
    prnt("Using Deezer as Target Platform")
    hookout("info:platform_target_deezer")
else:
    prnt("Unsupported destination platform")
    hookout("error:unsupported_target_platform")
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
<meta name="app-version" content='""" + str(constants.version) + """'>
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<h1>Result</h1>
<h3>Run ID: """ + run_id + """</h3>
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
dict_settings['version'] = constants.version
file_options.write(json.dumps(dict_settings))
url = settings.settings.URL
if("youtu" in url):
    hookout("info:platform_source_youtube")
    handle_yt(url)
else:
    prnt("Unsupported source platform")
    hookout("error:unsupported_source_platform")
    sys.exit()

file_overview.write("</table>")
shutil.rmtree(temp_dir)
hookout(f"end:{run_id}")