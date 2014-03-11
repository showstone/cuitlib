# -*- coding: utf-8 -*-
import MySQLdb
import Queue
import logging
import time
import datetime
import sys

from tool.workThread import * 

dbhost='localhost'
dbuser='cuitlib2'
dbpasswd='cuitlib2'
dbName='cuitlib3'
dbport=3306
dbcharset='utf8'

def initLogger(logFileName):
    # create logger with "spam_application"  
    logger = logging.getLogger("cuitlib")  
    logger.setLevel(logging.DEBUG)  
    # create file handler which logs even debug messages  
    fh = logging.FileHandler(logFileName+ datetime.datetime.now().strftime('%b-%d-%y_%H_%M_%S')+ ".log")  
    fh.setLevel(logging.DEBUG)  
    # create console handler with a higher log level  
    ch = logging.StreamHandler()  
    ch.setLevel(logging.ERROR)  
    # create formatter and add it to the handlers  
    formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")  
    fh.setFormatter(formatter)  
    ch.setFormatter(formatter)  
    # add the handlers to the logger  
    logger.addHandler(fh)  
    logger.addHandler(ch)
    return logger

def loadLastStatus(statusFile):
    try:
        fh = open(statusFile,"r+")
        dicStr = fh.read()
        dics = dicStr.split(";")
        readedDeaprtment = eval(dics[0])
        readingDepartment = eval(dics[1])
        fh.close()
    except:
        readedDeaprtment = {}
        readingDepartment = {}
    return (readedDeaprtment,readingDepartment)

def saveLastStatus(statusFile,readedDeaprtment,readingDepartment):
    fh = open(statusFile,"w+")
    fh.write( str(readedDeaprtment)+ ";"+ str(readingDepartment))
    fh.close()
    logger.debug("保存当前任务执行状态")

if __name__ == '__main__':
    logFileName = "cuitlib.log"
    logger = initLogger( logFileName)
    logger.debug("init cuitlib crawler,启动时间:"+ datetime.datetime.now().strftime('%b-%d-%y %H:%M:%S') )
    
    statusFile = os.getcwd()+ "\\"+ "status.cuitlib"
    lastStatus = loadLastStatus(statusFile)
    readDeaprtment = lastStatus[0]
    readingDepartment = lastStatus[1]
    threadCollect = []

    readDeaprtment = {}
    readingDepartment = {}
    
    bookIdQueue = Queue.Queue()
    readedBookId = {}
    bookDetailQueue = Queue.Queue()

    try:
        conn=MySQLdb.connect(host=dbhost, user=dbuser, passwd=dbpasswd, db=dbName, port=dbport,charset=dbcharset)
        cursor = conn.cursor()

        getAllMarcNoQueryStr = '''
            select distinct(marc_no) from(
                    select beb.marc_no from t_borrowedbook beb union all 
                    select bib.marc_no from t_borrowedbook bib
                ) marc_no
        '''
        cursor.execute( getAllMarcNoQueryStr )
        for marc_no in cursor.fetchall():
            bookIdQueue.put(marc_no[0])

        getReadedBookQueryStr = '''
            SELECT marc_no FROM t_books
        '''
        cursor.execute( getReadedBookQueryStr )
        for marc_no in cursor.fetchall():
            readedBookId[marc_no[0]] = ""

        cursor.close()
        conn.close()
    except MySQLdb.Error,e:
        print "Mysql Error %d: %s" % (e.args[0], e.args[1])

    dbConnQueue = Queue.Queue()
    
    try:
        for i in range(5):
            conn=MySQLdb.connect(host=dbhost, user=dbuser, passwd=dbpasswd, db=dbName, port=dbport,charset=dbcharset)
            dbConnQueue.put(conn)
        logger.debug("初始化数据库连接池成功")
    except MySQLdb.Error,e:
        logger.error("初始化数据库连接池失败,详细信息")
        logger.error("Mysql Error %d: %s" % (e.args[0], e.args[1]))
        logger.error("程序中止运行")
        sys.exit()

    departParaQueue = Queue.Queue()
    for yearPos in range(2010,2013):
            for departPos in range(1,2):
                departParaQueue.put((yearPos,'%03d'%(departPos)))

    userInfoQueue = Queue.Queue()

    for getUserDetailThreadNum in range(15):
        threadGetUserDetailThread = ThreadGetUserDetailThread(departParaQueue,userInfoQueue,readDeaprtment,readingDepartment)
        threadGetUserDetailThread.start()
        threadCollect.append( threadGetUserDetailThread)

    writtingUserDetailThread = WrittingUserDetailThread(dbConnQueue,userInfoQueue,bookIdQueue)
    writtingUserDetailThread.start()
    threadCollect.append( writtingUserDetailThread)

    for getBookDetailThreadNum in range(60):
        getBookDetailThread = GetBookDetailThread( bookIdQueue, bookDetailQueue,readedBookId)
        getBookDetailThread.start()
        threadCollect.append( getBookDetailThread)

    writtingBookDetailThread = WrittingBookDetailThread(dbConnQueue,bookDetailQueue)
    writtingBookDetailThread.start()
    threadCollect.append( writtingBookDetailThread)

    for t in threadCollect:
        t.join()

    logger.debug("等待所有执行线程")

    saveLastStatus(statusFile,readDeaprtment,readingDepartment)
    
    logger.debug("grap cuitlib finished,结束时间:"+ datetime.datetime.now().strftime('%b-%d-%y %H:%M:%S') )
