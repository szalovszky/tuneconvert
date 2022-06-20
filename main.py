#!/bin/python
__appname__ = "tuneconvert"
__version__ = "0.2"
__int_version__ = 20
__srv_version__ = "1.0"
__author__ = "Szalovszky David"

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
import time
import platform
import requests
from datetime import datetime

run_start = datetime.now()

import yt_dlp
import ffmpeg

import constants
from platforms import ddg_platform, startpage_platform, deezer_platform, youtube_platform, shazam_platform
from utils import data, music_data, file, output, audio
import settings
from checks import check_result, deezer_check, startpage_check, duckduckgo_check, shazam_check, external_check, data_check
import online
import objects

# TODO: Fix this
# Supress Asyncio deprecation warning
import warnings
warnings.filterwarnings("ignore", category=DeprecationWarning)

history = []

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

submission_user_agent = f"{__author__}/{__appname__}/{__version__}"

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
        # For compatibility with youtube-dl
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


def add_result(source, results, result, no_scoring=False):
    if(result is not None):
        id = data.hash(result['result'][1]['link'])
        if(id in results):
            if(not no_scoring):
                results[id]['score'] += 1.0
        else:
            results[id] = result
            if(not no_scoring):
                # Add length score
                results[id]['score'] += data_check.length(source_length=source.length, result_length=result['result'][1]['duration'])
                # Add score already calculated
                results[id]['score'] += result['result'][0]
    return results


total = 1
success = 0
not_found = 0

def find(source, music_type=objects.music.type.DEFAULT, only_metadata=False):
    is_remix = (music_type is objects.music.type.REMIX_OR_COVER_OR_INSTRUMENTAL)
    results = {}
    
    if((not settings.settings.force_mix_as_singular) and (music_type is objects.music.type.MIX_OR_ALBUM)):
        data.prnt("[WARN] Skipping mix or album... (not yet supported)")
    else:
        if((settings.settings.force_mix_as_singular) and (music_type is objects.music.type.MIX_OR_ALBUM)):
            data.prnt("[WARN] Forcing detected mix or album as a singular song. This may cause unaccurate results")
        add_result(source, results, deezer_check.track(source.title, is_remix))
        add_result(source, results, startpage_check.search(source.title, is_remix))
        add_result(source, results, deezer_check.album(source.title, is_remix))
        add_result(source, results, duckduckgo_check.search(source.title, is_remix))
        if(not only_metadata):
            add_result(source, results, external_check.links(source.title, source.description, is_remix))
            add_result(source, results, shazam_check.search(source.title, source.filename, is_remix))

    if(len(results.items()) > 0):
        # Sort results
        results = dict(sorted(results.items(), key=lambda x: (x[1]['score'])))
        top_result = list(results.items())[-1] if len(results.items()) > 0 else [0, [0, None]]
        top_result = top_result[1]
        return [top_result, is_remix]
    else:
        return [None, None]


def rank_find(query, **objects):
    if(len(objects) <= 0):
        return None
    
    results = []

    for key in objects:
        result = objects[key]
        if(result is None):
            continue
        if(result[0] is None):
            continue
        results.append(result[0])
    
    if(len(results) <= 0):
        return None
    
    # Sort results
    results = sorted(results, key=lambda x: (x['score']))
    top_result = results[-1] if len(results) > 0 else None
    return top_result


def handle(source, result, submit=True):
    global success, not_found

    if(result is not None):
        score = "%.2f" % result['score']
        result = objects.music(title=f"{(result['result'][1]['artist']['name'] + ' - ') if ('artist' in result['result'][1]) else ''}{result['result'][1]['title']}", link=result['result'][1]['link'], id=result['result'][1]['id'], isrc=result['result'][1]['isrc'])
        data.prnt(f"[SUCCESS] [{score}pts] {result.title}")
        success += 1
        data.hookout(type="status", status="found")
        add_to_json(status="found", score=score, original=source.link, found=result.link, query=source.title)
        file_overview.write(
            output.table_row(status="Success", score=score, original=source.link, original_title=source.name, found=result.link, found_title=result.title, query=source.title[1]))
        if(submit): online.submit_result(source, result, settings.submitter_obj)
    else:
        data.prnt(f"[ERROR] Not found {source.name}")
        not_found += 1
        result = source
        file_fail.write(f"notfound:{source.link}\n")
        add_to_json(status="not_found", original=source.link, query=source.title)
        file_overview.write(
            output.table_row(status="Not found", original=source.link, original_title=source.name, query=source.title))
        if(submit): online.submit_result(source, None, settings.submitter_obj)
    file_output.write(f"{source.link}\n")


