__author__ = 'infosense'
import sys,json,datetime,os,re,collections
from datetime import datetime
from multiprocessing import Pool
import yaml
from fuzzywuzzy import fuzz
from bs4 import BeautifulSoup
#from pymongo import MongoClient
import search,extraction,ebola_html_dealer
from elasticsearch import Elasticsearch
import certifi


def main():
    reload(sys)
    sys.setdefaultencoding("utf-8")
    query_path = "post_point_fact.json"
    answer_path = "answer.json"
    query_list = search.query_retrival(query_path)
    query_list = filter(lambda k:k["id"] not in os.listdir("Annotated_GT_PF/"),query_list)
    # f = open("parsed_queries","w")
    # for query in query_list:
    #     json.dump(search.query_parse(query),f)
    #     f.write("\n")
    # aggregate = filter(lambda k:k["type"] == "aggregate",query_list)
    # aggregate = filter(lambda k:k["id"] == "1223.11",aggregate)
    #global db
    # pool = Pool()
    # pool.map(pipeline,query_list)
    for query in query_list:
        ans = pipeline(query)
        if len(ans["answers"]) == 0:
            ans = pipeline(query,False)
        filepath = "Annotated_GT_PF/"+query["id"]
        f = open(filepath,"w")
        json.dump(ans,f)
        f.close()


def createIndex(index,type,es,doc):
    malpath = "mal.json"
    doc_id = doc["_id"]
    del doc["_id"]
    try:
        res = es.index(index=index, doc_type=type, id=doc_id, body=doc)
    except:
        doc["id"] = doc_id
        mal = open(malpath,"a")
        json.dump(doc,mal)
        mal.write("\n")
        mal.close()

def index(index_name):
    start = datetime.now()
    GT_path = "/Users/infosense/Desktop/Index/GT/12.json"
    # for file in os.listdir(GT_path):
    #     if not file.startswith("."):
    #path = os.path.join(GT_path,file)
    path = GT_path
    input = open(path)
    lines = input.readlines()
    input.close()
    for line in lines:
        document = json.loads(line)
        es = Elasticsearch()
        createIndex(index_name,document["content_type"],es,document)
    print((datetime.now()-start).seconds)

def TLD_specific_search(document):
    TLD = extraction.top_level_domain_pattern(document)
    raw_content = extraction.get_raw_content(document)
    if TLD and raw_content:
        soup = BeautifulSoup(raw_content, 'html.parser')
        content = ""
        if TLD == "escortcafe.com":
            content = soup.find_all("div", class_="details")
        elif TLD == "classifriedads.com":
            content = soup.find_all(id="contentcell")
        elif TLD == "slixa.com":
            content = soup.find_all("div", class_="span9 profile-content") + soup.find_all("aside", class_="profile-sidebar span3")
        # elif TLD == "allsexyescort.com":
        elif TLD == "escort-ads.com":
            content = soup.findall("div", class_="container main-content vip-content")
        # elif TLD == "liveescortreviews.com":
        # elif TLD == "escort-europe.com":
        elif TLD == "find-escorts.com":
            content = soup.findall(id="contentcell")
        elif TLD == "escortserv.com":
            content = soup.findall(id="index")
        elif TLD == "slixa.ca":
            content = soup.find_all("div", class_="span9 profile-content") + soup.find_all("aside", class_="profile-sidebar span3")
        elif TLD == "escortpost.com":
            content = soup.findall(id="content")
        elif TLD == "privateescorts.ro":
            content = soup.findall("tbody")
        elif TLD == "adultsearch.com":
            content = soup.findall(id="ad")
        return str(content)
    else:
        return ""

