__author__ = 'infosense'
import os,json
import search
dir = "JPL/JPL_PF"
output = "JPL/JPL_Point_Fact.json"
querypath = "post_point_fact.json"
querylist = search.query_retrival(querypath)
result = []

out = open(output,"w")
for file in os.listdir(dir):
    if not file.startswith("."):
        filepath = os.path.join(dir,file)
        f = open(filepath)
        answer = json.load(f)
        f.close()
	#if len(answer["answers"])>500:
	#    answer["answers"] = answer["answers"][:500]
	#answer["question_id"] = str(answer["question_id"])
       	#json.dump(answer,out)
	#out.write("\n")
	dic = {}
        if len(answer["answers"]) > 500:
            dic["answer"] = answer["answers"][:500]
        else:
            dic["answer"] = answer["answers"][:500]
        #print(dic["answer"])
	#for aggregate question only
	#if dic["answer"] and type(dic["answer"][0]) is list:
	#    dic["answer"][0] = dic["answer"][0][0]
	dic["id"] = answer["question_id"]
        for query in querylist:
            if query["id"] == answer["question_id"]:
                dic["type"] = query["type"]
        result.append(dic)

f = open(output,"w")
json.dump(result,f)
f.close()
