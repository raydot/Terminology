# -*- coding: utf-8 -*-
#####################
#
# © 2013–2014 Autodesk Development Sàrl
#
# Created in 2013 by Alok Goyal
#
# Changelog
# v3.1.5	Modified on 12 Aug 2014 by Ventsislav Zhechev
# Modified to use aliases for staging and production MySQL servers.
#
# v3.1.4	Modified on 27 May 2014 by Ventsislav Zhechev
# Fixed a bug where user names weren’t SQL-escaped, causing crashes.
#
# v3.1.3	Modified on 21 May 2014 by Ventsislav Zhechev
# Updated to connect to new MySQL setup.
#
# v3.1.2	Modified on 24 Mar 2014 by Ventsislav Zhechev
# Fixed a bug where login would fail for users with non-ascii characters in their username.
#
# v3.1.1	Modified on 17 Jan 2014 by Ventsislav Zhechev
# Fixed a bug where the error stream redirection was using the wrong App name in production.
#
# v3.1		Modified on 25 Nov 2013 by Ventsislav Zhechev
# Made it simpler to deploy from staging to production.
# Added a method that allows AJAX calls to check if a user is still authenticated in the system.
#
# v3.0		Modified on 18 Nov 2013 by Ventsislav Zhechev
# First production-ready version
#
# v2.5		Modified on 01 Nov 2013 by Ventsislav Zhechev
# Updated to fit the final database structure.
# Introduced handling of user logins.
# Database data can be viewed on linked pages.
#
# v2.1		Modified on 22 Oct 2013 by Ventsislav Zhechev
# The results of the term extrction process are now written to a MySQL database.
# The availability of the requested Content Type, Product Code and Language are checked against the data in a MySQL database.
#
# v2			Modified on 15 Oct 2013 by Ventsislav Zhechev
# Converted to queue-based processing of incomming requests with a single thread dedicated to term extraction and database interaction.
#
# v1			Modified by Alok Goyal, Mirko Plitt
# Original version.
#
#####################

isStaging = True

dbName = "Terminology"
if (isStaging):
	dbName +="_staging"
	from Terminology_staging import Terminology_staging as app, Extractor
	app.config['STAGING'] = True
else:
	from Terminology import Terminology as app, Extractor
	app.config['STAGING'] = False


class RedirectStderr:
	def write(self, string):
		app.logger.ERROR(string)

class RedirectStdout:
	def write(self, string):
		app.logger.ERROR(string)

import sys
sys.stderr = RedirectStderr()
sys.stdout = RedirectStdout()

from flask import request, session, render_template, redirect, make_response
from forms import LoginForm
import json
import os, re
from xml.sax.saxutils import escape
import pymysql
import urllib2, pyDes
from pyDes import triple_des
from datetime import timedelta
import traceback


import threading
import Queue

mainKey = "\xE7\xE4\x81\x29\xA1\xE3\x45\x38\xF8\x3A\xDE\x13\x15\xEB\x70\xCE\x5A\x1F\xE3\x31\x00\x00\x00\x00"
mainIV = "\xDA\x39\xA3\xEE\x5E\x6B\x4B\x0D"

exitFlag = False

logger = app.logger

def connectToDB():
	if isStaging:
		return pymysql.connect(host="aws.stg.mysql", port=3306, user="root", passwd="Demeter7", db=dbName, charset="utf8")
	else:
		return pymysql.connect(host="aws.prd.mysql", port=3306, user="root", passwd="Demeter7", db=dbName, charset="utf8")
	
class termHarvestThread (threading.Thread):
	def __init__(self, threadID):
		threading.Thread.__init__(self)
		self.threadID = threadID
		logger.debug(u"Initialising term extraction facilities…".encode('utf-8'))
		Extractor.__debug_on__ = True
		pathname = os.path.dirname(sys.argv[0])
		if not pathname:
			pathname = "."
		if not os.path.exists(pathname + "/" + dbName + "/auxiliaryData/unwords"):
			pathname = "/usr/lib/cgi-bin"
		Extractor.init(dict(
			adskCorpusRoot = pathname + "/" + dbName + "/auxiliaryData/taggerCorpus",
			adskUnwordsRoot = pathname + "/" + dbName + "/auxiliaryData/unwords",
			ngramFilePath = pathname + "/" + dbName + "/auxiliaryData/ngrams",
			))
		Extractor.loadAuxiliaryData()
		logger.debug(u"Training POS tagger…".encode('utf-8'))
		if isStaging:
			Extractor.trainPOSTagger(1)
		else:
			Extractor.trainPOSTagger(0)
		logger.debug("Initialised!".encode('utf-8'))
	def run(self):
		global exitFlag
		logger.debug("Starting thread " + str(self.threadID))
		while not exitFlag:
			try:
				jobID, contentID, products, language, data = jobQueue.get(True, 60)
				logger.debug((u"Processing a job…\nContentID: " + str(contentID) + "; ProductID: " + str(products[0]) + "; LanguageID: " + str(language[0])).encode('utf-8'))
				#process job
				terms = Extractor.Getterms(data, language[1], products[1], 0)
				conn = connectToDB()
				cursor = conn.cursor()
				for term in terms:
					sql = "insert into SourceTerms(Term) values ('%s') on duplicate key update ID=last_insert_id(ID)" % conn.escape_string(term[0])
# 					logger.debug("SQL: %s\n" % sql)
					cursor.execute(sql)
					cursor.execute("select last_insert_id()")
					sourceTermID, = cursor.fetchone()
					sql = "insert into TermTranslations(JobID, SourceTermID, LanguageID, ProductID, GlossID, ContentTypeID, NewTo, DateRequested) values (%s, %s, %s, %s, %s, %s, '%s', NULL) on duplicate key update ID=last_insert_id(ID), DateUpdated=CURRENT_TIMESTAMP, ContentTypeID=selectContentTypeID(ContentTypeID, %s)" % (jobID, sourceTermID, language[0], products[0][0], products[0][1], contentID, term[1], contentID)
