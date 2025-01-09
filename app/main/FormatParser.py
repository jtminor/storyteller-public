import json
import sys

def transform_to_json(indented_strings):
    """
    Transforms a list of indented strings into a JSON structure following a specific schema.

    Args:
        indented_strings (list): A list of strings, where indentation represents hierarchy.

    Returns:
        dict: A dictionary representing the JSON structure.
    """

    result = {
        "DISPLAY_NAME": "",
        "DESC": "",
        "AGENTS": {}
    }

    current_set = None
    for line in indented_strings:
        indent_level = len(line) - len(line.lstrip())
        line = line.strip()

        if not line:
            continue

        if indent_level == 0:
            # Top-level key
            key, desc = line.split(" - ")
            result["AGENTS"][key] = {
                "DESC": desc,
                "DATA": "",
                "TYPE": "set",
                "STATE": "needed",
                "PROMPTS": [],
                "MEMORIES": []
            }
            current_set = key
        else:
            # Sub-key within a set
            key, desc = line.split(" - ")
            result["AGENTS"][key] = {
                    "DESC": desc,
                    "DATA": "",
                    "TYPE": infer_type(key),
                    "STATE": "needed",
                    "PROMPTS": [],
                    "MEMORIES": []
                }
            result["AGENTS"][current_set]["DATA"] += key + ","


    return result

def infer_type(key):
    """Infers the TYPE based on the key."""
    if any(word in key for word in ["image", "snapshot", "shot", "poster"]):
        return "img"
    elif any(word in key for word in ["sound", "voice", "soundeffect", "music", "narration"]):
        return "audio"
    elif "location" in key:
        return "loc"
    return "txt"

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python format_parser.py <input_file>")
        sys.exit(1)

    input_file = sys.argv[1]
    file_name = input_file.rstrip(".txt")
    output_file = file_name + ".format.json"

    with open(input_file, 'r') as f:
        indented_strings = f.readlines()

    json_data = transform_to_json(indented_strings)

    with open(output_file, 'w') as f:
        json.dump(json_data, f, indent=4)

##example
#example.set - An example of a set type content item.
#   example.item - An example of a generic (txt) content item.
#   example.image - An example of a image type item.
#   example.audio - An example of an audio type item.
#
#