def handle_youtube_result(video, i=0):
    global total, json_index
    try:
        if(video is None):
            data.hookout(type="error", message="video_not_found")
            data.prnt(f"\n{constants.colors.BOLD}=== [{i+1} of {total}] {constants.colors.FAIL}NOT FOUND{constants.colors.ENDC}{constants.colors.BOLD} ==={constants.colors.ENDC}")
            file_fail.write(f"fatalerror:{i}\n")
            file_overview.write(output.table_row(status="Video not found"))
        else:
            music_type = music_type=music_data.detect_type(video['title'], video['duration'])
            is_remix = (music_type is objects.music.type.REMIX_OR_COVER_OR_INSTRUMENTAL)
            source = objects.music(name=video['title'], title=youtube_platform.parse(video, youtube_platform.parse_method.DEFAULT, is_remix), description=video['description'], id=video['id'], link=f"https://youtu.be/{video['id']}", length=video['duration'])
            if(source.link in history):
                data.prnt(f"\n{constants.colors.BOLD}=== [{i+1} of {total}] {constants.colors.FAIL}DUPLICATE, SKIPPING{constants.colors.ENDC}{constants.colors.BOLD} ==={constants.colors.ENDC}")
                total -= 1
                return False
            else:
                history.append(source.link)
            data.hookout(type="status", status="checking", message=source.name)
            data.prnt(f"\n{constants.colors.BOLD}=== [{i+1} of {total}] {source.name} ==={constants.colors.ENDC}")
            source.filename = f"{settings.temp_dir}audio.wav"

            online_result = online.get_song(source, settings.submitter_obj)
            is_online = (online_result != None)
            is_online = is_online and (online_result['song'] != None)
            if(is_online):
                data.prnt("✅  Found result on Tuneconvert Online!")
                result = online_result['song']
                # I know this is a crappy solution
                result['score'] = 0.0
                result['result'] = [0.0, online_result['song']]
                handle(source, result, submit=False)
            else:
                youtube_platform.download(f"https://youtu.be/{video['id']}", source.filename)
                audio.cut_leading_silence(source.filename)
                source.length = float(ffmpeg.probe(source.filename)['format']['duration']).__floor__()
                # Search by metadata
                by_default = None
                if(not is_remix):
                    by_default = find(source=source, music_type=music_type, only_metadata=False)
                # Search by uploader - title
                by_uploader_title = None
                if(not is_remix):
                    source.title = youtube_platform.parse(video, youtube_platform.parse_method.UPLOADER_TITLE, is_remix)
                    by_uploader_title = find(source=source, music_type=music_type, only_metadata=True)
                # Search by title only
                source.title = youtube_platform.parse(video, youtube_platform.parse_method.TITLE_ONLY, is_remix)
                by_title_only = find(source=source, music_type=music_type, only_metadata=True)
                
                result = rank_find(query=source.title, by_default=by_default, by_uploader_title=by_uploader_title, by_title_only=by_title_only)
                handle(source, result)

            if(os.path.exists(source.filename)):
                os.remove(source.filename)
        data.hookout(type="progress", now=i+1, total=total, not_found=not_found)
    except Exception as e:
        try:
            data.prnt("[ERROR] Handling error at index " + str(i))
            data.prnt(traceback.format_exc())
            file_fail.write("handleerror:" + str(i) + "\n")
            data.hookout(type="error", message="handling_error")

            # Catch if source isn't referenced yet
            source.link = source.link

            add_to_json(status="handle_error", original=source.link, index=i)
            file_overview.write(
                output.table_row(status="Handling error", original=source.link, original_title=source.name))
        except:
            add_to_json(status="handle_error", index=i)
            file_overview.write(
                output.table_row(status="Handling error", original_title=f"Index: {str(i)}"))


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