#					logger.debug("SQL: %s\n" % sql)
					cursor.execute(sql)
					cursor.execute("select last_insert_id()")
					termTranslationID, = cursor.fetchone()
					sql = "insert into TermContexts(TermTranslationID, ContentTypeID, SourceContext) values "
					for context in term[2]:
						sql += "(%s, %s, '%s'), " % (termTranslationID, contentID, conn.escape_string(context))
					sql = sql[:-2] + " on duplicate key update LastUpdate=NULL, ContentTypeID=selectContentTypeID(ContentTypeID, %s)" % (contentID)
#					logger.debug("SQL: %s\n" % sql)
					cursor.execute(sql)
					
				#finished processing job
				cursor.execute("update PendingJobs set Pending=0, DateProcessed=CURRENT_TIMESTAMP where ID=%s limit 1", jobID)
				conn.commit()
				conn.close()
				jobQueue.task_done()
			except Queue.Empty:
				pass
		logger.debug("Exiting thread " + str(self.threadID))
				
def isSupportedContent(content, conn):
	if content == "Both":
		return None
	cursor = conn.cursor()
	cursor.execute("select ID from ContentTypes where ContentType='%s' limit 1" % content)
	result = cursor.fetchone()
	if not result:
		return None
	return result[0]

def isSupportedProduct(prod, conn):
	cursor = conn.cursor()
	cursor.execute("select ProductCode from Products where GlossID = (select GlossID from Products where ProductCode = '" + prod + "')")
	result = cursor.fetchall()
	if not result:
		return None
	cursor.execute("select ID, GlossID from Products where ProductCode = '" + prod + "' limit 1")
	return (cursor.fetchone(), [p[0] for p in result])

def isSupportedLanguage(lang, conn):
	cursor = conn.cursor()
	cursor.execute("select ID, LangCode3Ltr from TargetLanguages where LangCode2Ltr = '" + lang + "' limit 1")
	result = cursor.fetchone()
	if not result:
		cursor.execute("select ID, LangCode3Ltr from TargetLanguages where LangCode3Ltr = '" + lang + "' limit 1")
		result = cursor.fetchone()
		if not result:
			return None
	return result
	
def recentLanguages(cursor):
	cursor.execute("select ID, LangName from TargetLanguages where LastUsed is not null order by LastUsed desc limit 5")
	return cursor.fetchall()

def recentProducts(cursor):
	cursor.execute("select ID, ProductCode from Products where LastUsed is not null order by LastUsed desc limit 15")
	return cursor.fetchall()

def latestJobs(cursor):
	cursor.execute("select JobID, concat_ws(', ', ProductCode, LangCode3Ltr, ContentType) as JobString from JobList order by DateProcessed desc limit 20")
	return cursor.fetchall()


@app.route('/termharvest/', methods=['POST'])
def termharvest():
	global threads
	#set default code 204 which will be returned in case every thing went fine
	respCode = 204
	#set message as success which will be returned until overridden
	respStr = "Started task in background"
	
	requestContent = None
	try:
		requestContent = request.get_json(cache=True)
	except:
		logger.error("Could not handle JSON data!")
		return ("Could not parse JSON data", 400)
	contentType = requestContent['contentType']
	productCode = requestContent['productCode']
	lang = requestContent['language']
	
	conn = connectToDB()
	cursor = conn.cursor()
	
	logger.debug((u"Checking if the requested content type is supported… (" + contentType + ")").encode('utf-8'))
	contentID = isSupportedContent(contentType, conn)
	if not contentID:
		respCode = 400
		respStr = "Unsupported content type: " + contentType + ". Choose one of these:"
		cursor.execute("select ContentType from ContentTypes where ContentType != 'Both'")
		for contentType in cursor:
			respStr = respStr + " " + contentType[0]
		return (respStr, respCode)
	else:
		logger.debug("Will use the following content ID: " + str(contentID) + "")

	logger.debug((u"Checking if the requested product is supported… (" + productCode + ")").encode('utf-8'))
	prods = isSupportedProduct(productCode, conn)
	if not prods:
		respCode = 400
		respStr = "Unsupported product code: " + productCode + ". Choose one of these:"
		cursor.execute("select ProductCode from Products")
		for product in cursor:
			respStr = respStr + " " + product[0]
		return (respStr,respCode)
	else:
		logger.debug("Will check against following product codes:")
		for p in prods[1]:
			logger.debug(p + " ")
		logger.debug("\n")
			
	logger.debug((u"Checking if the requested language is supported… (" + lang + ")").encode('utf-8'))
	language = isSupportedLanguage(lang, conn)
	if not language:
		respCode = 400
		respStr = "Unsupported language code: " + lang + ". Choose one of these:"
		cursor.execute("select LangCode2Ltr from TargetLanguages")
		for language in cursor:
			respStr = respStr + " " + language[0]
		return (respStr, respCode)
	else:
		logger.debug("Will use the following language ID: " + str(language[0]) + " " + language[1])
	
	try:
		if len(threads) > 0:
			sql = "insert into PendingJobs(ContentTypeID, ProductID, LanguageID) values (%s, %s, %s)" % (contentID, prods[0][0], language[0])
#			logger.debug("SQL: %s\n" % sql)
			cursor.execute(sql)
			jobID = conn.insert_id()
			conn.commit()
			jobQueue.put((jobID, contentID, prods, language, requestContent['data']))
		else:
			respCode = 503
			respStr = "Server unavailable"  
	except:
		logger.debug(traceback.format_exc())
		respCode = 500
		respStr = "Unable to start thread, try after some time"

	conn.close()

	return (respStr, respCode)

