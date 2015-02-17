#! /usr/bin/env python3
# -*- coding: utf-8 -*-

# Convert in-text references (URLs) to sequentially numbered footnotes and
# change text-based files (like HTML) to proper plaintext in the process.
# 
# Copyright (c) 2015 K Kollmann <code∆k.kollmann·moe>
# License: http://opensource.org/licenses/MIT The MIT License (MIT)

# You need to have Python 3.x installed to run this script.
# Use -h or --help for help on how to use the program.
#
# The script currently supports conversion of .txt and .html/.htm files.
# Round brackets containing URLs and square brackets get converted
# to footnotes. Round brackets containing other text (including any nested
# brackets) and square brackets within quotes to denote changes to
# original citations as well as [sic] and [sic!] are ignored.
#
# TODO:
# - ignore or warn on square brackets containing only digits
#   as these might already be footnotes
#   (possibly then check for appendix, integrate existing footnotes via cli option)
# - option to include begin text in conversion
# - option to re-index an existing appendix / to combine old and new refs
# - option to rename the output file
# - rename all converted files with references to .txt (keep .html for unconverted)

import sys
import os
import re
import argparse
import errno
from urllib.parse import urlparse
from collections import OrderedDict
from html.parser import HTMLParser
import html.entities

class HTMLClean(HTMLParser):
    """Class to clean HTML tags
    and entities, including script tags.
    """
    def __init__(self):
        HTMLParser.__init__(self)
        self.result = []
        self.urls = []

    def handle_starttag(self, tag, attrs):
        """Look for hyperlinks and filter out their href attribute.
        """
        if tag == "a":
            for attr in attrs:
                if attr[0] == "href":
                    the_url = attr[1].strip()
                    if the_url:
                        self.urls.append(the_url)
                        self.result.append(the_url)

    def handle_data(self, data):
        """Add content enclosed within various HTML tags.
        """
        # strip whitespace produced by html indentation
        data = re.sub('( +\n +)', ' ', data)
        data = re.sub('(\n +)', '\n', data)
        self.result.append(data)

    def handle_entityref(self, name):
        """Convert HTML entities to their Unicode representations.
        """
        html_entities = html.entities.name2codepoint[name]
        self.result.append(chr(html_entities))

    def handle_endtag(self, tag):
        """Look for hyperlinks whose <a></a> tags include a description,
        then switch URL and description (as saved in the results list).
        Remove hyperlinks whose <a></a> tags surround other content.
        """
        count_data = len(self.result)
        if tag == "a" and count_data >= 2:
            descriptions = []
            urls_copy = self.urls.copy()
            # remove hyperlink descriptions before closing </a> tags
            # if they do not belong to proper hyperlinks
            # + join hyperlink descriptions that belong together
            if len(urls_copy) >= 1:
                last_url = urls_copy.pop(-1)
                while True and count_data >= 2:
                    last_data = self.result.pop(-1)
                    count_data -= 1
                    if last_data == last_url:
                        break
                    else:
                        descriptions.append(last_data)
                if len(descriptions) == 0:
                    pass
                else:
                    if len(descriptions) > 1:
                        descriptions.reverse()
                        descriptions_collected = ''.join(descriptions)
                    else:
                        descriptions_collected = descriptions[0]
                    url = urlparse(last_url)
                    if url.scheme is not '' and url.netloc is not '':
                        self.result.append(descriptions_collected)
                        self.result.append(" (" + last_url + ")")
        # remove any data that was inside <script> or <style> tags
        if (tag == "script" or tag
                == "style") and len(self.result) >= 1:
            script = self.result.pop(-1)
    def concatenate(self):
        """Concatenate all individual pieces of data,
        trim whitespace at beginning and end of file and
        remove any remaining weird newline formatting.
        """
        fulltext = u''.join(self.result)
        fulltext = fulltext.lstrip()
        fulltext = fulltext.rstrip()
        fulltext = re.sub('(\w)( *)(\n)(\w)', r'\1 \4', fulltext)
        fulltext = re.sub('( *\n\n+ *)', '\n\n', fulltext)
        return fulltext

def html_to_text(html):
    content = HTMLClean()
    content.feed(html)
    return content.concatenate()

