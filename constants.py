similarity_threshold = 0.275

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

src_names = {
    0: "DeezerTrackMethod0",
    1: "DescriptionLinkParse",
    2: "DeezerTrackMethod1",
    3: "DeezerTrackMethod2",
    4: "DeezerAlbum",
    5: "Shazam"
}

def src_name(src):
    if(src > (len(src_names)-1)):
        return ""
    else:
        return src_names[src]