def buildQuickAccess(cursor):
	quickAccess = dict()
	cursor.execute("select ID, LangName from TargetLanguages order by LangCode2Ltr asc")
	quickAccess['language'] = cursor.fetchall()
	cursor.execute("select ID, ProductName from Products order by ProductName asc")
	quickAccess['product'] = cursor.fetchall()
	return quickAccess

@app.route('/', methods=['GET'])
@app.route('/index.html', methods=['GET', 'POST'])
def index():
	global mainKey
	form = LoginForm()
	loginOK = None
	userID = 0
	userFirstName = ""
	userLastName = ""
	
	if form.validate_on_submit():
		logger.debug("Login attempted when loading index!")
		key = triple_des(mainKey, pyDes.CBC, mainIV)
		password = form.password.data.encode("utf-8")
		cryptoPass = key.encrypt(password.encode('utf-16le'), padmode=pyDes.PAD_PKCS5).encode('base64').rstrip()
		username = escape(form.username.data.lower()).encode('ascii', 'xmlcharrefreplace')
		logger.debug("Username:" + username)
#		logger.debug(render_template('authentication.xml', username=username, password=cryptoPass.encode('base64').rstrip()))
		xmlResult = urllib2.urlopen(urllib2.Request(url="https://lsweb.autodesk.com/WWLAdminDS/WWLAdminDS.asmx", data=render_template('authentication.xml', username=username, password=cryptoPass), headers={"SOAPAction": "http://tempuri.org/GetUserAuth", "Content-Type": "text/xml; charset=utf-8"})).read()
		logger.debug(xmlResult.decode("utf-8"))
		result = re.search('<GetUserAuthResult>.*<ID_USER>(\d+)</ID_USER>.*<FIRSTNAME>([\w \'-]+)</FIRSTNAME>.*<LASTNAME>([\w \'-]+)</LASTNAME>.*</GetUserAuthResult>', xmlResult.decode("utf-8"), re.U)
		if result:
			userID = int(result.group(1))
			userFirstName = result.group(2)
			userLastName = result.group(3)
			conn = connectToDB()
			cursor = conn.cursor()
			cursor.execute("insert into Users(ID, FirstName, LastName) values(%s, '%s', '%s') on duplicate key update FirstName='%s', LastName='%s'" % (userID, conn.escape_string(userFirstName), conn.escape_string(userLastName), conn.escape_string(userFirstName), conn.escape_string(userLastName)))
			conn.commit()
			conn.close()
			session['UserID'] = userID
			session['UserFirstName'] = userFirstName
			session['UserLastName'] = userLastName
			loginOK = True
			if form.remember_me.data:
				session['RememberMe'] = form.remember_me.data
				session['UserLogin'] = username
				session['UserPassword'] = cryptoPass
				session.permanent = True
				app.permanent_session_lifetime = timedelta(days=365)
			else:
				session.pop('RememberMe', None)
				session.pop('UserLogin', None)
				session.pop('UserPassword', None)
				session.permanent = False
		else:
			loginOK = False
		
	elif 'UserID' in session:
		logger.debug("UserID encountered when loading index!")
		loginOK = True
		userID = session['UserID']
		userFirstName = session['UserFirstName']
		userLastName = session['UserLastName']
		
	elif 'RememberMe' in session:
		logger.debug("RememberMe encountered when loading index!")
		result = None
		if 'UserLogin' in session:
			key = triple_des(mainKey, pyDes.CBC, mainIV)
			xmlResult = urllib2.urlopen(urllib2.Request(url="https://lsweb.autodesk.com/WWLAdminDS/WWLAdminDS.asmx", data=render_template('authentication.xml', username=session['UserLogin'], password=session['UserPassword']), headers={"SOAPAction": "http://tempuri.org/GetUserAuth", "Content-Type": "text/xml; charset=utf-8"})).read()
#			logger.debug(xmlResult)
			result = re.search('<GetUserAuthResult>.*<ID_USER>(\d+)</ID_USER>.*<FIRSTNAME>([\w \'-]+)</FIRSTNAME>.*<LASTNAME>([\w \'-]+)</LASTNAME>.*</GetUserAuthResult>', xmlResult.decode("utf-8"), re.U)
		else:
			logger.debug(u"…but UserLogin not found when loading index!".encode("utf-8"))
			session.pop('UserLogin', None)
		if result:
			userID = int(result.group(1))
			userFirstName = result.group(2)
			userLastName = result.group(3)
			conn = connectToDB()
			cursor = conn.cursor()
			cursor.execute("insert into Users(ID, FirstName, LastName) values(%s, '%s', '%s') on duplicate key update FirstName='%s', LastName='%s'" % (userID, conn.escape_string(userFirstName), conn.escape_string(userLastName), conn.escape_string(userFirstName), conn.escape_string(userLastName)))
			conn.commit()
			conn.close()
			session['UserID'] = userID
			session['UserFirstName'] = userFirstName
			session['UserLastName'] = userLastName
			loginOK = True
		else:
			if 'UserLogin' in session:
				form = LoginForm(username = session['UserLogin'], remember_me = True)
				if session['UserPassword'] == "":
					loginOK = None
				else:
					loginOK = False
	
	conn = connectToDB()
	cursor = conn.cursor(pymysql.cursors.DictCursor)
	recentLangs = recentLanguages(cursor)
	recentProds = recentProducts(cursor)
	lateJobs = latestJobs(cursor)
	quickAccess = buildQuickAccess(cursor)
	conn.close()
	return render_template('index.html',
			recentLanguages = recentLangs,
			recentProducts = recentProds,
			latestJobs = lateJobs,
			quickAccess = quickAccess,
			form = form,
			loginOK = loginOK,
			userID = userID,
			userName = userFirstName + " " + userLastName,
			STAGING = isStaging)

