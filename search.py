# -*- coding: utf-8 -*-
import certifi,os,yaml,sys,re,json
from elasticsearch import Elasticsearch,RequestsHttpConnection
import extraction

def query_retrival(query_path):
    """
    Load the json query file into a list of queries
    :param query_path: str
    :return: List[Dictionary]
    """
    with open(query_path,"r") as f:
        lines = f.readlines()
        query_list = []
        for line in lines:
            query_list.append(json.loads(line,strict = False))
        return query_list

def query_parse(query):  # input query - json
    """
    Query parsing and expansion, query in sparql format
    :param query: Dictionary
    :return: parsed query: Dictionary
    """
    skin_color_list = ["white","yellow","black"]
    query_id = query['id']
    query_type = query['type']
    sparql = query['SPARQL'][0]
    lines = sparql.split('\n')
    parsed_dic = {} #Parsed query
    ans_field = {} #feature that's queried
    must_search = {} #feature value that must exist in target documents
    should_search = {} #feature value that probably exist in target documents, used to increase the rank score for target documents
    must_match = {} #Validation fields after document retrieval
    should_match = {} #Optional fields after document retrieval
    group = {}
    for line in lines:
        line = line.strip()
        words = line.split(' ')
        if line.startswith('PREFIX'):
            continue
        if line.startswith('SELECT'):
            if "price" in line.lower():
                ans_field["price"] = "?price"
            elif "height" in line.lower():
                ans_field["height"] = "?height"
            elif "weight" in line.lower():
                ans_field["weight"] = "?weight"
            else:
                pattern = "\?([A-Za-z_]+)"
                fields = re.findall(pattern,line)
                if len(fields) == 2:
                    for item in fields:
                        if item != "ad":
                            ans_field[item] = "?"+item
                #else:
                #    item = fields[0]
                #    ans_field[item] = "?"+item
        if line.startswith('qpr:'):
            line = line[:-1].strip() #remove the punctuation at the end
            words = line.split(" ",1)
            if not words[1].startswith("?"): #Given conditions
                words[1] = words[1][1:-1]
                predicate = words[0][4:]
                constraint = words[1]
                if predicate == 'ethnicity':
                    if constraint in skin_color_list:
                        should_search['ethnicity'] = constraint
                    else:
                        if constraint.lower() not in extraction.continent_dic:
                            must_search['ethnicity'] = constraint
                        else:
                            should_search["ethnicity"] = constraint
                    must_match[predicate] = constraint
                # search directly
                elif predicate == 'phone':
                    words = query["question"].split()
                    if "number" in words: #retrieve the original phone format in the query
                        number_index = words.index("number")+1
                        if number_index < len(words) and re.findall("\d",words[number_index]):
                            phone = ""
                            while len(re.findall("\d",phone))<8:
                                phone += words[number_index]+" "
                                number_index += 1
                            must_search["phone"] = re.sub(r"[^\d\(\)\-\+ ]","",phone.strip())
                            must_match["phone"] = re.sub(r"[^\d\(\)\-\+ ]","",phone.strip())
                        else:
                            should_search['phone'] = constraint
                            must_match[predicate] = constraint
                            must_search[predicate] = constraint
                elif predicate == 'location':
                    location = constraint.split(',')
                    if location:
                        should_search['location'] = constraint
                        if len(location)>1:
                            if location[1].lower().capitalize() in extraction.nationality_list:
                                must_search['location'] = location[0]
                            else: #city
                                must_search["location"] = constraint
                        else:
                            must_search['location'] = location[0]
                        must_match['location'] = constraint
                elif predicate == 'multiple_providers':
                    should_search['multiple_providers'] = constraint
                    must_match[predicate] = constraint
                elif predicate == 'hair_color':
                    should_search['hair_color'] = constraint
                    must_match[predicate] = constraint
                    must_search[predicate] = constraint
                elif predicate == 'eye_color':
                    should_search['eye_color'] = constraint
                    must_match[predicate] = constraint
                    must_search[predicate] = constraint
                elif predicate == "height":
                    he = re.findall("\d",constraint)
                    if len(he) == 1:
                        must_search["height"] = he[0]+"'"
                        should_search["height"] = he[0]+"\""
                        must_match["height"] = he[0]+"'"
                    elif len(he) == 2:
                        must_search["height"] = he[0]+"'"+he[1]
                        must_match["height"] = he[0]+"'"+he[1]
                elif predicate == "post_date":
                    should_search["post_date"] = constraint
                    must_match["post_date"] = constraint
                # cluster query
                elif predicate == 'seed':
                    if "@" in constraint:
                        must_search['email'] = constraint
                        must_match['email'] = constraint
                    elif constraint.isdigit():
                        must_search['phone'] = constraint
                        must_match['phone'] = constraint
                else:
                    must_search[predicate] = constraint
                    must_match[predicate] = constraint # email, street_address, social_media_id, review_site_id, age, price, services, height, weight, post_date

        if line.startswith('GROUP BY'):
            ans_pattern = '(?:\?)([a-z]+)'
            for word in words:
                group_variable = re.findall(ans_pattern, word)
                group['group_by'] = group_variable
        if line.startswith('ORDER BY'):
            for word in words:
                if 'DESC' in word:
                    group['order_by'] = 'DESC'
                elif 'ASEC' in word:
                    group['order_by'] = 'ASEC'
        if line.startswith("LIMIT"):
            group["limit"] = int(line.split()[1])
        if line.startswith("FILTER"):
            filterPattern = "'(.*?)'"
            filter_constraint = re.findall(filterPattern, line)
            if filter_constraint:
                filter_constraint = filter_constraint[0]
            if "content" in line:
                must_search["content"] = filter_constraint
                must_match["content"] = filter_constraint
            elif "title" in line:
                must_search["title"] = filter_constraint
                must_match["title"] = filter_constraint

    parsed_dic["id"] = query["id"]
    parsed_dic["type"] = query["type"]
    parsed_dic['answer_field'] = ans_field
    parsed_dic['must_search_field'] = must_search
    parsed_dic['should_search_field'] = should_search
    parsed_dic['required_match_field'] = must_match
    parsed_dic['optional_match_field'] = should_match
    parsed_dic['group'] = group
    return parsed_dic


