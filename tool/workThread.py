# -*- coding: utf-8 -*-
import os
import sys 
import re
import uuid
import time
import urllib 
import urllib2
import urlparse
import cookielib
import threading
import logging
import traceback
import unittest

sys.path.append("..")

from bs4 import BeautifulSoup
from entity.libraryPage import * 
from ConfigParser import ConfigParser

logger = logging.getLogger("cuitlib")  

waitTimeInConnDb = 10
waitTimeGetNextUnitInGrapThread = 3
waitTimeGetNextUnitInWriteThread = 3

config = ConfigParser()
config.read( 'config')

class ThreadGetUserDetailThread(threading.Thread):
    def __init__(self, userDetailQueue, userInfoQueue, readedDeaprtment, readingDepartment):
        threading.Thread.__init__(self)
        self.userDetailQueue = userDetailQueue
        self.userInfoQueue = userInfoQueue
        self.readedDeaprtment = readedDeaprtment
        self.readingDepartment = readingDepartment
        self.logger = logging.getLogger("cuitlib.GetUserDetail") 
        self.logger.error("新建获取用户资料线程")

    def __del__(self):
        self.logger.error("获取用户资料线程死亡")

    def run(self): 
        while True:
            try:
                departmentKey = self.userDetailQueue.get(True, waitTimeGetNextUnitInGrapThread) 
            except Queue.Empty, e:
                self.logger.error("获取要读取的用户超时")
                break
            readedAllDepartment = True
            if  not self.readedDeaprtment.has_key(departmentKey):
                availStuNum = 0
                self.readingDepartment[departmentKey] = {}
                lowerNumber = int(config.get('department','lowerNumberPerDepartement'))
                uperNumber = int(config.get('department','uperNumberPerDepartement'))
                for stuNum in range(lowerNumber,uperNumber):
                    number = '%s%03d' % (departmentKey,stuNum)
                    self.readingDepartment[departmentKey]['%03d' % (stuNum)] = ""
                    try:
                        times = 0
                        while( times < 5):
                            try:
                                user = self.getuser(number,number)
                                if None != user:
                                    self.userInfoQueue.put(user)
                                    self.logger.debug('获取用户信息成功'+number)
                                else:
                                    self.logger.debug('用户名：%s登录失败 ' % ( number))
                                break
                            except (urllib2.URLError, IOError), e:
                                times = times + 1 ;
                                time.sleep(times*times)
                                self.logger.debug('第%d次获取用户%s的信息' %(times,number))
                            except Exception, e:
                                if hasattr(e, 'code') and e.code == 404 :
                                    times = times + 1 ;
                                    time.sleep(times*times)
                                    self.logger.debug('第%d次获取用户%s的信息' %(times,number))
                                else:
                                    raise
                                
                        if times == 5:
                            self.logger.error('网络错误：获取用户%s的信息失败:' %(number))
                            readedAllDepartment = False
                            break
                    except Exception,data:
                        traceback.print_exc()
                        self.logger.error( '获取用户信息异常：'+ number)
                        self.logger.error( str(Exception)+ ":" +str(data) )
                if True == readedAllDepartment:
                    del self.readingDepartment[departmentKey]
                    self.readedDeaprtment[departmentKey] = ''
            self.userDetailQueue.task_done()
        print "跳出获取用户信息的循环"

    def getuser(self,number,passwd):
        ###用cookielib模块创建一个对象，再用urlllib2模块创建一个cookie的handler
        cookie = cookielib.CookieJar()
        cookie_handler = urllib2.HTTPCookieProcessor(cookie)
        opener = urllib2.build_opener(cookie_handler) #绑定handler，创建一个自定义的opener      
            
        ###登录需要提交的表单
        pstdata = {'number':number, #填入网站的用户名
                'passwd':passwd, #填入网站密码
                'select':'cert_no', 
                'returnUrl':''
                }
        
        user = LoginPage(opener,pstdata)
        user.getContent()
        if '' == user.user.name:
            return
        
        bookLst = BookLst(opener,user.user)
        bookLst.getContent()
        user.bookLst = bookLst.bookLst
        
        bookHst = BookHst(opener,user.user)
        bookHst.getContent()
        user.bookHst = bookHst.bookHst
        return user