@app.route('/logout', methods=['GET'])
def logout():
	if 'UserID' in session:
		session.pop('UserID', None)
		session.pop('UserFirstName', None)
		session.pop('UserLastName', None)
	if 'RememberMe' in session:
		session['UserPassword'] = ""
	return ('', 204)

@app.route('/isAuthorised', methods=['GET'])
def isAuthorised():
	if 'UserID' in session:
		return ('YES', 200)
	else:
		return ('NO', 401)


@app.route('/TermList.perl', methods=['GET'])
def TermListPerl():
	language = request.args.get('language', '')
	glossary = request.args.get('glossary', '')
	if not language or not glossary or language == '0' or glossary == '0':
		return ('You have to specify both a language and a glossary!', 400)
	language = re.sub("_", "-", language)
	
	conn = connectToDB()
	cursor = conn.cursor(pymysql.cursors.DictCursor)
	cursor.execute("select Term, TermTranslation from TermList where LangCode2Ltr = '%s' and ProductCode in (select ProductCode from ProductGlossaries where GlossaryName = '%s') and Approved = b'1' and IgnoreTerm = b'0'" % (language, glossary))
	terms = cursor.fetchall()
	conn.close()
	if not terms:
		return ('{}', 200)
	perlHash = '{'
	for term in terms:
		perlHash += '"'+re.sub(r'(["\\])', r'\\\1', term['Term'])+'" => "'+re.sub(r'(["\\])', r'\\\1', term['TermTranslation'])+'",'
	perlHash += '}'
	return (perlHash, 200)

@app.route('/TermList.html', methods=['GET'])
def TermList():
	jobID = 0
	langID = 0
	prodID = 0
	jobID = request.args.get('jobID', '')
	if not jobID:
		langID = request.args.get('langID', '')
		prodID = request.args.get('prodID', '')
		if not langID or langID == '0':
			if not prodID or prodID == '0':
				return redirect('/JobList.html')
			else:
				return redirect('/TermListProduct.html?productID=%s' % prodID)
		elif not prodID or prodID == '0':
			return redirect('/TermListLanguage.html?languageID=%s' % langID)
	
	userID = 0
	userFirstName = ""
	userLastName = ""
	
	if 'UserID' in session:
		userID = session['UserID']
		userFirstName = session['UserFirstName']
		userLastName = session['UserLastName']
	
	conn = connectToDB()
	cursor = conn.cursor(pymysql.cursors.DictCursor)
	if jobID:
		cursor.execute("select * from TermList where JobID = %s order by Term asc" % jobID)
	else:
		cursor.execute("select * from TermList where LangCode3Ltr = (select LangCode3Ltr from TargetLanguages where ID = %s) and ProductCode = (select ProductCode from Products where ID = %s) order by DateRequested desc, Term asc" % (langID, prodID))
	terms = cursor.fetchall()
	recentLangs = recentLanguages(cursor)
	recentProds = recentProducts(cursor)
	lateJobs = latestJobs(cursor)
	quickAccess = buildQuickAccess(cursor)
	if terms:
		cursor.execute("update TargetLanguages set LastUsed=CURRENT_TIMESTAMP where LangCode3Ltr='%s' limit 1" % terms[0]['LangCode3Ltr'])
		cursor.execute("update Products set LastUsed=CURRENT_TIMESTAMP where ProductCode='%s' limit 1" % terms[0]['ProductCode'])
		conn.commit()
		conn.close()
		return render_template('TermList.html',
			jobID = jobID,
			langID = langID,
			prodID = prodID,
			language = terms[0]['LangName'],
			productCode = terms[0]['ProductCode'],
			productName = terms[0]['ProductName'],
			contentType = terms[0]['ContentType'],
			recentLanguages = recentLangs,
			recentProducts = recentProds,
			latestJobs = lateJobs,
			quickAccess = quickAccess,
			terms = terms,
			userID = userID,
			userName = userFirstName + " " + userLastName,
			STAGING = isStaging)
	elif jobID:
		cursor.execute("select concat('job ', concat_ws(', ', ProductCode, LangCode3Ltr, ContentType)) as JobString from JobList where JobID = %s limit 1" % jobID)
		jobString = cursor.fetchone()
		conn.close()
		return render_template('TermList.html',
			jobString = jobString['JobString'],
			recentLanguages = recentLangs,
			recentProducts = recentProds,
			latestJobs = lateJobs,
			quickAccess = quickAccess,
			userID = userID,
			userName = userFirstName + " " + userLastName,
			STAGING = isStaging)
	else:
		cursor.execute("select concat_ws(', ', ProductName, LangName) as JobString from Products, TargetLanguages where Products.ID = %s and TargetLanguages.ID = %s limit 1" % (prodID, langID))
		jobString = cursor.fetchone()
		conn.close()
		return render_template('TermList.html',
			jobString = jobString['JobString'],
			recentLanguages = recentLangs,
			recentProducts = recentProds,
			latestJobs = lateJobs,
			quickAccess = quickAccess,
			userID = userID,
			userName = userFirstName + " " + userLastName,
			STAGING = isStaging)
		