def pipeline(query,tense=True):
    #client = MongoClient()
    #db = client.database
    start = datetime.now()
    answer_dic = []
    #if query["type"] == "aggregate" and query["id"] == "1223.12":
        #print(query)
    # filepath = "pointfact_test/"+query["id"]
    parsed_query_dic = search.query_parse(query)
    #print(parsed_query_dic)
    result = []
    if query["type"] == "Cluster Identification" or query["type"] == "Cluster Facet":
        result = cluster(query,5)
    else:
        query_body = search.query_body_build(parsed_query_dic)
        print(parsed_query_dic)
        print(query_body)
        documents = search.elastic_search(query_body)
        print(len(documents))
        for i in range(len(documents)):
            TLD =  TLD_specific_search(documents[i])
            if TLD:
                documents[i]["TLD"] = TLD
            if validate(documents[i],parsed_query_dic,tense):
                # print(documents[i]["_id"])
                answer = answer_extraction(documents[i],parsed_query_dic)
                if answer:
                    dic = {}
                    dic["id"] = documents[i]["_id"]
                    dic["validation_score"] = documents[i]["validation_score"]
                    dic["els_score"] = documents[i]["_score"]
                    dic["answer"] = answer
                    result.append(dic)
    final_result = generate_formal_answer(query,result)
    return final_result


def annotator(documents,query_id):
    """
    :param documents: List:The documents retrieved for each query
    :return: tuple(a,b) a:List of annotated raw_content  b:List of annotated extracted_text
    """
    #print(datetime.datetime.now())
    para_size = 300 #how many documents are annotated every time
    para_num,remainder = divmod(len(documents),para_size)
    if remainder:
        para_num += 1
    separator = "wjxseparator" #used to join raw_content from different documents, combine them and annotate at one time
    indexed_raw_result = []
    indexed_clean_result = []
    for i in range(para_num):
        raw_contents = []
        clean_contents = []
        for document in documents[i*para_size:(i+1)*para_size]:
            raw_content = document["_source"]["raw_content"]
            raw_contents.append(raw_content)
            clean_content = ""
            if "extracted_text" in document["_source"] and document["_source"]["extracted_text"]:
                clean_content = document["_source"]["extracted_text"]
            else:
                clean_content = ebola_html_dealer.make_clean_html(raw_content)
            clean_contents.append(clean_content)
        raw_indexed = search.annotation(separator.join(raw_contents),query_id)
        clean_indexed = search.annotation(separator.join(clean_contents),query_id)
        indexed_raw_result += raw_indexed.split(separator)
        indexed_clean_result += clean_indexed.split(separator)
        print(i)
    return (indexed_raw_result,indexed_clean_result)
    #print(datetime.datetime.now())

def modify_query(parsed_query, field, seed):  # Already test
    new_query = parsed_query.copy()
    connected_field = ["email", "phone"]
    for connect in connected_field:
        if connect in new_query["must_search_field"]:
            del new_query["must_search_field"][connect]
    new_query["must_search_field"][field] = seed
    return new_query

