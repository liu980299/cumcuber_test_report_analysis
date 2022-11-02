import json
import os
import sys
from time import sleep
import jenkins
import requests
import bs4
from bs4 import BeautifulSoup
import argparse


def getScenario(case_result):
    try:
        response = server.jenkins_request(requests.Request('GET',case_result["scenario_url"]))
    except requests.exceptions.ConnectionError as e:
        sleep(2)
        print("Connection error ...")
        getScenario(case_result)
        return

    soup = BeautifulSoup(response.text,"html.parser")
    li_infos = soup.find_all("li")
    for li in li_infos:
        if "list-group-item" in li.attrs["class"]:
            line = " ".join([item for item in li.strings]).strip(" \n")
            
            if len(li.contents) <= 3:
                if line.find(":") > 0:
                    key,value = line.split(":",1)
                elif line.find("@") < 0:
                    value,key = line.split(" ",1)
                case_result[key.strip(" \n")] = value.strip(" \n")
            elif  li.parent.parent.text.strip("\n").split("\n")[0] == "Steps":
                case_result["steps"] = []
                for child in li.children:
                    if isinstance(child,bs4.element.Tag):
                        flag = None
                        for style in child.attrs["class"]:
                            if style in flags:
                                flag = style.split("-")[2]
                                break
                        if flag:
                            step_res={"result":flag}
                            i=0
                            for item in child.contents:
                                if isinstance(item,bs4.element.Tag) and i <=2:
                                    step_res[step_keys[i]]=" ".join([ line for line in item.strings]).strip(" \n")
                                    i += 1
                            case_result["steps"].append(step_res)
            else:
                line_links = li.find_all("a")
                for line_link in line_links:
                    line = " ".join([item for item in line_link.strings]).strip(" \n")
                    if line.find("@") < 0:
                        value,key = line.split(" ",1)
                        case_result[key.strip(" \n")] = value.strip(" \n")
                    else:
                        case_result["tags"]=line.split(",")
                              

keys = ["PORTAL URL","PORTAL VERSION"]
cucumber_test ="Cluecumber_20Test_20Report/index.html"
step_keys=["sequence","name","duration"]
flags = ["table-row-passed","table-row-failed","table-row-skipped"]

parser = argparse.ArgumentParser()
parser.add_argument("--username",help="username",required=True)
parser.add_argument("--passwords",help="passowrd",required=True)
parser.add_argument("--servers",help="Jenkins Server",required=True)
parser.add_argument("--jobs", help="job name list and delimiter ','",required=True)
parser.add_argument("--output",help="output path",required=True)
parser.add_argument("--runs",help="keep how many runs data",required=True)

args = parser.parse_args()

if __name__ == "__main__":    
    servers = args.servers.split(",")
    passwords = args.passwords.split(",")
    server_dict = dict(zip(servers,passwords))
    runs = int(args.runs)
    for server_url in server_dict:
        server= jenkins.Jenkins(server_url, args.username, password=server_dict[server_url])
        all_jobs = server.get_jobs()
        jobs=[]
        job_names = args.jobs.split(",")
        for job in all_jobs:
            for job_name in job_names:
                if job["name"].find(job_name) == 0:
                    jobs.append(job)
        if not os.path.exists(args.output) :
            os.mkdir(args.output)

        for job in jobs:
            res = {}
            job_info = server.get_job_info(job["name"])            
            output_file = args.output+ "/" + job["name"]+".json"
            if os.path.exists(output_file):
                res = json.load(open(output_file,"r"))
            for build in job_info["builds"]:
                if build["number"] > job_info["lastCompletedBuild"]["number"] or str(build["number"]) in res:
                    continue
                try:
                    build_res={}
                    build_test_info = server.get_build_info(job["name"], build["number"])
                    if build_test_info["result"] == "ABORTED":
                        continue
                    cucumber_test_url = build_test_info["url"] + cucumber_test
                    response = server.jenkins_request(requests.Request('GET',cucumber_test_url))
                    soup = BeautifulSoup(response.text,"html.parser")
                    li_infos = soup.find_all("li")
                    for li in li_infos:
                        if "list-group-item" in li.attrs["class"]:
                            line = " ".join([item for item in li.strings]).strip(" \n")
                            if len(li.contents) <= 3:
                                if line.find(":") > 0:
                                    key,value = line.split(":",1)
                                else:
                                    value,key = line.split(" ",1)
                                build_res[key.strip(" \n")] = value.strip(" \n")
                            else:
                                line_links = li.find_all("a")
                                for line_link in line_links:
                                    line = " ".join([item for item in line_link.strings]).strip(" \n")
                                    value,key = line.split(" ",1)
                                    build_res[key.strip(" \n")] = value.strip(" \n")
                    trs = soup.find_all("tr")
                    build_res["scenarioes"] = []
                    for tr in trs:
                        key = None
                        for line in tr.strings:
                            for item in keys:
                                if line.find(item) >= 0:
                                    key = item
                                    break
                            if not line.strip("\n") == "" and key:
                                build_res[key] = line.strip(" \n")
                        if "class" in tr.attrs:
                            for style in tr.attrs["class"]:
                                if style in flags:
                                    case_result={}
                                    case_result["result"] = style.split("-")[2]
                                    for child in tr.children:
                                        if isinstance(child,bs4.element.Tag):
                                            if "data-order" in child.attrs:
                                                value = child.attrs["data-order"]
                                                if value.find("T") > 0:
                                                    case_result["start_time"] = value
                                                else:
                                                    case_result["duration"] = value
                                            else :
                                                links = child.find_all("a")
                                                for link in links:
                                                    url = link.attrs["href"]
                                                    url_items = url.split("/")
                                                    url = build_test_info["url"] + "/Cluecumber_20Test_20Report/" + url
                                                    last_url_item = url_items[len(url_items)-1]
                                                    if last_url_item.find("feature") >=0:
                                                        case_result["feature_url"] = url
                                                        case_result["feature"] = (" ").join([line for line in link.strings])
                                                    if last_url_item.find("scenario") >=0:
                                                        case_result["scenario_url"] = url
                                                        case_result["scenario"] = (" ").join([line for line in link.strings])
                                    if "scenario_url" in case_result:
                                        getScenario(case_result)
                                        build_res["scenarioes"].append(case_result)

                    res[str(build["number"])] = build_res
                except jenkins.NotFoundException as e :
                    continue
            keys = [run for run in res]
            keys.sort(reverse=True)
            data = {}
            for run in keys[:runs]:
                data[run] = res[run]
            json.dump(data,open(output_file,"w"),indent=4)