def inspectbrackets(matchobj):
    """Further break down the regex matches for brackets and quotes.
    """
    global counter
    global references
    fullref = matchobj.group(0)
    brkts_rd_content = matchobj.group('rd')
    brkts_sq_inquote = matchobj.group('sq_qu_reg')
    brkts_sq_inquote_2 = matchobj.group('sq_qu_form')
    brkts_sq_content = matchobj.group('sq')
    # regex search found round brackets
    if brkts_rd_content is not None:
        # verify brackets start with URL;
        # check for attributes: scheme (URL scheme specifier) and
        # netlocat (Network location part)
        url = urlparse(brkts_rd_content)
        if url.scheme is not '' and url.netloc is not '':
            if brkts_rd_content in references:
                refno = references[brkts_rd_content]
                # status message
                print("::: Note: Multiple occurrence of reference\n"
                        "    {}".format(brkts_rd_content))
            else:
                counter += 1
                refno = counter
                references[brkts_rd_content] = refno
            ref = "[" + str(refno) + "]"
            return ref
        # return original bracket content if it's not a URL
        else:
            return fullref
    # regex search found square brackets    
    elif brkts_sq_inquote is not None or brkts_sq_inquote_2 is not None:
        return fullref
    elif brkts_sq_content is not None:
        if brkts_sq_content != 'sic' and brkts_sq_content != 'sic!':

            if brkts_sq_content in references:
                refno = references[brkts_sq_content]
                # status message
                print("::: Note: Multiple occurrence of reference\n"
                        "    \"{}\"".format(brkts_sq_content))
            else:
                counter += 1
                refno = counter
                references[brkts_sq_content] = refno
            ref = "[" + str(refno) + "]"
            return ref
        else:
            return fullref
    # regex search did not find any brackets in this line
    else:
        return fullref

def writeappendix():
    """Write an appendix (list of references/footnotes).
    """
    global references
    # separate footnotes with separator. use _ instead of dashes
    # as -- is read as the beginning of a signature by e-mail clients
    fout.write("___\n")
    # write appendix/bibliography to output file
    for ref, no in references.items():
        fout.write("[{}] {}\n" .format(no, ref))

parser = argparse.ArgumentParser(
        formatter_class=argparse.RawTextHelpFormatter,
        description = '''---------------
%(prog)s is a program to change text-based files (like HTML)
to proper plaintext and to convert any references (like URLs or citations)
to sequentially numbered footnotes which are appended to the file.

References used for footnotes are URLs enclosed in round brackets
as well as any other text enclosed in square brackets.
Regular text in round brackets, if not preceded by a URL, is ignored.

See https://github.com/kerstin/plaintextref for a more detailed description.
---------------
''')
parser.add_argument("filename",
    help='''name of (path to) the file you want to convert;
supported file types are: .txt, .html/.htm, .md''')
parser.add_argument('-b','--begin', dest="begin", metavar="TEXT",
    help = '''define where to begin scanning an HTML file
e.g. --begin \"<body>\",
e.g. --b \"2 February 2015\"''')
parser.add_argument('-c','--contain', dest="contain", action="store_true",
    help = '''run argument -b containg the text provided;
by default, parsing begins only after the given string''')
# parser.add_argument('-i','--images', dest="images", action="store_true",
#     help = '''treat image files in <a></a> tags as part of the link description;
# default is to strip <img> tags from converted HTML files''')
parser.add_argument('-a','--append', dest="suffix", metavar="SUFFIX",
    default="_plaintext",
    help = '''the suffix to append to the filename of the output file;
defaults to _plaintext getting added to the original filename''')
# parser.add_argument('-s','--save', dest="suffix", metavar="FILENAME",
#     default="plaintext",
#     help = '''the name to save the new file under if you do not want to
# simply append a suffix to the original filename (see -a);
# the file extension gets added automatically in any case
# ''')
parser.add_argument('-p','--path', dest="path",
    help = '''path to save the converted file to if you do not want
to save it in the same directory as the original file
''')
# parser.add_argument('-r','--re-index', dest="reindex", action="store_true",
#     help = '''if there are already footnotes and an appendix present,
# renumber existing references and incorporate them
# into a new appendix including both old and new references''')
parser.add_argument('-n','--noref', dest="noref", action="store_true",
    help = '''convert the file to plaintext, but don't create an appendix;
useful if you just want to strip HTML tags''')
args = parser.parse_args()

# create an ordered dictionary to store all references
# add counter for references
# add counter for e-mail signature
references = OrderedDict()
suffix = args.suffix
counter = 0
signature = 0

