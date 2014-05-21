# -*- coding: utf-8 -*-
#####################
#
# © 2012–2014 Autodesk Development Sàrl
#
# Created by Petra Ribiczey
#
# Changelog
# v3.6			Modified on 21 May 2014 by Ventsislav Zhechev
# Updated to connect to new Solr setup for term lookup.
# Added a few status messages.
# Removed some dead code.
#
# v3.5			Modified on 16 Nov 2013 by Ventsislav Zhechev
# Switched to using a logger provided by the Service module for debug output.
# Fixed a bug with some global counters.
# Removed some unused imports.
# 
# v3.4			Modified on 05 Nov 2013 by Ventsislav Zhechev
# Modified to use one ngram list per language to facilitate language-specific terminology extraction.
#
# v3.3			Modified on 04 Nov 2013 by Ventsislav Zhechev
# Put in a MAJOR update to much of the chunk processing code geared towards speed optimisation.
# Delayed the chunk substring lookup to the moment with the least number of chunks to check before sending data off to NeXLT.
#
# v3.2			Modified on 28 Oct 2013 by Ventsislav Zhechev
# Removed the static processing of product names and available languages.
#
# v3.1			Modified on 21 Oct 2013 by Ventsislav Zhechev
# Modified Getterms method to proces a list of segments, rather than a single string containing all data.
# Simplified the generation of the final list of terms.
#
# v3.0.1		Modified on 18 Oct 2013 by Ventsislav Zhechev
# Simplified portions of the source code
#
# v3				Modified on 15 Oct 2013 by Ventsislav Zhechev
# Overhauled the architecture to allow the use as a module from within other Python scripts.
# Removed dead/useless code
# Improved code coherence
#
# v2.3.3		Modified on 29 Aug 2013 by Ventsislav Zhechev
# Moved up the validation of the command line parameters to before the tokeniser training.
# ‘NEW_PRODUCT’ is now an allowed product code option.
# Fixed a bug where the empty string could be extracted as a term candidate.
#
# v2.3.2		Modified on 28 Aug 2013 by Ventsislav Zhechev
# Fixed two index-out-of-bounds bugs.
#
# v2.3.1		Modified on 21 Jun 2013 by Ventsislav Zhechev
# Modified the code to filter substring terms. Now we are keeping the longest term available.
# Commented out all debug output.
#
# v2.3			Modified on 18 Jun 2013 by Ventsislav Zhechev
# Fixed a few UTF-8 related issues.
# Fixed a few minor bugs.
# Switched off substring filtering, as it does not appear to be beneficial.
#
# v2.2			Modified on 17 Jun 2013 by Ventsislav Zhechev
# Fixed a few bugs in chunk processing.
# Reduced the memory usage through using a single temp list for chunks.
# Reduced the number of cycles through the chunks by applying different filters in a single run.
#
# v2.1			Modified on 14 Jun 2013 by Ventsislav Zhechev
# Added more progress output to stderr.
# Combined some processing steps to improve performance.
# Removed some unnecessary processing steps.
# Switched to the brill POS tagger for efficiency—the TnT tagger was too slow.
#
# v2			Modified on 27 May 2013 by Ventsislav Zhechev
# Modified the hard-coded file paths.
# Added command-line parameter handling, so that the script could be called directly, rather launching it from within Python.
# Added extra check for bad POS-tagger output
# Added progress indicator output
#
# v1			Modified by Petra Ribiczey
# Original version.
#
#####################

"""
Prerequisites:
- files are encoded as utf-8
- 
"""

import nltk, codecs, locale, requests, json, re, bz2
from nltk.tokenize import LineTokenizer, TreebankWordTokenizer
from nltk.tag import brill, tnt, DefaultTagger
from nltk.corpus import conll2000, treebank
from nltk.corpus.reader import TaggedCorpusReader
from operator import itemgetter
from functools import cmp_to_key

import Service


# Module-level variables
pos_tagger = None
word_tok = sent_tokenizer = None
ngrams = {}
nowords = None
__debug_on__ = False

adskCorpusRoot = adskUnwordsRoot = ngramFilePath = None


