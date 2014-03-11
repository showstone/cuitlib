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

sys.path.append("..")

from bs4 import BeautifulSoup
from entity.libraryPage import * 

logger = logging.getLogger("cuitlib")  

class ThreadGetUserDetailThread(threading.Thread):
    def __init__(self, userDetailQueue, userInfoQueue, readedDeaprtment, readingDepartment):
        threading.Thread.__init__(self)
        self.userDetailQueue = userDetailQueue
        self.userInfoQueue = userInfoQueue
        self.readedDeaprtment = readedDeaprtment
        self.readingDepartment = readingDepartment
        self.logger = logging.getLogger("cuitlib.GetUserDetail")  

    def __del__(self):
        self.logger.debug("获取用户资料线程关毕")

    def run(self): 
        while True:
            #userPara = None
            try:
                #global userPara
                userPara = self.userDetailQueue.get(True, 60) 
            except Queue.Empty, e:
                break
            departmentKey = '%s%s' % (userPara[0],userPara[1]) 
            readedAllDepartment = True
            if  not self.readedDeaprtment.has_key(departmentKey):
                availStuNum = 0
                self.readingDepartment['%s%s' % (userPara[0],userPara[1])] = {}
                for stuNum in range(1,200):
                    number = '%s%s%03d' % (userPara[0],userPara[1],stuNum)
                    self.readingDepartment['%s%s' % (userPara[0],userPara[1])]['%03d' % (stuNum)] = ""
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
                    del self.readingDepartment['%s%s' % (userPara[0],userPara[1])]
                    self.readedDeaprtment[departmentKey] = ''
            self.userDetailQueue.task_done()

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
    def __init__(self, dbConnQueue, userInfoQueue ,bookIdQueue):
        threading.Thread.__init__(self)
        self.userInfoQueue = userInfoQueue
        self.dbConnQueue = dbConnQueue
        self.bookIdQueue = bookIdQueue
        self.conn = dbConnQueue.get(True, 60*3)
        self.logger = logging.getLogger("cuitlib.WrittingUserDetail") 

    def __del__(self):
        self.dbConnQueue.task_done()
        self.logger.debug("写入用户资料线程关毕")

    def run(self):
      while True:
            try:
                #user = None
                try:
                    #global user
                    user = self.userInfoQueue.get(True, 60) 
                except Queue.Empty, e:
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
                cursor.execute( insertUserQuery, userValue )

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
                    except :
                        print book

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
                    except :
                        print book
                self.conn.commit()
                cursor.close()
            except Exception,data:
                self.logger.error( '保存用户信息失败：'+ user.user.name)
                self.logger.error( str(Exception)+ ":" +str(data) )
            self.userInfoQueue.task_done()


class GetBookDetailThread(threading.Thread):
    def __init__(self, bookIdQueue,bookDetailQueue,readedBookId):
        threading.Thread.__init__(self)
        self.bookIdQueue = bookIdQueue
        self.bookDetailQueue = bookDetailQueue
        self.readedBookId = readedBookId
        self.logger = logging.getLogger("cuitlib.GetBookDetail") 

    def __del__(self):
        self.logger.debug("获取书籍详细资料线程关毕")

    def run(self):
      while True:
            #marc_no = None
            try:
                #global marc_no
                marc_no = self.bookIdQueue.get(True, 60)
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
        self.dbConnQueue = dbConnQueue
        self.bookDetailQueue = bookDetailQueue
        self.conn = dbConnQueue.get(True, 60*3)
        self.logger = logging.getLogger("cuitlib.WrittingBookDetail") 

    def __del__(self):
        self.logger.debug("写入书籍详细资料线程关毕")

    def run(self):
      while True:
            try:
                #bookDetail = None
                try:
                    #global bookDetail
                    bookDetail = self.bookDetailQueue.get(True, 60)
                except Queue.Empty, e:
                    self.logger.debug("获取书籍超时，跳出循环")
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
                cursor.execute( insertBookDetailQuery, bookValue )
                
                self.conn.commit()
                self.bookDetailQueue.task_done()
            except Exception,data:
                self.logger.error( str(Exception)+ ":" +str(data) )