if __name__ == "__main__":

    fullpath = os.path.realpath(args.filename)
    # validate provided filename/path

    try:
        f = open(fullpath, 'r')
    except OSError as e:
        # filename is a directory or invalid filename
        if e.errno == errno.EISDIR or e.errno == errno.ENOENT:
            sys.exit("You did not specify a valid file name.")
        # no permission to read the file
        elif e.errno == errno.EACCES:
            sys.exit("The specified file cannot be read from.")
        else:
            print(e)
    else:
        filepath, filename = os.path.split(fullpath)
        if filepath[-1:] is not "/":
            filepath += '/'
    finally:
        f.close()

    # ------------ start filename/path check mess
    cwd = os.getcwd()
    if cwd[-1:] is not "/":
        cwd += '/'

    # print("cwd: " +cwd) #debug

    # validate provided new path
    if args.path:
        newpath = args.path
        if newpath != filepath:
            # path provided is invalid
            if os.path.isdir(newpath) == False:
                # status message
                print("The specified path is not a valid directory.\n"
                        "Defaulting to directory containing the original file.")
                if filepath == cwd:
                    # status message
                    print("(= The current working directory.)")
                newpath = filepath
            # path provided is not writeable
            elif os.access(newpath, os.W_OK) == False:
                # status message
                print("The specified path is not a writeable directory.\n"
                "Defaulting to directory containing the original file.")
                if filepath == cwd:
                    # status message
                    print("(= The current working directory.)")
                newpath = filepath
            else:
                pass
            if newpath[-1:] is not "/":
                newpath += '/'
    else:
        newpath = filepath

    # print("------") #debug
    # print("filepath: " +filepath) #debug
    # print("newpath: " +newpath) #debug
    # print("cwd: " +cwd) #debug

    if newpath == cwd:
        if os.access(cwd, os.W_OK) == False:
            if newpath == filepath:
                # exit/error message
                sys.exit("The current working directory is not writeable either.\n"
                            "Exiting.")
            else:
                # exit/error message
                sys.exit("The current working directory is not writeable.\n"
                            "Exiting.")
    else:
        if os.access(newpath, os.W_OK) == False:
            # exit/error message
            print("The directory containing the original file is not "
                        "writeable.\nTrying the current working directory.")
            newpath = cwd
            if os.access(cwd, os.W_OK) == False:
                    # exit/error message
                    sys.exit("The current working directory is not writeable either.\n"
                                "Exiting.")
        else:
            if newpath == filepath and newpath == cwd:
                # print("all the same dir") #debug
                pass
            elif newpath != filepath and newpath == cwd:
                # print("current wd, cwd = " + cwd) #debug
                pass
            else:
                # print("everything fine") #debug
                pass
            pass
    # ------------ end filename/path check mess

    fileroot, extension = os.path.splitext(filename)
    # check for file root and extension
    if extension is "":
        # status message
        print("::: Attn: the provided file has no file extension")
        separator = ""
    else:
        separator = "."
        extsplit = extension.split(separator)
        extension = extsplit[-1]
    filename_out = newpath + fileroot + suffix + separator + extension
    # print("output file: " +filename_out) #debug

    # check for valid file types

    # only allow files up to 1MB in size
    if os.path.getsize(fullpath) <= 1000000:
        with open(fullpath, 'r', encoding='utf-8') as f:
            # Markdown still unsupported
            if extension == 'md':
                sys.exit("Sorry, Markdown conversion is not yet supported. ):")
            else:
                print("Reading input file...")
            if extension == 'htm' or extension == 'html':
                # status message
                print("Converting HTML to plaintext...")
                # read in html file as one string
                # and split at user-provided tag or string if present
                html_string = f.read()
                if args.begin:
                    beginparse = args.begin
                    html_split = html_string.split(beginparse, maxsplit=1)
                    if len(html_split) > 1:
                        if args.contain is True:
                            parsestring = beginparse + html_split[1]
                        else:
                            parsestring = html_split[1]
                        html_stripped = html_to_text(parsestring)
                    else:
                        # status message
                        print("::: Attn: the starting point provided by you "
                            "was _not_ found.")
                        html_stripped = html_to_text(html_split[0])
                else:
                    html_stripped = html_to_text(html_string)
                # create iterable list of lines
                html_stripped_lines = html_stripped.splitlines(True)
                with open(filename_out, 'w+', encoding='utf-8') as fout:
                    fout.write(html_stripped)
                # don't create any footnotes if --noref flag is set
                # (only converts html to plaintext)
                if args.noref:
                    # status message
                    print("DONE.\n")
                    print("The output file is: {}" .format(fout.name))
                    sys.exit()

            with open(filename_out, 'w+', encoding='utf-8') as fout:
                # status message
                print("Creating footnotes...")
                if extension == 'html' or extension == 'htm':
                    source = html_stripped_lines
                else:
                    source = f
                # iterate over all lines
                for line in source:
                    # if the current line does not mark an e-mail signature
                    if line != "--\n":
                        # search and substitute lines using regex
                        # find all round and square brackets
                        # find all square brackets within quotes
                        line_out = re.sub(""
                            "(?#check for round brackets)"
                            "([ ]*[\(])(?P<rd>[^\(\)]*)([\)])"
                            "(?#check for square brackets inside regular quotation marks)"
                            "|([\"][^\"[]*)([\[])(?P<sq_qu_reg>[^\"\]]+)([\]])([^\"]*[\"])"
                            "(?#check for square brackets inside formatted quotation marks)"
                            "|([“][^“”[]*)([\[])(?P<sq_qu_form>[^”\]]+)([\]])([^”]*[”])"
                            "(?#check for square brackets)"
                            "|([ ]*[\[])(?P<sq>[^\[\]]*)([\]])",
                                inspectbrackets, line)
                        # write back all lines (changed or unchanged)
                        fout.write(line_out)
                    # include appendix before e-mail signature
                    # if the current line marks such a signature (--)
                    else:
                        signature = 1
                        if len(references) > 0:
                            writeappendix()
                        fout.write("\n" +line)
                # include appendix at end if no signature was found
                if signature == 0 and len(references) > 0:
                    fout.write("\n\n")
                    writeappendix()
                # status message
                print("DONE.\n")
                print("The output file is: {}" .format(fout.name))
    else:
        print("File size must be below 1MB.")