if __name__ == "__main__":
    # Add arguments
    parser = argparse.ArgumentParser(description="tuneconvert", formatter_class=argparse.ArgumentDefaultsHelpFormatter)

    # Filtering
    parser.add_argument("--force-year", default=False, help="Don't filter year out of metadata", action='store_true')
    parser.add_argument("--force-emojis", default=False, help="Don't filter emojis out of metadata", action='store_true')
    parser.add_argument("--force-unicode", default=False, help="Don't filter Unicode text out of metadata", action='store_true')

    # Tuneconvert Online
    parser.add_argument("--disagree", default=False, help="Reset Tuneconvert Online terms agreement state", action='store_true')
    parser.add_argument("--no-submission", default=False, help="Disable score submission to the Tuneconvert Online but also disables usage of data stored there", action='store_true')

    # Sources
    parser.add_argument("--no-shazam", default=False, help="Disable Shazam as a source", action='store_true')
    parser.add_argument("--no-links", default=False, help="Disable DescriptionLinkParse as a source", action='store_true')
    parser.add_argument("--no-deezertrack", default=False, help="Disable DeezerTrack as a source", action='store_true')
    parser.add_argument("--no-deezeralbum", default=False, help="Disable DeezerAlbum as a source", action='store_true')
    parser.add_argument("--no-startpage", default=False, help="Disable Startpage as a source", action='store_true')
    parser.add_argument("--no-ddg", default=False, help="Disable DuckDuckGo as a source", action='store_true')
    parser.add_argument("--no-length", default=False, help="Disable Length as a check measure", action='store_true')

    # Misc.
    parser.add_argument("--hook", default=False, help="Special argument", action='store_true')

    parser.add_argument("--force-mix-as-singular", "--force-mix", "--force-album-as-singular", "--force-album", default=False, help="Parse detected mix or album as a singular song (legacy parsing method)", action='store_true')

    parser.add_argument("--legacy-search-ranking", default=False, help="Rank searches when querying (old method)", action='store_true')

    parser.add_argument("URL", help="Source Playlist/Song")
    parser.add_argument("destination", help="Target Platform to sync to")

    args = parser.parse_args()
    config = vars(args)

    settings.settings = args
    settings.srv_version = __srv_version__
    online.headers = {'User-Agent': submission_user_agent}

    if(settings.settings.disagree):
        file_license = open(constants.license_file_name, 'w', encoding="utf-8")
        file_license.write(str(-1))
        file_license.close()
    if(not settings.settings.no_submission):
        settings.settings.no_submission = not online.status()
        settings.submitter_obj = objects.submitter(os=f"{platform.system()} {platform.release()}", version=__version__, int_version=__int_version__, author=__author__, appname=__appname__, ip_address=requests.get('https://api.ipify.org').content.decode('utf8'))
        show_warn = True
        if(not os.path.exists(constants.license_file_name)):
            file_license = open(constants.license_file_name, 'w', encoding="utf-8")
            file_license.write(str(__int_version__))
            file_license.close()
        else:
            file_license_read = open(constants.license_file_name, 'r', encoding="utf-8")
            read_version = int(file_license_read.readlines()[0])
            file_license_read.close()
            if(read_version < __int_version__):
                file_license = open(constants.license_file_name, 'w', encoding="utf-8")
                file_license.write(str(__int_version__))
                file_license.close()
            else:
                show_warn = False
        if(show_warn):
            data.prnt("⚠️  By continuing to use the Tuneconvert Online services, you accept these terms and conditions: https://szalovszky.com/tuneconvert/online/terms")
            data.prnt("You can disable Tuneconvert Online by using the `--no-submission`")
            data.prnt("Operation will continue in 10 seconds...")
            data.prnt("")
            time.sleep(10)

    data.hookout(type="status", status="start", id=run_id)

    # Write header to overview file
    file_overview.write(constants.gen_output_html(name=__appname__, version=__version__, srv_version=__srv_version__, author=__author__, run_id=run_id, overview_version=3))

    # Determine destination platform
    platform = settings.settings.destination
    if("deezer" in platform):
        data.prnt("Using Deezer as Target Platform")
        data.hookout(type="target_platform", platform="deezer")
    else:
        data.prnt("Unsupported destination platform")
        data.hookout(type="target_platform", platform="")
        sys.exit()

    # Determine source platform
    url = settings.settings.URL
    if("youtu" in url):
        data.hookout(type="source_platform", platform="youtube")
        handle_youtube(url)
    else:
        data.prnt("Unsupported source platform")
        data.hookout(type="source_platform", platform="")
        sys.exit()

    # Write options to file
    dict_settings = settings.settings.__dict__
    dict_settings['name'] = __appname__
    dict_settings['author'] = __author__
    dict_settings['version'] = __version__
    dict_settings['srv-version'] = __srv_version__
    file_options.write(json.dumps(dict_settings))

    # Output result
    data.hookout(type="result", result=output_json)
    file_output_json.write(json.dumps(output_json))
    file_overview.write(constants.gen_output_html(start=False))

    data.prnt('='*32)
    success_rate = "{:.2f}".format((success/total)*100)
    runtime = (datetime.now() - run_start)
    result_info = f"Finished: {success_rate}% success (Total: {total}, Not found: {not_found})\nRuntime: {runtime}"
    data.hookout(type="result_info", success_rate=float(success_rate), total=total, not_found=not_found, runtime=runtime.total_seconds())
    data.prnt(result_info)
    file_overview.write("<p>" + result_info.replace("\n", "<br />") + "</p>")

    data.hookout(type="status", status="end", id=run_id)

    # Clean up remaining temp files & Close files
    shutil.rmtree(settings.temp_dir)
    file_overview.close()
    file_output_json.close()
    file_output.close()
    file_fail.close()
    file_unavailable.close()
    file_options.close()