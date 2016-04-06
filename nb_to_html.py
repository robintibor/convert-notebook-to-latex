#!/usr/bin/env python

import os
import base64
import sys
import re
from nbconvert import HTMLExporter


if __name__ == '__main__':
    assert len(sys.argv) == 3, \
        './convert_nb_to_html.py [notebook filename] [html output filename]'
    input_file = sys.argv[1]
    output_file = sys.argv[2]

    base_dir = os.path.dirname(os.path.abspath(input_file))

    def to_base64(match):
        full_path = os.path.join(base_dir, match.group(0))
        print('Replacing ' + full_path)

        with open(full_path, 'rb') as img:
            enc = base64.b64encode(img.read()).decode()
            ext = os.path.splitext(full_path)[1]

        return 'data:image/' + ext[1:] + ';base64,' + enc

    html_exporter = HTMLExporter()
    body, resources = html_exporter.from_filename(input_file)

    img_regex = r"(?<=img src=\")[^\"]*"
    body = re.sub(img_regex, to_base64, body)

    with open(output_file, 'w') as f:
        f.write(body)