class WrittingUserDetailThread(threading.Thread):
    def __init__(self, dbConnQueue, userInfoQueue, bookIdQueue):
        threading.Thread.__init__(self)
        self.logger = logging.getLogger("cuitlib.WrittingUserDetail") 
        self.userInfoQueue = userInfoQueue
        self.allGrapThreadDied = False
        self.dbConnQueue = dbConnQueue
        self.bookIdQueue = bookIdQueue
        self.record = {"user":0,"readingBook":0,"readedBook":0}
        try:
            self.conn = dbConnQueue.get(True, waitTimeInConnDb)
        except Queue.Empty, e:
            self.logger.error("写入用户资料线程获取数据库失败") 
            raise
        self.logger.error("新建写入用户资料线程")

    def __del__(self):
        self.dbConnQueue.task_done()
        self.logger.info("本次新增%d个用户,%d条借阅中记录，%d条借阅历史记录" 
            % (self.record["user"],self.record["readingBook"],self.record["readedBook"]))
        self.logger.error("写入用户资料线程关毕")

    def getUnit(self):
        while True:
            try: 
                return self.userInfoQueue.get(True,waitTimeGetNextUnitInWriteThread) 
            except Queue.Empty, e:
                if True == self.allGrapThreadDied:
                    raise
                else:
                    self.logger.error("写入用户资料线程超时")

    def run(self):
        while True:
            try:
                try:
                    user = self.getUnit()
                except Queue.Empty, e:
                    self.logger.error("获取用户信息超时，跳出循环")
                    break 
                
                cursor = self.conn.cursor()
        
                insertUserQuery = '''INSERT INTO t_user(  username , certificatenumber , barcode ,
                expireDate , registreDate , effectDate , readerType ,
                totalBooks , department , workunit , sex )VALUES(
                %s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)'''
                userValue = [user.user.name, user.user.certificateNumber, user.user.barcode,\
                             user.user.expireDate, user.user.registreDate, user.user.effectDate,\
                             user.user.readerType,user.user.totalBooks, user.user.department,\
                             user.user.workUnit, user.user.sex]
                try:
                    cursor.execute( insertUserQuery, userValue )
                except MySQLdb.Error, e:
                    if 1062 == e.args[0]:
                        self.logger.info("该记录已存在,用户:"
                            +"certificateNumber:"+ str(user.user.certificateNumber) )
                    else:
                        self.logger.error("Mysql Error %d: %s" % (e.args[0], e.args[1]))
                else:
                    self.record["user"] = self.record["user"] + 1

                insertBorringBookQuery = '''INSERT INTO  t_borrowingbook (
                    borrowercode , barcode , marc_no , name , writer ,borrowDate , dueDate , address )
                    VALUES(%s,%s,%s,%s,%s,%s,%s,%s)'''
                for bookEntity in user.bookLst :
                    book = (bookEntity.borrowerCode, bookEntity.barcode,
                        bookEntity.marc_no, bookEntity.name, bookEntity.writer, bookEntity.borrowDate,
                        bookEntity.dueDate, bookEntity.address)
                    self.bookIdQueue.put(bookEntity.marc_no)
                    try:
                        cursor.execute( insertBorringBookQuery, book )
                    except MySQLdb.Error, e:
                        if 1062 == e.args[0]:
                            self.logger.info("该记录已存在,"
                                +"borrowerCode:"+ str(bookEntity.borrowerCode) + ","
                                +"marc_no:"+ str(bookEntity.marc_no ) + ","
                                +"borrowDate:"+ str(bookEntity.borrowDate) )
                        else:
                            self.logger.error("Mysql Error %d: %s" % (e.args[0], e.args[1]))
                    else:
                        self.record["readingBook"] = self.record["readingBook"] + 1

                insertBorredBookQuery = '''INSERT INTO  t_borrowedbook (
                    borrowerCode, barcode , marc_no , name , 
                writer , borrowDate , returnDate , address )VALUES(
                %s,%s,%s,%s,%s,%s,%s,%s)'''
                for bookEntity in user.bookHst :
                    book = (bookEntity.borrowerCode, bookEntity.barcode,
                        bookEntity.marc_no, bookEntity.name,
                        bookEntity.writer, bookEntity.borrowDate,
                        bookEntity.returnDate, bookEntity.address)
                    self.bookIdQueue.put(bookEntity.marc_no)
                    try:
                        cursor.execute( insertBorredBookQuery, book)
                    except MySQLdb.Error, e:
                        if 1062 == e.args[0]:
                            self.logger.info("该记录已存在,"
                                +"borrowerCode:"+ str(bookEntity.borrowerCode) + ","
                                +"marc_no:"+ bookEntity.marc_no + ","
                                +"borrowDate:"+ str(bookEntity.borrowDate) )
                        else:
                            self.logger.error("Mysql Error %d: %s" % (e.args[0], e.args[1]))
                    else:
                        self.record["readedBook"] = self.record["readedBook"] + 1
                self.conn.commit()
                cursor.close()
            except Exception,data:
                traceback.print_exc()
                self.logger.error( str(Exception)+ ":" +str(data) )
            self.userInfoQueue.task_done()
        self.logger.error('跳出保存用户线程')