def cluster(query, search_round):
    need_to_search = []
    res = []
    searched_email = []
    searched_phone = []
    searched_address = []
    searched_ads = []
    ########## Base search ##############
    parsed_query = search.query_parse(query)
    #print(parsed_query)
    parsed_must_field = parsed_query["must_search_field"]
    if "email" in parsed_must_field:
        searched_email.append(parsed_must_field["email"])
    if "phone" in parsed_must_field:
        searched_phone.append(parsed_must_field["phone"])
    if "address" in parsed_must_field:
        searched_address.append(parsed_must_field["address"])
    query_body = search.query_body_build(parsed_query)
    # print query_body
    search_result = search.elastic_search(query_body)
    # print search_result
    dicts = build_dictionary(search_result, parsed_query, searched_ads)
    if dicts:
        need_to_search.extend(dicts)
    ########### Rounds search #############
    i = 1
    while i < search_round:
        if need_to_search:
            for j in range(len(need_to_search)):     # seed ads list in this round
                # for item in need_to_search[j]:			# Each ads
                email_to_search = []
                phone_to_search = []
                address_to_search = []
                ad_id,value = need_to_search[0].items()[0]
                #print value
                if "email" in value:
                    j_email = list(set(value["email"]))
                    #print(j_email)
                    if j_email:
                        for email in j_email:
                            if email not in searched_email:
                                email_to_search.append(email)
                        for email in email_to_search:
                            new_query = modify_query(parsed_query, "email", email)
                            #print parsed_query, new_query
                            email_query_body = search.query_body_build(new_query)
                            email_search_result = search.elastic_search(email_query_body)
                            new_dicts = build_dictionary(email_search_result, new_query, searched_ads)
                            if new_dicts:
                                need_to_search.extend(new_dicts)
                            searched_email.append(email)
                if "phone" in value:
                    j_phone = list(set(value["email"]))
                    #print(j_phone)
                    if j_phone:
                        for phone in j_phone:
                            if phone not in phone_to_search:
                                phone_to_search.append(phone)
                        for phone in phone_to_search:
                            new_query = modify_query(parsed_query, "phone", phone)
                            #print parsed_query, new_query
                            phone_query_body = search.query_body_build(new_query)
                            phone_search_result = search.elastic_search(phone_query_body)
                            new_dicts = build_dictionary(phone_search_result, new_query, searched_ads)
                            if new_dicts:
                                need_to_search.extend(new_dicts)
                            searched_phone.append(phone)
                if "address" in value:
                    j_address = list(set(value["address"]))
                    #print(j_address)
                    if j_address:
                        for add in j_address:
                            for searched in searched_address:
                                if fuzz.ratio(add, searched) < 80:
                                    address_to_search.append(add)
                        for add in address_to_search:
                            new_query = modify_query(parsed_query, "address", add)
                            # print parsed_query, new_query
                            address_query_body = search.query_body_build(new_query)
                            add_search_result = search.elastic_search(address_query_body)
                            new_dicts = build_dictionary(add_search_result, new_query, searched_ads)
                            if new_dicts:
                                need_to_search.extend(new_dicts)
                            searched_address.append(add)
                res.append(need_to_search.pop(0))
        i += 1
    return res

def build_dictionary(documents, parsed_query_dic, searched_ads):
    annotated_raw_contents = []
    annotated_clean_contents = []
    if "location" in parsed_query_dic["answer_field"] or "name" in parsed_query_dic["answer_field"]:
        annotated_raw_contents,annotated_clean_contents = annotator(documents,parsed_query_dic["id"])
    functionDic = extraction.functionDic
    dicts = []
    for i in range(len(documents)):
        dic = {}
        adID = documents[i]["_id"]
        if "location" in parsed_query_dic["answer_field"] or "name" in parsed_query_dic["answer_field"]:
            documents[i]["annotated_raw_content"] = annotated_raw_contents[i]
            documents[i]["annotated_clean_content"] = annotated_clean_contents[i]
        if adID not in searched_ads:
            searched_ads.append(adID)
            extracted_text = extraction.get_text(documents[i])
            if validate(documents[i], parsed_query_dic,True):
                # print("Pass validation")
                email = list(set(extraction.email_recognition(documents[i],True,False)))
                phone = list(set(extraction.phone_recognition(documents[i],True,False)))
                address = list(set(extraction.address_recognition(documents[i],True,False)))
                dic[adID] = {}
                if parsed_query_dic["type"] == "Cluster Facet":
                    if len(parsed_query_dic["answer_field"]) == 0:
                        answer = answer_extraction(documents[i],parsed_query_dic)
                        if answer:
                            dic[adID]["answer"] = answer
                        else:
                            continue
                dic[adID]["email"] = email
                dic[adID]["phone"] = phone
                dic[adID]["address"] = address
                dic[adID]["validation_score"] = documents[i]["validation_score"]
                dic[adID]["els_score"] = documents[i]["_score"]
                dicts.append(dic)
    return dicts

