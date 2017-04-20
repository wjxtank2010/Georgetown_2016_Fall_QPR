# -*- coding: utf-8 -*-
import re,sys,json,yaml,os,webcolors,search,collections
from fuzzywuzzy import fuzz
from nltk.corpus import stopwords
from datetime import date,timedelta
import ebola_html_dealer as html_cleaner
#import phonenumbers


def get_text(document):
    if "extracted_text" in document["_source"]:
        extract_text = document["_source"]["extracted_text"]
        if extract_text:
            return extract_text
    try:
        extract_text = html_cleaner.make_clean_html(get_raw_content(document))
    except Exception as e:
        extract_text = ""
    #document["extracted_text"] = extract_text
    return ""

def get_raw_content(document):
    if "raw_content" in document["_source"]:
        return document["_source"]["raw_content"]
    else:
        return ""

#extraction
#features: phone,email,street address, social media ID, review site ID, name, location, age, nationality/Ethnicity, price, tattoos, multiple provides, hair color, services, height, weight, eyecolor

def phone_recognition(document,is_raw_content,is_position): #retrieve distinct phone number
    """
    :param document:Dictionary
    :param is_raw_content: Boolean
    :param position:
    :return: List[str] containing all the distinct phone number in raw_content or extracted_text
    """
    text = ""
    if "TLD" in document:
        text = document["TLD"]
    else:
        if is_raw_content:
            text = get_raw_content(document)
        else:
            text = get_text(document)
    result = []
    number_pattern = r"(?:^|\D)([0-9]{3})[^A-Za-z0-9]{0,3}([0-9]{3})[^A-Za-z0-9]{0,2}([0-9]{3,6})(?:\D|$)" #Mainly retrieve national phone numbers
    if is_position:
        for item in re.finditer(number_pattern,text):
            result.append((item.start()*1.0/len(text),"".join(item.groups())))
    else:
        for item in re.findall(number_pattern,text):
            result.append("".join(item))

    inter_phone_pattern = r"(?:^|\D)\+?(\d{2})[ -_]?(\d{9,10})(?:$|\D)" #Retrieve international phone numebrs with regional number at the beginning.
    if is_position:
        for item in re.finditer(inter_phone_pattern,text):
            result.append((item.start()*1.0/len(text),"".join(item.groups())))
    else:
        for item in re.findall(inter_phone_pattern,text):
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


def email_recognition(document,is_raw_content,is_position):
    text = ""
    if "TLD" in document:
        text = document["TLD"]
    else:
        if is_raw_content:
            text = get_raw_content(document)
        else:
            text = get_text(document)
    regex = re.compile(("([a-z0-9!#$%&'*+\/=?^_`{|}~-]+(?:\.[a-z0-9!#$%&'*+\/=?^_`"
                    "{|}~-]+)*(@|\sat\s)(?:[a-z0-9](?:[a-z0-9-]*[a-z0-9])?(\.|"
                    "\sdot\s))+[a-z0-9](?:[a-z0-9-]*[a-z0-9])?)"))
    result = []
    if is_position:
        for item in re.finditer(regex,text):
            if not item.group().startswith("//") and "@" in item.group():
                result.append((item.start()*1.0/len(text),item.group(0)))
    else:
        text_result = re.findall(regex,text)
        for email in text_result:
            if not email[0].startswith('//') and "@" in email[0]:
                result.append(email[0].lower())
    TLD = top_level_domain_recognition(document)
    if TLD:
        cleaned_TLD = TLD[0].split('.')[0]
        i = 0
        length = len(result)
        while i < length:
            if "@" in result[i]:
                if cleaned_TLD in result[i][:result[i].index('@')]:
                    del result[i]
                    length -= 1
                else:
                    i += 1
            else:
                i += 1
    return result

def address_recognition(document,is_raw_content,is_position):
    text = ""
    if "TLD" in document:
        text = document["TLD"]
    else:
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
        #print(item)
        address_parts = item[0].split()
        if len(address_parts)>2:   #although only street number and streeName are required in the pattern, address consists of at least three parts.
            isValid = False
            for part in address_parts:
                if part.lower() in streetTypeString.lower() or part.lower() in nsew.lower():
                    isValid = True
            if isValid:
                if is_position: #Find the index of the name of the street
                    if item[5] in text:
                        result.append((text.index(item[5])*1.0/len(text),result_normalize(item[0])))
                    else:
                        result.append((0.5,result_normalize(item[0])))
                else:
                    result.append(result_normalize(item[0]))
    return result

