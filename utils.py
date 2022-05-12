import re
from difflib import SequenceMatcher
import emoji
import json
import requests
from bs4 import BeautifulSoup

import settings

class utils:
    def similar(a, b):
        return SequenceMatcher(None, a, b).ratio()

    def unique_list(l):
        ulist = []
        [ulist.append(x) for x in l if x not in ulist]
        return ulist

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
        artist = ' '.join(utils.unique_list(artist.split()))
        title = ' '.join(utils.unique_list(title.split()))

        # Remove emojis from the Artist and Title field
        if(not settings.settings.force_emojis):
            artist = emoji.replace_emoji(artist, "")
            title = emoji.replace_emoji(title, "")

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

    def gen_table_row(status = "-", engine = "-", certainty = "-", original = "-", found = "-", query = "-"):
        row = "<tr>"
        row += f"<td>{status}</td>"
        row += f"<td>{engine}</td>"
        row += f"<td>{certainty}</td>"
        row += f"<td>{original}</td>"
        row += f"<td>{found}</td>"
        row += f"<td>{query}</td>"
        row += "</tr>"
        return row