@app.route('/TermListLanguage.html', methods=['GET'])
def TermListLanguage():
	languageID = request.args.get('languageID', '')
	userID = 0
	userFirstName = ""
	userLastName = ""
	
	if 'UserID' in session:
		userID = session['UserID']
		userFirstName = session['UserFirstName']
		userLastName = session['UserLastName']
	
	conn = connectToDB()
	cursor = conn.cursor(pymysql.cursors.DictCursor)
	if not languageID:
		languageName = request.args.get('languageName', '')
		if not languageName:
			return redirect('/LanguageList.html')
		cursor.execute("select ID from TargetLanguages where LangName = '%s' limit 1" % languageName)
		languageID = cursor.fetchone()['ID']
		
	cursor.execute("select distinct TermID, IgnoreTerm, Term, TermTranslation, LangCode3Ltr, LangName, ProductCode, ProductName, ContentType, NewTo, DateRequested, DateUpdated, DateTranslated, TranslateUserID, Verified, VerifyUserID, Approved, ApproveUserID, HasArchive, HasComments from TermList where LangCode3Ltr = (select LangCode3Ltr from TargetLanguages where ID = %s) order by Term asc, ProductName asc" % languageID)
	terms = cursor.fetchall()
	recentLangs = recentLanguages(cursor)
	recentProds = recentProducts(cursor)
	lateJobs = latestJobs(cursor)
	quickAccess = buildQuickAccess(cursor)
	if terms:
		language = terms[0]['LangName']
		cursor.execute("update TargetLanguages set LastUsed=CURRENT_TIMESTAMP where ID=%s limit 1" % languageID)
		conn.commit()
		conn.close()
		return render_template('TermListLanguage.html',
			language = language,
			recentLanguages = recentLangs,
			recentProducts = recentProds,
			latestJobs = lateJobs,
			quickAccess = quickAccess,
			terms = terms,
			userID = userID,
			userName = userFirstName + " " + userLastName,
			STAGING = isStaging)
	else:
		cursor.execute("select LangName from TargetLanguages where ID = %s limit 1" % languageID)
		language = cursor.fetchone()
		conn.close()
		return render_template('TermListLanguage.html',
			language = language['LangName'],
			recentLanguages = recentLangs,
			recentProducts = recentProds,
			latestJobs = lateJobs,
			quickAccess = quickAccess,
			userID = userID,
			userName = userFirstName + " " + userLastName,
			STAGING = isStaging)
		
@app.route('/TermListProduct.html', methods=['GET'])
def TermListProduct():
	productID = request.args.get('productID', '')
	userID = 0
	userFirstName = ""
	userLastName = ""
	
	if 'UserID' in session:
		userID = session['UserID']
		userFirstName = session['UserFirstName']
		userLastName = session['UserLastName']
	
	conn = connectToDB()
	cursor = conn.cursor(pymysql.cursors.DictCursor)
	if not productID:
		productCode = request.args.get('productCode', '')
		if not productCode:
			return redirect('/ProductList.html')
		cursor.execute("select ID from Products where ProductCode = '%s' limit 1" % productCode)
		productID = cursor.fetchone()['ID']
	
	cursor.execute("select distinct TermID, IgnoreTerm, Term, TermTranslation, LangCode3Ltr, LangName, ProductCode, ProductName, ContentType, NewTo, DateRequested, DateUpdated, DateTranslated, TranslateUserID, Verified, VerifyUserID, Approved, ApproveUserID, HasArchive, HasComments from TermList where ProductCode = (select ProductCode from Products where ID = %s) order by LangCode2Ltr asc, Term asc" % productID)
	terms = cursor.fetchall()
	recentLangs = recentLanguages(cursor)
	recentProds = recentProducts(cursor)
	lateJobs = latestJobs(cursor)
	quickAccess = buildQuickAccess(cursor)
	if terms:
		product = terms[0]['ProductName']
		cursor.execute("update Products set LastUsed=CURRENT_TIMESTAMP where ID=%s limit 1" % productID)
		conn.commit()
		conn.close()
		return render_template('TermListProduct.html',
			product = product,
			recentLanguages = recentLangs,
			recentProducts = recentProds,
			latestJobs = lateJobs,
			quickAccess = quickAccess,
			terms = terms,
			userID = userID,
			userName = userFirstName + " " + userLastName,
			STAGING = isStaging)
	else:
		cursor.execute("select ProductName from Products where ID = %s limit 1" % productID)
		product = cursor.fetchone()
		conn.close()
		return render_template('TermListProduct.html',
			product = product['ProductName'],
			recentLanguages = recentLangs,
			recentProducts = recentProds,
			latestJobs = lateJobs,
			quickAccess = quickAccess,
			userID = userID,
			userName = userFirstName + " " + userLastName,
			STAGING = isStaging)
		
@app.route('/TermListContent.html', methods=['GET'])
def TermListContent():
	contentTypeID = request.args.get('contentTypeID', '')
	userID = 0
	userFirstName = ""
	userLastName = ""
	
	if 'UserID' in session:
		userID = session['UserID']
		userFirstName = session['UserFirstName']
		userLastName = session['UserLastName']
	
	conn = connectToDB()
	cursor = conn.cursor(pymysql.cursors.DictCursor)
	contentType = ""
	if not contentTypeID:
		contentType = request.args.get('contentType', '')
		if not contentType:
			return redirect('/ContentList.html')
		cursor.execute("select ID from ContentTypes where ContentType = '%s' limit 1" % contentType)
		contentTypeID = cursor.fetchone()['ID']
	
	cursor.execute("select distinct TermID, IgnoreTerm, Term, TermTranslation, LangCode3Ltr, LangName, ProductCode, ProductName, ContentType, NewTo, DateRequested, DateUpdated, DateTranslated, TranslateUserID, Verified, VerifyUserID, Approved, ApproveUserID, HasArchive, HasComments from TermList where ContentType = (select ContentType from ContentTypes where ID = %s) or ContentType = 'Both' order by ProductName asc, LangCode2Ltr asc, Term asc" % contentTypeID)
	terms = cursor.fetchall()