def init(settings):
#	Service.logger.debug("Initialising terminology extraction system...")
	if settings == None:
		settings = dict(
			adskCorpusRoot="/Volumes/OptiBay/ADSK_Software/termExtraction/auxiliaryData/taggerCorpus",
			adskUnwordsRoot="/Volumes/OptiBay/ADSK_Software/termExtraction/auxiliaryData/unwords",
			ngramFilePath="/Volumes/OptiBay/ADSK_Software/termExtraction/auxiliaryData/enu.ngrams.nocounts",
			)
	global adskCorpusRoot, adskUnwordsRoot, ngramFilePath
	adskCorpusRoot = settings["adskCorpusRoot"]
	adskUnwordsRoot = settings["adskUnwordsRoot"]
	ngramFilePath = settings["ngramFilePath"]
	

# Define tokenizers (these could be changed if needed.)
word_tok = nltk.TreebankWordTokenizer()
sent_tokenizer = nltk.LineTokenizer()

def preplists(filelocation):
	if __debug_on__:
		Service.logger.debug("\tReading file " + filelocation + "...")
	lineSet = set()
	for line in codecs.open(filelocation, "r", 'utf-8'):
		lineSet.add(line.rstrip().lower())
	return lineSet
	

def loadAuxiliaryData():
#	Service.logger.debug("Loading auxiliary data for terminology extraction system...")
	global ngramFilePath, adskUnwordsRoot
	global ngrams, nowords

#	ngrams = codecs.open(ngramFilePath, "r", "utf-8").read()
	conn = Service.connectToDB()
	cursor = conn.cursor()
	cursor.execute("select LangCode3Ltr from TargetLanguages")
	langs = cursor.fetchall()
	conn.close()
	for lang in langs:
		if __debug_on__:
			Service.logger.debug("\t\tReading nGram file " + ngramFilePath+"."+lang[0].upper()+".bz2...")
		ngrams[lang[0]] = bz2.BZ2File(ngramFilePath+"."+lang[0].upper()+".bz2", "r").read()

	# Load Autodesk-related lists:
	# - ngram-list (from Ventzi, including only the ngrams without counts)
	# - NeXLT product names (------ there is an N/A in it???)
	# - NeXLT language list
	# - city names from http://www.geodatasource.com/ and http://www.maxmind.com/en/worldcities
	# - words which should not be harvested (unwords and general words)
	# - Autodesk trademarks
	# - company names
	# Define nowords as filter
	nowords = preplists(adskUnwordsRoot+"/general_words.txt").union(preplists(adskUnwordsRoot+"/un_words.txt").union(preplists(adskUnwordsRoot+"/autodesk_trademarks.txt").union(preplists(adskUnwordsRoot+"/company_names.txt").union(preplists(adskUnwordsRoot+"/cities_regions.txt")))))

