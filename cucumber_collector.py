import json
import os
from os.path  import basename
import sys
from time import sleep
import jenkins
import requests
import bs4
from bs4 import BeautifulSoup
import argparse


def getScenario(case_result, lastCompletedBuild = False):
    try:
        response = server.jenkins_request(requests.Request('GET',case_result["scenario_url"]))
    except requests.exceptions.ConnectionError as e:
        sleep(2)
        print("Connection error ...")
        getScenario(case_result)
        return
    report_path = case_result["scenario_url"].rsplit("/",3)[0]
    soup = BeautifulSoup(response.text,"html.parser")
    li_infos = soup.find_all("li")
    check="pass"
    for li in li_infos:
        if "list-group-item" in li.attrs["class"]:
            line = " ".join([item for item in li.strings]).strip(" \n")
            

            if  li.parent.parent.text.strip("\n").split("\n")[0] == "Steps":
                case_result["steps"] = []
                for child in li.children:
                    if isinstance(child,bs4.element.Tag):
                        flag = None
                        for style in child.attrs["class"]:
                            if style in flags:
                                flag = style.split("-")[2]
                                check = flag
                                break
                        if flag:
                            step_res={"result":flag}
                            i=0
                            for item in child.contents:
                                if isinstance(item,bs4.element.Tag):
                                    if i <=2:
                                        step_res[step_keys[i]]=" ".join([ line for line in item.strings]).strip(" \n")
                                        i += 1
                                    if flag == "failed" and "scenarioErrorMessage" in item.attrs["class"]:
                                        pre = item.find("pre")
                                        step_res["error_message"] = "".join([line for line in pre.strings])
                                        # try:
                                        #     print(step_res["error_message"].encode(encoding='utf-8'))
                                        # except UnicodeEncodeError:
                                        #     pass
                            if child.find("table"):
                                step_res["table"] = []
                                table = child.find("table")
                                for line in table.find_all("tr"):
                                    row = []
                                    for td in line.find_all("td"):
                                        row.append("".join([item for item in td.strings]))
                                    step_res["table"].append(row)

                            case_result["steps"].append(step_res)
                        elif check == "failed" and lastCompletedBuild:
                            if "tags" in case_result:
                                for tag in case_result["tags"]:
                                    if tag.find("container") >= 0:
                                        tag = tag.strip("@")
                                        log_url = "/".join(case_result["scenario_url"].split("/")[:-4]) +"/artifact/console-" + tag + ".log"
                                        response = server.jenkins_request(requests.Request('GET', log_url))
                                        if response.text.find(case_result["scenario"]) > 0:
                                            start = response.text.find(case_result["scenario"])
                                            log_content = response.text[start:]
                                            start = log_content.find("============================================ START SCENARIO")
                                            log_content = log_content[start:]
                                            start = log_content.find(case_result["scenario"])
                                            log_content = log_content[start:]
                                            end = log_content.find(
                                                "============================================ START SCENARIO")
                                            case_result["console_log"] = log_content[:end]

                            if child.find("img"):
                                img_link = report_path + "/" + child.find("img").get("src")
                                step_res["img"] = case_result["job"] + "/" + basename(img_link)
                                img_name = step_res["img"]
                                with open(img_name, "wb") as f:
                                    f.write(server.jenkins_request(requests.Request("GET",img_link)).content)
                            else:
                                print("*** " + case_result["scenario_url"])

            elif len(li.contents) <= 3:
                if line.find("@") >= 0:
                    case_result["tags"] = line.split(",")
                    if line.find("container") >= 0:
                        case_result["tags"] = line.split(",")
                    # else:
                    #     print(line)
                else:
                    if line.find(":") > 0:
                        key, value = line.split(":", 1)
                    else:
                        value, key = line.split(" ", 1)
                    case_result[key.strip(" \n")] = value.strip(" \n")

            else:
                line_links = li.find_all("a")
                for line_link in line_links:
                    line = " ".join([item for item in line_link.strings]).strip(" \n")
                    if line.find("@") < 0:
                        value,key = line.split(" ",1)
                        case_result[key.strip(" \n")] = value.strip(" \n")
                    else:
                        if line.find("container") >= 0 :
                            case_result["tags"]=line.split(",")
                        # else:
                        #     print(line)


