# -*- coding: utf-8 -*-
import os
import sys 
import urllib 
import urllib2
import cookielib
import urlparse
import re
import uuid
import MySQLdb
import Queue
import logging
import traceback
import unittest


sys.path.append("..")

from bs4 import BeautifulSoup
from ConfigParser import ConfigParser
from entity import LibraryEntity
from main import *

class mainTest(unittest.TestCase):

    def setUp(self):
        configFile = os.getcwd()+ "\\"+ "testSource"
        self.config = ConfigParser()
        self.config.read( configFile)

        self.statusFile = os.getcwd()+ "\\"+ "status.cuitlib.test"
        fh = open(self.statusFile,"w")
        fh.write("{};{}")
        fh.close

    def tearDown(self):
        pass
    
    def testLoadStatus(self):
        sourceStatus = self.config.get('status','saveStatus')
        fh = open(self.statusFile,"w")
        fh.write(sourceStatus)
        fh.close()

        status = loadLastStatus(self.statusFile)
        readedDeaprtment = status[0]
        readingDepartment = status[1]
        self.assertEqual(4,len(readedDeaprtment))

        readingDepartmentSize = 0
        for department in readingDepartment:
            readingDepartmentSize = readingDepartmentSize + len(readingDepartment[department])
        self.assertEqual(36,readingDepartmentSize)

    def testSaveStatus(self):
        readedDeaprtment = {}
        readingDepartment = {}

        for num in range(1,5):
            readedDeaprtment['2011%03d' % (num)] = ""

        for num in range(6,10):
            readingDepartment['2011%03d' % (num)] = {}
            for user in range(1,10):
                readingDepartment['2011%03d' % (num)]['2011%03d%03d' % (num,user)] = {}

        saveLastStatus(self.statusFile,readedDeaprtment,readingDepartment);

        fh = open(self.statusFile,"r")
        actualStr = fh.read()

        expectStr = self.config.get('status','saveStatus')
        self.assertEqual(expectStr,actualStr)

if __name__ == "__main__":
    unittest.main()


