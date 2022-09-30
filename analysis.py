import csv
import json
import re
import numpy as np
import matplotlib.pyplot as plt
import django
from django.conf import settings
from django.template import Template,Context
from django.template.defaulttags import register
import argparse,os,urllib.parse


parser = argparse.ArgumentParser()
parser.add_argument("--case",help="QA Case ID",required=True, default="QA-23890")
parser.add_argument("--step",help="cucumber feature step words", required=True, default="The policy should be saved by")
parser.add_argument("--input",help="Test Result folder", required=True, default="c:/cucumber-result/")
args = parser.parse_args()


Templates = [
    {
        'BACKEND':'django.template.backends.django.DjangoTemplates'
    }
]

settings.configure(TEMPLATES=Templates)

django.setup()
@register.filter
def get_item(dictionary, key):
    return dictionary.get(key)


if __name__ == "__main__":
    files = os.listdir(args.input)
    res = {}
    for file_name in files:
        if file_name.endswith(".json"):
            file_path = args.input + "/" + file_name
            job_name = file_name.split(".")[0]
            if job_name not in res:
                res[job_name] = {}
            job_info = json.load(open(file_path,"r"))
            qa_case = args.case
            step = args.step
            env_res = res[job_name]
            for buildNum in job_info:
                build_res = job_info[buildNum]
                if "PORTAL URL" in build_res:
                    env_res["URL"] = build_res["PORTAL URL"]

                for scenario in build_res["scenarioes"]:
                    if scenario["scenario"].find(qa_case) >=0 and 'result'in scenario and not scenario["result"] == "skipped":
                        if scenario["scenario"] not in env_res:
                            env_res[scenario["scenario"]] = []
                        scenario_res = env_res[scenario["scenario"]]
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
                        if scenario_item["result"] == "failed":
                            scenario_item["color"] = "red"
                        else:
                            scenario_item["color"] = "green"
                        scenario_res.append(scenario_item)
    envs = {}
    for key in res:
        if len(res[key]) > 1:
            envs[key] = {"scenarios":[],"URL":res[key]["URL"]}
            scenario_list = envs[key]["scenarios"]
            env_res = res[key]
            for scenario in env_res:
                if not scenario == "URL":
                    img_url=urllib.parse.quote(key + "-" + scenario)
                    scenario_list.append({"name":scenario, "rows":env_res[scenario],"image":"./"+img_url+".jpg"})
                    fieldnames =[field for field in env_res[scenario][0].keys()]
                    fieldnames.sort()
                    dictWriter = csv.DictWriter(open(key + "-" + scenario + ".csv","w",newline=''),fieldnames)
                    dictWriter.writeheader()
                    env_res[scenario].sort(key=lambda x:x["build"])
                    dictWriter.writerows(env_res[scenario])
    fieldnames.remove('color')
    context = {"fields":fieldnames,"envs":envs}
    template = open("analysis.template","r").read()
    html = Template(template).render(Context(context))
    open("index.html","w").write(html)
    plt.figure(figsize=(10.195,3.841, ), dpi=100)
    for env in res:
        for scenario in res[env]:
            if not scenario == "URL":
                plt.clf()
                xpoints = np.array([item["build"] for item in res[env][scenario]])
                ypoints = np.array([item["duration"] for item in res[env][scenario]])
                plt.plot(xpoints,ypoints)
                plt.savefig(env + "-" + scenario+".jpg")
    print(res)
                                    
