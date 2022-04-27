import random
import string
import sys
import time
import logging
import argparse
import os
import hashlib
import shutil
import json

import re
import asyncio
import requests
from bs4 import BeautifulSoup

import yt_dlp
import deezer
import ffmpeg
from shazamio import Shazam

import constants
from platforms import deezer_platform
from utils import utils

parser = argparse.ArgumentParser(description="yt2deezer", formatter_class=argparse.ArgumentDefaultsHelpFormatter)

parser.add_argument("-r", "--reset", default=False, help="Reset output file's and config's contents", action='store_true')

parser.add_argument("--force-year", default=False, help="Don't filter year out of metadata", action='store_true')
parser.add_argument("--force-emojis", default=False, help="Don't filter emojis out of metadata", action='store_true')

parser.add_argument("--experimental-search-ranking", default=False, help="[EXPERIMENTAL] Rank searches when querying", action='store_true')

parser.add_argument("--no-shazam", default=False, help="Disable Shazam as a source", action='store_true')
parser.add_argument("--no-links", default=False, help="Disable DescriptionLinkParse as a source", action='store_true')
parser.add_argument("--no-deezertrack", default=False, help="Disable DeezerTrack as a source", action='store_true')
parser.add_argument("--no-deezeralbum", default=False, help="Disable DeezerAlbum as a source", action='store_true')

parser.add_argument("--hook", default=False, help="Special argument", action='store_true')

parser.add_argument("URL", help="Source Playlist/Song")
parser.add_argument("destination", help="Target Platform to sync to")

args = parser.parse_args()
config = vars(args)

run_id = str(int(time.time())).encode('utf-8') + str(''.join(random.choices(string.ascii_uppercase + string.digits, k=8))).encode('utf-8')
h = hashlib.new('md5')
h.update(run_id)
run_id = h.hexdigest()

out_dir = "output/"
working_dir = out_dir + run_id + "/"
temp_dir = working_dir + ".temp/"

if(not os.path.exists(out_dir)):
    os.mkdir(out_dir)
os.mkdir(working_dir)
os.mkdir(temp_dir)

logging.basicConfig(filename=working_dir + 'log.txt', filemode='w', encoding='utf-8', format='%(asctime)s %(message)s', level=logging.DEBUG)
logger = logging.getLogger()
logger.setLevel(logging.INFO)

overviewfile = open(working_dir + 'overview.html', 'w', encoding="utf-8")
outfile = open(working_dir + 'out.txt', 'w', encoding="utf-8")

failfile = open(working_dir + 'failed.txt', 'w', encoding="utf-8")
unavailablefile = open(working_dir + 'unavailable.txt', 'w', encoding="utf-8")

def prnt(string):
    global logger
    print(string)
    logger.info(string)

def hookout(string):
    if(args.hook):
        print(f"hook>{string}")

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
                                prnt("Segment not found.")
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
    elif(forceMethod == 2):
        artist = ""
        title = video['title']

    return utils.filter_data(artist, title, constants.dontneed, constants.dontneed_wholeword, not args.force_year, not args.force_emojis)

def yt_is_mix(video):
    #is_mix = ((video) Or (video))
    return False

deezerc = deezer.Client()

def check_links(desc):
    try:
        res = None
        x = desc.split()
        for i in range(len(x)):
            domain = re.sub(r"(https?:\/\/)?([w]{3}\.)?(\w*.\w*)([\/\w]*)", "\\3", x[i])
            if(domain.endswith("lnk.to")):
                res = x[i]
                break

        if(res == None):
            return res

        page = requests.get(res)
        res = [None, None]

        soup = BeautifulSoup(page.content, "html.parser")
        elems = soup.find_all("div", class_="music-service-list__item")

        for elem in elems:
            link_elem = elem.find("a", class_="music-service-list__link")
            link = link_elem["href"]
            domain = re.sub(r"(https?:\/\/)?([w]{3}\.)?(\w*.\w*)([\/\w]*)", "\\3", link)
            if(domain.startswith("deezer.com")):
                if("?" in link):
                    link = link.split("?")[0]
                res = [link.replace("https://www.deezer.com/track/", ""), res[1]]
            elif(domain.startswith("open.spotify.com")):
                # Deezer as a platform wasn't found, but we can find the ISRC from here
                # TODO: Janky solution, replace
                infojson = " ".join(soup.find('script', id="linkfire-tracking-data").string.split()) # Find <script> object and remove unnecessary whitespace from the string
                infojson = (infojson.replace("window.linkfire.tracking = { version: 1, parameters: ", "").replace(", required: {}, performance: {}, advertising: {}, additionalParameters: { subscribe: [], }, visitTrackingEvent: \"pageview\" };", "")) # Clear out non-JSON part of the <script>
                infojson = json.loads(infojson) # JSONify it
                res = [res[0], infojson['isrcs'][0]]

        if((res[0] == None) and (res[1] == None)):
            res = None

        return res
    except:
        return None

