import os,json,sys,datetime
import extraction,search,ebola_html_dealer

def index():
    reload(sys)
    sys.setdefaultencoding("utf-8")
    input_path = "/Users/infosense/Desktop/documents"
    output_path = "/Users/infosense/Desktop/indexed_documents"
    query_path = "sparql-queries-parsed-2016-07-23T11-11.json"
    query_list = search.query_retrival(query_path)
    for dir in os.listdir(input_path):
        if not dir.startswith("."):
            #create the output directory for each category of question with the same name as input category
            indexed_category_path = os.path.join(output_path,dir)
            if not os.path.exists(indexed_category_path):
                mkdir = "mkdir "+indexed_category_path
                os.system(mkdir)
            #do extration for each file in each category and then save the result in corresponding output path with same name
            category = os.path.join(input_path,dir)
            for query in os.listdir(category):
                if not query.startswith("."):
                    if query == "52":
                        parsed_query = {}
                        for query_item in query_list:
                            if query_item["id"] == query:
                                parsed_query = search.query_parse(query_item)
                                break
                        input_filepath = os.path.join(category,query)
                        output_filepath = os.path.join(indexed_category_path,query)
                        if not os.path.exists(output_filepath):
                            mkdir = "mkdir "+output_filepath
                            os.system(mkdir)
                        f = open(input_filepath)
                        documents = json.load(f)[:3000]
                        annotated_raw_contents,annotated_clean_contents = annotator(documents)
                        for i in range(len(documents)):
                            documents[i]["annotated_raw_content"] = annotated_raw_contents[i]
                            documents[i]["annotated_clean_content"] = annotated_clean_contents[i]
                            document_path = os.path.join(output_filepath,str(i))
                            w = open(document_path,"w")
                            extractions = {}
                            for func_name,func in extraction.functionDic.items():
                                extractions["raw_"+func_name] = func(documents[i],True)
                                extractions[func_name] = func(documents[i],False)
                            documents[i]["indexing"] = extractions
                            json.dump(documents[i],w)
                            w.close()
                        print(datetime.datetime.now())

def annotator(documents):
    #print(datetime.datetime.now())
    para_size = 300 #how many documents are annotated every time
    para_num = len(documents)/para_size
    separator = "wjxseparator" #used to join raw_content from different documents, combine them and annotate at one time
    indexed_raw_result = []
    indexed_clean_result = []
    for i in range(para_num):
        raw_contents = []
        clean_contents = []
        for j in range(i*para_size,(i+1)*para_size):
            raw_content = documents[j]["_source"]["raw_content"]
            raw_contents.append(raw_content)
            clean_content = ""
            if "extracted_text" in documents[j]["_source"] and documents[j]["_source"]["extracted_text"]:
                clean_content = documents[j]["_source"]["extracted_text"]
            else:
                clean_content = ebola_html_dealer.make_clean_html(raw_content)
            clean_contents.append(clean_content)
        raw_indexed = search.annotation(separator.join(raw_contents))
        clean_indexed = search.annotation(separator.join(clean_contents))
        indexed_raw_result += raw_indexed.split(separator)
        indexed_clean_result += clean_indexed.split(separator)
    return (indexed_raw_result,indexed_clean_result)

if __name__ == "__main__":
    index()
