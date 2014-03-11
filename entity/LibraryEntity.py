# -*- coding: cp936 -*-
class User(object):

    def __init__(self):
        self.name = ''
        self.certificateNumber = ''
        self.barcode = ''
        self.expireDate = ''
        self.registreDate = ''
        self.effectDate = ''
        self.readerType = ''
        self.totalBooks = 0
        self.department = ''
        self.workUnit = ''
        self.sex = ''

class BorrowingBook(object):

    def __init__(self):
        self.borrowerCode = None
        self.barcode = ''
        self.marc_no = ''
        self.name = ''
        self.writer = ''
        self.borrowDate = ''
        self.dueDate = ''
        self.address = ''

        
class BorrowedBook(object):

    def __init__(self):
        self.borrowerCode = None
        self.barcode = ''
        self.marc_no = ''
        self.name = ''
        self.writer = ''
        self.borrowDate = ''
        self.returnDate = ''
        self.address = ''

        
class Book(object):

    def __init__(self):
        self.name = ''
        self.writer = ''
        self.publisher = ''
        self.ISBN = ''
        self.marc_no = ''
        self.price = 0
        self.physicalDescriptionArea = ''
        self.subject = ''
        self.classNumber = ''   