def social_media_id_recognition(document,is_raw_content,is_position):
    """
    :param document:
    :param is_raw_content:
    :return: a list containing all the social media ID
    """
    social_media_list = ["facebook","instagram","twitter"]
    text = ""
    if "TLD" in document:
        text = document["TLD"]
    else:
        if is_raw_content:
            text = get_raw_content(document)
        else:
            text = get_text(document)
    result = []
    media_str = "|".join(social_media_list)
    #extract social media ID in a url
    url_media_pattern = r"(%s)(?:.com)?/([^\"/]+)"%media_str
    url_media_pattern_result = re.findall(url_media_pattern,text)
    if is_position:
        for item in re.finditer(url_media_pattern,text):
            if "share" not in item.groups()[1]:
                result.append((item.start()*1.0/len(text),item.groups()[0]+"@"+item.groups()[1]))
    else:
        for item in url_media_pattern_result:
            if "share" not in item[1]:
                result.append(item[0]+"@"+item[1])
    #extract social media ID in plain text
    plain_text_pattern = r"(%s): (\w+)\W"
    plain_text_pattern_result = re.findall(plain_text_pattern,text)
    if is_position:
        for item in re.finditer(plain_text_pattern,text):
            result.append((item.start(),item.groups()[0]+"@"+item.groups()[1]))
    else:
        for item in plain_text_pattern_result:
            result.append(item[0]+"@"+item[1])
    return result


def review_site_id_recognition(document,is_raw_content,is_position):
    #url_pattern = re.compile(r'(http[s]?://)|(www.)(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\(\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+')
    text = ""
    if "TLD" in document:
        text = document["TLD"]
    else:
        if is_raw_content:
            text = get_raw_content(document)
        else:
            text = get_text(document)
    # review_site_list = ["eccie", "TER", "preferred411"]
    # review_site = []
    # hyperlinks = hyperlink_recognition(document,is_raw_content,is_position)
    # for link in hyperlinks:
    #     tmp = link
    #     for site in review_site_list:
    #         if is_position:
    #             tmp = link[1]
    #             if site in tmp:
    #                 if site == "eccie.net":
    #                     site = "eccie"
    #                 if site == "theeroticreview":
    #                     site = "TER"
    #                 if is_position:
    #                     review_site.append((tmp[0],site))
    #                 else:
    #                     review_site.append(site)
    result = []
    url = document["_source"]["url"] + "/"      # Add a non-num and non-alph character in case review id is right at the end of url
    pattern = "(?:[^A-Za-z0-9])([0-9]{5,})(?:[^A-Za-z0-9])"
    if is_position:
        for item in re.finditer(pattern,text):
            result.append((item.start()/len(text),item.groups()[0]))
    else:
        result += re.findall(pattern, url)
    text_pattern = "(?i)id(?:\:|#) ?(\w+)(?:\W|$)"
    if is_position:
        for item in re.finditer(pattern,text):
            result.append((item.start()/len(text),item.groups()[0]))
    else:
        result += re.findall(text_pattern,text)
    return result

def name_recognition(document,is_raw_content,is_position):
    annotated_text = ""
    if is_raw_content:
        annotated_text = document["annotated_raw_content"]
    else:
        annotated_text = document["annotated_clean_content"]
    name_pattern = re.compile(r"\<PERSON\>(.*?)\</PERSON>")
    name_pattern_result = re.findall(name_pattern,annotated_text)
    result = []
    if is_position:
        for item in re.finditer(name_pattern,annotated_text):
            result.append((item.start()*1.0/len(annotated_text),"".join(item.groups())))
    else:
        for item in name_pattern_result:
            result.append(result_normalize(item))
    return result

def location_recognition(document,is_raw_content,is_position):
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
    location_pattern = r"\<LOCATION\>(.*?)\</LOCATION\>"
    location_arr = re.findall(r"\<LOCATION\>(.*?)\</LOCATION\>",annotated_text)
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
        # words = annotated_text.split()
        # for i in range(len(words)):
        #     if "<LOCATION>" in words[i]:
        #         result.append(i)
    if is_position:
        for item in re.finditer(location_pattern,annotated_text):
            result.append((item.start()*1.0/len(annotated_text),"".join(item.groups())))
    else:
        for location in location_arr:
            result.append(result_normalize(location))
    #print(result)
    # if document["_id"] == "AVisQxg3SNqSfhMS-sfy":
    #     print(result)
    return result