def generate_formal_answer(query,result):
    final_result = {}
    final_result["question_id"] = query["id"]
    candidates = []
    parsed_query_dic = search.query_parse(query)
    #print(result)
    if query["type"] == "Cluster Identification":
        for item in result:
            document_id = item.keys()[0]
            score = item[document_id]["validation_score"]
            candidates.append((document_id,score))
        candidates.sort(key = lambda k:k[1],reverse = True)
        threhold = 0.5
        thr_res = filter(lambda k:k[1]>threhold,candidates)
        if len(thr_res) == 0 and candidates:
            final_result["answers"] = candidates[:len(candidates)/2+1]
        else:
            final_result["answers"] = filter(lambda k:k[1]>threhold,candidates)
    elif query["type"] == "Cluster Facet":
        for item in result:
            document_id = item.keys()[0]
            for ans in item[document_id]["answer"]:
                answer_text = ans[0]
                score = (1-ans[1])*item[document_id]["validation_score"]
                candidates.append((answer_text,document_id,score))
        candidates.sort(key = lambda k:k[2],reverse = True)
        threhold = 0.5
        thr_res = filter(lambda k:k[2]>threhold,candidates)
        if len(thr_res) == 0 and candidates:
            final_result["answers"] = candidates[:len(candidates)/2+1]
        else:
            final_result["answers"] = filter(lambda k:k[2]>threhold,candidates)
    elif query["type"] == "Point Fact":
        #print(result)
        for item in result: #Currently pick the most relavant answer in each document
            document_id = item["id"]
            for answer in item["answer"]:
                answer_text = answer[0] #Currently pick the most relavant answer in each document
                score  = (1-item["answer"][0][1])*item["validation_score"]
                candidates.append((answer_text,document_id,score))
        candidates.sort(key = lambda k:k[2],reverse = True)
        threhold = 0.5
        thr_res = filter(lambda k:k[2]>threhold,candidates)
        if len(thr_res) == 0 and candidates:
            final_result["answers"] = candidates[:len(candidates)/2+1]
        else:
            final_result["answers"] = filter(lambda k:k[2]>threhold,candidates)
    else:
        if not result:
            final_result["answers"] = []
            return final_result
        for item in result:
            document_id = item["id"]
            for candi in item["answer"]:
                answer_text = candi[0]
                score  = (1-item["answer"][0][1])*item["validation_score"]
                candidates.append((answer_text,document_id,score))
        candidates.sort(key = lambda k:k[2],reverse = True)
        type_value = []
        threhold = 0.5
        if "price" in parsed_query_dic["answer_field"]:
            for i in range(len(candidates)):
                price_text = candidates[i][0]
                prices = re.findall("\d+",price_text)
                priceCounter = collections.Counter(prices)
                most_common_price = int(max(priceCounter,key=priceCounter.get))
                candidates[i] = (candidates[i][0],candidates[i][1],candidates[i][2],most_common_price)
        if query["type"] == "MODE":
            value_counter = collections.Counter()
            if "price" in parsed_query_dic["answer_field"]:
                value_counter = collections.Counter(k[3] for k in candidates)
            else:
                value_counter = collections.Counter(k[0] for k in candidates)
            if parsed_query_dic["group"]["order_by"] == "DESC":
                value_list = value_counter.items()
                value_list.sort(key = lambda k:k[1],reverse = True)
                type_value = value_list[:parsed_query_dic["group"]["limit"]]
                if "price" in parsed_query_dic["answer_field"]:
                    final_result["answers"] = type_value+map(lambda k:(k[0],k[1],k[2]),filter(lambda k:k[2]>threhold,candidates))
                else:
                    final_result["answers"] = type_value+filter(lambda k:k[2]>threhold,candidates)
            else:
                value_list = value_counter
                value_list.sort(key = lambda k:k[1],reverse = True)
                type_value = value_list[:parsed_query_dic["group"]["limit"]]
                if "price" in parsed_query_dic["answer_field"]:
                    final_result["answers"] = type_value+map(lambda k:(k[0],k[1],k[2]),filter(lambda k:k[2]>threhold,candidates))
                else:
                    final_result["answers"] = type_value+filter(lambda k:k[2]>threhold,candidates)
        else:
            if "price" in parsed_query_dic["answer_field"]:
                candidates.sort(key = lambda k:k[3], reverse = True)
            else:
                candidates.sort(key = lambda k:k[0], reverse = True)
            threhold = 0.5
            if type == "MIN":
                type_value = candidates[0][0]
            elif type == "MAX":
                type_value = candidates[-1][0]
            elif type == "AVG":
                if "price" in parsed_query_dic["answer_field"]:
                    type_value = sum(k[3] for k in candidates)/len(candidates)
                else:
                    type_value = sum(k[0] for k in candidates)/len(candidates)
            candidates.sort(key = lambda k:k[2],reverse = True)
            final_result["answers"] = type_value+ map(lambda k:(k[0],k[1],k[2]),filter(lambda k:k[2]>threhold,candidates))
    return final_result