#	import pprint
#	pprint.PrettyPrinter(indent=2).pprint(terms)
	recentLangs = recentLanguages(cursor)
	recentProds = recentProducts(cursor)
	lateJobs = latestJobs(cursor)
	quickAccess = buildQuickAccess(cursor)
	if not contentType:
		cursor.execute("select ContentType from ContentTypes where ID = %s limit 1" % contentTypeID)
		content = cursor.fetchone()
		contentType = content['ContentType']
	conn.close()
	if terms:
		return render_template('TermListContent.html',
			contentType = contentType,
			recentLanguages = recentLangs,
			recentProducts = recentProds,
			latestJobs = lateJobs,
			quickAccess = quickAccess,
			terms = terms,
			userID = userID,
			userName = userFirstName + " " + userLastName,
			STAGING = isStaging)
	else:
		return render_template('TermListContent.html',
			contentType = contentType,
			recentLanguages = recentLangs,
			recentProducts = recentProds,
			latestJobs = lateJobs,
			quickAccess = quickAccess,
			userID = userID,
			userName = userFirstName + " " + userLastName,
			STAGING = isStaging)
			
@app.route('/terminology.tbx', methods=['GET'])
def terminology():
	jobID = 0
	langID = 0
	prodID = 0
	jobID = request.args.get('jobID', '')

	userID = 0
	userFirstName = ""
	userLastName = ""
	
	if 'UserID' in session:
		userID = session['UserID']
		userFirstName = session['UserFirstName']
		userLastName = session['UserLastName']
	
	conn = connectToDB()
	cursor = conn.cursor(pymysql.cursors.DictCursor)
	if jobID:
		cursor.execute("select * from TermList where Approved = b'1' and IgnoreTerm = b'0' and JobID = %s order by Term asc" % jobID)
	else:
		langID = request.args.get('langID', '')
		prodID = request.args.get('prodID', '')
		if not langID or langID == '0':
			if not prodID or prodID == '0':
				cursor.execute("select * from TermList where Approved = b'1' and IgnoreTerm = b'0' and order by LangCode3Ltr asc, Term asc, ProductName asc")
			else:
				cursor.execute("select * from TermList where Approved = b'1' and IgnoreTerm = b'0' and ProductCode = (select ProductCode from Products where ID = %s) order by LangCode3Ltr asc, Term asc" % prodID)
		elif not prodID or prodID == '0':
			cursor.execute("select * from TermList where Approved = b'1' and IgnoreTerm = b'0' and LangCode3Ltr = (select LangCode3Ltr from TargetLanguages where ID = %s) order by Term asc, ProductName asc" % langID)
		else:
			cursor.execute("select * from TermList where Approved = b'1' and IgnoreTerm = b'0' and ProductCode = (select ProductCode from Products where ID = %s) and LangCode3Ltr = (select LangCode3Ltr from TargetLanguages where ID = %s) order by Term asc, ProductName asc" % (prodID, langID))
	
	terms = cursor.fetchall()
	glossary = {}
	for term in terms:
		if term['Term'] not in glossary:
			glossary[term['Term']] = []
		glossary[term['Term']].append(term)
	
	recentLangs = recentLanguages(cursor)
	recentProds = recentProducts(cursor)
	lateJobs = latestJobs(cursor)
	quickAccess = buildQuickAccess(cursor)
	if terms:
		response = make_response(render_template('terminology.tbx',
			jobID = jobID,
			langID = langID,
			prodID = prodID,
			termBaseTitle = 'tbd',
			terms = glossary,
			userID = userID,
			userName = userFirstName + " " + userLastName,
			STAGING = isStaging))
		response.headers['Content-Disposition'] = "attachment; filename=glossary.tbx"
		response.headers['Content-Type'] = "text/tbx; charset=utf-8"
		return response
	elif jobID:
		cursor.execute("select concat('job ', concat_ws(', ', ProductCode, LangCode3Ltr, ContentType)) as JobString from JobList where JobID = %s limit 1" % jobID)
		jobString = cursor.fetchone()
		conn.close()
		return render_template('TermList.html',
			jobString = jobString['JobString'],
			recentLanguages = recentLangs,
			recentProducts = recentProds,
			latestJobs = lateJobs,
			quickAccess = quickAccess,
			userID = userID,
			userName = userFirstName + " " + userLastName,
			STAGING = isStaging)
	else:
		if not langID or langID == '0':
			if not prodID or prodID == '0':
				cursor.execute("select concat_ws(', ', 'All products', 'All languages')")
			else:
				cursor.execute("select concat_ws(', ', ProductName, 'All languages') as JobString from Products where Products.ID = %s limit 1" % prodID)
		elif not prodID or prodID == '0':
			cursor.execute("select concat_ws(', ', 'All products', LangName) as JobString from TargetLanguages where TargetLanguages.ID = %s limit 1" % langID)
		else:
			cursor.execute("select concat_ws(', ', ProductName, LangName) as JobString from Products, TargetLanguages where Products.ID = %s and TargetLanguages.ID = %s limit 1" % (prodID, langID))
		jobString = cursor.fetchone()
		conn.close()
		return render_template('TermList.html',
			jobString = jobString['JobString'],
			recentLanguages = recentLangs,
			recentProducts = recentProds,
			latestJobs = lateJobs,
			quickAccess = quickAccess,
			userID = userID,
			userName = userFirstName + " " + userLastName,
			STAGING = isStaging)
		
