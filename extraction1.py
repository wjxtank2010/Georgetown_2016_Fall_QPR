# -*- coding: utf-8 -*-
import re,sys,json,yaml,os,webcolors,search
from fuzzywuzzy import fuzz
from nltk.corpus import stopwords
from datetime import date,timedelta
import ebola_html_dealer as html_cleaner
import phonenumbers


def get_text(document):
    if "extracted_text" in document["_source"]:
        extract_text = document["_source"]["extracted_text"]
        if extract_text:
            return extract_text
    try:
        extract_text = html_cleaner.make_clean_html(get_raw_content(document))
    except Exception as e:
        extract_text = ""
    document["_source"]["extracted_text"] = extract_text
    return extract_text

def get_raw_content(document):
    return document["_source"]["raw_content"]

#Feature_list [1:is_extract_text,2:is_meta_data,3:raw_content_match percentage, 4:extracted_text_match percentage 5:meta_data_match percentage
#6:raw_content_len, 7:extract_len, 8:match_frequency, 9:elastic_score, 10:raw_content_ave_distance, 11:extract_text_ave_dis
def is_extract_text(document):
    if get_text(document):
        return 1
    else:
        return 0

def is_metadata(document): #extraction from elastic search
    if "extracted_metadata" in document["_source"]:
        return 1
    else:
        return 0

def raw_content_length(document):
    if "raw_content" in document["_source"]:
        return len(document["_source"]["raw_content"].split())
    else:
        return 0

def extract_content_length(document):
    return len(get_text(document).split())

def elastic_score(document):
    return document["_score"]

def generate_feature_score(document):
    feature = {}
    feature[1] = is_extract_text(document)
    feature[2] = is_metadata(document)
    feature[3] = document["raw_content_percentage"]
    feature[4] = document["extract_text_percentage"]
    feature[5] = document["meta_text_percentage"]
    feature[6] = raw_content_length(document)
    feature[7] = extract_content_length(document)
    feature[8] = document["match_frequency"]
    #feature[9] = elastic_score(document)
    return feature

def write_feature_score(feature_dic,query_id,document_id):
    feature = "qid:"+document_id+" "
    #print(feature_dic)
    for i in range(len(feature_dic)):
        feature += str(i+1)+":"+str(feature_dic[i+1])+" "
    feature += "#docid = "+document_id
    return feature

#extraction
#features: phone,email,street address, social media ID, review site ID, name, location, age, nationality/Ethnicity, price, tattoos, multiple provides, hair color, services, height, weight, eyecolor

def phone_recognition(document,is_raw_content): #retrieve distinct phone number
    """
    :param document:Dictionary
    :param is_raw_content: Boolean
    :return: List[str] containing all the distinct phone number in raw_content or extracted_text
    """
    text = ""
    if is_raw_content:
        text = get_raw_content(document)
    else:
        text = get_text(document)
    result = []
    number_pattern = r"(?:^|\D)([0-9]{3})[^A-Za-z0-9]{0,2}([0-9]{3})[^A-Za-z0-9]{0,2}([0-9]{3,6})(?:\D|$)" #Mainly retrieve national phone numbers
    text_result = re.findall(number_pattern,text)
    for item in text_result:
        result.append("".join(item))
    inter_phone_pattern = r"(?:^|\D)\+?(\d{2})[ -_]?(\d{9,10})(?:$|\D)" #Retrieve international phone numebrs with regional number at the beginning.
    inter_phone_pattern_result = re.findall(inter_phone_pattern,text)
    for item in inter_phone_pattern_result:
        result.append("".join(item))
    return list(set(result))
    # result = []
    # for country in country_abbr_list:
    #     for match in phonenumbers.PhoneNumberMatcher(text,country):
    #         if match.raw_string not in result:
    #             result.append(match.raw_string)
    # for i in range(len(result)):
    #     result[i] = re.sub(r"[\D]","",result[i])
    #return list(set(result))


def email_recognition(document,is_raw_content):
    text = ""
    if is_raw_content:
        text = get_raw_content(document)
    else:
        text = get_text(document)
    regex = re.compile(("([a-z0-9!#$%&'*+\/=?^_`{|}~-]+(?:\.[a-z0-9!#$%&'*+\/=?^_`"
                    "{|}~-]+)*(@|\sat\s)(?:[a-z0-9](?:[a-z0-9-]*[a-z0-9])?(\.|"
                    "\sdot\s))+[a-z0-9](?:[a-z0-9-]*[a-z0-9])?)"))
    result = []
    text_result = re.findall(regex,text)
    for email in text_result:
        if not email[0].startswith('//'):
            result.append(email[0].lower())
    return result