total = 1
success = 0
not_found = 0

def handle_res(video, i = 0):
    global success, not_found
    try:
        res = parse_video(video)
        if(res == None):
            if(video == None):
                hookout(f"error:video_not_found")
                prnt("======")
                prnt("Video not found at index " + str(i))
                failfile.write("fatalerror:" + str(i) + "\n")
                overviewfile.write("""
                    <tr>
                        <td>Video not found</td>
                        <td>-</td>
                        <td>-</td>
                        <td>-</td>
                        <td>-</td>
                        <td>-</td>
                    </tr>
                """)
            else:
                hookout(f"error:general_error")
                failfile.write("generror:https://youtu.be/" + video['id'] + ":" + video['title'] + "\n")
                overviewfile.write("""
                    <tr>
                        <td>Res error</td>
                        <td>-</td>
                        <td>-</td>
                        <td><a target='_blank' href='https://youtu.be/""" + video['id'] + """'>""" + video['title'] + """</a></td>
                        <td>-</td>
                        <td>-</td>
                    </tr>
                """)
        else:
            hookout(f"info:checking:{video['title']}")
            prnt("=== " + video['title'] + " ===")
            src = 0
            tsuccess = False
            #yt_is_mix(video)
            while(not tsuccess):
                if(src < len(constants.src_names)):
                    src_name = constants.src_name(src)
                    prnt("[INFO] Searching using " + src_name + "...")
                    hookout(f"info:checking_src:{src_name}")
                if(src == 0):
                    if(args.no_deezertrack == False):
                        parsed_video = parse_video(video)
                        res = " ".join(parsed_video)
                        deezer_result = deezer_platform.search_track(res)
                        res = parsed_video
                        if(deezer_result != None):
                            tsuccess = True
                    else:
                        prnt("Not using DeezerTrackMethod0, because -dt switch was used")
                elif(src == 1):
                    if(args.no_links == False):
                        parsed_video = parse_video(video)
                        res = " ".join(parsed_video)
                        lres = check_links(video['description'].replace("\n", " "))
                        if(lres != None):
                            if(lres[0] != None):
                                lres = lres[0]
                                deezer_result = deezer_platform.trackid(lres)
                            elif(lres[1] != None):
                                lres = lres[1]
                                deezer_result = deezer_platform.isrc(lres)
                            if(deezer_result != None):
                                tsuccess = True
                    else:
                        prnt("Not using DescriptionLinkParse, because -l switch was used")
                elif(src == 2):
                    if(args.no_deezertrack == False):
                        parsed_video = parse_video(video, 1)
                        res = " ".join(parsed_video)
                        deezer_result = deezer_platform.search_track(res)
                        if(deezer_result != None):
                            tsuccess = True
                    else:
                        prnt("Not using DeezerTrackMethod1, because -dt switch was used")
                elif(src == 3):
                    if(args.no_deezertrack == False):
                        parsed_video = parse_video(video, 2)
                        res = " ".join(parsed_video)
                        deezer_result = deezer_platform.search_track(res)
                        if(deezer_result != None):
                            tsuccess = True
                    else:
                        prnt("Not using DeezerTrackMethod2, because -dt switch was used")
                elif(src == 4):
                    if(args.no_deezeralbum == False):
                        parsed_video = parse_video(video)
                        res = " ".join(parsed_video)
                        deezer_result = deezer_platform.search_album(res)
                        if(deezer_result != None):
                            tsuccess = True
                    else:
                        prnt("Not using DeezerAlbum, because -da switch was used")
                elif(src == 5):
                    if(args.no_shazam == False):
                        prnt("Please wait, this process might take a while...")
                        parsed_video = parse_video(video)
                        res = " ".join(parsed_video)
                        shazam = loop.run_until_complete(shazam_yt("https://youtu.be/" + video['id']))
                        if(shazam != None):
                            deezer_result = deezer_platform.isrc(shazam)
                            tsuccess = True
                    else:
                        prnt("Not using Shazam, because -s switch was used")
                else:
                    tsuccess = True
                    prnt("[ERROR] Not found " + video['title'])
                    not_found += 1
                    failfile.write("notfound:https://youtu.be/" + video['id'] + ":" + video['title'] + "\n")
                    outfile.write("https://youtu.be/" + video['id'] + "\n")
                    overviewfile.write("""
                        <tr>
                            <td>Not found</td>
                            <td>-</td>
                            <td>-</td>
                            <td><a target='_blank' href='https://youtu.be/""" + video['id'] + """'>""" + video['title'] + """</a></td>
                            <td>-</td>
                            <td>""" + str(res) + """</td>
                        </tr>
                    """)
                    break
                if(tsuccess):
                    deezer_check = deezer_platform.check_yt_res(video, deezer_result, res, args.experimental_search_ranking)
                    if(deezer_check == None or deezer_check == False):
                        print(deezer_check)
                        tsuccess = False
                    else:
                        certainty = deezer_check[0]
                        deezer_res = deezer_check[1]
                        formatted_certainty = str(round(certainty*100, 2))
                        if(certainty > constants.similarity_threshold):
                            prnt(f"[SUCCESS] [{formatted_certainty}% - {constants.src_name(src)}] {deezer_res['artist']['name']} - {deezer_res['title']}")
                            success += 1
                            outfile.write(deezer_res['link'] + "\n")
                            overviewfile.write("""
                                <tr>
                                    <td>Success</td>
                                    <td>""" + constants.src_name(src) + """</td>
                                    <td>""" + formatted_certainty + """%</td>
                                    <td><a target='_blank' href='https://youtu.be/""" + video['id'] + """'>""" + video['title'] + """</a></td>
                                    <td><a target='_blank' href='""" + deezer_res['link'] + """'>""" + deezer_res['artist']['name'] + " - " + deezer_res['title'] + """</a></td>
                                    <td>""" + str(res) + """</td>
                                </tr>
                            """)
                        else:
                            tsuccess = False
                if(not tsuccess):
                    if(src < len(constants.src_names)):
                        prnt("[WARN] Couldn't find using " + constants.src_name(src))
                    src += 1
        hookout(f"info:progress:{i+1}/{total};{not_found}")
    except Exception as e:
        prnt("Handling error at index " + str(i))
        prnt(e)
        failfile.write("handleerror:" + str(i) + "\n")
        hookout(f"error:handling_error")
        overviewfile.write("""
            <tr>
                <td>Handling error</td>
                <td>-</td>
                <td>-</td>
                <td><a target='_blank' href='https://youtu.be/""" + video['id'] + """'>""" + video['title'] + """</a></td>
                <td>-</td>
                <td>-</td>
            </tr>
        """)

