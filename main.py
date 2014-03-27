# -*- coding: utf-8 -*-
import MySQLdb
import Queue
import logging
import time
import datetime
import sys
import traceback

from tool.workThread import * 
from ConfigParser import ConfigParser

config = ConfigParser()
config.read( 'config')
dbhost = config.get('database','dbhost')
dbuser = config.get('database','dbuser')
dbpasswd = config.get('database','dbpasswd')
dbName = config.get('database','dbName')
dbport = int( config.get( 'database', 'dbport'))
dbcharset = config.get('database','dbcharset')

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
        fh = open(statusFile,"r")
        dicStr = fh.read()
        dics = dicStr.split(";")
        readedDeaprtment = eval(dics[0])
        readingDepartment = eval(dics[1])
        fh.close()
    except:
        readedDeaprtment = {}
        readingDepartment = {}
        traceback.print_exc()
    return (readedDeaprtment,readingDepartment)

def saveLastStatus(statusFile,readedDeaprtment,readingDepartment):
    fh = open(statusFile,"w+")
    fh.write( str(readedDeaprtment)+ ";"+ str(readingDepartment))
    fh.close()

def getExistBookId(conn):
        existBookId = {}
        getExistBookIdQuery = '''
            SELECT marc_no FROM t_books
        '''
        try:
            cursor = conn.cursor()
            cursor.execute( getExistBookIdQuery )
            results = cursor.fetchall()   
            for row in results:   
                print row[0]
                existBookId[row[0]] = ""
            cursor.close()
        except MySQLdb.Error, e:
            if 1062 == e.args[0]:
                logger.info("该记录已存在,书籍:"
                    +"marc_no:"+ str(bookEntity.marc_no ) )
            else:
                logger.error("Mysql Error %d: %s" % (e.args[0], e.args[1]))
        return existBookId

if __name__ == '__main__':
    logFileName = "cuitlib.log"
    logger = initLogger( logFileName)
    logger.error("init cuitlib crawler,启动时间:"+ datetime.datetime.now().strftime('%b-%d-%y %H:%M:%S') )
    
    statusFile = os.getcwd()+ "\\"+ "status.cuitlib"
    logger.error("开始读取上次任务状态")
    lastStatus = loadLastStatus(statusFile)
    logger.error("读取上次任务状态完毕")
    readDeaprtment = lastStatus[0]
    readingDepartment = lastStatus[1]
    threadCollect = []
    writeThread = []

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
        logger.error("初始化数据库连接池成功")
    except MySQLdb.Error,e:
        logger.error("初始化数据库连接池失败,详细信息")
        logger.error("Mysql Error %d: %s" % (e.args[0], e.args[1]))
        logger.error("程序中止运行")
        sys.exit()

    departementLowerNumber = int(config.get('department','departementLowerNumber'))
    departementUperNumber = int(config.get('department','departementUperNumber'))
    departParaQueue = Queue.Queue()
    for yearPos in range(departementLowerNumber,departementUperNumber):
            for departPos in range(81,82):
                departParaQueue.put('%4d%03d'%( yearPos, departPos))
    logger.error("共写入%d个部门" %(departParaQueue.qsize()))

    userInfoQueue = Queue.Queue()

    getUserDetailThreadNums = int(config.get('thread','getUserDetailThreadNum'))
    for getUserDetailThreadNum in range(getUserDetailThreadNums):
        threadGetUserDetailThread = ThreadGetUserDetailThread(departParaQueue,userInfoQueue,readDeaprtment,readingDepartment)
        threadGetUserDetailThread.start()
        threadCollect.append( threadGetUserDetailThread)

    writtingUserDetailThread = WrittingUserDetailThread(dbConnQueue,userInfoQueue,bookIdQueue)
    writtingUserDetailThread.start()
    writeThread.append( writtingUserDetailThread)

    logger.error("数据库中已经有%d本书的信息" % (len(readedBookId)))
    getBookDetailThreadNums = int(config.get('thread','getBookDetailThreadNum'))
    for getBookDetailThreadNum in range(getBookDetailThreadNums):
        getBookDetailThread = GetBookDetailThread( bookIdQueue, bookDetailQueue,readedBookId)
        getBookDetailThread.start()
        threadCollect.append( getBookDetailThread)

    writtingBookDetailThread = WrittingBookDetailThread(dbConnQueue,bookDetailQueue)
    writtingBookDetailThread.start()
    writeThread.append( writtingBookDetailThread)

    logger.error("等待所有抓取线程运行...")
    for t in threadCollect:
        t.join()    

    while True:
        allGrapThreadDied = True
        for t in threadCollect:
            if True == t.isAlive():
                allGrapThreadDied = False
                time.sleep(5)
                continue
        if True == allGrapThreadDied:
            logger.error("所有爬虫线程都已死亡，等待写入线程死亡")
            for t in writeThread:
                t.allGrapThreadDied = True
                logger.error(str( t.allGrapThreadDied))
                logger.error("所有爬虫线程都已死亡，设置写入线程死亡参数")
            while True:
                allGrapThreadDied = True
                for t in writeThread:
                    if True == t.isAlive():
                        allGrapThreadDied = False
                        time.sleep(5)
                        continue
                if True == allGrapThreadDied:
                    logger.error("所有写入线程都已死亡")
                    break
        break

    logger.error("开始保存当前爬虫")
    logger.error("开始保存当前任务执行状态")
    saveLastStatus(statusFile,readDeaprtment,readingDepartment)
    logger.error("保存当前任务执行状态完毕")

    logger.error("grap cuitlib finished,结束时间:"+ datetime.datetime.now().strftime('%b-%d-%y %H:%M:%S') )