def address_recognition(document,is_raw_content):
    text = ""
    if is_raw_content:
        text = get_raw_content(document)
    else:
        text = get_text(document)
    text_without_quotation = re.sub(r'[^\w\s]','',text)
    streetNumber = "([1-9][0-9]{1,3} )"
    nsew = "(((N|S|E|W|North|South|East|West|NW|NE|SW|SE) )?)"
    nsewString = "North|South|East|West|NW|NE|SW|SE|"
    streetTypeString = "Street|St|ST|Boulevard|Blvd|Lane|Ln|Road|Rd|Avenue|Ave|Circle|Cir|Cove|Cv|Drive|Dr|Parkway|Pkwy|Court|Ct|Square|Sq|Loop|Lp|"
    roomString = "Suite|suite|Ste|ste|Apt|apt|Apartment|apartment|Room|room|Rm|rm|#|suitenumber"
    streetName_pattern1 = r"(((?!(?:"+nsewString+streetTypeString+roomString+r")\b)[A-Z][a-z]+(?: (?!(?:"+nsewString+streetTypeString+roomString+r")\b)[A-Z][a-z]+){0,2})|((\d+)(st|ST|nd|ND|rd|RD|th|TH)))"
    #streetName_pattern2 = r"((\d+)(st|ST|nd|ND|rd|RD|th|TH))"
    streetName = streetName_pattern1 #+ "|" + streetName_pattern2
    #streetName = "((?!(?:Apt)\b)[A-Z][a-z]+(?: (?!(?:Apt)\b)[A-Z][a-z]+){0,2})"
    streetType = "((Street|St|ST|Boulevard|Blvd|Lane|Ln|Road|Rd|Avenue|Ave|Circle|Cir|Cove|Cv|Drive|Dr|Parkway|Pkwy|Court|Ct|Square|Sq|Loop|Lp) )?"
    room = "(((Suite|suite|Ste|ste|Apt|apt|Apartment|apartment|Room|room|Rm|rm|#|suitenumber) ([0-9]{1,4}([A-Za-z]?)) )?)"
    city_state = "((((([A-Z][a-z]+)|([A-Z]+)) ){1,2}[A-Z]{2} )?)"
    zip_code = "([0-9]{5} )?"
    addree_pattern = re.compile(r"("+streetNumber+nsew+streetName_pattern1+" "+streetType+nsew+room+city_state+zip_code+")")
    text_result= re.findall(addree_pattern,text_without_quotation)
    result = []
    for item in text_result:
        address_parts = item[0].split()
        if len(address_parts)>2:   #although only street number and streeName are required in the pattern, address consists of at least three parts.
            isValid = False
            for part in address_parts:
                if part.lower() in streetTypeString.lower() or part.lower() in nsew.lower():
                    isValid = True
            if isValid:
                result.append(result_normalize(item[0]))
    return result

def social_media_id_recognition(document,is_raw_content):
    """
    :param document:
    :param is_raw_content:
    :return: a list containing all the social media ID
    """
    social_media_list = ["facebook","instagram","twitter"]
    text = ""
    result = []
    if is_raw_content:
        text = get_raw_content(document)
    else:
        text = get_text(document)
    media_str = "|".join(social_media_list)
    #extract social media ID in a url
    url_media_pattern = r"(%s).com/(.*)/"%media_str
    url_media_pattern_result = re.findall(url_media_pattern,text)
    for item in url_media_pattern_result:
        result.append(item[0]+"@"+item[1])
    #extract social media ID in plain text
    plain_text_pattern = r"(%s): (\w+)\W"
    plain_text_pattern_result = re.findall(plain_text_pattern,text)
    for item in plain_text_pattern_result:
        result.append(item[0]+"@"+item[1])
    return result


def review_site_recognition(document,is_raw_content):
    #url_pattern = re.compile(r'(http[s]?://)|(www.)(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\(\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+')
    text = ""
    if is_raw_content:
        text = get_raw_content(document)
    else:
        text = get_text(document)
    review_site_list = ["eccie", "TER", "preferred411"]
    review_site = []
    hyperlinks = hyperlink_recognition(document,is_raw_content)
    if hyperlinks:
        for link in hyperlinks:
            for site in review_site_list:
                if site in link:
                    if site == "eccie.net":
                        site = "eccie"
                    if site == "theeroticreview":
                        site = "TER"
                    review_site.append(site)
    return review_site

def name_recognition(document,is_raw_content):
    annotated_text = ""
    if is_raw_content:
        annotated_text = document["annotated_raw_content"]
    else:
        annotated_text = document["annotated_clean_content"]
    name_pattern = re.compile(r"\<PERSON\>(.*?)\</PERSON>")
    name_pattern_result = re.findall(name_pattern,annotated_text)
    result = []
    if len(name_pattern_result)>0:
        for item in name_pattern_result:
            result.append(result_normalize(item))
    return result

def location_recognition(document,is_raw_content):
    # text = ""
    # if is_raw_content:
    #     text = get_raw_content(document)
    # else:
    #     text = get_text(document)
    annotated_text = ""
    if is_raw_content:
        annotated_text = document["annotated_raw_content"]
    else:
        annotated_text = document["annotated_clean_content"]
    location_arr = re.findall(r"\<LOCATION\>(.*?)\</LOCATION\>",annotated_text)
    #print(document)
    result = []
    # if len(location_arr) == 0:
    #     state_pattern = re.compile(r"in ([A-Z]{2})")
    #     state_pattern_result = re.findall(state_pattern,document)
    #     if len(state_pattern_result)>0:
    #         start_index = 0
    #         for item in state_pattern_result:
    #             str_index = document[start_index:].index(item)
    #             subdocument = document[:str_index]
    #             word_index = len(subdocument.split())
    #             result.append(word_index)
    #             start_index = start_index+str_index+len(item)
    if len(location_arr) > 0:
        # words = annotated_text.split()
        # for i in range(len(words)):
        #     if "<LOCATION>" in words[i]:
        #         result.append(i)
        for location in location_arr:
            result.append(result_normalize(location))
    #print(result)
    return result

