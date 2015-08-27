#!/usr/bin/env python
import os.path
import sys
import nbformat
from jinja2 import DictLoader
from nbconvert.exporters import LatexExporter
import os
import bibtexparser
import requests
import re
from nbconvert.preprocessors.svg2pdf import SVG2PDFPreprocessor
import base64
import Image
from ipython_genutils.tempdir import TemporaryDirectory



def convert_notebook(notebook_filename, bibtex_filename):
    (body, resources) = convert_to_body_resources(notebook_filename, bibtex_filename)
    write_body_resources(notebook_filename, body, resources)
    

def convert_to_body_resources(notebook_filename, bibtex_filename):
    ## Initializing resources to have correct output directory
    notebook_name = notebook_filename.split('/')[-1].replace('.ipynb', '')
    #see https://github.com/jupyter/nbconvert/blob/fcc3a831295b373a7a9ee5e8e0dea175475f8f26/nbconvert/nbconvertapp.py#L288
    resources = {}
    #resources['config_dir'] = self.config_dir
    resources['unique_key'] = notebook_name
    resources['output_files_dir'] = '%s_files' % notebook_name

    own_notebook = nbformat.read(notebook_filename, as_version=4)

    # replace cite keys by bibtex citekeys:
    if bibtex_filename is not None and 'cite2c' in own_notebook['metadata']:
        with open(bibtex_filename, 'r') as bibtex_file:
            bibtex = bibtexparser.load(bibtex_file)
        cite2_key_to_bibtex_key = dict()
        for key, cite2c_entry in own_notebook['metadata']['cite2c']['citations'].iteritems():
            equal_bibtex_entries = [b for b in bibtex.entries if cite2c_bibtex_equal(cite2c_entry,b)]
            if (len(equal_bibtex_entries) == 1):
                cite2_key_to_bibtex_key[key] = equal_bibtex_entries[0]['ID']
            assert len(equal_bibtex_entries) < 2, ("expected at most "
                "one equal bibtex entry, got {:s}".format(str(equal_bibtex_entries)))
        for cell in own_notebook['cells']:
            for cite2_key, bibtex_key in cite2_key_to_bibtex_key.iteritems():
                if cell['cell_type'] == 'markdown':
                    cell['source'] = cell['source'].replace(cite2_key, bibtex_key)
   
    # find imgs and convert to resources
    resources['outputs'] = dict()
    for cell in own_notebook['cells']:
        if cell['cell_type'] == 'markdown':
            img_urls_filenames = re.findall(r"<img.*src=\"([^>]*/([^\.]*\.[a-z]*)[^\"]*)\"[^>]*>[^<]*</img>", cell['source'])
            for url, img_filename in img_urls_filenames:
                response = requests.get(url, stream=True)
                all_blocks = []
                if not response.ok:
                    continue
                for block in response.iter_content(1024):
                    all_blocks.append(block)
                data = ''.join(all_blocks)
                if img_filename.endswith('svg'):
                    svg_2_pdf = SVG2PDFPreprocessor()
                    pdfdata = svg_2_pdf.convert_figure(None, data)
                    pdfdata = base64.decodestring(pdfdata) # it is encoded by svg2pdfpreproc.. not sure if decoding is necessary
                    img_filename = img_filename.replace('.svg', '.pdf')
                    data = pdfdata
                if img_filename.endswith('gif'):
                    jpgdata = gif_to_jpg(data)
                    img_filename = img_filename.replace('.gif', '.jpg')
                    data = jpgdata
                resource_key = os.path.join(resources['output_files_dir'], img_filename)
                
                resources['outputs'][resource_key] = data
                
            # Replace the whole image tag by latex code with the correct filename
            cell['source'] = re.sub(r"<img.*src=\"[^>]*/([^\.]*\.[a-z]*)[^>]*>[^<]*</img>", 
                   "\\\\begin{center}\n" +
                   "\\\\adjustimage{max size={0.9\\linewidth}{0.9\\paperheight}}{" + 
                   resources['output_files_dir'] + "/" +
                   r"\1" + # here is the filename
                   "}\n"+ 
                   "\\end{center}\n",
                   cell['source'])
            
            cell['source'] = cell['source'].replace('.svg', '.pdf')
            cell['source'] = cell['source'].replace('.gif', '.jpg')
                       
                       
    # remove javascript/html outputs
    for cell in own_notebook['cells']:
        if cell['cell_type'] == 'code' and 'outputs' in cell:
            cell['outputs'] = remove_javascript_html_outputs(cell['outputs'])
        
        
    
    # do some custom replacements of html
    for cell in own_notebook['cells']:
        if cell['cell_type'] == 'markdown':
            cell['source'] = cell['source'].replace('<span class="todecide">', '\\begin{comment}\nTODECIDE\n')
            cell['source'] = cell['source'].replace('<span class="todo">', '\\begin{comment}\nTODO\n')
            cell['source'] = cell['source'].replace('</span>', '\n\\end{comment}\n')

            cell['source'] = cell['source'].replace("<div class=\"summary\">", "\\begin{keypointbox}")
            cell['source'] = cell['source'].replace("</div>", "\\end{keypointbox}")

            cell['source'] = cell['source'].replace("<li>", "\\item ")
            cell['source'] = cell['source'].replace("</li>", "").replace("<ul>", "").replace("</ul>", "")

    dl = DictLoader({'article.tplx':
    """
    ((*- extends 'base.tplx' -*))
    ((* block header *))
    ((* endblock header *))
    
    % only part-document, not complete document, so call not base constructor, but the one above
    ((* block body *))
        ((( super.super() )))
    ((* endblock body *))

    % is this removing code? unclear.. probaby removing stdout/stdin
    ((* block stream *))
    ((* endblock stream *))

    % Remove execute result stuff
    ((* block execute_result scoped *))
    ((* endblock execute_result *))


    ((* macro draw_figure(filename) -*))
    ((* set filename = filename | posix_path *))
    ((*- block figure scoped -*))

        %\\begin{figure}[ht]
        \\begin{center}
        \\adjustimage{max size={0.9\\linewidth}{0.9\\paperheight}}{((( filename )))}
        \\end{center}
        %\\end{figure}
        %{ \\hspace*{\\fill} \\\\}
    ((*- endblock figure -*))
    ((*- endmacro *))


    ((* block markdowncell scoped *))
    ((( cell.source | citation2latex | strip_files_prefix | markdown2latex(extra_args=["--chapters"]) )))
    ((* endblock markdowncell *))


    """})


    exportLatex = LatexExporter(extra_loaders=[dl])
    (body, resources) = exportLatex.from_notebook_node(own_notebook,resources=resources)
    
    # postprocess url links with footnotes
    body = re.sub(r"(\\href{([^}]*)}{[^}]*})", r"\1\\footnote{\\url{\2}}", body)
    return body, resources
                
