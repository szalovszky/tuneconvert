import re
from difflib import SequenceMatcher
import emoji
import json
import requests
from bs4 import BeautifulSoup
import unicodedata
import magic
from pydub import AudioSegment
import bpm_detector
import numpy
import math
import traceback
from urllib.parse import urlparse
import random

import settings
import constants

class data:
    def similar(a, b):
        return SequenceMatcher(None, a, b).ratio()

    def unique_list(l):
        ulist = []
        [ulist.append(x) for x in l if x not in ulist]
        return ulist

    def text_between(text, a, b):
        try:
            return re.search(rf'{a}(.*?){b}', text).group(1)
        except:
            return None

    def prnt(string, end='\n'):
        # Patch up ffmpeg output
        string = string.replace("[info]", "[INFO]").replace("[download]", "[DOWNLOAD]")
        # Add color to output
        string = string.replace("[INFO]", f"{constants.colors.OKCYAN}[INFO]{constants.colors.ENDC}").replace("[WARN]", f"{constants.colors.WARNING}[WARN]{constants.colors.ENDC}").replace("[SUCCESS]", f"{constants.colors.OKGREEN}[SUCCESS]{constants.colors.ENDC}").replace("[ERROR]", f"{constants.colors.FAIL}[ERROR]{constants.colors.ENDC}").replace("[DOWNLOAD]", f"{constants.colors.HEADER}[DOWNLOAD]{constants.colors.ENDC}").replace("[ExtractAudio]", f"{constants.colors.HEADER}[ExtractAudio]{constants.colors.ENDC}")
        print(string, end=end)
        settings.logger.info(string)

    def hookout(**objects):
        if(settings.settings.hook):
            print(f"hook>{json.dumps(objects)}")

    def valid_link(string):
        regex = re.compile(
            r'^(?:http|ftp)s?://'
            r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+(?:[A-Z]{2,6}\.?|[A-Z0-9-]{2,}\.?)|'
            r'localhost|'
            r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'
            r'(?::\d+)?'
            r'(?:/?|[/?]\S+)$', re.IGNORECASE)
        return re.match(regex, string) is not None

class music_data:
    def filter_data(artist, title, filter_list, filter_word_list):
        # Convert all fields to lowercase (search engines don't like cased queries for some reason and it doesn't need to be capitalized anyways)
        artist = artist.lower()
        title = title.lower()

        # Remove unnecessary information between "()"s and "[]"s and "||"s (ex. Official Music Video)
        title = re.sub(r'\([\s\S]*\)', '', title)
        title = re.sub(r'\[[\s\S]*\]', '', title)
        title = re.sub(r'\|[\s\S]*\|', '', title)

        # Fix common problems with the artist field
        artist = artist.replace("/", " ").replace(";", " ").replace(" - Topic", "")

        # Apply basic filtering
        artist = artist.replace(", ", " ").replace(" x ", " ").replace(";", " ")
        title = title.replace(", ", " ").replace(" x ", " ").replace(" ", " ")

        # Apply advanced filtering by replacing every instance of filtered words
        for item in filter_list:
            artist = artist.replace(item, "")
            title = title.replace(item, "")

        # Apply advanced filtering by replacing full word matches of filtered words
        x = artist.split()
        for i in range(len(x)):
            for word in filter_word_list:
                if(word.lower() == (x[i]).lower()):
                    x[i] = ""
        artist = " ".join(x)

        x = title.split()
        for i in range(len(x)):
            for word in filter_word_list:
                if(word.lower() == (x[i]).lower()):
                    x[i] = ""
        title = " ".join(x)

        title = title.replace(artist + " - ", "")
        title = title.replace(artist, "")

        # Replace Year in titles (very common and confuses most search algos, but sometimes it may be relevant to keep it, so use the -y arg to skip this)
        if(not settings.settings.force_year):
            x = title.split()
            for i in range(len(x)):
                x[i] = re.sub(r"^(19|[2-9][0-9])\d{2}$", '', x[i])
            title = " ".join(x)

        # Remove duplicate words
        artist = ' '.join(data.unique_list(artist.split()))
        title = ' '.join(data.unique_list(title.split()))

        # Remove emojis from the Artist and Title field
        if(not settings.settings.force_emojis):
            artist = emoji.replace_emoji(artist, "")
            title = emoji.replace_emoji(title, "")

        # Ununicode some characters
        if(not settings.settings.force_unicode):
            title = unicodedata.normalize('NFD', title).encode('ascii', 'ignore').decode()
        
        # Cut out Unicode characters from the Title field
        if(not settings.settings.force_unicode):
            title = re.sub(r'[^a-zA-Z0-9 ]', '', title)

        # Cut out unnecessary spaces from the Artist field
        artist = " ".join(artist.split())

        # Cut out Artist from Title field and Cut out unnecessary spaces from the Title field
        x = artist.split()
        for i in range(len(x)):
            if(len(x[i]) > 3):
                title.replace(x[i], "")
        title = " ".join(title.split())

        # Lastly, return the result
        return [artist, title]

    def check_links(desc):
        try:
            res = None
            x = desc.split()
            search = True
            for i in range(len(x)):
                if(not search):
                    break
                if(not data.valid_link(x[i])):
                    continue
                domain = urlparse(x[i]).netloc
                if(domain in constants.dontsearch_links):
                    continue

                headers = {
                    'User-Agent': random.choice(constants.user_agents)
                }

                page = requests.get(x[i], headers)
                res = [None, None]

                soup = BeautifulSoup(page.content, "html.parser")
                elems = soup.find_all("a")
                for elem in elems:
                    link = elem["href"]
                    if(link.startswith("https://www.deezer.com")):
                        if("?" in link):
                            link = link.split("?")[0]
                        res = [link.replace("https://www.deezer.com/track/", ""), res[1]]
                        search = False
                        break
                    elif(link.startswith("open.spotify.com")):
                        # Deezer as a platform wasn't found, but we can find the ISRC from here
                        # TODO: Janky solution, replace
                        infojson = " ".join(soup.find('script', id="linkfire-tracking-data").string.split()) # Find <script> object and remove unnecessary whitespace from the string
                        infojson = (infojson.replace("window.linkfire.tracking = { version: 1, parameters: ", "").replace(", required: {}, performance: {}, advertising: {}, additionalParameters: { subscribe: [], }, visitTrackingEvent: \"pageview\" };", "")) # Clear out non-JSON part of the <script>
                        infojson = json.loads(infojson) # JSONify it
                        res = [res[0], infojson['isrcs'][0]]
                        search = False
                        break

                if((res[0] == None) and (res[1] == None)):
                    res = None

            return res
        except:
            print(traceback.format_exc())
            return None