def age_recognition(document,is_raw_content,is_position):
    text = ""
    if "TLD" in document:
        text = document["TLD"]
    else:
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
                    if is_position:
                        result.append((i*1.0/len(words),int(age)+2))
                    else:
                        result.append(int(age)+2)
                    break
                if "mid" in words[i-1].lower():
                    #result.append([str(int(age)+4),str(int(age)+5),str(int(age)+6)])
                    if is_position:
                        result.append((i*1.0/len(words),int(age)+5))
                    else:
                        result.append(int(age)+5)
                    break
                if "late" in words[i-1].lower():
                    #result.append([str(int(age)+7),str(int(age)+8),str(int(age)+9)])
                    if is_position:
                        result.append((i*1.0/len(words),int(age)+8))
                    else:
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
                if is_position:
                    result.append((i*1.0/len(words),int(age)))
                else:
                    result.append(int(age))
    birthday_pattern = re.compile(r"(?i)birthday[^A-Za-z0-9]{1,3}((?:19[0-9]{2})|(?:20[01][0-9]))")  #pattern of bodyrubresumes.com
    birthday_pattern_result = re.findall(birthday_pattern,text)
    if is_position:
        for item in re.finditer(birthday_pattern,text):
            result.append((item.start(),2016-int(item.groups()[0])))
    else:
        for item in birthday_pattern_result:
            result.append(2016-int(item))
    # if "extractions" in document["_source"]:
    #     crawl_extractions = document["_source"]["extractions"]
    #     if "age" in crawl_extractions:
    #         for age in crawl_extractions["age"]["results"]:
    #             if age.isdigit():
    #                 if int(age) not in result:
    #                     result.append(age)
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


def nationality_recognition(document,is_raw_content,is_position):
    text = ""
    if "TLD" in document:
        text = document["TLD"]
    else:
        if is_raw_content:
            text = get_raw_content(document)
        else:
            text = get_text(document)
    nationality_filepath = "./resource/nationality"
    with open(nationality_filepath) as f:
        nationality_list = ','.join(f.readlines()).split(",")
        f.close()
        text_without_quotation = re.sub(r"[^\w\s]"," ",text)
        words = text_without_quotation.split()
        text_result = []
        for i in range(len(words)):
            word_norm = words[i].lower().capitalize()
            if word_norm in nationality_list:
                if is_position:
                    text_result.append((i*1.0/len(words),result_normalize(word_norm)))
                else:
                    text_result.append(result_normalize(word_norm))
        return text_result


def ethnicity_recognition(document,is_raw_content,is_position):
    text = ""
    if "TLD" in document:
        text = document["TLD"]
    else:
        if is_raw_content:
            text = get_raw_content(document)
        else:
            text = get_text(document)
    result = []
    #text = re.sub(r"\\n|\\t"," ",text)
    text = re.sub("\W"," ",text)
    words = text.split()
    #print(words)
    for i in range(len(words)):
            word_norm = words[i].lower().capitalize()
            if word_norm in nationality_list:
                if is_position:
                    result.append((i*1.0/len(words),word_norm))
                else:
                    result.append(word_norm)
    lowercase_text = text.lower()
    for word in ethnicity_arr:
        if word in lowercase_text:
            if is_position:
                result.append((lowercase_text.index(word)/len(lowercase_text),word))
            else:
                result.append(word)
    return result