class GetBookDetailThread(threading.Thread):
    def __init__(self, bookIdQueue,bookDetailQueue,readedBookId):
        threading.Thread.__init__(self)
        self.bookIdQueue = bookIdQueue
        self.bookDetailQueue = bookDetailQueue
        self.readedBookId = readedBookId
        self.logger = logging.getLogger("cuitlib.GetBookDetail") 

    def __del__(self):
        self.logger.error("获取书籍详细资料线程关毕")

    def run(self):
      while True:
            try:
                marc_no = self.bookIdQueue.get(True, waitTimeGetNextUnitInGrapThread)
            except Queue.Empty, e:
                break
            if( self.readedBookId.has_key(marc_no) ):
                continue
            try:
                times = 0
                while( times < 5):
                    try:
                        bookDetailPage = BookDetailPage(marc_no)
                        bookDetail = bookDetailPage.getContent()
                        self.bookDetailQueue.put(bookDetail)
                        break
                    except (urllib2.URLError, IOError), e:
                        times = times + 1 ;
                        time.sleep(times*times)
                        self.logger.debug('第%d次获取书籍%s的信息' %(times,marc_no.encode('utf8')))
                    except Exception, e:
                        if hasattr(e, 'code') and e.code == 404 :
                            times = times + 1 ;
                            time.sleep(times*times)
                            self.logger.debug('第%d次获取书籍%s的信息' %(times,marc_no.encode('utf8')))
                        else:
                            raise
                if times == 5:
                    self.logger.error('网络错误：获取书籍%s的信息失败:' %(marc_no.encode('utf8')))
                    break
                self.bookIdQueue.task_done()
                self.readedBookId[marc_no] = ""
            except Exception,data:
                traceback.print_exc()
                self.logger.error( '获取书籍信息失败：'+ str(marc_no) )
                self.logger.error( str(Exception)+ ":" +str(data) )

class WrittingBookDetailThread(threading.Thread):
    def __init__(self, dbConnQueue, bookDetailQueue):
        threading.Thread.__init__(self)
        self.logger = logging.getLogger("cuitlib.WrittingBookDetail") 
        self.logger.error("新建写入书籍详细资料线程")
        self.dbConnQueue = dbConnQueue
        self.bookDetailQueue = bookDetailQueue
        self.conn = dbConnQueue.get(True, waitTimeInConnDb)
        self.allGrapThreadDied = False
        self.record = {"bookNum":0}

    def __del__(self):
        self.logger.error("本次新增%d本书" % (self.record["bookNum"]))
        self.logger.error("写入书籍详细资料线程关毕")

    def getUnit(self):
        while True:
            try: 
                return self.bookDetailQueue.get(True,waitTimeGetNextUnitInWriteThread) 
            except Queue.Empty, e:
                if True == self.allGrapThreadDied:
                    raise
                else:
                    self.logger.error("写入书籍详细资料线程超时")

    def run(self):
      while True:
            try:
                try:
                    bookDetail = self.getUnit()
                except Queue.Empty, e:
                    self.logger.error("获取书籍超时，跳出循环")
                    break
                if None == bookDetail:
                    continue

                cursor = self.conn.cursor()
        
                insertBookDetailQuery = '''
                    INSERT INTO t_books(
                        name,writer,publisher,ISBN,price,
                        physicalDescriptionArea,subject,classNumber,marc_no
                    )VALUES(
                        %s,%s,%s,%s,%s,
                        %s,%s,%s,%s
                    )
                '''
                bookValue = [bookDetail.name,bookDetail.writer,bookDetail.publisher,bookDetail.ISBN,bookDetail.price,
                    bookDetail.physicalDescriptionArea,bookDetail.subject,bookDetail.classNumber,bookDetail.marc_no]
                try:
                    cursor.execute( insertBookDetailQuery, bookValue )
                except MySQLdb.Error, e:
                    if 1062 == e.args[0]:
                        self.logger.info("该记录已存在,书籍:"
                            +"marc_no:"+ str(bookDetail.marc_no ) )
                    else:
                        self.logger.error("Mysql Error %d: %s" % (e.args[0], e.args[1]))
                else:
                    self.record["bookNum"] = self.record["bookNum"] + 1
                
                self.conn.commit()
                self.bookDetailQueue.task_done()
            except Exception,data:
                traceback.print_exc()
                self.logger.error( bookDetail.marc_no + str(Exception)+ ":" +str(data) )
            