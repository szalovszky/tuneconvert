import traceback
import time
import re
import deezer
import requests
from bs4 import BeautifulSoup
from time import sleep
import random

import constants
from utils import data, music_data
import platforms
import settings

class deezer_platform:
    deezer_client = deezer.Client()

    def search_track(query):
        success = False
        while(not success):
            try:
                res = platforms.deezer_platform.deezer_client.search(query)
                if(len(res) <= 0):
                    res = None
                success = True
            except Exception as e:
                if("quota" in str(e).lower()):
                    time.sleep(1)
                else:
                    print(traceback.format_exc())
                    res = None
                    break
        return res

    def isrc(isrc):
        success = False
        while(not success):
            try:
                res = platforms.deezer_platform.deezer_client.request("GET", "track/isrc:" + isrc, resource_type=deezer.Track)
                success = True
            except Exception as e:
                if("quota" in str(e).lower()):
                    time.sleep(1)
                else:
                    print(traceback.format_exc())
                    res = None
                    break
        return res

    def trackid(id):
        success = False
        while(not success):
            try:
                res = platforms.deezer_platform.deezer_client.request("GET", "track/" + id, resource_type=deezer.Track)
                success = True
            except Exception as e:
                if("quota" in str(e).lower()):
                    time.sleep(1)
                else:
                    print(traceback.format_exc())
                    res = None
                    break
        return res

    def tracklink(url):
        success = False
        while(not success):
            try:
                # I know this can be done fully by RegEx, but I can't into RegEx
                id = re.sub(r'(?<=https://www.deezer.com/).*(?=/track/)', '', url).replace("https://www.deezer.com//track/", "")
                res = platforms.deezer_platform.deezer_client.request("GET", "track/" + id, resource_type=deezer.Track)
                success = True
            except Exception as e:
                if("quota" in str(e).lower()):
                    time.sleep(1)
                else:
                    print(traceback.format_exc())
                    res = None
                    break
        return res

    def search_album(query):
        success = False
        while(not success):
            try:
                res = platforms.deezer_platform.deezer_client.request("GET", "search/album?q=" + query, resource_type=deezer.Album)
                if(len(res) > 0):
                    res = res[0].as_dict()
                    if(res['record_type'] == "single"):
                        res = platforms.deezer_platform.deezer_client.request("GET", res['tracklist'].replace("https://api.deezer.com/", ""))
                        if(len(res) > 0):
                            res = res[0]
                        else:
                            res = None
                    else:
                        res = None
                else:
                    res = None
                success = True
            except Exception as e:
                if("quota" in str(e).lower()):
                    time.sleep(1)
                else:
                    print(traceback.format_exc())
                    res = None
                    break
        return res

    def check_yt_res(original, result, query, search_ranking = False, featured_artists = False):
        if(result == None):
            return None
        seperate = isinstance(query, list)

        try:
            iterator = iter(result)
        except TypeError:
            result_item = result
            try:
                result_item = result_item.as_dict()
            except:
                pass
            if(seperate):
                artist = result_item['artist']['name']
                if(featured_artists):
                    if("contributors" not in result_item):
                        result_item = platforms.deezer_platform.trackid(str(result_item['id']))
                        try:
                            result_item = result_item.as_dict()
                        except:
                            pass
                    artist_sum = ""
                    for m_artist in result_item['contributors']:
                        artist_sum += music_data.filter_data(m_artist['name'], "", constants.dontneed, constants.dontneed_wholeword)[0] + " "
                    artist = ' '.join(data.unique_list(artist_sum.split()))
                artist_filtered = music_data.filter_data(artist, "", constants.dontneed, constants.dontneed_wholeword)[0]
                title_filtered = music_data.filter_data("", result_item['title'], constants.dontneed, constants.dontneed_wholeword)[1]
                artist_certainty = data.similar(query[0], artist_filtered)
                title_certainty = data.similar(query[1], title_filtered)
                if((artist_certainty < constants.similarity_threshold) or (title_certainty < constants.similarity_threshold)):
                    return False
                else:
                    return [((artist_certainty + title_certainty)/2), result_item]
            else:
                result_filtered = " ".join(music_data.filter_data(result_item['artist']['name'], result_item['title'], constants.dontneed, constants.dontneed_wholeword))
                certainty = data.similar(query, result_filtered)
                if(certainty < constants.similarity_threshold):
                    return False
                else:
                    return [certainty, result_item]
        else:
            most_certain = ["", 0.0, 0.0]
            iterate_success = False
            while(not iterate_success):
                try:
                    for result_item in result:
                        try:
                            result_item = result_item.as_dict()
                        except:
                            pass
                        if(seperate):
                            artist = result_item['artist']['name']
                            if(featured_artists):
                                if("contributors" not in result_item):
                                    result_item = platforms.deezer_platform.trackid(str(result_item['id']))
                                    try:
                                        result_item = result_item.as_dict()
                                    except:
                                        pass
                                artist_sum = ""
                                for m_artist in result_item['contributors']:
                                    artist_sum += music_data.filter_data(m_artist['name'], "", constants.dontneed, constants.dontneed_wholeword)[0] + " "
                                artist = ' '.join(data.unique_list(artist_sum.split()))
                            artist_filtered = music_data.filter_data(artist, "", constants.dontneed, constants.dontneed_wholeword)[0]
                            title_filtered = music_data.filter_data("", result_item['title'], constants.dontneed, constants.dontneed_wholeword)[1]
                            artist_certainty = data.similar(query[0], artist_filtered)
                            title_certainty = data.similar(query[1], title_filtered)
                            if((artist_certainty < constants.similarity_threshold) or (title_certainty < constants.similarity_threshold)):
                                pass
                            else:
                                if(artist_certainty > most_certain[1]):
                                    most_certain = [result_item, artist_certainty, title_certainty]
                                if((artist_certainty > most_certain[1]) and (title_certainty > most_certain[2])):
                                    most_certain = [result_item, artist_certainty, title_certainty]
                        else:
                            result_filtered = " ".join(music_data.filter_data(result_item['artist']['name'], result_item['title'], constants.dontneed, constants.dontneed_wholeword))
                            certainty = data.similar(query, result_filtered)
                            if(certainty < constants.similarity_threshold):
                                pass
                            else:
                                if(certainty > most_certain[1]):
                                    most_certain = [result_item, certainty, 0.0]
                        if(not search_ranking):
                            break
                    certainty = most_certain[1] if most_certain[2] == 0.0 else ((most_certain[1] + most_certain[2])/2)
                    return [certainty, result_item]
                    iterate_success = True
                except Exception as e:
                    if("quota" in str(e).lower()):
                        time.sleep(1)
                    else:
                        print(traceback.format_exc())
                        return None