# def price_recognition(document,is_raw_content,is_position):
#     text = ""
#     if "TLD" in document:
#         text = document["TLD"]
#     else:
#         if is_raw_content:
#             text = get_raw_content(document)
#         else:
#             text = get_text(document)
#     price1 = "(\d+,)?(\d+\.)?\d+"
#     # price2 = "(^(\$|€|¥|£|$|Fr|¥|kr|Ꝑ|ք|₩|R|(R$)|₺|₹)\d+)"
#     price2 = "((\$|€|¥|£|Fr|kr|Ꝑ)\d+)"
#     units = "(Z|zero)|(O|one)|(T|two)|(T|three)|(F|four)|(F|five)|(S|six)|(S|seven)|(E|eight)|(N|nine)|(T|ten)|(E|eleven)|(T|twelve)|(T|thirteen)|(F|fourteen)|(F|fifteen)|(S|sixteen)|(S|seventeen)|(E|eighteen)|(N|nineteen)"
#     tens = "(T|ten)|(T|twenty)|(T|thirty)|(F|forty)|(F|fourty)|(F|fifty)|(S|sixty)|(S|seventy)|(E|eighty)|(N|ninety)"
#     hundred = "(H|hundred)"
#     thousand = "(T|thousand)"
#     OPT_DASH = "-?"
#     price3 = "(" + units + OPT_DASH + "(" + thousand + ")?" + OPT_DASH + "(" + units + OPT_DASH + hundred + ")?" + OPT_DASH + "(" + tens + ")?" + ")" + "|" + "(" + tens + OPT_DASH + "(" + units + ")?" + ")"
#     price4 = "\d+"
#     # price5 = "(\d+(\$|€|¥|£|$|Fr|¥|kr|Ꝑ|ք|₩|R|(R$)|₺|₹)$)"
#     price5 = "(\d+(\$|€|¥|£|Fr|kr|Ꝑ))"
#     preDollarPrice = [price1, price3, price4]
#     otherPrice = [price2, price5]
#     split = text.split(" ")
#     # priceDict = collections.OrderedDict()
#     priceDict = {}
#     currency = ["$", "€", "¥", "£", "$", "Fr", "¥", "kr", "Ꝑ", "ք", "₩", "R", "R$", "₺", "₹"]
#     pre_price_indicator = ["Hour:", "night:", "price:", "Price:", "Hourly", "H/H", "H", "special", "Special", "price", "Price", "$", "€", "¥", "£", "Fr", "kr", "Ꝑ", "Rate", "rate"]
#     post_price_indicator = ["dollar", "dollars", "jewel", "jewels", "rose", "roses", "/hour", "/Hour", "/HOUR", "/night", "/Night", "/NIGHT", "$", "H/H", "H", "AM", "PM", "all", "include", "All", "Include"]
#     time1 = "(\d)(\d)?((AM)|(PM))(-)(-)?(\d)(\d)?((AM)|(PM))"
#     time2 = "(\d)(\d)?((AM)|(PM))(to)(\d)(\d)?((AM)|(PM))"
#     time_indicator = [time1, time2]
#     ans = []
#     for i in range(len(split)):
#         # cur = split[i]
#         # print(cur)
#         if split[i] in post_price_indicator:
#             for pricePat in preDollarPrice:
#                 #print((split[i], split[i - 1]))
#                 price = re.findall(pricePat, split[i - 1])
#                 if price:
#                     # priceDict[i - 1] = ('$' + re.sub('\D', '', split[i - 1]))
#                     if i - 1 not in priceDict:
#                         priceDict[i - 1] = split[i - 1]
#                 if i not in priceDict:
#                     priceDict[i] = split[i]
#                     #print(priceList[i-1])
#         if split[i] in pre_price_indicator:
#             for pricePat in preDollarPrice:
#                 price = re.findall(pricePat, split[i + 1])
#                 if price:
#                     #print((split[i], split[i + 1]))
#                     # for cur in currency:
#                     #     if cur in split[i + 1]:
#                     #         priceList.append(cur + re.sub('\D', '', split[i + 1]))
#                     #     else:
#                     #         priceList.append('$' + re.sub('\D', '', split[i + 1]))
#
#                     if i + 1 not in priceDict:
#                         priceDict[i + 1] = split[i + 1]
#                 if i not in priceDict:
#                     priceDict[i] = split[i]
#
#         for pricePat in otherPrice:
#             price = re.findall(pricePat, split[i])
#             if price:
#                 if i not in priceDict:
#                     priceDict[i] = price[0][0]
#                 #print(price[0][0])
#             #print(priceList[i])
#         for timePat in time_indicator:
#             time = re.findall(timePat, split[i])
#             if time:
#                 if i not in priceDict:
#                     priceDict[i] = split[i]
#     priceDict = collections.OrderedDict(sorted(priceDict.items(), key=lambda t: t[0]))
#     prevKey = 0
#     price = ""
#     for key in priceDict:
#         # print(priceDict[key])
#         if key - prevKey <= 2:
#             price += ' ' + priceDict[key]
#         else:
#             if price != "":
#                 price = price.strip(" ")
#                 if is_position:
#                     ans += (key/len(split),price),
#                 else:
#                     ans += price,
#                 price = priceDict[key]
#         prevKey = key
#     if price != "":
#         price = price.strip(" ")
#         if is_position:
#             ans += (prevKey/len(split),price),
#         else:
#             ans += price,
#     # return(priceDict)
#     return(ans)