def handle_yt(url):
    global success, not_found, total
    global loop
    ydl = yt_dlp.YoutubeDL({"ignoreerrors": True, 'logger': normallogger(), 'progress_hooks': [my_hook],})
    with ydl:
        hookout(f"info:fetching")
        result = ydl.extract_info(url, download=False)
        hookout(f"info:parsing")
        
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

if(args.reset == True):
    # Delete output file
    if os.path.exists("out.txt"):
        os.remove("out.txt")

hookout(f"start:{run_id}")
platform = args.destination
if("deezer" in platform):
    prnt("Using Deezer as Target Platform")
    hookout(f"info:platform_target_deezer")
else:
    prnt("Unsupported destination platform")
    hookout(f"error:unsupported_target_platform")
    exit()

overviewfile.write("""<style>
table {
  font-family: arial, sans-serif;
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
<meta charset="UTF-8">
<meta name="overview-version" content="0">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<h1>Result <a href='out.txt'>(open)</a></h1>
<table>
<tr>
    <th>Status</th>
    <th>Engine</th>
    <th>Certainty</th>
    <th>Original</th>
    <th>Found</th>
    <th>Query</th>
</tr>""")

url = args.URL
if("youtu" in url):
    hookout(f"info:platform_source_youtube")
    handle_yt(url)
else:
    prnt("Unsupported source platform")
    hookout(f"error:unsupported_source_platform")
    exit()

overviewfile.write("</table>")
shutil.rmtree(temp_dir)
hookout(f"end:{run_id}")