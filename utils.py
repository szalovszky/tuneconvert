import re
from difflib import SequenceMatcher

class utils:
    def similar(a, b):
        return SequenceMatcher(None, a, b).ratio()

    def filter_data(artist, title, filter_list, filter_word_list, force_year = False):
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

        # Cut out unnecessary spaces from the Artist field
        artist = " ".join(artist.split())

        # Cut out Artist from Title field and Cut out unnecessary spaces from the Title field
        x = title.split()
        for i in range(len(x)):
            if((utils.similar(artist, x[i]) > .25) and (artist.split()[0] in x[i])):
                x[i] = ""
        title = " ".join(x)

        title = title.replace(artist + " - ", "")
        title = title.replace(artist, "")

        # Replace Year in titles (very common and confuses most search algos, but sometimes it may be relevant to keep it, so use the -y arg to skip this)
        if(force_year):
            x = title.split()
            for i in range(len(x)):
                x[i] = re.sub(r"^(19|[2-9][0-9])\d{2}$", '', x[i])
            title = " ".join(x)

        # Lastly, return the result
        return [artist, title]
    
    def compare_res(original_link, result_metadata, result_link, certainty, src_engine):
        res_str = f"[{round(certainty*100, 2)}% - {src_name(src_engine)}] {result_metadata[0]} - {result_metadata[1]}"
        if(certainty < similarity_threshold):
            return None
        else:
            res_str = "[SUCCESS] " + res_str
            prnt(res_str)
            return certainty