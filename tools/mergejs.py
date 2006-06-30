#!/usr/bin/env python
#
# Merge multiple JavaScript source code files into one.
#
# Usage:
# This script requires source files to have dependencies specified in them.
#
# Dependencies are specified with a comment of the form:
#
#     // @require: <file path>
#
#  e.g.
#
#    // @require: Geo/DataSource.js
#
# This script should be executed like so:
#
#     mergejs.py <output.js> <directory> [...]
#
# e.g.
#
#     mergejs.py openlayers.js Geo/ CrossBrowser/
#
#  This example will cause the script to walk the `Geo` and
#  `CrossBrowser` directories--and subdirectories thereof--and import
#  all `*.js` files encountered. The dependency declarations will be extracted
#  and then the source code from imported files will be output to 
#  a file named `openlayers.js` in an order which fulfils the dependencies
#  specified.
#
#
# Note: This is a very rough initial version of this code.
#
# -- Copyright 2005-2006 MetaCarta, Inc. / OpenLayers project --
#

# TODO: Allow files to be excluded. e.g. `Crossbrowser/DebugMode.js`?
# TODO: Report error when dependency can not be found rather than KeyError.

import re
import os
import sys

SUFFIX_JAVASCRIPT = ".js"

RE_REQUIRE = "@require: (.*)\n" # TODO: Ensure in comment?
class SourceFile:
    """
    Represents a Javascript source code file.
    """

    def __init__(self, filepath, source):
        """
        """
        self.filepath = filepath
        self.source = source

        self.requiredBy = []


    def _getRequirements(self):
        """
        Extracts the dependencies specified in the source code and returns
        a list of them.
        """
        # TODO: Cache?
        return re.findall(RE_REQUIRE, self.source)

    requires = property(fget=_getRequirements, doc="")



def usage(filename):
    """
    Displays a usage message.
    """
    print "%s [-c <config file>] <output.js> <directory> [...]" % filename


class Config:
    """
    Represents a parsed configuration file.

    A configuration file should be of the following form:

        [first]
        3rd/prototype.js
        core/application.js
        core/params.js

        [last]
        core/api.js

        [exclude]
        3rd/logger.js

    All headings are required.

    The files listed in the `first` section will be forced to load
    *before* all other files (in the order listed). The files in `last`
    section will be forced to load *after* all the other files (in the
    order listed).

    The files list in the `exclude` section will not be imported.
    
    """

    def __init__(self, filename):
        """
        Parses the content of the named file and stores the values.
        """
        lines = [line[:-1] # Assumes end-of-line character is present
                 for line in open(filename)
                 if line != "\n"] # Skip blank lines

        self.forceFirst = \
                    lines[lines.index("[first]") + 1:lines.index("[last]")]

        self.forceLast = \
                      lines[lines.index("[last]") + 1:lines.index("[exclude]")]
        
        self.exclude =  lines[lines.index("[exclude]") + 1:]

if __name__ == "__main__":
    import getopt

    options, args = getopt.getopt(sys.argv[1:], "-c:")
    
    try:
        outputFilename = args[0]
    except IndexError:
        usage(sys.argv[0])
        raise SystemExit
    else:
        sourceDirectory = args[1]
        if not sourceDirectory:
            usage(sys.argv[0])
            raise SystemExit

    cfg = None
    if options and options[0][0] == "-c":
        filename = options[0][1]
        print "Parsing configuration file: %s" % filename

        cfg = Config(filename)

    allFiles = []

    ## Find all the Javascript source files
    for root, dirs, files in os.walk(sourceDirectory):
	for filename in files:
	    if filename.endswith(SUFFIX_JAVASCRIPT) and not filename.startswith("."):
		filepath = os.path.join(root, filename)[len(sourceDirectory)+1:]
		if (not cfg) or (filepath not in cfg.exclude):
		    allFiles.append(filepath)

    ## Header inserted at the start of each file in the output
    HEADER = "/* " + "=" * 70 + "\n"\
             "    %s\n" +\
             "   " + "=" * 70 + " */\n\n"

    files = {}

    order = [] # List of filepaths to output, in a dependency satisfying order 

    ## Import file source code
    ## TODO: Do import when we walk the directories above?
    for filepath in allFiles:
        print "Importing: %s" % filepath
	fullpath = os.path.join(sourceDirectory, filepath)
        content = open(fullpath, "U").read() # TODO: Ensure end of line @ EOF?
        files[filepath] = SourceFile(filepath, content) # TODO: Chop path?

    ## Resolve the dependencies
    print "\nResolving dependencies...\n"

    from toposort import toposort

    nodes = []
    routes = []

    for filepath, info in files.items():
        nodes.append(filepath)
        for neededFilePath in info.requires:
            routes.append((neededFilePath, filepath))

    for dependencyLevel in toposort(nodes, routes):
        for filepath in dependencyLevel:
            order.append(filepath)


    ## Move forced first and last files to the required position
    if cfg:
        print "Re-ordering files...\n"
        order = cfg.forceFirst + \
                    [item
                     for item in order
                     if ((item not in cfg.forceFirst) and
                         (item not in cfg.forceLast))] + \
                cfg.forceLast

    ## Double check all dependencies have been met
    for fp in order:
        if max([order.index(rfp) for rfp in files[fp].requires] +
               [order.index(fp)]) != order.index(fp):
            print "Inconsistent!"
            raise SystemExit


    ## Output the files in the determined order
    result = []

    for fp in order:
        f = files[fp]
        print "Exporting: ", f.filepath
        result.append(HEADER % f.filepath)
        source = f.source
        result.append(source)
        if not source.endswith("\n"):
            result.append("\n")

    print "\nTotal files merged: %d " % len(allFiles)

    print "\nGenerating: %s" % (outputFilename)

    open(outputFilename, "w").write("".join(result))
