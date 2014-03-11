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


sys.path.append("..")

from bs4 import BeautifulSoup
from LibraryEntity import *

class Page(object) :
    
    hds = { 'User-Agent' : 'Mozilla/5.0 (Windows NT 6.1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/28.0.1500.72 Safari/537.36' }  
    
    def __init__(self,opener):
        self.opener = opener
        self.url = 'http://210.41.233.144:8080/reader/redr_info.php'
        self.para = {}

    def getContent(self):
        req = urllib2.Request(url = self.url,data = urllib.urlencode( self.para) ,headers = self.__class__.hds) 
        response = self.opener.open(req)  
        page = response.read()
        page = page.decode('utf-8')
        self.page = page
        
class LoginPage(Page):

    def __init__(self,opener,para):
        super(LoginPage, self).__init__(opener)
        self.url = 'http://210.41.233.144:8080/reader/redr_verify.php'
        self.para = para
        self.user = None
        
    def getContent(self):
        super(LoginPage,self).getContent()
        htmlPage = BeautifulSoup(self.page)
        mylibInfoDiv = htmlPage.find('div',id='mylib_info')
        user = User()
        self.user = user
        if None == mylibInfoDiv:
            return
        user.name = [unicode(ele.next_sibling) for ele in mylibInfoDiv.find_all('span',text='姓名：')][0]
        user.certificateNumber = [unicode(ele.next_sibling) for ele in mylibInfoDiv.find_all('span',text='证件号： ')][0]
        user.barcode = [unicode(ele.next_sibling) for ele in mylibInfoDiv.find_all('span',text='条码号：')][0]
        user.expireDate = [unicode(ele.next_sibling) for ele in mylibInfoDiv.find_all('span',text='失效日期：')][0]
        user.registreDate = [unicode(ele.next_sibling) for ele in mylibInfoDiv.find_all('span',text='办证日期：')][0]
        user.effectDate = [unicode(ele.next_sibling) for ele in mylibInfoDiv.find_all('span',text='生效日期：')][0]
        user.readerType = [unicode(ele.next_sibling) for ele in mylibInfoDiv.find_all('span',text='读者类型：')][0]
        user.totalBooks =  [unicode(ele.next_sibling) for ele in mylibInfoDiv.find_all('span',text='累计借书：')][0]
        user.totalBooks = int(user.totalBooks.replace(u'册次',''))
        user.department =  [unicode(ele.next_sibling) for ele in mylibInfoDiv.find_all('span',text='系别：')][0]
        user.workUnit = [unicode(ele.next_sibling) for ele in mylibInfoDiv.find_all('span',text='工作单位：')][0]
        user.sex = [unicode(ele.next_sibling) for ele in mylibInfoDiv.find_all('span',text='性别：')][0]
        
class ReadInfo(Page):

    def __init__(self,opener):
        super(ReadInfo, self).__init__(opener)
        self.url = 'http://210.41.233.144:8080/reader/redr_info.php'
        
class BookLst(Page):

    def __init__(self,opener,user):
        super(BookLst, self).__init__(opener)
        self.url = 'http://210.41.233.144:8080/reader/book_lst.php'
        self.bookLst = []
        self.user = user

    def getContent(self):
        super(BookLst,self).getContent()
        htmlPage = BeautifulSoup(self.page)
        mylibInfoDiv = htmlPage.find('div',id='mylib_content').find('table',class_='table_line')
        #print mylibInfoDiv
        if not mylibInfoDiv is None:
            for tr in mylibInfoDiv.find_all('tr')[1:]:
                book = BorrowingBook()
                book.borrowerCode = self.user.barcode
                book.barcode = tr.find_all('td')[0].text
                book.marc_no = unicode(tr.find_all('td')[1].find('a')['href']\
                    .replace('../opac/item.php?marc_no=',''))
                book.name = unicode(tr.find_all('td')[1].find('a').string)
                book.writer = unicode(tr.find_all('td')[1].find('a').next_sibling)\
                    .replace(' / ','').replace(u'主编','')
                book.borrowDate = tr.find_all('td')[2].text.replace(' ','')
                book.dueDate = tr.find_all('td')[3].text.replace(' ','')
                book.address = tr.find_all('td')[5].text
                self.bookLst[1:1] = [book]
        
