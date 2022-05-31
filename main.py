__appname__ = "tuneconvert"
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
from datetime import datetime

run_start = datetime.now()

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

parser.add_argument("--force-mix-as-singular", "--force-mix", "--force-album-as-singular", "--force-album", default=False, help="Parse detected mix or album as a singular song (legacy parsing method)", action='store_true')

parser.add_argument("--experimental-search-ranking", default=False, help="[EXPERIMENTAL] Rank searches when querying", action='store_true')
parser.add_argument("--experimental-bpm", default=False, help="[EXPERIMENTAL] Check source BPM and compare result's BPM", action='store_true')

parser.add_argument("--no-shazam", default=False, help="Disable Shazam as a source", action='store_true')
parser.add_argument("--no-links", default=False, help="Disable DescriptionLinkParse as a source", action='store_true')
parser.add_argument("--no-deezertrack", default=False, help="Disable DeezerTrack as a source", action='store_true')
parser.add_argument("--no-deezeralbum", default=False, help="Disable DeezerAlbum as a source", action='store_true')
parser.add_argument("--no-startpage", default=False, help="Disable Startpage as a source", action='store_true')
parser.add_argument("--no-ddg", default=False, help="Disable DuckDuckGo as a source", action='store_true')

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

def find(source, music_type=music.type.DEFAULT, only_metadata=False):
    if(settings.settings.experimental_bpm):
        data.hookout(type="status", status="checking_bpm")
        data.prnt("Detecting source BPM... ", end='')
        audio.cut_leading_silence(source.filename)
        source.bpm = audio.detect_bpm(source.filename)
        data.prnt(str(source.bpm))
        data.hookout(type="bpm", bpm=source.bpm)

    is_remix = (music_type is music.type.REMIX_OR_COVER_OR_INSTRUMENTAL)
    results = {}
    
    if((not settings.settings.force_mix_as_singular) and (music_type is music.type.MIX_OR_ALBUM)):
        data.prnt("[WARN] Skipping mix or album... (not yet supported)")
    else:
        if((settings.settings.force_mix_as_singular) and (music_type is music.type.MIX_OR_ALBUM)):
            data.prnt("[WARN] Forcing detected mix or album as a singular song. This may cause unaccurate results")
        add_result(results, deezer_check.track(source.title, is_remix))
        add_result(results, startpage_check.search(source.title, is_remix))
        add_result(results, deezer_check.album(source.title, is_remix))
        add_result(results, duckduckgo_check.search(source.title, is_remix))
        if(not only_metadata):
            add_result(results, external_check.links(source.title, source.description, is_remix))
            add_result(results, shazam_check.search(source.title, source.filename, is_remix))

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
        if(result[0] is None):
            continue
        results.append(result[0])
    
    if(len(results) <= 0):
        return None
    
    # Sort results
    results = sorted(results, key=lambda x: (x['score']))
    top_result = results[-1] if len(results) > 0 else None
    return top_result


def handle(source, result):
    global success, not_found

    if(result is not None):
        score = "%.2f" % result['score']
        result = music(title=f"{result['result'][1]['artist']['name']} - {result['result'][1]['title']}", link=result['result'][1]['link'])
        data.prnt(f"[SUCCESS] [{score}pts] {result.title}")
        success += 1
        data.hookout(type="status", status="found")
        add_to_json(status="found", score=score, original=source.link, found=result.link, query=source.title[1])
        file_overview.write(
            output.table_row(status="Success", score=score, original=source.link, original_title=source.name, found=result.link, found_title=result.title, query=source.title[1]))
    else:
        data.prnt(f"[ERROR] Not found {source.name}")
        not_found += 1
        result = source
        file_fail.write(f"notfound:{source.link}\n")
        add_to_json(status="not_found", original=source.link, query=source.title[1])
        file_overview.write(
            output.table_row(status="Not found", original=source.link, original_title=source.name, query=source.title[1]))
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
            data.prnt(f"\n{constants.colors.BOLD}=== [{i+1} of {total}] {source.name} ==={constants.colors.ENDC}")
            source.filename = f"{settings.temp_dir}audio.wav"
            youtube_platform.download(f"https://youtu.be/{video['id']}", source.filename)
            source.length = float(ffmpeg.probe(source.filename)['format']['duration']).__floor__()

            music_type = music_type=music_data.detect_type(source.name, source.length)
            # Search by metadata
            by_default = find(source=source, music_type=music_type, only_metadata=False)
            # Search by uploader - title
            source.title = youtube_platform.parse(video, youtube_platform.parse_method.UPLOADER_TITLE)
            by_uploader_title = find(source=source, music_type=music_type, only_metadata=True)
            # Search by title only
            source.title = youtube_platform.parse(video, youtube_platform.parse_method.TITLE_ONLY)
            by_title_only = find(source=source, music_type=music_type, only_metadata=True)
            
            result = rank_find(query=source.title, by_default=by_default, by_uploader_title=by_uploader_title, by_title_only=by_title_only)
            handle(source, result)

            os.remove(settings.temp_dir + "audio.wav")
        data.hookout(type="progress", now=i+1, total=total, not_found=not_found)
    except Exception as e:
        try:
            data.prnt("[ERROR] Handling error at index " + str(i))
            data.prnt(traceback.format_exc())
            file_fail.write("handleerror:" + str(i) + "\n")
            data.hookout(type="error", message="handling_error")

            # Catch if source isn't referenced yet
            source.link = source.link

            file_overview.write(
                output.table_row(status="Handling error", original=source.link, original_title=source.name))
        except:
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
    data.hookout(type="status", status="start", id=run_id)

    # Write header to overview file
    file_overview.write(constants.gen_output_html(name=__appname__, version=__version__, author=__author__, run_id=run_id, overview_version=3))

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
    file_output.close()
    file_fail.close()
    file_unavailable.close()
    file_options.close()