def age_recognition(document,is_raw_content):
    text = ""
    if is_raw_content:
        text = get_raw_content(document)
    else:
        text = get_text(document)
    age_pattern = r"(?:^|\D)([1-6]\d)(?:\D|$)"
    words = re.sub(r'[^\w\s]',' ',text).split()
    result = []
    match_range = 5
    pre_match_words = ["i","am","this","age","aged","my"]
    post_match_words = ["year","years","old","yrs"]
    for i in range(len(words)):
        tmp = re.findall(age_pattern,words[i])
        if len(tmp)>0:  #check if the words appear around the age_pattern indicates it is age
            age = tmp[0]
            is_validate_age = False
            post_match_field = words[i+1:i+match_range]
            if i>0 and int(age)%10 == 0:  # check if it satisfies the pattern: early,mid,late 30s
                if "early" in words[i-1].lower():
                    #result.append([age,str(int(age)+1),str(int(age)+2),str(int(age)+3)])
                    result.append(int(age)+2)
                    break
                if "mid" in words[i-1].lower():
                    #result.append([str(int(age)+4),str(int(age)+5),str(int(age)+6)])
                    result.append(int(age)+5)
                    break
                if "late" in words[i-1].lower():
                    #result.append([str(int(age)+7),str(int(age)+8),str(int(age)+9)])
                    result.append(int(age)+8)
                    break
            for word in post_match_field:
                if word.lower() in post_match_words:
                    is_validate_age = True
                    break
            pre_match_field = words[i-match_range:i]
            for word in pre_match_field:
                if word.lower() in pre_match_words:
                    is_validate_age = True
                    break
            if is_validate_age:
                result.append(int(age))
    birthday_pattern = re.compile(r"(?i)birthday[^A-Za-z0-9]{1,3}((?:19[0-9]{2})|(?:20[01][0-9]))")  #pattern of bodyrubresumes.com
    birthday_pattern_result = re.findall(birthday_pattern,text)
    for item in birthday_pattern_result:
        result.append(2016-int(item))
    if "extractions" in document["_source"]:
        crawl_extractions = document["_source"]["extractions"]
        if "age" in crawl_extractions:
            for age in crawl_extractions["age"]["results"]:
                if age.isdigit():
                    if int(age) not in result:
                        result.append(age)
    return result
    # age_pattern1 = re.compile(r"(?i)age[^A-Za-z0-9]{1,3}([1-6][0-9])[^A-Za-z0-9]")
    # age_pattern2 = re.compile(r"((?i)(?:i'm|im|i am)?[^A-Za-z0-9]?[1-6][0-9])(?:[^A-Za-z0-9]?(?i)(?:years|yrs|year)[^A-Za-z0-9](?:old)?)")
    # #early: 1,2,3; mid: 4,5,6; late: 7,8,9
    # age_pattern3 = re.compile(r"((early|mid|late) ([1-9]0)'?s)")
    # age_pattern1_result = re.findall(age_pattern1,text)
    # age_pattern2_result = re.findall(age_pattern2,text)
    # age_pattern3_result = re.findall(age_pattern3,text)
    # for item in age_pattern1_result+age_pattern2_result+age_pattern3_result:
    #     result.append(item[0])
    # return result


def nationality_recognition(document,is_raw_content):
    text = ""
    if is_raw_content:
        text = get_raw_content(document)
    else:
        text = get_text(document)
    nationality_filepath = "./resource/nationality"
    with open(nationality_filepath) as f:
        nationality_list = ','.join(f.readlines()).split(",")
        f.close()
        words = text.split()
        #raw_words = raw_content.split()
        text_result = []
        #raw_content_result = []
        for word in words:
            word_norm = word.lower().capitalize()
            if word_norm in nationality_list:
                text_result.append(result_normalize(word_norm))
        # for word in raw_words:
        #     word_norm = word.lower().capitalize()
        #     if word_norm in nationality_list:
        #         raw_content_result.append(result_normalize(word_norm))
        # if len(text_result)>len(raw_content_result):
        #     return text_result
        # else:
        #     return raw_content_result
        return text_result