def query_body_build(parsed_query):
    """
    Build the query body for elasticsearch
    :param parsed_query: Dictionary
    :return: query body: Dictionary
    """
    must_list = []
    should_list = []
    must_not_list = []
    must_search_dic = parsed_query["must_search_field"]
    should_search_dic = parsed_query["should_search_field"]
    must_not_dic = parsed_query["must_not_field"]
    answer_field = parsed_query["answer_field"]
    for condition in must_search_dic:
        if condition == "phone" and not re.findall("\D",must_search_dic["phone"]):
            must_list.append(must_search_dic[condition][:3])
            must_list.append(must_search_dic[condition][3:6])
            must_list.append(must_search_dic[condition][6:])
            should_list.append(must_search_dic[condition][:3]+"-"+must_search_dic[condition][3:6]+"-"+must_search_dic[condition][6:])
            should_list.append("("+must_search_dic[condition][:3]+")"+must_search_dic[condition][3:6]+"-"+must_search_dic[condition][6:])
        elif condition == "posting_date":
            calendar = must_search_dic[condition].split("-")
            if len(calendar) == 3: #year,month,day are all included
                must_list.append(calendar[0])
                must_list.append(calendar[2])
            elif len(calendar) == 2:
                must_list.append(calendar[1])
        elif condition == "eye_color":
            must_list.append("eye")
        elif condition == "hair_color":
            must_list.append("hair")
        elif condition == "ethnicity":
            should_list.append("ethnicity")
        elif condition == "nationality":
            should_list.append("nationality")
        else:
            must_list.append(must_search_dic[condition])

    for condition in should_search_dic:
        should_list.append(should_search_dic[condition])

    feature_should_search_map = {"tattoos":"tattoo","name":"name","street_address":"address","age":"age","hair_color":"hair","eye_color":"eye","nationality":"nationality","ethnicity":"ethnicity","review_site_id":"review","email":"email","phone":"phone","location":"location","price":"","multiple_providers":"","social_media_id":"","services":"","height":"height","weight":"weight","post_date":"posted"}
    for field in answer_field:
        if feature_should_search_map[field]:
            should_list.append(feature_should_search_map[field])

    should_arr = []
    must_str = " AND ".join(must_list)
    for word in should_list:
        query_dic = {}
        query_dic["match"] = {}
        query_dic["match"]["extracted_text"] = word
        should_arr.append(query_dic)
    size = 3000 #number of documents retrieved from elasticsearch
    body = {"size":size,"query":{"bool":{"must":{"match":{"extracted_text": must_str}}, "should": should_arr}}}
    return body

def elastic_search(query_body,username = "",password = ""):
    """
    :param query_body: Dictionary
    :param username: String
    :param password: String
    :return:
    """
    es = Elasticsearch(
         ["https://memexproxy.com/es/dig-nov-eval-hg-01/"],
         http_auth=(username, password),
         port=9200,
         use_ssl=True,
         verify_certs = True,
         ca_certs=certifi.where(),
    )
    response = es.search(body=query_body,request_timeout=60)
    documents = response["hits"]["hits"]
    return documents

def annotation(text,query_id):
    """
    Using StanfordNER to annotate name entity(name, location, organization in this project)
    :param text: String, text to be annotated
    :param query_id: String
    :return: String, annotated text by StanfordNER
    """
    filename = "tmp"+query_id+".txt" #Stanford supports file input only, so text has to be saved into file
    with open(filename,"w") as f:
        f.write(text)
        shell_cmd = "java -mx5g -cp \"stanford-ner-2015-12-09/*:stanford-ner-2015-12-09/lib/*\" edu.stanford.nlp.ie.crf.CRFClassifier -loadClassifier stanford-ner-2015-12-09/classifiers/english.all.3class.distsim.crf.ser.gz -outputFormat inlineXML -textFile %s" % filename
        annotated_text = os.popen(shell_cmd).read()
        os.system("rm "+filename)
        return annotated_text

