#!/usr/bin/env python

# Author: Gerrit Addiks <gerrit@addiks.de>

import os
import sys
import gi
import csv
from os.path import expanduser
from tkinter import Tk     # from tkinter import Tk for Python 3.x
from tkinter.filedialog import askopenfilename


gi.require_version('Gtk', '3.0')
gi.require_version('AppIndicator3', '0.1')

from gi.repository import Gtk, Pango, GObject

class TraceEntry:
    __level = 0
    __number = 0
    __begin = 0.0
    __end = 0.0
    __duration = 0.0
    __memory = 0
    __function = "NONE"
    __file = "NONE"
    __arguments = ""
    __children = []
    __row_iter = None
    __row_path = None
    __tree_store = None
    __tree_view = None

    def __init__(
        self,
        level,
        number,
        begin,
        memory,
        function,
        fileName,
        arguments
    ):
        self.__level = level
        self.__number = number
        self.__begin = begin
        self.__memory = memory
        self.__function = function
        self.__file = fileName
        self.__arguments = arguments
        self.__children = []
        self.__visible = True

    def addChild(self, child):
        self.__children.append(child);

    def close(self, end):
        self.__end = end
        self.__duration = self.__end - self.__begin

    def asListStoreEntry(self):
        return [
            self.__level,
            self.__number,
            self.__begin,
            self.__end,
            self.__duration,
            self.__memory,
            self.__function,
            self.__file,
            self.__arguments,
            self.__visible
        ]

    def addRowToTreeStore(self, treeStore, treeView, treeStoreFilter, parentRowIter):
        rowIter = treeStore.append(parentRowIter, self.asListStoreEntry())
        self.__row_path = treeStore.get_path(rowIter)
        self.__tree_store = treeStore
        self.__tree_store_filter = treeStoreFilter
        self.__tree_view = treeView

    def addChildrenToTreeStore(self, treeStore, treeView, treeStoreFilter, parentRowIter):
        self.__tree_store = treeStore
        self.__tree_store_filter = treeStoreFilter
        self.__tree_view = treeView

        if len(self.__children) > 0:
            for child in self.__children:
                child.addRowToTreeStore(
                    self.__tree_store,
                    treeView,
                    self.__tree_store_filter,
                    self.__tree_store.get_iter(self.__row_path)
                )

            treeView.connect("row-expanded", self.onRowExpanded);

    def onRowExpanded(self, treeView, treeIter, treePath):

        treeIter = self.__tree_store_filter.convert_iter_to_child_iter(treeIter)

        rowPath = self.__tree_store.get_path(treeIter)

        if self.__row_path != rowPath:
            return

        for child in self.__children:
            child.addChildrenToTreeStore(
                self.__tree_store,
                self.__tree_view,
                self.__tree_store_filter,
                self.__tree_store.get_iter(rowPath)
            )

        print("*row expand*")

    def children(self):
        return self.__children

    def num(self):
        return self.__number

    def duration(self):
        return self.__duration

    def descr(self):
        return self.__file + ":" + self.__function

    def onFilterChanged(self, durationLimit):
        self.__visible = self.__duration > durationLimit

        if self.__tree_store != None:
            self.__tree_store.set_value(
                self.__tree_store.get_iter(self.__row_path),
                9,
                self.__visible
            )

        for child in self.__children:
            child.onFilterChanged(durationLimit)

class TraceFile:
    __entries = []
    __highest_duration = 0.0

    def __init__(self, file_handle):

        with file_handle as handle:
            print(handle.readline(), end="") # Version: 3.3.2
            print(handle.readline(), end="") # File format: 4

            if 'TRACE START' not in handle.readline():
                print('Invalid format for the trace. Did you forget to change the trace format to be machine readable?')
                print('Try adding: xdebug.trace_format=1 to the config')


            reader = csv.reader(handle, delimiter="\t")
            level = 0
            entryStack = []
            for row in reader:

                currentEntry = None

                if len(row) < 3:
                    continue

                if row[2] == '0': # Entry
                    # print('ENTRY')

                    # The format can be found here: https://xdebug.org/docs/trace#trace_format
                    [ level, function_number, zero, begin_time, memory, function_name, user_defined, included_file, filename, line_number, *args ] = row
                    if len(args) != 0:
                        arguments = "TODO"
                    else:
                        arguments = "Feature disabled. Set xdebug.collect_params=1"

                    newEntry = TraceEntry(
                        int(level), # Level
                        int(function_number), # Number
                        float(begin_time), # Begin
                        int(memory), # Memory
                        function_name, # Function
                        f"{filename}:{line_number}", # FileName
                        arguments
                    )

                    if len(entryStack) > 0:
                        parent = entryStack[-1]
                        parent.addChild(newEntry)

                    else:
                        self.__entries.append(newEntry)

                    entryStack.append(newEntry)

                if row[2] == '1': # Exit
                    currentEntry = entryStack.pop()
                    currentEntry.close(
                        float(row[3]) # End
                    )

                    duration = currentEntry.duration()

                    if duration > self.__highest_duration:
                        self.__highest_duration = duration

                if row[2] == 'R': # Return
                    print('RETURN')

    def attachToStore(self, treeStore, treeView, treeStoreFilter):
        for root in self.__entries:
            root.addRowToTreeStore(treeStore, treeView, treeStoreFilter, None)
            root.addChildrenToTreeStore(treeStore, treeView, treeStoreFilter, None)

    def highestDuration(self):
        return self.__highest_duration

    def onFilterChanged(self, durationLimit):
        for root in self.__entries:
            root.onFilterChanged(durationLimit)

class Handler:

    def __init__(self, traceFile):
        self.__traceFile = traceFile

    def onDeleteWindow(self, *args):
        Gtk.main_quit(*args)

    def onRowExpanded(self, treeView, treeIter, treePath):
        pass

    def onRowCollapsed(self, *args):
        pass

    def onFilterChanged(self, *args):
        filterEntry = builder.get_object("duration_filter_value")

        traceFile.onFilterChanged(filterEntry.get_value())

        treeStoreFilter = builder.get_object("traces_filtered")
        treeStoreFilter.refilter()

basedir = os.path.dirname(os.path.abspath(__file__))

Tk().withdraw() # we don't want a full GUI, so keep the root window from appearing

if len(sys.argv) == 2 and os.path.exists(sys.argv[1]):
    filename = sys.argv[1]
else:
    filename = askopenfilename() # show an "Open" dialog box and return the path to the selected file

if filename.endswith('.gz'):
    import gzip, io
    file_handle = io.TextIOWrapper(gzip.open(filename, 'rb'))
else:
    file_handle = open(filename)

traceFile = TraceFile(file_handle)

handler = Handler(traceFile)

builder = Gtk.Builder()
handler.builder = builder
builder.add_from_file(basedir + "/ui.glade")
builder.connect_signals(handler)

treeStoreFilter = builder.get_object("traces_filtered")
treeStoreFilter.set_visible_column(9)

traceDataStore = builder.get_object("traces") # GtkTreeStore

print(traceDataStore)
traceFile.attachToStore(
    traceDataStore,
    builder.get_object("traces_view"),
    treeStoreFilter
)

filterScale = builder.get_object("duration_filter_value")
filterScale.set_upper(traceFile.highestDuration())
filterScale.set_step_increment(0.0001)

window = builder.get_object("windowMain")
window.show_all()

Gtk.main()
