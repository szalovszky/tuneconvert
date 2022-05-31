similarity_threshold = 0.275
mix_length_threshold = 750
link_timeout = 10
length_difference_threshold = 45
length_weight = 0.5

dontneed = [
    "(", ")", "/", "-", ".", "&", "[", "]", ":", "|", '"', "!", "?", "│", "▶",
    "music video", "videoclip", "videoklip", "prod", "version", "album",
    "official", "hivatalos", "radio edit", "full song",
    "lyrics", "lyric", "dalszöveg", "dirty", "explicit",
]

dontneed_wholeword = [
    "video", "ost", "nightcore", "uncensored",
    "feat", "by", "ft", "km",
    "hd", "4k",
]

user_agents = ["Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/101.0.4951.64 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/101.0.4951.64 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 12_3_1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/101.0.4951.64 Safari/537.36",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 15_4 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) CriOS/101.0.4951.44 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (iPad; CPU OS 15_4 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) CriOS/101.0.4951.44 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (iPod; CPU iPhone OS 15_4 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) CriOS/101.0.4951.44 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (Linux; Android 10) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/101.0.4951.61 Mobile Safari/537.36",
    "Mozilla/5.0 (Linux; Android 10; SM-A205U) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/101.0.4951.61 Mobile Safari/537.36",
    "Mozilla/5.0 (Linux; Android 10; LM-Q720) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/101.0.4951.61 Mobile Safari/537.36",
    "Mozilla/5.0 (Linux; Android 10; LM-X420) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/101.0.4951.61 Mobile Safari/537.36"]

dontsearch_links = [
    "www.youtube.com",
    "youtu.be"
]

output_html_start = """<html>
<head>
    <style>
        * {
            font-family: arial, sans-serif;
        }
        table {
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
    <title>${name} - Overview</title>
    <meta charset="UTF-8">
    <meta name="overview-version" content="${overview_version}">
    <meta name="app-name" content='${name}'>
    <meta name="app-author" content='${author}'>
    <meta name="app-version" content='${version}'>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body>
    <h1 id='title'>${name} - Result overview</h1>
    <p id='run-id'>Run ID: <code>${run_id}</code></p>
    <a class='c1-link' href='output.txt'>Output file</a> | 
    <a class='c1-link' href='output.json'>Output JSON</a> | 
    <a class='c1-link' href='failed.txt'>Failed</a> | 
    <a class='c1-link' href='unavailable.txt'>Unavailable</a> | 
    <a class='c1-link' href='options.json'>Settings</a> | 
    <a class='c1-link' href='log.txt'>Log</a><br />
    <a class='c2-link' href='data:text/plain;charset=UTF-8,out.txt' download='output.txt'><b>Download Output file</b></a> | 
    <a class='c2-link' href='data:text/plain;charset=UTF-8,out.json' download='output.json'><b>Download Output JSON</b></a> | 
    <a class='c2-link' href='data:text/plain;charset=UTF-8,options.json' download='settings.json'><b>Download Settings</b></a><br />
    <table>
    <tr>
        <th>Status</th>
        <th>Score</th>
        <th>Original</th>
        <th>Found</th>
        <th>Query</th>
    </tr>"""

output_html_end = """</table>
</body>
</html>"""

def gen_output_html(start=True, **objects):
    html = output_html_start if start else output_html_end
    if(len(objects) > 0):
        for obj in objects:
            html = html.replace("${"+obj+"}", str(objects[obj]))
    return html

class colors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'
