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
    
    def __init__(self, filePath):
        
        with open(filePath) as handle:
            
            handle.readline() # Version: 3.3.2
            handle.readline() # File format: 4
            handle.readline() # TRACE START ...
            
            reader = csv.reader(handle, delimiter="\t")
            level = 0
            entryStack = []
            for row in reader:
                
                currentEntry = None
                
                if len(row) < 3:
                    continue
                
                if row[2] == '0': # Entry
                    # print('ENTRY')
                    
                    newEntry = TraceEntry(
                        int(row[0]), # Level
                        int(row[1]), # Number
                        float(row[3]), # Begin
                        int(row[4]), # Memory
                        row[5], # Function
                        row[7], # FileName
                        "TODO"            
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
filename = askopenfilename() # show an "Open" dialog box and return the path to the selected file

traceFile = TraceFile(filename)

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
