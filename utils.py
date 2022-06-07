import re
from difflib import SequenceMatcher
import emoji
import json
import requests
from bs4 import BeautifulSoup
import unicodedata
import mimetypes
from pydub import AudioSegment
import traceback
from urllib.parse import urlparse
import random
import hashlib

import settings
import constants
from timeout import timeout

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
        # Prevent var type errors
        string = str(string)
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
    
    def hash(string, method='md5'):
        string = str(string).encode('utf-8')
        h = hashlib.new(method)
        h.update(string)
        return h.hexdigest()

    def asciify(string):
        return unicodedata.normalize('NFD', string).encode('ascii', 'ignore').decode()

class music:
    name = ""
    title = ""
    description = ""
    id = ""
    bpm = 0
    length = 0
    link = ""
    filename = ""

    def __init__(self, name="", title="", description="", id="", bpm=0, length=0, link="", filename=""):
        self.name = name
        self.title = title
        self.description = description
        self.id = id
        self.bpm = bpm
        self.length = length
        self.link = link
        self.filename = filename

    class type:
        DEFAULT = 0
        MIX_OR_ALBUM = 1
        REMIX_OR_COVER_OR_INSTRUMENTAL = 2

class music_data:
    def detect_type(title, length):
        title = title.lower()

        if((("mix" in title) and ("remix" not in title)) or ("full album" in title) or (length > constants.mix_length_threshold)):
            return music.type.MIX_OR_ALBUM

        if any(trigger in title for trigger in constants.REMIX_OR_COVER_OR_INSTRUMENTAL_triggers):
            return music.type.REMIX_OR_COVER_OR_INSTRUMENTAL

        return music.type.DEFAULT

    def filter_data(artist, title, is_remix=False):
        # Convert all fields to lowercase (search engines don't like cased queries for some reason and it filtering also takes place in lowercase)
        artist = artist.lower()
        title = title.lower()
        
        title_extra_info = ""

        # Filter out only necessary information if the song is a remix
        if(is_remix):
            brackets = []
            brackets.append(re.findall('\((.*?)\)', title))
            brackets.append(re.findall('\[(.*?)\]', title))
            brackets.append(re.findall('\|(.*?)\|', title))
            
            # Merge list
            brackets = [j for i in brackets for j in i]

            # Format list
            extra_info = []
            for info in brackets:
                extra_info.append(data.asciify(" ".join(info.split())))

            if(len(extra_info) > 0):
                for info in extra_info:
                    if any(trigger in info for trigger in constants.REMIX_OR_COVER_OR_INSTRUMENTAL_triggers):
                        title_extra_info += info

        # Remove unnecessary information between "()"s, "[]"s, "||"s and "\\"s (ex. Official Music Video)
        title = re.sub(r'\([\s\S]*\)', '', title)
        title = re.sub(r'\[[\s\S]*\]', '', title)
        title = re.sub(r'\|[\s\S]*\|', '', title)
        title = re.sub(r'\\[\s\S]*\\', '', title)

        # Re-add extra info to title
        title += title_extra_info

        # Fix common problems with the artist field
        artist = artist.replace("/", " ").replace(";", " ").replace(" - Topic", "")

        # Apply basic filtering
        artist = artist.replace(", ", " ").replace(" x ", " ").replace(";", " ")
        title = title.replace(", ", " ").replace(" x ", " ").replace(" ", " ")

        # Apply advanced filtering by replacing every instance of filtered words
        for item in constants.dontneed:
            artist = artist.replace(item, "")
            title = title.replace(item, "")

        # Apply advanced filtering by replacing full word matches of filtered words
        x = artist.split()
        for i in range(len(x)):
            for word in constants.dontneed_wholeword:
                if(word.lower() == (x[i]).lower()):
                    x[i] = ""
        artist = " ".join(x)

        x = title.split()
        for i in range(len(x)):
            for word in constants.dontneed_wholeword:
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
            title = data.asciify(title)
        
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

    @timeout(constants.link_timeout)
    def check_links(desc):
        try:
            res = None
            x = desc.split()
            search = True
            for i in range(len(x)):
                try:
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
                        try:
                            link = elem["href"]
                            if((link.startswith("https://www.deezer.com/")) and ("/album/" not in link)):
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
                        except:
                            pass
                    
                    if((res[0] == None) and (res[1] == None)):
                        res = None
                except:
                    pass
            return res
        except:
            print(traceback.format_exc())
            return None

class output:
    def table_row(status="-", score="0", original="", original_title="-", found="", found_title="-", query="-"):
        has_original = (original != '')
        has_result = (found != '')
        row = "<tr>"
        row += f"<td>{status}</td>"
        row += f"<td>{score}pts</td>"
        row += "<td>" + (('<a href="' + original + '" target="_blank">') if has_original else '') + f"{original_title}{'</a>' if has_original else ''}</td>"
        row += "<td>" + (('<a href="' + found + '" target="_blank">') if has_result else '') + f"{found_title}{'</a>' if has_result else ''}</td>"
        row += f"<td><code>{query}</code></td>"
        row += "</tr>"
        return row

class file:
    def determine_mime(filename): 
        mime = mimetypes.guess_type(filename)[0]
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