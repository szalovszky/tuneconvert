import sys
import time
import logging
import argparse
import os

from difflib import SequenceMatcher
import re
import asyncio

import yt_dlp
import deezer
from shazamio import Shazam

parser = argparse.ArgumentParser(description="yt2deezer", formatter_class=argparse.ArgumentDefaultsHelpFormatter)

parser.add_argument("-r", "--reset", default=False, help="Reset output file's and config's contents", action='store_true')

parser.add_argument("-s", "--no-shazam", default=False, help="Disable Shazam as a source", action='store_true')
parser.add_argument("-dt", "--no-deezertrack", default=False, help="Disable DeezerTrack as a source", action='store_true')
parser.add_argument("-da", "--no-deezeralbum", default=False, help="Disable DeezerAlbum as a source", action='store_true')

parser.add_argument("URL", help="YouTube Playlist/Video")

args = parser.parse_args()
config = vars(args)

def similar(a, b):
    return SequenceMatcher(None, a, b).ratio()

similarity_threshold = 0.275

logging.basicConfig(filename='latest.log', filemode='w', encoding='utf-8', format='%(asctime)s %(message)s', level=logging.DEBUG)
logger = logging.getLogger()
logger.setLevel(logging.INFO)

outfile = open('out.txt', 'a', encoding="utf-8")
failfile = open('failed.txt', 'w', encoding="utf-8")
unavailablefile = open('unavailable.txt', 'w', encoding="utf-8")

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

async def shazamit(url):
    prnt("Please wait, this might take a while...")
    #prnt(f"Extracting audio of {url}...")
    ydl_opts = {
        'logger': dllogger(),
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
        'outtmpl': 'audio',
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ytdl:
        try:
            error_code = ytdl.download(url)
        except:
            return None
        #prnt(f"Shazaming {url}...")
        try:
            shazam = Shazam()
            out = await shazam.recognize_song('audio.ogg')
            if os.path.exists("audio.ogg"):
                os.remove("audio.ogg")
            #return (out['track']['subtitle'], out['track']['title'])
            return out['track']['isrc']
        except:
            return None
loop = asyncio.get_event_loop()

dontneed = [
    "(", ")", "/", "-", ".", "&", "[", "]", ":", "|", '"',
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

    # Lastly, format it nicely and return the result
    x = (artist + " " + title)
    return (" ".join(x.split()))

def parse_video(video):
    if(video == None):
        return None
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
    0: "DeezerTrack",
    1: "DeezerAlbum",
    2: "Shazam"
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
                prnt("Video not found at index " + str(i))
                failfile.write("fatalerror:" + str(i) + "\n")
            else:
                failfile.write("generror:https://youtu.be/" + video['id'] + ":" + video['title'] + "\n")
        else:
            prnt("=== " + video['title'] + " ===")
            src = 0
            success = False
            while(not success):
                prnt("[INFO] Searching using " + get_src_name(src) + "...")
                if(src == 0):
                    if(args.no_deezertrack == False):
                        deezer_result = converto_deezer(res)
                        if(deezer_result != None):
                            success = True
                    else:
                        prnt("Not using DeezerTrack, because -dt switch was used")
                elif(src == 1):
                    if(args.no_deezeralbum == False):
                        deezer_result = deezer_album(res)
                        if(deezer_result != None):
                            success = True
                    else:
                        prnt("Not using DeezerAlbum, because -da switch was used")
                elif(src == 2):
                    if(args.no_shazam == False):
                        shazam = loop.run_until_complete(shazamit("https://youtu.be/" + video['id']))
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
    print("No link provided")
    exit()

if(args.reset == True):
    # Delete output file
    if os.path.exists("out.txt"):
        os.remove("out.txt")

prnt("Fetching data...")
url = args.URL
if("youtu" in url):
    handle_yt(url)
else:
    prnt("Unsupported source platform")