def ethnicity_recognition(document,is_raw_content):
    text = ""
    if is_raw_content:
        text = get_raw_content(document)
    else:
        text = get_text(document)
    nationality_filepath = "./resource/nationality"
    ethnicity_arr = ["caucasian", "hispanic", "asian", "african american", "caribbean", "pacific islander", "middle eastern", "biracial" , "south asian", "native american"]
    result = []
    f = open(nationality_filepath)
    nationality_list = ','.join(f.readlines()).split(",")
    f.close()
    text = re.sub("\W"," ",text)
    words = text.split()
    for word in words:
            word_norm = word.lower().capitalize()
            if word_norm in nationality_list:
                result.append(word_norm)
    lowercase_text = text.lower()
    for word in ethnicity_arr:
        if word in lowercase_text:
            result.append(word)
    return result

def price_recognition(document,is_raw_content):
    text = ""
    if is_raw_content:
        text = get_raw_content(document)
    else:
        text = get_text(document)
    price1 = "(\d+,)?(\d+\.)?\d+"
    # price2 = "(^(\$|€|¥|£|$|Fr|¥|kr|Ꝑ|ք|₩|R|(R$)|₺|₹)\d+)"
    price2 = "((\$|€|¥|£|Fr|kr|Ꝑ)\d+)"
    units = "(Z|zero)|(O|one)|(T|two)|(T|three)|(F|four)|(F|five)|(S|six)|(S|seven)|(E|eight)|(N|nine)|(T|ten)|(E|eleven)|(T|twelve)|(T|thirteen)|(F|fourteen)|(F|fifteen)|(S|sixteen)|(S|seventeen)|(E|eighteen)|(N|nineteen)"
    tens = "(T|ten)|(T|twenty)|(T|thirty)|(F|forty)|(F|fourty)|(F|fifty)|(S|sixty)|(S|seventy)|(E|eighty)|(N|ninety)"
    hundred = "(H|hundred)"
    thousand = "(T|thousand)"
    OPT_DASH = "-?"
    price3 = "(" + units + OPT_DASH + "(" + thousand + ")?" + OPT_DASH + "(" + units + OPT_DASH + hundred + ")?" + OPT_DASH + "(" + tens + ")?" + ")" + "|" + "(" + tens + OPT_DASH + "(" + units + ")?" + ")"
    price4 = "\d+"
    # price5 = "(\d+(\$|€|¥|£|$|Fr|¥|kr|Ꝑ|ք|₩|R|(R$)|₺|₹)$)"
    price5 = "(\d+(\$|€|¥|£|Fr|kr|Ꝑ))"
    preDollarPrice = [price1, price3, price4]
    otherPrice = [price2, price5]
    split = text.split(" ")
    priceList = []
    currency = ["$", "€", "¥", "£", "$", "Fr", "¥", "kr", "Ꝑ", "ք", "₩", "R", "R$", "₺", "₹"]
    pre_price_indicator = ["Hour:", "night:", "price:", "Price:", "Hourly"]
    post_price_indicator = ["dollar", "dollars", "jewel", "jewels", "rose", "roses", "/hour", "/Hour", "/HOUR", "/night", "/Night", "/NIGHT", "$"] 
    for i in range(len(split)):
        if split[i] in post_price_indicator:
            for pricePat in preDollarPrice:
                #print((split[i], split[i - 1]))
                price = re.findall(pricePat, split[i - 1])
                if price:
                    priceList.append('$' + re.sub('\D', '', split[i - 1]))  
                    #print(priceList[i-1])
        elif split[i] in pre_price_indicator:
            for pricePat in preDollarPrice:
                price = re.findall(pricePat, split[i + 1])
                if price:
                    #print((split[i], split[i + 1]))
                    for cur in currency:
                        if cur in split[i + 1]:
                            priceList.append(cur + re.sub('\D', '', split[i + 1]))
                        else:
                            priceList.append('$' + re.sub('\D', '', split[i + 1]))
        else:
            for pricePat in otherPrice:
                price = re.findall(pricePat, split[i])
                if price:
                    priceList.append(price[0][0])
                    #print(price[0][0])
                #print(priceList[i])
    return(priceList)

def hair_color_recognition(document,is_raw_content):
    text = ""
    if is_raw_content:
        text = get_raw_content(document)
    else:
        text = get_text(document)
    normalized_color = ["blonde", "brown", "black", "red", "auburn", "chestnut", "gray", "white","dark"]
    color_dic = webcolors.CSS3_NAMES_TO_HEX
    for color in normalized_color:
        if color not in color_dic:
            color_dic[color] = "1"
    text_result = []
    text_without_quotation = re.sub(r'[^\w\s]','',text)
    words = text_without_quotation.split()
    for i in range(len(words)):
        if fuzz.ratio(words[i].lower(),"hair")>=75: #judge if word and hair are similar
            color_str = ""
            eye_color = False
            for j in range(i+1,i+6): #look for color vocabulary after hair
                if j<len(words):
                    if words[j].lower() in color_dic:
                        color_str = words[j].lower()
                    if fuzz.ratio(words[i].lower(),"eyes")>=75: #check if eyes color is around
                        eye_color = True
            if color_str:
                if eye_color:
                    hair_color_str = ""
                    for j in range(i-5,i):
                        if words[j].lower() in color_dic:
                            hair_color_str = words[j].lower()
                    if hair_color_str:
                        text_result.append(hair_color_str)
                    else:
                        text_result.append(color_str)
                else:
                    text_result.append(color_str)
            else:
                hair_color_str = ""
                for j in range(i-5,i):
                    if words[j].lower() in color_dic:
                        hair_color_str = words[j].lower()
                if hair_color_str:
                    text_result.append(hair_color_str)
    return text_result