def price_recognition(document,is_raw_content,is_position):
    text = ""
    if "TLD" in document:
        text = document["TLD"]
    else:
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
    # priceDict = collections.OrderedDict()
    priceDict = {}
    currency = ["$", "€", "¥", "£", "$", "Fr", "¥", "kr", "Ꝑ", "ք", "₩", "R", "R$", "₺", "₹"]
    pre_price_indicator = ["Hour:", "night:", "price:", "Price:", "Hourly", "H/H", "H", "special", "Special", "price", "Price", "$", "€", "¥", "£", "Fr", "kr", "Ꝑ", "Rate", "rate"]
    post_price_indicator = ["dollar", "dollars", "jewel", "jewels", "rose", "roses", "/hour", "/Hour", "/HOUR", "/night", "/Night", "/NIGHT", "$", "H/H", "H", "AM", "PM", "all", "include", "All", "Include"]
    time1 = "(\d)(\d)?((AM)|(PM))(-)(-)?(\d)(\d)?((AM)|(PM))"
    time2 = "(\d)(\d)?((AM)|(PM))(to)(\d)(\d)?((AM)|(PM))"
    time_indicator = [time1, time2]
    ans = []
    for i in range(1,len(split)-1):
        # cur = split[i]
        # print(cur)
        if split[i] in post_price_indicator:
            for pricePat in preDollarPrice:
                #print((split[i], split[i - 1]))
                price = re.findall(pricePat, split[i - 1])
                if price:
                    # priceDict[i - 1] = ('$' + re.sub('\D', '', split[i - 1]))
                    if i - 1 not in priceDict:
                        if re.findall('(\d+)', split[i - 1]):
                            priceDict[i - 1] = re.findall('(\d+)', split[i - 1])[0]
                    # if i not in priceDict:
                    #     priceDict[i] = split[i]
                    #print(priceList[i-1])
        if split[i] in pre_price_indicator:
            for pricePat in preDollarPrice:
                price = re.findall(pricePat, split[i + 1])
                if price:
                    #print((split[i], split[i + 1]))
                    # for cur in currency:
                    #     if cur in split[i + 1]:
                    #         priceList.append(cur + re.sub('\D', '', split[i + 1]))
                    #     else:
                    #         priceList.append('$' + re.sub('\D', '', split[i + 1]))

                    if i + 1 not in priceDict:
                        if re.findall('(\d+)', split[i + 1]):
                            priceDict[i + 1] = re.findall('(\d+)', split[i + 1])[0]
                    # if i not in priceDict:
                    #     priceDict[i] = split[i]

        for pricePat in otherPrice:
            price = re.findall(pricePat, split[i])
            if price:
                if i not in priceDict:
                    if re.findall('(\d+)', price[0][0]):
                        priceDict[i] = re.findall('(\d+)', price[0][0])[0]
                #print(price[0][0])
            #print(priceList[i])
        # for timePat in time_indicator:
        #     time = re.findall(timePat, split[i])
        #     if time:
        #         if i not in priceDict:
        #             priceDict[i] = split[i]
    # priceDict = collections.OrderedDict(sorted(priceDict.items(), key=lambda t: t[0]))
    # prevKey = 0
    # price = ""
    for key in priceDict:
        # print(priceDict[key])
        # if key - prevKey <= 2:
        #     price += ' ' + priceDict[key]
        # else:
        #     if price != "":
        #         price = price.strip(" ")
        if is_position:
            ans += (key/len(split),priceDict[key]),
        else:
            ans += priceDict[key],
        # price = priceDict[key]
    #     prevKey = key
    # if price != "":
    #     price = price.strip(" ")
    #     if is_position:
    #         ans += (prevKey/len(split),price),
    #     else:
    #         ans += price,
    for i in range(len(ans)):
        if type(i) is list:
            ans.pop(i)
    return ans

def hair_color_recognition(document,is_raw_content,is_position):
    text = ""
    if "TLD" in document:
        text = document["TLD"]
    else:
        if is_raw_content:
            text = get_raw_content(document)
        else:
            text = get_text(document)
    if not text:
        return []
    normalized_color = ["blonde", "brown", "black", "red", "auburn", "chestnut", "gray", "white","dark"]
    color_dic = webcolors.CSS3_NAMES_TO_HEX
    if "tan" in color_dic:
        del color_dic["tan"]
    for color in normalized_color:
        if color not in color_dic:
            color_dic[color] = "1"
    text_result = []
    text_without_quotation = re.sub(r'[^\w\s]','',text)
    words = text_without_quotation.split()
    #position = -4
    for i in range(len(words)):
        if words[i].lower() == "hair": #judge if word and hair are similar
            color_str = ""
            eye_color = False
            # if is_position:
            #     position += text[position+4:].index(words[i])
            for j in range(i+1,i+3): #look for color vocabulary after hair
                if j<len(words):
                    if words[j].lower() in color_dic:
                        color_str = words[j].lower()
                    if fuzz.ratio(words[j].lower(),"eyes")>=75: #check if eyes color is around
                        eye_color = True
            if color_str:
                if eye_color:
                    hair_color_str = ""
                    for j in range(i-2,i):
                        if words[j].lower() in color_dic:
                            hair_color_str = words[j].lower()
                    if hair_color_str:
                        if is_position:
                            text_result.append((i*1.0/len(words),hair_color_str))
                        else:
                            text_result.append(hair_color_str)
                    else:
                        if is_position:
                            text_result.append((i*1.0/len(words),color_str))
                        else:
                            text_result.append(color_str)
                else:
                    if is_position:
                        text_result.append((i*1.0/len(words),color_str))
                    else:
                        text_result.append(color_str)
            else:
                hair_color_str = ""
                for j in range(i-2,i):
                    if words[j].lower() in color_dic:
                        hair_color_str = words[j].lower()
                if hair_color_str:
                    if is_position:
                        text_result.append((i*1.0/len(words),hair_color_str))
                    else:
                        text_result.append(hair_color_str)
    return text_result

