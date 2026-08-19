import json
import urllib.parse
import urllib.request

from vesper.tools import tool

@tool(description="Read the contents of a file at the given path")
def read_file(path: str) -> str:
    with open(path) as f:
        return f.read()

@tool(description="Search the web for a query and return a short text summary")
def web_search(query: str) -> str:
    params = urllib.parse.urlencode({"q": query, "format": "json", "no_html": 1})
    url = f"https://api.duckduckgo.com/?{params}"

    with urllib.request.urlopen(url, timeout=10) as response:
        data = json.loads(response.read())

    results = []
    if data.get("AbstractText"):
        results.append(data["AbstractText"])
    for topic in data.get("RelatedTopics", []):
        if "Text" in topic:
            results.append(topic["Text"])

    return "\n".join(results[:5]) or "No results found."

BUILTIN_TOOLS = [read_file, web_search]