def eye_color_recognition(document,is_raw_content):
    text = ""
    if is_raw_content:
        text = get_raw_content(document)
    else:
        text = get_text(document)
    normalized_color = ["blue", "brown", "green", "hazel", "gray", "amber"]
    color_dic = webcolors.CSS3_NAMES_TO_HEX
    for color in normalized_color:
        if color not in color_dic:
            color_dic[color] = "1"
    text_result = []
    text_without_quotation = re.sub(r'[^\w\s]','',text)
    words = text_without_quotation.split()
    for i in range(len(words)):
        if fuzz.ratio(words[i].lower(),"eyes")>=75: #judge if word and hair are similar
            color_str = ""
            hair_color = False
            for j in range(i+1,i+6): #look for color vocabulary after eyes
                if words[j].lower() in color_dic:
                    color_str = words[j].lower()
                if fuzz.ratio(words[i].lower(),"hair")>=75: #check if eyes color is around
                    hair_color = True
            if color_str:
                if hair_color:
                    eye_color_str = ""
                    for j in range(i-5,i):
                        if words[j].lower() in color_dic:
                            eye_color_str = words[j].lower()
                    if eye_color_str:
                        text_result.append(eye_color_str)
                    else:
                        text_result.append(color_str)
                else:
                    text_result.append(color_str)
            else:
                eye_color_str = ""
                for j in range(i-5,i):
                    if words[j].lower() in color_dic:
                        eye_color_str = words[j].lower()
                if eye_color_str:
                    text_result.append(eye_color_str)
    return text_result

def services_recognition(document,is_raw_content):
    """
    :param document: Dictionary
    :param is_raw_content: Boolean
    :return: List[str] containing all distinct service that is in the document as well as in the local service list
    """
    text = ""
    if is_raw_content:
        text = get_raw_content(document)
    else:
        text = get_text(document)
    result = []
    for service in service_list:
        if service == "69":
            pattern = r"\W69\W"
            if re.search(pattern,text):
                result.append("69")
        else:
            service_item = service.lower()
            if service_item in text.lower():
                result.append(service_item)
    return result

def tattoo_recognition(document,is_raw_content):
    return ""

def multi_providers(document,is_raw_content):
    return number_of_individuals_recognition(document,is_raw_content)

def height_recognition(document,is_raw_content):
    text = ""
    if is_raw_content:
        text = get_raw_content(document)
    else:
        text = get_text(document)
    #inch pattern
    height_pattern = r"(?:^|\W)([3-9])'[ ]?([0-9])?(?:\")?"
    height_pattern_result = re.findall(height_pattern,text)
    result = []
    for item in height_pattern_result:
        if item[1]: #inch is present
            result.append(str(int(item[0])*12+int(item[1])))
        else:
            result.append(str(int(item[0])*12))
    #cm pattern
    return result

def weight_recognition(document,is_raw_content):
    text = ""
    if is_raw_content:
        text = get_raw_content(document)
    else:
        text = get_text(document)
    weight_pattern = r"(?:^|\D)([\d]{2,3})[^A-Za-z0-9]?(?i)(kg|lb)"
    weight_pattern_result = re.findall(weight_pattern,text)
    result = []
    if len(weight_pattern_result)>0:
        for item in weight_pattern_result:
            if item[1] == "kg":
                result.append(str(int(float(item[0])*2.2)))
            else:
                result.append(item[0])
    return result

#############################################################################

def organization_recognition(document,is_raw_content):
    # text = ""
    # if is_raw_content:
    #     text = get_raw_content(document)
    # else:
    #     text = get_text(document)
    annotated_text = ""
    if is_raw_content:
        annotated_text = document["annotated_raw_content"]
    else:
        annotated_text = document["annotated_clean_content"]
    organization_pattern = re.compile(r"\<ORGANIZATION\>(.*?)\</ORGANIZATION>")
    organization_pattern_result = re.findall(organization_pattern,annotated_text)
    result = []
    if len(organization_pattern_result)>0:
        for item in organization_pattern_result:
            result.append(result_normalize(item))
    return result

