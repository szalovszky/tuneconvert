import random
import string
import sys
import time
import logging
import argparse
import os
import hashlib
import shutil

from difflib import SequenceMatcher
import re
import asyncio

import yt_dlp
import deezer
import ffmpeg
from shazamio import Shazam

parser = argparse.ArgumentParser(description="yt2deezer", formatter_class=argparse.ArgumentDefaultsHelpFormatter)

parser.add_argument("-r", "--reset", default=False, help="Reset output file's and config's contents", action='store_true')

parser.add_argument("-y", "--force-year", default=False, help="Don't filter year out of metadata", action='store_true')

parser.add_argument("-s", "--no-shazam", default=False, help="Disable Shazam as a source", action='store_true')
parser.add_argument("-dt", "--no-deezertrack", default=False, help="Disable DeezerTrack as a source", action='store_true')
parser.add_argument("-da", "--no-deezeralbum", default=False, help="Disable DeezerAlbum as a source", action='store_true')

parser.add_argument("URL", help="Source Playlist/Song")
parser.add_argument("destination", help="Target Platform to sync to")

args = parser.parse_args()
config = vars(args)

run_id = str(int(time.time())).encode('utf-8') + str(''.join(random.choices(string.ascii_uppercase + string.digits, k=8))).encode('utf-8')
h = hashlib.new('md5')
h.update(run_id)
run_id = h.hexdigest()

working_dir = run_id + "/"
temp_dir = working_dir + ".temp/"

os.mkdir(working_dir)
os.mkdir(temp_dir)

def similar(a, b):
    return SequenceMatcher(None, a, b).ratio()

similarity_threshold = 0.275

logging.basicConfig(filename='latest.log', filemode='w', encoding='utf-8', format='%(asctime)s %(message)s', level=logging.DEBUG)
logger = logging.getLogger()
logger.setLevel(logging.INFO)

outfile = open('out.txt', 'a', encoding="utf-8")

failfile = open(working_dir + 'failed.txt', 'w', encoding="utf-8")
unavailablefile = open(working_dir + 'unavailable.txt', 'w', encoding="utf-8")

def prnt(string):
    global logger
    print(string)
    logger.info(string)

class normallogger:
    def debug(self, msg):
        # For compatibility with youtube-dl, both debug and info are passed into debug
        # You can distinguish them by the prefix '[debug] '
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
            unavailablefile.write(msg + "\n")
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
        print ("downloading "+ str(round(float(d['downloaded_bytes'])/float(d['total_bytes'])*100,1))+"%")
    if d['status'] == 'finished':
        filename=d['filename']
        print(filename)

