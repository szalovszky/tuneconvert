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

from difflib import SequenceMatcher
import re
import asyncio
import requests
from bs4 import BeautifulSoup

import yt_dlp
import deezer
import ffmpeg
from shazamio import Shazam

from platforms import deezer_platform

parser = argparse.ArgumentParser(description="yt2deezer", formatter_class=argparse.ArgumentDefaultsHelpFormatter)

parser.add_argument("-r", "--reset", default=False, help="Reset output file's and config's contents", action='store_true')

parser.add_argument("-y", "--force-year", default=False, help="Don't filter year out of metadata", action='store_true')

parser.add_argument("-s", "--no-shazam", default=False, help="Disable Shazam as a source", action='store_true')
parser.add_argument("-l", "--no-links", default=False, help="Disable DescriptionLinkParse as a source", action='store_true')
parser.add_argument("-dt", "--no-deezertrack", default=False, help="Disable DeezerTrack as a source", action='store_true')
parser.add_argument("-da", "--no-deezeralbum", default=False, help="Disable DeezerAlbum as a source", action='store_true')

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

def similar(a, b):
    return SequenceMatcher(None, a, b).ratio()

similarity_threshold = 0.275

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

dontneed = [
    "(", ")", "/", "-", ".", "&", "[", "]", ":", "|", '"', "!", "?", "│", "▶", "🎧",
    "music video", "videoclip", "videoklip", "prod", "version", "album",
    "official", "hivatalos", "radio edit", "full song",
    "lyrics", "lyric", "dalszöveg", "dirty", "explicit",
]

dontneed_wholeword = [
    "video", "ost", "nightcore", "uncensored",
    "feat", "by", "ft", "km",
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

    # Fix common problems with the artist field
    artist = artist.replace("/", " ").replace(";", " ")

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
    elif(forceMethod == 2):
        artist = ""
        title = video['title']
    
    return filter_data(artist, title)

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

src_names = {
    0: "DeezerTrackMethod0",
    1: "DescriptionLinkParse",
    2: "DeezerTrackMethod1",
    3: "DeezerTrackMethod2",
    4: "DeezerAlbum",
    5: "Shazam"
}

def get_src_name(src):
    if(src > (len(src_names)-1)):
        return ""
    else:
        return src_names[src]

def out(res, deezer_result, src, video):
    # Result ranking
    if(deezer_result != None):
        try:
            iterator = iter(deezer_result)
        except TypeError:
            try:
                deezer_result = deezer_result.as_dict()
            except:
                pass
            deezersrc = filter_data(deezer_result['artist']['name'], deezer_result['title']).lower()
            ressrc = res.lower()
            compare = similar(deezersrc, ressrc)
        else:
            highest = ["", 0.0]
            tsuccess = False
            while(not tsuccess):
                try:
                    for dres in deezer_result:
                        try:
                            dres['title']
                        except TypeError:
                            dres = dres.as_dict()
                        deezersrc = filter_data(dres['artist']['name'], dres['title']).lower()
                        ressrc = res.lower()
                        compare = similar(deezersrc, ressrc)
                        if(compare > highest[1]):
                            highest[0] = dres
                            highest[1] = compare
                    deezer_result = highest[0]
                    tsuccess = True
                except Exception as e:
                    if("quota" in str(e).lower()):
                        time.sleep(1)
                    else:
                        return None
            compare = highest[1]
    else:
        return None

    global success, not_found
    
    # Final decision
    final = "[" + str(round(compare*100, 2)) + "% - " + get_src_name(src) + "] " + deezer_result['artist']['name'] + " - " + deezer_result['title']
    if(compare < similarity_threshold):
        return None
    else:
        final = "[SUCCESS] " + final
        success += 1
        outfile.write(deezer_result['link'] + "\n")
        prnt(final)
        overviewfile.write("""
            <tr>
                <td>Success</td>
                <td>""" + get_src_name(src) + """</td>
                <td>""" + str(round(compare*100, 2)) + """%</td>
                <td><a target='_blank' href='https://youtu.be/""" + video['id'] + """'>""" + video['title'] + """</a></td>
                <td><a target='_blank' href='""" + deezer_result['link'] + """'>""" + deezer_result['artist']['name'] + " - " + deezer_result['title'] + """</a></td>
                <td>""" + res + """</td>
            </tr>
        """)
        return True

def handle_res(video, i = 0):
    global not_found
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
            success = False
            #yt_is_mix(video)
            while(not success):
                if(src < len(src_names)):
                    src_name = get_src_name(src)
                    prnt("[INFO] Searching using " + src_name + "...")
                    hookout(f"info:checking_src:{src_name}")
                if(src == 0):
                    if(args.no_deezertrack == False):
                        res = parse_video(video)
                        deezer_result = deezer_platform.search_track(res)
                        if(deezer_result != None):
                            success = True
                    else:
                        prnt("Not using DeezerTrackMethod0, because -dt switch was used")
                elif(src == 1):
                    if(args.no_links == False):
                        lres = check_links(video['description'].replace("\n", " "))
                        if(lres != None):
                            if(lres[0] != None):
                                lres = lres[0]
                                deezer_result = deezer_platform.trackid(lres)
                            elif(lres[1] != None):
                                lres = lres[1]
                                deezer_result = deezer_platform.isrc(lres)
                            if(deezer_result != None):
                                success = True
                    else:
                        prnt("Not using DescriptionLinkParse, because -l switch was used")
                elif(src == 2):
                    if(args.no_deezertrack == False):
                        res = parse_video(video, 1)
                        deezer_result = deezer_platform.search_track(res)
                        if(deezer_result != None):
                            success = True
                    else:
                        prnt("Not using DeezerTrackMethod1, because -dt switch was used")
                elif(src == 3):
                    if(args.no_deezertrack == False):
                        res = parse_video(video, 2)
                        deezer_result = deezer_platform.search_track(res)
                        if(deezer_result != None):
                            success = True
                    else:
                        prnt("Not using DeezerTrackMethod2, because -dt switch was used")
                elif(src == 4):
                    if(args.no_deezeralbum == False):
                        res = parse_video(video)
                        deezer_result = deezer_platform.search_album(res)
                        if(deezer_result != None):
                            success = True
                    else:
                        prnt("Not using DeezerAlbum, because -da switch was used")
                elif(src == 5):
                    if(args.no_shazam == False):
                        prnt("Please wait, this process might take a while...")
                        res = parse_video(video)
                        shazam = loop.run_until_complete(shazam_yt("https://youtu.be/" + video['id']))
                        if(shazam != None):
                            deezer_result = deezer_platform.isrc(shazam)
                            success = True
                    else:
                        prnt("Not using Shazam, because -s switch was used")
                else:
                    success = True
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
                            <td>""" + res + """</td>
                        </tr>
                    """)
                    break
                if(success):
                    if(out(res, deezer_result, src, video) == None):
                        success = False
                if(not success):
                    if(src < len(src_names)):
                        prnt("[WARN] Couldn't find using " + get_src_name(src))
                    src += 1
        hookout(f"info:progress:{i+1}/{total};{not_found}")
    except Exception as e:
        prnt("Handling error at index " + str(i))
        prnt(e)
        failfile.write("handleerror:" + str(i) + "\n")

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