#return all the extracted dates in dictioanry format -- date_dic = {day:int month:int year: int}, if date is not exact(more than a week ago), use an interval(int_low,int_high) instead
def posting_date_recognition(document,is_raw_content):
    text = ""
    if is_raw_content:
        text = get_raw_content(document)
    else:
        text = get_text(document)
    #digit date pattern like 8/7/2000, 2000/7/8
    month = r"((?:0?[1-9])|(?:1[0-2]))"
    day = r"((?:0?[1-9])|(?:[12][0-9])|(?:[3][01]))"
    year = r"((?:19[0-9]{2})|(?:20[01][0-9]))"
    conjunction = r"[^A-Za-z0-9]"
    month_day_year = "("+month+conjunction+day+conjunction+year+")"
    day_month_year = "("+day+conjunction+month+conjunction+year+")"
    year_month_day = "("+year+conjunction+month+conjunction+day+")"
    digit_date_pattern = month_day_year+"|"+day_month_year+"|"+year_month_day
    digit_date_pattern_result = re.findall(digit_date_pattern,text)
    result = []
    for item in digit_date_pattern_result:
        dic = {}
        if len(item[0])>0:
            dic["month"] = item[1]
            dic["day"] = item[2]
            dic["year"] = item[3]
        elif len(item[4])>0:
            dic["day"] = item[5]
            dic["month"] = item[6]
            dic["year"] = item[7]
        elif len(item[8])>0:
            dic["year"] = item[9]
            dic["month"] = item[10]
            dic["day"] = item[11]
        if len(dic)>0:
            date_int = int(dic["year"])*(10**4)+int(dic["month"])*(10**2)+int(dic["day"])
            result.append(date_int)

    #str_digit pattern like Jan 8th 2001
    month_str = r"(?i)(January|Jan|February|Feb|March|Mar|April|Apr|May|June|Jun|July|Jul|August|Aug|September|Sep|October|Oct|November|Nov|December|Dec)"
    day_str = r"((?:[1-3]?1(?i)(?:st)?)|(?:[1-2]?2(?i)(?:nd)?)|(?:[1-2]?3(?i)(?:rd)?)|(?:[1-3]?[04-9](?i)(?:th)?))"
    month_day_pattern = "("+month_str+r"[^A-Za-z0-9]"+day_str+r"[^A-Za-z0-9]{1,2}"+year+"(?:[^A-Za-z0-9])"+")"
    day_month_pattern = "("+day_str+r"[^A-Za-z0-9]"+month_str+r"[^A-Za-z0-9]{1,2}"+year+"(?:[^A-Za-z0-9])"+")"
    str_date_pattern = month_day_pattern+"|"+day_month_pattern
    str_date_pattern_result = re.findall(str_date_pattern,text)
    month_dic = {"jan":1,"january":1, "feb": 2, "february": 2, "mar": 3, "march": 3, "apr": 4, "april": 4, "may": 5, "june": 6, "jun": 6, "july": 7, "jul": 7, "august": 8, "aug": 8, "september": 9, "sep": 9, "october": 10, "oct": 10, "november": 11, "nov": 11, "december": 12, "dec": 12}
    for item in str_date_pattern_result:
        dic = {}
        if item[0]:
            dic["month"] = month_dic[item[1].lower()]
            dic["day"] = re.sub("[A-Za-z]","",item[2])
            dic["year"] = item[3]
        else:
            dic["month"] = month_dic[item[6].lower()]
            dic["day"] = re.sub("[A-Za-z]","",item[5])
            dic["year"] = item[7]
        if len(dic)>0:
            date_int = int(dic["year"])*(10**4)+int(dic["month"])*(10**2)+int(dic["day"])
            result.append(date_int)
            
    #relative date pattern like 10 months ago, more than a week a ago
    # number_str = r"((?i)(?:[1-3]?[0-9])|a|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|thirteen|fourteen|fifteen|sixteen|seventeen|eighteen|nineteen|twenty)"
    # number_dic = {"a":1,"one":1,"two":2,"three":3,"four":4,"five":5,"six":6,"seven":7,"eight":8,"nine":9,"ten":10,"eleven":11,"twelve":12,"thirteen":13,"fourteen":14,"fifteen":15,"sixteen":16,"seventeen":17,"eighteen":18,"nineteen":19,"twenty":20}
    # relative_date_pattern = r"(?i)(more than|less than|over)?[^A-Za-z0-9]"+ number_str+r"[^A-Za-z0-9](day|week|month|year)(?:s)?[^A-Za-z0-9]ago"
    # relative_date_pattern_result = re.findall(relative_date_pattern,text)
    # current_date = date.today()
    # result = []
    # for item in relative_date_pattern_result:
    #     dic = {}
    #     if item[1] in number_dic:
    #         time_interval = number_dic[item[1]]
    #     else:
    #         time_interval = int(item[1])
    #     if len(item[0]) == 0:
    #         if item[2] == "day":
    #             post_date = current_date - timedelta(days = time_interval)
    #         elif item[2] == "week":
    #             post_date = current_date - timedelta(weeks = time_interval)
    #         elif item[2] == "month":
    #             post_date = current_date - timedelta(days = time_interval*30)
    #         else:
    #             post_date = current_date - timedelta(days = time_interval*365)
    #         dic["day"] = post_date.day
    #         dic["month"] = post_date.month
    #         dic["year"] = post_date.year
    #     else:
    #         if item[0] == "more than" or item[0] == "over":
    #             if item[2] == "day":
    #                 post_date_high = current_date - timedelta(days = time_interval-1)
    #                 post_date_low = current_date - timedelta(days = time_interval)
    #             elif item[2] == "week":
    #                 post_date_high = current_date - timedelta(weeks = time_interval-1)
    #                 post_date_low = current_date - timedelta(weeks = time_interval)
    #             elif item[2] == "month":
    #                 post_date_high = current_date - timedelta(days = (time_interval-1)*30)
    #                 post_date_low = current_date - timedelta(days = (time_interval)*30)
    #             else:
    #                 post_date_high = current_date - timedelta(days = (time_interval-1)*365)
    #                 post_date_low = current_date - timedelta(days = (time_interval)*365)
    #             dic["day"] = (post_date_low.day,post_date_high.day)
    #             dic["month"] = (post_date_low.month,post_date_high.month)
    #             dic["year"] = (post_date_low.year,post_date_high.year)
    #         else:
    #             if item[2] == "day":
    #                 post_date_high = current_date - timedelta(days = time_interval)
    #                 post_date_low = current_date - timedelta(days = time_interval+1)
    #             elif item[2] == "week":
    #                 post_date_high = current_date - timedelta(weeks = time_interval)
    #                 post_date_low = current_date - timedelta(weeks = time_interval+1)
    #             elif item[2] == "month":
    #                 post_date_high = current_date - timedelta(days = time_interval*30)
    #                 post_date_low = current_date - timedelta(days = (time_interval+1)*30)
    #             else:
    #                 post_date_high = current_date - timedelta(days = time_interval*365)
    #                 post_date_low = current_date - timedelta(days = (time_interval+1)*365)
    #             dic["day"] = (post_date_low.day,post_date_high.day)
    #             dic["month"] = (post_date_low.month,post_date_high.month)
    #             dic["year"] = (post_date_low.year,post_date_high.year)
    #     result.append(dic)
    return result