class BookHst(Page):

    def __init__(self,opener,user):
        super(BookHst, self).__init__(opener)
        self.url = 'http://210.41.233.144:8080/reader/book_hist.php?para_string=all'
        self.bookHst = []
        self.user = user

    def getContent(self):
        super(BookHst,self).getContent()
        htmlPage = BeautifulSoup(self.page)
        mylibInfoDiv = htmlPage.find('div',id='mylib_content').find('table',class_='table_line')
        #print mylibInfoDiv
        if not mylibInfoDiv is None:
            for tr in mylibInfoDiv.find_all('tr')[1:]:
                if 7 == len(tr.find_all('td')):
                    book = BorrowedBook()
                    book.borrowerCode = self.user.barcode
                    book.barcode = tr.find_all('td')[1].text
                    book.marc_no = tr.find_all('td')[2].find('a')['href'].replace('../opac/item.php?marc_no=','')
                    book.name = tr.find_all('td')[2].find('a').text
                    book.writer = tr.find_all('td')[3].text
                    book.borrowDate = tr.find_all('td')[4].text
                    book.returnDate = tr.find_all('td')[5].text
                    book.address = tr.find_all('td')[6].text
                    self.bookHst[1:1] = [book]

class BookDetailPage(Page):
    def __init__(self,marc_no):
        opener = urllib2.build_opener() #绑定handler，创建一个自定义的opener      
        super(BookDetailPage, self).__init__(opener)
        self.marc_no = marc_no
        self.url = 'http://210.41.233.144:8080/opac/item.php?marc_no='+marc_no
    
    def getContent(self):
        super(BookDetailPage,self).getContent()
        htmlPage = BeautifulSoup(self.page)
        detailDiv = htmlPage.find('div',id='item_detail')
        if None == detailDiv:
            return

        bookDetail = Book()
        if None == detailDiv.find('dt',text='题名/责任者:'):
            bookDetail.name = ""
            bookDetail.writer = ""
        else:
            bookDetail.name = unicode(detailDiv.find('dt',text='题名/责任者:').parent.find('dd').find('a').text)
            bookDetail.writer = unicode(detailDiv.find('dt',text='题名/责任者:').parent.find('dd').find('a').next_sibling)  
            bookDetail.writer = unicode(bookDetail.writer.replace(u'/',''))
        
        if None == detailDiv.find('dt',text='出版发行项:'):
            bookDetail.publisher = ""
        else:
            bookDetail.publisher = unicode(detailDiv.find('dt',text='出版发行项:').parent.find('dd').text)
        
        if None == detailDiv.find('dt',text='ISBN及定价:'):
            bookDetail.ISBN = ""
            bookDetail.marc_no = self.marc_no
            bookDetail.price = ""
        else: 
            reobj = re.compile('/|\s+')
            isbnAndPrice = unicode(detailDiv.find('dt',text='ISBN及定价:').parent.find('dd').text).strip()
            isbnAndPrice = reobj.split(isbnAndPrice)
            while len(isbnAndPrice) < 2:
                isbnAndPrice.append("")
            bookDetail.ISBN = unicode(isbnAndPrice[0])
            bookDetail.marc_no = unicode(self.marc_no)
            bookDetail.price = unicode(isbnAndPrice[1])
        
        if None == detailDiv.find('dt',text='载体形态项:'):
             bookDetail.physicalDescriptionArea = ""
        else:
            bookDetail.physicalDescriptionArea = unicode(detailDiv.find('dt',text='载体形态项:').parent.find('dd').text)

        if None == detailDiv.find('dt',text='学科主题:') :
            bookDetail.subject = unicode('')
        else:
            subject = detailDiv.find('dt',text='学科主题:').parent.find('dd')    
            bookDetail.subject = unicode(subject.find('a').string) + unicode(subject.find('a').next_sibling)
        if None == detailDiv.find('dt',text='中图法分类号:'):
            bookDetail.classNumber = ""
        else:
            bookDetail.classNumber = unicode(detailDiv.find('dt',text='中图法分类号:').parent.find('dd').find('a').text)
        return bookDetail

if __name__ == '__main__':
    bookDetailPage = BookDetailPage("0000620124")
    print vars(bookDetailPage.getContent())