def trainPOSTagger(useTnTTagger):
	global __debug_on__
	global pos_tagger
	global adskCorpusRoot
	# Train TNT/Brill POS-tagger using own training data + treebank data from nltk. Tested that using treebank data improves results.

	autodesk = TaggedCorpusReader(adskCorpusRoot, '.*', encoding='utf-8')
	train_sents =  autodesk.tagged_sents() + treebank.tagged_sents()

	# Use TnT tagger on request
	if useTnTTagger:
		if __debug_on__:
			Service.logger.debug("Using TnT POS tagger...")
		unk_tagger = DefaultTagger('NN')

		pos_tagger = tnt.TnT(unk=unk_tagger, Trained=True)
		pos_tagger.train(train_sents)
	# Use Brill tagger by default
	else:
		if __debug_on__:
			Service.logger.debug("Using Brill POS tagger...")

		def backoff_tagger(tagged_sents, tagger_classes, backoff=None):
			if not backoff:
				backoff = tagger_classes[0](tagged_sents)
				del tagger_classes[0]
 
			for cls in tagger_classes:
				tagger = cls(tagged_sents, backoff=backoff)
				backoff = tagger
 
			return backoff
	
		word_patterns = [
			(r'^-?[0-9]+(.[0-9]+)?$', 'CD'),
			(r'.*ould$', 'MD'),
			(r'.*ing$', 'VBG'),
			(r'.*ed$', 'VBD'),
			(r'.*ness$', 'NN'),
			(r'.*ment$', 'NN'),
			(r'.*ful$', 'JJ'),
			(r'.*ious$', 'JJ'),
			(r'.*ble$', 'JJ'),
			(r'.*ic$', 'JJ'),
			(r'.*ive$', 'JJ'),
			(r'.*ic$', 'JJ'),
			(r'.*est$', 'JJ'),
			(r'^a$', 'PREP'),
		]
		raubt_tagger = backoff_tagger(train_sents, [nltk.tag.AffixTagger, nltk.tag.UnigramTagger, nltk.tag.BigramTagger, nltk.tag.TrigramTagger], backoff=nltk.tag.RegexpTagger(word_patterns))
 
		templates = [
			brill.SymmetricProximateTokensTemplate(brill.ProximateTagsRule, (1,1)),
			brill.SymmetricProximateTokensTemplate(brill.ProximateTagsRule, (2,2)),
			brill.SymmetricProximateTokensTemplate(brill.ProximateTagsRule, (1,2)),
			brill.SymmetricProximateTokensTemplate(brill.ProximateTagsRule, (1,3)),
			brill.SymmetricProximateTokensTemplate(brill.ProximateWordsRule, (1,1)),
			brill.SymmetricProximateTokensTemplate(brill.ProximateWordsRule, (2,2)),
			brill.SymmetricProximateTokensTemplate(brill.ProximateWordsRule, (1,2)),
			brill.SymmetricProximateTokensTemplate(brill.ProximateWordsRule, (1,3)),
			brill.ProximateTokensTemplate(brill.ProximateTagsRule, (-1, -1), (1,1)),
			brill.ProximateTokensTemplate(brill.ProximateWordsRule, (-1, -1), (1,1))
		]
	 
		trainer = brill.FastBrillTaggerTrainer(raubt_tagger, templates)
		pos_tagger = trainer.train(train_sents, max_rules=200, min_score=3)


# Define harvesting process

# 'content' is the text to harvest terms from
# 'lang' is the target language
# 'prods' is a list of product codes on NeXLT
# example for a string that is in an Inventor product: Getterms("Define user-specific information %d", 'jpn', 'INV'])
def Getterms(content, lang, prods, returnJSON):
	global __debug_on__, bad_stemmer_1, bad_stemmer_3, bad_stemmer_4
	bad_stemmer_1 = bad_stemmer_3 = bad_stemmer_4 = 0

	Service.logger.debug("Started processing for %d segments for language %s" % (len(content), lang))

	
	new_content = set()
	new_content_orig = ""
	new_content_orig_tok = set()
	
	for seg in set(content):
		seg = seg.replace('\\r','\r') # Treating UI strings containing \r escapes
		seg = seg.replace('\\n','\n') # Treating UI strings containing \n escapes
		seg = seg.replace('\r\n','\n')# Collapsing new lines
		seg = seg.replace('\n ','\n') # Clean-up the line endings—not sure if useful at all
		new_content_orig += " " + seg
		new_content_orig_tok.union(set(word_tok.tokenize(seg)))

		seg = seg.replace('%','')
		seg = seg.replace(".. ."," ...")
		seg = seg.replace('<openparen>','(')
		seg = seg.replace('<closeparen>',')')
		seg = seg.replace("&apos;","'")
		seg = seg.replace('&quot;', '"')
		seg = seg.replace('&amp;', '&')
		seg = seg.replace('&lt;', '<')
		seg = seg.replace('&gt;', '>')

	# Do the following even occur in our data?
	#	new_content = new_content.replace('&circ;', '^')
	#	new_content = new_content.replace('&tilde;', '~')
	#	new_content = new_content.replace('&ndash;', '–')
	#	new_content = new_content.replace('&mdash;', '—')
	#	new_content = new_content.replace('&lsquo;', '‘')
	#	new_content = new_content.replace('&rsquo;', '’')
	#	new_content = new_content.replace('&sbquo;', ',')
	#	new_content = new_content.replace('&ldquo;', '“')
	#	new_content = new_content.replace('&rdquo;', '”')
	#	new_content = new_content.replace('&bdquo;', '"')
	#	new_content = new_content.replace('&permil;', '‰')
	#	new_content = new_content.replace('&euro;', '€')
	
		seg_htmlcleaned = nltk.clean_html(seg)
		seg = seg_htmlcleaned.replace('\\t','\n')

		# Some very crude pre-tokenisation
		seg = seg.replace(':',' :')
		seg = seg.replace('\t','\n')
		seg = seg.replace("\\", '\n')
		seg = seg.replace('|','\n')


		# It’s not quite clear what this is supposed to do
		seg = seg.replace("&","")
		seg = seg.replace("[\\w]+_[\\w]+","\n")
		seg = seg.replace("[\\w]+_","\n")
		seg = seg.replace("_[\\w]+","\n")