def eye_color_recognition(document,is_raw_content,is_position):
    text = ""
    if "TLD" in document:
        text = document["TLD"]
    else:
        if is_raw_content:
            text = get_raw_content(document)
        else:
            text = get_text(document)
    if not text:
        return []
    normalized_color = ["blue", "brown", "green", "hazel", "gray", "amber"]
    color_dic = webcolors.CSS3_NAMES_TO_HEX
    if "tan" in color_dic:
        del color_dic["tan"]
    for color in normalized_color:
        if color not in color_dic:
            color_dic[color] = "1"
    text_result = []
    text_without_quotation = re.sub(r'[^\w\s]','',text)
    words = text_without_quotation.split()
    #position = -4
    for i in range(len(words)):
        if words[i] == "eye" or words[i] == "eyes": #judge if word and eyes are similar
            color_str = ""
            hair_color = False
            # if is_position:
            #     position += text[position+4:].index(words[i])
            for j in range(i+1,min(len(words),i+3)): #look for color vocabulary after eyes
                if words[j].lower() in color_dic:
                    color_str = words[j].lower()
                if words[i].lower() == "hair": #check if eyes color is around
                    hair_color = True
            if color_str:
                if hair_color:
                    eye_color_str = ""
                    for j in range(i-2,i):
                        if words[j].lower() in color_dic:
                            eye_color_str = words[j].lower()
                    if eye_color_str:
                        if is_position:
                            text_result.append((i*1.0/len(words),eye_color_str))
                        else:
                            text_result.append(eye_color_str)
                    else:
                        if is_position:
                            text_result.append((i*1.0/len(words),color_str))
                        else:
                            text_result.append(color_str)
                else:
                    if is_position:
                        text_result.append((i*1.0/len(words),color_str))
                    else:
                        text_result.append(color_str)
            else:
                eye_color_str = ""
                for j in range(i-2,i):
                    if words[j].lower() in color_dic:
                        eye_color_str = words[j].lower()
                if eye_color_str:
                    if is_position:
                        text_result.append((i*1.0/len(words),eye_color_str))
                    else:
                        text_result.append(eye_color_str)
    return text_result

def services_recognition(document,is_raw_content,is_position):
    """
    :param document: Dictionary
    :param is_raw_content: Boolean
    :return: List[str] containing all distinct service that is in the document as well as in the local service list
    """
    if "TLD" in document:
        text = document["TLD"]
    else:
        if is_raw_content:
            text = get_raw_content(document)
        else:
            text = get_text(document)
    result = []
    text = text.lower()
    for service in service_list:
        pattern = r"(?i)\W"+service+"\W"
        if is_position:
            for item in re.finditer(pattern,text):
                result.append((item.start()*1.0/len(text),service))
        else:
            if re.search(pattern,text):
                result.append(service)
    return result

def tattoos_recognition(document,is_raw_content,is_position):
    return []

def multi_providers(document,is_raw_content,is_position):
    text = ""
    if "TLD" in document:
        text = document["TLD"]
    else:
        if is_raw_content:
            text = get_raw_content(document)
        else:

            text = get_text(document)
    if "twin" in text:
        return [2]
    text = text.lower()
    two_providers_list = ["my friend","my sister","and me"]
    for words in two_providers_list:
        if words in text:
            return [2]