def clarify(document,feature,is_raw_content): #Calculate the character distance between target feature and clarify_list feature
    clarify_list = ["phone","hair_color","eye_color","height","weight","services"]
    clarify_result = []
    candidates = []
    if feature == "name" or feature == "location":
        candidates = [(document["_source"][feature+"_position"][i],document["_source"][feature][i]) for i in range(len(document["_source"][feature]))]
    else:
        candidates = extraction.functionDic[feature](document,is_raw_content,True)
    for func in clarify_list:
        if feature != func:
            ex_ans = extraction.functionDic[func](document,is_raw_content,True)
            if ex_ans:
                clarify_result.append(ex_ans)
    scores = {}
    if len(clarify_result) == 0:
        for candidate in candidates:
            scores[candidate[1]] = 1
        return scores
    for candidate in candidates:
        score = 0
        for item in clarify_result:
            for result in item:
                score += abs((candidate[0]-result[0])/len(item))
        if candidate[1] not in scores:
            scores[candidate[1]] = score/len(clarify_result)
        else:
            scores[candidate[1]] = min(scores[candidate[1]],score/len(clarify_result))
    return scores


def get_cluster_seed(query):
    clauses = query["where"]["clauses"]
    for clause in clauses:
        if clause["predicate"] == "seed":
            return clause["constraint"]

def answer_extraction(document,parsed_query_dic):
    """
    :param document: Dictionary
    :param parsed_query_dic: Dictionary
    :return: list[(answer,score)]: all the possible answers associated with given document
    """
    extraction_result = []
    answer_field = parsed_query_dic["answer_field"].keys()
    if answer_field:
        feature = answer_field[0] #only one attibutue will be questioned
    else:
        return []
    if feature == "tattoos":
        return []
    raw_result = []
    result = []
    if feature == "name" or feature == "location":
        raw_result = document["_source"][feature]
        result = document["_source"][feature]
    else:
        raw_result = extraction.functionDic[feature](document,True,False) #answer from raw_content
        result = extraction.functionDic[feature](document,False,False) #answer from extracted_text
    if result and raw_result:
        intersection = list(set(raw_result) & set(result)) #return those results that are both in the raw_content and extracted_text
        if intersection:
            if len(intersection) == 1: #If there is only one answer, it should be 0.0
                extraction_result = [(intersection[0],0.0)]
            else:
                extracted_position_result = clarify(document,feature,False)
                overlap = []
                # print("position")
                # print(extracted_position_result)
                for item in extracted_position_result:
                    if type(item) is str:
                        intersection_keys = map(lambda k:k.lower(),intersection)
                        if item.lower() in intersection_keys:
                            overlap.append((item,extracted_position_result[item]))
                    else:
                        if item in intersection:
                            overlap.append((item,extracted_position_result[item]))
                extraction_result = overlap
        #         print("extraction")
        #         print(extraction_result)
        # else: #If there is not overlap between raw content result and extracted result, use extracted result.
            if len(set(result)) == 1:
                extraction_result = [(result[0],0.0)]
            else:
                extraction_result = clarify(document,feature,False).items()
    else:
        if result:
            if len(set(result)) == 1:
                extraction_result = [(result[0],0.0)]
            else:
                extraction_result = clarify(document,feature,False).items()
        if raw_result:
            if len(set(raw_result)) == 1:
                extraction_result = [(raw_result[0],0.0)]
            else:
                extraction_result = clarify(document,feature,True).items()
    return extraction_result