portal_keys = ["PORTAL URL","PORTAL VERSION"]
cucumber_test ="Cluecumber_20Test_20Report/index.html"
step_keys=["sequence","name","duration"]
flags = ["table-row-passed","table-row-failed","table-row-skipped"]

parser = argparse.ArgumentParser()
parser.add_argument("--username",help="username",required=True)
parser.add_argument("--passwords",help="passowrd",required=True)
parser.add_argument("--servers",help="Jenkins Server",required=True)
parser.add_argument("--jobs", help="job name list and delimiter ','",required=True)
parser.add_argument("--output",help="output path",required=True)
parser.add_argument("--reports",help="gluecumber job report naming map",required=True)
parser.add_argument("--runs",help="keep how many runs data",required=True)

args = parser.parse_args()

if __name__ == "__main__":    
    servers = args.servers.split(",")
    passwords = args.passwords.split(",")
    server_dict = dict(zip(servers,passwords))
    report_map = args.reports
    report_dict = {}
    for report_items in report_map.split("|"):
        report_name,job_list = report_items.split(":")
        for job_name in job_list.split(","):
            report_dict[job_name] = report_name
    runs = int(args.runs)
    for server_url in server_dict:
        server= jenkins.Jenkins(server_url, args.username, password=server_dict[server_url])
        all_jobs = server.get_jobs()
        jobs=[]
        job_names = args.jobs.split(",")
        for job in all_jobs:
            for job_name in job_names:
                if job["name"].find(job_name) == 0 and job["name"].lower().find("temp") < 0:
                    jobs.append(job)
        if not os.path.exists(args.output) :
            os.mkdir(args.output)

        for job in jobs:
            if job["name"] not in report_dict:
                continue
            res = {}
            job_info = server.get_job_info(job["name"])
            if not os.path.exists(job["name"]):
                os.mkdir(job["name"])
            output_file = args.output+ "/" + job["name"]+".json"
            if os.path.exists(output_file):
                res = json.load(open(output_file,"r"))
            builds = job_info["builds"]
            builds.sort(key=lambda x:x["number"],reverse=True)
            if len(builds) > runs:
                builds = builds[:runs]
            for build in builds:
                if build["number"] > job_info["lastCompletedBuild"]["number"] or \
                        str(build["number"]) in res:
                    continue
                try:
                    lastCompletedBuild = False
                    if build["number"] == job_info["lastCompletedBuild"]["number"]:
                        lastCompletedBuild = True
                    build_res={}
                    build_test_info = server.get_build_info(job["name"], build["number"])
                    if build_test_info["result"] == "ABORTED":
                        continue
                    cucumber_test_url = build_test_info["url"] + report_dict[job["name"]] + "/index.html"
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
                            for item in portal_keys:
                                try:
                                    if line.find(item) >= 0:
                                        key = item
                                        break
                                except TypeError as e:
                                    print(str(line) + ":" + str(item))
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
                                                    url = build_test_info["url"] + "/" + report_dict[job["name"]] + "/" + url
                                                    last_url_item = url_items[len(url_items)-1]
                                                    if last_url_item.find("feature") >=0:
                                                        case_result["feature_url"] = url
                                                        case_result["feature"] = (" ").join([line for line in link.strings])
                                                    if last_url_item.find("scenario") >=0:
                                                        case_result["scenario_url"] = url
                                                        case_result["scenario"] = (" ").join([line for line in link.strings])
                                    if "scenario_url" in case_result:
                                        case_result["job"] = job["name"]
                                        getScenario(case_result, lastCompletedBuild)
                                        build_res["scenarioes"].append(case_result)

                    res[str(build["number"])] = build_res
                except jenkins.NotFoundException as e :
                    continue
            keys = [int(run) for run in res]
            keys.sort(reverse=True)
            data = {}
            for run in keys[:runs]:
                data[str(run)] = res[str(run)]
            json.dump(data,open(output_file,"w"),indent=4)
            # print(output_file)
