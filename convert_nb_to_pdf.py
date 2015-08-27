#!/usr/bin/env python

import os
import re
import nbformat
from nbconvert.exporters import LatexExporter, PDFExporter
from nbconvert.writers import FilesWriter
from traitlets.config import Config
import sys
from jinja2 import DictLoader
import argparse

def convert_notebook(notebook_filename, output_dir=None, exporter_class=PDFExporter):
    """Convert notebook. 
    To PDF unless specified differently by exporter."""
    assert exporter_class == PDFExporter or exporter_class == LatexExporter
    (body, resources) = convert_to_body_resources(notebook_filename, exporter_class=exporter_class)
    if exporter_class == LatexExporter:
        write_body_resources(notebook_filename, body, resources, output_dir=output_dir)
    else:
        write_only_body(notebook_filename, body, output_dir=output_dir)
        
    
def convert_to_body_resources(notebook_filename, exporter_class=PDFExporter):
    """Convert notebook to body and resources... replaces markdown local images on the way."""
    ## Read the actual notebook
    notebook = nbformat.read(notebook_filename, as_version=4)
    notebook, resources = preprocess_markdown_local_images(notebook, notebook_filename)
    
    # Overwrite article style    
    dl = DictLoader({'article.tplx':
    """
    % Default to the notebook output style
    ((* if not cell_style is defined *))
        ((* set cell_style = 'style_ipython.tplx' *))
    ((* endif *))

    % Inherit from the specified cell style.
    ((* extends cell_style *))


    %===============================================================================
    % Latex Article
    %===============================================================================

    ((* block docclass *))
    % In case you want to change it
    \documentclass{article}
    ((* endblock docclass *))
    
    ((* block header *))
        ((( super() )))
        % Indentation, no indetation for paragraphs, but blank lines
        \setlength{\parskip}{\medskipamount}
        \setlength{\parindent}{0pt}

    ((* endblock header *))
    """})
        
    if exporter_class is None:
        exporter = LatexExporter(extra_loaders=[dl])
    else:
        exporter = exporter_class(extra_loaders=[dl])
    (body, resources) = exporter.from_notebook_node(notebook,resources=resources)
    return body, resources
    
    
def preprocess_markdown_local_images(notebook, notebook_filename):
    """ Replace markdown local images by corresponding latex code and 
    add images to resources.
    Side effect: modifies notebook object itself."""
    ## Initialize resources to have correct output directory
    notebook_name = to_notebook_basename(notebook_filename)
    # see https://github.com/jupyter/nbconvert/blob/fcc3a831295b373a7a9ee5e8e0dea175475f8f26/nbconvert/nbconvertapp.py#L288
    resources = {}
    resources['unique_key'] = notebook_name
    notebook_out_dir = '%s_files' % notebook_name
    resources['output_files_dir'] = notebook_out_dir
    notebook_dir = os.path.dirname(notebook_filename)
   
    # Find local images with 
    #![Alt text](/path/to/img.jpg "Optional title") tags
    # read out image files and add to resources dict
    resources['outputs'] = dict()
    for cell in notebook['cells']:
        if cell['cell_type'] == 'markdown':
            # It will find the images. Hopefully. (it will capture img filename by capturing imggroup)
            img_tag_match_regex = r"!\[[^\]]*\]\(([^ \"'\)]*)[^\)]*\)"
            all_img_filenames = re.findall(img_tag_match_regex, cell['source'])

            for img_filename in all_img_filenames:
                # replace directory by two __
                # could lead to name collisions but quite unlikely...
                # just in case there is for examplea file img/1.jpg
                # and a file img__1.jpg...
                img_no_dir_name = "__".join(os.path.split(img_filename))
                resource_key = os.path.join(resources['output_files_dir'], img_no_dir_name)
                img_path = os.path.join(notebook_dir, img_filename)
                with open(img_path, 'rb') as img_file:
                    data = img_file.read()
                    resources['outputs'][resource_key] = data
                
            # Replace the whole image tag by latex code with the complete filename
            # We now still have the filename with the path/directory structure, 
            # so put markers around it (fix_adjust_image)
            # to later replace the forward slashes
            # by two underscores
            marker = 'fix_adjust_image'
            # make sure marker does not exist in the cell source
            # just repeat the marker until it is not in the string anymore
            while marker in cell['source']:
                marker += 'fix_adjust_image'
            
            cell['source'] = re.sub(img_tag_match_regex,
                   "\\\\begin{center}\n" +
                   "\\\\adjustimage{max size={0.9\\linewidth}{0.9\\paperheight}}{" + 
                   resources['output_files_dir'] + "/" +
                    marker +
                   r"\1" + # \1 is the filename (by backreference to group matched by parantheses)
                   marker +
                   "}\n"+ 
                   "\\end{center}\n",
                   cell['source'])
            
            # now split it by the marker and correct the filenames 
            # (replace "/" by "__")
            cell_src_parts = re.split(marker, cell['source'])
            for i in xrange(len(cell_src_parts)):
                # now every odd index will be a filename
                # in case there is no match there will be only one element
                # in the list (the original string) and this will not change anything
                if i % 2 == 1:
                    cell_src_parts[i] = "__".join(os.path.split(cell_src_parts[i]))
            cell['source'] = ''.join(cell_src_parts)
    return notebook, resources
    
    
    