def validate(document, parsed_query,tense): # Need to write
    """
    :param document: Dictionary
    :param parsed_query: Dictionary: Parsed query in dictionary format providing validation fields
    :param tense: Bool: validate mode(tense or loose)
    :return: Bool: If the document satisfies the required conditions in query
    """
    raw_content = extraction.get_raw_content(document)
    lower_raw_content = raw_content.lower()
    extract_text = extraction.get_text(document)
    lower_extract_text = extract_text.lower()
    matchword = parsed_query["required_match_field"]  #Validation fields
    #if document["_id"] == "17E9B1E77C39D0D688A125B1E051C6F35823D26AD5DBC51B67D97BB5A30DF245":
        #print(matchword)
    validate_count = 0
    for feature in matchword:
        isValid = False
        #Check first if the feature value in string or list
        if type(matchword[feature]) is list: #Haven't figure out what values would be a list
            for value in matchword[feature]:
                if value.lower() in lower_raw_content or value.lower() in lower_extract_text: #Either in the raw_content or extract_text is regarded as valid
                    isValid = True
                    break
        else:
            if feature == "location":
                location_fields = [field.strip() for field in matchword[feature].split(",")]
                for location_field in location_fields:
                    if location_field in extraction.state_abbr_dic: #Validate state should be case sensitive
                        state_pattern = r"(?:[^A-Za-z])("+location_field+")(?:[^A-Za-z])"
                        if re.search(state_pattern,raw_content) or re.search(state_pattern,extract_text) or extraction.state_abbr_dic[location_field].lower() in lower_extract_text or extraction.state_abbr_dic[location_field].lower() in lower_raw_content: #Check if a state abbr or its full name is in raw_content or extracted_text field
                            isValid = True
                    else:
                        if location_field.lower() in lower_raw_content or location_field.lower() in lower_extract_text:
                            isValid = True
            elif feature == "title" or feature == "content":
                if matchword[feature] in re.sub("[^\s\w]","",lower_raw_content) or matchword[feature] in re.sub("[^\s\w]","",lower_extract_text):
                    isValid = True
            else:
                if feature == "ethnicity" and matchword[feature].lower() in extraction.continent_dic:
                    for country in extraction.continent_dic[matchword[feature].lower()]:
                        if country.lower() in lower_raw_content or country.lower() in lower_extract_text:
                            isValid = True
                else:
                    if matchword[feature].lower() in lower_raw_content or matchword[feature].lower() in lower_extract_text:
                        isValid = True
        if isValid:
            validate_count += 1
            continue

        if feature in ["name","location","multipl_providers"]: #If given feature is in this list and can not be found by string matching, the time-consuming annotation can hardly extract as well.
            if tense:
                return False
            else:
                continue
        results = extraction.functionDic[feature](document,False,False) #Extracted result
        for result in results:
            if feature == "phone": #phone number has to be exactly the same while other features tolerate some minor difference
                if result == re.sub("\D","",matchword[feature]):
                    isValid = True
                    break
            else:
                if fuzz.ratio(str(result).lower(),matchword[feature].lower())>=80:
                    isValid = True
                    break

        #If not found in extracted text, go ahead searching in raw_content
        if not isValid:
            results = extraction.functionDic[feature](document,True,False)
            for result in results:
                if feature == "phone": #phone number has to be exactly the same while other features tolerate some minor difference
                    if result == re.sub("\D","",matchword[feature]):
                        isValid = True
                        break
                else:
                    if fuzz.ratio(str(result).lower(),matchword[feature].lower())>=80:
                        isValid = True
                        break
        if isValid:
            validate_count += 1
            continue
        else:
            if tense:
                return False
            else:
                continue
    document["validation_score"] = validate_count*1.0/len(matchword)
    if validate_count>0:
        return True
    else:
        return False

if __name__ == "__main__":
    main()