@app.route('/JobList.html', methods=['GET'])
def JobList():
	langID = request.args.get('langID', '')
	prodID = request.args.get('prodID', '')

	userID = 0
	userFirstName = ""
	userLastName = ""
	
	if 'UserID' in session:
		userID = session['UserID']
		userFirstName = session['UserFirstName']
		userLastName = session['UserLastName']
	
	conn = connectToDB()
	cursor = conn.cursor(pymysql.cursors.DictCursor)
	if not langID or langID == '0':
		if not prodID or prodID == '0':
			cursor.execute("select * from JobList")
		else:
			cursor.execute("select * from JobList where ProductCode = (select ProductCode from Products where Products.ID = %s limit 1)" % prodID)
	elif not prodID or prodID == '0':
		cursor.execute("select * from JobList where LangCode3Ltr = (select LangCode3Ltr from TargetLanguages where TargetLanguages.ID = %s limit 1)" % langID)
	else:
		cursor.execute("select * from JobList where LangCode3Ltr = (select LangCode3Ltr from TargetLanguages where TargetLanguages.ID = %s limit 1) and ProductCode = (select ProductCode from Products where Products.ID = %s limit 1)" % (langID, prodID))
	jobs = cursor.fetchall()
	language = None
	if langID and langID != '0':
		cursor.execute("select LangName from TargetLanguages where ID = %s" % langID)
		language = cursor.fetchone()
		if language:
			language = language['LangName']
	product = None
	if prodID and prodID != '0':
		cursor.execute("select ProductName from Products where ID = %s" % prodID)
		product = cursor.fetchone()
		if product:
			product = product['ProductName']
	recentLangs = recentLanguages(cursor)
	recentProds = recentProducts(cursor)
	quickAccess = buildQuickAccess(cursor)
	conn.close()
	return render_template('JobList.html',
		recentLanguages = recentLangs,
		recentProducts = recentProds,
		quickAccess = quickAccess,
		language = language,
		product = product,
		jobs = jobs,
		userID = userID,
		userName = userFirstName + " " + userLastName,
		STAGING = isStaging)

@app.route('/LanguageList.html', methods=['GET'])
def LanguageList():
	userID = 0
	userFirstName = ""
	userLastName = ""
	
	if 'UserID' in session:
		userID = session['UserID']
		userFirstName = session['UserFirstName']
		userLastName = session['UserLastName']
	
	conn = connectToDB()
	cursor = conn.cursor(pymysql.cursors.DictCursor)
	cursor.execute("select * from LanguageList")
	languages = cursor.fetchall()
#	import pprint
#	pprint.PrettyPrinter(indent=2).pprint(jobs)
	recentProds = recentProducts(cursor)
	lateJobs = latestJobs(cursor)
	quickAccess = buildQuickAccess(cursor)
	conn.close()
	if languages:
		return render_template('LanguageList.html',
			recentProducts = recentProds,
			latestJobs = lateJobs,
			quickAccess = quickAccess,
			languages = languages,
			userID = userID,
			userName = userFirstName + " " + userLastName,
			STAGING = isStaging)
	else:
		return render_template('LanguageList.html',
			recentProducts = recentProds,
			latestJobs = lateJobs,
			quickAccess = quickAccess,
			userID = userID,
			userName = userFirstName + " " + userLastName,
			STAGING = isStaging)

@app.route('/ProductList.html', methods=['GET'])
def ProductList():
	userID = 0
	userFirstName = ""
	userLastName = ""
	
	if 'UserID' in session:
		userID = session['UserID']
		userFirstName = session['UserFirstName']
		userLastName = session['UserLastName']
	
	conn = connectToDB()
	cursor = conn.cursor(pymysql.cursors.DictCursor)
	cursor.execute("select * from ProductList")
	products = cursor.fetchall()
	recentLangs = recentLanguages(cursor)
	lateJobs = latestJobs(cursor)
	quickAccess = buildQuickAccess(cursor)
	conn.close()
	if products:
		return render_template('ProductList.html',
			recentLanguages = recentLangs,
			latestJobs = lateJobs,
			quickAccess = quickAccess,
			products = products,
			userID = userID,
			userName = userFirstName + " " + userLastName,
			STAGING = isStaging)
	else:
		return render_template('ProductList.html',
			recentLanguages = recentLangs,
			latestJobs = lateJobs,
			quickAccess = quickAccess,
			userID = userID,
			userName = userFirstName + " " + userLastName,
			STAGING = isStaging)

@app.route('/ContentList.html', methods=['GET'])
def ContentList():
	userID = 0
	userFirstName = ""
	userLastName = ""
	
	if 'UserID' in session:
		userID = session['UserID']
		userFirstName = session['UserFirstName']
		userLastName = session['UserLastName']
	
	conn = connectToDB()
	cursor = conn.cursor(pymysql.cursors.DictCursor)
	cursor.execute("select * from ContentList")
	contentTypes = cursor.fetchall()
	recentLangs = recentLanguages(cursor)
	recentProds = recentProducts(cursor)
	lateJobs = latestJobs(cursor)
	quickAccess = buildQuickAccess(cursor)
	conn.close()
	if contentTypes:
		return render_template('ContentList.html',
			recentLanguages = recentLangs,
			recentProducts = recentProds,
			latestJobs = lateJobs,
			quickAccess = quickAccess,
			contentTypes = contentTypes,
			userID = userID,
			userName = userFirstName + " " + userLastName,
			STAGING = isStaging)
	else:
		return render_template('ContentList.html',
			recentLanguages = recentLangs,
			recentProducts = recentProds,
			latestJobs = lateJobs,
			quickAccess = quickAccess,
			userID = userID,
			userName = userFirstName + " " + userLastName,
			STAGING = isStaging)
			
@app.route('/archiveForTerm/<termID>', methods=['GET'])
def archiveForTerm(termID):
	conn = connectToDB()
	cursor = conn.cursor(pymysql.cursors.DictCursor)
	cursor.execute("select TermTranslation, DateTranslated, getUserNameByID(Archive.TranslateUserID) as TranslateUserID from Archive where TermTranslationID = %s order by DateTranslated desc" % termID)
	archive = cursor.fetchall()
	conn.close()
	return render_template('ArchiveList.html',
		archive = archive,
		STAGING = isStaging)

