Georgetown Memex Human Traffic Point Fact Search System
================================================

This is the search system for Memex Human Traffic ``Point Fact`` questions from Georgetown Univerisity Infosense Team. 

Usage
=====

The system is generally divided into 4 parts, which are ``Search``, ``Validation``, ``Answer Extraction`` and ``Ranking``. It is mainly implemented by Python so before you go ahead and run the system, there are several packages that need to be installed:

::
    fuzzywuzzy,elasticsearch,certifi,pyyaml,bs4,webcolors,nltk,cbor,lxml
    

There is also a shell script named ``pipInstall.sh`` in this repository that can help you install all the packages above once you run it. 

Search
======

The code of this part is mainly in ``search.py``. It basically takes a SPARQL query as input, do query parsing & expansion, then build elasticsearch query body based on it, finally retrive documents from elasticsearch. A sample query could be:

::
    {
		"type": "Point Fact", 
		"question": "What is the country of birth listed in the ad that contains the phone number 6135019502, in Toronto Ontario, with the title 'the millionaires mistress'?", 
		"id": "192", 
		"SPARQL": ["PREFIX qpr: <http://istresearch.com/qpr>\nSELECT ?ad ?ethnicity\nWHERE\n{\t?ad a qpr:Ad ;\n\tqpr:phone '6135019502' ;\n\tqpr:location 'Toronto, Ontario' ;\n\tqpr:title ?title .\n\tFILTER CONTAINS(LCASE(?title), 'the millionaires mistress')\n}"]
    }

and the parsed query would be:

::
    {
		'must_search_field': 
			{
				'phone': '6135019502', 
				'location': 'Toronto', 
				'title': 'the millionaires mistress'
			}, 
		'should_search_field': 
			{
				'location': 'Toronto, Ontario'
			}, 
		'group': {}, 
		'required_match_field': 
			{
				'phone': '6135019502', 
				'location': 'Toronto, Ontario', 
				'title': 'the millionaires mistress'
			}, 
		'answer_field': 
			{
				'ethnicity': '?ethnicity'
			}, 
		'type': 'Point Fact', 
		'id': '192'
	}

the elasticsearch query body would be:

::
    {'query': 
		{'bool': 
			{'should': 
				[
					{'match': 
						{'extracted_text': '613-501-9502'}
					}, 
					{'match': 
						{'extracted_text': '(613)501-9502'}
					}, 
					{'match': 
						{'extracted_text': 'Toronto, Ontario'}
					}, 
					{'match': {'extracted_text': 'ethnicity'}
					}
				], 
			'must': 
				{'match': 
					{'extracted_text': '613 AND 501 AND 9502 AND Toronto AND the millionaires mistress'}
				}
			}
		}, 
		'size': 3000
	}

Validation
==========

After document retrival, we would do validation to check if a document is atcually what we are search for. The validation step is done in ``validate`` function in main.py. There are two modes for validation which are restricted mode and  unrestricted mode. In the restricted mode, all the given conditions in the query have to be satified in order for a document to be validated. While in unrestriced mode, the more conditions satisfied, the better the document is. And we will evaluate the validation quality by a score which called ``validation score``. In restricted mode, the ``validation score``is either 1(all given conditions satisfied) or 0(any condition not satisfied). In unrestricted mode, the ``validation score`` depends on how much conditions satified. For example, if there are 5 given conditions and 3 of them meets in a document, then the ``validation score`` for that docuemnt is 3/5 = 0.6. Initially, we answer the query in restricted mode. Unless there is no answers in the end, we won't use unrestricted mode. 

Answer Extraction
=================

Answer extraction is basically extracting the answer that the question is mainly concerned about(all the extraction fucntions are in ``extraction.py``). However, it could be challenging due to the "noises". What we do here is combining several features of interests and make use of the fact that the features of one person should be grouped together, that is they lie near each other in the document. Therefore by calculating the word distance, we can in a way determine which answer is better. The shorter the overall distance is, the more convincing the candidate answer is. We use an answer extraction score to stand for the quality of the answer. The "denoise" step is done in ``clarify`` function in main.py.

Ranking
=======

After we got the candidate answers, ``validation score`` and ``answer extraction score``, we need to do a rank to see which document is better, namely we need to get a ``final score`` for each document. What we define here is 

::
    ``final score`` = ``validation score`` * ``answer extraction score``

Then we set up a threshhold to do a filter of the documents. This step is done in ``generate_formal_answer`` function in main.py. If there is no answer in the end, we will run the query again but with unrestricted mode this time. 