def gender_recognition(document,is_raw_content):
    text = ""
    if is_raw_content:
        text = get_raw_content(document)
    else:
        text = get_text(document)
    result = []
    gender_list = ["male","female","transsexual"]
    if "extractions" in document["_source"]:
        crawl_extractions = document["_source"]["extractions"]
        if "gender" in crawl_extractions:
            genders = crawl_extractions["gender"]["results"]
            for item in genders:
                for gender in gender_list:
                    if fuzz.ratio(item,gender)>=80:
                        result.append(gender)
    if len(result) == 0:
        male_words = ["ladies","girls","boy"]
        female_words = ["boys","gentlemen","girl"]
        for word in female_words:
            if word in text:
                result.append(word)
    return result


def number_of_individuals_recognition(document,is_raw_content):
    text = ""
    if is_raw_content:
        text = get_raw_content(document)
    else:
        text = get_text(document)
    if "twin" in text:
        return [2]
    names = name_recognition(document,is_raw_content)
    for i in range(len(names)):
        names[i] = result_normalize(names[i])
    names = list(set(names))
    eye_colors = eye_color_recognition(document,is_raw_content)
    hair_colors = hair_color_recognition(document,is_raw_content)
    ages = age_recognition(document,is_raw_content)
    nationalities = nationality_recognition(document,is_raw_content)
    ethnicities = ethnicity_recognition(document,is_raw_content)
    number_list = [names,eye_colors,hair_colors,ages,nationalities,ethnicities]
    #print(number_list)
    number_list.sort(key=lambda k:len(k))
    result = 0
    for item in number_list:
        if len(item) >0:
            result = len(item)
            break
    if result == 0:
        return [1]
    else:
        return [result]

def review_id_recognition(document,is_raw_content):
    url = document["_source"]["cleaned_url"] + "/"      # Add a non-num and non-alph character in case review id is right at the end of url
    pattern = "(?:[^A-Za-z0-9])([0-9]{5,})(?:[^A-Za-z0-9])"
    review_id = re.findall(pattern, url)
    return review_id

def title_recognition(document,is_raw_content):
    result = []
    if "extractions" in document["_source"]:
        crawl_extractions = document["_source"]["extractions"]
        if "title" in crawl_extractions:
            if "results" in crawl_extractions["title"]:
                result = crawl_extractions["title"]["results"][:]
                for i in range(len(result)):
                    result[i] = result_normalize(result[i])
    return result

def business_recognition(document,is_raw_content):
    text = get_text(document)
    business = []
    business_name = business_name_recognition(document,is_raw_content)
    business_address = address_recognition(document,is_raw_content)
    if business_name:
        for name in business_name:
            name = result_normalize(name)
            business.append(name)
    if business_address:
        for address in business_address:
            address = result_normalize(address)
            business.append(address)
    return business

def business_type_recognition(document,is_raw_content):
    text = ""
    if is_raw_content:
        text = get_raw_content(document)
    else:
        text = get_text(document)
    business_type_found = []
    business_type = ["massage", "spa", "escort agency", "escort-agency"]
    for business in business_type:
        pattern = "(?:[^A-Za-z])(?i)(" + business + ")(?:$|[^A-Za-z])"
        results = re.findall(pattern, text)
        if results:
            for res in results:
                business_type_found.append(result_normalize(res))
    return business_type_found

def business_name_recognition(document,is_raw_content):
    return organization_recognition(document,is_raw_content)

def result_normalize(result):
    normedResult = ""
    if type(result) is str:
        normedResult = re.sub("[^\w\s]"," ",result.lower())
    return normedResult