#		Service.logger.debug("Segment: " + seg)
		for seg in sent_tokenizer.tokenize(seg):
			new_content.add(seg)
	

	if __debug_on__:
#		Service.logger.debug("Finished sentence segmentation.")
		Service.logger.debug("Finished character-level pre-processing.")

	# word tokenize the sentences
	new_content_tokenized = [word_tok.tokenize(line) for line in new_content]

	if __debug_on__:
		Service.logger.debug("Finished main tokenisation.")

	# Remove empty lines	
	# Remove one-word lines which are all caps. Typically: commands.	
	for l in new_content_tokenized:
		if len(l)==0 or (len(l)==1 and str(l).isupper()):
			new_content_tokenized.remove(l)
		else:
	# Remove placeholders (note: any modification can be made to the text here, as the final output will be verified in the original content)   
	# (this doesn’t really make any sense to me —— V.)
			for t in l:
				if '%' in t:
					l.remove(t)
   
	# POS tag sentences
	tagged_sent = pos_tagger.batch_tag(new_content_tokenized)

	if __debug_on__:
		Service.logger.debug("Finished main POS tagging.")


	# [Issue not repro since default tagger is added] I leave it in, in any case. None tags are extremely rare, deleting these segments results in minimal loss. 
	tagged_sent = [r for r in tagged_sent if ("', None), ('" not in str(r)) and ("', None" not in str(r)) and ("', ''" not in str(r))]


	# Define chunkers (left in 'Unk'/'UNK' as POS-tags for unknown words in the chunker definition, but the tagger uses 'NN'.) 
	def GetSurfaceChunksByStem(sentences):
		global bad_stemmer_1
		grammar = (r'''CHUNK: {(<Unk|UNK|NN.*|VBN>*)(<JJ.*|VBN>*)(<Unk|UNK|NN.*|VBN>)(<Unk|UNK|NN.*>+)}''')
		cp = nltk.RegexpParser(grammar)
		chunks = set()
		for sent in sentences:
			try:
				tree = cp.parse(sent)
				for subtree in tree.subtrees():
					if subtree.node == 'CHUNK':
						chunks.add(' '.join([l[0] for l in subtree.leaves()]))
			except:
				bad_stemmer_1 += 1
				# Service.logger.debug("1+")
				# Service.logger.debug("Bad stemmer 1: "+str(sent))
		return chunks

	# This chunker extracts units like "Elements limiting slenderness"
	def GetSurfaceChunksByStem3(sentences):
		global bad_stemmer_3
		grammar = (r'''CHUNK: {<Unk|UNK|NN.*|VBN> <VBG> <Unk|UNK|NN.*>}''')
		cp = nltk.RegexpParser(grammar)
		chunks = set()
		for sent in sentences:
			try:
				tree = cp.parse(sent)
				for subtree in tree.subtrees():
					if subtree.node == 'CHUNK':
						chunks.add(' '.join([l[0] for l in subtree.leaves()]))
			except:
				bad_stemmer_3 += 1
				# Service.logger.debug("3+")
		return chunks

	# Chunker for single word noun-like units 
	def GetNouns(sentences):
		global bad_stemmer_4
		grammar = (r'''CHUNK: {<Unk|UNK|NN.*|VBN|JJ.*>}''')
		cp = nltk.RegexpParser(grammar)
		chunks = set()
		for sent in sentences:
			try:
				tree = cp.parse(sent)
				for subtree in tree.subtrees():
					if subtree.node == 'CHUNK':
						chunks.add(' '.join([l[0] for l in subtree.leaves()]))
			except:
				bad_stemmer_4 += 1
				# Service.logger.debug("4+")
		return chunks
	
	# Get compound chunks extracted   
	# AND Remove duplicate chunks
	new_chunks = GetSurfaceChunksByStem(tagged_sent).union(GetSurfaceChunksByStem3(tagged_sent))

	if __debug_on__:
		Service.logger.debug("Finished main chunking.")
		Service.logger.debug((u"Skipped bad parses as follows: 1=" + str(bad_stemmer_1) + u" 3=" + str(bad_stemmer_3) + u" 4=" + str(bad_stemmer_4)).encode('utf-8'))



	# Correct chunks (Some corrections aren't repro, because they were added for a different tokenizer.
	# They don't hurt to have - I leave them in.)	

	#  Maybe these characters should be removed from the beginning...?
	not_needed = ['.', '^', "'", "\\", "/", "!", '_', '%', "=", '*', '>', '<', '\\', ":", "|"]

	tempSet = set()
	for w in new_chunks:
	# [Issue not repro.] Remove '@' from multi-word units.	
		w = w.replace('@', '')
	# [Issue not repro.] Remove '*' from the multi-word units.
		w = w.replace('*', '')
	# [Issue not repro.] Remove '.' from the end of multi-word units.	
	# [Issue not repro.] Remove ',' from the end of multi-word units.	
		w.rstrip(".,")
	# Correct issue deriving from tokenization	
		w = w.replace(" 's", "'s")
	# Get rid of words containing '+' in chunks (for sw strings).
	# Eg: 'Ctrl+A key combination' will become 'key combination'
		if '+' in w:
			tok = word_tok.tokenize(w)
			for i in tok:
				if  "+" in i:
					w = w.replace(i, '')
	# [Issue not repro.] Remove '=' from multi-word units.
		w = w.replace('=', '')
	# [Issue not repro.] Remove double spaces from multi-word units.
		w = w.replace('  ', ' ')
	# [Issue not repro.] Remove space from the end of multi-word units.
	# [Issue not repro.] Remove space from the beginning of multi-word units.
		w.strip()
	
	# remove one letter words from the chunk units (eg. remains of placeholders)
		newWord = []
		noWordFound = False
		for word in word_tok.tokenize(w):
			if len(word) > 1:
				if word in nowords:
					noWordFound = True
					break
				newWord.append(word)
		if not noWordFound:
			newWord = " ".join(newWord)
			for mark in not_needed:
				if mark in newWord:
					noWordFound = True
					break
			if not noWordFound:
				tempSet.add(newWord)
	new_chunks = list(tempSet)
  

	if __debug_on__:
		Service.logger.debug("Finished first chunk cleanup.")

	
	# check if extracted multi-word units are in the ngram list. 
	compounds_new_to_the_ngram_set = set()
	
	
	counter = 0
	for wrd in new_chunks:
		if __debug_on__:
			counter += 1
			if not counter % 100:
				Service.logger.debug(".")
			if not counter % 5000:
				Service.logger.debug(str(counter))
		if re.search(" " + wrd + " ", ngrams[lang]) == None:
			compounds_new_to_the_ngram_set.add(wrd)


	if __debug_on__:
		Service.logger.debug("Finished n-gram list lookup.")


	# extract noun(like) units
	nouns = [w for w in GetNouns(tagged_sent) if w.isdigit() == False]


	# clean results up from (untranslatable) characters, nowords content and check if they are in the original content as-is
	new_nouns = set()
	for n in nouns:
		not_needed_found = False
		for mark in not_needed:
			if mark in n:
				not_needed_found = True
				break
		if not not_needed_found:
			new_nouns.add(n)
	
	new_nouns = [w.lower() for w in new_nouns if (w.lower() not in nowords) and (w in new_content_orig_tok)]

	counter = 0
	# check whether nouns exist in the ngram list	
	nouns_new_to_tm_ngram_set = set()
	for wrd in new_nouns:
		if __debug_on__:
			counter += 1
			if not counter % 100:
				Service.logger.debug(".")
			if not counter % 5000:
				Service.logger.debug(str(counter))
		if re.search(" " + wrd + " ", ngrams[lang]) == None:
			nouns_new_to_tm_ngram_set.add(wrd)
	
	if __debug_on__:
		Service.logger.debug("Finished noun selection.")

	   
	
	# Compounds: compounds_new_to_the_ngram_set
	# Single words: nouns_new_to_tm_ngram_set
	# Create one group of all chunks
	# check back if extracted term candidates are in the original text as well
	new_words_and_compounds = [w for w in compounds_new_to_the_ngram_set.union(nouns_new_to_tm_ngram_set) if w in new_content_orig]

	
	if __debug_on__:
		Service.logger.debug("Starting substring cleanup for " + str(len(new_words_and_compounds)) + " chunks")
	# remove multi-word chunks that are compouns of smaller multi-word chunks. For example, 'calculation configuration' and
	# 'dialog box' remains, but 'calculation configuration dialog box' will be removed
	tempSet = set()
	new_chunks_set = set([_.lower() for _ in new_words_and_compounds])
	new_chunks_temp = sorted(new_chunks_set, key=cmp_to_key(locale.strcoll))
	counter = 0
	for i in range(0, len(new_chunks_temp)):
		for j in range(i, len(new_chunks_temp)):
			if __debug_on__:
				counter += 1
				if not counter % 10000:
					Service.logger.debug(".")
				if not counter % 500000:
					Service.logger.debug(str(counter))
			nc = new_chunks_temp[i] + ' ' + new_chunks_temp[j]
			if nc in new_chunks_set:
				# Service.logger.debug("found superstring " + nc)
				tempSet.add(nc)
			nc = new_chunks_temp[j] + ' ' + new_chunks_temp[i]
			if nc in new_chunks_set:
				# Service.logger.debug("found superstring " + nc)
				tempSet.add(nc)
	# Word tokenize filtered multi-word units.
	new_words_and_compounds = [w for w in new_chunks_temp if w not in tempSet]

	if __debug_on__:
		Service.logger.debug("Finished chunk substring cleanup.")
		

	# Query NeXLT for existing translation
	if __debug_on__:
		Service.logger.debug("Running NeXLT queries for " + str(len(new_words_and_compounds)) + " chunks...")
	
	def QueryNeXLT(term, language, prod_name):
		r = requests.get("http://10.37.23.237:8983/solr/select/?wt=json&start=0&rows=1&q=enu%3A%22" + term + "%22%20AND%20product:"  + prod_name +  "%20AND%20" + language + ":['' TO *]")
		r.encoding = "utf-8"
		try:
			response = r.json()['response']['numFound']
		except:
			response = 0
		return response
					   
	
	def QueryNeXLTAllProds(term, language):
		r = requests.get("http://10.37.23.237:8983/solr/select/?wt=json&start=0&rows=1&q=enu%3A%22" + term + "%22%20AND%20product:"  + '*' +  "%20AND%20" + language + ":['' TO *]")
		r.encoding = "utf-8"
		try:
			response = r.json()['response']['numFound']
		except:
			response = 0
		return response


	new_words_and_compounds_in_product = []

	for t in new_words_and_compounds:
		newTerm = True
		for prod_name in prods:
			newTerm = newTerm and QueryNeXLT(t.lower(), lang, prod_name) == 0
		if newTerm:
			new_words_and_compounds_in_product.append(t)

   
	# product independent query to NeXLT
	# append context and product/corpus information + number of occurrences
	terms = []

	for term in new_words_and_compounds_in_product:
		contexts = [con for con in new_content if term.lower() in con.lower()]
		if QueryNeXLTAllProds(term.lower(), lang) == 0:
			terms.append([term, "Corpus", contexts, len(contexts), len(term)])
		else:
			terms.append([term, "Product", contexts, len(contexts), len(term)])
				


	# Sort final term list and create json format
	terms = sorted(terms, key=itemgetter(1,0), reverse=True)
	
	if __debug_on__:
		Service.logger.debug("Finished NeXLT calls with %s new terms remaining." % len(terms))

		 
	if returnJSON:
		terms_for_json = {}

		for listitem in terms:
			if prods[0] == "NEW_PRODUCT":
				k = {listitem[0]: {'newto': "New product, search in corpus only", 'context':  listitem[2], 'numContextSents': listitem[3]}}
			else:
				k = {listitem[0]: {'newto': listitem[1], 'context':  listitem[2], 'numContextSents': listitem[3]}}
			terms_for_json.update(k)

  
		if __debug_on__:
			Service.logger.debug("Finished final processing.")

		  
		return terms_for_json
		
	else:
#		import pprint
#		pprint.PrettyPrinter(indent=2).pprint(final_terms)
		if __debug_on__:
			Service.logger.debug("Finished final processing.")

		return terms
