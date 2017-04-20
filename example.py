from fuzzywuzzy import fuzz
from elasticsearch import Elasticsearch
import phonenumbers,certifi
import extraction
import re,json
def phone_recognition(text,country_abbr_list):
    result = []
    for country in country_abbr_list:
        for match in phonenumbers.PhoneNumberMatcher(text,country):
            if match.raw_string not in result:
                result.append(match.raw_string)
    for i in range(len(result)):
        result[i] = re.sub(r"\D","",result[i])
    return list(set(result))

def retrieveDocument(id):
    es = Elasticsearch(
        ['https://cdr-es.istresearch.com:9200/memex-qpr-cp4-2'],
        http_auth=('cdr-memex', '5OaYUNBhjO68O7Pn'),
        port=9200,
        use_ssl=True,
        verify_certs = True,
        ca_certs=certifi.where(),
    )
    query_body = {
       "query": {
           "bool": {
            "must": {
              "match":{
                  "_id":id
              }
          }
        }
       }
    }
    response = es.search(body=query_body,request_timeout=60)
    document = response["hits"]["hits"][0]
    return document

def validate(document, parsed_query): # Need to write
    raw_content = extraction.get_raw_content(document)
    extract_text = extraction.get_text(document)
    matchword = parsed_query["required_match_field"]  #Validation fields
    lower_raw_content = raw_content.lower()
    lower_extract_text = extract_text.lower()
    for feature in matchword:
        isValid = False
        #Check first if the feature value in text or not
        if type(matchword[feature]) is list:
            for value in matchword[feature]:
                if value.lower() in lower_raw_content or value.lower() in lower_extract_text: #Either in the raw_content or extract_text is regarded as valid
                    isValid = True
                    break
        else:
            if feature == "location": #Special case for location which has two fields(city and state) in value
                location_fields = [field.strip() for field in matchword[feature].split(",")]
                for location_field in location_fields:
                    if location_field in state_abbr_dic: #Validate state should be case sensitive
                        state_pattern = r"(?:[^A-Za-z])("+location_field+")(?:[^A-Za-z])"
                        if re.search(state_pattern,raw_content) or re.search(state_pattern,extract_text) or state_abbr_dic[location_field].lower() in lower_extract_text or state_abbr_dic[location_field].lower in lower_raw_content: #Check if a state abbr or its full name is in raw_content or extracted_text field
                            isValid = True
                    else:
                        if location_field.lower() in lower_raw_content or location_field.lower() in lower_extract_text:
                            isValid = True
            else:
                if matchword[feature].lower() in lower_raw_content or matchword[feature].lower() in lower_extract_text:
                    isValid = True
        if isValid:
            continue
        #If the document does not contain the raw string, do extractions and match
        results = extraction.functionDic[feature](document,True)
        for result in results:
            if feature == "phone": #phone number has to be exactly the same while other features tolerate some minor difference
                if result == re.sub("\D","",matchword[feature]):
                    isValid = True
            else:
                if fuzz.ratio(str(result),matchword[feature])>=80:
                    isValid = True
                    break
        if extract_text:
            results = extraction.functionDic[feature](document,False)
            for result in results:
                if feature == "phone": #phone number has to be exactly the same while other features tolerate some minor difference
                    if result == re.sub("\D","",matchword[feature]):
                        isValid = True
                else:
                    if fuzz.ratio(str(result),matchword[feature])>=80:
                        isValid = True
                        break
        if isValid:
            continue
        else:
            return False
    return True

state_abbr_path = "state_abbr"
parsed_query_dic = {'must_search_field': {'phone': '7022187871', 'eye_color': 'hair'}, 'optional_match_field': {}, 'required_match_field': {'phone': '7022187871'}, 'must_not_field': {}, 'should_search_field': {}, 'answer_field': {'eye_color': '?eye_color'}}
w = open(state_abbr_path)
state_abbr_dic = json.load(w)
w.close()
id = "10B2D00F4DA89DFF78483926BAB7B2A70B1AAB080C513CEB00C9AF315FC5CFE3"
print(validate(retrieveDocument(id),parsed_query_dic))