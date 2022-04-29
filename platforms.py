import traceback
import time
import deezer

import constants
from utils import utils
import platforms

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
                        artist_sum += utils.filter_data(m_artist['name'], "", constants.dontneed, constants.dontneed_wholeword)[0] + " "
                    artist = ' '.join(utils.unique_list(artist_sum.split()))
                artist_filtered = utils.filter_data(artist, "", constants.dontneed, constants.dontneed_wholeword)[0]
                title_filtered = utils.filter_data("", result_item['title'], constants.dontneed, constants.dontneed_wholeword)[1]
                artist_certainty = utils.similar(query[0], artist_filtered)
                title_certainty = utils.similar(query[1], title_filtered)
                if((artist_certainty < constants.similarity_threshold) or (title_certainty < constants.similarity_threshold)):
                    return False
                else:
                    return [((artist_certainty + title_certainty)/2), result_item]
            else:
                result_filtered = " ".join(utils.filter_data(result_item['artist']['name'], result_item['title'], constants.dontneed, constants.dontneed_wholeword))
                certainty = utils.similar(query, result_filtered)
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
                                    artist_sum += utils.filter_data(m_artist['name'], "", constants.dontneed, constants.dontneed_wholeword)[0] + " "
                                artist = ' '.join(utils.unique_list(artist_sum.split()))
                            artist_filtered = utils.filter_data(artist, "", constants.dontneed, constants.dontneed_wholeword)[0]
                            title_filtered = utils.filter_data("", result_item['title'], constants.dontneed, constants.dontneed_wholeword)[1]
                            artist_certainty = utils.similar(query[0], artist_filtered)
                            title_certainty = utils.similar(query[1], title_filtered)
                            if((artist_certainty < constants.similarity_threshold) or (title_certainty < constants.similarity_threshold)):
                                pass
                            else:
                                if(artist_certainty > most_certain[1]):
                                    most_certain = [result_item, artist_certainty, title_certainty]
                                if((artist_certainty > most_certain[1]) and (title > most_certain[2])):
                                    most_certain = [result_item, artist_certainty, title_certainty]
                        else:
                            result_filtered = " ".join(utils.filter_data(result_item['artist']['name'], result_item['title'], constants.dontneed, constants.dontneed_wholeword))
                            certainty = utils.similar(query, result_filtered)
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