def hyperlink_recognition(document,is_raw_content):
    text = ""
    if is_raw_content:
        text = get_raw_content(document)
    else:
        text = get_text(document)
    pattern = "href=\"(.*?)\""
    hyperlinks = re.findall(pattern, text)
    return hyperlinks

def drug_use_recognition(document,is_raw_content):
    result = []
    text = ""
    if is_raw_content:
        text = get_raw_content(document)
    else:
        text = get_text(document)
    cleaned_text = re.sub("[^\w\s]"," ",text)
    words = cleaned_text.split()
    for i in range(len(words)):
        if fuzz.ratio(words[i].lower(),"drug")>=80:
            drug_use = "true"
            for word in words[i-3:i+4]:
                if word.lower == "no":
                    result.append("false")
                    drug_use = "false"
                    break
                if drug_use:
                    result.append("true")
    return result

def multiple_phone_recognition(document,is_raw_content):
    result = phone_recognition(document,is_raw_content)
    return list(set(result))

def top_level_domain_recognition(document,is_raw_conent):
    path = "resource/Seed_TLDs_7.15.2016.txt"
    parentUrl = document["_source"]["cleaned_url"]
    findTLD = False
    result = []
    with open(path) as inputFile:
        TLDs = inputFile.readlines()
        for TLD in TLDs:
            TLD = TLD.strip("\n")
            if parentUrl.find(TLD) != -1:
                findTLD = True
                result.append(TLD)
                break
            else:
                continue
        if findTLD == False:
            if parentUrl.startswith("http://"):
                url = parentUrl[len("http://"):]
            elif parentUrl.startswith("https://"):
                url = parentUrl[len("https://")]
            else:
                url = parentUrl
            url = url[:url.find("/")]
            url_parts = url.split(".")
            TLD = url_parts[-2] + "." + url_parts[-1]
            result.append(TLD)
    return result

def image_with_phone_recognition(document):
    return []

def image_with_email_recognition(document):
    return []

def obfuscation_recognition(document):
    return []

def image_with_review_id_recognition(document):
    return []

def image_with_tattoo_recognition(document):
    return []

def image_in_hotel_motel_room_recognition(document):
    return []

def image_without_professional_lighting_recognition(document):
    return []

def color_recognition(document,is_raw_content):
    text = ""
    if is_raw_content:
        text = get_raw_content(document)
    else:
        text = get_text(document)
    color_dic = webcolors.CSS3_NAMES_TO_HEX
    text_without_quotation = re.sub(r'[^\w\s]',' ',text)
    words = text_without_quotation.split()
    result = {}
    for i in range(len(words)):
        if words[i].lower() in color_dic:
            result[i] = words[i]
    return result


if __name__ != "__main__":
    global functionDic
    functionDic = {"address": address_recognition,"age":age_recognition,
                   "name":name_recognition, "hair_color":hair_color_recognition,"eye_color":eye_color_recognition,"nationality":nationality_recognition,
                   "ethnicity":ethnicity_recognition,"review_site":review_site_recognition,"email": email_recognition,"phone": phone_recognition,
                   "location":location_recognition,"price":price_recognition,"number_of_individuals": number_of_individuals_recognition,
                    "social_media_id":social_media_id_recognition,"services":services_recognition,"height":height_recognition,"weight":weight_recognition
                   }
    global feature_list
    feature_list = ["address","age","name","hair_color","eye_color","nationality","ethnicity","review_site","email","phone","location","posting_date","price","number_of_individuals","gender","review_id","title","business","business_type","business_name","services","hyperlink","multiple_phone","top_level_domain"]

    normalized_color = ["blonde", "brown", "black", "red", "auburn", "chestnut", "gray", "white","dark", "blue", "brown", "green", "hazel", "amber"]
    global color_list
    color_dic = webcolors.CSS3_NAMES_TO_HEX.keys()
    color_list = color_dic
    for color in normalized_color:
        if color not in color_dic:
            color_list.append(color)

    global nationality_list
    nationality_filepath = "./resource/nationality"
    with open(nationality_filepath) as f:
        nationality_list = ','.join(f.readlines()).split(",")
        f.close()
    ethnicity_arr = ["caucasian", "hispanic", "asian", "african american", "caribbean", "pacific islander", "middle eastern", "biracial", "south asian", "native american"]
    nationality_list += ethnicity_arr

    global service_list
    service_list_path = "./resource/serviceList.txt"
    service_list = []
    with open(service_list_path, "r") as inputFile:
        services = inputFile.readlines()
        for i in range(len(services)):
           service_list.append(services[i].strip())

    global review_site_list
    review_site_list = ["eccie", "TER", "preferred411"]

    global country_abbr_list
    country_abbr_path = "./resource/country_abbr"
    f = open(country_abbr_path)
    line = f.readlines()[0]
    country_abbr_list = yaml.load(line)

    global state_abbr_dic
    state_abbr_path = "state_abbr"
    w = open(state_abbr_path)
    state_abbr_dic = json.load(w)
    w.close()