@app.route('/contextForTerm/<termID>', methods=['GET'])
def contextForTerm(termID):
	conn = connectToDB()
	cursor = conn.cursor(pymysql.cursors.DictCursor)
	cursor.execute("select SourceContext, MTofContext, ContentType from TermContexts inner join ContentTypes on ContentTypeID = ContentTypes.ID where TermTranslationID = %s order by SourceContext asc limit 20" % termID)
	contexts = cursor.fetchall()
	conn.close()
	return render_template('ContextList.html',
		contexts = contexts,
		STAGING = isStaging)

@app.route('/commentsForTerm/<termID>', methods=['GET'])
@app.route('/commentsForTerm/<termID>/<newComment>', methods=['GET'])
def commentsForTerm(termID, newComment='0'):
	userID = 0
	userFirstName = ""
	userLastName = ""
	
	if 'UserID' in session:
		userID = session['UserID']
		userFirstName = session['UserFirstName']
		userLastName = session['UserLastName']

	conn = connectToDB()
	cursor = conn.cursor(pymysql.cursors.DictCursor)
	cursor.execute("select ID, Comment, getUserNameByID(TermComments.UserID) as UserID, CommentDate, (TermComments.UserID = '%s') as ToDelete from TermComments where TermTranslationID = %s order by CommentDate desc" % (userID, termID))
	comments = cursor.fetchall()
	conn.close()
	return render_template('CommentsList.html',
		new = newComment == '1',
		termID = termID,
		comments = comments,
		userID = userID,
		userName = userFirstName + " " + userLastName,
		STAGING = isStaging)

@app.route('/addCommentsForTerm', methods=['POST'])
def addCommentsForTerm():
	content = convertContent(request.get_json())
	conn = connectToDB()
	cursor = conn.cursor(pymysql.cursors.DictCursor)
	cursor.execute("insert into TermComments(TermTranslationID, Comment, UserID) values(%s, '%s', '%s')" % (content['TermTranslationID'], conn.escape_string(content['Comment']), conn.escape_string(content['UserID'])))
	cursor.execute("select last_insert_id() as ID")
	commentID = cursor.fetchone()
	cursor.execute("update TermTranslations set DateUpdated=CURRENT_TIMESTAMP where ID=%s limit 1" % content['TermTranslationID'])
	conn.commit()
	cursor.execute("select CommentDate, getUserNameByID(%s) as UserID from TermComments where ID = %s limit 1" % (content['UserID'], commentID['ID']))
	result = cursor.fetchone()
	content['CommentDate'] = result['CommentDate']
	content['UserID'] = result['UserID']
	content['ID'] = commentID['ID']
	conn.close()
	return render_template('CommentRow.html',
		comment = content)
		
@app.route('/deleteComment', methods=['POST'])
def deleteComment():
	content = convertContent(request.get_json())
	conn = connectToDB()
	cursor = conn.cursor()
	cursor.execute("delete from TermComments where ID = %s" % content['ID'])
	cursor.execute("update TermTranslations set DateUpdated=CURRENT_TIMESTAMP where ID=%s limit 1" % content['TermID'])
	conn.commit()
	conn.close()
	return ("", 204)

def convertContent(content):
	result = {}
	for datum in content:
		result[datum['name']] = datum['value']
	return result
	
@app.route('/translateTerm', methods=['POST'])
def translateTerm():
	content = convertContent(request.get_json())
	conn = connectToDB()
	cursor = conn.cursor(pymysql.cursors.DictCursor)
	if content['IgnoreTerm']:
		content['IgnoreTerm'] = '1'
	else:
		content['IgnoreTerm'] = '0'
	if content['Verified']:
		content['Verified'] = '1'
	else:
		content['Verified'] = '0'
	if content['Approved']:
		content['Approved'] = '1'
	else:
		content['Approved'] = '0'
# 	logger.debug("update TermTranslations set IgnoreTerm=b'%s', TermTranslation='%s', TranslateUserID='%s', Verified=b'%s', Approved=b'%s' where TermTranslations.ID=%s limit 1" % (content['IgnoreTerm'], conn.escape_string(content['TermTranslation']), content['UserID'], content['Verified'], content['Approved'], content['TermID']))
	cursor.execute("update TermTranslations set IgnoreTerm=b'%s', TermTranslation='%s', TranslateUserID='%s', Verified=b'%s', Approved=b'%s' where TermTranslations.ID=%s limit 1" % (content['IgnoreTerm'], conn.escape_string(content['TermTranslation']), content['UserID'], content['Verified'], content['Approved'], content['TermID']))
	conn.commit()
	cursor.execute("select * from TermList where TermID=%s limit 1" % content['TermID'])
	content, = cursor.fetchall()
	conn.close()
	content['DateRequested'] = str(content['DateRequested'])
	content['DateUpdated'] = str(content['DateUpdated'])
	content['DateTranslated'] = str(content['DateTranslated'])
	content['IgnoreTerm'] = str(content['IgnoreTerm'])
	content['Verified'] = str(content['Verified'])
	content['Approved'] = str(content['Approved'])
	content['HasArchive'] = str(content['HasArchive'])
	content['HasComments'] = str(content['HasComments'])
	return json.dumps(content)
	
def cleanup(*args):
	global threads
	global exitFlag
	if len(threads) > 0:
		exitFlag = True
		for t in threads:
			t.join()
	sys.exit(0)
	

jobQueue = Queue.Queue()
threads = []

thread = termHarvestThread(len(threads) + 1)
thread.start()
threads.append(thread)
