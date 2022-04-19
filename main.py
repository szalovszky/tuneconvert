import sys
import time
import logging
import argparse

from difflib import SequenceMatcher
import re
import asyncio

import yt_dlp
import deezer
from shazamio import Shazam

parser = argparse.ArgumentParser(description="yt2deezer",
                                 formatter_class=argparse.ArgumentDefaultsHelpFormatter)

parser.add_argument("-s", "--no-shazam", default=False, help="Use Shazam as a 3rd-party verification source (only visual, does not affect actual searching)", action='store_true')
parser.add_argument("URL", help="YouTube Playlist/Video")

args = parser.parse_args()
config = vars(args)

def similar(a, b):
    return SequenceMatcher(None, a, b).ratio()

dontneed = [
    "(", ")", "/", "-", ".", "&", "[", "]", ":", "|",
    "music video", "videoclip", "prod", "ost",
    "official", "radio edit",
    "lyrics", "dalszöveg",
    " hd", " 4k",
    " feat", " by", " ft"
]

logging.basicConfig(filename='latest.log', filemode='w', encoding='utf-8', format='%(asctime)s %(message)s', level=logging.DEBUG)
logger = logging.getLogger()
logger.setLevel(logging.INFO)

outfile = open('out.txt', 'w', encoding="utf-8")
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
        print(msg)

    def warning(self, msg):
        print(msg)

    def error(self, msg):
        if(("removed" in msg) or ("unavailable" in msg)):
            unavailablefile.write(msg + "\n")
        print(msg)

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
        print(msg)

    def error(self, msg):
        print(msg)

def my_hook(d):
    if d['status'] == 'downloading':
        print ("downloading "+ str(round(float(d['downloaded_bytes'])/float(d['total_bytes'])*100,1))+"%")
    if d['status'] == 'finished':
        filename=d['filename']
        print(filename)

async def shazamit(url):
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
        prnt(f"Shazaming {url}...")
        try:
            shazam = Shazam()
            out = await shazam.recognize_song('audio.ogg')
            return (out['track']['subtitle'], out['track']['title'])
        except:
            return None
loop = asyncio.get_event_loop()

def filter_data(artist, title):
    # Remove unnecessary information between "()"s and "[]"s (ex. Official Music Video)
    title = re.sub(r'\([\s\S]*\)', '', title)
    title = re.sub(r'\[[\s\S]*\]', '', title)

    # Apply basic filtering
    artist = artist.replace(", ", " ").replace(" x ", " ").replace(";", " ")
    title = title.replace(", ", " ").replace(" x ", " ")

    # Apply advanced filtering
    for item in dontneed:
        artist = artist.replace(item, "")
        title = title.replace(item, "")

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

deezer = deezer.Client()
def converto_deezer(query):
    success = False
    while(not success):
        try:
            res = deezer.search(query)
            if(len(res) > 0):
                res = res[0].as_dict()
            else:
                res = None
            success = True
        except:
            time.sleep(1)
    return res

total = 1
success = 0
not_found = 0
invalid = 0

def out(res, deezer_result, shazam, video):
    global success, not_found, invalid
    if(deezer_result != None):
        if(shazam != None):
            compare1 = similar(filter_data(shazam[0], shazam[1]).lower(), res.lower())
        else:
            compare1 = 0
        compare2 = similar(filter_data(deezer_result['artist']['name'], deezer_result['title']).lower(), res.lower())
        shazamed = False
        if(compare1 >= 0.25):
            shazamed = True
            compare = ((compare1+compare2)/2)
        else:
            compare = compare2
        final = "[" + str(round(compare*100, 2)) + "%" + ("S" if shazamed else "") + "] " + deezer_result['artist']['name'] + " - " + deezer_result['title']
        if(compare < 0.25):
            final = "[ERROR] " + final + " but it doesn't match searched song: " + res
            invalid+=1
            failfile.write("invalid:https://youtu.be/" + video['id'] + ":" + video['title'] + "\n")
            outfile.write("https://youtu.be/" + video['id'] + "\n")
        else:
            final = "[SUCCESS] " + final + " from " + video['title']
            success+=1
            outfile.write(deezer_result['link'] + "\n")
        prnt(final)
    else:
        prnt("[ERROR] Couldn't find " + res)
        not_found+=1
        failfile.write("notfound:https://youtu.be/" + video['id'] + ":" + video['title'] + "\n")
        outfile.write("https://youtu.be/" + video['id'] + "\n")

def handle_yt(url):
    global success, not_found, invalid, total
    global loop
    ydl = yt_dlp.YoutubeDL({"ignoreerrors": True, 'logger': normallogger(), 'progress_hooks': [my_hook],})
    with ydl:
        result = ydl.extract_info(url, download=False)
        prnt("Parsing data...")

        if(args.no_shazam == True):
            prnt("Not verifying using Shazam, because -s switch was used")
        
        if 'entries' in result:
            # This is a playlist or a list of videos
            video = result['entries']
            total = len(video)

            # Loops entries to grab each video
            for i, item in enumerate(video):
                video = result['entries'][i]
                res = parse_video(video)
                if(res == None):
                    failfile.write("generror:https://youtu.be/" + video['id'] + ":" + video['title'] + "\n")
                else:
                    if(args.no_shazam == False):
                        shazam = loop.run_until_complete(shazamit("https://youtu.be/" + video['id']))
                    else:
                        shazam = None
                    deezer_result = (converto_deezer(res))
                    out(res, deezer_result, shazam, video)
        else:
            video = result
            res = parse_video(video)
            if(args.no_shazam == False):
                shazam = loop.run_until_complete(shazamit("https://youtu.be/" + video['id']))
            else:
                shazam = None
            deezer_result = (converto_deezer(res))
            out(res, deezer_result, shazam, video)

    prnt('Finished: ' + "{:.2f}".format((success/total)*100) + "% success (Invalid: " + str(invalid) + ", Not found: " + str(not_found) + ")")
    outfile.close()
    failfile.close()
    unavailablefile.close()

if(len(sys.argv) < 2):
    print("No link provided")
    exit()
prnt("Fetching data...")
url = args.URL
if("youtu" in url):
    handle_yt(url)
else:
    prnt("Unsupported source platform")