def height_recognition(document,is_raw_content,is_position):
    """
    :param document: Dictionary
    :param is_raw_content: Bool
    :param is_position: Bool
    :return: list[int] in cm unit
    """
    if "TLD" in document:
        text = document["TLD"]
    else:
        if is_raw_content:
            text = get_raw_content(document)
        else:
            text = get_text(document)
    #inch pattern
    inch_pattern = r"(?:^|\W)([3-9])'[ ]?([0-9])?(?:\")?"
    inch_pattern_result = re.findall(inch_pattern,text)
    result = []
    if is_position:
        for item in re.finditer(inch_pattern,text):
            if item.groups()[1]:
                result.append( ( item.start()*1.0/len(text),int((int(item.groups()[0])*12+int(item.groups()[1]))*2.54) ))
            else:
                result.append(( item.start()*1.0/len(text),int((int(item.groups()[0]*12))*2.54) ))
    else:
        for item in inch_pattern_result:
            if item[1]: #inch is present
                result.append(int((int(item[0])*12+int(item[1]))*2.54))
            else:
                result.append(int((int(item[0])*12)*2.54))
    #cm pattern
    cm_pattern = r"(?:^|\W)([12][0-9]{2})[ ]?cm(?:\W|$)"
    if is_position:
        for item in re.finditer(cm_pattern,text):
            result.append( (item.start()*1.0/len(text),int(item.groups()[0])) )
    else:
        for item in re.findall(cm_pattern,text):
            result.append(int(item))
    #print(result)
    if result:
	if type(result[0]) == int:
    	    result = filter(lambda x:x<220,result)
        else:
	    result = filter(lambda x:x[1]<220,result)
    return result

def weight_recognition(document,is_raw_content,is_position):
    """
    :param document: Dictionary
    :param is_raw_content: Bool
    :param is_position: Bool
    :return: list[int]: in lbs unit
    """
    if "TLD" in document:
        text = document["TLD"]
    else:
        if is_raw_content:
            text = get_raw_content(document)
        else:
            text = get_text(document)
    weight_pattern = r"(?:^|\D)([\d]{2,3})[^A-Za-z0-9]?(?i)(kg|lb)"
    weight_pattern_result = re.findall(weight_pattern,text)
    result = []
    if is_position:
        for item in re.finditer(weight_pattern,text):
            if item.groups()[1] == "kg":
                result.append( (item.start()*1.0/len(text),int(float(item.groups()[0])*2.2) ) )
            else:
                result.append((item.start()*1.0/len(text),int(item.groups()[0])))
    else:
        for item in weight_pattern_result:
            if item[1] == "kg":
                result.append(int(float(item[0])*2.2))
            else:
                result.append(item[0])
    return result

#return all the extracted dates in dictioanry format -- date_dic = {day:int month:int year: int}, if date is not exact(more than a week ago), use an interval(int_low,int_high) instead
def posting_date_recognition(document,is_raw_content,is_position):
    text = ""
    if "TLD" in document:
        text = document["TLD"]
    else:
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
    digit_month = {1:"January",2:"February",3:"March",4:"April",5:"May",6:"June",7:"July",8:"August",9:"September",10:"October",11:"November",12:"December"}
    result = []
    for item in digit_date_pattern_result:
        dic = {}
        if len(item[0])>0:
            dic["month"] = item[1]
            if len(item[1]) == 1:
                dic["month"] = "0"+item[1]
            dic["day"] = item[2]
            if len(item[2]) == 1:
                dic["day"] = "0"+item[2]
            dic["year"] = item[3]
        elif len(item[4])>0:
            dic["day"] = item[5]
            if len(item[5]) == 1:
                dic["day"] = "0"+item[5]
            dic["month"] = item[6]
            if len(item[6]) == 1:
                dic["month"] = "0"+item[6]
            dic["year"] = item[7]
        elif len(item[8])>0:
            dic["year"] = item[9]
            dic["month"] = item[10]
            if len(item[10]) == 1:
                dic["month"] = "0"+item[10]
            dic["day"] = item[11]
            if len(item[11]) == 1:
                dic["day"] = "0"+item[11]
        #print(dic)
        if len(dic)>0:
            date_str = dic["year"]+"-"+dic["month"]+"-"+dic["day"]
            if is_position:
                result.append((0.5,date_str))
            else:
                result.append(date_str)

    #str_digit pattern like Jan 8th 2001
    month_str = r"(?i)(January|Jan|February|Feb|March|Mar|April|Apr|May|June|Jun|July|Jul|August|Aug|September|Sep|October|Oct|November|Nov|December|Dec)"
    day_str = r"((?:[1-3]?1(?i)(?:st)?)|(?:[1-2]?2(?i)(?:nd)?)|(?:[1-2]?3(?i)(?:rd)?)|(?:[1-3]?[04-9](?i)(?:th)?))"
    month_day_pattern = "("+month_str+r"[^A-Za-z0-9]"+day_str+r"[^A-Za-z0-9]{1,2}"+year+"(?:[^A-Za-z0-9])"+")"
    day_month_pattern = "("+day_str+r"[^A-Za-z0-9]"+month_str+r"[^A-Za-z0-9]{1,2}"+year+"(?:[^A-Za-z0-9])"+")"
    str_date_pattern = month_day_pattern+"|"+day_month_pattern
    str_date_pattern_result = re.findall(str_date_pattern,text)
    month_dic = {"jan":"01","january":"01", "feb": "02", "february": "02", "mar": "03", "march": "03", "apr": "04", "april": "04", "may": "05", "june": "06", "jun": "06", "july": "07", "jul": "07", "august": "08", "aug": "08", "september": "09", "sep": "09", "october": "10", "oct": "10", "november": "11", "nov": "11", "december": "12", "dec": "12"}
    for item in str_date_pattern_result:
        dic = {}
        if item[0]:
            dic["month"] = month_dic[item[1].lower()]
            dic["day"] = re.sub("[A-Za-z]","",item[2])
            if len(dic["day"]) == 1:
                dic["day"] = "0"+dic["day"]
            dic["year"] = item[3]
        else:
            dic["month"] = month_dic[item[6].lower()]
            dic["day"] = re.sub("[A-Za-z]","",item[5])
            if len(dic["day"]) == 1:
                dic["day"] = "0"+dic["day"]
            dic["year"] = item[7]
        if len(dic)>0:
            date_str = dic["year"]+"-"+dic["month"]+"-"+dic["day"]
            if is_position:
                result.append((0.5,date_str))
            else:
                result.append(date_str)

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

