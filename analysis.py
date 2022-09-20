import csv
import json
import re
import numpy as np
import matplotlib.pyplot as plt
import django
from django.conf import settings
from django.template import Template,Context
from django.template.defaulttags import register

@register.filter
def get_item(dictionary, key):
    return dictionary.get(key)



job_info = json.load(open("c:/cucumber-result/release-canary-test-2.json","r"))
qa_case = "QA-23890"
step = "The policy should be saved by"
res = {}

Templates = [
    {
        'BACKEND':'django.template.backends.django.DjangoTemplates'
    }
]

settings.configure(TEMPLATES=Templates)

django.setup()

for buildNum in job_info:
    build_res = job_info[buildNum]
    for scenario in build_res["scenarioes"]:
        if scenario["scenario"].find(qa_case) >=0:
            if scenario["scenario"] not in res:
                res[scenario["scenario"]] = []
            scenario_res = res[scenario["scenario"]]
            scenario_item= {"build" : buildNum}
            scenario_item["version"]= build_res["PORTAL VERSION"]
            steps = scenario["steps"]
            for step_info in steps:
                if step_info["name"].find(step) >=0:
                    for key in step_info:
                        if key == "duration":
                            duration = step_info[key]
                            m = re.search('(\d+)m\s*(\d+)s\s*(\d+)ms', duration)
                            if m:                                
                                scenario_item["duration"] = float(m.group(1)) * 60 + float(m.group(2)) + float(m.group(3))/1000
                        else:
                            scenario_item[key] = step_info[key]
                    break
            scenario_res = res[scenario["scenario"]].append(scenario_item)
scenario_list=[]
for key in res:
    scenario_list.append({"name":key, "rows":res[key],"image":"./"+key+".jpg"})
    fieldnames =[field for field in res[key][0].keys()]
    fieldnames.sort()
    dictWriter = csv.DictWriter(open(key+".csv","w",newline=''),fieldnames) 
    dictWriter.writeheader()
    res[key].sort(key=lambda x:x["build"])
    dictWriter.writerows(res[key])     

context = {"fields":fieldnames,"scenarios":scenario_list}
template = open("analysis.template","r").read()
html = Template(template).render(Context(context))
open("index.html","w").write(html)

for scenario in res:
    plt.clf()
    xpoints = np.array([item["build"] for item in res[scenario]])      
    ypoints = np.array([item["duration"] for item in res[scenario]])
    plt.plot(xpoints,ypoints)
    plt.savefig(scenario+".jpg")
print(res)
                        