class ddg_platform:
    class result:
        def __init__(self, title, link):
            self.title = title
            self.link = link
        def as_dict(self):
            return self.__dict__

    def search(query):
        success = False
        delay = 2
        while(not success):
            try:
                headers = {
                    'User-Agent': random.choice(constants.user_agents)
                }

                page = requests.get(f"https://html.duckduckgo.com/html/?q={query}", headers=headers)
                res = []
                if("If this error persists, please let us know" in str(page.content)):
                    delay *= 2
                    print(f"You are being ratelimited, waiting {delay} seconds before retrying...")
                    if(delay >= 30):
                        success = True
                        res = False
                    sleep(delay)
                    continue
                soup = BeautifulSoup(page.content, "html.parser")
                elems = soup.find_all("div", class_="result__body")

                for elem in elems:
                    title = elem.find("a", class_="result__a")
                    if(title == None):
                        continue
                    else:
                        title = title.text
                    link = "https://" + " ".join(elem.find("a", class_="result__url").text.split())
                    res.append(ddg_platform.result(title, link).as_dict())

                success = True
                return res
            except Exception:
                print(traceback.format_exc())
                return None

    def search_track(query, use_spotify = False):
        if(len(query) <= 4):
            return None

        try:
            res = None
            srch = ddg_platform.search(f"{query} site:{'deezer.com' if (not use_spotify) else 'open.spotify.com'}")
            for srch_res in srch:
                if((not use_spotify and srch_res['link'].startswith("https://www.deezer.com/") and ("/artist/" not in str(srch_res['link'])) and ("/playlist/" not in str(srch_res['link'])) and ("/album/" not in str(srch_res['link']))) or
                (use_spotify and srch_res['link'].startswith("https://open.spotify.com"))):
                    res = srch_res['link']
                    # Remove non-numeric chars
                    res = re.sub("[^0-9]", "", res)
                    if(res == ""):
                        res = None
                    if(res != None):
                        return res

            return res
        except Exception as e:
            print(e)
            return None

class startpage_platform:
    class result:
        def __init__(self, title, link):
            self.title = title
            self.link = link
        def as_dict(self):
            return self.__dict__
    
    def search(query):
        success = False
        while(not success):
            # An extra precaution to not get ratelimited
            sleep(1)
            try:
                headers = {
                    'User-Agent': random.choice(constants.user_agents)
                }

                page = requests.get(f"https://www.startpage.com/sp/search?query={query}", headers=headers)
                res = []
                soup = BeautifulSoup(page.content, "html.parser")
                elems = soup.find_all("div", class_="w-gl__result__main")

                for elem in elems:
                    title = elem.find("h3").text
                    link = elem.find("a", class_="result-link")['href']
                    res.append(startpage_platform.result(title, link).as_dict())

                success = True
                return res
            except Exception as e:
                print(e)
                return None

    def search_track(query, use_spotify = False):
        if(len(query) <= 4):
            return None

        try:
            res = None
            srch = startpage_platform.search(f"{query} site:{'deezer.com' if (not use_spotify) else 'open.spotify.com'}")
            for srch_res in srch:
                if((not use_spotify and srch_res['link'].startswith("https://www.deezer.com/") and ("/artist/" not in str(srch_res['link'])) and ("/playlist/" not in str(srch_res['link'])) and ("/album/" not in str(srch_res['link']))) or
                (use_spotify and srch_res['link'].startswith("https://open.spotify.com"))):
                    res = srch_res['link']
                    # Remove non-numeric chars
                    res = re.sub("[^0-9]", "", res)
                    if(res == ""):
                        res = None
                    if(res != None):
                        return res

            return res
        except Exception as e:
            print(e)
            return None