async def shazam_yt(url):
    ydl_opts = {
        'format': 'bestaudio/best',
        'postprocessors': [{
            'key': 'FFmpegVideoConvertor',
            'preferedformat': 'ogg'
        },
        {
            'key': 'SponsorBlock', 
            'categories': ['music_offtopic']
        },
        {
            'key': 'ModifyChapters', 
            'remove_sponsor_segments': ['music_offtopic']
        }],
        'outtmpl': temp_dir + 'audio',
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ytdl:
        try:
            error_code = ytdl.download(url)
        except:
            return None
        try:
            shazam = Shazam()

            (ffmpeg
                .input(temp_dir + 'audio.ogg')
                .output(temp_dir + 'audio%02d.ogg', c='copy', map='0', segment_time='00:00:30', f='segment', reset_timestamps='1')
                .run()
            )

            os.remove(temp_dir + "audio.ogg")

            found_isrc = None
            last_isrc = "0"

            segment = 0

            search = True

            for file in os.listdir(temp_dir):
                if (file.startswith("audio")):
                    file = temp_dir + file
                    if (search):
                        if (int(file.replace("audio", "").replace(".ogg", "").replace(temp_dir, "")) % 2 == 0):
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
                                        prnt("Last result doesn't match current result, continuing...")
                                    last_isrc = isrc
                            except:
                                prnt("Segment failed.")
                    if os.path.exists(file):
                        os.remove(file)
                    else:
                        prnt(f"Somehow {file} doesn't exist?")
            
            return found_isrc
            #return (out['track']['subtitle'], out['track']['title'])
        except Exception as e:
            print(e)
            return None
loop = asyncio.get_event_loop()

dontneed = [
    "(", ")", "/", "-", ".", "&", "[", "]", ":", "|", '"', "!", "?", "│",
    "music video", "videoclip", "videoklip", "prod", "version", "album",
    "official", "hivatalos", "radio edit",
    "lyrics", "lyric", "dalszöveg", "dirty", "explicit",
]

dontneed_wholeword = [
    "video", "ost",
    "feat", "by", "ft", "nightcore",
    "hd", "4k",
]

def filter_data(artist, title):
    # Convert all fields to lowercase (search engines don't like cased queries for some reason and it doesn't need to be capitalized anyways)
    artist = artist.lower()
    title = title.lower()

    # Remove unnecessary information between "()"s and "[]"s and "||"s (ex. Official Music Video)
    title = re.sub(r'\([\s\S]*\)', '', title)
    title = re.sub(r'\[[\s\S]*\]', '', title)
    title = re.sub(r'\|[\s\S]*\|', '', title)

    # Apply basic filtering
    artist = artist.replace(", ", " ").replace(" x ", " ").replace(";", " ")
    title = title.replace(", ", " ").replace(" x ", " ")

    # Apply advanced filtering by replacing every instance of filtered words
    for item in dontneed:
        artist = artist.replace(item, "")
        title = title.replace(item, "")

    # Apply advanced filtering by replacing full word matches of filtered words
    x = artist.split()
    for i in range(len(x)):
        for word in dontneed_wholeword:
            if(word.lower() == (x[i]).lower()):
                x[i] = ""
    artist = " ".join(x)

    x = title.split()
    for i in range(len(x)):
        for word in dontneed_wholeword:
            if(word.lower() == (x[i]).lower()):
                x[i] = ""
    title = " ".join(x)

    # Cut out unnecessary spaces from the Artist field
    artist = " ".join(artist.split())

    # Cut out Artist from Title field and Cut out unnecessary spaces from the Title field
    x = title.split()
    for i in range(len(x)):
        if((similar(artist, x[i]) > .25) and (artist.split()[0] in x[i])):
            x[i] = ""
    title = " ".join(x)

    title = title.replace(artist + " - ", "")
    title = title.replace(artist, "")

    # Replace Year in titles (very common and confuses most search algos, but sometimes it may be relevant to keep it, so use the -y arg to skip this)
    if(args.force_year == False):
        x = title.split()
        for i in range(len(x)):
            #x[i] = re.sub(r"^(19|20)\d{2}$", '', x[i])
            x[i] = re.sub(r"^(19|[2-9][0-9])\d{2}$", '', x[i])
        title = " ".join(x)

    # Lastly, format it nicely and return the result
    x = (artist + " " + title)
    return (" ".join(x.split()))

def parse_video(video, forceMethod = 0):
    if(video == None):
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
    
    return filter_data(artist, title)

deezerc = deezer.Client()
def converto_deezer(query):
    success = False
    while(not success):
        try:
            res = deezerc.search(query)
            if(len(res) > 0):
                res = res[0].as_dict()
            else:
                res = None
            success = True
        except Exception as e:
            if("quota" in e.lower()):
                time.sleep(1)
            else:
                res = None
                break
    return res

def deezer_isrc(isrc):
    success = False
    while(not success):
        try:
            res = deezerc.request("GET", "track/isrc:" + isrc, resource_type=deezer.Track)
            res = res.as_dict()
            success = True
        except Exception as e:
            if("quota" in e.lower()):
                time.sleep(1)
            else:
                res = None
                break
    return res

def deezer_album(query):
    success = False
    while(not success):
        try:
            res = deezerc.request("GET", "search/album?q=" + query, resource_type=deezer.Album)
            if(len(res) > 0):
                res = res[0].as_dict()
                if(res['record_type'] == "single"):
                    res = deezerc.request("GET", res['tracklist'].replace("https://api.deezer.com/", ""))
                    if(len(res) > 0):
                        res = res[0].as_dict()
                    else:
                        res = None
                else:
                    res = None
            else:
                res = None
            success = True
        except Exception as e:
            if("quota" in e.lower()):
                time.sleep(1)
            else:
                res = None
                break
    return res

total = 1
success = 0
not_found = 0

src_names = {
    0: "DeezerTrackMethod0",
    1: "DeezerTrackMethod1",
    2: "DeezerAlbum",
    3: "Shazam"
}

def get_src_name(src):
    if(src > (len(src_names)-1)):
        return ""
    else:
        return src_names[src]

def out(res, deezer_result, src):
    global success, not_found
    deezersrc = filter_data(deezer_result['artist']['name'], deezer_result['title']).lower()
    ressrc = res.lower()
    compare = similar(deezersrc, ressrc)
    final = "[" + str(round(compare*100, 2)) + "% - " + get_src_name(src) + "] " + deezer_result['artist']['name'] + " - " + deezer_result['title']
    if(compare < similarity_threshold):
        return None
        final = "[ERROR] " + final + " but it doesn't match searched song: " + res
    else:
        final = "[SUCCESS] " + final
        success += 1
        outfile.write(deezer_result['link'] + "\n")
        prnt(final)
        return True

def handle_res(video, i = 0):
    global not_found
    try:
        res = parse_video(video)
        if(res == None):
            if(video == None):
                prnt("======")
                prnt("Video not found at index " + str(i))
                failfile.write("fatalerror:" + str(i) + "\n")
            else:
                failfile.write("generror:https://youtu.be/" + video['id'] + ":" + video['title'] + "\n")
        else:
            prnt("=== " + video['title'] + " ===")
            src = 0
            success = False
            while(not success):
                if(src < len(src_names)):
                    prnt("[INFO] Searching using " + get_src_name(src) + "...")
                if(src == 0):
                    if(args.no_deezertrack == False):
                        res = parse_video(video)
                        deezer_result = converto_deezer(res)
                        if(deezer_result != None):
                            success = True
                    else:
                        prnt("Not using DeezerTrackMethod0, because -dt switch was used")
                elif(src == 1):
                    if(args.no_deezertrack == False):
                        res = parse_video(video, 1)
                        deezer_result = converto_deezer(res)
                        if(deezer_result != None):
                            success = True
                    else:
                        prnt("Not using DeezerTrackMethod1, because -dt switch was used")
                elif(src == 2):
                    if(args.no_deezeralbum == False):
                        res = parse_video(video)
                        deezer_result = deezer_album(res)
                        if(deezer_result != None):
                            success = True
                    else:
                        prnt("Not using DeezerAlbum, because -da switch was used")
                elif(src == 3):
                    if(args.no_shazam == False):
                        prnt("Please wait, this process might take a while...")
                        res = parse_video(video)
                        shazam = loop.run_until_complete(shazam_yt("https://youtu.be/" + video['id']))
                        if(shazam != None):
                            deezer_result = deezer_isrc(shazam)
                            success = True
                    else:
                        prnt("Not using Shazam, because -s switch was used")
                else:
                    success = True
                    prnt("[ERROR] Not found " + res)
                    not_found += 1
                    failfile.write("notfound:https://youtu.be/" + video['id'] + ":" + video['title'] + "\n")
                    outfile.write("https://youtu.be/" + video['id'] + "\n")
                    break
                if(success):
                    if(out(res, deezer_result, src) == None):
                        success = False
                if(not success):
                    if(src < len(src_names)):
                        prnt("[WARN] Couldn't find using " + get_src_name(src))
                    src += 1
    except Exception as e:
        prnt("Handling error at index " + str(i))
        prnt(e)
        failfile.write("handleerror:" + str(i) + "\n")

def handle_yt(url):
    global success, not_found, total
    global loop
    ydl = yt_dlp.YoutubeDL({"ignoreerrors": True, 'logger': normallogger(), 'progress_hooks': [my_hook],})
    with ydl:
        result = ydl.extract_info(url, download=False)
        prnt("Parsing data...")
        
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
    outfile.close()
    failfile.close()
    unavailablefile.close()

if(len(sys.argv) < 2):
    prnt("No link provided")
    exit()

if(args.reset == True):
    # Delete output file
    if os.path.exists("out.txt"):
        os.remove("out.txt")

prnt("Fetching data...")
platform = args.destination
if("deezer" in platform):
    prnt("Using Deezer as Target Platform")
else:
    prnt("Unsupported destination platform")
    exit()

url = args.URL
if("youtu" in url):
    handle_yt(url)
else:
    prnt("Unsupported source platform")
    exit()

shutil.rmtree(temp_dir)