def title_recognition(document,is_raw_content,is_position):
    return []

def content_recognition(document,is_raw_content,is_position):
    return []

def top_level_domain_pattern(document):
    path = "TLD_list.txt"
    parentUrl = document["_source"]["url"]
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
    return result

def top_level_domain_recognition(document):
    parentUrl = document["_source"]["url"]
    result = []
    if parentUrl.startswith("http://"):
        url = parentUrl[len("http://"):]
    elif parentUrl.startswith("https://"):
        url = parentUrl[len("https://")]
    else:
        url = parentUrl
    url = url[:url.find("/")]
    url_parts = url.split(".")
    if len(url_parts)>=2:
        TLD = url_parts[-2] + "." + url_parts[-1]
        result.append(TLD)
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


def review_id_recognition(document,is_raw_content):
    url = document["_source"]["cleaned_url"] + "/"      # Add a non-num and non-alph character in case review id is right at the end of url
    pattern = "(?:[^A-Za-z0-9])([0-9]{5,})(?:[^A-Za-z0-9])"
    review_id = re.findall(pattern, url)
    return review_id


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

def hyperlink_recognition(document,is_raw_content,is_position):
    text = ""
    if is_raw_content:
        text = get_raw_content(document)
    else:
        text = get_text(document)
    pattern = "href=\"(.*?)\""
    result = []
    if is_position:
        for item in re.finditer(pattern,text):
            result.append((item.start(),"".join(item.groups())))
    else:
        for item in re.findall(pattern,text):
            result.append(item)
    return result

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


################################################
#Feature Functions Determining The correct Value
###############################################
# def phone_position(document):
#
#
# def eye_position(document):
#
#
# def hair_position(document):
#
#
# def email_position(document):
#
#
# def weight_position(document):
#
#
# def height_position(document):
#
#
# def services_position(document):

##############################################

if __name__ != "__main__":
    global functionDic
    functionDic = {"post_date":posting_date_recognition,"tattoos":tattoos_recognition,"street_address": address_recognition,"age":age_recognition,
                   "name":name_recognition, "hair_color":hair_color_recognition,"eye_color":eye_color_recognition,"nationality":nationality_recognition,
                   "ethnicity":ethnicity_recognition,"review_site_id":review_site_id_recognition,"email": email_recognition,"phone": phone_recognition,
                   "location":location_recognition,"price":price_recognition,"multiple_providers": multi_providers,"title":title_recognition,"content":content_recognition,
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
    os.system("pwd")
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
    f.close()
    country_abbr_list = yaml.load(line)

    global state_abbr_dic
    state_abbr_path = "./resource/state_abbr"
    w = open(state_abbr_path)
    state_abbr_dic = json.load(w)
    w.close()

    global continent_dic
    continent_dic_path = "./resource/nation_continent.txt"
    f = open(continent_dic_path)
    continent_dic = yaml.load(f)
    f.close()