class output:
    def table_row(status = "-", engine = "-", certainty = "-", original = "-", found = "-", query = "-"):
        row = "<tr>"
        row += f"<td>{status}</td>"
        row += f"<td>{engine}</td>"
        row += f"<td>{certainty}%</td>"
        row += f"<td>{original}</td>"
        row += f"<td>{found}</td>"
        row += f"<td><code>{query}</code></td>"
        row += "</tr>"
        return row

class file:
    def determine_mime(filename): 
        mime = magic.Magic(mime=True)
        mime = mime.from_file(filename)
        if mime != None:
            mime = mime.split('/')
            return mime
        else:
            return None
        return result


class audio:
    def leading_silence(sound, silence_threshold=-50.0, chunk_size=10):
        trim_ms = 0
        assert chunk_size > 0
        while sound[trim_ms:trim_ms+chunk_size].dBFS < silence_threshold and trim_ms < len(sound):
            trim_ms += chunk_size
        return trim_ms

    def cut_leading_silence(filename):
        sound = AudioSegment.from_file(filename, format="wav")
        start_trim = audio.leading_silence(sound)
        end_trim = audio.leading_silence(sound.reverse())
        trimmed_sound = sound[start_trim:len(sound)-end_trim]
        trimmed_sound.export(filename, format="wav")

    def detect_bpm(filename, window=3.0):
        samps, fs = bpm_detector.read_wav(filename)
        data = []
        correl = []
        n = 0
        nsamps = len(samps)
        window_samps = int(window * fs)
        samps_ndx = 0
        max_window_ndx = math.floor(nsamps / window_samps)
        bpms = numpy.zeros(max_window_ndx)
        # Iterate through all windows
        for window_ndx in range(0, max_window_ndx):
            data = samps[samps_ndx : samps_ndx + window_samps]
            if not ((len(data) % window_samps) == 0):
                raise AssertionError(str(len(data)))
            bpm, correl_temp = bpm_detector.bpm_detector(data, fs)
            if bpm is None:
                continue
            bpms[window_ndx] = bpm
            correl = correl_temp
            # Iterate at the end of the loop
            samps_ndx = samps_ndx + window_samps
            n = n + 1
        #print(f"Median of collected windows' values: {numpy.median(bpms)}")
        bpm = numpy.round(numpy.median(bpms)-0.005)
        return int(bpm)