def cite2c_bibtex_equal(cite2c_entry, bibtex_entry):
    title_equal = cite2c_entry['title'] == bibtex_entry['title'].replace('{','').replace('}','')
    url_equal = 'URL' in cite2c_entry and (cite2c_entry['URL'] == bibtex_entry['link'])
    if 'URL' not in cite2c_entry:
        print ("Url not there for", cite2c_entry)
    return title_equal or url_equal

def gif_to_jpg(gif_data):
    with TemporaryDirectory() as tmpdir:
        gif_file_name = os.path.join(tmpdir, 'temp-file.gif')
        open(gif_file_name, 'wb').write(gif_data)
        jpg_file_name = os.path.join(tmpdir, 'temp-file.jpg')
        gif_img = Image.open(gif_file_name)
        gif_img.convert('RGB').save(jpg_file_name)
        jpg_data = open(jpg_file_name, 'rb').read()
    return jpg_data

def remove_javascript_html_outputs(outputs):
    # text html and application javascript should be in keys of output data
    # if we have html/javascript output
    outputs = [o for o in outputs if (('data' not in o) or ('text/html' not in o['data']))]
    outputs = [o for o in outputs if (('data' not in o) or ('application/javascript' not in o['data']))]
    return outputs

def write_body_resources(notebook_filename, body, resources):
    notebook_file_base_name = notebook_filename.replace('.ipynb', '')
    tex_filename = notebook_file_base_name + '.tex'
    print tex_filename
    with open(tex_filename, 'w') as tex_file:
        tex_file.write(body.encode('utf8'))
    
    # Now store resources
    notebook_dir = os.path.dirname(notebook_filename)
    output_dir = os.path.join(notebook_dir, resources['output_files_dir'])
    try:
        os.mkdir(output_dir)
    except OSError:
        print(output_dir + " already existed.")
        
    for key in resources['outputs']:
        if not key.endswith('svg'):
            val = resources['outputs'][key]
            resource_filename = os.path.join(notebook_dir, key)
            with open(resource_filename, 'wb') as resource_file:
                resource_file.write(val)

if __name__ == '__main__':
    if (len(sys.argv) != 2):
        print ("Usage: ./convert_latex.py notebookfilename")
        sys.exit(0)
    convert_notebook(sys.argv[1], 'latex-only-tex/Deep_EEG_Learning.bib')
    