def to_notebook_basename(notebook_filename):
    """Only keep file basename (remove directory and .ipynb extension)"""
    return os.path.split(notebook_filename)[1].replace('.ipynb', '')

def ensure_directory_exists(directory_name):
    """Ensure directory exists by creating it if it does not exist.
    Ignores empty string."""
    # see http://stackoverflow.com/a/273227/1469195
    # there is a exotic race condition here, that I couldn't really care less about :P
    # (if the directory is created (e.g., from another program)
    # between the if check and the os makedirs,
    # there will be an error...)
    if not os.path.exists(directory_name) and not directory_name == '':
        os.makedirs(directory_name)
    

def write_body_resources(notebook_filename, body, resources, output_dir=None):
    """Write actual notebook and files to output dir.
    Use notebook directory if output dir is none"""
    output_dir = determine_output_dir(notebook_filename, output_dir)
    config = Config()
    config.FilesWriter.build_directory = output_dir
    file_writer = FilesWriter(config=config)
    file_writer.write(body, resources, notebook_name=to_notebook_basename(notebook_filename))
    
def write_only_body(notebook_filename, body, output_dir=None):
    output_dir = determine_output_dir(notebook_filename, output_dir)
    config = Config()
    config.FilesWriter.build_directory = output_dir
    file_writer = FilesWriter(config=config)
    resources = dict() # no resources since we don't want files written
    file_writer.write(body, resources, notebook_name=to_notebook_basename(notebook_filename))
    
def determine_output_dir(notebook_filename, output_dir):
    if output_dir is None:
        notebook_base_dir = os.path.split(notebook_filename)[0]
        output_dir = notebook_base_dir
    return output_dir
    

def parse_command_line_arguments():
    parser = argparse.ArgumentParser(
        description="""Convert notebook to pdf an experiment from a YAML experiment file.
        Example: ./convert_nb_to_pdf.py notebooks/Example_Notebook.yaml --outdir out --pdf """
    )
    parser.add_argument('notebook_file_name', action='store',
                        choices=None,
                        help='File name of notebook to convert')
    
    group_convert_type = parser.add_mutually_exclusive_group(required=True)
    
    group_convert_type.add_argument("--pdf", action="store_true",  help="Convert to pdf.")
    group_convert_type.add_argument("--latex", action="store_true", help="Convert to latex.")
    parser.add_argument('--outdir', action='store',
                        default=None,
                        help='Directory to write latex or pdf output to. Defaults to same directory as notebook.')
    args = parser.parse_args()
    return args
    
if __name__ == '__main__':
    args = parse_command_line_arguments()
    notebook_filename = args.notebook_file_name
    output_dir = args.outdir

    if args.pdf:
        exporter_class = PDFExporter
    else:
        exporter_class = LatexExporter
        
    convert_notebook(notebook_filename, output_dir=output_dir, exporter_class=exporter_class)