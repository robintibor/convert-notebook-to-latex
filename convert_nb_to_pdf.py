#!/usr/bin/env python

import os
import re
import nbformat
from nbconvert.exporters import LatexExporter, PDFExporter
from nbconvert.writers import FilesWriter
from traitlets.config import Config
import sys

def convert_notebook(notebook_filename, output_dir=None, exporter=PDFExporter()):
    """Convert notebook. 
    To PDF unless specified differently by exporter."""
    (body, resources) = convert_to_body_resources(notebook_filename, exporter=exporter)
    write_body_resources(notebook_filename, body, resources, output_dir=output_dir)
    
def convert_to_body_resources(notebook_filename, exporter=LatexExporter()):
    """Convert notebook to body and resources... replaces markdown local images on the way."""
    ## Read the actual notebook
    notebook = nbformat.read(notebook_filename, as_version=4)
    notebook, resources = preprocess_markdown_local_images(notebook, notebook_filename)
    
    if exporter is None:
        exporter = LatexExporter()
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

   
    # Find local images with 
    #![Alt text](/path/to/img.jpg "Optional title") tags
    # read out image files and add to resources dict
    resources['outputs'] = dict()
    for cell in notebook['cells']:
        if cell['cell_type'] == 'markdown':
            # It will find the images. Hopefully.
            all_img_filenames = re.findall(r"!\[[^\]]*\]\(([^ \"']*)[^\)]*\)", cell['source'])

            for img_filename in all_img_filenames:
                # replace directory by two __
                # could lead to name collisions but quite unlikely...
                # just in case there is for examplea file img/1.jpg
                # and a file img__1.jpg...
                img_no_dir_name = "__".join(os.path.split(img_filename))
                resource_key = os.path.join(resources['output_files_dir'], img_no_dir_name)
                
                with open(img_filename, 'rb') as img_file:
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
            
            cell['source'] = re.sub(r"!\[[^\]]*\]\(([^ \"']*)[^\)]*\)", 
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
    """Ensure directory exists by creating it if it does not exist."""
    # see http://stackoverflow.com/a/273227/1469195
    # there is a exotic race condition here, that I couldn't really care less about :P
    # (if the directory is created (e.g., from another program)
    # between the if check and the os makedirs,
    # there will be an error...)
    if not os.path.exists(directory_name):
        os.makedirs(directory_name)
    

def write_body_resources(notebook_filename, body, resources, output_dir=None):
    """Write actual notebook and files to output dir.
    Use notebook directory if output dir is none"""
    if output_dir is None:
        notebook_base_dir = os.path.split(notebook_filename)[0]
        output_dir = notebook_base_dir
    config = Config()
    config.FilesWriter.build_directory = output_dir
    file_writer = FilesWriter(config=config)
    file_writer.write(body, resources, notebook_name=to_notebook_basename(notebook_filename))
    
    
if __name__ == '__main__':
    if (len(sys.argv) != 2 and len(sys.argv) != 3):
        print ("Usage: ./convert_latex.py notebook_filename [output_directory]")
        sys.exit(0)
    notebook_filename = sys.argv[1]
    if len(sys.argv) > 2:
        output_dir = sys.argv[2]
    else:
        output_dir = None
    convert_notebook(notebook_filename, output_dir=output_dir, exporter=PDFExporter())