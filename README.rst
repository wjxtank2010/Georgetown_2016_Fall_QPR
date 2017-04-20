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

In the Search part, it takes ``SPARQL query`` as input, does ``query parsing`` and ``query expansion``, then builds ``Elasticsearch query body`` and ``retrieves top 3000 documents`` from Elasticsearch.

The code of this part is mainly in ``search.py``. A sample ``SPARQL query input`` could be:

::
    {
		"type": "Point Fact", 
		"question": "What is the country of birth listed in the ad that contains the phone number 6135019502, in Toronto Ontario, with the title 'the millionaires mistress'?", 
		"id": "192", 
		"SPARQL": ["PREFIX qpr: <http://istresearch.com/qpr>\nSELECT ?ad ?ethnicity\nWHERE\n{\t?ad a qpr:Ad ;\n\tqpr:phone '6135019502' ;\n\tqpr:location 'Toronto, Ontario' ;\n\tqpr:title ?title .\n\tFILTER CONTAINS(LCASE(?title), 'the millionaires mistress')\n}"]
    }

and the ``parsed query`` would be:

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

the ``elasticsearch query body`` would be (after query expansion):

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

After document retrival, we would do validation to check if a document is atcually what we are search for. It takes ``candidate documents`` in last step as ``input`` and generate ``validation score`` for each document. The validation step is done in ``validate`` function in ``main.py`` and validates documents by functions in ``extraction.py``. 

There are two modes for validation which are ``restricted mode`` and  ``unrestricted mode``. 

In the ``restricted mode``, all the given conditions (which stored in ``required_match_field`` in ``parsed query``) in the query have to be satified in order for a document to be validated. While in ``loosed mode``, the more conditions satisfied, the better the document is. 

And the system evaluates the validation quality by a score which called ``validation score``. In restricted mode, the ``validation score``is either 1(all given conditions satisfied) or 0(any condition not satisfied). In unrestricted mode, the ``validation score`` depends on how much conditions satified. For example, if there are 5 given conditions and 3 of them meets in a document, then the ``validation score`` for that docuemnt is 3/5 = 0.6. 

Initially, we answer the query in restricted mode. If there is no answers in stricted mode, then the system automatically try the unrestricted mode. 

Answer Extraction
=================

In answer extraction part, the system check whether the ``validated documents`` really have ``answer`` for the query and gives documents ``answer extraction score``. It also uses functions in ``extraction.py``, while doing extractions for features stored in ``answer_field`` in ``parsed query`` and generate ``answer extraction score`` for each documents. 

However, it could be challenging due to the ``"noises"`` that one document may contain more than one ``"answers"``. We consider that a more confident answer should be appear together with relevant ``person features``.

After doing answer extraction, if there are only one answer in a document, the document gets a answer extraction score ``"1"`` by ``1-0`` (0 means no noise). 

If there are multiple answers, calculate the ``average word distance`` of each answer and ``selected features`` (features relevant to person, e.g. name, address, email...). For example, if the selected features are name, address, email, there are 2 names, 1 address, 0 email, 3 answers found in the document, the ``average word distance`` for the ``answer_i`` defined as:
::
avg_dis_i = (|P_name_1 - P_ans_i| + |P_name_2 - P_ans_i| + |P_address_1 - P_ans_i|)/3

The better is the answer, the smaller is the average word distance for that answer. We use an answer extraction score to stand for the quality of the answer. Corresponding ``answer extraction score`` is ``1 - avg_dis_i``. The ``"denoise"`` is done in ``clarify`` function in main.py.

Ranking
=======

After we got the candidate answers, ``validation score`` and ``answer extraction score``, we need to do a rank to see which document is better, namely we need to get a ``final score`` for each document. What we define here is 

::
    ``final score`` = ``validation score`` * ``answer extraction score``

Then we set up a threshhold to do a filter of the documents. This step is done in ``generate_formal_answer`` function in main.py. If there is no answer in the end, we will run the query again but with unrestricted mode this time. 


